import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import time

st.set_page_config(page_title="Key Decisions by Issue Area", page_icon="📋", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

ISSUE_AREAS = [
    "Criminal Procedure", "Civil Rights", "First Amendment", "Due Process",
    "Privacy", "Economic Activity", "Judicial Power", "Federalism",
    "Federal Taxation", "Unions", "Attorneys", "Interstate Relations",
    "Miscellaneous", "Private Action",
]

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

def get_issue_label(c: dict) -> str:
    ia = c.get("issue_area")
    if isinstance(ia, dict):
        return ia.get("label", "Unknown")
    return str(ia) if ia else "Unknown"

def get_disposition_label(c: dict) -> str:
    d = c.get("disposition")
    if isinstance(d, dict):
        return d.get("label", "Unknown")
    return str(d) if d else "Unknown"

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📋 Key Decisions by Issue Area")
st.markdown("Browse all SCOTUS decisions in a selected legal domain, ranked by term.")

col1, col2, col3 = st.columns(3)
with col1:
    issue = st.selectbox("Legal Issue Area", ISSUE_AREAS)
with col2:
    import datetime as _dt; _CURRENT_YEAR = _dt.date.today().year
    _term_range = list(range(_CURRENT_YEAR, 1989, -1))
    start_term = st.selectbox("From Term", _term_range, index=10)
with col3:
    end_term = st.selectbox("To Term", _term_range, index=0)

if start_term > end_term:
    start_term, end_term = end_term, start_term
terms = list(range(start_term, end_term + 1))

if st.button("Load Decisions", type="primary"):
    rows = []
    progress = st.progress(0)
    for idx, term in enumerate(sorted(terms, reverse=True)):
        cases = fetch_cases_for_term(term)
        for c in cases:
            label = get_issue_label(c)
            if issue.lower() in label.lower():
                rows.append({
                    "Term": term,
                    "Case": c.get("name", ""),
                    "Disposition": get_disposition_label(c),
                    "Issue Area": label,
                    "href": c.get("href", ""),
                })
        progress.progress((idx + 1) / len(terms))
        time.sleep(0.02)
    progress.empty()
    st.session_state["issue_rows"] = rows
    st.session_state["issue_area"] = issue

if "issue_rows" in st.session_state and st.session_state.get("issue_area") == issue:
    rows = st.session_state["issue_rows"]

    if not rows:
        st.warning(f"No cases found for '{issue}' in the selected range.")
        st.stop()

    df = pd.DataFrame(rows)
    st.success(f"Found **{len(df)}** decisions in **{issue}** from {start_term}–{end_term}.")

    # ── Outcome breakdown ────────────────────────────────────────────────────
    col_pie, col_trend = st.columns(2)
    with col_pie:
        disp_counts = df["Disposition"].value_counts().reset_index()
        disp_counts.columns = ["Disposition", "Count"]
        fig_pie = px.pie(
            disp_counts, names="Disposition", values="Count",
            title=f"{issue} — Decision Outcomes", hole=0.3,
        )
        fig_pie.update_layout(height=330)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_trend:
        term_counts = df.groupby("Term").size().reset_index(name="Cases")
        fig_trend = px.bar(
            term_counts.sort_values("Term"),
            x="Term", y="Cases",
            title=f"{issue} — Cases per Term",
            color="Cases", color_continuous_scale="Blues",
        )
        fig_trend.update_layout(
            height=330, coloraxis_showscale=False,
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # ── Case table ───────────────────────────────────────────────────────────
    st.subheader("Case List")
    disp_filter = st.multiselect(
        "Filter by Disposition",
        options=sorted(df["Disposition"].unique()),
        default=[],
    )
    display_df = df[df["Disposition"].isin(disp_filter)] if disp_filter else df
    display_df = display_df[["Term", "Case", "Disposition"]].sort_values("Term", ascending=False)
    st.dataframe(display_df, use_container_width=True, height=400)
    st.caption(f"Showing {len(display_df)} cases.")

    # ── Case drilldown ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Case Drilldown")
    case_names = df["Case"].tolist()
    selected_case_name = st.selectbox("Select a case to inspect", case_names)
    row = df[df["Case"] == selected_case_name].iloc[0]

    if row.get("href"):
        with st.spinner("Loading case details..."):
            detail = fetch_case_detail(row["href"])
        if detail:
            question = detail.get("question", "")
            facts = detail.get("facts_of_the_case", "") or detail.get("description", "")
            col_q, col_f = st.columns(2)
            with col_q:
                if question:
                    st.markdown("**Legal Question**")
                    st.write(question)
            with col_f:
                if facts:
                    st.markdown("**Background**")
                    st.write(facts)
            # Votes
            votes = []
            for dec in detail.get("decisions", []):
                for vote in dec.get("votes", []):
                    member = vote.get("member", {}) or {}
                    votes.append({"Justice": member.get("name", "?"), "Vote": vote.get("vote", "")})
            if votes:
                vote_df = pd.DataFrame(votes)
                maj = vote_df[vote_df["Vote"].str.lower().isin(["majority", "concurrence"])]["Justice"].tolist()
                dis = vote_df[vote_df["Vote"].str.lower() == "dissent"]["Justice"].tolist()
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**✅ Majority ({len(maj)}):** {', '.join(maj)}")
                with c2:
                    st.markdown(f"**❌ Dissent ({len(dis)}):** {', '.join(dis) if dis else 'None'}")
