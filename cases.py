import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from utils import add_sidebar_logo
from utils.oyez_api import (
    get_cases_by_term,
    get_case_detail,
    get_recent_terms,
    extract_court_journey,
)
from utils.charts import build_journey_diagram, build_voting_chart
from utils.local_data import strip_html, safe_md

# ── App-wide config — called ONCE here; sub-pages must NOT call set_page_config ──
st.set_page_config(
    page_title="Supreme Scrutiny",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def home_page():
    add_sidebar_logo()
    st.title("🏛️ Supreme Scrutiny")
    st.markdown(
        "Explore how Supreme Court cases traveled through the judicial system — "
        "from the originating court all the way to the nation's highest bench."
    )
    st.markdown("---")

    # Sidebar controls
    with st.sidebar:
        st.header("Find a Case")
        term = st.selectbox("Select Term", get_recent_terms(25), index=0)
        st.markdown("*Data provided by [Oyez](https://www.oyez.org)*")

    with st.spinner(f"Loading {term} term cases..."):
        cases = get_cases_by_term(term)

    if not cases:
        st.error("Could not load cases for this term. Please try another year.")
        st.stop()

    case_names = sorted([c.get("name", "Unknown") for c in cases])
    selected_name = st.selectbox(
        f"Select a Case ({len(cases)} cases in {term} term)",
        case_names,
        key="main_case_select",
    )

    selected_case = next((c for c in cases if c.get("name") == selected_name), None)
    if not selected_case:
        st.stop()

    href = selected_case.get("href", "")
    with st.spinner("Loading case details from Oyez..."):
        detail = get_case_detail(href) if href else None

    if not detail:
        st.warning("Could not load full case details. Try another case.")
        st.stop()

    # ── Case header ──────────────────────────────────────────────────────────────
    col_info, col_meta = st.columns([2, 1])

    with col_info:
        st.subheader(detail.get("name", selected_name))
        description = detail.get("description") or detail.get("facts_of_the_case", "")
        if description:
            with st.expander("Background & Facts", expanded=False):
                st.write(safe_md(description))

        question = detail.get("question", "")
        if question:
            with st.expander("Legal Question Before the Court", expanded=False):
                st.write(safe_md(question))

    with col_meta:
        st.markdown("**Case Metadata**")
        docket = detail.get("docket_number", "N/A")
        st.markdown(f"- **Docket:** {docket}")
        argued = detail.get("argued_on", [])
        if argued:
            st.markdown(f"- **Argued:** {argued[0].get('date', 'N/A') if isinstance(argued[0], dict) else argued[0]}")
        decided = detail.get("decided_on", [])
        if decided:
            st.markdown(f"- **Decided:** {decided[0].get('date', 'N/A') if isinstance(decided[0], dict) else decided[0]}")
        decided_by = detail.get("decided_by") or {}
        if decided_by:
            st.markdown(f"- **Court:** {decided_by.get('name', 'N/A')}")
        disposition = detail.get("disposition") or {}
        if isinstance(disposition, dict) and disposition.get("label"):
            st.markdown(f"- **Disposition:** {disposition['label']}")

    st.markdown("---")

    # ── Journey Diagram ───────────────────────────────────────────────────────────
    st.subheader("⬆️ Case Journey Through the Courts")

    steps = extract_court_journey(detail)

    if len(steps) < 2:
        # Try to surface whatever lower court info is available
        lower = detail.get("lower_court") or {}
        lc_name = lower.get("name", "") if isinstance(lower, dict) else str(lower)
        if lc_name:
            lc_lower = lc_name.lower()
            if any(kw in lc_lower for kw in ("court of appeals", "circuit", "appellate",
                                              "supreme court of", "state supreme", "court of last resort")):
                lc_level = "Appellate Court"
            else:
                lc_level = "Lower Court"
            steps = [
                {"court": lc_name, "level": lc_level, "decision": ""},
                {"court": "U.S. Supreme Court", "level": "Supreme Court", "decision": ""},
            ]
        else:
            st.info(
                "Court journey data is not available for this case in the Oyez API. "
                "Try a more recent case (2015 onward usually has richer data)."
            )

    if steps:
        # Annotate with disposition at SCOTUS level
        disposition_label = ""
        if isinstance(detail.get("disposition"), dict):
            disposition_label = detail["disposition"].get("label", "")
        if disposition_label and steps:
            steps[-1]["decision"] = disposition_label

        fig = build_journey_diagram(steps, detail.get("name", selected_name))
        if fig:
            col_diag, col_legend = st.columns([3, 1])
            with col_diag:
                st.plotly_chart(fig)
            with col_legend:
                st.markdown("**Court Levels**")
                st.markdown("🔵 &nbsp; Lower Court (District/State)")
                st.markdown("🟠 &nbsp; Intermediate Appeals Court")
                st.markdown("🔴 &nbsp; U.S. Supreme Court")
                st.markdown("")
                st.markdown("**How to read this chart:**")
                st.markdown(
                    "Each node is a court that heard the case. "
                    "The arrow shows the direction of appeal — upward toward SCOTUS."
                )

    st.markdown("---")

    # ── Justice Votes ────────────────────────────────────────────────────────────
    st.subheader("⚖️ Justice Votes")

    justices = []
    for step in steps:
        if step.get("justices"):
            justices = step["justices"]
            break

    if not justices:
        # Pull directly from detail
        decisions = detail.get("decisions") or []
        for dec in decisions:
            for vote in dec.get("votes", []):
                member = vote.get("member", {}) or {}
                justices.append({
                    "name": member.get("name", "Unknown"),
                    "vote": vote.get("vote", ""),
                })

    if justices:
        vote_fig = build_voting_chart(justices)
        if vote_fig:
            st.plotly_chart(vote_fig)

        vote_cols = st.columns(3)
        majority = [j for j in justices if (j.get("vote") or "").lower() in ("majority", "concurrence")]
        dissent = [j for j in justices if (j.get("vote") or "").lower() == "dissent"]
        recusal = [j for j in justices if (j.get("vote") or "").lower() == "recusal"]

        with vote_cols[0]:
            st.markdown("**✅ Majority / Concurrence**")
            for j in majority:
                st.markdown(f"- {j['name']}")
        with vote_cols[1]:
            st.markdown("**❌ Dissent**")
            if dissent:
                for j in dissent:
                    st.markdown(f"- {j['name']}")
            else:
                st.markdown("_None_")
        with vote_cols[2]:
            st.markdown("**🚫 Recusal**")
            if recusal:
                for j in recusal:
                    st.markdown(f"- {j['name']}")
            else:
                st.markdown("_None_")
    else:
        st.info("Voting data not available for this case.")

    st.markdown("---")

    # ── Oral Arguments link ──────────────────────────────────────────────────────
    oral_args = detail.get("oral_argument_audio", [])
    if oral_args:
        docket = detail.get("docket_number", "")
        oyez_case_url = f"https://www.oyez.org/cases/{term}/{docket}"
        st.subheader("🎙️ Oral Arguments")
        for arg in oral_args[:3]:
            if isinstance(arg, dict):
                title = arg.get("title", "Listen on Oyez")
                st.markdown(f"[🎧 {title}]({oyez_case_url})")

    # ── Footer ───────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        "Data sourced from [Oyez](https://www.oyez.org) — a free, multimedia archive of the U.S. Supreme Court. "
        "Use the sidebar pages to explore justice voting patterns, case timelines, and statistics."
    )


# ── Navigation ───────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="Case Journey", icon="🏛️", default=True),
        ],
        "Cases": [
            st.Page("pages/1_Cases.py",      title="Cases",            icon="⚖️"),
        ],
        "People": [
            st.Page("pages/People.py",       title="People",           icon="👥"),
        ],
        "History & Courts": [
            st.Page("pages/History.py",      title="History & Courts", icon="🏛️"),
        ],
        "Analysis": [
            st.Page("pages/Analysis.py",     title="Analysis",         icon="📊"),
            st.Page("pages/Topics.py",       title="Topics & Networks",icon="📚"),
        ],
        "Insights": [
            st.Page("pages/Insights.py",     title="Insights",         icon="🎖️"),
        ],
    }
)
pg.run()
