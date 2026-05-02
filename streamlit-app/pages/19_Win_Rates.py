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
from collections import defaultdict

st.set_page_config(page_title="Historical Win Rates", page_icon="🏆", layout="wide")

HEADERS  = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Party classification helpers ─────────────────────────────────────────────

FEDERAL_KEYWORDS = [
    "united states", "u.s.", "federal", "department of", "secretary of",
    "attorney general", "irs", "epa", "fbi", "cia", "doj", "hhs",
    "commissioner", "administrator", "director of", "bureau of",
    "national labor relations", "securities and exchange", "federal trade",
    "immigration", "customs", "immigration and customs",
]

STATE_KEYWORDS = [
    "state of", "commonwealth of", "people of", "city of", "county of",
    "town of", "village of", "board of", "district of",
    # state abbreviation patterns handled separately
    "california", "texas", "new york", "florida", "illinois", "ohio",
    "michigan", "georgia", "north carolina", "virginia", "arizona",
    "washington", "colorado", "nevada", "oregon", "utah", "minnesota",
]

CORP_KEYWORDS = [
    "inc.", "corp.", "corporation", "company", "co.", "llc", "ltd.",
    "association", "bank", "insurance", "industries", "enterprises",
    "group", "partners", "trust",
]

def classify_party(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in FEDERAL_KEYWORDS):
        return "Federal Government"
    if any(k in n for k in STATE_KEYWORDS):
        return "State / Local Gov't"
    if any(k in n for k in CORP_KEYWORDS):
        return "Corporation / Org"
    return "Individual / Other"


def disposition_winner(disp: str, petitioner: str, respondent: str) -> str | None:
    """Return 'petitioner' or 'respondent' based on disposition text."""
    d = (disp or "").lower()
    if any(w in d for w in ["affirm"]):
        return "respondent"
    if any(w in d for w in ["revers", "vacate", "remand"]):
        return "petitioner"
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def load_win_data(terms: tuple[int, ...]) -> list[dict]:
    rows = []
    for term in terms:
        try:
            r = requests.get(
                f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                headers=HEADERS, timeout=10,
            )
            r.raise_for_status()
            cases = r.json()
        except Exception:
            continue

        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            try:
                dr = requests.get(href, headers=HEADERS, timeout=8)
                dr.raise_for_status()
                detail = dr.json()
            except Exception:
                continue

            petitioner  = detail.get("petitioner", "") or ""
            respondent  = detail.get("respondent", "") or ""
            if not petitioner and not respondent:
                # Fallback: parse from case name
                name_parts = detail.get("name", "").split(" v. ")
                petitioner  = name_parts[0].strip() if len(name_parts) >= 2 else ""
                respondent  = name_parts[1].strip() if len(name_parts) >= 2 else ""

            disp = detail.get("disposition") or {}
            disp_label = disp.get("label", "") if isinstance(disp, dict) else str(disp)

            winner_side = disposition_winner(disp_label, petitioner, respondent)
            if not winner_side:
                continue

            pet_type = classify_party(petitioner)
            res_type = classify_party(respondent)

            winner_type = pet_type if winner_side == "petitioner" else res_type
            loser_type  = res_type if winner_side == "petitioner" else pet_type

            ia = detail.get("issue_area") or {}
            issue = ia.get("label", "Unknown") if isinstance(ia, dict) else str(ia)

            rows.append({
                "term":         term,
                "case":         detail.get("name", ""),
                "petitioner":   petitioner[:60],
                "respondent":   respondent[:60],
                "pet_type":     pet_type,
                "res_type":     res_type,
                "winner_side":  winner_side,
                "winner_type":  winner_type,
                "loser_type":   loser_type,
                "issue_area":   issue,
                "disposition":  disp_label,
            })
            time.sleep(0.02)
    return rows


# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🏆 Historical Win Rates at SCOTUS")
st.markdown(
    "Who wins at the Supreme Court? Track how the federal government, states, "
    "corporations, and individuals fare — broken down by term and issue area."
)

available_terms = list(range(CURRENT_YEAR, CURRENT_YEAR - 25, -1))

