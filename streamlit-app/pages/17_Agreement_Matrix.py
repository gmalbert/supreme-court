import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
import datetime
from collections import defaultdict

st.set_page_config(page_title="Justice Agreement Matrix", page_icon="🤝", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

KNOWN_JUSTICES = [
    "John G. Roberts", "Clarence Thomas", "Samuel Alito",
    "Sonia Sotomayor", "Elena Kagan", "Neil Gorsuch",
    "Brett Kavanaugh", "Amy Coney Barrett", "Ketanji Brown Jackson",
    # Recently retired
    "Stephen Breyer", "Ruth Bader Ginsburg", "Anthony Kennedy",
    "David Souter", "John Paul Stevens", "Sandra Day O'Connor",
    "Antonin Scalia",
]

JUSTICE_SHORT = {
    "John G. Roberts":        "Roberts",
    "Clarence Thomas":        "Thomas",
    "Samuel Alito":           "Alito",
    "Sonia Sotomayor":        "Sotomayor",
    "Elena Kagan":            "Kagan",
    "Neil Gorsuch":           "Gorsuch",
    "Brett Kavanaugh":        "Kavanaugh",
    "Amy Coney Barrett":      "Barrett",
    "Ketanji Brown Jackson":  "Jackson",
    "Stephen Breyer":         "Breyer",
    "Ruth Bader Ginsburg":    "Ginsburg",
    "Anthony Kennedy":        "Kennedy",
    "David Souter":           "Souter",
    "John Paul Stevens":      "Stevens",
    "Sandra Day O'Connor":    "O'Connor",
    "Antonin Scalia":         "Scalia",
}

# Lean classification for coloring name labels
JUSTICE_LEAN = {
    "Roberts": "Conservative", "Thomas": "Conservative", "Alito": "Conservative",
    "Gorsuch": "Conservative", "Kavanaugh": "Conservative", "Barrett": "Conservative",
    "Scalia": "Conservative", "Kennedy": "Moderate", "O'Connor": "Moderate",
    "Sotomayor": "Liberal", "Kagan": "Liberal", "Jackson": "Liberal",
    "Breyer": "Liberal", "Ginsburg": "Liberal", "Stevens": "Liberal",
    "Souter": "Liberal",
}

LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#27AE60", "Liberal": "#3498DB"}


@st.cache_data(show_spinner=False, ttl=3600)
def load_votes_for_terms(terms: tuple[int, ...]) -> list[dict]:
    """Return a list of {case, justice, vote} rows."""
    rows = []
    for term in terms:
        try:
            r = requests.get(
                f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                headers=HEADERS, timeout=10,
            )
            r.raise_for_status()
            cases = r.json()
        except Exception:
            continue
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            try:
                dr = requests.get(href, headers=HEADERS, timeout=8)
                dr.raise_for_status()
                detail = dr.json()
            except Exception:
                continue
            case_name = detail.get("name", "")
            decisions = detail.get("decisions") or []
            for decision in decisions:
                for vote in (decision.get("votes") or []):
                    member = vote.get("member") or {}
                    justice = member.get("name", "") if isinstance(member, dict) else str(member)
                    v = (vote.get("vote") or "").lower().strip()
                    if justice and v:
                        rows.append({
                            "term": term,
                            "case": case_name,
                            "justice": justice,
                            "vote": v,
                        })
            time.sleep(0.02)
    return rows


def normalize_name(name: str) -> str:
    """Map API names to display names."""
    for full, short in JUSTICE_SHORT.items():
        if full.lower() in name.lower() or name.lower() in full.lower():
            return short
    return name.split()[-1]  # fallback to last name


def build_agreement_matrix(rows: list[dict], min_cases: int = 5) -> pd.DataFrame:
    """Build pairwise agreement percentage matrix."""
    # Pivot: case → justice → vote
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    df["justice_short"] = df["justice"].apply(normalize_name)
    pivot = df.pivot_table(
        index="case", columns="justice_short", values="vote", aggfunc="first"
    )

    justices = list(pivot.columns)
    agree: dict[tuple, int] = defaultdict(int)
    total: dict[tuple, int] = defaultdict(int)

    for j1 in justices:
        for j2 in justices:
            if j1 >= j2:
                continue
            both = pivot[[j1, j2]].dropna()
            n = len(both)
            if n < min_cases:
                continue
            matched = (both[j1] == both[j2]).sum()
            agree[(j1, j2)] = int(matched)
            total[(j1, j2)] = n

    # Build symmetric matrix
    all_j = sorted(set(
        j for pair in total for j in pair
    ))
    mat = pd.DataFrame(index=all_j, columns=all_j, dtype=float)
    for j1 in all_j:
        for j2 in all_j:
            if j1 == j2:
                mat.at[j1, j2] = 100.0
            else:
                key = (min(j1, j2), max(j1, j2))
                if key in total and total[key] > 0:
                    mat.at[j1, j2] = round(agree[key] / total[key] * 100, 1)
    return mat


def make_heatmap(mat: pd.DataFrame) -> go.Figure:
    labels = list(mat.index)
    values = mat.values.tolist()

    # Color labels by lean
    label_colors = [
        LEAN_COLORS.get(JUSTICE_LEAN.get(j, "Moderate"), "#7F8C8D")
        for j in labels
    ]

    text_vals = [
        [f"{v:.0f}%" if v == v else "" for v in row]   # nan check
        for row in values
    ]

    fig = go.Figure(go.Heatmap(
        z=values,
        x=labels,
        y=labels,
        text=text_vals,
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#2C3E50"],
            [0.5, "#F39C12"],
            [0.7, "#27AE60"],
            [1.0, "#1ABC9C"],
        ],
        zmin=40,
        zmax=100,
        colorbar=dict(title="Agreement %", ticksuffix="%"),
        hovertemplate="<b>%{y}</b> ↔ <b>%{x}</b><br>Agreement: %{z:.1f}%<extra></extra>",
    ))

    # Color-coded axis tick labels
    fig.update_xaxes(tickfont=dict(size=11), tickangle=-45)
    fig.update_yaxes(tickfont=dict(size=11))

    fig.update_layout(
        height=600,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=100, r=60, t=30, b=100),
        xaxis=dict(side="bottom"),
    )
    return fig


