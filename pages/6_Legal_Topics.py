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
import json
from collections import defaultdict
from utils.charts import build_journey_diagram, build_voting_chart
from utils.oyez_api import extract_court_journey


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Load legal data from JSON ─────────────────────────────────────────────────
_DATA_FILE = os.path.join(os.path.dirname(__file__), "legal_data.json")
with open(_DATA_FILE, "r", encoding="utf-8") as _f:
    _LEGAL_DATA = json.load(_f)

def _oyez_web_url(api_href: str) -> str:
    """Convert an api.oyez.org href to a www.oyez.org case page URL."""
    return api_href.replace("https://api.oyez.org/", "https://www.oyez.org/") if api_href else ""

@st.cache_data(show_spinner=False)
def _lt_fetch_cases_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",headers=HEADERS,timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _lt_fetch_case(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _lt_issue_label(c: dict) -> str:
    ia = c.get("issue_area")
    if isinstance(ia, dict): return ia.get("label","Unknown")
    return str(ia) if ia else "Unknown"

def _lt_disp_label(c: dict) -> str:
    d = c.get("disposition")
    if isinstance(d, dict): return d.get("label","Unknown")
    return str(d) if d else "Unknown"

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📚 Legal Topics")
tab_issue, tab_amend, tab_provisions, tab_landmark = st.tabs([
    "📋 Issue Area Decisions", "📜 Amendments Tracker",
    "🏛️ Constitutional Provisions", "⭐ Landmark Cases"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: ISSUE AREA DECISIONS
# ──────────────────────────────────────────────────────────────────────────────
with tab_issue:
    st.markdown("Browse all SCOTUS decisions in a selected legal domain, ranked by term.")
    ISSUE_AREAS_LT = ["Criminal Procedure","Civil Rights","First Amendment","Due Process",
        "Privacy","Economic Activity","Judicial Power","Federalism","Federal Taxation",
        "Unions","Attorneys","Interstate Relations","Miscellaneous","Private Action"]
    col1_ia, col2_ia, col3_ia = st.columns(3)
    _term_range_ia = list(range(CURRENT_YEAR, 1989, -1))
    with col1_ia: issue_ia = st.selectbox("Legal Issue Area",ISSUE_AREAS_LT,key="ia_issue")
    with col2_ia: start_term_ia = st.selectbox("From Term",_term_range_ia,index=10,key="ia_start")
    with col3_ia: end_term_ia   = st.selectbox("To Term",_term_range_ia,index=0,key="ia_end")
    if start_term_ia > end_term_ia: start_term_ia, end_term_ia = end_term_ia, start_term_ia
    terms_ia = list(range(start_term_ia, end_term_ia+1))

    if st.button("Load Decisions",type="primary",key="ia_btn"):
        rows_ia = []
        progress_ia = st.progress(0)
        for idx, term in enumerate(sorted(terms_ia,reverse=True)):
            cases = _lt_fetch_cases_term(term)
            for c in cases:
                label = _lt_issue_label(c)
                if issue_ia.lower() in label.lower():
                    rows_ia.append({"Term":term,"Case":c.get("name",""),"Disposition":_lt_disp_label(c),
                                    "Issue Area":label,"href":c.get("href","")})
            progress_ia.progress((idx+1)/len(terms_ia)); time.sleep(0.02)
        progress_ia.empty()
        st.session_state["ia_rows"] = rows_ia; st.session_state["ia_area"] = issue_ia

    if "ia_rows" in st.session_state and st.session_state.get("ia_area") == issue_ia:
        rows_ia_data = st.session_state["ia_rows"]
        if not rows_ia_data:
            st.warning(f"No cases found for '{issue_ia}' in the selected range.")
        else:
            df_ia = pd.DataFrame(rows_ia_data)
            st.success(f"Found **{len(df_ia)}** decisions in **{issue_ia}** from {start_term_ia}–{end_term_ia}.")
            col_pie_ia, col_trend_ia = st.columns(2)
            with col_pie_ia:
                disp_counts_ia = df_ia["Disposition"].value_counts().reset_index()
                disp_counts_ia.columns = ["Disposition","Count"]
                fig_pie_ia = px.pie(disp_counts_ia,names="Disposition",values="Count",title=f"{issue_ia} — Decision Outcomes",hole=0.3)
                fig_pie_ia.update_layout(height=330); st.plotly_chart(fig_pie_ia)
            with col_trend_ia:
                term_counts_ia = df_ia.groupby("Term").size().reset_index(name="Cases")
                fig_trend_ia = px.bar(term_counts_ia.sort_values("Term"),x="Term",y="Cases",
                                      title=f"{issue_ia} — Cases per Term",color="Cases",color_continuous_scale="Blues")
                fig_trend_ia.update_layout(height=330,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                st.plotly_chart(fig_trend_ia)
            st.subheader("Case List")
            disp_filter_ia = st.multiselect("Filter by Disposition",sorted(df_ia["Disposition"].unique()),default=[],key="ia_disp_filter")
            display_ia = df_ia[df_ia["Disposition"].isin(disp_filter_ia)] if disp_filter_ia else df_ia
            display_ia = display_ia[["Term","Case","Disposition"]].sort_values("Term",ascending=False)
            st.dataframe(display_ia,height=400)
            st.divider(); st.subheader("Case Drilldown")
            case_names_ia = df_ia["Case"].tolist()
            sel_case_ia = st.selectbox("Select a case to inspect",case_names_ia,key="ia_case_sel")
            row_ia = df_ia[df_ia["Case"]==sel_case_ia].iloc[0]
            if row_ia.get("href"):
                with st.spinner("Loading case details..."):
                    detail_ia = _lt_fetch_case(row_ia["href"])
                if detail_ia:
                    question_ia = detail_ia.get("question",""); facts_ia = detail_ia.get("facts_of_the_case","") or detail_ia.get("description","")
                    col_q_ia, col_f_ia = st.columns(2)
                    with col_q_ia:
                        if question_ia: st.markdown("**Legal Question**"); st.write(question_ia)
                    with col_f_ia:
                        if facts_ia: st.markdown("**Background**"); st.write(facts_ia)
                    votes_ia = []
                    for dec in (detail_ia.get("decisions") or []):
                        for vote in (dec.get("votes") or []):
                            member = vote.get("member",{}) or {}
                            votes_ia.append({"Justice":member.get("name","?"),"Vote":vote.get("vote","")})
                    if votes_ia:
                        vote_df_ia = pd.DataFrame(votes_ia)
                        maj_ia = vote_df_ia[vote_df_ia["Vote"].str.lower().isin(["majority","concurrence"])]["Justice"].tolist()
                        dis_ia = vote_df_ia[vote_df_ia["Vote"].str.lower()=="dissent"]["Justice"].tolist()
                        c1_ia, c2_ia = st.columns(2)
                        with c1_ia: st.markdown(f"**✅ Majority ({len(maj_ia)}):** {', '.join(maj_ia)}")
                        with c2_ia: st.markdown(f"**❌ Dissent ({len(dis_ia)}):** {', '.join(dis_ia) if dis_ia else 'None'}")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: CONSTITUTIONAL AMENDMENTS TRACKER
# ──────────────────────────────────────────────────────────────────────────────
with tab_amend:
    # ── Data loaded from legal_data.json ──────────────────────────────────
    AMENDMENTS = _LEGAL_DATA["amendments"]

    st.markdown("Map landmark SCOTUS rulings to the constitutional amendment they interpreted.")
    amendment_sel = st.selectbox("Select an Amendment", list(AMENDMENTS.keys()), key="amend_sel")
    amend_data = AMENDMENTS[amendment_sel]; color_amend = amend_data["color"]
    st.markdown(f"> {amend_data['summary']}")
    st.divider()
    cases_amend = amend_data["cases"]
    years_amend  = [c[3] for c in cases_amend]
    names_amend  = [c[0] for c in cases_amend]
    holdings_amend = [c[2] for c in cases_amend]

    fig_tl_amend = go.Figure()
    fig_tl_amend.add_trace(go.Scatter(x=years_amend,y=[0]*len(years_amend),mode="markers+text",
                                       marker=dict(size=18,color=color_amend,line=dict(width=2,color="white")),
                                       text=[str(y) for y in years_amend],textposition="top center",
                                       textfont=dict(size=10,color="#2C3E50"),
                                       hovertext=[f"<b>{n}</b><br>{h}" for n,h in zip(names_amend,holdings_amend)],
                                       hoverinfo="text",showlegend=False))
    fig_tl_amend.add_shape(type="line",x0=min(years_amend)-5,x1=max(years_amend)+5,y0=0,y1=0,
                            line=dict(color="#BDC3C7",width=2))
    fig_tl_amend.update_layout(height=180,
                                xaxis=dict(showgrid=False,zeroline=False,range=[min(years_amend)-8,max(years_amend)+8]),
                                yaxis=dict(showgrid=False,zeroline=False,showticklabels=False,range=[-0.5,0.8]),
                                plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=20,r=20,t=20,b=20))
    st.subheader("Case Timeline"); st.plotly_chart(fig_tl_amend)
    st.divider(); st.subheader("Key Cases")
    for i, (name, href, holding, year) in enumerate(cases_amend):
        with st.expander(f"**{name}** — {holding[:80]}{'…' if len(holding)>80 else ''}"):
            st.markdown(f"**Holding:** {holding}"); st.markdown(f"**Year:** {year}")
            _oyez_url_am = _oyez_web_url(href)
            col_load_amend, col_oyez_amend, _ = st.columns([1, 1, 2])
            with col_load_amend:
                load_key_amend = f"load_amend_{amendment_sel}_{i}"
                if st.button("Load Full Details", key=load_key_amend):
                    st.session_state[f"detail_amend_{amendment_sel}_{i}"] = _lt_fetch_case(href)
            with col_oyez_amend:
                if _oyez_url_am:
                    st.markdown(f'<a href="{_oyez_url_am}" target="_blank"><button style="background:#1565C0;color:white;border:none;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:0.85em;">🔗 View on Oyez</button></a>', unsafe_allow_html=True)
            detail_key_amend = f"detail_amend_{amendment_sel}_{i}"
            if detail_key_amend in st.session_state:
                detail_amend = st.session_state[detail_key_amend]
                if not detail_amend:
                    st.warning("Could not load case."); continue
                col_facts_amend, col_meta_amend = st.columns([2,1])
                with col_facts_amend:
                    facts_am = detail_amend.get("facts_of_the_case","") or detail_amend.get("description","")
                    if facts_am: st.markdown("**Facts**"); st.write(facts_am[:800]+("…" if len(facts_am or "")>800 else ""))
                    conclusion_am = detail_amend.get("conclusion","")
                    if conclusion_am: st.markdown("**Conclusion**"); st.write(conclusion_am[:600]+("…" if len(conclusion_am or "")>600 else ""))
                with col_meta_amend:
                    decided_by_am = detail_amend.get("decided_by") or {}
                    if decided_by_am: st.markdown(f"**Court:** {decided_by_am.get('name','')}")
                    disp_am = detail_amend.get("disposition") or {}
                    if isinstance(disp_am,dict) and disp_am.get("label"): st.markdown(f"**Disposition:** {disp_am['label']}")
                justices_am = []
                for dec in (detail_amend.get("decisions") or []):
                    for vote in (dec.get("votes") or []):
                        member = vote.get("member",{}) or {}
                        justices_am.append({"name":member.get("name","?"),"vote":vote.get("vote","")})
                if justices_am:
                    fig_v_am = build_voting_chart(justices_am)
                    if fig_v_am: st.plotly_chart(fig_v_am)
                    majority_am = [j["name"] for j in justices_am if (j.get("vote") or "").lower() in ("majority","concurrence")]
                    dissent_am  = [j["name"] for j in justices_am if (j.get("vote") or "").lower()=="dissent"]
                    c1_am, c2_am = st.columns(2)
                    with c1_am: st.markdown(f"**✅ Majority:** {', '.join(majority_am)}")
                    with c2_am: st.markdown(f"**❌ Dissent:** {', '.join(dissent_am) if dissent_am else 'None (unanimous)'}")

    st.divider(); st.subheader("All Amendments — Case Count Overview")
    summary_rows_amend = [{"Amendment":k.split("—")[0].strip(),"Cases":len(v["cases"]),"Color":v["color"]} for k,v in AMENDMENTS.items()]
    summary_df_amend = pd.DataFrame(summary_rows_amend)
    fig_overview_amend = go.Figure(go.Bar(x=summary_df_amend["Amendment"],y=summary_df_amend["Cases"],
                                           marker_color=summary_df_amend["Color"].tolist(),
                                           text=summary_df_amend["Cases"],textposition="outside"))
    fig_overview_amend.update_layout(height=340,xaxis_title="",yaxis_title="Landmark Cases Tracked",
                                      plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
    st.plotly_chart(fig_overview_amend)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: CONSTITUTIONAL PROVISIONS TRACKER
# ──────────────────────────────────────────────────────────────────────────────
with tab_provisions:
    # ── Data loaded from legal_data.json ──────────────────────────────────
    PROVISIONS = [tuple(p) for p in _LEGAL_DATA["provisions"]]
    PROV_MAP = {p[0]:p for p in PROVISIONS}

    # LANDMARK_CASES_PROV: convert inner provision lists back to lists (already lists from JSON)
    LANDMARK_CASES_PROV = [tuple(c[:2]) + (c[2],) + tuple(c[3:]) for c in _LEGAL_DATA["landmark_cases_prov"]]

    def _prov_label(pid): return PROV_MAP.get(pid,("","","","",""))[1]
    def _prov_color(pid): return PROV_MAP.get(pid,("","","","","#95A5A6"))[4]

    st.markdown("Explore which constitutional provisions have generated the most landmark litigation.")

    # Inline filters (converted from sidebar)
    col_f1_pv, col_f2_pv, col_f3_pv = st.columns(3)
    with col_f1_pv:
        amendment_options_pv = sorted(set(p[3] for p in PROVISIONS))
        sel_amendments_pv = st.multiselect("Filter by Article / Amendment",amendment_options_pv,default=amendment_options_pv,key="pv_amend")
    with col_f2_pv:
        year_range_pv = st.slider("Year range",1800,CURRENT_YEAR,(1900,CURRENT_YEAR),key="pv_yr")
    with col_f3_pv:
        min_sig_pv = st.slider("Min. significance (1–5 stars)",1,5,3,key="pv_sig")

    all_prov_ids_pv = [p[0] for p in PROVISIONS if p[3] in sel_amendments_pv]
    filtered_cases_pv = [c for c in LANDMARK_CASES_PROV
                         if year_range_pv[0]<=c[1]<=year_range_pv[1] and c[4]>=min_sig_pv
                         and any(pid in all_prov_ids_pv for pid in c[2])]

    sub_ov_pv, sub_detail_pv, sub_tl_pv, sub_cross_pv = st.tabs(["📊 Overview","🔍 Provision Detail","📅 Timeline","⚔️ Cross-Provision"])

    with sub_ov_pv:
        prov_counts_pv: dict[str,int] = defaultdict(int)
        for c in filtered_cases_pv:
            for pid in c[2]:
                if pid in all_prov_ids_pv: prov_counts_pv[pid] += 1
        if prov_counts_pv:
            count_df_pv = pd.DataFrame([{"Provision":_prov_label(pid),"Cases":cnt,"Amendment":PROV_MAP[pid][3],"Color":_prov_color(pid)}
                                         for pid,cnt in sorted(prov_counts_pv.items(),key=lambda x:-x[1])])
            fig_bar_pv = go.Figure(go.Bar(x=count_df_pv["Cases"],y=count_df_pv["Provision"],orientation="h",
                                           marker_color=count_df_pv["Color"].tolist(),text=count_df_pv["Cases"],textposition="outside",
                                           hovertemplate="<b>%{y}</b><br>%{x} landmark cases<extra></extra>"))
            fig_bar_pv.update_layout(title="Landmark Cases per Constitutional Provision",
                                      height=max(350,len(count_df_pv)*28),xaxis_title="Number of Cases",
                                      yaxis=dict(autorange="reversed"),plot_bgcolor="white",paper_bgcolor="white",
                                      margin=dict(l=160,r=40,t=40,b=40))
            st.plotly_chart(fig_bar_pv)
        amend_counts_pv: dict[str,int] = defaultdict(int)
        for c in filtered_cases_pv:
            seen: set[str] = set()
            for pid in c[2]:
                amend = PROV_MAP.get(pid,("","","","",""))[3]
                if amend not in seen: amend_counts_pv[amend]+=1; seen.add(amend)
        amend_df_pv = pd.DataFrame([{"Amendment":a,"Cases":n} for a,n in sorted(amend_counts_pv.items(),key=lambda x:-x[1])])
        fig_donut_pv = go.Figure(go.Pie(labels=amend_df_pv["Amendment"],values=amend_df_pv["Cases"],hole=0.45,
                                         textinfo="label+value",marker_colors=px.colors.qualitative.Set3))
        fig_donut_pv.update_layout(height=360,margin=dict(l=20,r=20,t=20,b=20))
        st.subheader("Cases per Amendment"); st.plotly_chart(fig_donut_pv)

    with sub_detail_pv:
        visible_provs_pv = [(p[1],p[0]) for p in PROVISIONS if p[0] in all_prov_ids_pv]
        if visible_provs_pv:
            sel_prov_pv = st.selectbox("Select provision",visible_provs_pv,format_func=lambda x: x[0],key="pv_sel")
            sel_prov_label_pv, sel_prov_id_pv = sel_prov_pv
            prov_data_pv = PROV_MAP[sel_prov_id_pv]; color_pv = prov_data_pv[4]
            st.markdown(f'<div style="border-left:5px solid {color_pv};padding:10px 16px;background:#F8F9FA;margin-bottom:16px;">'
                        f'<strong style="font-size:1.1em;">{prov_data_pv[2]}</strong></div>',unsafe_allow_html=True)
            prov_cases_pv = [c for c in filtered_cases_pv if sel_prov_id_pv in c[2]]
            prov_cases_pv.sort(key=lambda x: x[1])
            st.markdown(f"**{len(prov_cases_pv)} landmark cases** touch this provision.")
            stars_fn = lambda n: "★"*n+"☆"*(5-n)
            for case_pv in prov_cases_pv:
                sig_color_pv = "#E74C3C" if case_pv[4]==5 else "#E67E22" if case_pv[4]>=4 else "#27AE60"
                other_provs_pv = [_prov_label(pid) for pid in case_pv[2] if pid != sel_prov_id_pv]
                also_str_pv = f"  ·  *Also: {', '.join(other_provs_pv)}*" if other_provs_pv else ""
                # Look up Oyez href from LANDMARK_CASES_LT for cross-linking
                _pv_oyez_href = next((c[1] for cat in _LEGAL_DATA["landmark_cases_lt"].values() for c in cat if c[0].startswith(case_pv[0].split(" (")[0])), "")
                _pv_oyez_btn = f' <a href="{_oyez_web_url(_pv_oyez_href)}" target="_blank" style="font-size:0.8em;color:#1565C0;">🔗 Oyez</a>' if _pv_oyez_href else ""
                st.markdown(f'<div style="border-left:3px solid {sig_color_pv};padding:6px 12px;margin-bottom:6px;">'
                             f'<strong>{case_pv[0]}</strong> ({case_pv[1]}) <span style="color:{sig_color_pv}">{stars_fn(case_pv[4])}</span>{_pv_oyez_btn}'
                             f'{also_str_pv}<br><span style="color:#555;">{case_pv[3]}</span></div>',unsafe_allow_html=True)

    with sub_tl_pv:
        tl_rows_pv = []
        for c in filtered_cases_pv:
            for pid in c[2]:
                if pid in all_prov_ids_pv:
                    tl_rows_pv.append({"Case":c[0],"Year":c[1],"Provision":_prov_label(pid),
                                        "Significance":c[4],"Holding":c[3],"Color":_prov_color(pid)})
        if tl_rows_pv:
            tl_df_pv = pd.DataFrame(tl_rows_pv)
            fig_tl_pv = px.scatter(tl_df_pv,x="Year",y="Provision",size="Significance",color="Provision",
                                    hover_name="Case",hover_data={"Year":True,"Holding":True,"Significance":True,"Provision":False},
                                    title="Constitutional Provisions Litigation Timeline",size_max=18)
            fig_tl_pv.update_layout(height=max(450,len(all_prov_ids_pv)*30),plot_bgcolor="white",paper_bgcolor="white",
                                     yaxis_title="",xaxis_title="Year",showlegend=False,margin=dict(l=170,r=20,t=40,b=40))
            st.plotly_chart(fig_tl_pv)
            st.caption("Dot size = significance rating (1–5). Hover for case name and holding.")

    with sub_cross_pv:
        st.markdown("Cases that implicate **multiple constitutional provisions** highlight the Court's need to balance competing rights.")
        multi_pv = [c for c in filtered_cases_pv if len(c[2])>=2 and sum(1 for pid in c[2] if pid in all_prov_ids_pv)>=2]
        if multi_pv:
            for c in sorted(multi_pv,key=lambda x: -x[4]):
                provs_pv = [_prov_label(pid) for pid in c[2] if pid in all_prov_ids_pv]
                colors_pv = [_prov_color(pid) for pid in c[2] if pid in all_prov_ids_pv]
                prov_tags = "".join(f'<span style="background:{col};color:white;padding:2px 8px;border-radius:3px;font-size:0.8em;margin-right:4px;">{prov}</span>'
                                    for prov,col in zip(provs_pv,colors_pv))
                st.markdown(f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px 14px;margin-bottom:8px;">'
                             f'<strong>{c[0]}</strong> ({c[1]})<br>{prov_tags}<br>'
                             f'<span style="color:#555;font-size:0.9em;">{c[3]}</span></div>',unsafe_allow_html=True)
        else:
            st.info("No multi-provision cases found with current filters.")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: LANDMARK CASES EXPLORER
# ──────────────────────────────────────────────────────────────────────────────
with tab_landmark:
    # ── Data loaded from legal_data.json ──────────────────────────────────
    LANDMARK_CASES_LT = {k: [tuple(c) for c in v] for k, v in _LEGAL_DATA["landmark_cases_lt"].items()}

    st.markdown("A curated collection of landmark Supreme Court rulings — select any case for full details, votes, and court journey.")
    category_lt = st.selectbox("Legal Category", list(LANDMARK_CASES_LT.keys()), key="lm_cat")
    cases_in_cat_lt = LANDMARK_CASES_LT[category_lt]
    case_options_lt = [c[0] for c in cases_in_cat_lt]
    selected_label_lt = st.selectbox("Select a Landmark Case", case_options_lt, key="lm_case")
    selected_lt = next(c for c in cases_in_cat_lt if c[0]==selected_label_lt)
    case_name_lt, case_href_lt, significance_lt = selected_lt
    _oyez_web_lt = _oyez_web_url(case_href_lt)
    _oyez_link_lt = f' &nbsp; [🔗 View on Oyez]({_oyez_web_lt}){{:target="_blank"}}' if _oyez_web_lt else ""
    st.info(f"**Why it matters:** {significance_lt}")
    if _oyez_web_lt:
        st.markdown(f'<a href="{_oyez_web_lt}" target="_blank"><button style="background:#1565C0;color:white;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:0.9em;margin-bottom:8px;">🔗 View Full Case on Oyez</button></a>', unsafe_allow_html=True)

    with st.spinner("Loading case from Oyez..."):
        detail_lt = _lt_fetch_case(case_href_lt)

    if not detail_lt:
        st.error("Could not load this case from Oyez. It may have moved. Try refreshing.")
    else:
        col_hdr_lt, col_meta_lt = st.columns([2,1])
        with col_hdr_lt:
            st.subheader(detail_lt.get("name",case_name_lt))
            facts_lt = detail_lt.get("facts_of_the_case","") or detail_lt.get("description","")
            if facts_lt:
                with st.expander("Facts of the Case",expanded=True): st.write(facts_lt)
            question_lt = detail_lt.get("question","")
            if question_lt:
                with st.expander("Legal Question"): st.write(question_lt)
            conclusion_lt = detail_lt.get("conclusion","")
            if conclusion_lt:
                with st.expander("Court's Conclusion"): st.write(conclusion_lt)
        with col_meta_lt:
            st.markdown("**Case Details**")
            st.markdown(f"- **Docket:** {detail_lt.get('docket_number','N/A')}")
            decided_by_lt = detail_lt.get("decided_by") or {}
            if decided_by_lt: st.markdown(f"- **Decided by:** {decided_by_lt.get('name','N/A')}")
            disp_lt = detail_lt.get("disposition") or {}
            if isinstance(disp_lt,dict) and disp_lt.get("label"): st.markdown(f"- **Disposition:** {disp_lt['label']}")

        st.divider(); st.subheader("⬆️ Court Journey")
        steps_lt = extract_court_journey(detail_lt)
        lower_lt = detail_lt.get("lower_court") or {}
        lc_name_lt = lower_lt.get("name","") if isinstance(lower_lt,dict) else ""
        if len(steps_lt)<2 and lc_name_lt:
            steps_lt = [{"court":lc_name_lt,"level":"Lower Court","decision":""},
                        {"court":"U.S. Supreme Court","level":"Supreme Court","decision":""}]
        if steps_lt:
            dispo_label_lt = (detail_lt.get("disposition") or {}).get("label","") if isinstance(detail_lt.get("disposition"),dict) else ""
            if dispo_label_lt: steps_lt[-1]["decision"] = dispo_label_lt
            fig_lt = build_journey_diagram(steps_lt, detail_lt.get("name",case_name_lt))
            if fig_lt: st.plotly_chart(fig_lt)
        else:
            st.info("Court journey data not available for this case.")

        st.divider(); st.subheader("⚖️ Justice Votes")
        justices_lt = []
        for dec in (detail_lt.get("decisions") or []):
            winning_party_lt = dec.get("winning_party","")
            for vote in (dec.get("votes") or []):
                member = vote.get("member",{}) or {}
                justices_lt.append({"name":member.get("name","Unknown"),"vote":vote.get("vote",""),"winning_party":winning_party_lt})
        if justices_lt:
            fig2_lt = build_voting_chart(justices_lt)
            if fig2_lt: st.plotly_chart(fig2_lt)
            majority_lt = [j["name"] for j in justices_lt if (j.get("vote") or "").lower() in ("majority","concurrence")]
            dissent_lt  = [j["name"] for j in justices_lt if (j.get("vote") or "").lower()=="dissent"]
            winning_lt  = justices_lt[0].get("winning_party","") if justices_lt else ""
            c1_lt, c2_lt, c3_lt = st.columns(3)
            with c1_lt:
                st.markdown(f"**✅ Majority ({len(majority_lt)}):**")
                for n in majority_lt: st.markdown(f"- {n}")
            with c2_lt:
                st.markdown(f"**❌ Dissent ({len(dissent_lt)}):**")
                if dissent_lt:
                    for n in dissent_lt: st.markdown(f"- {n}")
                else:
                    st.markdown("_Unanimous_")
            with c3_lt:
                if winning_lt: st.markdown(f"**🏆 Winning Party:**"); st.markdown(winning_lt)
        else:
            st.info("Voting data not available for this case.")

        oral_args_lt = detail_lt.get("oral_argument_audio",[])
        if oral_args_lt:
            st.divider(); st.subheader("🎙️ Oral Arguments")
            for arg in oral_args_lt[:2]:
                if isinstance(arg,dict) and arg.get("href"):
                    st.markdown(f"[{arg.get('title','Listen to oral argument')}]({arg['href']})")
