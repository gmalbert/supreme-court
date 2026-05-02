import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import time

st.set_page_config(page_title="Justice Career Overview", page_icon="👨‍⚖️", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

@st.cache_data(show_spinner=False)
def fetch_justices() -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/justices", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_justice_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def fetch_cases_for_term(term: int) -> list[dict]:
    try:
        r = requests.get(
            f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
            headers=HEADERS,
            timeout=10,
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

def get_justice_votes(justice_name: str, terms: list[int]) -> pd.DataFrame:
    rows = []
    progress = st.progress(0)
    for idx, term in enumerate(terms):
        cases = fetch_cases_for_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            detail = fetch_case_detail(href)
            if not detail:
                continue
            for dec in detail.get("decisions", []):
                winning_party = dec.get("winning_party", "")
                for vote in dec.get("votes", []):
                    member = vote.get("member", {}) or {}
                    name = member.get("name", "")
                    if justice_name.lower() in name.lower():
                        rows.append({
                            "Term": term,
                            "Case": detail.get("name", ""),
                            "Vote": vote.get("vote", ""),
                            "Winning Party": winning_party,
                            "Issue Area": (
                                detail.get("issue_area", {}).get("label", "Unknown")
                                if isinstance(detail.get("issue_area"), dict)
                                else str(detail.get("issue_area", "Unknown"))
                            ),
                        })
            time.sleep(0.02)
        progress.progress((idx + 1) / len(terms))
    progress.empty()
    return pd.DataFrame(rows)

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("👨‍⚖️ Justice Career Overview")
st.markdown("Explore a justice's voting history, issue area tendencies, and notable cases.")

with st.spinner("Loading justices..."):
    justices = fetch_justices()

if not justices:
    st.error("Could not load justices from Oyez. Please try again later.")
    st.stop()

# Sort by last name
justices_sorted = sorted(justices, key=lambda j: j.get("name", "").split()[-1])
justice_names = [j.get("name", "Unknown") for j in justices_sorted]
selected_name = st.selectbox("Select a Justice", justice_names)
selected_justice = next((j for j in justices_sorted if j.get("name") == selected_name), None)

if not selected_justice:
    st.stop()

# ── Justice bio card ─────────────────────────────────────────────────────────
href = selected_justice.get("href", "")
with st.spinner("Loading justice profile..."):
    detail = fetch_justice_detail(href) if href else None

col_bio, col_stats = st.columns([2, 1])

with col_bio:
    st.subheader(selected_name)
    if detail:
        roles = detail.get("roles", [])
        if roles:
            for role in roles:
                court = role.get("institution_name", "")
                date_start = role.get("date_start", 0)
                date_end = role.get("date_end", 0)
                title = role.get("role_title", "Justice")

                import datetime
                def ts_to_year(ts):
                    if ts:
                        try:
                            return datetime.datetime.utcfromtimestamp(ts).year
                        except Exception:
                            return "?"
                    return "present"

                start_yr = ts_to_year(date_start)
                end_yr = ts_to_year(date_end) if date_end else "present"
                st.markdown(f"- **{title}**, {court} ({start_yr} – {end_yr})")

        desc = detail.get("description", "")
        if desc:
            with st.expander("Biography"):
                st.write(desc)

with col_stats:
    st.markdown("**Quick Info**")
    if detail:
        roles = detail.get("roles", [])
        if roles:
            latest = roles[-1]
            appointer = latest.get("appointing_president", "")
            if appointer:
                st.markdown(f"- **Appointed by:** {appointer}")
            party = latest.get("party_affiliation", {})
            if isinstance(party, dict) and party.get("label"):
                st.markdown(f"- **Party:** {party['label']}")

st.divider()

# ── Voting analysis ───────────────────────────────────────────────────────────
st.subheader("Voting History Analysis")
st.info(
    "This analysis fetches live case data from Oyez for each selected term. "
    "Selecting many terms will take longer to load."
)

import datetime as _dt; _CURRENT_YEAR = _dt.date.today().year
available_terms = list(range(_CURRENT_YEAR, _CURRENT_YEAR - 27, -1))
selected_terms = st.multiselect(
    "Select Terms to Analyze",
    options=available_terms,
    default=available_terms[:5],
    max_selections=10,
)

if not selected_terms:
    st.warning("Please select at least one term.")
    st.stop()

if st.button("Load Voting History", type="primary"):
    with st.spinner(f"Fetching voting records for {selected_name} across {len(selected_terms)} term(s)..."):
        df = get_justice_votes(selected_name, sorted(selected_terms, reverse=True))
    st.session_state["justice_df"] = df
    st.session_state["justice_name"] = selected_name

if "justice_df" in st.session_state and st.session_state.get("justice_name") == selected_name:
    df = st.session_state["justice_df"]

    if df.empty:
        st.warning("No voting data found for this justice in the selected terms.")
        st.stop()

    st.success(f"Found {len(df)} votes across {df['Term'].nunique()} term(s).")

    # Summary metrics
    total = len(df)
    majority = len(df[df["Vote"].str.lower().isin(["majority", "concurrence"])])
    dissent = len(df[df["Vote"].str.lower() == "dissent"])

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Votes", total)
    m2.metric("Majority / Concurrence", majority, f"{majority/total*100:.0f}%")
    m3.metric("Dissents", dissent, f"{dissent/total*100:.0f}%")

    col_left, col_right = st.columns(2)

    with col_left:
        # Vote type breakdown
        vote_counts = df["Vote"].value_counts().reset_index()
        vote_counts.columns = ["Vote Type", "Count"]
        color_map = {
            "majority": "#27AE60",
            "concurrence": "#2ECC71",
            "dissent": "#E74C3C",
            "recusal": "#95A5A6",
        }
        colors = [color_map.get(v.lower(), "#BDC3C7") for v in vote_counts["Vote Type"]]
        fig_votes = go.Figure(go.Bar(
            x=vote_counts["Vote Type"],
            y=vote_counts["Count"],
            marker_color=colors,
            text=vote_counts["Count"],
            textposition="outside",
        ))
        fig_votes.update_layout(
            title="Vote Type Breakdown",
            xaxis_title="Vote Type",
            yaxis_title="Count",
            height=320,
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_votes, use_container_width=True)

    with col_right:
        # Issue area breakdown
        issue_counts = df["Issue Area"].value_counts().reset_index()
        issue_counts.columns = ["Issue Area", "Count"]
        fig_issues = px.pie(
            issue_counts,
            names="Issue Area",
            values="Count",
            title="Cases by Issue Area",
            hole=0.3,
        )
        fig_issues.update_layout(height=320)
        st.plotly_chart(fig_issues, use_container_width=True)

    # Dissent rate by term
    if df["Term"].nunique() > 1:
        term_stats = []
        for term, grp in df.groupby("Term"):
            total_t = len(grp)
            dissent_t = len(grp[grp["Vote"].str.lower() == "dissent"])
            term_stats.append({"Term": term, "Dissent Rate (%)": dissent_t / total_t * 100, "Cases": total_t})
        term_df = pd.DataFrame(term_stats).sort_values("Term")
        fig_trend = px.bar(
            term_df,
            x="Term",
            y="Dissent Rate (%)",
            title=f"{selected_name} — Dissent Rate by Term",
            text="Cases",
            color="Dissent Rate (%)",
            color_continuous_scale="Reds",
        )
        fig_trend.update_layout(height=320, coloraxis_showscale=False, plot_bgcolor="white")
        st.plotly_chart(fig_trend, use_container_width=True)

    # Notable dissents
    st.subheader("Dissenting Votes")
    dissents_df = df[df["Vote"].str.lower() == "dissent"][["Term", "Case", "Issue Area"]].drop_duplicates()
    if dissents_df.empty:
        st.info("No dissenting votes found in the selected terms.")
    else:
        st.dataframe(dissents_df.sort_values("Term", ascending=False), use_container_width=True, height=300)

    # Full vote table
    with st.expander("Full Voting Record"):
        st.dataframe(df.sort_values(["Term", "Case"], ascending=[False, True]), use_container_width=True, height=400)
