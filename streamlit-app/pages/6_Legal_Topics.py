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
from utils.charts import build_journey_diagram, build_voting_chart
from utils.oyez_api import extract_court_journey

st.set_page_config(page_title="Legal Topics Hub", page_icon="📚", layout="wide")

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

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
                fig_pie_ia.update_layout(height=330); st.plotly_chart(fig_pie_ia,use_container_width=True)
            with col_trend_ia:
                term_counts_ia = df_ia.groupby("Term").size().reset_index(name="Cases")
                fig_trend_ia = px.bar(term_counts_ia.sort_values("Term"),x="Term",y="Cases",
                                      title=f"{issue_ia} — Cases per Term",color="Cases",color_continuous_scale="Blues")
                fig_trend_ia.update_layout(height=330,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                st.plotly_chart(fig_trend_ia,use_container_width=True)
            st.subheader("Case List")
            disp_filter_ia = st.multiselect("Filter by Disposition",sorted(df_ia["Disposition"].unique()),default=[],key="ia_disp_filter")
            display_ia = df_ia[df_ia["Disposition"].isin(disp_filter_ia)] if disp_filter_ia else df_ia
            display_ia = display_ia[["Term","Case","Disposition"]].sort_values("Term",ascending=False)
            st.dataframe(display_ia,use_container_width=True,height=400)
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
    AMENDMENTS = {
        "1st Amendment — Free Speech, Press, Religion, Assembly": {
            "summary":"Prohibits Congress from abridging freedom of speech, press, religion, or peaceful assembly.",
            "color":"#2980B9",
            "cases":[
                ("Schenck v. United States (1919)","https://api.oyez.org/cases/1900-1940/249us47","Upheld conviction for anti-draft pamphlets; established 'clear and present danger' test.",1919),
                ("New York Times v. Sullivan (1964)","https://api.oyez.org/cases/1963/39","Required 'actual malice' for defamation claims by public officials.",1964),
                ("Brandenburg v. Ohio (1969)","https://api.oyez.org/cases/1968/492","Protected inflammatory speech unless directed to incite imminent lawless action.",1969),
                ("Texas v. Johnson (1989)","https://api.oyez.org/cases/1988/88-155","Flag burning is protected symbolic speech under the First Amendment.",1989),
                ("Citizens United v. FEC (2010)","https://api.oyez.org/cases/2008/08-205","Corporate political spending is protected speech; struck down campaign finance limits.",2010),
                ("Snyder v. Phelps (2011)","https://api.oyez.org/cases/2010/09-751","Protected Westboro Baptist Church's anti-gay funeral protests as public concern speech.",2011),
            ]},
        "2nd Amendment — Right to Bear Arms": {
            "summary":"Protects the individual right to keep and bear arms.",
            "color":"#8E44AD",
            "cases":[
                ("District of Columbia v. Heller (2008)","https://api.oyez.org/cases/2007/07-290","Recognized an individual's right to possess firearms independent of militia service.",2008),
                ("McDonald v. City of Chicago (2010)","https://api.oyez.org/cases/2009/08-1521","Incorporated the Second Amendment against state and local governments.",2010),
                ("New York State Rifle & Pistol Assn. v. Bruen (2022)","https://api.oyez.org/cases/2021/20-843","Struck down NY's 'proper cause' requirement for concealed carry permits.",2022),
            ]},
        "4th Amendment — Search & Seizure": {
            "summary":"Guards against unreasonable searches and seizures; requires warrants based on probable cause.",
            "color":"#E67E22",
            "cases":[
                ("Mapp v. Ohio (1961)","https://api.oyez.org/cases/1960/236","Applied the exclusionary rule to the states — illegally seized evidence inadmissible.",1961),
                ("Katz v. United States (1967)","https://api.oyez.org/cases/1967/35","Extended 4th Amendment to electronic surveillance; created 'reasonable expectation of privacy'.",1967),
                ("Terry v. Ohio (1968)","https://api.oyez.org/cases/1967/67","Permitted police 'stop and frisk' based on reasonable suspicion, not full probable cause.",1968),
                ("United States v. Jones (2012)","https://api.oyez.org/cases/2011/10-1259","Attaching a GPS device to a vehicle constitutes a search under the 4th Amendment.",2012),
                ("Riley v. California (2014)","https://api.oyez.org/cases/2013/13-132","Police must obtain a warrant before searching a cell phone incident to arrest.",2014),
                ("Carpenter v. United States (2018)","https://api.oyez.org/cases/2017/16-402","Government needs a warrant to access historical cell-site location information.",2018),
            ]},
        "5th Amendment — Due Process, Self-Incrimination": {
            "summary":"Prohibits double jeopardy, self-incrimination, and deprivation of life/liberty/property without due process.",
            "color":"#C0392B",
            "cases":[
                ("Miranda v. Arizona (1966)","https://api.oyez.org/cases/1965/759","Police must inform suspects of their rights before custodial interrogation.",1966),
                ("Kelo v. City of New London (2005)","https://api.oyez.org/cases/2004/04-108","Upheld government's use of eminent domain for economic development (takings clause).",2005),
            ]},
        "6th Amendment — Right to Counsel & Fair Trial": {
            "summary":"Guarantees the right to a speedy trial, impartial jury, and assistance of counsel.",
            "color":"#27AE60",
            "cases":[
                ("Gideon v. Wainwright (1963)","https://api.oyez.org/cases/1962/155","States must provide counsel to criminal defendants who cannot afford an attorney.",1963),
                ("Crawford v. Washington (2004)","https://api.oyez.org/cases/2003/02-9410","Testimonial statements of absent witnesses are inadmissible unless defendant had prior cross-examination.",2004),
            ]},
        "8th Amendment — Cruel & Unusual Punishment": {
            "summary":"Prohibits excessive bail, excessive fines, and cruel and unusual punishment.",
            "color":"#E74C3C",
            "cases":[
                ("Furman v. Georgia (1972)","https://api.oyez.org/cases/1971/69-5003","Struck down existing death penalty statutes as arbitrary and therefore unconstitutional.",1972),
                ("Gregg v. Georgia (1976)","https://api.oyez.org/cases/1975/74-6257","Upheld revised death penalty statutes with guided discretion.",1976),
                ("Atkins v. Virginia (2002)","https://api.oyez.org/cases/2001/00-8452","Executing intellectually disabled persons is unconstitutional.",2002),
                ("Roper v. Simmons (2005)","https://api.oyez.org/cases/2004/03-633","Death penalty for crimes committed while under 18 is unconstitutional.",2005),
            ]},
        "14th Amendment — Equal Protection & Due Process": {
            "summary":"Grants citizenship, equal protection, and due process rights.",
            "color":"#F39C12",
            "cases":[
                ("Brown v. Board of Education (1954)","https://api.oyez.org/cases/1953/1","Racial segregation in public schools is unconstitutional under equal protection.",1954),
                ("Loving v. Virginia (1967)","https://api.oyez.org/cases/1966/395","Laws prohibiting interracial marriage violate the Equal Protection and Due Process Clauses.",1967),
                ("Roe v. Wade (1973)","https://api.oyez.org/cases/1971/70-18","Recognized a woman's right to abortion under the Due Process Clause.",1973),
                ("Grutter v. Bollinger (2003)","https://api.oyez.org/cases/2002/02-241","Upheld race-conscious admissions at University of Michigan Law School.",2003),
                ("Obergefell v. Hodges (2015)","https://api.oyez.org/cases/2014/14-556","Same-sex couples have a fundamental right to marry under the 14th Amendment.",2015),
                ("Dobbs v. Jackson Women's Health (2022)","https://api.oyez.org/cases/2021/19-1392","Overturned Roe v. Wade; the Constitution does not confer a right to abortion.",2022),
                ("Students for Fair Admissions v. Harvard (2023)","https://api.oyez.org/cases/2022/20-1199","Race-conscious admissions programs at Harvard and UNC are unconstitutional.",2023),
            ]},
    }

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
    st.subheader("Case Timeline"); st.plotly_chart(fig_tl_amend,use_container_width=True)
    st.divider(); st.subheader("Key Cases")
    for i, (name, href, holding, year) in enumerate(cases_amend):
        with st.expander(f"**{name}** — {holding[:80]}{'…' if len(holding)>80 else ''}"):
            st.markdown(f"**Holding:** {holding}"); st.markdown(f"**Year:** {year}")
            col_load_amend, _ = st.columns([1,3])
            with col_load_amend:
                load_key_amend = f"load_amend_{amendment_sel}_{i}"
                if st.button("Load Full Details", key=load_key_amend):
                    st.session_state[f"detail_amend_{amendment_sel}_{i}"] = _lt_fetch_case(href)
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
                    if fig_v_am: st.plotly_chart(fig_v_am,use_container_width=True)
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
    st.plotly_chart(fig_overview_amend,use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: CONSTITUTIONAL PROVISIONS TRACKER
# ──────────────────────────────────────────────────────────────────────────────
with tab_provisions:
    PROVISIONS = [
        ("free_speech","Free Speech","First Amendment — Freedom of Speech & Press","Amendment I","#E74C3C"),
        ("establishment","Establishment Clause","First Amendment — Establishment of Religion","Amendment I","#E67E22"),
        ("free_exercise","Free Exercise","First Amendment — Free Exercise of Religion","Amendment I","#F39C12"),
        ("search_seizure","Search & Seizure","Fourth Amendment — Unreasonable Searches & Seizures","Amendment IV","#27AE60"),
        ("self_incrim","Self-Incrimination","Fifth Amendment — Right Against Self-Incrimination","Amendment V","#1ABC9C"),
        ("due_process_5","Due Process (5th)","Fifth Amendment — Due Process of Law","Amendment V","#16A085"),
        ("takings","Takings Clause","Fifth Amendment — Just Compensation / Takings","Amendment V","#2ECC71"),
        ("right_counsel","Right to Counsel","Sixth Amendment — Right to Counsel","Amendment VI","#3498DB"),
        ("confrontation","Confrontation","Sixth Amendment — Confrontation Clause","Amendment VI","#2980B9"),
        ("cruel_unusual","Cruel & Unusual","Eighth Amendment — Cruel and Unusual Punishment","Amendment VIII","#9B59B6"),
        ("equal_prot","Equal Protection","Fourteenth Amendment — Equal Protection Clause","Amendment XIV","#8E44AD"),
        ("due_process_14","Due Process (14th)","Fourteenth Amendment — Due Process / Incorporation","Amendment XIV","#6C3483"),
        ("second_amend","Second Amendment","Second Amendment — Right to Keep and Bear Arms","Amendment II","#D35400"),
        ("commerce","Commerce Clause","Article I, § 8 — Commerce Clause","Article I","#C0392B"),
        ("spending","Spending Clause","Article I, § 8 — Spending Clause","Article I","#E74C3C"),
        ("tenth_amend","Tenth Amendment","Tenth Amendment — Reserved Powers / Federalism","Amendment X","#7F8C8D"),
        ("eleventh_amend","Eleventh Amendment","Eleventh Amendment — State Sovereign Immunity","Amendment XI","#95A5A6"),
        ("free_press","Freedom of Press","First Amendment — Freedom of Press","Amendment I","#E74C3C"),
    ]
    PROV_MAP = {p[0]:p for p in PROVISIONS}

    LANDMARK_CASES_PROV = [
        ("Schenck v. United States",1919,["free_speech"],"Clear and present danger test upheld speech restrictions during wartime.",3),
        ("Brandenburg v. Ohio",1969,["free_speech"],"Imminent lawless action test replaced clear and present danger.",5),
        ("Texas v. Johnson",1989,["free_speech"],"Flag burning is protected symbolic speech.",5),
        ("Citizens United v. FEC",2010,["free_speech"],"Political spending by corporations is protected speech.",5),
        ("Snyder v. Phelps",2011,["free_speech"],"Westboro Baptist Church protests near military funerals are protected.",4),
        ("303 Creative v. Elenis",2023,["free_speech","equal_prot"],"Designer cannot be compelled to create websites for same-sex weddings.",4),
        ("Engel v. Vitale",1962,["establishment"],"School-sponsored prayer violates Establishment Clause.",5),
        ("Lemon v. Kurtzman",1971,["establishment"],"Three-part Lemon test established for Establishment Clause cases.",5),
        ("Kennedy v. Bremerton School District",2022,["establishment","free_exercise"],"Public school coach's personal prayer on field is protected.",5),
        ("Employment Division v. Smith",1990,["free_exercise"],"Neutral, generally applicable laws may burden religion without exemption.",5),
        ("Burwell v. Hobby Lobby",2014,["free_exercise"],"Closely-held corporations may claim religious exemptions under RFRA.",5),
        ("Mapp v. Ohio",1961,["search_seizure"],"Exclusionary rule applies to states via 14th Amendment.",5),
        ("Katz v. United States",1967,["search_seizure"],"Wiretapping phone booth requires warrant; reasonable expectation of privacy.",5),
        ("Terry v. Ohio",1968,["search_seizure"],"Stop-and-frisk constitutional under reasonable suspicion standard.",5),
        ("Riley v. California",2014,["search_seizure"],"Police must get warrant to search cell phone contents after arrest.",5),
        ("Carpenter v. United States",2018,["search_seizure"],"Warrant required for historical cell-site location information.",5),
        ("Miranda v. Arizona",1966,["self_incrim","due_process_5"],"Police must inform suspects of rights before custodial interrogation.",5),
        ("Kelo v. City of New London",2005,["takings"],"Economic development qualifies as public use under Takings Clause.",5),
        ("Gideon v. Wainwright",1963,["right_counsel"],"Right to counsel incorporated against states via 14th Amendment.",5),
        ("Crawford v. Washington",2004,["confrontation"],"Testimonial statements of absent witnesses require prior cross-examination.",5),
        ("Furman v. Georgia",1972,["cruel_unusual"],"Death penalty as then applied was unconstitutional.",5),
        ("Gregg v. Georgia",1976,["cruel_unusual"],"Death penalty itself is not per se unconstitutional.",5),
        ("Atkins v. Virginia",2002,["cruel_unusual"],"Executing intellectually disabled persons is unconstitutional.",5),
        ("Roper v. Simmons",2005,["cruel_unusual"],"Executing juvenile offenders violates Eighth Amendment.",5),
        ("Brown v. Board of Education",1954,["equal_prot"],"Racial segregation in public schools is unconstitutional.",5),
        ("Loving v. Virginia",1967,["equal_prot","due_process_14"],"Anti-miscegenation laws violate Equal Protection and Due Process.",5),
        ("Grutter v. Bollinger",2003,["equal_prot"],"Race may be a factor in university admissions to achieve diversity.",5),
        ("SFFA v. Harvard",2023,["equal_prot"],"Race-conscious admissions programs at Harvard and UNC unconstitutional.",5),
        ("Obergefell v. Hodges",2015,["equal_prot","due_process_14"],"Same-sex couples have fundamental right to marry.",5),
        ("Griswold v. Connecticut",1965,["due_process_14"],"Right to marital privacy for contraceptives implied by Bill of Rights.",5),
        ("Roe v. Wade",1973,["due_process_14"],"Abortion is protected under right to privacy.",5),
        ("Lawrence v. Texas",2003,["due_process_14"],"State sodomy laws violate Due Process liberty interest.",5),
        ("Dobbs v. Jackson Women's Health",2022,["due_process_14"],"Constitution does not confer right to abortion; Roe overruled.",5),
        ("DC v. Heller",2008,["second_amend"],"Second Amendment protects individual right to keep firearms at home.",5),
        ("McDonald v. City of Chicago",2010,["second_amend"],"Second Amendment incorporated against states via 14th Amendment.",5),
        ("NY State Rifle & Pistol v. Bruen",2022,["second_amend"],"Historical tradition test replaces means-ends scrutiny.",5),
        ("Wickard v. Filburn",1942,["commerce"],"Growing wheat for personal use affects interstate commerce.",5),
        ("Lopez v. United States",1995,["commerce"],"Gun-Free School Zones Act exceeds commerce power; first limit in 60 years.",5),
        ("NFIB v. Sebelius",2012,["commerce","spending"],"ACA individual mandate exceeds commerce power; upheld as tax.",5),
        ("West Virginia v. EPA",2022,["commerce"],"Major questions doctrine limits EPA's broad regulatory authority.",5),
        ("Loper Bright v. Raimondo",2024,["commerce"],"Chevron deference overruled; courts interpret statutes independently.",5),
        ("McCulloch v. Maryland",1819,["tenth_amend","commerce"],"Necessary and Proper Clause gives Congress implied powers.",5),
        ("Printz v. United States",1997,["tenth_amend"],"Federal government cannot commandeer state executive officers.",5),
    ]

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
            st.plotly_chart(fig_bar_pv,use_container_width=True)
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
        st.subheader("Cases per Amendment"); st.plotly_chart(fig_donut_pv,use_container_width=True)

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
                st.markdown(f'<div style="border-left:3px solid {sig_color_pv};padding:6px 12px;margin-bottom:6px;">'
                             f'<strong>{case_pv[0]}</strong> ({case_pv[1]}) <span style="color:{sig_color_pv}">{stars_fn(case_pv[4])}</span>'
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
            st.plotly_chart(fig_tl_pv,use_container_width=True)
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
    LANDMARK_CASES_LT = {
        "Free Speech & Press": [
            ("New York Times v. Sullivan (1964)","https://api.oyez.org/cases/1963/39","Established 'actual malice' standard for defamation of public officials."),
            ("Brandenburg v. Ohio (1969)","https://api.oyez.org/cases/1968/492","Protected inflammatory speech unless it incites imminent lawless action."),
            ("Snyder v. Phelps (2011)","https://api.oyez.org/cases/2010/09-751","Protected Westboro Baptist Church's funeral protests as free speech."),
        ],
        "Privacy & Civil Liberties": [
            ("Griswold v. Connecticut (1965)","https://api.oyez.org/cases/1964/496","Recognized a constitutional right to marital privacy."),
            ("Roe v. Wade (1973)","https://api.oyez.org/cases/1971/70-18","Recognized a woman's constitutional right to abortion."),
            ("Dobbs v. Jackson Women's Health (2022)","https://api.oyez.org/cases/2021/19-1392","Overturned Roe v. Wade; returned abortion regulation to the states."),
        ],
        "Equal Protection & Civil Rights": [
            ("Brown v. Board of Education (1954)","https://api.oyez.org/cases/1953/1","Declared racial segregation in public schools unconstitutional."),
            ("Loving v. Virginia (1967)","https://api.oyez.org/cases/1966/395","Struck down laws prohibiting interracial marriage."),
            ("Obergefell v. Hodges (2015)","https://api.oyez.org/cases/2014/14-556","Recognized same-sex couples' constitutional right to marry."),
        ],
        "Criminal Procedure": [
            ("Miranda v. Arizona (1966)","https://api.oyez.org/cases/1965/759","Required police to inform suspects of their rights before interrogation."),
            ("Mapp v. Ohio (1961)","https://api.oyez.org/cases/1960/236","Applied the exclusionary rule to the states."),
            ("Gideon v. Wainwright (1963)","https://api.oyez.org/cases/1962/155","Guaranteed the right to counsel in all felony criminal cases."),
        ],
        "Government Powers & Federalism": [
            ("Marbury v. Madison (1803)","https://api.oyez.org/cases/1789-1850/5us137","Established the principle of judicial review."),
            ("McCulloch v. Maryland (1819)","https://api.oyez.org/cases/1789-1850/17us316","Affirmed Congress's implied powers and federal supremacy over states."),
            ("Citizens United v. FEC (2010)","https://api.oyez.org/cases/2008/08-205","Ruled political spending by corporations is protected free speech."),
        ],
        "Search & Seizure": [
            ("Katz v. United States (1967)","https://api.oyez.org/cases/1967/35","Extended Fourth Amendment protections to electronic surveillance."),
            ("Riley v. California (2014)","https://api.oyez.org/cases/2013/13-132","Required police to get a warrant before searching a cell phone."),
            ("Carpenter v. United States (2018)","https://api.oyez.org/cases/2017/16-402","Required warrants for cell-site location data."),
        ],
    }

    st.markdown("A curated collection of landmark Supreme Court rulings — select any case for full details, votes, and court journey.")
    category_lt = st.selectbox("Legal Category", list(LANDMARK_CASES_LT.keys()), key="lm_cat")
    cases_in_cat_lt = LANDMARK_CASES_LT[category_lt]
    case_options_lt = [c[0] for c in cases_in_cat_lt]
    selected_label_lt = st.selectbox("Select a Landmark Case", case_options_lt, key="lm_case")
    selected_lt = next(c for c in cases_in_cat_lt if c[0]==selected_label_lt)
    case_name_lt, case_href_lt, significance_lt = selected_lt
    st.info(f"**Why it matters:** {significance_lt}")

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
            if fig_lt: st.plotly_chart(fig_lt,use_container_width=True)
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
            if fig2_lt: st.plotly_chart(fig2_lt,use_container_width=True)
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
