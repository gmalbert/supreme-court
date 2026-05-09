import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from utils import add_sidebar_logo
add_sidebar_logo()

_REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
_CIRCUIT_PARQUET = os.path.join(_REPO_ROOT, "data_files", "circuit_stats.parquet")

ALL_CIRCUITS = [
    "1st Circuit", "2nd Circuit", "3rd Circuit", "4th Circuit", "5th Circuit",
    "6th Circuit", "7th Circuit", "8th Circuit", "9th Circuit", "10th Circuit",
    "11th Circuit", "D.C. Circuit", "Federal Circuit", "State Courts", "District Courts",
]

ISSUE_AREAS = [
    "Any",
    "Criminal Procedure", "Civil Rights", "First Amendment", "Due Process",
    "Privacy", "Economic Activity", "Judicial Power", "Federalism",
    "Federal Taxation", "Labor & Unions", "Administrative Law", "Immigration",
    "Environmental Law", "Veterans & Military", "Miscellaneous",
]


@st.cache_data(show_spinner=False)
def _load_df() -> pd.DataFrame:
    if not os.path.exists(_CIRCUIT_PARQUET):
        return pd.DataFrame(
            columns=["term", "name", "circuit", "lower_court", "outcome", "issue_area"]
        )
    df = pd.read_parquet(_CIRCUIT_PARQUET)
    df["term"] = pd.to_numeric(df["term"], errors="coerce").astype("Int64")
    return df


