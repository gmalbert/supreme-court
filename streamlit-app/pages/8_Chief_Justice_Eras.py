import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import time

st.set_page_config(page_title="Chief Justice Eras", page_icon="🏛️", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

ERAS = {
    "Warren Court (1953–1969)": (1953, 1969, "#2980B9"),
    "Burger Court (1969–1986)": (1969, 1986, "#8E44AD"),
    "Rehnquist Court (1986–2005)": (1986, 2005, "#E67E22"),
    "Roberts Court (2005–present)": (2005, 2023, "#C0392B"),
}

ISSUE_LABELS = [
    "Criminal Procedure", "Civil Rights", "First Amendment", "Due Process",
    "Privacy", "Economic Activity", "Judicial Power", "Federalism",
    "Federal Taxation", "Unions",
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

def get_issue_label(c: dict) -> str:
    ia = c.get("issue_area")
    if isinstance(ia, dict):
        return ia.get("label", "Unknown")
    return str(ia) if ia else "Unknown"

def get_disposition(c: dict) -> str:
    d = c.get("disposition")
    if isinstance(d, dict):
        return d.get("label", "Unknown")
    return str(d) if d else "Unknown"

@st.cache_data(show_spinner=False, ttl=600)
def load_era_data(start: int, end: int) -> pd.DataFrame:
    rows = []
    for term in range(start, end + 1):
        cases = fetch_cases_for_term(term)
        for c in cases:
            rows.append({
                "Term": term,
                "Case": c.get("name", ""),
                "Issue Area": get_issue_label(c),
                "Disposition": get_disposition(c),
            })
        time.sleep(0.03)
    return pd.DataFrame(rows)

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🏛️ Chief Justice Era Comparison")
st.markdown(
    "Compare the character of the SCOTUS docket across four eras: "
    "Warren, Burger, Rehnquist, and Roberts courts."
)

selected_eras = st.multiselect(
    "Select Eras to Compare",
    options=list(ERAS.keys()),
    default=["Rehnquist Court (1986–2005)", "Roberts Court (2005–present)"],
)

if len(selected_eras) < 1:
    st.warning("Select at least one era.")
    st.stop()

st.info(
    "Loading era data pulls many terms from Oyez — expect 20–60 seconds per era. "
    "Results are cached so subsequent views are instant."
)

if st.button("Load Era Data", type="primary"):
    era_frames: dict[str, pd.DataFrame] = {}
    for era in selected_eras:
        start, end, _ = ERAS[era]
        with st.spinner(f"Loading {era}..."):
            era_frames[era] = load_era_data(start, end)
    st.session_state["era_frames"] = era_frames
    st.session_state["era_selection"] = selected_eras

if "era_frames" in st.session_state and set(st.session_state.get("era_selection", [])) == set(selected_eras):
    era_frames = st.session_state["era_frames"]

    # ── Total case volume ────────────────────────────────────────────────────
    st.subheader("Total Cases Decided")
    vol_data = [{"Era": era, "Cases": len(df)} for era, df in era_frames.items()]
    vol_df = pd.DataFrame(vol_data)
    colors = [ERAS[era][2] for era in vol_df["Era"]]
    fig_vol = go.Figure(go.Bar(
        x=vol_df["Era"], y=vol_df["Cases"],
        marker_color=colors,
        text=vol_df["Cases"], textposition="outside",
    ))
    fig_vol.update_layout(
        height=320, plot_bgcolor="white", paper_bgcolor="white",
        xaxis_title="", yaxis_title="Number of Cases",
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    st.divider()

    # ── Issue area breakdown per era ─────────────────────────────────────────
    st.subheader("Issue Area Focus by Era")

    issue_rows = []
    for era, df in era_frames.items():
        total = len(df)
        for issue, grp in df.groupby("Issue Area"):
            issue_rows.append({
                "Era": era,
                "Issue Area": issue,
                "Count": len(grp),
                "Share (%)": round(len(grp) / total * 100, 1) if total else 0,
            })
    issue_df = pd.DataFrame(issue_rows)

    if not issue_df.empty:
        top_issues = (
            issue_df.groupby("Issue Area")["Count"].sum()
            .sort_values(ascending=False).head(10).index.tolist()
        )
        filtered = issue_df[issue_df["Issue Area"].isin(top_issues)]
        era_colors = {era: ERAS[era][2] for era in ERAS}
        fig_issue = px.bar(
            filtered,
            x="Issue Area", y="Share (%)",
            color="Era",
            barmode="group",
            title="Top 10 Issue Areas — Share of Docket (%)",
            color_discrete_map=era_colors,
        )
        fig_issue.update_layout(
            height=420, plot_bgcolor="white", paper_bgcolor="white",
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig_issue, use_container_width=True)

    st.divider()

    # ── Disposition trends ───────────────────────────────────────────────────
    st.subheader("Decision Outcome Distribution")
    disp_rows = []
    for era, df in era_frames.items():
        total = len(df)
        for disp, grp in df.groupby("Disposition"):
            disp_rows.append({
                "Era": era,
                "Disposition": disp,
                "Share (%)": round(len(grp) / total * 100, 1) if total else 0,
            })
    disp_df = pd.DataFrame(disp_rows)

    if not disp_df.empty:
        top_disps = (
            disp_df.groupby("Disposition")["Share (%)"].mean()
            .sort_values(ascending=False).head(6).index.tolist()
        )
        disp_filtered = disp_df[disp_df["Disposition"].isin(top_disps)]
        fig_disp = px.bar(
            disp_filtered,
            x="Disposition", y="Share (%)",
            color="Era",
            barmode="group",
            title="Top Dispositions — Share of Docket (%)",
            color_discrete_map=era_colors,
        )
        fig_disp.update_layout(
            height=380, plot_bgcolor="white", paper_bgcolor="white",
            xaxis_tickangle=-20,
        )
        st.plotly_chart(fig_disp, use_container_width=True)

    st.divider()

    # ── Cases per year trend across all eras ─────────────────────────────────
    st.subheader("Case Volume Over Time")
    all_rows = []
    for era, df in era_frames.items():
        for term, grp in df.groupby("Term"):
            all_rows.append({"Term": term, "Cases": len(grp), "Era": era})
    all_df = pd.DataFrame(all_rows).sort_values("Term")

    if not all_df.empty:
        fig_time = px.line(
            all_df, x="Term", y="Cases", color="Era",
            title="Cases Decided per Term",
            markers=True,
            color_discrete_map=era_colors,
        )
        fig_time.update_layout(height=350, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_time, use_container_width=True)

    # ── Raw data ─────────────────────────────────────────────────────────────
    with st.expander("Browse raw case data by era"):
        era_tab_names = list(era_frames.keys())
        tabs = st.tabs(era_tab_names)
        for tab, era in zip(tabs, era_tab_names):
            with tab:
                st.dataframe(
                    era_frames[era][["Term", "Case", "Issue Area", "Disposition"]]
                    .sort_values("Term", ascending=False),
                    use_container_width=True, height=350,
                )
