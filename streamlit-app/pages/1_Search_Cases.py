import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from utils.oyez_api import search_cases, get_case_detail, extract_court_journey
from utils.charts import build_journey_diagram, build_voting_chart

st.set_page_config(page_title="Search Cases", page_icon="🔍", layout="wide")

st.title("🔍 Search Supreme Court Cases")
st.markdown("Search by case name across recent terms (2000–present).")

query = st.text_input("Enter case name or keyword", placeholder="e.g. Roe, Citizens United, Obergefell")

if query and len(query) >= 3:
    with st.spinner(f'Searching for "{query}"...'):
        results = search_cases(query)

    if not results:
        st.warning("No cases found. Try a different keyword.")
    else:
        st.success(f"Found {len(results)} matching case(s).")
        case_names = [c.get("name", "Unknown") for c in results]
        selected = st.selectbox("Select a case to view", case_names)
        selected_case = next((c for c in results if c.get("name") == selected), None)

        if selected_case:
            href = selected_case.get("href", "")
            with st.spinner("Loading case details..."):
                detail = get_case_detail(href) if href else None

            if not detail:
                st.warning("Could not load case details.")
            else:
                st.subheader(detail.get("name", selected))

                col1, col2 = st.columns([2, 1])
                with col1:
                    desc = detail.get("description") or detail.get("facts_of_the_case", "")
                    if desc:
                        with st.expander("Background & Facts"):
                            st.write(desc)
                    q = detail.get("question", "")
                    if q:
                        with st.expander("Legal Question"):
                            st.write(q)

                with col2:
                    st.markdown("**Metadata**")
                    st.markdown(f"- **Docket:** {detail.get('docket_number', 'N/A')}")
                    disposition = detail.get("disposition") or {}
                    if isinstance(disposition, dict) and disposition.get("label"):
                        st.markdown(f"- **Disposition:** {disposition['label']}")
                    decided_by = detail.get("decided_by") or {}
                    if decided_by:
                        st.markdown(f"- **Decided by:** {decided_by.get('name', 'N/A')}")

                st.subheader("⬆️ Case Journey")
                steps = extract_court_journey(detail)
                lower = detail.get("lower_court") or {}
                lc_name = lower.get("name", "") if isinstance(lower, dict) else ""
                if len(steps) < 2 and lc_name:
                    steps = [
                        {"court": lc_name, "level": "Lower Court", "decision": ""},
                        {"court": "U.S. Supreme Court", "level": "Supreme Court", "decision": ""},
                    ]

                if steps:
                    disposition_label = ""
                    if isinstance(detail.get("disposition"), dict):
                        disposition_label = detail["disposition"].get("label", "")
                    if disposition_label and steps:
                        steps[-1]["decision"] = disposition_label

                    fig = build_journey_diagram(steps, detail.get("name", selected))
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Journey data not available for this case.")

                st.subheader("⚖️ Justice Votes")
                justices = []
                for dec in detail.get("decisions", []):
                    for vote in dec.get("votes", []):
                        member = vote.get("member", {}) or {}
                        justices.append({
                            "name": member.get("name", "Unknown"),
                            "vote": vote.get("vote", ""),
                        })

                if justices:
                    fig2 = build_voting_chart(justices)
                    if fig2:
                        st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Voting data not available for this case.")
elif query:
    st.info("Please enter at least 3 characters to search.")
