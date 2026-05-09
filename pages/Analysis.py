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
from utils.local_data import fetch_oyez, infer_issue_area, infer_disposition
from utils.export import csv_download_button


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Party win-rate helpers ─────────────────────────────────────────────────────
FEDERAL_KEYWORDS = ["united states","u.s.","federal","department of","secretary of","attorney general",
    "irs","epa","fbi","cia","doj","hhs","commissioner","administrator","director of","bureau of",
    "national labor relations","securities and exchange","federal trade","immigration","customs"]
STATE_KEYWORDS   = ["state of","commonwealth of","people of","city of","county of","town of","village of",
    "board of","district of","california","texas","new york","florida","illinois","ohio",
    "michigan","georgia","north carolina","virginia","arizona","washington","colorado",
    "nevada","oregon","utah","minnesota"]
CORP_KEYWORDS    = ["inc.","corp.","corporation","company","co.","llc","ltd.","association","bank",
    "insurance","industries","enterprises","group","partners","trust"]

def _classify_party(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in FEDERAL_KEYWORDS): return "Federal Government"
    if any(k in n for k in STATE_KEYWORDS):   return "State / Local Gov't"
    if any(k in n for k in CORP_KEYWORDS):    return "Corporation / Org"
    return "Individual / Other"

def _disposition_winner(disp: str) -> str | None:
    d = (disp or "").lower()
    if any(w in d for w in ["affirm"]): return "respondent"
    if any(w in d for w in ["revers","vacate","remand"]): return "petitioner"
    return None

JUSTICE_LEAN = {
    "Roberts":"Conservative","Thomas":"Conservative","Alito":"Conservative",
    "Gorsuch":"Conservative","Kavanaugh":"Conservative","Barrett":"Conservative",
    "Scalia":"Conservative","Kennedy":"Moderate","O'Connor":"Moderate",
    "Sotomayor":"Liberal","Kagan":"Liberal","Jackson":"Liberal",
    "Breyer":"Liberal","Ginsburg":"Liberal","Stevens":"Liberal",
    "Souter":"Liberal","White":"Moderate","Blackmun":"Liberal",
    "Powell":"Moderate","Rehnquist":"Conservative","Burger":"Conservative",
}
LEAN_COLORS  = {"Conservative":"#E74C3C","Moderate":"#27AE60","Liberal":"#3498DB"}
PARTY_COLORS = {"Federal Government":"#E74C3C","State / Local Gov't":"#E67E22",
                "Corporation / Org":"#3498DB","Individual / Other":"#27AE60"}

def _last_name(full: str) -> str:
    parts = full.strip().split(); return parts[-1] if parts else full

# ── Cached loaders ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _an_load_close_decisions(terms: tuple) -> list[dict]:
    cases_out = []
    for term in terms:
        cases = get_cases_by_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            detail = get_case_detail(href)
            if not detail:
                continue
            for decision in (detail.get("decisions") or []):
                votes = decision.get("votes") or []
                if not votes:
                    continue
                maj_votes = [v for v in votes if (v.get("vote") or "").lower() in ("majority", "concurrence", "concurring")]
                dis_votes = [v for v in votes if (v.get("vote") or "").lower() in ("dissent", "minority")]
                maj_count = len(maj_votes)
                dis_count = len(dis_votes)
                total = maj_count + dis_count
                if total < 7:
                    continue
                split = f"{maj_count}-{dis_count}"
                is_close = (maj_count - dis_count) <= 1
                is_near = (maj_count - dis_count) == 2
                if not (is_close or is_near):
                    continue
                issue = infer_issue_area(detail)
                disp_label = (decision.get("decision_type") or "").strip().title()
                maj_names = [_last_name((v.get("member") or {}).get("name", "")) for v in maj_votes if isinstance(v.get("member"), dict)]
                dis_names = [_last_name((v.get("member") or {}).get("name", "")) for v in dis_votes if isinstance(v.get("member"), dict)]
                cases_out.append({
                    "term": term, "case": detail.get("name", ""), "split": split,
                    "majority_count": maj_count, "dissent_count": dis_count,
                    "majority": maj_names, "dissent": dis_names,
                    "issue_area": issue, "disposition": disp_label,
                    "is_close": is_close, "href": href,
                })
    return cases_out

@st.cache_data(show_spinner=False)
def _an_load_win_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = get_cases_by_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href:
                continue
            detail = get_case_detail(href)
            if not detail:
                continue
            name = detail.get("name", "")
            name_parts = name.split(" v. ")
            petitioner = detail.get("first_party") or (name_parts[0].strip() if len(name_parts) >= 2 else "")
            respondent = detail.get("second_party") or (name_parts[1].strip() if len(name_parts) >= 2 else "")
            disp_label = infer_disposition(detail)
            winner_side = _disposition_winner(disp_label)
            if not winner_side:
                continue
            pet_type = _classify_party(petitioner)
            res_type = _classify_party(respondent)
            winner_type = pet_type if winner_side == "petitioner" else res_type
            issue = infer_issue_area(detail)
            rows.append({
                "term": term, "case": name[:60],
                "petitioner": petitioner[:60], "respondent": respondent[:60],
                "pet_type": pet_type, "res_type": res_type,
                "winner_side": winner_side, "winner_type": winner_type,
                "issue_area": issue, "disposition": disp_label,
            })
    return rows

# ── SCOTUS vs Congress curated data ──────────────────────────────────────────
LAWS_STRUCK_DOWN = [
    dict(case="Marbury v. Madison",             year=1803, law="Judiciary Act of 1789 §13",         basis="Article III",         area="Judicial Power",  era="Pre-New Deal",     notes="Established judicial review"),
    dict(case="Dred Scott v. Sandford",          year=1857, law="Missouri Compromise of 1820",       basis="5th Amendment",       area="Civil Rights",    era="Pre-New Deal",     notes="Declared Congress lacked power to ban slavery in territories"),
    dict(case="Pollock v. Farmers' Loan",        year=1895, law="Income Tax Act of 1894",            basis="Article I",           area="Taxation",        era="Pre-New Deal",     notes="Led to 16th Amendment"),
    dict(case="Hammer v. Dagenhart",             year=1918, law="Keating-Owen Child Labor Act",      basis="Commerce Clause",     area="Commerce",        era="Pre-New Deal",     notes="Restricted Congress's commerce power"),
    dict(case="Schechter Poultry v. US",         year=1935, law="NIRA Title I",                      basis="Commerce Clause / Non-delegation", area="Commerce",   era="New Deal Era",   notes="Struck core New Deal legislation"),
    dict(case="US v. Butler",                    year=1936, law="Agricultural Adjustment Act",       basis="Spending Clause",     area="Agriculture",     era="New Deal Era",     notes="Restricted use of federal spending power"),
    dict(case="Youngstown Sheet v. Sawyer",      year=1952, law="Executive Order 10340",             basis="Separation of Powers",area="Executive Power", era="Warren Court",     notes="Steel seizure case; defined presidential power limits"),
    dict(case="Bolling v. Sharpe",               year=1954, law="DC school segregation statutes",    basis="5th Amendment",       area="Civil Rights",    era="Warren Court",     notes="Applied Brown to federal government"),
    dict(case="Wesberry v. Sanders",             year=1964, law="GA congressional apportionment",    basis="Article I §2",        area="Voting Rights",   era="Warren Court",     notes="One person, one vote rule"),
    dict(case="Harper v. Virginia",              year=1966, law="Virginia poll tax (state)",         basis="14th Amendment",      area="Voting Rights",   era="Warren Court",     notes="Struck down poll taxes in state elections"),
    dict(case="Immigration v. Chadha",           year=1983, law="Immigration and Nationality Act",   basis="Separation of Powers",area="Immigration",     era="Burger Court",     notes="Struck down legislative veto"),
    dict(case="Bowsher v. Synar",                year=1986, law="Gramm-Rudman-Hollings Act",         basis="Separation of Powers",area="Budget",          era="Burger Court",     notes="Congress cannot control execution of laws"),
    dict(case="US v. Lopez",                     year=1995, law="Gun-Free School Zones Act",         basis="Commerce Clause",     area="Commerce",        era="Rehnquist Court",  notes="First limit on Commerce Clause in 60 years"),
    dict(case="US v. Morrison",                  year=2000, law="Violence Against Women Act §13981", basis="Commerce Clause",     area="Civil Rights",    era="Rehnquist Court",  notes="Civil remedy provision exceeded commerce power"),
    dict(case="Printz v. United States",         year=1997, law="Brady Handgun Violence Prevention Act",basis="10th Amendment",  area="Federalism",      era="Rehnquist Court",  notes="Anti-commandeering doctrine"),
    dict(case="City of Boerne v. Flores",        year=1997, law="Religious Freedom Restoration Act", basis="14th Amendment §5",   area="Religion",        era="Rehnquist Court",  notes="Congress overstepped enforcement power"),
    dict(case="Bush v. Gore",                    year=2000, law="Florida recount statute (state)",   basis="14th Amendment",      area="Elections",       era="Rehnquist Court",  notes="Halted 2000 presidential recount"),
    dict(case="Hamdi v. Rumsfeld",               year=2004, law="AUMF enemy combatant detention",    basis="Due Process",         area="National Security",era="Rehnquist Court",notes="Due process rights for US citizens detained as combatants"),
    dict(case="Gonzales v. Raich",               year=2005, law="(upheld CSA federal drug law)",     basis="Commerce Clause",     area="Commerce",        era="Rehnquist Court",  notes="Upheld federal power over home-grown marijuana"),
    dict(case="Boumediene v. Bush",              year=2008, law="Detainee Treatment Act / Military Commissions Act",basis="Suspension Clause",area="National Security",era="Roberts Court",notes="Guantanamo detainees have habeas corpus rights"),
    dict(case="Citizens United v. FEC",          year=2010, law="BCRA §203 (McCain-Feingold)",       basis="1st Amendment",       area="Campaign Finance", era="Roberts Court",   notes="Corporate political spending protected as speech"),
    dict(case="NFIB v. Sebelius",                year=2012, law="ACA individual mandate (Commerce Clause theory)",basis="Commerce Clause",area="Healthcare",era="Roberts Court",notes="Mandate exceeded commerce power; saved as tax"),
    dict(case="Shelby County v. Holder",         year=2013, law="Voting Rights Act §4(b) coverage formula",basis="14th/15th Amendment",area="Voting Rights",era="Roberts Court",notes="Gutted VRA preclearance requirements"),
    dict(case="Zivotofsky v. Kerry",             year=2015, law="Foreign Relations Authorization Act",basis="Separation of Powers",area="Foreign Affairs",era="Roberts Court",notes="Congress cannot override president's passport authority"),
    dict(case="West Virginia v. EPA",            year=2022, law="Clean Air Act §111(d) EPA authority",basis="Major Questions Doctrine",area="Environment",era="Roberts Court",notes="Major questions doctrine limits broad regulatory authority"),
    dict(case="Biden v. Nebraska",               year=2023, law="HEROES Act student debt cancellation",basis="Major Questions Doctrine",area="Education",era="Roberts Court",notes="Broad student loan relief exceeded statute's scope"),
    dict(case="Loper Bright v. Raimondo",        year=2024, law="Fishery Conservation Act / Chevron deference",basis="APA / Article III",area="Administrative Law",era="Roberts Court",notes="Overruled Chevron; courts now interpret statutes independently"),
]

