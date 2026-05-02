import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from utils.oyez_api import get_cases_by_term, get_case_detail, get_recent_terms
from utils.charts import build_voting_chart

st.set_page_config(page_title="Justice Voting Patterns", page_icon="⚖️", layout="wide")

st.title("⚖️ Justice Voting Patterns")
st.markdown("Explore how individual justices voted on Supreme Court cases.")

col1, col2 = st.columns(2)
with col1:
    term = st.selectbox("Select Term", get_recent_terms(15), key="jv_term")

with st.spinner("Loading cases..."):
    cases = get_cases_by_term(term)

if not cases:
    st.warning("No cases found for the selected term.")
    st.stop()

case_names = [c.get("name", "Unknown") for c in cases]
selected_name = st.selectbox("Select a Case", case_names)

selected_case = next((c for c in cases if c.get("name") == selected_name), None)
if not selected_case:
    st.stop()

href = selected_case.get("href", "")
if not href:
    st.warning("No detail link available.")
    st.stop()

with st.spinner("Loading case details..."):
    detail = get_case_detail(href)

if not detail:
    st.warning("Could not load case details.")
    st.stop()

decisions = detail.get("decisions", [])
if not decisions:
    st.info("No voting data available for this case.")
    st.stop()

for decision in decisions:
    winning_party = decision.get("winning_party", "Unknown")
    votes = decision.get("votes", [])

    st.subheader(f"Winning Party: {winning_party}")

    if votes:
        fig = build_voting_chart(votes)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        rows = []
        for v in votes:
            member = v.get("member", {}) or {}
            rows.append({
                "Justice": member.get("name", "Unknown"),
                "Vote": v.get("vote", ""),
            })
        if rows:
            df = pd.DataFrame(rows)
            majority = df[df["Vote"].str.lower().isin(["majority", "concurrence"])]
            dissent = df[df["Vote"].str.lower() == "dissent"]

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Majority/Concurrence**")
                for _, row in majority.iterrows():
                    st.markdown(f"- {row['Justice']} ({row['Vote']})")
            with c2:
                st.markdown("**Dissent**")
                if dissent.empty:
                    st.markdown("_No dissents_")
                else:
                    for _, row in dissent.iterrows():
                        st.markdown(f"- {row['Justice']}")
    st.divider()
