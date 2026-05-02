import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
import datetime
import re
from collections import defaultdict

st.set_page_config(page_title="Term Calendar", page_icon="📅", layout="wide")

HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

# SCOTUS term year = the October the term opens; current term started Oct 2025
TODAY        = datetime.date.today()
CURRENT_TERM = TODAY.year if TODAY.month >= 10 else TODAY.year - 1


MONTH_ORDER = [
    "October", "November", "December",
    "January", "February", "March",
    "April", "May", "June", "July", "August", "September",
]

STATUS_COLOR = {
    "Decided":         "#27AE60",
    "Argued":          "#3498DB",
    "Scheduled":       "#E67E22",
    "Cert Granted":    "#9B59B6",
    "Unknown":         "#95A5A6",
}

STATUS_ICON = {
    "Decided":      "✅",
    "Argued":       "🔵",
    "Scheduled":    "📅",
    "Cert Granted": "📌",
    "Unknown":      "❓",
}


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_term_summary(term: int) -> list[dict]:
    try:
        r = requests.get(
            f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=150&page=0",
            headers=HEADERS, timeout=12,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def parse_unix(ts) -> datetime.date | None:
    try:
        if ts:
            return datetime.date.fromtimestamp(int(ts))
    except Exception:
        pass
    return None


def extract_arg_date(oral_args: list) -> datetime.date | None:
    """Try to parse argument date from oral_argument_audio title strings."""
    months = {m[:3].lower(): i for i, m in enumerate(
        ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1
    )}
    for arg in oral_args or []:
        if not isinstance(arg, dict):
            continue
        title = arg.get("title", "")
        # e.g. "Oral Argument - October 5, 2022"  or  "October 5, 2022"
        m = re.search(
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
            title,
        )
        if m:
            month_s, day_s, year_s = m.group(1), m.group(2), m.group(3)
            mon = months.get(month_s[:3].lower())
            if mon:
                try:
                    return datetime.date(int(year_s), mon, int(day_s))
                except ValueError:
                    pass
    return None


def term_month_label(d: datetime.date, term: int) -> str:
    """Return 'October', 'November', … in term order."""
    return d.strftime("%B")


def status_of(detail: dict, arg_date: datetime.date | None, decided_date: datetime.date | None) -> str:
    if decided_date:
        return "Decided"
    if arg_date and arg_date <= TODAY:
        return "Argued"
    if arg_date and arg_date > TODAY:
        return "Scheduled"
    decisions = detail.get("decisions") or []
    if decisions:
        return "Decided"
    oral_args = detail.get("oral_argument_audio") or []
    if oral_args:
        return "Argued"
    return "Cert Granted"


# ── Load data ─────────────────────────────────────────────────────────────────
st.title("📅 SCOTUS Term Calendar")

available_terms = list(range(CURRENT_TERM, CURRENT_TERM - 10, -1))
term = st.selectbox(
    "Select Term",
    available_terms,
    format_func=lambda t: f"{t}–{t+1} Term",
)

with st.spinner(f"Loading {term}–{term+1} term docket…"):
    summary_cases = fetch_term_summary(term)

if not summary_cases:
    st.error("Could not load cases for this term. The Oyez API may not have data yet.")
    st.stop()

st.info(
    f"Found **{len(summary_cases)}** cases on the {term}–{term+1} docket. "
    "Loading details to determine argument and decision dates…"
)

# Load details with a progress bar
progress = st.progress(0.0, text="Fetching case details…")
cases_data = []

for i, c in enumerate(summary_cases):
    href = c.get("href", "")
    if href:
        detail = fetch_detail(href)
    else:
        detail = None

    if detail:
        decided_ts  = detail.get("decided_on")
        decided_date = parse_unix(decided_ts)

        oral_args   = detail.get("oral_argument_audio") or []
        arg_date    = extract_arg_date(oral_args)

        # Fallback: decided_on gives a rough anchor
        if not arg_date and decided_date:
            # Argument is typically ~3 months before decision
            arg_date_approx = None
        else:
            arg_date_approx = None

        ia = detail.get("issue_area") or {}
        issue = ia.get("label", "Unknown") if isinstance(ia, dict) else str(ia)

        disp = detail.get("disposition") or {}
        disp_label = disp.get("label", "") if isinstance(disp, dict) else str(disp)

        decisions = detail.get("decisions") or []
        vote_split = ""
        for dec in decisions:
            votes = dec.get("votes") or []
            maj = sum(1 for v in votes if (v.get("vote") or "").lower() in ("majority", "concurrence"))
            dis = sum(1 for v in votes if (v.get("vote") or "").lower() == "dissent")
            if maj or dis:
                vote_split = f"{maj}-{dis}"
                break

        status = status_of(detail, arg_date, decided_date)

        cases_data.append({
            "name":         detail.get("name", c.get("name", "")),
            "docket":       detail.get("docket_number", c.get("docket_number", "")),
            "issue_area":   issue,
            "status":       status,
            "arg_date":     arg_date,
            "decided_date": decided_date,
            "disposition":  disp_label,
            "vote_split":   vote_split,
            "href":         href,
            "has_audio":    len(oral_args) > 0,
        })
    else:
        cases_data.append({
            "name":         c.get("name", ""),
            "docket":       c.get("docket_number", ""),
            "issue_area":   "Unknown",
            "status":       "Unknown",
            "arg_date":     None,
            "decided_date": None,
            "disposition":  "",
            "vote_split":   "",
            "href":         href,
            "has_audio":    False,
        })

    progress.progress((i + 1) / len(summary_cases), text=f"Loaded {i+1}/{len(summary_cases)} cases…")

progress.empty()
df = pd.DataFrame(cases_data)

# ── Summary metrics ───────────────────────────────────────────────────────────
decided   = (df["status"] == "Decided").sum()
argued    = (df["status"] == "Argued").sum()
scheduled = (df["status"] == "Scheduled").sum()
cert      = (df["status"] == "Cert Granted").sum()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Cases",         len(df))
m2.metric("✅ Decided",           decided)
m3.metric("🔵 Argued / Pending", argued)
m4.metric("📅 Scheduled",        scheduled)
m5.metric("📌 Cert Granted",     cert)

st.divider()

tab_timeline, tab_monthly, tab_list, tab_issue = st.tabs([
    "🗓️ Timeline", "📆 Monthly View", "📋 Full Docket", "🏛️ Issue Areas",
])

# ── Timeline ─────────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader(f"{term}–{term+1} Term Timeline")

    timeline_rows = []
    for _, row in df.iterrows():
        anchor = row["decided_date"] or row["arg_date"]
        if anchor:
            timeline_rows.append({
                "Case": row["name"][:55] + ("…" if len(row["name"]) > 55 else ""),
                "Date": pd.Timestamp(anchor),
                "Status": row["status"],
                "Issue": row["issue_area"],
                "Disposition": row["disposition"],
                "Vote": row["vote_split"],
            })

    if timeline_rows:
        tl_df = pd.DataFrame(timeline_rows).sort_values("Date")

        fig_tl = px.scatter(
            tl_df,
            x="Date",
            y="Status",
            color="Status",
            color_discrete_map=STATUS_COLOR,
            hover_name="Case",
            hover_data={"Date": True, "Issue": True, "Disposition": True, "Vote": True, "Status": False},
            title=f"{term}–{term+1} SCOTUS Term — Cases by Date & Status",
            category_orders={"Status": ["Decided", "Argued", "Scheduled", "Cert Granted"]},
        )
        fig_tl.update_traces(marker=dict(size=12, opacity=0.85))
        fig_tl.update_layout(
            height=400,
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_title="Date",
            yaxis_title="",
            legend_title="Status",
        )
        st.plotly_chart(fig_tl, use_container_width=True)
        st.caption(
            "Each dot is a case. Hover for name and details. "
            "X-axis shows decision date (✅) or argument date (🔵📅)."
        )
    else:
        st.info("Not enough date data to render a timeline for this term yet.")

    # Gantt-style for cases with both arg and decision dates
    both_dates = df.dropna(subset=["arg_date", "decided_date"]).copy()
    if not both_dates.empty:
        st.markdown("**Argued → Decided Duration (cases with both dates)**")
        both_dates = both_dates.sort_values("arg_date")
        fig_gantt = go.Figure()
        for _, row in both_dates.iterrows():
            color = STATUS_COLOR.get(row["status"], "#95A5A6")
            name_short = row["name"][:50] + ("…" if len(row["name"]) > 50 else "")
            arg_ts = pd.Timestamp(row["arg_date"])
            dec_ts = pd.Timestamp(row["decided_date"])
            days   = (row["decided_date"] - row["arg_date"]).days
            fig_gantt.add_trace(go.Bar(
                x=[(dec_ts - arg_ts).days],
                y=[name_short],
                base=[arg_ts.timestamp() * 1000],
                orientation="h",
                marker_color=color,
                hovertemplate=(
                    f"<b>{name_short}</b><br>"
                    f"Argued: {row['arg_date']}<br>"
                    f"Decided: {row['decided_date']}<br>"
                    f"Days to decision: {days}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
        fig_gantt.update_layout(
            height=max(250, len(both_dates) * 24),
            xaxis=dict(
                type="date",
                title="Date",
                tickformat="%b %Y",
            ),
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=200, r=20, t=20, b=40),
        )
        st.plotly_chart(fig_gantt, use_container_width=True)

# ── Monthly view ──────────────────────────────────────────────────────────────
with tab_monthly:
    st.subheader("Cases by Argument Month")

    month_buckets: dict[str, list] = defaultdict(list)
    for _, row in df.iterrows():
        if row["arg_date"]:
            month_label = row["arg_date"].strftime("%B %Y")
        elif row["decided_date"]:
            month_label = "Decided (no arg date)"
        else:
            month_label = "Pending / Scheduled"
        month_buckets[month_label].append(row)

    # Sort by calendar order within the term
    def sort_key(label: str):
        try:
            return datetime.datetime.strptime(label, "%B %Y")
        except Exception:
            return datetime.datetime(9999, 1, 1)

    for month_label in sorted(month_buckets, key=sort_key):
        cases_in_month = month_buckets[month_label]
        decided_ct = sum(1 for c in cases_in_month if c["status"] == "Decided")
        with st.expander(
            f"**{month_label}** — {len(cases_in_month)} case(s), "
            f"{decided_ct} decided",
            expanded=False,
        ):
            for c in cases_in_month:
                icon = STATUS_ICON.get(c["status"], "❓")
                color = STATUS_COLOR.get(c["status"], "#95A5A6")
                vote_str = f"  ·  **{c['vote_split']}**" if c["vote_split"] else ""
                disp_str = f"  ·  {c['disposition']}" if c["disposition"] else ""
                st.markdown(
                    f'{icon} <span style="font-weight:bold;">{c["name"]}</span>'
                    f' <span style="color:#7F8C8D;font-size:0.85em;">({c["issue_area"]})</span>'
                    f'{vote_str}{disp_str}',
                    unsafe_allow_html=True,
                )

# ── Full docket list ──────────────────────────────────────────────────────────
with tab_list:
    st.subheader("Full Docket")

    status_options = ["All"] + sorted(df["status"].unique())
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        status_sel = st.selectbox("Filter by status", status_options)
    with col_f2:
        search_q = st.text_input("Search case name", placeholder="e.g. Trump, EPA, First Amendment")

    view = df.copy()
    if status_sel != "All":
        view = view[view["status"] == status_sel]
    if search_q:
        view = view[view["name"].str.contains(search_q, case=False, na=False)]

    view = view.sort_values(
        ["decided_date", "arg_date"],
        ascending=[False, False],
        na_position="last",
    )

    for _, row in view.iterrows():
        icon  = STATUS_ICON.get(row["status"], "❓")
        color = STATUS_COLOR.get(row["status"], "#95A5A6")
        arg_str  = str(row["arg_date"]) if row["arg_date"] else "—"
        dec_str  = str(row["decided_date"]) if row["decided_date"] else "pending"
        vote_str = row["vote_split"] or "—"
        audio_badge = " 🎙️" if row["has_audio"] else ""

        with st.expander(
            f'{icon} **{row["name"]}** — {row["status"]}{audio_badge}'
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Docket:** {row['docket'] or '—'}")
            c2.markdown(f"**Issue:** {row['issue_area']}")
            c3.markdown(f"**Argued:** {arg_str}")
            c4.markdown(f"**Decided:** {dec_str}")
            if row["disposition"]:
                st.markdown(f"**Disposition:** {row['disposition']}  |  **Vote:** {vote_str}")
            if row["href"]:
                st.markdown(f"[Open on Oyez ↗]({row['href'].replace('api.oyez.org/cases', 'www.oyez.org/cases')})")

# ── Issue area breakdown ──────────────────────────────────────────────────────
with tab_issue:
    st.subheader("Issue Areas This Term")

    issue_status: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for _, row in df.iterrows():
        issue_status[row["issue_area"]][row["status"]] += 1

    issue_rows = []
    for area, statuses in issue_status.items():
        issue_rows.append({
            "Issue Area": area,
            **statuses,
            "Total": sum(statuses.values()),
        })

    issue_df = pd.DataFrame(issue_rows).fillna(0).sort_values("Total", ascending=False)

    # Stacked bar by status
    status_cols = [s for s in ["Decided", "Argued", "Scheduled", "Cert Granted", "Unknown"]
                   if s in issue_df.columns]
    fig_issue = go.Figure()
    for s in status_cols:
        fig_issue.add_trace(go.Bar(
            name=s,
            x=issue_df["Issue Area"],
            y=issue_df[s],
            marker_color=STATUS_COLOR.get(s, "#95A5A6"),
        ))
    fig_issue.update_layout(
        barmode="stack",
        title=f"{term}–{term+1} Term — Cases by Issue Area and Status",
        xaxis_tickangle=-35,
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(x=1.01, y=1),
    )
    st.plotly_chart(fig_issue, use_container_width=True)

    # Decision time analysis
    decided_df = df[df["decided_date"].notna() & df["arg_date"].notna()].copy()
    if not decided_df.empty:
        decided_df["days_to_decision"] = decided_df.apply(
            lambda r: (r["decided_date"] - r["arg_date"]).days, axis=1
        )
        avg_days = decided_df["days_to_decision"].mean()
        max_row  = decided_df.loc[decided_df["days_to_decision"].idxmax()]
        min_row  = decided_df.loc[decided_df["days_to_decision"].idxmin()]

        st.markdown("**Decision Speed**")
        d1, d2, d3 = st.columns(3)
        d1.metric("Avg Days Argued → Decided", f"{avg_days:.0f} days")
        d2.metric("Fastest Decision",
                  f"{min_row['days_to_decision']} days",
                  delta=min_row["name"][:30])
        d3.metric("Slowest Decision",
                  f"{max_row['days_to_decision']} days",
                  delta=max_row["name"][:30])

        fig_speed = px.histogram(
            decided_df,
            x="days_to_decision",
            nbins=20,
            title="Distribution: Days from Argument to Decision",
            labels={"days_to_decision": "Days"},
            color_discrete_sequence=["#3498DB"],
        )
        fig_speed.update_layout(
            height=280,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_speed, use_container_width=True)
