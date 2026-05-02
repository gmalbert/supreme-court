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

st.set_page_config(page_title="Close Decisions Tracker", page_icon="⚖️", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

JUSTICE_LEAN = {
    "Roberts": "Conservative", "Thomas": "Conservative", "Alito": "Conservative",
    "Gorsuch": "Conservative", "Kavanaugh": "Conservative", "Barrett": "Conservative",
    "Scalia": "Conservative", "Kennedy": "Moderate", "O'Connor": "Moderate",
    "Sotomayor": "Liberal", "Kagan": "Liberal", "Jackson": "Liberal",
    "Breyer": "Liberal", "Ginsburg": "Liberal", "Stevens": "Liberal",
    "Souter": "Liberal", "White": "Moderate", "Blackmun": "Liberal",
    "Powell": "Moderate", "Rehnquist": "Conservative", "Burger": "Conservative",
}

LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#27AE60", "Liberal": "#3498DB"}

def last_name(full: str) -> str:
    parts = full.strip().split()
    return parts[-1] if parts else full


@st.cache_data(show_spinner=False, ttl=3600)
def load_close_decisions(terms: tuple[int, ...]) -> list[dict]:
    cases_out = []
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

            decisions = detail.get("decisions") or []
            for decision in decisions:
                votes = decision.get("votes") or []
                if not votes:
                    continue

                majority_votes = [v for v in votes if (v.get("vote") or "").lower() in ("majority", "concurrence", "concurring")]
                dissent_votes  = [v for v in votes if (v.get("vote") or "").lower() in ("dissent", "minority")]

                maj_count = len(majority_votes)
                dis_count = len(dissent_votes)
                total     = maj_count + dis_count
                if total < 7:
                    continue

                split = f"{maj_count}-{dis_count}"
                is_close = (maj_count - dis_count) <= 1   # 5-4, 6-5, etc.
                is_near  = (maj_count - dis_count) == 2   # 6-3, 5-3

                if not (is_close or is_near):
                    continue

                ia = detail.get("issue_area") or {}
                issue = ia.get("label", "Unknown") if isinstance(ia, dict) else str(ia)

                disp = detail.get("disposition") or {}
                disp_label = disp.get("label", "") if isinstance(disp, dict) else str(disp)

                majority_names = [
                    last_name((v.get("member") or {}).get("name", ""))
                    for v in majority_votes
                    if isinstance(v.get("member"), dict)
                ]
                dissent_names = [
                    last_name((v.get("member") or {}).get("name", ""))
                    for v in dissent_votes
                    if isinstance(v.get("member"), dict)
                ]

                cases_out.append({
                    "term":           term,
                    "case":           detail.get("name", ""),
                    "split":          split,
                    "majority_count": maj_count,
                    "dissent_count":  dis_count,
                    "majority":       majority_names,
                    "dissent":        dissent_names,
                    "issue_area":     issue,
                    "disposition":    disp_label,
                    "is_close":       is_close,
                    "href":           detail.get("href", href),
                })
            time.sleep(0.02)
    return cases_out


# ── Page ─────────────────────────────────────────────────────────────────────
st.title("⚖️ Close Decisions Tracker")
st.markdown(
    "Browse every **5-4** and **6-3** Supreme Court ruling, see who was in the majority "
    "and dissent for each case, and discover which justices cast the deciding vote most often."
)

available_terms = list(range(CURRENT_YEAR, CURRENT_YEAR - 25, -1))

with st.form("close_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_terms = st.multiselect(
            "Terms to include",
            options=available_terms,
            default=available_terms[:6],
            max_selections=15,
        )
    with col2:
        split_filter = st.multiselect(
            "Vote splits to show",
            ["5-4", "6-3", "5-3", "6-4", "7-2"],
            default=["5-4", "6-3"],
        )
    load_btn = st.form_submit_button("Load Cases", type="primary")

if load_btn and selected_terms:
    with st.spinner(f"Fetching close decisions for {len(selected_terms)} term(s)…"):
        raw = load_close_decisions(tuple(sorted(selected_terms, reverse=True)))
    st.session_state["close_raw"] = raw
    st.session_state["close_terms"] = selected_terms

if "close_raw" not in st.session_state:
    st.info("Select terms above and click **Load Cases**.")
    st.stop()

raw: list[dict] = st.session_state["close_raw"]
terms_loaded   = st.session_state.get("close_terms", selected_terms)

# Apply split filter
if split_filter:
    filtered = [c for c in raw if c["split"] in split_filter]
else:
    filtered = raw

if not filtered:
    st.warning("No close decisions found for the selected terms and split filters.")
    st.stop()

total_cases = len(filtered)
five_four   = sum(1 for c in filtered if c["split"] == "5-4")
six_three   = sum(1 for c in filtered if c["split"] == "6-3")

st.success(
    f"Found **{total_cases}** close decision(s) across "
    f"**{min(terms_loaded)}–{max(terms_loaded)}** — "
    f"**{five_four}** were 5-4, **{six_three}** were 6-3."
)

# ── Overview metrics ──────────────────────────────────────────────────────────
tab_overview, tab_cases, tab_deciding, tab_issue = st.tabs([
    "📊 Overview", "📋 Case Browser", "🎯 Deciding Vote", "🏛️ Issue Areas"
])

with tab_overview:
    # Split breakdown donut
    split_counts = defaultdict(int)
    for c in filtered:
        split_counts[c["split"]] += 1
    sc_df = pd.DataFrame(list(split_counts.items()), columns=["Split", "Count"]).sort_values("Count", ascending=False)

    col_donut, col_trend = st.columns(2)
    with col_donut:
        fig_donut = go.Figure(go.Pie(
            labels=sc_df["Split"],
            values=sc_df["Count"],
            hole=0.45,
            textinfo="label+percent",
            marker_colors=px.colors.qualitative.Set2,
        ))
        fig_donut.update_layout(
            title="Split Breakdown",
            height=320,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_trend:
        term_counts = defaultdict(lambda: defaultdict(int))
        for c in filtered:
            term_counts[c["term"]][c["split"]] += 1
        trend_rows = []
        for term_yr, splits in sorted(term_counts.items()):
            for sp, cnt in splits.items():
                trend_rows.append({"Term": term_yr, "Split": sp, "Count": cnt})
        if trend_rows:
            trend_df = pd.DataFrame(trend_rows)
            fig_trend = px.bar(
                trend_df, x="Term", y="Count", color="Split",
                barmode="stack",
                title="Close Decisions Per Term",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_trend.update_layout(
                height=320,
                plot_bgcolor="white",
                paper_bgcolor="white",
                xaxis=dict(type="category"),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    # Disposition breakdown
    disp_counts = defaultdict(int)
    for c in filtered:
        d = c["disposition"].lower()
        if "affirm" in d:
            disp_counts["Affirmed"] += 1
        elif "revers" in d or "vacate" in d:
            disp_counts["Reversed/Vacated"] += 1
        elif "remand" in d:
            disp_counts["Remanded"] += 1
        else:
            disp_counts["Other"] += 1

    st.markdown("**Dispositions in Close Decisions**")
    disp_cols = st.columns(len(disp_counts))
    for i, (label, count) in enumerate(sorted(disp_counts.items())):
        disp_cols[i].metric(label, count)

with tab_cases:
    st.subheader("All Close Decisions")

    # Search / filter
    search_q = st.text_input("Search case name", placeholder="e.g. Biden, Texas, EPA")
    display  = filtered
    if search_q:
        display = [c for c in display if search_q.lower() in c["case"].lower()]

    st.markdown(f"*Showing {len(display)} case(s)*")

    for c in sorted(display, key=lambda x: x["term"], reverse=True):
        maj_str = " · ".join(c["majority"]) if c["majority"] else "—"
        dis_str = " · ".join(c["dissent"])  if c["dissent"]  else "—"
        label_color = "#E74C3C" if c["split"] == "5-4" else "#E67E22"

        with st.expander(
            f"**{c['case']}** ({c['term']})  —  "
            f":{'red' if c['split']=='5-4' else 'orange'}[{c['split']}]  |  {c['issue_area']}"
        ):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**✅ Majority ({c['majority_count']}):**")
                for j in c["majority"]:
                    lean = JUSTICE_LEAN.get(j, "Moderate")
                    color = LEAN_COLORS.get(lean, "#7F8C8D")
                    st.markdown(
                        f'<span style="color:{color};font-weight:bold;">■</span> {j}',
                        unsafe_allow_html=True,
                    )
            with col_b:
                st.markdown(f"**❌ Dissent ({c['dissent_count']}):**")
                for j in c["dissent"]:
                    lean = JUSTICE_LEAN.get(j, "Moderate")
                    color = LEAN_COLORS.get(lean, "#7F8C8D")
                    st.markdown(
                        f'<span style="color:{color};font-weight:bold;">■</span> {j}',
                        unsafe_allow_html=True,
                    )
            if c["disposition"]:
                st.markdown(f"**Disposition:** {c['disposition']}")

with tab_deciding:
    st.subheader("🎯 Deciding Vote Analysis")
    st.markdown(
        "In **5-4** decisions, every majority justice is technically the deciding vote. "
        "Below we rank justices by how often they appear in the **majority** of 5-4 rulings — "
        "the higher the count, the more frequently they sided with the winning coalition in the closest cases."
    )

    five_four_only = [c for c in filtered if c["split"] == "5-4"]

    if not five_four_only:
        st.info("No 5-4 decisions in this selection. Try including more terms or the 5-4 split.")
    else:
        maj_counts: dict[str, int] = defaultdict(int)
        dis_counts: dict[str, int] = defaultdict(int)
        total_participated: dict[str, int] = defaultdict(int)

        for c in five_four_only:
            for j in c["majority"]:
                maj_counts[j] += 1
                total_participated[j] += 1
            for j in c["dissent"]:
                dis_counts[j] += 1
                total_participated[j] += 1

        deciding_rows = []
        for j, total in total_participated.items():
            if total < 3:
                continue
            maj = maj_counts.get(j, 0)
            dis = dis_counts.get(j, 0)
            deciding_rows.append({
                "Justice": j,
                "Majority": maj,
                "Dissent": dis,
                "Total 5-4 Cases": total,
                "Majority %": round(maj / total * 100, 1),
                "Lean": JUSTICE_LEAN.get(j, "Moderate"),
            })

        if deciding_rows:
            dec_df = pd.DataFrame(deciding_rows).sort_values("Majority %", ascending=False)

            fig_dec = go.Figure()
            fig_dec.add_trace(go.Bar(
                name="Majority",
                x=dec_df["Justice"],
                y=dec_df["Majority"],
                marker_color=[LEAN_COLORS.get(l, "#7F8C8D") for l in dec_df["Lean"]],
                text=dec_df["Majority %"].apply(lambda v: f"{v:.0f}%"),
                textposition="outside",
            ))
            fig_dec.add_trace(go.Bar(
                name="Dissent",
                x=dec_df["Justice"],
                y=dec_df["Dissent"],
                marker_color="rgba(150,150,150,0.4)",
            ))
            fig_dec.update_layout(
                barmode="stack",
                title="5-4 Majority vs. Dissent Count by Justice",
                xaxis_tickangle=-30,
                height=400,
                plot_bgcolor="white",
                paper_bgcolor="white",
                legend=dict(x=1.01, y=1),
            )
            st.plotly_chart(fig_dec, use_container_width=True)

            # Most "pivotal" — closest to 50/50 majority rate
            dec_df["Pivotal Score"] = (dec_df["Majority %"] - 50).abs()
            st.markdown("**Most Pivotal Justices** *(closest to 50% majority rate = swing behavior)*")
            st.dataframe(
                dec_df[["Justice", "Majority", "Dissent", "Total 5-4 Cases", "Majority %"]]
                .sort_values("Majority %")
                .reset_index(drop=True)
                .style.background_gradient(subset=["Majority %"], cmap="RdYlGn"),
                use_container_width=True,
                height=320,
                hide_index=True,
            )

with tab_issue:
    st.subheader("Issue Areas in Close Decisions")

    issue_split: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in filtered:
        issue_split[c["issue_area"]][c["split"]] += 1

    issue_rows = []
    for area, splits in issue_split.items():
        for sp, cnt in splits.items():
            issue_rows.append({"Issue Area": area, "Split": sp, "Count": cnt})

    if issue_rows:
        iss_df = pd.DataFrame(issue_rows)
        total_by_area = iss_df.groupby("Issue Area")["Count"].sum().sort_values(ascending=False)

        fig_iss = px.bar(
            iss_df[iss_df["Issue Area"].isin(total_by_area.head(12).index)],
            x="Issue Area",
            y="Count",
            color="Split",
            barmode="stack",
            title="Top Issue Areas — Close Decisions",
            category_orders={"Issue Area": list(total_by_area.head(12).index)},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_iss.update_layout(
            height=400,
            xaxis_tickangle=-30,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_iss, use_container_width=True)

        # Most contentious areas: highest % of close decisions
        total_all = len(raw)
        st.markdown("**Most Contentious Issue Areas** *(by share of all close decisions)*")
        contention = (
            iss_df.groupby("Issue Area")["Count"].sum()
            .reset_index()
            .rename(columns={"Count": "Close Decisions"})
            .sort_values("Close Decisions", ascending=False)
        )
        st.dataframe(contention.head(10).reset_index(drop=True), use_container_width=True, height=300, hide_index=True)
