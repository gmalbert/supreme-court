import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import time

st.set_page_config(page_title="Court Comparison", page_icon="⚖️", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

CIRCUIT_COURTS = {
    "1st Circuit": "First Circuit",
    "2nd Circuit": "Second Circuit",
    "3rd Circuit": "Third Circuit",
    "4th Circuit": "Fourth Circuit",
    "5th Circuit": "Fifth Circuit",
    "6th Circuit": "Sixth Circuit",
    "7th Circuit": "Seventh Circuit",
    "8th Circuit": "Eighth Circuit",
    "9th Circuit": "Ninth Circuit",
    "10th Circuit": "Tenth Circuit",
    "11th Circuit": "Eleventh Circuit",
    "D.C. Circuit": "District of Columbia Circuit",
    "Federal Circuit": "Federal Circuit",
    "State Supreme Courts": "state",
    "District Courts": "district",
}

@st.cache_data(show_spinner=False)
def fetch_cases_for_term(term: int) -> list[dict]:
    try:
        r = requests.get(
            f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
            headers=HEADERS, timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_case_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def court_matches(lower_court_name: str, search_term: str) -> bool:
    if not lower_court_name or not search_term:
        return False
    return search_term.lower() in lower_court_name.lower()

def analyze_court(court_keyword: str, terms: list[int]) -> list[dict]:
    rows = []
    for term in terms:
        cases = fetch_cases_for_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            detail = fetch_case_detail(href)
            if not detail:
                continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name", "") if isinstance(lower, dict) else str(lower)
            if not court_matches(lc_name, court_keyword):
                continue
            disposition = detail.get("disposition") or {}
            disp_label = disposition.get("label", "Unknown") if isinstance(disposition, dict) else str(disposition)
            affirmed = any(w in disp_label.lower() for w in ["affirm", "uphold"])
            reversed_ = any(w in disp_label.lower() for w in ["revers", "vacate", "remand"])
            rows.append({
                "Term": term,
                "Case": detail.get("name", ""),
                "Lower Court": lc_name,
                "Disposition": disp_label,
                "Affirmed": affirmed,
                "Reversed": reversed_,
                "Issue Area": (
                    detail.get("issue_area", {}).get("label", "Unknown")
                    if isinstance(detail.get("issue_area"), dict)
                    else str(detail.get("issue_area", "Unknown"))
                ),
            })
        time.sleep(0.02)
    return rows

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("⚖️ Court of Appeals Comparison")
st.markdown(
    "Compare two federal circuit courts side-by-side: see how often SCOTUS "
    "affirmed or reversed their decisions, and which issue areas came up most."
)

col1, col2 = st.columns(2)
with col1:
    court_a_label = st.selectbox("Court A", list(CIRCUIT_COURTS.keys()), index=8)  # 9th Circuit default
with col2:
    court_b_label = st.selectbox("Court B", list(CIRCUIT_COURTS.keys()), index=4)  # 5th Circuit default

available_terms = list(range(2023, 2004, -1))
selected_terms = st.multiselect(
    "Terms to analyze",
    options=available_terms,
    default=available_terms[:6],
    max_selections=10,
)

if not selected_terms:
    st.warning("Select at least one term.")
    st.stop()

court_a_kw = CIRCUIT_COURTS[court_a_label]
court_b_kw = CIRCUIT_COURTS[court_b_label]

if st.button("Compare Courts", type="primary"):
    with st.spinner(f"Fetching data for {court_a_label}..."):
        rows_a = analyze_court(court_a_kw, sorted(selected_terms, reverse=True))
    with st.spinner(f"Fetching data for {court_b_label}..."):
        rows_b = analyze_court(court_b_kw, sorted(selected_terms, reverse=True))

    st.session_state["compare_a"] = (court_a_label, pd.DataFrame(rows_a))
    st.session_state["compare_b"] = (court_b_label, pd.DataFrame(rows_b))

if "compare_a" in st.session_state and "compare_b" in st.session_state:
    label_a, df_a = st.session_state["compare_a"]
    label_b, df_b = st.session_state["compare_b"]

    def summary_stats(df: pd.DataFrame, label: str) -> dict:
        total = len(df)
        affirmed = df["Affirmed"].sum() if total else 0
        reversed_ = df["Reversed"].sum() if total else 0
        return {
            "Court": label,
            "Cases Reviewed": total,
            "Affirmed": int(affirmed),
            "Reversed / Vacated": int(reversed_),
            "Affirm Rate": f"{affirmed/total*100:.0f}%" if total else "N/A",
            "Reversal Rate": f"{reversed_/total*100:.0f}%" if total else "N/A",
        }

    stats_a = summary_stats(df_a, label_a)
    stats_b = summary_stats(df_b, label_b)

    # ── Summary metrics ──────────────────────────────────────────────────────
    st.subheader("Summary")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(f"### {label_a}")
        st.metric("Cases Reviewed by SCOTUS", stats_a["Cases Reviewed"])
        st.metric("Affirmed", stats_a["Affirmed"], stats_a["Affirm Rate"])
        st.metric("Reversed / Vacated", stats_a["Reversed / Vacated"], stats_a["Reversal Rate"])

    with col_b:
        st.markdown(f"### {label_b}")
        st.metric("Cases Reviewed by SCOTUS", stats_b["Cases Reviewed"])
        st.metric("Affirmed", stats_b["Affirmed"], stats_b["Affirm Rate"])
        st.metric("Reversed / Vacated", stats_b["Reversed / Vacated"], stats_b["Reversal Rate"])

    st.divider()

    # ── Side-by-side reversal rate bar chart ─────────────────────────────────
    st.subheader("Affirmed vs. Reversed")
    categories = ["Affirmed", "Reversed / Vacated", "Other"]

    def get_counts(df, total):
        aff = int(df["Affirmed"].sum())
        rev = int(df["Reversed"].sum())
        other = total - aff - rev
        return [aff, rev, max(other, 0)]

    total_a = len(df_a)
    total_b = len(df_b)
    counts_a = get_counts(df_a, total_a)
    counts_b = get_counts(df_b, total_b)

    fig_bar = go.Figure(data=[
        go.Bar(name=label_a, x=categories, y=counts_a, marker_color="#4A90D9"),
        go.Bar(name=label_b, x=categories, y=counts_b, marker_color="#E67E22"),
    ])
    fig_bar.update_layout(
        barmode="group",
        title="Outcome Comparison",
        xaxis_title="Outcome",
        yaxis_title="Number of Cases",
        height=350,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Issue area comparison ────────────────────────────────────────────────
    st.subheader("Issue Areas Sent to SCOTUS")

    def issue_counts(df):
        return df["Issue Area"].value_counts().reset_index().rename(
            columns={"index": "Issue Area", "Issue Area": "Count", "count": "Count"}
        )

    ic_a = issue_counts(df_a)
    ic_b = issue_counts(df_b)

    col_ia, col_ib = st.columns(2)
    with col_ia:
        if not ic_a.empty:
            fig_ia = px.bar(
                ic_a.head(8),
                x="Count" if "Count" in ic_a.columns else ic_a.columns[1],
                y=ic_a.columns[0],
                orientation="h",
                title=f"{label_a} — Issue Areas",
                color_discrete_sequence=["#4A90D9"],
            )
            fig_ia.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_ia, use_container_width=True)

    with col_ib:
        if not ic_b.empty:
            fig_ib = px.bar(
                ic_b.head(8),
                x="Count" if "Count" in ic_b.columns else ic_b.columns[1],
                y=ic_b.columns[0],
                orientation="h",
                title=f"{label_b} — Issue Areas",
                color_discrete_sequence=["#E67E22"],
            )
            fig_ib.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_ib, use_container_width=True)

    # ── Case tables ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Case Details")
    tab_a, tab_b = st.tabs([label_a, label_b])

    with tab_a:
        if df_a.empty:
            st.info("No cases found for this court in the selected terms.")
        else:
            st.dataframe(
                df_a[["Term", "Case", "Disposition", "Issue Area"]].sort_values("Term", ascending=False),
                use_container_width=True, height=350,
            )

    with tab_b:
        if df_b.empty:
            st.info("No cases found for this court in the selected terms.")
        else:
            st.dataframe(
                df_b[["Term", "Case", "Disposition", "Issue Area"]].sort_values("Term", ascending=False),
                use_container_width=True, height=350,
            )
