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

st.set_page_config(page_title="Circuit Courts Hub", page_icon="🏛️", layout="wide")

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

CIRCUITS = {
    "1st Circuit":"First Circuit","2nd Circuit":"Second Circuit","3rd Circuit":"Third Circuit",
    "4th Circuit":"Fourth Circuit","5th Circuit":"Fifth Circuit","6th Circuit":"Sixth Circuit",
    "7th Circuit":"Seventh Circuit","8th Circuit":"Eighth Circuit","9th Circuit":"Ninth Circuit",
    "10th Circuit":"Tenth Circuit","11th Circuit":"Eleventh Circuit",
    "D.C. Circuit":"District of Columbia Circuit","Federal Circuit":"Federal Circuit",
}
CIRCUIT_COURTS = {**CIRCUITS,"State Supreme Courts":"state","District Courts":"district"}
CIRCUIT_KEYWORDS = {**CIRCUITS,"State Courts":"state","District Courts":"district","Any / Unknown":""}

# ── Shared fetch ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cc_fetch_cases_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _cc_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _court_matches(lc_name: str, search_term: str) -> bool:
    if not lc_name or not search_term: return False
    return search_term.lower() in lc_name.lower()

def _classify_disposition(label: str) -> str:
    label_l = label.lower()
    if any(w in label_l for w in ["affirm","uphold"]): return "Affirmed"
    if any(w in label_l for w in ["revers","vacate"]): return "Reversed/Vacated"
    if "remand" in label_l: return "Remanded"
    return "Other"

@st.cache_data(show_spinner=False, ttl=3600)
def _cc_load_all_circuits(terms: tuple) -> pd.DataFrame:
    rows = []
    for term in terms:
        cases = _cc_fetch_cases_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = _cc_fetch_detail(href)
            if not detail: continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name","") if isinstance(lower,dict) else str(lower)
            if not lc_name: continue
            disp = detail.get("disposition") or {}
            disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
            outcome = _classify_disposition(disp_label)
            matched_circuit = None
            for label, keyword in CIRCUITS.items():
                if keyword.lower() in lc_name.lower():
                    matched_circuit = label; break
            if matched_circuit:
                ia = detail.get("issue_area") or {}
                rows.append({"Term":term,"Circuit":matched_circuit,"Case":detail.get("name",""),
                              "Lower Court":lc_name,"Disposition":disp_label,"Outcome":outcome,
                              "Issue Area":ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")})
        time.sleep(0.03)
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False, ttl=3600)
def _cc_load_historical(terms: tuple) -> pd.DataFrame:
    rows = []
    for term in terms:
        try:
            r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                             headers=HEADERS, timeout=10)
            r.raise_for_status(); cases = r.json()
        except Exception: continue
        for c in cases:
            href = c.get("href","")
            if not href: continue
            try:
                dr = requests.get(href, headers=HEADERS, timeout=8)
                dr.raise_for_status(); detail = dr.json()
            except Exception: continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name","") if isinstance(lower,dict) else str(lower)
            disp = detail.get("disposition") or {}
            disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
            ia = detail.get("issue_area") or {}
            issue_label = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia)
            affirmed  = "affirm" in disp_label.lower()
            reversed_ = any(w in disp_label.lower() for w in ["revers","vacate","remand"])
            rows.append({"term":term,"lower_court":lc_name,"issue_area":issue_label,
                          "disposition":disp_label,"affirmed":affirmed,"reversed":reversed_})
            time.sleep(0.02)
    return pd.DataFrame(rows)