with st.form("win_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_terms = st.multiselect(
            "Terms to include",
            options=available_terms,
            default=available_terms[:8],
            max_selections=15,
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.form_submit_button("Load Data", type="primary")

if load_btn and selected_terms:
    with st.spinner(f"Fetching case data for {len(selected_terms)} term(s)…"):
        rows = load_win_data(tuple(sorted(selected_terms, reverse=True)))
    st.session_state["win_rows"]  = rows
    st.session_state["win_terms"] = selected_terms

if "win_rows" not in st.session_state:
    st.info("Select terms and click **Load Data** to begin.")
    st.stop()

rows: list[dict] = st.session_state["win_rows"]
terms_loaded = st.session_state.get("win_terms", [])

if not rows:
    st.warning("No usable case data found.")
    st.stop()

df = pd.DataFrame(rows)
st.success(
    f"Analysed **{len(df)}** decided cases across "
    f"**{min(terms_loaded)}–{max(terms_loaded)}**."
)

PARTY_COLORS = {
    "Federal Government":  "#E74C3C",
    "State / Local Gov't": "#E67E22",
    "Corporation / Org":   "#3498DB",
    "Individual / Other":  "#27AE60",
}

tab_overview, tab_vs, tab_trend, tab_issue, tab_sol_gen = st.tabs([
    "📊 Overall Win Rates", "⚔️ Head-to-Head", "📈 Trend Over Time",
    "🏛️ By Issue Area", "🎙️ Solicitor General"
])

# ── Overall win rates ─────────────────────────────────────────────────────────
with tab_overview:
    st.subheader("Win Rate by Party Type")
    st.caption(
        "Each case is classified by whether the petitioner or respondent won, "
        "and each party is typed as Federal Government, State/Local, Corporation, or Individual."
    )

    party_types = ["Federal Government", "State / Local Gov't", "Corporation / Org", "Individual / Other"]
    win_rows_out = []
    for ptype in party_types:
        as_pet = df[df["pet_type"] == ptype]
        as_res = df[df["res_type"] == ptype]
        total  = len(as_pet) + len(as_res)
        wins   = len(as_pet[as_pet["winner_side"] == "petitioner"]) + \
                 len(as_res[as_res["winner_side"] == "respondent"])
        if total >= 5:
            win_rows_out.append({
                "Party Type": ptype,
                "Total Cases": total,
                "Wins": wins,
                "Losses": total - wins,
                "Win Rate %": round(wins / total * 100, 1),
            })

    wr_df = pd.DataFrame(win_rows_out).sort_values("Win Rate %", ascending=False)

    col_bars, col_metrics = st.columns([2, 1])
    with col_bars:
        fig_wr = go.Figure()
        fig_wr.add_trace(go.Bar(
            x=wr_df["Party Type"],
            y=wr_df["Win Rate %"],
            marker_color=[PARTY_COLORS.get(p, "#95A5A6") for p in wr_df["Party Type"]],
            text=wr_df["Win Rate %"].apply(lambda v: f"{v:.1f}%"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<extra></extra>",
        ))
        fig_wr.add_hline(y=50, line_dash="dot", line_color="#95A5A6",
                         annotation_text="50% baseline")
        fig_wr.update_layout(
            title="Overall Win Rate by Party Type",
            yaxis=dict(title="Win Rate (%)", range=[0, 105]),
            height=360,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_wr, use_container_width=True)

    with col_metrics:
        for _, row in wr_df.iterrows():
            color = PARTY_COLORS.get(row["Party Type"], "#95A5A6")
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:6px 10px;margin-bottom:8px;">'
                f'<strong>{row["Party Type"]}</strong><br>'
                f'{row["Wins"]}W / {row["Losses"]}L out of {row["Total Cases"]} cases<br>'
                f'<span style="font-size:1.2em;font-weight:bold;">{row["Win Rate %"]}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Petitioner advantage
    pet_wins = len(df[df["winner_side"] == "petitioner"])
    res_wins = len(df[df["winner_side"] == "respondent"])
    st.divider()
    st.subheader("Petitioner vs. Respondent")
    st.markdown(
        "SCOTUS grants *certiorari* most often when it disagrees with the lower court — "
        "so petitioners (the party that lost below and appealed) tend to win more."
    )
    col_p, col_r = st.columns(2)
    col_p.metric("Petitioner Win Rate",
                 f"{pet_wins/(pet_wins+res_wins)*100:.1f}%",
                 f"{pet_wins} of {pet_wins+res_wins} cases")
    col_r.metric("Respondent Win Rate",
                 f"{res_wins/(pet_wins+res_wins)*100:.1f}%",
                 f"{res_wins} of {pet_wins+res_wins} cases")

# ── Head-to-head ──────────────────────────────────────────────────────────────
with tab_vs:
    st.subheader("Head-to-Head: Party Type vs. Party Type")
    st.markdown("Select two party types to see their direct win/loss record against each other.")

    col1, col2 = st.columns(2)
    with col1:
        type_a = st.selectbox("Party A (petitioner)", party_types, index=0)
    with col2:
        type_b = st.selectbox("Party B (respondent)", party_types, index=3)

    matchup = df[(df["pet_type"] == type_a) & (df["res_type"] == type_b)]
    reverse = df[(df["pet_type"] == type_b) & (df["res_type"] == type_a)]

    def matchup_stats(sub: pd.DataFrame, pet_label: str, res_label: str):
        if sub.empty:
            return None
        pet_wins_m = len(sub[sub["winner_side"] == "petitioner"])
        res_wins_m = len(sub[sub["winner_side"] == "respondent"])
        total_m = len(sub)
        return {"pet": pet_label, "res": res_label,
                "pet_wins": pet_wins_m, "res_wins": res_wins_m, "total": total_m}

    s1 = matchup_stats(matchup, type_a, type_b)
    s2 = matchup_stats(reverse, type_b, type_a)

    for s in [s1, s2]:
        if s:
            st.markdown(
                f"**{s['pet']} (petitioner) vs. {s['res']} (respondent)** — "
                f"{s['total']} cases"
            )
            c1, c2 = st.columns(2)
            c1.metric(f"{s['pet']} wins", s["pet_wins"],
                      f"{s['pet_wins']/s['total']*100:.1f}%")
            c2.metric(f"{s['res']} wins", s["res_wins"],
                      f"{s['res_wins']/s['total']*100:.1f}%")
            # Sample cases
            combined = matchup if s == s1 else reverse
            with st.expander(f"Sample cases ({min(5, len(combined))} shown)"):
                for _, row in combined.head(5).iterrows():
                    st.markdown(f"- **{row['case']}** ({row['term']}) — {row['disposition']}")
            st.divider()

    if not s1 and not s2:
        st.info("No direct matchups found between these two party types.")

# ── Trend over time ───────────────────────────────────────────────────────────
with tab_trend:
    st.subheader("Win Rate Over Time")
    focus_type = st.selectbox("Track party type", party_types)

    trend_rows = []
    for term_yr, grp in df.groupby("term"):
        as_pet = grp[grp["pet_type"] == focus_type]
        as_res = grp[grp["res_type"] == focus_type]
        total  = len(as_pet) + len(as_res)
        wins   = len(as_pet[as_pet["winner_side"] == "petitioner"]) + \
                 len(as_res[as_res["winner_side"] == "respondent"])
        if total >= 2:
            trend_rows.append({
                "Term": term_yr,
                "Win Rate %": round(wins / total * 100, 1),
                "Cases": total,
                "Wins": wins,
            })

    if trend_rows:
        trend_df = pd.DataFrame(trend_rows).sort_values("Term")
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend_df["Term"],
            y=trend_df["Win Rate %"],
            mode="lines+markers",
            line=dict(color=PARTY_COLORS.get(focus_type, "#3498DB"), width=2.5),
            marker=dict(size=trend_df["Cases"].clip(upper=20) * 0.8 + 6),
            text=trend_df["Cases"].apply(lambda n: f"{n} cases"),
            hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<br>%{text}<extra></extra>",
        ))
        fig_trend.add_hline(y=50, line_dash="dot", line_color="#BDC3C7")
        fig_trend.update_layout(
            title=f"{focus_type} — Win Rate Per Term",
            yaxis=dict(title="Win Rate (%)", range=[0, 105]),
            xaxis=dict(title="Term"),
            height=360,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption("Marker size reflects number of cases that term (larger = more cases).")

# ── By issue area ─────────────────────────────────────────────────────────────
with tab_issue:
    st.subheader("Win Rate by Issue Area")
    focus_type2 = st.selectbox("Party type", party_types, key="issue_type")

    issue_rows = []
    for area, grp in df.groupby("issue_area"):
        as_pet = grp[grp["pet_type"] == focus_type2]
        as_res = grp[grp["res_type"] == focus_type2]
        total  = len(as_pet) + len(as_res)
        wins   = len(as_pet[as_pet["winner_side"] == "petitioner"]) + \
                 len(as_res[as_res["winner_side"] == "respondent"])
        if total >= 3:
            issue_rows.append({
                "Issue Area": area,
                "Win Rate %": round(wins / total * 100, 1),
                "Cases": total,
            })

    if issue_rows:
        issue_df = pd.DataFrame(issue_rows).sort_values("Win Rate %", ascending=False)
        color = PARTY_COLORS.get(focus_type2, "#3498DB")
        fig_issue = go.Figure(go.Bar(
            x=issue_df["Issue Area"],
            y=issue_df["Win Rate %"],
            marker_color=color,
            opacity=0.8,
            text=issue_df["Cases"].apply(lambda n: f"n={n}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<br>%{text}<extra></extra>",
        ))
        fig_issue.add_hline(y=50, line_dash="dot", line_color="#BDC3C7")
        fig_issue.update_layout(
            title=f"{focus_type2} — Win Rate by Issue Area",
            yaxis=dict(title="Win Rate (%)", range=[0, 115]),
            xaxis_tickangle=-35,
            height=420,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_issue, use_container_width=True)

# ── Solicitor General spotlight ───────────────────────────────────────────────
with tab_sol_gen:
    st.subheader("🎙️ Solicitor General — The 'Tenth Justice'")
    st.markdown(
        "The U.S. Solicitor General argues cases on behalf of the federal government "
        "and is often called the **'Tenth Justice'** due to the government's historically "
        "high win rate at SCOTUS."
    )

    fed_as_pet = df[df["pet_type"] == "Federal Government"]
    fed_as_res = df[df["res_type"] == "Federal Government"]

    fed_wins = (
        len(fed_as_pet[fed_as_pet["winner_side"] == "petitioner"]) +
        len(fed_as_res[fed_as_res["winner_side"] == "respondent"])
    )
    fed_total = len(fed_as_pet) + len(fed_as_res)

    if fed_total > 0:
        col1, col2, col3 = st.columns(3)
        col1.metric("Cases Involving Federal Gov't", fed_total)
        col2.metric("Federal Gov't Wins", fed_wins)
        col3.metric("Federal Gov't Win Rate",
                    f"{fed_wins/fed_total*100:.1f}%",
                    delta=f"{fed_wins/fed_total*100 - 50:.1f}% vs 50% baseline")

    # Fed as petitioner vs respondent
    st.markdown("---")
    st.markdown("**As Petitioner vs. As Respondent**")
    fed_pet_wins = len(fed_as_pet[fed_as_pet["winner_side"] == "petitioner"])
    fed_res_wins = len(fed_as_res[fed_as_res["winner_side"] == "respondent"])
    c1, c2 = st.columns(2)
    if len(fed_as_pet) > 0:
        c1.metric("Win Rate as Petitioner",
                  f"{fed_pet_wins/len(fed_as_pet)*100:.1f}%",
                  f"{len(fed_as_pet)} cases")
    if len(fed_as_res) > 0:
        c2.metric("Win Rate as Respondent",
                  f"{fed_res_wins/len(fed_as_res)*100:.1f}%",
                  f"{len(fed_as_res)} cases")

    # Term-by-term SG win rate
    sg_trend = []
    for term_yr, grp in df.groupby("term"):
        p = grp[grp["pet_type"] == "Federal Government"]
        r = grp[grp["res_type"] == "Federal Government"]
        t = len(p) + len(r)
        w = len(p[p["winner_side"] == "petitioner"]) + len(r[r["winner_side"] == "respondent"])
        if t >= 2:
            sg_trend.append({"Term": term_yr, "Win Rate %": round(w/t*100,1), "Cases": t})

    if sg_trend:
        sg_df = pd.DataFrame(sg_trend).sort_values("Term")
        fig_sg = px.area(
            sg_df, x="Term", y="Win Rate %",
            title="Federal Government Win Rate Per Term",
            color_discrete_sequence=["#E74C3C"],
        )
        fig_sg.add_hline(y=50, line_dash="dot", line_color="#BDC3C7",
                         annotation_text="50% baseline")
        fig_sg.update_layout(
            height=320,
            yaxis=dict(range=[0, 105]),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_sg, use_container_width=True)

    # Notable cases where federal gov lost
    st.markdown("**Cases Where Federal Government Lost (sample)**")
    fed_lost = pd.concat([
        fed_as_pet[fed_as_pet["winner_side"] == "respondent"],
        fed_as_res[fed_as_res["winner_side"] == "petitioner"],
    ])
    if not fed_lost.empty:
        sample = fed_lost[["term", "case", "issue_area", "disposition"]].sort_values("term", ascending=False).head(10)
        st.dataframe(sample.reset_index(drop=True), use_container_width=True, height=280, hide_index=True)