def _outcome_stats(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {"total": 0, "reversed": 0, "affirmed": 0, "remanded": 0,
                "rev_pct": 0.0, "aff_pct": 0.0, "rem_pct": 0.0}
    rev = len(df[df["outcome"] == "Reversed/Vacated"])
    aff = len(df[df["outcome"] == "Affirmed"])
    rem = len(df[df["outcome"] == "Remanded"])
    return {
        "total": total, "reversed": rev, "affirmed": aff, "remanded": rem,
        "rev_pct": rev / total * 100,
        "aff_pct": aff / total * 100,
        "rem_pct": rem / total * 100,
    }


st.title("\U0001f3db\ufe0f Circuit Courts")

_df_all = _load_df()

if _df_all.empty:
    st.error(
        "Circuit court data not found. "
        "Run `scripts/build_cases_parquet.py` to generate it."
    )
    st.stop()

tab_compare, tab_scorecard, tab_predictor = st.tabs([
    "\u2696\ufe0f Court Comparison",
    "\U0001f4ca Reversal Scorecard",
    "\U0001f3af Outcome Predictor",
])

# ── TAB 1: COURT COMPARISON ───────────────────────────────────────────────────
with tab_compare:
    st.markdown(
        "Compare two federal circuit courts side-by-side: see how often SCOTUS affirmed "
        "or reversed their decisions based on historical data."
    )

    min_term_cmp = int(_df_all["term"].min())
    max_term_cmp = int(_df_all["term"].max())

    col_a, col_b = st.columns(2)
    with col_a:
        court_a = st.selectbox("Court A", ALL_CIRCUITS, index=8, key="cmp_a")
    with col_b:
        court_b = st.selectbox("Court B", ALL_CIRCUITS, index=4, key="cmp_b")

    term_range_cmp = st.slider(
        "Term range",
        min_value=min_term_cmp, max_value=max_term_cmp,
        value=(max(min_term_cmp, max_term_cmp - 24), max_term_cmp),
        key="cmp_terms",
    )

    df_a = _df_all[
        (_df_all["circuit"] == court_a) &
        (_df_all["term"] >= term_range_cmp[0]) &
        (_df_all["term"] <= term_range_cmp[1])
    ]
    df_b = _df_all[
        (_df_all["circuit"] == court_b) &
        (_df_all["term"] >= term_range_cmp[0]) &
        (_df_all["term"] <= term_range_cmp[1])
    ]

    stats_a = _outcome_stats(df_a)
    stats_b = _outcome_stats(df_b)

    st.subheader("Summary")
    col_ra, col_rb = st.columns(2)
    with col_ra:
        st.markdown(f"### {court_a}")
        st.metric("Cases Reviewed", stats_a["total"])
        st.metric("Affirmed", stats_a["affirmed"], f"{stats_a['aff_pct']:.0f}%")
        st.metric("Reversed / Vacated", stats_a["reversed"], f"{stats_a['rev_pct']:.0f}%")
        st.metric("Remanded", stats_a["remanded"], f"{stats_a['rem_pct']:.0f}%")
    with col_rb:
        st.markdown(f"### {court_b}")
        st.metric("Cases Reviewed", stats_b["total"])
        st.metric("Affirmed", stats_b["affirmed"], f"{stats_b['aff_pct']:.0f}%")
        st.metric("Reversed / Vacated", stats_b["reversed"], f"{stats_b['rev_pct']:.0f}%")
        st.metric("Remanded", stats_b["remanded"], f"{stats_b['rem_pct']:.0f}%")

    st.divider()

    categories_cmp = ["Reversed/Vacated", "Affirmed", "Remanded"]
    counts_a_cmp = [stats_a["reversed"], stats_a["affirmed"], stats_a["remanded"]]
    counts_b_cmp = [stats_b["reversed"], stats_b["affirmed"], stats_b["remanded"]]
    fig_bar_cmp = go.Figure(data=[
        go.Bar(name=court_a, x=categories_cmp, y=counts_a_cmp, marker_color="#4A90D9"),
        go.Bar(name=court_b, x=categories_cmp, y=counts_b_cmp, marker_color="#E67E22"),
    ])
    fig_bar_cmp.update_layout(
        barmode="group", title="Outcome Comparison", height=350,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_bar_cmp)

    st.subheader("Issue Areas Sent to SCOTUS")
    col_ia_a, col_ia_b = st.columns(2)

    def _issue_bar(df, label, color):
        vc = (
            df[df["issue_area"] != "Unknown"]["issue_area"]
            .value_counts().head(10).reset_index()
        )
        vc.columns = ["Issue Area", "Count"]
        if vc.empty:
            st.info("No issue area data.")
            return
        fig = px.bar(
            vc, x="Count", y="Issue Area", orientation="h",
            title=f"{label} \u2014 Issue Areas",
            color_discrete_sequence=[color],
        )
        fig.update_layout(height=340, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig)

    with col_ia_a:
        _issue_bar(df_a, court_a, "#4A90D9")
    with col_ia_b:
        _issue_bar(df_b, court_b, "#E67E22")

    st.divider()
    st.subheader("Case Details")
    tab_da, tab_db = st.tabs([court_a, court_b])
    with tab_da:
        st.dataframe(
            df_a[["term", "name", "outcome", "issue_area"]].rename(
                columns={"term": "Term", "name": "Case",
                         "outcome": "Outcome", "issue_area": "Issue Area"}
            ).sort_values("Term", ascending=False),
            height=350, hide_index=True,
        )
    with tab_db:
        st.dataframe(
            df_b[["term", "name", "outcome", "issue_area"]].rename(
                columns={"term": "Term", "name": "Case",
                         "outcome": "Outcome", "issue_area": "Issue Area"}
            ).sort_values("Term", ascending=False),
            height=350, hide_index=True,
        )

# ── TAB 2: REVERSAL SCORECARD ─────────────────────────────────────────────────
with tab_scorecard:
    st.markdown(
        "Which federal circuit courts does SCOTUS reverse most often? "
        "Use the slider to narrow the term range."
    )

    min_term_sc = int(_df_all["term"].min())
    max_term_sc = int(_df_all["term"].max())

    term_range_sc = st.slider(
        "Term range",
        min_value=min_term_sc, max_value=max_term_sc,
        value=(max(min_term_sc, max_term_sc - 24), max_term_sc),
        key="sc_terms",
    )

    sc_slice = _df_all[
        (_df_all["term"] >= term_range_sc[0]) &
        (_df_all["term"] <= term_range_sc[1]) &
        (~_df_all["circuit"].isin(["State Courts", "District Courts"]))
    ]

    summary_rows = []
    for circuit, grp in sc_slice.groupby("circuit"):
        s = _outcome_stats(grp)
        summary_rows.append({
            "Circuit": circuit,
            "Cases Reviewed": s["total"],
            "Reversed / Vacated": s["reversed"],
            "Affirmed": s["affirmed"],
            "Remanded": s["remanded"],
            "Reversal Rate": round(s["rev_pct"], 1),
            "Affirmance Rate": round(s["aff_pct"], 1),
        })

    if not summary_rows:
        st.warning("No data found for the selected term range.")
    else:
        summary_df = pd.DataFrame(summary_rows).sort_values("Reversal Rate", ascending=False)

        fig_sc = go.Figure()
        fig_sc.add_trace(go.Bar(
            name="Reversed / Vacated", x=summary_df["Circuit"], y=summary_df["Reversal Rate"],
            marker_color="#E74C3C",
            text=summary_df["Reversal Rate"].apply(lambda x: f"{x:.0f}%"),
            textposition="outside",
        ))
        fig_sc.add_trace(go.Bar(
            name="Affirmed", x=summary_df["Circuit"], y=summary_df["Affirmance Rate"],
            marker_color="#27AE60",
            text=summary_df["Affirmance Rate"].apply(lambda x: f"{x:.0f}%"),
            textposition="outside",
        ))
        fig_sc.update_layout(
            barmode="group",
            title="Reversal vs. Affirmance Rate by Circuit (%)",
            xaxis_tickangle=-30, height=440,
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(x=1.01, y=1),
        )
        st.plotly_chart(fig_sc)
        st.dataframe(
            summary_df.style.background_gradient(subset=["Reversal Rate"], cmap="RdYlGn_r"),
            height=380, hide_index=True,
        )

        st.divider()
        st.subheader("Reversal Rate Trend \u2014 Single Circuit")
        avail_circuits_sc = sorted(sc_slice["circuit"].unique())
        sel_circ_sc = st.selectbox(
            "Select Circuit", avail_circuits_sc,
            index=min(8, len(avail_circuits_sc) - 1),
            key="sc_circ",
        )
        circ_df_sc = sc_slice[sc_slice["circuit"] == sel_circ_sc]

        trend_rows_sc = []
        for term_val, grp in circ_df_sc.groupby("term"):
            s = _outcome_stats(grp)
            trend_rows_sc.append({
                "Term": term_val,
                "Reversal Rate (%)": round(s["rev_pct"], 1),
                "Cases": s["total"],
            })

        if trend_rows_sc:
            trend_df_sc = pd.DataFrame(trend_rows_sc).sort_values("Term")
            fig_trend_sc = px.bar(
                trend_df_sc, x="Term", y="Reversal Rate (%)",
                title=f"{sel_circ_sc} \u2014 Reversal Rate by Term",
                text="Cases",
                color="Reversal Rate (%)", color_continuous_scale="RdYlGn_r",
            )
            fig_trend_sc.update_layout(
                height=320, coloraxis_showscale=False,
                plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_trend_sc)

        st.divider()
        ia_counts_sc = (
            circ_df_sc[circ_df_sc["issue_area"] != "Unknown"]["issue_area"]
            .value_counts().head(10).reset_index()
        )
        ia_counts_sc.columns = ["Issue Area", "Count"]
        if not ia_counts_sc.empty:
            fig_issues_sc = px.bar(
                ia_counts_sc, x="Count", y="Issue Area", orientation="h",
                title=f"Top Issue Areas from {sel_circ_sc}",
                color="Count", color_continuous_scale="Blues",
            )
            fig_issues_sc.update_layout(
                height=340, coloraxis_showscale=False,
                plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_issues_sc)

        with st.expander(f"All cases from {sel_circ_sc}"):
            st.dataframe(
                circ_df_sc[["term", "name", "outcome", "issue_area"]].rename(
                    columns={"term": "Term", "name": "Case",
                             "outcome": "Outcome", "issue_area": "Issue Area"}
                ).sort_values("Term", ascending=False),
                height=350,
            )

# ── TAB 3: OUTCOME PREDICTOR ──────────────────────────────────────────────────
with tab_predictor:
    st.markdown(
        "Based on historical SCOTUS data, estimate the likelihood that a case from a given "
        "lower court and issue area will be **reversed**, **affirmed**, or **remanded**. "
        "This is a statistical tool \u2014 not legal prediction."
    )

    min_term_pr = int(_df_all["term"].min())
    max_term_pr = int(_df_all["term"].max())

    col1_pr, col2_pr = st.columns(2)
    with col1_pr:
        circuit_pr = st.selectbox("Lower Court / Circuit", ALL_CIRCUITS, key="pr_circuit")
    with col2_pr:
        issue_pr = st.selectbox("Issue Area", ISSUE_AREAS, key="pr_issue")

    term_range_pr = st.slider(
        "Term range",
        min_value=min_term_pr, max_value=max_term_pr,
        value=(max(min_term_pr, max_term_pr - 24), max_term_pr),
        key="pr_terms",
    )

    df_pr = _df_all[
        (_df_all["circuit"] == circuit_pr) &
        (_df_all["term"] >= term_range_pr[0]) &
        (_df_all["term"] <= term_range_pr[1])
    ].copy()
    if issue_pr != "Any":
        df_pr = df_pr[df_pr["issue_area"] == issue_pr]

    stats_pr = _outcome_stats(df_pr)

    st.divider()
    st.subheader("Results")

    if stats_pr["total"] == 0:
        st.warning(
            f"No historical cases found for **{circuit_pr}**"
            + (f" / **{issue_pr}**" if issue_pr != "Any" else "")
            + f" between {term_range_pr[0]} and {term_range_pr[1]}."
        )
    else:
        rev_pr = stats_pr["rev_pct"]
        aff_pr = stats_pr["aff_pct"]
        rem_pr = stats_pr["rem_pct"]

        if rev_pr > aff_pr:
            verdict = "\u2b06\ufe0f **More likely to be REVERSED**"
            verdict_color = "#E74C3C"
        elif aff_pr > rev_pr:
            verdict = "\u2705 **More likely to be AFFIRMED**"
            verdict_color = "#27AE60"
        else:
            verdict = "\u2696\ufe0f **Roughly equal odds**"
            verdict_color = "#F39C12"

        st.markdown(
            f"<div style='background:{verdict_color}22;border-left:5px solid {verdict_color};"
            f"padding:14px 18px;border-radius:6px;font-size:1.15em'>{verdict}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cases Analyzed", stats_pr["total"])
        m2.metric("Affirmed", f"{aff_pr:.1f}%")
        m3.metric("Reversed / Vacated", f"{rev_pr:.1f}%")
        m4.metric("Remanded", f"{rem_pr:.1f}%")

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=rev_pr,
            title={"text": "Reversal Rate (%)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#E74C3C"},
                "steps": [
                    {"range": [0, 33], "color": "#D5F5E3"},
                    {"range": [33, 66], "color": "#FCF3CF"},
                    {"range": [66, 100], "color": "#FADBD8"},
                ],
                "threshold": {
                    "line": {"color": "#27AE60", "width": 4},
                    "thickness": 0.75,
                    "value": aff_pr,
                },
            },
            number={"suffix": "%"},
        ))
        fig_gauge.update_layout(height=280, margin=dict(l=30, r=30, t=60, b=10))
        st.plotly_chart(fig_gauge)

        if issue_pr == "Any":
            st.subheader(f"Outcome Breakdown by Issue Area \u2014 {circuit_pr}")
            ia_rows_pr = []
            for ia_lbl, grp in df_pr[df_pr["issue_area"] != "Unknown"].groupby("issue_area"):
                s = _outcome_stats(grp)
                ia_rows_pr.append({
                    "Issue Area": ia_lbl,
                    "Cases": s["total"],
                    "Reversal %": round(s["rev_pct"], 1),
                    "Affirm %": round(s["aff_pct"], 1),
                })
            if ia_rows_pr:
                ia_df_pr = pd.DataFrame(ia_rows_pr).sort_values("Reversal %", ascending=False)
                fig_ia_pr = px.bar(
                    ia_df_pr, x="Issue Area", y=["Reversal %", "Affirm %"],
                    barmode="group",
                    title=f"{circuit_pr} \u2014 Reversal vs. Affirmance by Issue Area",
                    color_discrete_map={"Reversal %": "#E74C3C", "Affirm %": "#27AE60"},
                )
                fig_ia_pr.update_layout(
                    height=360, plot_bgcolor="white", paper_bgcolor="white",
                    xaxis_tickangle=-30,
                )
                st.plotly_chart(fig_ia_pr)

        st.subheader("Reversal Rate Trend Over Time")
        trend_rows_pr = []
        for term_val, grp in df_pr.groupby("term"):
            s = _outcome_stats(grp)
            trend_rows_pr.append({
                "Term": term_val,
                "Reversal %": round(s["rev_pct"], 1),
                "Cases": s["total"],
            })
        if trend_rows_pr:
            trend_df_pr = pd.DataFrame(trend_rows_pr).sort_values("Term")
            fig_trend_pr = px.line(
                trend_df_pr, x="Term", y="Reversal %",
                markers=True, title="Reversal Rate by Term",
            )
            fig_trend_pr.update_layout(
                height=280, plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_trend_pr)

        st.caption(
            f"Based on {stats_pr['total']} cases from terms "
            f"{term_range_pr[0]}\u2013{term_range_pr[1]}. Statistical trends, not legal advice."
        )
