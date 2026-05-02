import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from utils.oyez_api import get_cases_by_term, get_recent_terms
from utils.charts import build_issue_area_chart, build_decision_trend_chart

st.set_page_config(page_title="Timeline Browser", page_icon="📅", layout="wide")

st.title("📅 Case Timeline Browser")
st.markdown("Browse Supreme Court cases across terms and explore trends.")

terms_available = get_recent_terms(20)

col1, col2 = st.columns(2)
with col1:
    start_term = st.selectbox("From Term", terms_available, index=len(terms_available) - 1)
with col2:
    end_term = st.selectbox("To Term", terms_available, index=0)

if start_term > end_term:
    start_term, end_term = end_term, start_term

selected_terms = list(range(start_term, end_term + 1))

if st.button("Load Timeline", type="primary"):
    cases_by_term: dict[int, list] = {}
    progress = st.progress(0)
    for i, t in enumerate(selected_terms):
        with st.spinner(f"Loading term {t}..."):
            cases_by_term[t] = get_cases_by_term(t)
        progress.progress((i + 1) / len(selected_terms))

    st.session_state["cases_by_term"] = cases_by_term
    progress.empty()

if "cases_by_term" in st.session_state:
    cases_by_term = st.session_state["cases_by_term"]

    trend_fig = build_decision_trend_chart(cases_by_term)
    if trend_fig:
        st.plotly_chart(trend_fig, use_container_width=True)

    all_cases = []
    for term, cases in cases_by_term.items():
        for c in cases:
            all_cases.append({
                "Term": term,
                "Case Name": c.get("name", ""),
                "Issue Area": (c.get("issue_area") or {}).get("label", "Unknown") if isinstance(c.get("issue_area"), dict) else str(c.get("issue_area", "Unknown")),
                "Decided": c.get("term", ""),
            })

    if all_cases:
        df = pd.DataFrame(all_cases)

        issue_fig = build_issue_area_chart(all_cases)
        if issue_fig:
            st.plotly_chart(issue_fig, use_container_width=True)

        st.subheader("All Cases")
        issue_filter = st.multiselect(
            "Filter by Issue Area",
            options=sorted(df["Issue Area"].unique()),
            default=[]
        )
        if issue_filter:
            df = df[df["Issue Area"].isin(issue_filter)]

        st.dataframe(df, use_container_width=True, height=400)
        st.caption(f"Showing {len(df)} cases across {len(cases_by_term)} term(s).")
