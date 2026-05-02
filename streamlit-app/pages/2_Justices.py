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
from utils.oyez_api import get_cases_by_term, get_case_detail, get_recent_terms
from utils.charts import build_voting_chart

st.set_page_config(page_title="Justices Hub", page_icon="👨‍⚖️", layout="wide")

HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Shared fetch helpers ──────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _jh_fetch_justices() -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/justices", headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _jh_fetch_justice_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

@st.cache_data(show_spinner=False)
def _jh_fetch_cases_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _jh_fetch_case_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

@st.cache_data(show_spinner=False, ttl=3600)
def _jh_load_votes_for_terms(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        try:
            r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                             headers=HEADERS, timeout=10)
            r.raise_for_status(); cases = r.json()
        except Exception: continue
        for c in cases:
            href = c.get("href",""); 
            if not href: continue
            try:
                dr = requests.get(href, headers=HEADERS, timeout=8)
                dr.raise_for_status(); detail = dr.json()
            except Exception: continue
            case_name = detail.get("name","")
            for decision in (detail.get("decisions") or []):
                for vote in (decision.get("votes") or []):
                    member = vote.get("member") or {}
                    justice = member.get("name","") if isinstance(member,dict) else str(member)
                    v = (vote.get("vote") or "").lower().strip()
                    if justice and v:
                        rows.append({"term":term,"case":case_name,"justice":justice,"vote":v})
            time.sleep(0.02)
    return rows

# ── Justice career helpers ─────────────────────────────────────────────────────
def _get_justice_votes(justice_name: str, terms: list[int]) -> pd.DataFrame:
    rows = []
    progress = st.progress(0)
    for idx, term in enumerate(terms):
        cases = _jh_fetch_cases_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = _jh_fetch_case_detail(href)
            if not detail: continue
            for dec in (detail.get("decisions") or []):
                for vote in (dec.get("votes") or []):
                    member = vote.get("member",{}) or {}
                    name = member.get("name","")
                    if justice_name.lower() in name.lower():
                        ia = detail.get("issue_area",{})
                        rows.append({
                            "Term": term, "Case": detail.get("name",""),
                            "Vote": vote.get("vote",""),
                            "Issue Area": ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown"),
                        })
            time.sleep(0.02)
        progress.progress((idx+1)/len(terms))
    progress.empty()
    return pd.DataFrame(rows)

# ── Agreement matrix helpers ───────────────────────────────────────────────────
KNOWN_JUSTICES = [
    "John G. Roberts","Clarence Thomas","Samuel Alito","Sonia Sotomayor","Elena Kagan",
    "Neil Gorsuch","Brett Kavanaugh","Amy Coney Barrett","Ketanji Brown Jackson",
    "Stephen Breyer","Ruth Bader Ginsburg","Anthony Kennedy","David Souter",
    "John Paul Stevens","Sandra Day O'Connor","Antonin Scalia",
]
JUSTICE_SHORT = {
    "John G. Roberts":"Roberts","Clarence Thomas":"Thomas","Samuel Alito":"Alito",
    "Sonia Sotomayor":"Sotomayor","Elena Kagan":"Kagan","Neil Gorsuch":"Gorsuch",
    "Brett Kavanaugh":"Kavanaugh","Amy Coney Barrett":"Barrett","Ketanji Brown Jackson":"Jackson",
    "Stephen Breyer":"Breyer","Ruth Bader Ginsburg":"Ginsburg","Anthony Kennedy":"Kennedy",
    "David Souter":"Souter","John Paul Stevens":"Stevens","Sandra Day O'Connor":"O'Connor",
    "Antonin Scalia":"Scalia",
}
JUSTICE_LEAN = {
    "Roberts":"Conservative","Thomas":"Conservative","Alito":"Conservative",
    "Gorsuch":"Conservative","Kavanaugh":"Conservative","Barrett":"Conservative",
    "Scalia":"Conservative","Kennedy":"Moderate","O'Connor":"Moderate",
    "Sotomayor":"Liberal","Kagan":"Liberal","Jackson":"Liberal",
    "Breyer":"Liberal","Ginsburg":"Liberal","Stevens":"Liberal","Souter":"Liberal",
}
LEAN_COLORS = {"Conservative":"#E74C3C","Moderate":"#27AE60","Liberal":"#3498DB"}

def _normalize_name(name: str) -> str:
    for full, short in JUSTICE_SHORT.items():
        if full.lower() in name.lower() or name.lower() in full.lower():
            return short
    return name.split()[-1]

