import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import time

st.set_page_config(page_title="Outcome Predictor", page_icon="🎯", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

ISSUE_AREAS = [
    "Criminal Procedure", "Civil Rights", "First Amendment", "Due Process",
    "Privacy", "Economic Activity", "Judicial Power", "Federalism",
    "Federal Taxation", "Unions", "Attorneys", "Miscellaneous",
]

CIRCUIT_KEYWORDS = {
    "1st Circuit":    "First Circuit",
    "2nd Circuit":    "Second Circuit",
    "3rd Circuit":    "Third Circuit",
    "4th Circuit":    "Fourth Circuit",
    "5th Circuit":    "Fifth Circuit",
    "6th Circuit":    "Sixth Circuit",
    "7th Circuit":    "Seventh Circuit",
    "8th Circuit":    "Eighth Circuit",
    "9th Circuit":    "Ninth Circuit",
    "10th Circuit":   "Tenth Circuit",
    "11th Circuit":   "Eleventh Circuit",
    "D.C. Circuit":   "District of Columbia Circuit",
    "Federal Circuit":"Federal Circuit",
    "State Courts":   "state",
    "District Courts":"district",
    "Any / Unknown":  "",
}

@st.cache_data(show_spinner=False, ttl=3600)
def load_historical_data(terms: tuple) -> pd.DataFrame:
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
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name", "") if isinstance(lower, dict) else str(lower)
            disposition = detail.get("disposition") or {}
            disp_label = disposition.get("label", "") if isinstance(disposition, dict) else str(disposition)
            ia = detail.get("issue_area") or {}
            issue_label = ia.get("label", "Unknown") if isinstance(ia, dict) else str(ia)
            affirmed = any(w in disp_label.lower() for w in ["affirm"])
            reversed_ = any(w in disp_label.lower() for w in ["revers", "vacate", "remand"])
            rows.append({
                "term": term,
                "lower_court": lc_name,
                "issue_area": issue_label,
                "disposition": disp_label,
                "affirmed": affirmed,
                "reversed": reversed_,
            })
            time.sleep(0.02)
    return pd.DataFrame(rows)

def compute_stats(df: pd.DataFrame, circuit_kw: str, issue: str) -> dict:
    filtered = df.copy()
    if circuit_kw:
        filtered = filtered[filtered["lower_court"].str.contains(circuit_kw, case=False, na=False)]
    if issue and issue != "Any":
        filtered = filtered[filtered["issue_area"].str.contains(issue, case=False, na=False)]

    total = len(filtered)
    if total == 0:
        return {"total": 0, "affirm_pct": None, "reverse_pct": None, "df": filtered}

    affirm_pct = filtered["affirmed"].sum() / total * 100
    reverse_pct = filtered["reversed"].sum() / total * 100
    return {
        "total": total,
        "affirm_pct": affirm_pct,
        "reverse_pct": reverse_pct,
        "other_pct": 100 - affirm_pct - reverse_pct,
        "df": filtered,
    }

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🎯 Case Outcome Predictor")
st.markdown(
    "Based on historical SCOTUS data, estimate the likelihood that a case from a given "
    "lower court and issue area will be **reversed**, **affirmed**, or **remanded** by the Supreme Court. "
    "This is a statistical tool — not a legal prediction."
)

st.info(
    "This page loads detailed case data from Oyez. Select fewer terms for a faster result, "
    "or choose a larger window for higher confidence. Results are cached after first load."
)

with st.form("predictor_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        circuit_label = st.selectbox("Lower Court / Circuit", list(CIRCUIT_KEYWORDS.keys()))
    with col2:
        issue_area = st.selectbox("Issue Area", ["Any"] + ISSUE_AREAS)
    with col3:
        num_terms = st.slider("Number of recent terms to analyze", 3, 15, 8)
    submitted = st.form_submit_button("Predict", type="primary")

if submitted:
    terms_tuple = tuple(range(2023, 2023 - num_terms, -1))
    with st.spinner(f"Loading {num_terms} terms of data from Oyez... (this may take a minute)"):
        df = load_historical_data(terms_tuple)
    st.session_state["predictor_df"] = df
    st.session_state["predictor_params"] = (circuit_label, issue_area, num_terms)

if "predictor_df" in st.session_state:
    df = st.session_state["predictor_df"]
    circuit_label, issue_area, num_terms = st.session_state.get("predictor_params", ("Any / Unknown", "Any", 8))
    circuit_kw = CIRCUIT_KEYWORDS.get(circuit_label, "")

    stats = compute_stats(df, circuit_kw, issue_area if issue_area != "Any" else "")

    st.divider()
    st.subheader("Results")

    if stats["total"] == 0:
        st.warning(
            f"No historical cases found matching **{circuit_label}** + **{issue_area}** "
            f"in the last {num_terms} terms. Try broadening your filters."
        )
    else:
        aff = stats["affirm_pct"]
        rev = stats["reverse_pct"]
        oth = stats["other_pct"]

        # Verdict callout
        if rev > aff:
            verdict = "⬆️ **More likely to be REVERSED**"
            verdict_color = "#E74C3C"
        elif aff > rev:
            verdict = "✅ **More likely to be AFFIRMED**"
            verdict_color = "#27AE60"
        else:
            verdict = "⚖️ **Roughly equal odds**"
            verdict_color = "#F39C12"

        st.markdown(
            f"<div style='background:{verdict_color}22;border-left:5px solid {verdict_color};"
            f"padding:14px 18px;border-radius:6px;font-size:1.15em'>{verdict}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cases Analyzed", stats["total"])
        m2.metric("Affirmed", f"{aff:.1f}%")
        m3.metric("Reversed / Vacated", f"{rev:.1f}%")
        m4.metric("Other Outcome", f"{oth:.1f}%")

        # Gauge chart
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=rev,
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
                    "value": aff,
                },
            },
            number={"suffix": "%"},
        ))
        fig_gauge.update_layout(height=280, margin=dict(l=30, r=30, t=60, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # Breakdown by issue area (if circuit was selected)
        if circuit_kw:
            st.subheader(f"Outcome Breakdown by Issue Area — {circuit_label}")
            issue_rows = []
            for ia_label, grp in stats["df"].groupby("issue_area"):
                total_ia = len(grp)
                rev_ia = grp["reversed"].sum()
                aff_ia = grp["affirmed"].sum()
                issue_rows.append({
                    "Issue Area": ia_label,
                    "Cases": total_ia,
                    "Reversal %": round(rev_ia / total_ia * 100, 1),
                    "Affirm %": round(aff_ia / total_ia * 100, 1),
                })
            if issue_rows:
                ia_df = pd.DataFrame(issue_rows).sort_values("Reversal %", ascending=False)
                fig_ia = px.bar(
                    ia_df, x="Issue Area", y=["Reversal %", "Affirm %"],
                    barmode="group",
                    title=f"{circuit_label} — Reversal vs. Affirmance by Issue Area",
                    color_discrete_map={"Reversal %": "#E74C3C", "Affirm %": "#27AE60"},
                )
                fig_ia.update_layout(
                    height=360, plot_bgcolor="white", paper_bgcolor="white",
                    xaxis_tickangle=-30,
                )
                st.plotly_chart(fig_ia, use_container_width=True)

        # Trend over time
        st.subheader("Reversal Rate Trend Over Time")
        trend_rows = []
        for term_val, grp in stats["df"].groupby("term"):
            total_t = len(grp)
            rev_t = grp["reversed"].sum()
            trend_rows.append({
                "Term": term_val,
                "Reversal %": round(rev_t / total_t * 100, 1),
                "Cases": total_t,
            })
        if trend_rows:
            trend_df = pd.DataFrame(trend_rows).sort_values("Term")
            fig_trend = px.line(
                trend_df, x="Term", y="Reversal %",
                markers=True, title="Reversal Rate by Term",
                labels={"Reversal %": "Reversal Rate (%)"},
            )
            fig_trend.update_layout(
                height=280, plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        st.caption(
            f"Based on {stats['total']} cases from the {num_terms} most recent terms "
            f"matching the selected filters. Statistical trends, not legal advice."
        )
