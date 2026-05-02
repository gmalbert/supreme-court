import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.oyez_api import get_cases_by_term, get_recent_terms

st.set_page_config(page_title="Statistics", page_icon="📊", layout="wide")

st.title("📊 SCOTUS Statistics")
st.markdown("High-level statistics about Supreme Court decisions.")

term = st.selectbox("Select Term", get_recent_terms(20))

with st.spinner("Loading cases..."):
    cases = get_cases_by_term(term)

if not cases:
    st.warning("No cases found.")
    st.stop()

st.metric("Total Cases", len(cases))

rows = []
for c in cases:
    issue = c.get("issue_area", {})
    if isinstance(issue, dict):
        issue_label = issue.get("label", "Unknown")
    else:
        issue_label = str(issue) if issue else "Unknown"

    disposition = c.get("disposition", {})
    if isinstance(disposition, dict):
        disposition_label = disposition.get("label", "Unknown")
    else:
        disposition_label = str(disposition) if disposition else "Unknown"

    rows.append({
        "Case Name": c.get("name", ""),
        "Issue Area": issue_label,
        "Disposition": disposition_label,
    })

df = pd.DataFrame(rows)

col1, col2 = st.columns(2)
with col1:
    issue_counts = df["Issue Area"].value_counts().reset_index()
    issue_counts.columns = ["Issue Area", "Count"]
    fig = px.bar(
        issue_counts,
        x="Count",
        y="Issue Area",
        orientation="h",
        title="Cases by Issue Area",
        color="Count",
        color_continuous_scale="Blues",
    )
    fig.update_layout(height=400, showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    disp_counts = df["Disposition"].value_counts().reset_index()
    disp_counts.columns = ["Disposition", "Count"]
    fig2 = px.pie(
        disp_counts,
        names="Disposition",
        values="Count",
        title="Case Dispositions",
        hole=0.3,
    )
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Case Listing")
search = st.text_input("Filter by name")
filtered = df[df["Case Name"].str.contains(search, case=False)] if search else df
st.dataframe(filtered, use_container_width=True, height=350)