def _build_agreement_matrix(rows: list[dict], min_cases: int = 5) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty: return pd.DataFrame()
    df["justice_short"] = df["justice"].apply(_normalize_name)
    pivot = df.pivot_table(index="case", columns="justice_short", values="vote", aggfunc="first")
    justices = list(pivot.columns)
    agree: dict[tuple,int] = defaultdict(int); total: dict[tuple,int] = defaultdict(int)
    for j1 in justices:
        for j2 in justices:
            if j1 >= j2: continue
            both = pivot[[j1,j2]].dropna(); n = len(both)
            if n < min_cases: continue
            agree[(j1,j2)] = int((both[j1]==both[j2]).sum()); total[(j1,j2)] = n
    all_j = sorted(set(j for pair in total for j in pair))
    mat = pd.DataFrame(index=all_j, columns=all_j, dtype=float)
    for j1 in all_j:
        for j2 in all_j:
            if j1 == j2: mat.at[j1,j2] = 100.0
            else:
                key = (min(j1,j2),max(j1,j2))
                if key in total and total[key]>0:
                    mat.at[j1,j2] = round(agree[key]/total[key]*100,1)
    return mat

def _make_heatmap(mat: pd.DataFrame) -> go.Figure:
    labels = list(mat.index); values = mat.values.tolist()
    text_vals = [[f"{v:.0f}%" if v==v else "" for v in row] for row in values]
    fig = go.Figure(go.Heatmap(
        z=values, x=labels, y=labels, text=text_vals, texttemplate="%{text}",
        colorscale=[[0.0,"#2C3E50"],[0.5,"#F39C12"],[0.7,"#27AE60"],[1.0,"#1ABC9C"]],
        zmin=40, zmax=100, colorbar=dict(title="Agreement %",ticksuffix="%"),
        hovertemplate="<b>%{y}</b> ↔ <b>%{x}</b><br>Agreement: %{z:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(tickfont=dict(size=11), tickangle=-45)
    fig.update_yaxes(tickfont=dict(size=11))
    fig.update_layout(height=600, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=100,r=60,t=30,b=100))
    return fig

def _find_blocs(mat: pd.DataFrame, threshold: float = 72.0) -> list[set]:
    justices = list(mat.index); blocs: list[set] = []; assigned: set[str] = set()
    for j1 in justices:
        if j1 in assigned: continue
        bloc = {j1}
        for j2 in justices:
            if j2 == j1 or j2 in assigned: continue
            v = mat.at[j1,j2]
            if v == v and v >= threshold: bloc.add(j2)
        if len(bloc) > 1: blocs.append(bloc); assigned.update(bloc)
    return blocs

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("👨‍⚖️ Justices")
tab_voting, tab_career, tab_matrix = st.tabs([
    "⚖️ Voting Patterns", "📊 Justice Career", "🤝 Agreement Matrix"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: JUSTICE VOTING PATTERNS
# ──────────────────────────────────────────────────────────────────────────────
with tab_voting:
    st.markdown("Explore how individual justices voted on Supreme Court cases.")
    jv_term = st.selectbox("Select Term", get_recent_terms(15), key="jv_term")
    with st.spinner("Loading cases..."):
        jv_cases = get_cases_by_term(jv_term)
    if not jv_cases:
        st.warning("No cases found for the selected term.")
    else:
        jv_case_names = [c.get("name","Unknown") for c in jv_cases]
        jv_selected_name = st.selectbox("Select a Case", jv_case_names, key="jv_case")
        jv_selected = next((c for c in jv_cases if c.get("name")==jv_selected_name), None)
        if jv_selected:
            jv_href = jv_selected.get("href","")
            if jv_href:
                with st.spinner("Loading case details..."):
                    jv_detail = get_case_detail(jv_href)
                if not jv_detail:
                    st.warning("Could not load case details.")
                else:
                    decisions = jv_detail.get("decisions") or []
                    if not decisions:
                        st.info("No voting data available for this case.")
                    else:
                        for decision in decisions:
                            winning_party = decision.get("winning_party","Unknown")
                            votes = decision.get("votes",[])
                            st.subheader(f"Winning Party: {winning_party}")
                            if votes:
                                fig = build_voting_chart(votes)
                                if fig: st.plotly_chart(fig, use_container_width=True)
                                rows = []
                                for v in votes:
                                    member = v.get("member",{}) or {}
                                    rows.append({"Justice":member.get("name","Unknown"),"Vote":v.get("vote","")})
                                if rows:
                                    df = pd.DataFrame(rows)
                                    majority = df[df["Vote"].str.lower().isin(["majority","concurrence"])]
                                    dissent  = df[df["Vote"].str.lower()=="dissent"]
                                    c1, c2 = st.columns(2)
                                    with c1:
                                        st.markdown("**Majority/Concurrence**")
                                        for _, row in majority.iterrows():
                                            st.markdown(f"- {row['Justice']} ({row['Vote']})")
                                    with c2:
                                        st.markdown("**Dissent**")
                                        if dissent.empty: st.markdown("_No dissents_")
                                        else:
                                            for _, row in dissent.iterrows():
                                                st.markdown(f"- {row['Justice']}")
                            st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: JUSTICE CAREER OVERVIEW
# ──────────────────────────────────────────────────────────────────────────────
with tab_career:
    st.markdown("Explore a justice's voting history, issue area tendencies, and notable cases.")
    with st.spinner("Loading justices..."):
        justices_list = _jh_fetch_justices()
    if not justices_list:
        st.error("Could not load justices from Oyez.")
    else:
        justices_sorted = sorted(justices_list, key=lambda j: j.get("name","").split()[-1])
        justice_names = [j.get("name","Unknown") for j in justices_sorted]
        jc_selected_name = st.selectbox("Select a Justice", justice_names, key="jc_sel")
        jc_selected = next((j for j in justices_sorted if j.get("name")==jc_selected_name), None)

        if jc_selected:
            jc_href = jc_selected.get("href","")
            with st.spinner("Loading justice profile..."):
                jc_detail = _jh_fetch_justice_detail(jc_href) if jc_href else None

            col_bio, col_stats = st.columns([2,1])
            with col_bio:
                st.subheader(jc_selected_name)
                if jc_detail:
                    for role in (jc_detail.get("roles") or []):
                        court = role.get("institution_name","")
                        date_start = role.get("date_start",0); date_end = role.get("date_end",0)
                        title = role.get("role_title","Justice")
                        def _ts_to_year(ts):
                            if ts:
                                try: return datetime.datetime.utcfromtimestamp(ts).year
                                except Exception: return "?"
                            return "present"
                        start_yr = _ts_to_year(date_start)
                        end_yr   = _ts_to_year(date_end) if date_end else "present"
                        st.markdown(f"- **{title}**, {court} ({start_yr} – {end_yr})")
                    desc = jc_detail.get("description","")
                    if desc:
                        with st.expander("Biography"): st.write(desc)
            with col_stats:
                st.markdown("**Quick Info**")
                if jc_detail:
                    roles = jc_detail.get("roles",[])
                    if roles:
                        latest = roles[-1]
                        appointer = latest.get("appointing_president","")
                        if appointer: st.markdown(f"- **Appointed by:** {appointer}")
                        party = latest.get("party_affiliation",{})
                        if isinstance(party,dict) and party.get("label"):
                            st.markdown(f"- **Party:** {party['label']}")

            st.divider()
            st.subheader("Voting History Analysis")
            st.info("Fetches live case data. Selecting many terms will take longer to load.")
            available_terms = list(range(CURRENT_YEAR, CURRENT_YEAR-27,-1))
            jc_sel_terms = st.multiselect("Select Terms to Analyze", available_terms,
                                           default=available_terms[:5], max_selections=10, key="jc_terms")
            if not jc_sel_terms:
                st.warning("Please select at least one term.")
            elif st.button("Load Voting History", type="primary", key="jc_load"):
                with st.spinner(f"Fetching voting records for {jc_selected_name}…"):
                    jc_df = _get_justice_votes(jc_selected_name, sorted(jc_sel_terms, reverse=True))
                st.session_state["jc_df"] = jc_df
                st.session_state["jc_name"] = jc_selected_name

            if "jc_df" in st.session_state and st.session_state.get("jc_name")==jc_selected_name:
                jc_df = st.session_state["jc_df"]
                if jc_df.empty:
                    st.warning("No voting data found for this justice in the selected terms.")
                else:
                    total = len(jc_df)
                    majority = len(jc_df[jc_df["Vote"].str.lower().isin(["majority","concurrence"])])
                    dissent  = len(jc_df[jc_df["Vote"].str.lower()=="dissent"])
                    st.success(f"Found {total} votes across {jc_df['Term'].nunique()} term(s).")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Votes", total)
                    m2.metric("Majority/Concurrence", majority, f"{majority/total*100:.0f}%")
                    m3.metric("Dissents", dissent, f"{dissent/total*100:.0f}%")

                    col_left, col_right = st.columns(2)
                    with col_left:
                        vote_counts = jc_df["Vote"].value_counts().reset_index()
                        vote_counts.columns = ["Vote Type","Count"]
                        color_map = {"majority":"#27AE60","concurrence":"#2ECC71","dissent":"#E74C3C","recusal":"#95A5A6"}
                        colors = [color_map.get(v.lower(),"#BDC3C7") for v in vote_counts["Vote Type"]]
                        fig_votes = go.Figure(go.Bar(x=vote_counts["Vote Type"],y=vote_counts["Count"],
                                                     marker_color=colors,text=vote_counts["Count"],textposition="outside"))
                        fig_votes.update_layout(title="Vote Type Breakdown",height=320,plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_votes, use_container_width=True)
                    with col_right:
                        issue_counts = jc_df["Issue Area"].value_counts().reset_index()
                        issue_counts.columns = ["Issue Area","Count"]
                        fig_issues = px.pie(issue_counts,names="Issue Area",values="Count",
                                            title="Cases by Issue Area",hole=0.3)
                        fig_issues.update_layout(height=320)
                        st.plotly_chart(fig_issues, use_container_width=True)

                    if jc_df["Term"].nunique() > 1:
                        term_stats = []
                        for term, grp in jc_df.groupby("Term"):
                            total_t = len(grp)
                            dissent_t = len(grp[grp["Vote"].str.lower()=="dissent"])
                            term_stats.append({"Term":term,"Dissent Rate (%)":dissent_t/total_t*100,"Cases":total_t})
                        term_df = pd.DataFrame(term_stats).sort_values("Term")
                        fig_trend = px.bar(term_df,x="Term",y="Dissent Rate (%)",
                                           title=f"{jc_selected_name} — Dissent Rate by Term",
                                           text="Cases",color="Dissent Rate (%)",color_continuous_scale="Reds")
                        fig_trend.update_layout(height=320,coloraxis_showscale=False,plot_bgcolor="white")
                        st.plotly_chart(fig_trend, use_container_width=True)

                    st.subheader("Dissenting Votes")
                    dissents_df = jc_df[jc_df["Vote"].str.lower()=="dissent"][["Term","Case","Issue Area"]].drop_duplicates()
                    if dissents_df.empty: st.info("No dissenting votes found in the selected terms.")
                    else: st.dataframe(dissents_df.sort_values("Term",ascending=False),use_container_width=True,height=300)
                    with st.expander("Full Voting Record"):
                        st.dataframe(jc_df.sort_values(["Term","Case"],ascending=[False,True]),use_container_width=True,height=400)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: JUSTICE AGREEMENT MATRIX
# ──────────────────────────────────────────────────────────────────────────────
with tab_matrix:
    st.markdown("How often do pairs of justices vote the same way? Computed from live Oyez data.")
    available_terms_m = list(range(CURRENT_YEAR, CURRENT_YEAR-25,-1))

    with st.form("matrix_form"):
        col1, col2 = st.columns([2,1])
        with col1:
            sel_terms_m = st.multiselect("Terms to include", available_terms_m,
                                          default=available_terms_m[:6], max_selections=12, key="matrix_terms")
        with col2:
            min_cases_m = st.slider("Min shared cases per pair", 2, 20, 5, key="matrix_min")
        submitted_m = st.form_submit_button("Build Matrix", type="primary")

    if submitted_m and sel_terms_m:
        with st.spinner(f"Loading vote data for {len(sel_terms_m)} term(s)…"):
            matrix_rows = _jh_load_votes_for_terms(tuple(sorted(sel_terms_m, reverse=True)))
        st.session_state["matrix_rows"] = matrix_rows
        st.session_state["matrix_terms_loaded"] = sel_terms_m
        st.session_state["matrix_min_cases"] = min_cases_m

    if "matrix_rows" not in st.session_state:
        st.info("Select terms above and click **Build Matrix** to load the data.")
    else:
        matrix_rows = st.session_state["matrix_rows"]
        terms_loaded = st.session_state.get("matrix_terms_loaded",[])
        min_cases_val = st.session_state.get("matrix_min_cases",5)

        if not matrix_rows:
            st.warning("No vote data found.")
        else:
            df_all = pd.DataFrame(matrix_rows)
            n_cases = df_all["case"].nunique(); n_terms_loaded = df_all["term"].nunique()
            st.success(f"Loaded **{len(matrix_rows):,}** votes across **{n_cases}** cases from **{n_terms_loaded}** term(s).")

            mat = _build_agreement_matrix(matrix_rows, min_cases=min_cases_val)
            if mat.empty:
                st.warning("Not enough shared cases to build a matrix.")
            else:
                st.subheader("Agreement Heatmap")
                st.caption("Dark = lower agreement, teal = high agreement. Diagonal = 100%.")
                lean_cols = st.columns(3)
                for i, (lean, color) in enumerate(LEAN_COLORS.items()):
                    lean_cols[i].markdown(f'<span style="color:{color};font-weight:bold;">■</span> {lean}', unsafe_allow_html=True)
                st.plotly_chart(_make_heatmap(mat), use_container_width=True)

                st.divider()
                st.subheader("Most & Least Aligned Pairs")
                pair_rows = []
                jj = list(mat.index)
                for i, j1 in enumerate(jj):
                    for j2 in jj[i+1:]:
                        v = mat.at[j1,j2]
                        if v == v: pair_rows.append({"Justice A":j1,"Justice B":j2,"Agreement %":v})
                if pair_rows:
                    pair_df = pd.DataFrame(pair_rows).sort_values("Agreement %",ascending=False)
                    col_top, col_bot = st.columns(2)
                    with col_top:
                        st.markdown("**Highest Agreement**")
                        st.dataframe(pair_df.head(10).reset_index(drop=True)
                                     .style.background_gradient(subset=["Agreement %"],cmap="Greens"),
                                     use_container_width=True, height=320)
                    with col_bot:
                        st.markdown("**Lowest Agreement**")
                        st.dataframe(pair_df.tail(10).sort_values("Agreement %").reset_index(drop=True)
                                     .style.background_gradient(subset=["Agreement %"],cmap="Reds_r"),
                                     use_container_width=True, height=320)

                st.divider()
                st.subheader("Detected Voting Blocs")
                threshold_m = st.slider("Agreement threshold for bloc membership", 55, 90, 72, step=1,
                                        format="%d%%", key="bloc_thresh")
                blocs = _find_blocs(mat, threshold=float(threshold_m))
                if blocs:
                    for i, bloc in enumerate(blocs,1):
                        members = sorted(bloc)
                        leans = [JUSTICE_LEAN.get(j,"Moderate") for j in members]
                        dominant = max(set(leans), key=leans.count)
                        color = LEAN_COLORS.get(dominant,"#7F8C8D")
                        st.markdown(f'<div style="border-left:4px solid {color};padding-left:10px;margin-bottom:8px;">'
                                    f'<strong>Bloc {i}:</strong> {" · ".join(members)}</div>', unsafe_allow_html=True)
                else:
                    st.info("No blocs found at this threshold. Try lowering the agreement %.")

                st.divider()
                st.subheader("Average Agreement by Justice")
                avg_rows = []
                for j in mat.index:
                    valid = [mat.at[j,j2] for j2 in mat.columns if j2!=j and mat.at[j,j2]==mat.at[j,j2]]
                    if valid: avg_rows.append({"Justice":j,"Avg Agreement %":round(sum(valid)/len(valid),1)})
                if avg_rows:
                    avg_df = pd.DataFrame(avg_rows).sort_values("Avg Agreement %",ascending=False)
                    avg_df["Lean"]  = avg_df["Justice"].map(lambda j: JUSTICE_LEAN.get(j,"Moderate"))
                    avg_df["Color"] = avg_df["Lean"].map(LEAN_COLORS)
                    fig_avg = go.Figure(go.Bar(
                        x=avg_df["Justice"], y=avg_df["Avg Agreement %"],
                        marker_color=avg_df["Color"].tolist(),
                        text=avg_df["Avg Agreement %"].apply(lambda v: f"{v:.1f}%"),
                        textposition="outside"))
                    fig_avg.update_layout(height=340, yaxis=dict(title="Avg Agreement %",range=[40,100]),
                                          xaxis_tickangle=-30, plot_bgcolor="white", paper_bgcolor="white")
                    st.plotly_chart(fig_avg, use_container_width=True)