def find_blocs(mat: pd.DataFrame, threshold: float = 72.0) -> list[set]:
    """Simple greedy bloc detection: justices that agree with each other above threshold."""
    justices = list(mat.index)
    blocs: list[set] = []
    assigned: set[str] = set()

    for j1 in justices:
        if j1 in assigned:
            continue
        bloc = {j1}
        for j2 in justices:
            if j2 == j1 or j2 in assigned:
                continue
            v = mat.at[j1, j2]
            if v == v and v >= threshold:   # nan check
                bloc.add(j2)
        if len(bloc) > 1:
            blocs.append(bloc)
            assigned.update(bloc)

    return blocs


# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🤝 Justice Agreement Matrix")
st.markdown(
    "How often do pairs of justices vote the same way? "
    "This heatmap is computed from actual case vote data fetched live from Oyez."
)

available_terms = list(range(CURRENT_YEAR, CURRENT_YEAR - 25, -1))

with st.form("matrix_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_terms = st.multiselect(
            "Terms to include",
            options=available_terms,
            default=available_terms[:6],
            max_selections=12,
        )
    with col2:
        min_cases = st.slider("Min shared cases per pair", 2, 20, 5,
                              help="Pairs with fewer shared cases are hidden (shown as blank)")
    submitted = st.form_submit_button("Build Matrix", type="primary")

if submitted and selected_terms:
    with st.spinner(f"Loading vote data for {len(selected_terms)} term(s) from Oyez… (cached after first run)"):
        rows = load_votes_for_terms(tuple(sorted(selected_terms, reverse=True)))
    st.session_state["agreement_rows"] = rows
    st.session_state["agreement_terms"] = selected_terms
    st.session_state["agreement_min_cases"] = min_cases

if "agreement_rows" not in st.session_state:
    st.info("Select terms above and click **Build Matrix** to load the data.")
    st.stop()

rows = st.session_state["agreement_rows"]
terms_loaded = st.session_state.get("agreement_terms", [])
min_cases_val = st.session_state.get("agreement_min_cases", 5)

if not rows:
    st.warning("No vote data found.")
    st.stop()

df_all = pd.DataFrame(rows)
n_cases = df_all["case"].nunique()
n_terms = df_all["term"].nunique()
st.success(
    f"Loaded **{len(rows):,}** votes across **{n_cases}** cases "
    f"from **{n_terms}** term(s) ({min(terms_loaded)}–{max(terms_loaded)})."
)