ERAS_ORDER = ["Pre-New Deal","New Deal Era","Warren Court","Burger Court","Rehnquist Court","Roberts Court"]
BASIS_COLORS = {
    "Commerce Clause":"#E74C3C","1st Amendment":"#E67E22","14th Amendment":"#F39C12",
    "Separation of Powers":"#27AE60","Article III":"#2980B9","5th Amendment":"#9B59B6",
    "10th Amendment":"#7F8C8D","Article I":"#C0392B","Major Questions Doctrine":"#1ABC9C",
    "APA / Article III":"#16A085","Spending Clause":"#D35400","Due Process":"#8E44AD",
    "Suspension Clause":"#2C3E50","14th/15th Amendment":"#6C3483","Article I §2":"#2471A3",
}

# ── Page ─────────────────────────────────────────────────────────────────────

def _page_analytics():
    tab_stats, tab_close, tab_win, tab_congress = st.tabs([
        "📊 Term Statistics", "⚖️ Close Decisions", "🏆 Win Rates", "🏛️ SCOTUS vs. Congress"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: TERM STATISTICS
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_stats:
        st.markdown("High-level statistics about Supreme Court decisions by term.")
        stats_term = st.selectbox("Select Term", get_recent_terms(20), key="stats_term")
        with st.spinner("Loading cases..."):
            stats_cases = get_cases_by_term(stats_term)
        if not stats_cases:
            st.warning("No cases found.")
        else:
            st.metric("Total Cases", len(stats_cases))
            rows_s = []
            for c in stats_cases:
                detail_s = get_case_detail(c.get("href", "")) or c
                rows_s.append({
                    "Case Name": c.get("name", ""),
                    "Issue Area": infer_issue_area(detail_s),
                    "Disposition": infer_disposition(detail_s),
                })
            df_s = pd.DataFrame(rows_s)
            col1_s, col2_s = st.columns(2)
            with col1_s:
                issue_counts_s = df_s["Issue Area"].value_counts().reset_index()
                issue_counts_s.columns = ["Issue Area","Count"]
                fig_s = px.bar(issue_counts_s,x="Count",y="Issue Area",orientation="h",
                                title="Cases by Issue Area",color="Count",color_continuous_scale="Blues")
                fig_s.update_layout(height=400,showlegend=False,coloraxis_showscale=False)
                st.plotly_chart(fig_s)
            with col2_s:
                disp_counts_s = df_s["Disposition"].value_counts().reset_index()
                disp_counts_s.columns = ["Disposition","Count"]
                fig_s2 = px.pie(disp_counts_s,names="Disposition",values="Count",title="Case Dispositions",hole=0.3)
                fig_s2.update_layout(height=400)
                st.plotly_chart(fig_s2)
            st.subheader("Case Listing")
            search_s = st.text_input("Filter by name", key="stats_search")
            filtered_s = df_s[df_s["Case Name"].str.contains(search_s,case=False)] if search_s else df_s
            st.dataframe(filtered_s, height=350, hide_index=True)
            csv_download_button(filtered_s, filename=f"scotus_term_{stats_term}.csv", key="csv_term_stats")

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: CLOSE DECISIONS
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_close:
        st.markdown("Browse every **5-4** and **6-3** Supreme Court ruling, see who was in the majority and dissent, and discover which justices cast the deciding vote most often.")
        available_terms_cd = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))
        with st.form("close_form"):
            col1_cd, col2_cd = st.columns([2,1])
            with col1_cd:
                sel_terms_cd = st.multiselect("Terms to include",available_terms_cd,
                                               default=available_terms_cd[:6],max_selections=15,key="close_terms")
            with col2_cd:
                split_filter_cd = st.multiselect("Vote splits",["5-4","6-3","5-3","6-4","7-2"],
                                                  default=["5-4","6-3"],key="close_splits")
            load_cd = st.form_submit_button("Load Cases", type="primary")

        if load_cd and sel_terms_cd:
            with st.spinner(f"Fetching close decisions for {len(sel_terms_cd)} term(s)…"):
                raw_cd = _an_load_close_decisions(tuple(sorted(sel_terms_cd,reverse=True)))
            st.session_state["close_raw"] = raw_cd
            st.session_state["close_terms_loaded"] = sel_terms_cd

        if "close_raw" not in st.session_state:
            st.info("Select terms above and click **Load Cases**.")
        else:
            raw_cd_data: list[dict] = st.session_state["close_raw"]
            terms_loaded_cd = st.session_state.get("close_terms_loaded",[])
            filtered_cd = [c for c in raw_cd_data if c["split"] in split_filter_cd] if split_filter_cd else raw_cd_data
            if not filtered_cd:
                st.warning("No close decisions found for the selected terms and split filters.")
            else:
                five_four_n = sum(1 for c in filtered_cd if c["split"]=="5-4")
                six_three_n = sum(1 for c in filtered_cd if c["split"]=="6-3")
                st.success(f"Found **{len(filtered_cd)}** close decisions — **{five_four_n}** were 5-4, **{six_three_n}** were 6-3.")

                sub_ov, sub_cases, sub_deciding, sub_issue_cd = st.tabs(["📊 Overview","📋 Case Browser","🎯 Deciding Vote","🏛️ Issue Areas"])

                with sub_ov:
                    split_counts_cd = defaultdict(int)
                    for c in filtered_cd: split_counts_cd[c["split"]] += 1
                    sc_df_cd = pd.DataFrame(list(split_counts_cd.items()),columns=["Split","Count"]).sort_values("Count",ascending=False)
                    col_donut_cd, col_trend_cd = st.columns(2)
                    with col_donut_cd:
                        fig_donut_cd = go.Figure(go.Pie(labels=sc_df_cd["Split"],values=sc_df_cd["Count"],hole=0.45,
                                                         textinfo="label+percent",marker_colors=px.colors.qualitative.Set2))
                        fig_donut_cd.update_layout(title="Split Breakdown",height=320)
                        st.plotly_chart(fig_donut_cd)
                    with col_trend_cd:
                        term_counts_cd: dict = defaultdict(lambda: defaultdict(int))
                        for c in filtered_cd: term_counts_cd[c["term"]][c["split"]] += 1
                        trend_rows_cd = [{"Term":t,"Split":sp,"Count":cnt} for t,splits in sorted(term_counts_cd.items()) for sp,cnt in splits.items()]
                        if trend_rows_cd:
                            fig_trend_cd = px.bar(pd.DataFrame(trend_rows_cd),x="Term",y="Count",color="Split",
                                                   barmode="stack",title="Close Decisions Per Term",
                                                   color_discrete_sequence=px.colors.qualitative.Set2)
                            fig_trend_cd.update_layout(height=320,plot_bgcolor="white",paper_bgcolor="white",xaxis=dict(type="category"))
                            st.plotly_chart(fig_trend_cd)
                    disp_counts_cd = defaultdict(int)
                    for c in filtered_cd:
                        d = c["disposition"].lower()
                        if "affirm" in d: disp_counts_cd["Affirmed"] += 1
                        elif "revers" in d or "vacate" in d: disp_counts_cd["Reversed/Vacated"] += 1
                        elif "remand" in d: disp_counts_cd["Remanded"] += 1
                        else: disp_counts_cd["Other"] += 1
                    st.markdown("**Dispositions in Close Decisions**")
                    disp_cols_cd = st.columns(len(disp_counts_cd))
                    for i, (label, count) in enumerate(sorted(disp_counts_cd.items())):
                        disp_cols_cd[i].metric(label, count)

                with sub_cases:
                    search_cd = st.text_input("Search case name",placeholder="e.g. Biden, Texas, EPA",key="close_search")
                    display_cd = [c for c in filtered_cd if search_cd.lower() in c["case"].lower()] if search_cd else filtered_cd
                    st.markdown(f"*Showing {len(display_cd)} case(s)*")
                    for c in sorted(display_cd,key=lambda x: x["term"],reverse=True):
                        maj_str = " · ".join(c["majority"]) if c["majority"] else "—"
                        dis_str = " · ".join(c["dissent"])  if c["dissent"]  else "—"
                        with st.expander(f"**{c['case']}** ({c['term']})  —  {'🔴' if c['split']=='5-4' else '🟠'} {c['split']}  |  {c['issue_area']}"):
                            col_a_cd, col_b_cd = st.columns(2)
                            with col_a_cd:
                                st.markdown(f"**✅ Majority ({c['majority_count']}):**")
                                for j in c["majority"]:
                                    lean = JUSTICE_LEAN.get(j,"Moderate"); color = LEAN_COLORS.get(lean,"#7F8C8D")
                                    st.markdown(f'<span style="color:{color};font-weight:bold;">■</span> {j}',unsafe_allow_html=True)
                            with col_b_cd:
                                st.markdown(f"**❌ Dissent ({c['dissent_count']}):**")
                                for j in c["dissent"]:
                                    lean = JUSTICE_LEAN.get(j,"Moderate"); color = LEAN_COLORS.get(lean,"#7F8C8D")
                                    st.markdown(f'<span style="color:{color};font-weight:bold;">■</span> {j}',unsafe_allow_html=True)
                            if c["disposition"]: st.markdown(f"**Disposition:** {c['disposition']}")

                with sub_deciding:
                    five_four_only_cd = [c for c in filtered_cd if c["split"]=="5-4"]
                    if not five_four_only_cd:
                        st.info("No 5-4 decisions found.")
                    else:
                        maj_counts_cd: dict[str,int] = defaultdict(int)
                        dis_counts_cd: dict[str,int] = defaultdict(int)
                        total_part_cd: dict[str,int] = defaultdict(int)
                        for c in five_four_only_cd:
                            for j in c["majority"]: maj_counts_cd[j]+=1; total_part_cd[j]+=1
                            for j in c["dissent"]:  dis_counts_cd[j]+=1; total_part_cd[j]+=1
                        dec_rows_cd = []
                        for j,total_j in total_part_cd.items():
                            if total_j < 3: continue
                            maj = maj_counts_cd.get(j,0); dis = dis_counts_cd.get(j,0)
                            dec_rows_cd.append({"Justice":j,"Majority":maj,"Dissent":dis,"Total 5-4 Cases":total_j,
                                                "Majority %":round(maj/total_j*100,1),"Lean":JUSTICE_LEAN.get(j,"Moderate")})
                        if dec_rows_cd:
                            dec_df_cd = pd.DataFrame(dec_rows_cd).sort_values("Majority %",ascending=False)
                            fig_dec_cd = go.Figure()
                            fig_dec_cd.add_trace(go.Bar(name="Majority",x=dec_df_cd["Justice"],y=dec_df_cd["Majority"],
                                                         marker_color=[LEAN_COLORS.get(l,"#7F8C8D") for l in dec_df_cd["Lean"]],
                                                         text=dec_df_cd["Majority %"].apply(lambda v: f"{v:.0f}%"),textposition="outside"))
                            fig_dec_cd.add_trace(go.Bar(name="Dissent",x=dec_df_cd["Justice"],y=dec_df_cd["Dissent"],
                                                         marker_color="rgba(150,150,150,0.4)"))
                            fig_dec_cd.update_layout(barmode="stack",title="5-4 Majority vs. Dissent Count",
                                                      xaxis_tickangle=-30,height=400,plot_bgcolor="white",paper_bgcolor="white")
                            st.plotly_chart(fig_dec_cd)
                            st.dataframe(dec_df_cd[["Justice","Majority","Dissent","Total 5-4 Cases","Majority %"]]
                                         .sort_values("Majority %").reset_index(drop=True)
                                         .style.background_gradient(subset=["Majority %"],cmap="RdYlGn"),
                                         height=320,hide_index=True)
                            csv_download_button(dec_df_cd[["Justice","Majority","Dissent","Total 5-4 Cases","Majority %"]].sort_values("Majority %").reset_index(drop=True), filename="scotus_close_decisions_justices.csv", key="csv_close_dec")

                with sub_issue_cd:
                    issue_split_cd: dict[str,dict[str,int]] = defaultdict(lambda: defaultdict(int))
                    for c in filtered_cd: issue_split_cd[c["issue_area"]][c["split"]] += 1
                    issue_rows_cd = [{"Issue Area":area,"Split":sp,"Count":cnt} for area,splits in issue_split_cd.items() for sp,cnt in splits.items()]
                    if issue_rows_cd:
                        iss_df_cd = pd.DataFrame(issue_rows_cd)
                        total_by_area_cd = iss_df_cd.groupby("Issue Area")["Count"].sum().sort_values(ascending=False)
                        fig_iss_cd = px.bar(iss_df_cd[iss_df_cd["Issue Area"].isin(total_by_area_cd.head(12).index)],
                                            x="Issue Area",y="Count",color="Split",barmode="stack",
                                            title="Top Issue Areas — Close Decisions",
                                            category_orders={"Issue Area":list(total_by_area_cd.head(12).index)},
                                            color_discrete_sequence=px.colors.qualitative.Set2)
                        fig_iss_cd.update_layout(height=400,xaxis_tickangle=-30,plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_iss_cd)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: WIN RATES
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_win:
        st.markdown("Track how the federal government, states, corporations, and individuals fare at the Supreme Court.")
        available_terms_wr = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))
        with st.form("win_form"):
            col1_wr, col2_wr = st.columns([3,1])
            with col1_wr:
                sel_terms_wr = st.multiselect("Terms to include",available_terms_wr,
                                               default=available_terms_wr[:8],max_selections=15,key="win_terms")
            with col2_wr:
                st.markdown("<br>",unsafe_allow_html=True)
                load_wr = st.form_submit_button("Load Data",type="primary")
        if load_wr and sel_terms_wr:
            with st.spinner(f"Fetching case data for {len(sel_terms_wr)} term(s)…"):
                win_rows = _an_load_win_data(tuple(sorted(sel_terms_wr,reverse=True)))
            st.session_state["win_rows"] = win_rows
            st.session_state["win_terms_loaded"] = sel_terms_wr

        if "win_rows" not in st.session_state:
            st.info("Select terms and click **Load Data** to begin.")
        else:
            win_rows_data = st.session_state["win_rows"]
            terms_loaded_wr = st.session_state.get("win_terms_loaded",[])
            if not win_rows_data:
                st.warning("No usable case data found.")
            else:
                df_wr = pd.DataFrame(win_rows_data)
                st.success(f"Analysed **{len(df_wr)}** decided cases across **{min(terms_loaded_wr)}–{max(terms_loaded_wr)}**.")
                party_types_wr = ["Federal Government","State / Local Gov't","Corporation / Org","Individual / Other"]

                sub_ov_wr, sub_vs_wr, sub_trend_wr, sub_issue_wr, sub_sg_wr = st.tabs([
                    "📊 Overall Win Rates","⚔️ Head-to-Head","📈 Trend Over Time","🏛️ By Issue Area","🎙️ Solicitor General"])

                with sub_ov_wr:
                    win_rows_out = []
                    for ptype in party_types_wr:
                        as_pet = df_wr[df_wr["pet_type"]==ptype]; as_res = df_wr[df_wr["res_type"]==ptype]
                        total_pt = len(as_pet)+len(as_res)
                        wins_pt  = len(as_pet[as_pet["winner_side"]=="petitioner"])+len(as_res[as_res["winner_side"]=="respondent"])
                        if total_pt >= 5:
                            win_rows_out.append({"Party Type":ptype,"Total Cases":total_pt,"Wins":wins_pt,
                                                  "Losses":total_pt-wins_pt,"Win Rate %":round(wins_pt/total_pt*100,1)})
                    wr_df = pd.DataFrame(win_rows_out).sort_values("Win Rate %",ascending=False)
                    col_bars_wr, col_metrics_wr = st.columns([2,1])
                    with col_bars_wr:
                        fig_wr2 = go.Figure()
                        fig_wr2.add_trace(go.Bar(x=wr_df["Party Type"],y=wr_df["Win Rate %"],
                                                 marker_color=[PARTY_COLORS.get(p,"#95A5A6") for p in wr_df["Party Type"]],
                                                 text=wr_df["Win Rate %"].apply(lambda v: f"{v:.1f}%"),textposition="outside"))
                        fig_wr2.add_hline(y=50,line_dash="dot",line_color="#95A5A6",annotation_text="50% baseline")
                        fig_wr2.update_layout(title="Overall Win Rate by Party Type",yaxis=dict(title="Win Rate (%)",range=[0,105]),
                                              height=360,plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_wr2)
                    with col_metrics_wr:
                        for _, row in wr_df.iterrows():
                            color = PARTY_COLORS.get(row["Party Type"],"#95A5A6")
                            st.markdown(f'<div style="border-left:4px solid {color};padding:6px 10px;margin-bottom:8px;">'
                                        f'<strong>{row["Party Type"]}</strong><br>{row["Wins"]}W / {row["Losses"]}L<br>'
                                        f'<span style="font-size:1.2em;font-weight:bold;">{row["Win Rate %"]}%</span></div>',
                                        unsafe_allow_html=True)
                    pet_wins_wr = len(df_wr[df_wr["winner_side"]=="petitioner"]); res_wins_wr = len(df_wr)-pet_wins_wr
                    st.divider(); st.subheader("Petitioner vs. Respondent")
                    col_p_wr, col_r_wr = st.columns(2)
                    col_p_wr.metric("Petitioner Win Rate",f"{pet_wins_wr/(pet_wins_wr+res_wins_wr)*100:.1f}%",f"{pet_wins_wr} cases")
                    col_r_wr.metric("Respondent Win Rate",f"{res_wins_wr/(pet_wins_wr+res_wins_wr)*100:.1f}%",f"{res_wins_wr} cases")

                with sub_vs_wr:
                    col1_vs, col2_vs = st.columns(2)
                    with col1_vs: type_a_wr = st.selectbox("Party A (petitioner)",party_types_wr,index=0,key="wr_type_a")
                    with col2_vs: type_b_wr = st.selectbox("Party B (respondent)",party_types_wr,index=3,key="wr_type_b")
                    matchup_wr = df_wr[(df_wr["pet_type"]==type_a_wr)&(df_wr["res_type"]==type_b_wr)]
                    reverse_wr = df_wr[(df_wr["pet_type"]==type_b_wr)&(df_wr["res_type"]==type_a_wr)]
                    for sub_m, pet_l, res_l in [(matchup_wr,type_a_wr,type_b_wr),(reverse_wr,type_b_wr,type_a_wr)]:
                        if not sub_m.empty:
                            pet_wins_m = len(sub_m[sub_m["winner_side"]=="petitioner"]); res_wins_m = len(sub_m)-pet_wins_m
                            st.markdown(f"**{pet_l} (petitioner) vs. {res_l} (respondent)** — {len(sub_m)} cases")
                            c1_vs, c2_vs = st.columns(2)
                            c1_vs.metric(f"{pet_l} wins",pet_wins_m,f"{pet_wins_m/len(sub_m)*100:.1f}%")
                            c2_vs.metric(f"{res_l} wins",res_wins_m,f"{res_wins_m/len(sub_m)*100:.1f}%")
                            with st.expander(f"Sample cases ({min(5,len(sub_m))} shown)"):
                                for _, row in sub_m.head(5).iterrows():
                                    st.markdown(f"- **{row['case']}** ({row['term']}) — {row['disposition']}")
                            st.divider()

                with sub_trend_wr:
                    focus_wr = st.selectbox("Track party type",party_types_wr,key="wr_focus")
                    trend_rows_wr = []
                    for term_yr, grp in df_wr.groupby("term"):
                        as_pet = grp[grp["pet_type"]==focus_wr]; as_res = grp[grp["res_type"]==focus_wr]
                        total_tr = len(as_pet)+len(as_res)
                        wins_tr  = len(as_pet[as_pet["winner_side"]=="petitioner"])+len(as_res[as_res["winner_side"]=="respondent"])
                        if total_tr >= 2: trend_rows_wr.append({"Term":term_yr,"Win Rate %":round(wins_tr/total_tr*100,1),"Cases":total_tr})
                    if trend_rows_wr:
                        trend_df_wr = pd.DataFrame(trend_rows_wr).sort_values("Term")
                        fig_trend_wr = go.Figure()
                        fig_trend_wr.add_trace(go.Scatter(x=trend_df_wr["Term"],y=trend_df_wr["Win Rate %"],
                                                           mode="lines+markers",line=dict(color=PARTY_COLORS.get(focus_wr,"#3498DB"),width=2.5),
                                                           marker=dict(size=trend_df_wr["Cases"].clip(upper=20)*0.8+6),
                                                           text=trend_df_wr["Cases"].apply(lambda n: f"{n} cases"),
                                                           hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<br>%{text}<extra></extra>"))
                        fig_trend_wr.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
                        fig_trend_wr.update_layout(title=f"{focus_wr} — Win Rate Per Term",
                                                   yaxis=dict(title="Win Rate (%)",range=[0,105]),height=360,
                                                   plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_trend_wr)

                with sub_issue_wr:
                    focus2_wr = st.selectbox("Party type",party_types_wr,key="wr_issue_focus")
                    issue_rows_wr = []
                    for area, grp in df_wr.groupby("issue_area"):
                        as_pet = grp[grp["pet_type"]==focus2_wr]; as_res = grp[grp["res_type"]==focus2_wr]
                        total_ia = len(as_pet)+len(as_res)
                        wins_ia  = len(as_pet[as_pet["winner_side"]=="petitioner"])+len(as_res[as_res["winner_side"]=="respondent"])
                        if total_ia >= 3: issue_rows_wr.append({"Issue Area":area,"Win Rate %":round(wins_ia/total_ia*100,1),"Cases":total_ia})
                    if issue_rows_wr:
                        issue_df_wr = pd.DataFrame(issue_rows_wr).sort_values("Win Rate %",ascending=False)
                        color_wr = PARTY_COLORS.get(focus2_wr,"#3498DB")
                        fig_issue_wr = go.Figure(go.Bar(x=issue_df_wr["Issue Area"],y=issue_df_wr["Win Rate %"],
                                                        marker_color=color_wr,opacity=0.8,
                                                        text=issue_df_wr["Cases"].apply(lambda n: f"n={n}"),textposition="outside"))
                        fig_issue_wr.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
                        fig_issue_wr.update_layout(title=f"{focus2_wr} — Win Rate by Issue Area",
                                                   yaxis=dict(title="Win Rate (%)",range=[0,115]),xaxis_tickangle=-35,
                                                   height=420,plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_issue_wr)

                with sub_sg_wr:
                    st.subheader("🎙️ Solicitor General — The 'Tenth Justice'")
                    fed_as_pet_sg = df_wr[df_wr["pet_type"]=="Federal Government"]
                    fed_as_res_sg = df_wr[df_wr["res_type"]=="Federal Government"]
                    fed_wins_sg = len(fed_as_pet_sg[fed_as_pet_sg["winner_side"]=="petitioner"])+len(fed_as_res_sg[fed_as_res_sg["winner_side"]=="respondent"])
                    fed_total_sg = len(fed_as_pet_sg)+len(fed_as_res_sg)
                    if fed_total_sg > 0:
                        col1_sg, col2_sg, col3_sg = st.columns(3)
                        col1_sg.metric("Cases Involving Federal Gov't",fed_total_sg)
                        col2_sg.metric("Federal Gov't Wins",fed_wins_sg)
                        col3_sg.metric("Federal Gov't Win Rate",f"{fed_wins_sg/fed_total_sg*100:.1f}%",delta=f"{fed_wins_sg/fed_total_sg*100-50:.1f}% vs 50%")
                    sg_trend = []
                    for term_yr, grp in df_wr.groupby("term"):
                        p_sg = grp[grp["pet_type"]=="Federal Government"]; r_sg = grp[grp["res_type"]=="Federal Government"]
                        t_sg = len(p_sg)+len(r_sg); w_sg = len(p_sg[p_sg["winner_side"]=="petitioner"])+len(r_sg[r_sg["winner_side"]=="respondent"])
                        if t_sg >= 2: sg_trend.append({"Term":term_yr,"Win Rate %":round(w_sg/t_sg*100,1),"Cases":t_sg})
                    if sg_trend:
                        sg_df_plot = pd.DataFrame(sg_trend).sort_values("Term")
                        fig_sg = px.area(sg_df_plot,x="Term",y="Win Rate %",title="Federal Government Win Rate Per Term",color_discrete_sequence=["#E74C3C"])
                        fig_sg.add_hline(y=50,line_dash="dot",line_color="#BDC3C7",annotation_text="50% baseline")
                        fig_sg.update_layout(height=320,yaxis=dict(range=[0,105]),plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_sg)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 4: SCOTUS VS CONGRESS
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_congress:
        st.markdown(
            "Explore every major instance where the Supreme Court struck down or significantly limited "
            "a federal or state law — from Marbury v. Madison in 1803 to the present day."
        )
        laws_df = pd.DataFrame(LAWS_STRUCK_DOWN)

        # Filters
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            era_sel_cg = st.multiselect("Filter by Era", ERAS_ORDER, default=ERAS_ORDER, key="cg_era")
        with col_f2:
            all_areas_cg = sorted(laws_df["area"].unique())
            area_sel_cg = st.multiselect("Filter by Issue Area", all_areas_cg, default=all_areas_cg, key="cg_area")
        with col_f3:
            all_bases_cg = sorted(laws_df["basis"].unique())
            basis_sel_cg = st.multiselect("Filter by Constitutional Basis", all_bases_cg, default=all_bases_cg, key="cg_basis")

        filtered_cg = laws_df[
            laws_df["era"].isin(era_sel_cg) &
            laws_df["area"].isin(area_sel_cg) &
            laws_df["basis"].isin(basis_sel_cg)
        ]

        m1_cg, m2_cg, m3_cg, m4_cg = st.columns(4)
        m1_cg.metric("Laws Struck Down", len(filtered_cg))
        m2_cg.metric("Constitutional Bases Used", filtered_cg["basis"].nunique())
        m3_cg.metric("Issue Areas", filtered_cg["area"].nunique())
        m4_cg.metric("Eras Covered", filtered_cg["era"].nunique())
        st.divider()

        sub_tl_cg, sub_basis_cg, sub_era_cg, sub_table_cg = st.tabs(["📅 Timeline","⚖️ Constitutional Basis","📊 By Era","📋 Full List"])

        with sub_tl_cg:
            st.subheader("Timeline of Laws Struck Down")
            fig_tl_cg = px.scatter(
                filtered_cg, x="year", y="area",
                color="era", size_max=18,
                hover_name="case",
                hover_data={"year":True,"law":True,"basis":True,"notes":True,"area":False,"era":False},
                title="Federal & State Laws Struck Down by SCOTUS",
                category_orders={"era":ERAS_ORDER},
                color_discrete_sequence=["#2C3E50","#8E44AD","#2980B9","#16A085","#E67E22","#E74C3C"],
            )
            fig_tl_cg.update_traces(marker=dict(size=14,opacity=0.85))
            fig_tl_cg.update_layout(height=520,plot_bgcolor="white",paper_bgcolor="white",
                                      xaxis_title="Year",yaxis_title="",legend_title="Era",
                                      margin=dict(l=20,r=20,t=50,b=40))
            st.plotly_chart(fig_tl_cg)
            st.caption("Each dot is a case where SCOTUS struck down or significantly limited a law. Hover for details.")

        with sub_basis_cg:
            st.subheader("Constitutional Basis for Striking Down Laws")
            basis_counts_cg = filtered_cg["basis"].value_counts().reset_index()
            basis_counts_cg.columns = ["Constitutional Basis","Cases"]
            colors_basis = [BASIS_COLORS.get(b,"#95A5A6") for b in basis_counts_cg["Constitutional Basis"]]
            fig_basis_cg = go.Figure(go.Bar(
                x=basis_counts_cg["Cases"], y=basis_counts_cg["Constitutional Basis"],
                orientation="h", marker_color=colors_basis,
                text=basis_counts_cg["Cases"], textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{x} cases<extra></extra>"))
            fig_basis_cg.update_layout(
                title="How Often Each Constitutional Basis Was Used",
                height=max(300, len(basis_counts_cg)*32),
                xaxis_title="Number of Cases",
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="white",paper_bgcolor="white",
                margin=dict(l=220,r=40,t=40,b=40))
            st.plotly_chart(fig_basis_cg)

            # Treemap of basis by area
            st.subheader("Constitutional Basis × Issue Area")
            cross_cg = filtered_cg.groupby(["basis","area"]).size().reset_index(name="count")
            if not cross_cg.empty:
                fig_tree = px.treemap(cross_cg, path=["basis","area"], values="count",
                                      title="Constitutional Basis → Issue Area (treemap)",
                                      color="count", color_continuous_scale="Blues")
                fig_tree.update_layout(height=420,margin=dict(l=20,r=20,t=50,b=20))
                st.plotly_chart(fig_tree)

        with sub_era_cg:
            st.subheader("How Many Laws Did Each Court Strike Down?")
            era_counts_cg = filtered_cg["era"].value_counts().reset_index()
            era_counts_cg.columns = ["Era","Cases"]
            era_counts_cg["Era"] = pd.Categorical(era_counts_cg["Era"], categories=ERAS_ORDER, ordered=True)
            era_counts_cg = era_counts_cg.sort_values("Era")
            era_colors_cg = ["#2C3E50","#8E44AD","#2980B9","#16A085","#E67E22","#E74C3C"]
            fig_era_cg = go.Figure(go.Bar(
                x=era_counts_cg["Era"], y=era_counts_cg["Cases"],
                marker_color=era_colors_cg[:len(era_counts_cg)],
                text=era_counts_cg["Cases"], textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{y} laws struck down<extra></extra>"))
            fig_era_cg.update_layout(title="Laws Struck Down by Court Era",height=350,
                                      plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-15)
            st.plotly_chart(fig_era_cg)

            # Issue area breakdown by era
            st.subheader("Issue Areas Challenged Across Eras")
            era_issue_cg = filtered_cg.groupby(["era","area"]).size().reset_index(name="count")
            era_issue_cg["era"] = pd.Categorical(era_issue_cg["era"], categories=ERAS_ORDER, ordered=True)
            if not era_issue_cg.empty:
                fig_ea_cg = px.bar(era_issue_cg, x="era", y="count", color="area", barmode="stack",
                                   title="Issue Areas Struck Down by Era",
                                   category_orders={"era":ERAS_ORDER},
                                   color_discrete_sequence=px.colors.qualitative.Alphabet)
                fig_ea_cg.update_layout(height=400,plot_bgcolor="white",paper_bgcolor="white",
                                         xaxis_tickangle=-15,legend=dict(x=1.01,y=1,font=dict(size=9)))
                st.plotly_chart(fig_ea_cg)

        with sub_table_cg:
            st.subheader("Complete List of Laws Struck Down")
            search_cg = st.text_input("Search by case name or law", key="cg_search")
            display_cg = filtered_cg.copy()
            if search_cg:
                display_cg = display_cg[
                    display_cg["case"].str.contains(search_cg, case=False, na=False) |
                    display_cg["law"].str.contains(search_cg, case=False, na=False)
                ]
            for _, row in display_cg.sort_values("year", ascending=False).iterrows():
                basis_color = BASIS_COLORS.get(row["basis"],"#95A5A6")
                with st.expander(f"**{row['case']}** ({row['year']}) — {row['law'][:70]}"):
                    c1_t, c2_t = st.columns([3,1])
                    with c1_t:
                        st.markdown(f"**Law:** {row['law']}")
                        if row["notes"]:
                            st.markdown(f"**Significance:** {row['notes']}")
                    with c2_t:
                        st.markdown(f'<div style="background:{basis_color}22;border-left:4px solid {basis_color};'
                                    f'padding:8px;border-radius:4px;margin-bottom:8px;">'
                                    f'<strong style="color:{basis_color};">{row["basis"]}</strong></div>',
                                    unsafe_allow_html=True)
                        st.markdown(f"**Issue Area:** {row['area']}")
                        st.markdown(f"**Era:** {row['era']}")

def _page_geography():
    tab_state, tab_compare, tab_citation = st.tabs([
        "🗺️ State Impact Map", "📊 Term Comparator", "🔗 Citation Explorer"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: STATE IMPACT MAP
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_state:
        st.markdown(
            "Which states' laws and court decisions are reviewed most by the Supreme Court? "
            "Track how often each state's lower courts are reversed."
        )
        available_terms_geo = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))
        col1_geo, col2_geo = st.columns([2,1])
        with col1_geo:
            terms_sel_geo = st.multiselect("Terms to include", available_terms_geo,
                                            default=available_terms_geo[:10], max_selections=15, key="geo_terms")
        with col2_geo:
            metric_geo = st.selectbox("Map metric", ["Cases Reviewed","Reversal Rate (%)","Affirmance Rate (%)"], key="geo_metric")

        if st.button("Build State Map", type="primary", key="geo_btn"):
            with st.spinner(f"Loading {len(terms_sel_geo)} terms of state-level data…"):
                geo_rows = _geo_load_state_data(tuple(sorted(terms_sel_geo, reverse=True)))
            st.session_state["geo_rows"] = geo_rows
            st.session_state["geo_terms_loaded"] = terms_sel_geo

        if "geo_rows" not in st.session_state:
            st.info("Select terms and click **Build State Map**.")
        else:
            geo_rows_data = st.session_state["geo_rows"]
            if not geo_rows_data:
                st.warning("No state-level data found.")
            else:
                geo_df = pd.DataFrame(geo_rows_data)
                st.success(f"Loaded **{len(geo_df)}** state-court cases across **{geo_df['state'].nunique()}** states.")

                # Aggregate by state
                state_agg = []
                for state, grp in geo_df.groupby("state"):
                    total = len(grp); rev = len(grp[grp["outcome"]=="Reversed/Vacated"]); aff = len(grp[grp["outcome"]=="Affirmed"])
                    state_agg.append({
                        "State": state, "Abbrev": STATE_ABBREV.get(state,state),
                        "Cases Reviewed": total,
                        "Reversed": rev, "Affirmed": aff,
                        "Reversal Rate (%)": round(rev/total*100,1) if total else 0,
                        "Affirmance Rate (%)": round(aff/total*100,1) if total else 0,
                    })
                state_df = pd.DataFrame(state_agg)

                # Choropleth
                fig_choro = px.choropleth(
                    state_df, locations="Abbrev", locationmode="USA-states",
                    color=metric_geo, scope="usa",
                    color_continuous_scale="YlOrRd" if "Reversal" in metric_geo else "Blues",
                    title=f"SCOTUS Review of State Courts — {metric_geo}",
                    hover_name="State",
                    hover_data={"Cases Reviewed":True,"Reversal Rate (%)":True,"Affirmance Rate (%)":True,"Abbrev":False},
                )
                fig_choro.update_layout(height=500, geo_bgcolor="white",
                                         coloraxis_colorbar=dict(title=metric_geo, ticksuffix="%" if "%" in metric_geo else ""))
                st.plotly_chart(fig_choro)

                col_top_geo, col_bot_geo = st.columns(2)
                with col_top_geo:
                    st.markdown("**States Most Reviewed**")
                    top_states = state_df.sort_values("Cases Reviewed", ascending=False).head(10)
                    fig_top = go.Figure(go.Bar(y=top_states["State"],x=top_states["Cases Reviewed"],orientation="h",
                                               marker_color="#3498DB",text=top_states["Cases Reviewed"],textposition="outside"))
                    fig_top.update_layout(height=340,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=130,r=40,t=30,b=30))
                    st.plotly_chart(fig_top)
                with col_bot_geo:
                    st.markdown("**Highest Reversal Rates**")
                    rev_states = state_df[state_df["Cases Reviewed"]>=3].sort_values("Reversal Rate (%)",ascending=False).head(10)
                    fig_rev = go.Figure(go.Bar(y=rev_states["State"],x=rev_states["Reversal Rate (%)"],orientation="h",
                                               marker_color="#E74C3C",text=rev_states["Reversal Rate (%)"].apply(lambda v:f"{v:.0f}%"),
                                               textposition="outside"))
                    fig_rev.update_layout(height=340,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=130,r=40,t=30,b=30))
                    st.plotly_chart(fig_rev)

                st.divider()
                st.subheader("Issue Areas by State")
                state_issue = geo_df.groupby(["state","issue_area"]).size().reset_index(name="count")
                top_states_issue = state_df.nlargest(15,"Cases Reviewed")["State"].tolist()
                state_issue_top = state_issue[state_issue["state"].isin(top_states_issue)]
                fig_si = px.bar(state_issue_top,x="state",y="count",color="issue_area",barmode="stack",
                                title="Issue Areas Sent to SCOTUS — Top 15 States",
                                category_orders={"state":top_states_issue},
                                color_discrete_sequence=px.colors.qualitative.Alphabet)
                fig_si.update_layout(height=420,xaxis_tickangle=-30,plot_bgcolor="white",paper_bgcolor="white",
                                      legend=dict(title="Issue Area",x=1.01,y=1,font=dict(size=9)))
                st.plotly_chart(fig_si)

                st.subheader("State Drilldown")
                sel_state_drill = st.selectbox("Select State",sorted(geo_df["state"].unique()),key="geo_drill")
                state_drill_df = geo_df[geo_df["state"]==sel_state_drill]
                d1,d2,d3 = st.columns(3)
                d1.metric("Cases Reviewed",len(state_drill_df))
                d2.metric("Reversed",(state_drill_df["outcome"]=="Reversed/Vacated").sum())
                d3.metric("Affirmed",(state_drill_df["outcome"]=="Affirmed").sum())
                st.dataframe(state_drill_df[["term","case","lower_court","outcome","issue_area"]]
                             .sort_values("term",ascending=False),height=300)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: TERM-TO-TERM COMPARATOR
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_compare:
        st.markdown("Compare any two SCOTUS terms across 8+ dimensions simultaneously — case volume, issue areas, vote splits, and more.")
        available_terms_cmp = list(range(CURRENT_YEAR-1, 1993,-1))
        col_ta, col_tb = st.columns(2)
        with col_ta: term_a = st.selectbox("Term A", available_terms_cmp, index=4,  format_func=lambda t: f"{t}–{t+1}", key="cmp_ta")
        with col_tb: term_b = st.selectbox("Term B", available_terms_cmp, index=10, format_func=lambda t: f"{t}–{t+1}", key="cmp_tb")

        if term_a == term_b:
            st.warning("Please select two different terms to compare.")
        else:
            if st.button("Compare Terms", type="primary", key="cmp_btn"):
                with st.spinner(f"Loading {term_a}–{term_a+1} term…"):
                    data_a = _geo_load_term_data(term_a)
                with st.spinner(f"Loading {term_b}–{term_b+1} term…"):
                    data_b = _geo_load_term_data(term_b)
                st.session_state["cmp_data_a"] = (term_a, data_a)
                st.session_state["cmp_data_b"] = (term_b, data_b)

            if "cmp_data_a" in st.session_state and "cmp_data_b" in st.session_state:
                loaded_a_yr, data_a = st.session_state["cmp_data_a"]
                loaded_b_yr, data_b = st.session_state["cmp_data_b"]
                df_a = pd.DataFrame(data_a); df_b = pd.DataFrame(data_b)

                label_a = f"{loaded_a_yr}–{loaded_a_yr+1}"; label_b = f"{loaded_b_yr}–{loaded_b_yr+1}"

                def _avg_margin(df):
                    margins = df["margin"].dropna()
                    return round(margins.mean(), 2) if not margins.empty else None

                def _pct_close(df):
                    if df.empty: return 0
                    close = df["margin"].dropna().apply(lambda m: m <= 1).sum()
                    return round(close / len(df) * 100, 1) if len(df) else 0

                def _pct_unanimous(df):
                    if df.empty: return 0
                    unano = df["margin"].dropna().apply(lambda m: m == 9).sum()
                    return round(unano / len(df) * 100, 1) if len(df) else 0

                # Radar chart comparison
                metrics_radar = {
                    "Total Cases":           (len(df_a),                        len(df_b)),
                    "Avg Vote Margin":       (_avg_margin(df_a) or 0,           _avg_margin(df_b) or 0),
                    "% Close (5-4)":         (_pct_close(df_a),                 _pct_close(df_b)),
                    "% Unanimous":           (_pct_unanimous(df_a),             _pct_unanimous(df_b)),
                    "Unique Issue Areas":    (df_a["issue_area"].nunique(),      df_b["issue_area"].nunique()),
                    "Affirm Count":          ((df_a["disposition"].str.lower().str.contains("affirm",na=False)).sum(),
                                              (df_b["disposition"].str.lower().str.contains("affirm",na=False)).sum()),
                    "Reverse Count":         ((df_a["disposition"].str.lower().str.contains("revers|vacat",na=False,regex=True)).sum(),
                                              (df_b["disposition"].str.lower().str.contains("revers|vacat",na=False,regex=True)).sum()),
                }

                # Side-by-side metrics
                st.subheader(f"📊 {label_a} vs. {label_b} — Head to Head")
                metric_cols = st.columns(len(metrics_radar))
                for i, (metric, (val_a, val_b)) in enumerate(metrics_radar.items()):
                    with metric_cols[i % len(metrics_radar)]:
                        delta = None
                        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                            diff = round(val_a - val_b, 2)
                            delta = f"{diff:+.1f}" if diff != 0 else "same"
                        st.metric(metric, f"{val_a:.1f}" if isinstance(val_a, float) else str(val_a),
                                  delta=delta, help=f"{label_b}: {val_b:.1f}" if isinstance(val_b,float) else f"{label_b}: {val_b}")

                st.divider()
                # Radar chart
                cats_radar = list(metrics_radar.keys())
                vals_a_norm = []; vals_b_norm = []
                for k, (va, vb) in metrics_radar.items():
                    mx = max(float(va), float(vb), 1)
                    vals_a_norm.append(float(va) / mx * 100)
                    vals_b_norm.append(float(vb) / mx * 100)
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(r=vals_a_norm+[vals_a_norm[0]], theta=cats_radar+[cats_radar[0]],
                                                     fill="toself", name=label_a, line_color="#3498DB", opacity=0.7))
                fig_radar.add_trace(go.Scatterpolar(r=vals_b_norm+[vals_b_norm[0]], theta=cats_radar+[cats_radar[0]],
                                                     fill="toself", name=label_b, line_color="#E74C3C", opacity=0.7))
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=False,range=[0,110])),
                                         showlegend=True,height=420,margin=dict(l=50,r=50,t=50,b=50))
                st.plotly_chart(fig_radar)

                st.divider()
                sub_issues_cmp, sub_splits_cmp, sub_cases_cmp = st.tabs(["Issue Areas","Vote Splits","Case Lists"])

                with sub_issues_cmp:
                    ia_a = df_a["issue_area"].value_counts().reset_index(); ia_a.columns=["Issue Area","Count"]; ia_a["Term"]=label_a
                    ia_b = df_b["issue_area"].value_counts().reset_index(); ia_b.columns=["Issue Area","Count"]; ia_b["Term"]=label_b
                    ia_combined = pd.concat([ia_a,ia_b])
                    top_ias = ia_combined.groupby("Issue Area")["Count"].sum().sort_values(ascending=False).head(12).index.tolist()
                    ia_filtered = ia_combined[ia_combined["Issue Area"].isin(top_ias)]
                    fig_ia_cmp = px.bar(ia_filtered,x="Issue Area",y="Count",color="Term",barmode="group",
                                         title=f"Issue Areas — {label_a} vs. {label_b}",
                                         color_discrete_map={label_a:"#3498DB",label_b:"#E74C3C"})
                    fig_ia_cmp.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
                    st.plotly_chart(fig_ia_cmp)

                with sub_splits_cmp:
                    split_a = df_a["vote_split"].value_counts().reset_index(); split_a.columns=["Split","Count"]; split_a["Term"]=label_a
                    split_b = df_b["vote_split"].value_counts().reset_index(); split_b.columns=["Split","Count"]; split_b["Term"]=label_b
                    split_combined = pd.concat([split_a[split_a["Split"]!=""],split_b[split_b["Split"]!=""]])
                    top_splits = split_combined.groupby("Split")["Count"].sum().sort_values(ascending=False).head(10).index.tolist()
                    split_filtered = split_combined[split_combined["Split"].isin(top_splits)]
                    fig_split_cmp = px.bar(split_filtered,x="Split",y="Count",color="Term",barmode="group",
                                            title=f"Vote Splits — {label_a} vs. {label_b}",
                                            color_discrete_map={label_a:"#3498DB",label_b:"#E74C3C"})
                    fig_split_cmp.update_layout(height=360,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_split_cmp)

                with sub_cases_cmp:
                    col_ca_list, col_cb_list = st.columns(2)
                    with col_ca_list:
                        st.markdown(f"**{label_a} Cases ({len(df_a)})**")
                        st.dataframe(df_a[["case","issue_area","vote_split","disposition"]].reset_index(drop=True),
                                     height=400)
                    with col_cb_list:
                        st.markdown(f"**{label_b} Cases ({len(df_b)})**")
                        st.dataframe(df_b[["case","issue_area","vote_split","disposition"]].reset_index(drop=True),
                                     height=400)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: CITATION EXPLORER — Cross-court citations
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_citation:
        st.markdown(
            "Explore how SCOTUS decisions are cited across different legal domains. "
            "The most cited cases form the backbone of American constitutional law."
        )

        # Curated citation frequency data (based on Westlaw/CourtListener citation counts)
        MOST_CITED = [
            dict(case="Chevron v. NRDC",              year=1984, citations=15000, domain="Administrative Law",     area="Federal Power",      cites_per_yr=375, post_overruled=True),
            dict(case="New York Times v. Sullivan",    year=1964, citations=11000, domain="First Amendment",        area="Media Law",          cites_per_yr=183, post_overruled=False),
            dict(case="Miranda v. Arizona",            year=1966, citations=10500, domain="Criminal Procedure",     area="All Courts",         cites_per_yr=175, post_overruled=False),
            dict(case="Roe v. Wade",                   year=1973, citations= 9500, domain="Privacy / Abortion",     area="Healthcare",         cites_per_yr=190, post_overruled=True),
            dict(case="Strickland v. Washington",      year=1984, citations= 9200, domain="Criminal Procedure",     area="Ineffective Counsel",cites_per_yr=230, post_overruled=False),
            dict(case="Celotex Corp. v. Catrett",      year=1986, citations= 9000, domain="Civil Procedure",        area="Summary Judgment",   cites_per_yr=237, post_overruled=False),
            dict(case="Anderson v. Liberty Lobby",     year=1986, citations= 8800, domain="Civil Procedure",        area="Summary Judgment",   cites_per_yr=232, post_overruled=False),
            dict(case="Matsushita Electric v. Zenith", year=1986, citations= 8200, domain="Civil Procedure",        area="Antitrust",          cites_per_yr=216, post_overruled=False),
            dict(case="Iqbal v. Ashcroft",             year=2009, citations= 7500, domain="Civil Procedure",        area="Pleading Standards", cites_per_yr=500, post_overruled=False),
            dict(case="Bell Atlantic v. Twombly",      year=2007, citations= 7200, domain="Civil Procedure",        area="Pleading Standards", cites_per_yr=411, post_overruled=False),
            dict(case="Terry v. Ohio",                 year=1968, citations= 6800, domain="Criminal Procedure",     area="Search & Seizure",   cites_per_yr=119, post_overruled=False),
            dict(case="Brandenburg v. Ohio",           year=1969, citations= 5900, domain="First Amendment",        area="Free Speech",        cites_per_yr=102, post_overruled=False),
            dict(case="Batson v. Kentucky",            year=1986, citations= 5800, domain="Criminal Procedure",     area="Jury Selection",     cites_per_yr=153, post_overruled=False),
            dict(case="Daubert v. Merrell Dow Pharma.", year=1993, citations= 5600, domain="Evidence",              area="Expert Testimony",   cites_per_yr=186, post_overruled=False),
            dict(case="Graham v. Connor",              year=1989, citations= 5500, domain="Civil Rights",           area="Police Use of Force",cites_per_yr=157, post_overruled=False),
            dict(case="McDonnell Douglas v. Green",    year=1973, citations= 5400, domain="Employment Law",         area="Title VII",          cites_per_yr=108, post_overruled=False),
            dict(case="Brown v. Board of Education",   year=1954, citations= 5200, domain="Equal Protection",       area="Education",          cites_per_yr=74,  post_overruled=False),
            dict(case="Katz v. United States",         year=1967, citations= 5000, domain="Criminal Procedure",     area="Search & Seizure",   cites_per_yr=86,  post_overruled=False),
            dict(case="District of Columbia v. Heller",year=2008, citations= 4800, domain="Second Amendment",       area="Firearms",           cites_per_yr=300, post_overruled=False),
            dict(case="Monell v. Dept of Social Svcs.", year=1978, citations= 4700, domain="Civil Rights",          area="§1983 Liability",    cites_per_yr=102, post_overruled=False),
            dict(case="Obergefell v. Hodges",          year=2015, citations= 3800, domain="Equal Protection",       area="Marriage Rights",    cites_per_yr=380, post_overruled=False),
            dict(case="Citizens United v. FEC",        year=2010, citations= 3600, domain="First Amendment",        area="Campaign Finance",   cites_per_yr=240, post_overruled=False),
            dict(case="Crawford v. Washington",        year=2004, citations= 3500, domain="Criminal Procedure",     area="Confrontation",      cites_per_yr=175, post_overruled=False),
            dict(case="Twining v. New Jersey (overruled)",year=1908,citations=   0,domain="Historical",             area="Self-Incrimination",  cites_per_yr=0, post_overruled=True),
            dict(case="Dobbs v. Jackson Women's Health",year=2022, citations= 1800, domain="Privacy",               area="Abortion",           cites_per_yr=600, post_overruled=False),
            dict(case="Loper Bright v. Raimondo",      year=2024, citations=  400, domain="Administrative Law",     area="Agency Deference",   cites_per_yr=400, post_overruled=False),
            dict(case="West Virginia v. EPA",          year=2022, citations= 2100, domain="Administrative Law",     area="Regulatory Power",   cites_per_yr=700, post_overruled=False),
        ]
        # Filter out zero-citation placeholders
        MOST_CITED = [c for c in MOST_CITED if c["citations"] > 0]

        cited_df = pd.DataFrame(MOST_CITED)

        # Filters
        col_f1_cite, col_f2_cite = st.columns(2)
        with col_f1_cite:
            domain_filter_cite = st.multiselect("Filter by Legal Domain", sorted(cited_df["domain"].unique()),
                                                  default=sorted(cited_df["domain"].unique()), key="cite_domain")
        with col_f2_cite:
            overruled_filter = st.radio("Include overruled cases", ["All","Still Good Law Only","Overruled Only"],
                                        horizontal=True, key="cite_overruled")

        filtered_cite = cited_df[cited_df["domain"].isin(domain_filter_cite)]
        if overruled_filter == "Still Good Law Only": filtered_cite = filtered_cite[~filtered_cite["post_overruled"]]
        elif overruled_filter == "Overruled Only":     filtered_cite = filtered_cite[filtered_cite["post_overruled"]]

        st.subheader("Most Cited SCOTUS Cases (All Courts)")
        fig_cite = px.scatter(
            filtered_cite, x="year", y="citations",
            size="cites_per_yr", color="domain",
            hover_name="case",
            hover_data={"year":True,"citations":True,"cites_per_yr":True,"area":True,"post_overruled":True,"domain":False},
            title="Most Cited SCOTUS Decisions (bubble size = citations per year since decided)",
            symbol="post_overruled",
            symbol_map={True:"x",False:"circle"},
            labels={"citations":"Total Citations","year":"Year Decided","cites_per_yr":"Citations/Year"},
        )
        fig_cite.update_traces(marker=dict(opacity=0.85))
        fig_cite.update_layout(height=500,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
        st.plotly_chart(fig_cite)
        st.caption("✕ = overruled. Circle size = how many citations per year since decided.")

        st.divider()
        col_bar_cite, col_evo_cite = st.columns(2)
        with col_bar_cite:
            st.subheader("Top Cases by Total Citations")
            top_cite = filtered_cite.sort_values("citations",ascending=True).tail(15)
            fig_bar_cite = go.Figure(go.Bar(
                y=top_cite["case"].apply(lambda s: s[:45]+"…" if len(s)>45 else s),
                x=top_cite["citations"],orientation="h",
                marker_color=["#E74C3C" if r else "#3498DB" for r in top_cite["post_overruled"]],
                text=top_cite["citations"].apply(lambda v: f"{v:,}"),textposition="outside"))
            fig_bar_cite.update_layout(height=480,plot_bgcolor="white",paper_bgcolor="white",
                                        xaxis_title="Total Citations",margin=dict(l=320,r=80,t=30,b=30))
            st.plotly_chart(fig_bar_cite)
            st.caption("🔴 = overruled cases. Note: Roe and Chevron still cited frequently even after being overruled.")
        with col_evo_cite:
            st.subheader("Citation Rate by Domain")
            domain_cite = filtered_cite.groupby("domain").agg({"citations":"sum","cites_per_yr":"mean","case":"count"}).reset_index()
            domain_cite.columns=["Domain","Total Citations","Avg Citations/Year","Cases"]
            domain_cite = domain_cite.sort_values("Total Citations",ascending=False)
            fig_domain = px.bar(domain_cite,x="Domain",y="Total Citations",color="Avg Citations/Year",
                                 title="Citation Volume by Legal Domain",
                                 color_continuous_scale="Blues",text="Cases")
            fig_domain.update_layout(height=480,xaxis_tickangle=-30,plot_bgcolor="white",paper_bgcolor="white",
                                      coloraxis_colorbar=dict(title="Avg Cites/Year"))
            st.plotly_chart(fig_domain)

        st.divider()
        st.subheader("Post-Overruling Citation Persistence")
        st.markdown("Even after a case is overruled, its citation count reflects the legal legacy it left behind:")
        overruled_cases = cited_df[cited_df["post_overruled"]].sort_values("citations",ascending=False)
        for _, row in overruled_cases.iterrows():
            yrs_since = CURRENT_YEAR - row["year"]
            st.markdown(
                f'<div style="border-left:4px solid #E74C3C;padding:8px 14px;margin:6px 0;background:#FFF5F5;border-radius:0 4px 4px 0;">'
                f'<strong>{row["case"]}</strong> ({row["year"]}) — <span style="color:#E74C3C;">Overruled</span><br>'
                f'{row["citations"]:,} total citations over {yrs_since} years '
                f'({row["cites_per_yr"]:.0f}/year) in <em>{row["domain"]}</em></div>',
                unsafe_allow_html=True)

# ── Page ─────────────────────────────────────────────────────────────────────
_page_analytics()