def _compute_predictor_stats(df: pd.DataFrame, circuit_kw: str, issue: str) -> dict:
    filtered = df.copy()
    if circuit_kw: filtered = filtered[filtered["lower_court"].str.contains(circuit_kw,case=False,na=False)]
    if issue and issue != "Any": filtered = filtered[filtered["issue_area"].str.contains(issue,case=False,na=False)]
    total = len(filtered)
    if total == 0: return {"total":0,"affirm_pct":None,"reverse_pct":None,"df":filtered}
    affirm_pct  = filtered["affirmed"].sum()/total*100
    reverse_pct = filtered["reversed"].sum()/total*100
    return {"total":total,"affirm_pct":affirm_pct,"reverse_pct":reverse_pct,
            "other_pct":100-affirm_pct-reverse_pct,"df":filtered}

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🏛️ Circuit Courts")
tab_compare, tab_scorecard, tab_predictor = st.tabs([
    "⚖️ Court Comparison", "📊 Reversal Scorecard", "🎯 Outcome Predictor"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: COURT OF APPEALS COMPARISON
# ──────────────────────────────────────────────────────────────────────────────
with tab_compare:
    st.markdown("Compare two federal circuit courts side-by-side: see how often SCOTUS affirmed or reversed their decisions.")
    col1_cmp, col2_cmp = st.columns(2)
    with col1_cmp: court_a_label = st.selectbox("Court A", list(CIRCUIT_COURTS.keys()), index=8, key="cmp_a")
    with col2_cmp: court_b_label = st.selectbox("Court B", list(CIRCUIT_COURTS.keys()), index=4, key="cmp_b")

    available_terms_cmp = list(range(CURRENT_YEAR, CURRENT_YEAR-25,-1))
    sel_terms_cmp = st.multiselect("Terms to analyze",available_terms_cmp,default=available_terms_cmp[:6],max_selections=10,key="cmp_terms")
    if not sel_terms_cmp:
        st.warning("Select at least one term.")
    else:
        court_a_kw = CIRCUIT_COURTS[court_a_label]; court_b_kw = CIRCUIT_COURTS[court_b_label]

        def _analyze_court(kw: str, terms: list[int]) -> list[dict]:
            rows = []
            for term in terms:
                cases = _cc_fetch_cases_term(term)
                for c in cases:
                    href = c.get("href","")
                    if not href: continue
                    detail = _cc_fetch_detail(href)
                    if not detail: continue
                    lower = detail.get("lower_court") or {}
                    lc_name = lower.get("name","") if isinstance(lower,dict) else str(lower)
                    if not _court_matches(lc_name, kw): continue
                    disp = detail.get("disposition") or {}
                    disp_label = disp.get("label","Unknown") if isinstance(disp,dict) else str(disp)
                    affirmed  = any(w in disp_label.lower() for w in ["affirm","uphold"])
                    reversed_ = any(w in disp_label.lower() for w in ["revers","vacate","remand"])
                    ia = detail.get("issue_area") or {}
                    rows.append({"Term":term,"Case":detail.get("name",""),"Lower Court":lc_name,
                                  "Disposition":disp_label,"Affirmed":affirmed,"Reversed":reversed_,
                                  "Issue Area":ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")})
                time.sleep(0.02)
            return rows

        if st.button("Compare Courts", type="primary", key="cmp_btn"):
            with st.spinner(f"Fetching data for {court_a_label}..."):
                rows_a = _analyze_court(court_a_kw, sorted(sel_terms_cmp,reverse=True))
            with st.spinner(f"Fetching data for {court_b_label}..."):
                rows_b = _analyze_court(court_b_kw, sorted(sel_terms_cmp,reverse=True))
            st.session_state["compare_a"] = (court_a_label, pd.DataFrame(rows_a))
            st.session_state["compare_b"] = (court_b_label, pd.DataFrame(rows_b))

        if "compare_a" in st.session_state and "compare_b" in st.session_state:
            label_a, df_a = st.session_state["compare_a"]
            label_b, df_b = st.session_state["compare_b"]

            def _summary_stats(df: pd.DataFrame, label: str) -> dict:
                total = len(df); aff = df["Affirmed"].sum() if total else 0; rev = df["Reversed"].sum() if total else 0
                return {"Court":label,"Cases Reviewed":total,"Affirmed":int(aff),"Reversed / Vacated":int(rev),
                        "Affirm Rate":f"{aff/total*100:.0f}%" if total else "N/A",
                        "Reversal Rate":f"{rev/total*100:.0f}%" if total else "N/A"}

            stats_a = _summary_stats(df_a, label_a); stats_b = _summary_stats(df_b, label_b)
            st.subheader("Summary")
            col_a_res, col_b_res = st.columns(2)
            with col_a_res:
                st.markdown(f"### {label_a}")
                st.metric("Cases Reviewed by SCOTUS",stats_a["Cases Reviewed"])
                st.metric("Affirmed",stats_a["Affirmed"],stats_a["Affirm Rate"])
                st.metric("Reversed / Vacated",stats_a["Reversed / Vacated"],stats_a["Reversal Rate"])
            with col_b_res:
                st.markdown(f"### {label_b}")
                st.metric("Cases Reviewed by SCOTUS",stats_b["Cases Reviewed"])
                st.metric("Affirmed",stats_b["Affirmed"],stats_b["Affirm Rate"])
                st.metric("Reversed / Vacated",stats_b["Reversed / Vacated"],stats_b["Reversal Rate"])
            st.divider()

            categories_cmp = ["Affirmed","Reversed / Vacated","Other"]
            counts_a_cmp = [int(df_a["Affirmed"].sum()),int(df_a["Reversed"].sum()),max(len(df_a)-int(df_a["Affirmed"].sum())-int(df_a["Reversed"].sum()),0)]
            counts_b_cmp = [int(df_b["Affirmed"].sum()),int(df_b["Reversed"].sum()),max(len(df_b)-int(df_b["Affirmed"].sum())-int(df_b["Reversed"].sum()),0)]
            fig_bar_cmp = go.Figure(data=[
                go.Bar(name=label_a,x=categories_cmp,y=counts_a_cmp,marker_color="#4A90D9"),
                go.Bar(name=label_b,x=categories_cmp,y=counts_b_cmp,marker_color="#E67E22")])
            fig_bar_cmp.update_layout(barmode="group",title="Outcome Comparison",height=350,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_bar_cmp, use_container_width=True)

            st.subheader("Issue Areas Sent to SCOTUS")
            col_ia_a, col_ia_b = st.columns(2)

            def _issue_counts_cmp(df):
                vc = df["Issue Area"].value_counts().reset_index()
                vc.columns = ["Issue Area","Count"]; return vc

            with col_ia_a:
                ic_a = _issue_counts_cmp(df_a)
                if not ic_a.empty:
                    fig_ia_a = px.bar(ic_a.head(8),x="Count",y="Issue Area",orientation="h",
                                      title=f"{label_a} — Issue Areas",color_discrete_sequence=["#4A90D9"])
                    fig_ia_a.update_layout(height=320,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_ia_a, use_container_width=True)
            with col_ia_b:
                ic_b = _issue_counts_cmp(df_b)
                if not ic_b.empty:
                    fig_ia_b = px.bar(ic_b.head(8),x="Count",y="Issue Area",orientation="h",
                                      title=f"{label_b} — Issue Areas",color_discrete_sequence=["#E67E22"])
                    fig_ia_b.update_layout(height=320,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_ia_b, use_container_width=True)

            st.divider(); st.subheader("Case Details")
            tab_da, tab_db = st.tabs([label_a, label_b])
            with tab_da:
                st.dataframe(df_a[["Term","Case","Disposition","Issue Area"]].sort_values("Term",ascending=False),
                             use_container_width=True, height=350)
            with tab_db:
                st.dataframe(df_b[["Term","Case","Disposition","Issue Area"]].sort_values("Term",ascending=False),
                             use_container_width=True, height=350)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: REVERSAL RATE SCORECARD
# ──────────────────────────────────────────────────────────────────────────────
with tab_scorecard:
    st.markdown("Which federal circuit courts does SCOTUS reverse most often? Build the full scorecard from historical data.")
    available_terms_sc = list(range(CURRENT_YEAR, CURRENT_YEAR-25,-1))
    sel_terms_sc = st.multiselect("Terms to include",available_terms_sc,default=available_terms_sc[:8],max_selections=15,key="sc_terms")
    if not sel_terms_sc: st.warning("Select at least one term.")
    else:
        st.info(f"Loading {len(sel_terms_sc)} term(s) — this may take a minute. Results are cached.")
        if st.button("Build Scorecard", type="primary", key="sc_btn"):
            with st.spinner("Fetching case data from Oyez..."):
                sc_df = _cc_load_all_circuits(tuple(sorted(sel_terms_sc,reverse=True)))
            st.session_state["scorecard_df"] = sc_df
            st.session_state["scorecard_terms"] = sel_terms_sc

        if "scorecard_df" not in st.session_state:
            st.stop()
        else:
            sc_df_data: pd.DataFrame = st.session_state["scorecard_df"]
            terms_loaded_sc = st.session_state.get("scorecard_terms",[])
            if sc_df_data.empty:
                st.warning("No circuit court data found.")
            else:
                st.success(f"Loaded **{len(sc_df_data)}** cases across **{sc_df_data['Circuit'].nunique()}** circuits.")
                summary_sc = []
                for circuit, grp in sc_df_data.groupby("Circuit"):
                    total = len(grp); rev = len(grp[grp["Outcome"]=="Reversed/Vacated"]); aff = len(grp[grp["Outcome"]=="Affirmed"])
                    summary_sc.append({"Circuit":circuit,"Cases Reviewed":total,"Reversed / Vacated":rev,"Affirmed":aff,
                                       "Other":total-rev-aff,"Reversal Rate":round(rev/total*100,1) if total else 0.0,
                                       "Affirmance Rate":round(aff/total*100,1) if total else 0.0})
                summary_df_sc = pd.DataFrame(summary_sc).sort_values("Reversal Rate",ascending=False)
                fig_main_sc = go.Figure()
                fig_main_sc.add_trace(go.Bar(name="Reversed / Vacated",x=summary_df_sc["Circuit"],y=summary_df_sc["Reversal Rate"],
                                              marker_color="#E74C3C",text=summary_df_sc["Reversal Rate"].apply(lambda x: f"{x:.0f}%"),textposition="outside"))
                fig_main_sc.add_trace(go.Bar(name="Affirmed",x=summary_df_sc["Circuit"],y=summary_df_sc["Affirmance Rate"],
                                              marker_color="#27AE60",text=summary_df_sc["Affirmance Rate"].apply(lambda x: f"{x:.0f}%"),textposition="outside"))
                fig_main_sc.update_layout(barmode="group",title="Reversal vs. Affirmance Rate by Circuit (%)",
                                           xaxis_tickangle=-30,height=420,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
                st.plotly_chart(fig_main_sc, use_container_width=True)
                st.dataframe(summary_df_sc.style.background_gradient(subset=["Reversal Rate"],cmap="RdYlGn_r"),
                             use_container_width=True,height=380)
                st.divider()
                st.subheader("Reversal Rate Trend — Single Circuit")
                all_circuits_sc = sorted(sc_df_data["Circuit"].unique())
                sel_circ_sc = st.selectbox("Select Circuit",all_circuits_sc,index=min(8,len(all_circuits_sc)-1),key="sc_circ")
                circ_df_sc = sc_df_data[sc_df_data["Circuit"]==sel_circ_sc]
                trend_rows_sc = []
                for term, grp in circ_df_sc.groupby("Term"):
                    total = len(grp); rev = len(grp[grp["Outcome"]=="Reversed/Vacated"])
                    trend_rows_sc.append({"Term":term,"Reversal Rate (%)":round(rev/total*100,1) if total else 0,"Cases":total})
                if trend_rows_sc:
                    trend_df_sc = pd.DataFrame(trend_rows_sc).sort_values("Term")
                    fig_trend_sc = px.bar(trend_df_sc,x="Term",y="Reversal Rate (%)",
                                          title=f"{sel_circ_sc} — Reversal Rate by Term",text="Cases",
                                          color="Reversal Rate (%)",color_continuous_scale="RdYlGn_r")
                    fig_trend_sc.update_layout(height=320,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_trend_sc, use_container_width=True)
                st.divider()
                issue_counts_sc = circ_df_sc["Issue Area"].value_counts().reset_index()
                issue_counts_sc.columns = ["Issue Area","Count"]
                fig_issues_sc = px.bar(issue_counts_sc.head(10),x="Count",y="Issue Area",orientation="h",
                                       title=f"Top Issue Areas from {sel_circ_sc}",color="Count",color_continuous_scale="Blues")
                fig_issues_sc.update_layout(height=340,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                st.plotly_chart(fig_issues_sc, use_container_width=True)
                with st.expander(f"All cases from {sel_circ_sc}"):
                    st.dataframe(circ_df_sc[["Term","Case","Outcome","Issue Area"]].sort_values("Term",ascending=False),
                                 use_container_width=True,height=350)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: OUTCOME PREDICTOR
# ──────────────────────────────────────────────────────────────────────────────
with tab_predictor:
    st.markdown(
        "Based on historical SCOTUS data, estimate the likelihood that a case from a given "
        "lower court and issue area will be **reversed**, **affirmed**, or **remanded**. "
        "This is a statistical tool — not legal prediction."
    )
    st.info("Loads detailed case data from Oyez. Fewer terms = faster. Results are cached after first load.")
    ISSUE_AREAS_PR = ["Criminal Procedure","Civil Rights","First Amendment","Due Process",
                      "Privacy","Economic Activity","Judicial Power","Federalism",
                      "Federal Taxation","Unions","Attorneys","Miscellaneous"]

    with st.form("predictor_form"):
        col1_pr, col2_pr, col3_pr = st.columns(3)
        with col1_pr: circuit_label_pr = st.selectbox("Lower Court / Circuit",list(CIRCUIT_KEYWORDS.keys()),key="pr_circuit")
        with col2_pr: issue_area_pr    = st.selectbox("Issue Area",["Any"]+ISSUE_AREAS_PR,key="pr_issue")
        with col3_pr: num_terms_pr     = st.slider("Number of recent terms",3,15,8,key="pr_num_terms")
        submitted_pr = st.form_submit_button("Predict",type="primary")

    if submitted_pr:
        terms_tuple_pr = tuple(range(CURRENT_YEAR, CURRENT_YEAR-num_terms_pr,-1))
        with st.spinner(f"Loading {num_terms_pr} terms of data…"):
            df_pr = _cc_load_historical(terms_tuple_pr)
        st.session_state["predictor_df"] = df_pr
        st.session_state["predictor_params"] = (circuit_label_pr, issue_area_pr, num_terms_pr)

    if "predictor_df" in st.session_state:
        df_pr_data = st.session_state["predictor_df"]
        cl_pr, ia_pr, nt_pr = st.session_state.get("predictor_params",("Any / Unknown","Any",8))
        circuit_kw_pr = CIRCUIT_KEYWORDS.get(cl_pr,"")
        stats_pr = _compute_predictor_stats(df_pr_data, circuit_kw_pr, ia_pr if ia_pr!="Any" else "")
        st.divider(); st.subheader("Results")
        if stats_pr["total"] == 0:
            st.warning(f"No historical cases found matching **{cl_pr}** + **{ia_pr}** in the last {nt_pr} terms.")
        else:
            aff_pr = stats_pr["affirm_pct"]; rev_pr = stats_pr["reverse_pct"]; oth_pr = stats_pr["other_pct"]
            if rev_pr > aff_pr: verdict_pr = "⬆️ **More likely to be REVERSED**"; verdict_color_pr = "#E74C3C"
            elif aff_pr > rev_pr: verdict_pr = "✅ **More likely to be AFFIRMED**"; verdict_color_pr = "#27AE60"
            else: verdict_pr = "⚖️ **Roughly equal odds**"; verdict_color_pr = "#F39C12"
            st.markdown(f"<div style='background:{verdict_color_pr}22;border-left:5px solid {verdict_color_pr};"
                        f"padding:14px 18px;border-radius:6px;font-size:1.15em'>{verdict_pr}</div>",unsafe_allow_html=True)
            st.markdown("")
            m1_pr, m2_pr, m3_pr, m4_pr = st.columns(4)
            m1_pr.metric("Cases Analyzed",stats_pr["total"])
            m2_pr.metric("Affirmed",f"{aff_pr:.1f}%")
            m3_pr.metric("Reversed / Vacated",f"{rev_pr:.1f}%")
            m4_pr.metric("Other Outcome",f"{oth_pr:.1f}%")
            fig_gauge_pr = go.Figure(go.Indicator(
                mode="gauge+number",value=rev_pr,title={"text":"Reversal Rate (%)"},
                gauge={"axis":{"range":[0,100]},"bar":{"color":"#E74C3C"},
                       "steps":[{"range":[0,33],"color":"#D5F5E3"},{"range":[33,66],"color":"#FCF3CF"},{"range":[66,100],"color":"#FADBD8"}],
                       "threshold":{"line":{"color":"#27AE60","width":4},"thickness":0.75,"value":aff_pr}},
                number={"suffix":"%"}))
            fig_gauge_pr.update_layout(height=280,margin=dict(l=30,r=30,t=60,b=10))
            st.plotly_chart(fig_gauge_pr, use_container_width=True)
            if circuit_kw_pr:
                st.subheader(f"Outcome Breakdown by Issue Area — {cl_pr}")
                issue_rows_pr = []
                for ia_lbl, grp in stats_pr["df"].groupby("issue_area"):
                    total_ia = len(grp); rev_ia = grp["reversed"].sum(); aff_ia = grp["affirmed"].sum()
                    issue_rows_pr.append({"Issue Area":ia_lbl,"Cases":total_ia,
                                           "Reversal %":round(rev_ia/total_ia*100,1),"Affirm %":round(aff_ia/total_ia*100,1)})
                if issue_rows_pr:
                    ia_df_pr = pd.DataFrame(issue_rows_pr).sort_values("Reversal %",ascending=False)
                    fig_ia_pr = px.bar(ia_df_pr,x="Issue Area",y=["Reversal %","Affirm %"],barmode="group",
                                       title=f"{cl_pr} — Reversal vs. Affirmance by Issue Area",
                                       color_discrete_map={"Reversal %":"#E74C3C","Affirm %":"#27AE60"})
                    fig_ia_pr.update_layout(height=360,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
                    st.plotly_chart(fig_ia_pr, use_container_width=True)
            st.subheader("Reversal Rate Trend Over Time")
            trend_rows_pr = []
            for term_val, grp in stats_pr["df"].groupby("term"):
                total_t = len(grp); rev_t = grp["reversed"].sum()
                trend_rows_pr.append({"Term":term_val,"Reversal %":round(rev_t/total_t*100,1),"Cases":total_t})
            if trend_rows_pr:
                trend_df_pr = pd.DataFrame(trend_rows_pr).sort_values("Term")
                fig_trend_pr = px.line(trend_df_pr,x="Term",y="Reversal %",markers=True,title="Reversal Rate by Term")
                fig_trend_pr.update_layout(height=280,plot_bgcolor="white",paper_bgcolor="white")
                st.plotly_chart(fig_trend_pr, use_container_width=True)
            st.caption(f"Based on {stats_pr['total']} cases from the {nt_pr} most recent terms. Statistical trends, not legal advice.")
