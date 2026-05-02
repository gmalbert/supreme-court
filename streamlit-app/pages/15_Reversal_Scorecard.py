import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import time

st.set_page_config(page_title="Reversal Rate Scorecard", page_icon="📊", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

CIRCUITS = {
    "1st Circuit":   "First Circuit",
    "2nd Circuit":   "Second Circuit",
    "3rd Circuit":   "Third Circuit",
    "4th Circuit":   "Fourth Circuit",
    "5th Circuit":   "Fifth Circuit",
    "6th Circuit":   "Sixth Circuit",
    "7th Circuit":   "Seventh Circuit",
    "8th Circuit":   "Eighth Circuit",
    "9th Circuit":   "Ninth Circuit",
    "10th Circuit":  "Tenth Circuit",
    "11th Circuit":  "Eleventh Circuit",
    "D.C. Circuit":  "District of Columbia Circuit",
    "Federal Circuit":"Federal Circuit",
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
def fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def classify_disposition(label: str) -> str:
    label_l = label.lower()
    if any(w in label_l for w in ["affirm", "uphold"]):
        return "Affirmed"
    if any(w in label_l for w in ["revers", "vacate"]):
        return "Reversed/Vacated"
    if "remand" in label_l:
        return "Remanded"
    return "Other"

@st.cache_data(show_spinner=False, ttl=3600)
def load_all_circuits(terms: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for term in terms:
        cases = fetch_cases_for_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            detail = fetch_detail(href)
            if not detail:
                continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name", "") if isinstance(lower, dict) else str(lower)
            if not lc_name:
                continue
            disposition = detail.get("disposition") or {}
            disp_label = disposition.get("label", "") if isinstance(disposition, dict) else str(disposition)
            outcome = classify_disposition(disp_label)

            matched_circuit = None
            for label, keyword in CIRCUITS.items():
                if keyword.lower() in lc_name.lower():
                    matched_circuit = label
                    break

            if matched_circuit:
                rows.append({
                    "Term": term,
                    "Circuit": matched_circuit,
                    "Case": detail.get("name", ""),
                    "Lower Court": lc_name,
                    "Disposition": disp_label,
                    "Outcome": outcome,
                    "Issue Area": (
                        detail.get("issue_area", {}).get("label", "Unknown")
                        if isinstance(detail.get("issue_area"), dict)
                        else str(detail.get("issue_area", "Unknown"))
                    ),
                })
        time.sleep(0.03)
    return pd.DataFrame(rows)

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📊 SCOTUS Reversal Rate Scorecard")
st.markdown(
    "Which federal circuit courts does SCOTUS reverse most often? "
    "Load historical data across multiple terms to build the full scorecard."
)

available_terms = list(range(2023, 2004, -1))
selected_terms = st.multiselect(
    "Terms to include",
    options=available_terms,
    default=available_terms[:8],
    max_selections=15,
)

if not selected_terms:
    st.warning("Select at least one term.")
    st.stop()

st.info(
    f"Loading {len(selected_terms)} term(s) — this may take a minute. Results are cached for fast subsequent views."
)

if st.button("Build Scorecard", type="primary"):
    with st.spinner("Fetching case data from Oyez..."):
        df = load_all_circuits(tuple(sorted(selected_terms, reverse=True)))
    st.session_state["scorecard_df"] = df
    st.session_state["scorecard_terms"] = selected_terms

if "scorecard_df" not in st.session_state:
    st.stop()

df: pd.DataFrame = st.session_state["scorecard_df"]
terms_loaded = st.session_state.get("scorecard_terms", [])

if df.empty:
    st.warning("No circuit court data found in the selected terms.")
    st.stop()

st.success(f"Loaded **{len(df)}** cases across **{df['Circuit'].nunique()}** circuits from {min(terms_loaded)}–{max(terms_loaded)}.")

# ── Summary table ─────────────────────────────────────────────────────────────
st.subheader("Reversal Rate by Circuit")

summary = []
for circuit, grp in df.groupby("Circuit"):
    total = len(grp)
    reversed_ = len(grp[grp["Outcome"] == "Reversed/Vacated"])
    affirmed = len(grp[grp["Outcome"] == "Affirmed"])
    summary.append({
        "Circuit": circuit,
        "Cases Reviewed": total,
        "Reversed / Vacated": reversed_,
        "Affirmed": affirmed,
        "Other": total - reversed_ - affirmed,
        "Reversal Rate": round(reversed_ / total * 100, 1) if total else 0.0,
        "Affirmance Rate": round(affirmed / total * 100, 1) if total else 0.0,
    })

summary_df = pd.DataFrame(summary).sort_values("Reversal Rate", ascending=False)

# Color-coded bar chart
fig_main = go.Figure()
fig_main.add_trace(go.Bar(
    name="Reversed / Vacated",
    x=summary_df["Circuit"],
    y=summary_df["Reversal Rate"],
    marker_color="#E74C3C",
    text=summary_df["Reversal Rate"].apply(lambda x: f"{x:.0f}%"),
    textposition="outside",
))
fig_main.add_trace(go.Bar(
    name="Affirmed",
    x=summary_df["Circuit"],
    y=summary_df["Affirmance Rate"],
    marker_color="#27AE60",
    text=summary_df["Affirmance Rate"].apply(lambda x: f"{x:.0f}%"),
    textposition="outside",
))
fig_main.update_layout(
    barmode="group",
    title="Reversal vs. Affirmance Rate by Circuit (%)",
    xaxis_title="",
    yaxis_title="Rate (%)",
    height=420,
    plot_bgcolor="white",
    paper_bgcolor="white",
    xaxis_tickangle=-30,
    legend=dict(x=1.01, y=1),
)
st.plotly_chart(fig_main, use_container_width=True)

# Summary table with color-coded reversal rate
st.dataframe(
    summary_df.style.background_gradient(subset=["Reversal Rate"], cmap="RdYlGn_r"),
    use_container_width=True,
    height=380,
)

st.divider()

# ── Trend over time for a selected circuit ────────────────────────────────────
st.subheader("Reversal Rate Trend — Single Circuit")

all_circuits = sorted(df["Circuit"].unique())
selected_circuit = st.selectbox("Select Circuit", all_circuits, index=min(8, len(all_circuits)-1))
circ_df = df[df["Circuit"] == selected_circuit]

trend_rows = []
for term, grp in circ_df.groupby("Term"):
    total = len(grp)
    rev = len(grp[grp["Outcome"] == "Reversed/Vacated"])
    trend_rows.append({"Term": term, "Reversal Rate (%)": round(rev/total*100, 1) if total else 0, "Cases": total})

if trend_rows:
    trend_df = pd.DataFrame(trend_rows).sort_values("Term")
    fig_trend = px.bar(
        trend_df, x="Term", y="Reversal Rate (%)",
        title=f"{selected_circuit} — Reversal Rate by Term",
        text="Cases",
        color="Reversal Rate (%)",
        color_continuous_scale="RdYlGn_r",
    )
    fig_trend.update_layout(
        height=320, coloraxis_showscale=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── Issue area breakdown for the selected circuit ────────────────────────────
st.subheader(f"Issue Areas — {selected_circuit}")
issue_counts = circ_df["Issue Area"].value_counts().reset_index()
issue_counts.columns = ["Issue Area", "Count"]
fig_issues = px.bar(
    issue_counts.head(10),
    x="Count", y="Issue Area",
    orientation="h",
    title=f"Top Issue Areas sent to SCOTUS from {selected_circuit}",
    color="Count",
    color_continuous_scale="Blues",
)
fig_issues.update_layout(
    height=340, coloraxis_showscale=False,
    plot_bgcolor="white", paper_bgcolor="white",
)
st.plotly_chart(fig_issues, use_container_width=True)

st.divider()

# ── Full case list ────────────────────────────────────────────────────────────
with st.expander(f"All cases from {selected_circuit}"):
    show_df = circ_df[["Term", "Case", "Outcome", "Issue Area"]].sort_values("Term", ascending=False)
    st.dataframe(show_df, use_container_width=True, height=350)