mat = build_agreement_matrix(rows, min_cases=min_cases_val)

if mat.empty:
    st.warning("Not enough shared cases between justices to build a matrix.")
    st.stop()

# ── Heatmap ───────────────────────────────────────────────────────────────────
st.subheader("Agreement Heatmap")
st.caption(
    "Color scale: dark = lower agreement, teal = high agreement. "
    "Diagonal is always 100%. "
    "Blank cells = fewer shared cases than the minimum threshold."
)

lean_legend_cols = st.columns(3)
for i, (lean, color) in enumerate(LEAN_COLORS.items()):
    lean_legend_cols[i].markdown(
        f'<span style="color:{color};font-weight:bold;">■</span> {lean} justices',
        unsafe_allow_html=True,
    )

fig = make_heatmap(mat)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Top pairs ─────────────────────────────────────────────────────────────────
st.subheader("Most & Least Aligned Pairs")
pair_rows = []
justices_in_mat = list(mat.index)
for i, j1 in enumerate(justices_in_mat):
    for j2 in justices_in_mat[i+1:]:
        v = mat.at[j1, j2]
        if v == v:   # not nan
            pair_rows.append({"Justice A": j1, "Justice B": j2, "Agreement %": v})

if pair_rows:
    pair_df = pd.DataFrame(pair_rows).sort_values("Agreement %", ascending=False)
    col_top, col_bot = st.columns(2)
    with col_top:
        st.markdown("**Highest Agreement**")
        st.dataframe(
            pair_df.head(10).reset_index(drop=True)
            .style.background_gradient(subset=["Agreement %"], cmap="Greens"),
            use_container_width=True, height=320,
        )
    with col_bot:
        st.markdown("**Lowest Agreement**")
        st.dataframe(
            pair_df.tail(10).sort_values("Agreement %").reset_index(drop=True)
            .style.background_gradient(subset=["Agreement %"], cmap="Reds_r"),
            use_container_width=True, height=320,
        )

st.divider()

# ── Voting blocs ──────────────────────────────────────────────────────────────
st.subheader("Detected Voting Blocs")
threshold = st.slider("Agreement threshold for bloc membership", 55, 90, 72, step=1,
                      format="%d%%")
blocs = find_blocs(mat, threshold=float(threshold))

if blocs:
    for i, bloc in enumerate(blocs, 1):
        members = sorted(bloc)
        leans = [JUSTICE_LEAN.get(j, "Moderate") for j in members]
        dominant_lean = max(set(leans), key=leans.count)
        color = LEAN_COLORS.get(dominant_lean, "#7F8C8D")
        st.markdown(
            f'<div style="border-left:4px solid {color}; padding-left:10px; margin-bottom:8px;">'
            f'<strong>Bloc {i}:</strong> {" · ".join(members)}'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.info("No blocs found at this threshold. Try lowering the agreement %.")

st.divider()

# ── Per-justice average agreement ─────────────────────────────────────────────
st.subheader("Average Agreement by Justice")
avg_rows = []
for j in mat.index:
    others = [mat.at[j, j2] for j2 in mat.columns if j2 != j]
    valid = [v for v in others if v == v]
    if valid:
        avg_rows.append({"Justice": j, "Avg Agreement %": round(sum(valid) / len(valid), 1)})

if avg_rows:
    avg_df = pd.DataFrame(avg_rows).sort_values("Avg Agreement %", ascending=False)
    avg_df["Lean"] = avg_df["Justice"].map(lambda j: JUSTICE_LEAN.get(j, "Moderate"))
    avg_df["Color"] = avg_df["Lean"].map(LEAN_COLORS)

    fig_avg = go.Figure(go.Bar(
        x=avg_df["Justice"],
        y=avg_df["Avg Agreement %"],
        marker_color=avg_df["Color"].tolist(),
        text=avg_df["Avg Agreement %"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Avg Agreement: %{y:.1f}%<extra></extra>",
    ))
    fig_avg.update_layout(
        height=340,
        yaxis=dict(title="Avg Agreement %", range=[40, 100]),
        xaxis_tickangle=-30,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=80),
    )
    st.plotly_chart(fig_avg, use_container_width=True)
    st.caption(
        "A higher average means this justice voted with all colleagues more often overall — "
        "not necessarily that they are moderate, but that their views frequently overlapped with majorities."
    )
