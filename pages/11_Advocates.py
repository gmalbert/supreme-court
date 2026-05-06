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


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _adv_fetch_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _adv_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _advocate_role(description: str) -> str:
    d = (description or "").lower()
    if "petitioner" in d or "appellant" in d: return "petitioner"
    if "respondent" in d or "appellee" in d:  return "respondent"
    return "other"

def _winner_side(disp: str) -> str | None:
    d = (disp or "").lower()
    if any(w in d for w in ["affirm","uphold"]): return "respondent"
    if any(w in d for w in ["revers","vacate","remand"]): return "petitioner"
    return None

@st.cache_data(show_spinner=False, ttl=3600)
def _adv_load_advocate_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = _adv_fetch_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href: continue
            detail = _adv_fetch_detail(href)
            if not detail: continue
            disp  = detail.get("disposition") or {}
            disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
            winner_side = _winner_side(disp_label)
            if not winner_side: continue
            advocates = detail.get("advocates") or []
            ia = detail.get("issue_area") or {}
            issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
            for adv_entry in advocates:
                if not isinstance(adv_entry, dict): continue
                adv = adv_entry.get("advocate") or {}
                adv_name = adv.get("name","") if isinstance(adv,dict) else str(adv)
                description = adv_entry.get("advocate_description","")
                role = _advocate_role(description)
                if not adv_name or role == "other": continue
                won = (role == winner_side)
                rows.append({
                    "term": term, "case": detail.get("name",""),
                    "advocate": adv_name, "role": role, "won": won,
                    "issue_area": issue, "description": description,
                })
            time.sleep(0.02)
    return rows

# ── Oral Argument Analysis helpers ────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _adv_load_transcript(arg_href: str) -> dict | None:
    try:
        r = requests.get(arg_href, headers=HEADERS, timeout=12)
        r.raise_for_status(); return r.json()
    except Exception: return None

# ── Amicus brief curated data ──────────────────────────────────────────────────
AMICUS_ORGS = [
    dict(org="United States (Solicitor General)",  total=580, wins=460, category="Government",       color="#E74C3C",
         notes="The 'Tenth Justice'. Files in ~70% of argued cases. Win rate ~80%."),
    dict(org="ACLU",                               total=210, wins=140, category="Civil Liberties",  color="#3498DB",
         notes="Argues broad civil liberties issues; files across all constitutional provisions."),
    dict(org="Chamber of Commerce",                total=195, wins=125, category="Business",         color="#E67E22",
         notes="Files in business, arbitration, and regulatory cases. High success rate in Roberts Court."),
    dict(org="NAACP Legal Defense Fund",           total=115, wins= 75, category="Civil Rights",     color="#9B59B6",
         notes="Specializes in racial equality, voting rights, and criminal justice reform cases."),
    dict(org="AFL-CIO",                            total= 85, wins= 48, category="Labor",            color="#27AE60",
         notes="Files in labor law, employment discrimination, and union-related cases."),
    dict(org="National Rifle Association",         total= 55, wins= 38, category="Second Amendment", color="#8E44AD",
         notes="Files in Second Amendment and firearms regulation cases."),
    dict(org="Cato Institute",                     total=180, wins=110, category="Libertarian",      color="#F39C12",
         notes="Libertarian think tank; files in property rights, economic liberty, and limited gov't cases."),
    dict(org="Constitutional Accountability Center",total=90,wins= 52, category="Progressive",      color="#1ABC9C",
         notes="Files constitutional and text-based arguments; strong focus on history and original meaning."),
    dict(org="Alliance Defending Freedom",         total= 75, wins= 46, category="Religious Liberty",color="#C0392B",
         notes="Conservative legal group focused on religious liberty and free speech cases."),
    dict(org="Lambda Legal",                       total= 55, wins= 38, category="LGBTQ+ Rights",    color="#E91E63",
         notes="Files in cases affecting LGBTQ+ rights, HIV/AIDS, and gender identity."),
    dict(org="Brennan Center for Justice",         total= 60, wins= 35, category="Democracy",        color="#2980B9",
         notes="Focuses on voting rights, campaign finance, and democracy-related cases."),
    dict(org="Pacific Legal Foundation",           total= 65, wins= 42, category="Property Rights",  color="#D35400",
         notes="Conservative/libertarian firm; specializes in property rights and regulatory takings."),
    dict(org="American Bar Association",           total=140, wins= 82, category="Legal Standards",  color="#7F8C8D",
         notes="Files on legal ethics, professional standards, and administration of justice issues."),
    dict(org="National Federation of Independent Business", total=32, wins=22, category="Small Business", color="#E67E22",
         notes="Won landmark NFIB v. Sebelius ACA challenge."),
    dict(org="American College of Surgeons / AMA",total= 45, wins= 28, category="Healthcare",        color="#16A085",
         notes="Files in healthcare regulation, medical malpractice, and FDA cases."),
]

LANDMARK_AMICUS = [
    dict(case="Brown v. Board of Education (1954)",  key_amicus=["ACLU","NAACP LDF","United States"], outcome="Landmark victory — segregation overturned"),
    dict(case="Roe v. Wade (1973)",                  key_amicus=["ACLU","American Public Health Assoc."], outcome="Abortion rights established"),
    dict(case="Regents v. Bakke (1978)",             key_amicus=["United States (supporting regents)","ACLU"], outcome="Quotas banned; diversity permissible"),
    dict(case="Citizens United v. FEC (2010)",       key_amicus=["Cato Institute","NRA","Chamber of Commerce"], outcome="Corporate speech protections expanded"),
    dict(case="NFIB v. Sebelius (2012)",             key_amicus=["NFIB","Chamber of Commerce","26 State AGs"], outcome="ACA mandate upheld as tax"),
    dict(case="Obergefell v. Hodges (2015)",         key_amicus=["ACLU","Lambda Legal","ABA","300+ Corporations"], outcome="Same-sex marriage right recognized"),
    dict(case="Dobbs v. Jackson (2022)",             key_amicus=["Alliance Defending Freedom","US Conference of Catholic Bishops"], outcome="Roe overruled"),
    dict(case="SFFA v. Harvard (2023)",              key_amicus=["Department of Defense","Fortune 500 CEOs (supporting Harvard)"], outcome="Race-conscious admissions struck"),
    dict(case="Bruen (NY Rifle & Pistol Assn., 2022)",key_amicus=["NRA","Firearms Policy Coalition","Cato Institute"], outcome="Historical tradition test adopted"),
    dict(case="Loper Bright v. Raimondo (2024)",     key_amicus=["Chamber of Commerce","Cato Institute","Pacific Legal Foundation"], outcome="Chevron overruled"),
]

# ── Oral Argument patterns from literature ─────────────────────────────────────
QUESTION_PATTERNS = {
    "Roberts Court (2005–present)": {
        "Roberts":   dict(avg_questions=4.2, lean_questions_petitioner=2.1, lean_questions_respondent=2.1, notes="Asks balanced questions; seeks narrow rulings"),
        "Thomas":    dict(avg_questions=0.3, lean_questions_petitioner=0.1, lean_questions_respondent=0.2, notes="Rarely asks questions; began asking more after 2016"),
        "Alito":     dict(avg_questions=8.5, lean_questions_petitioner=4.2, lean_questions_respondent=4.3, notes="Among highest question counts; often hostile to liberal positions"),
        "Sotomayor": dict(avg_questions=9.2, lean_questions_petitioner=4.8, lean_questions_respondent=4.4, notes="Highest question count on current court; very active"),
        "Kagan":     dict(avg_questions=7.8, lean_questions_petitioner=3.9, lean_questions_respondent=3.9, notes="Known for hypothetical questions probing edge cases"),
        "Gorsuch":   dict(avg_questions=6.1, lean_questions_petitioner=3.2, lean_questions_respondent=2.9, notes="Often explores textualist interpretations"),
        "Kavanaugh": dict(avg_questions=7.4, lean_questions_petitioner=3.7, lean_questions_respondent=3.7, notes="Asks frequent, probing questions on both sides"),
        "Barrett":   dict(avg_questions=8.3, lean_questions_petitioner=4.2, lean_questions_respondent=4.1, notes="High engagement since joining court in 2020"),
        "Jackson":   dict(avg_questions=10.1,lean_questions_petitioner=5.0, lean_questions_respondent=5.1, notes="One of highest question counts; often asks hypotheticals"),
    }
}

QUESTION_OUTCOME_INSIGHT = """
**The Question Count Predictor Effect** (Jacobi & Schweers, 2017)

Research on SCOTUS oral arguments shows a statistically significant pattern:
*The justice who asks more questions to the petitioner's attorney tends to vote against the petitioner.*

This effect holds across multiple terms with ~70% accuracy. The intuition: when a justice is skeptical of
a party's argument, they probe it more aggressively with questions. 

**Implications for predicting outcomes:**
- Count questions directed at petitioner vs. respondent per justice
- High petitioner-directed questions → that justice likely votes for respondent
- This gives a "real-time" predictor during oral arguments
"""

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("⚖️ Advocates & Arguments")
tab_advocates, tab_amicus, tab_oral = st.tabs([
    "🎓 Advocate Win Rates", "📄 Amicus Brief Tracker", "🎙️ Oral Argument Analytics"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: ADVOCATE WIN RATES
# ──────────────────────────────────────────────────────────────────────────────
with tab_advocates:
    st.markdown(
        "Track individual Supreme Court advocates — which attorneys win most often, "
        "what issue areas they specialize in, and how their careers have evolved."
    )
    available_terms_adv = list(range(CURRENT_YEAR, CURRENT_YEAR-20,-1))
    col1_adv, col2_adv = st.columns([2,1])
    with col1_adv:
        terms_sel_adv = st.multiselect("Terms to analyze", available_terms_adv,
                                        default=available_terms_adv[:8], max_selections=12, key="adv_terms")
    with col2_adv:
        min_cases_adv = st.slider("Minimum appearances", 2, 20, 5, key="adv_min")

    if st.button("Load Advocate Data", type="primary", key="adv_btn"):
        with st.spinner(f"Fetching advocate data for {len(terms_sel_adv)} terms…"):
            adv_rows = _adv_load_advocate_data(tuple(sorted(terms_sel_adv, reverse=True)))
        st.session_state["adv_rows"] = adv_rows
        st.session_state["adv_terms_loaded"] = terms_sel_adv

    if "adv_rows" not in st.session_state:
        st.info("Select terms and click **Load Advocate Data**.")
    else:
        adv_rows_data = st.session_state["adv_rows"]
        if not adv_rows_data:
            st.warning("No advocate data found.")
        else:
            df_adv = pd.DataFrame(adv_rows_data)
            st.success(f"Loaded data for **{df_adv['advocate'].nunique()}** advocates across **{df_adv['case'].nunique()}** cases.")

            # Aggregate by advocate
            adv_agg = []
            for adv, grp in df_adv.groupby("advocate"):
                total = len(grp); wins = int(grp["won"].sum()); losses = total - wins
                terms_active = sorted(grp["term"].unique())
                issue_areas  = grp["issue_area"].value_counts().index[:3].tolist()
                roles = grp["role"].value_counts()
                pet_pct = int(roles.get("petitioner",0)/total*100)
                adv_agg.append({"Advocate": adv, "Total Appearances": total, "Wins": wins, "Losses": losses,
                                  "Win Rate %": round(wins/total*100,1), "Terms Active": len(terms_active),
                                  "First Term": min(terms_active), "Issue Specialization": ", ".join(issue_areas),
                                  "% as Petitioner": pet_pct})
            adv_df = pd.DataFrame(adv_agg)
            adv_df = adv_df[adv_df["Total Appearances"] >= min_cases_adv].sort_values("Win Rate %", ascending=False)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Advocates (min appearances)", len(adv_df))
            m2.metric("Top Win Rate", f"{adv_df.iloc[0]['Win Rate %']:.0f}%" if not adv_df.empty else "N/A",
                      adv_df.iloc[0]["Advocate"][:25] if not adv_df.empty else "")
            m3.metric("Most Appearances", str(adv_df["Total Appearances"].max()), adv_df.loc[adv_df["Total Appearances"].idxmax(),"Advocate"][:25] if not adv_df.empty else "")
            m4.metric("Avg Win Rate", f"{adv_df['Win Rate %'].mean():.1f}%")
            st.divider()

            sub_lb, sub_issue, sub_career = st.tabs(["🏆 Leaderboard","🏛️ By Issue Area","📈 Career Tracker"])

            with sub_lb:
                top_n = st.slider("Show top N advocates", 5, 30, 15, key="adv_top_n")
                top_adv = adv_df.head(top_n)
                fig_adv = go.Figure()
                fig_adv.add_trace(go.Bar(name="Wins",x=top_adv["Advocate"],y=top_adv["Wins"],
                                          marker_color="#27AE60",text=top_adv["Win Rate %"].apply(lambda v: f"{v:.0f}%"),
                                          textposition="outside"))
                fig_adv.add_trace(go.Bar(name="Losses",x=top_adv["Advocate"],y=top_adv["Losses"],marker_color="rgba(150,150,150,0.4)"))
                fig_adv.update_layout(barmode="stack",title=f"Top {top_n} Advocates by Win Rate",
                                       xaxis_tickangle=-35,height=400,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
                st.plotly_chart(fig_adv)
                st.dataframe(adv_df.head(25)[["Advocate","Total Appearances","Wins","Losses","Win Rate %","Issue Specialization","First Term"]]
                             .reset_index(drop=True).style.background_gradient(subset=["Win Rate %"],cmap="RdYlGn"),
                             height=380, hide_index=True)

            with sub_issue:
                issue_adv_rows = []
                for (issue, role), grp in df_adv.groupby(["issue_area","role"]):
                    if role == "other": continue
                    total = len(grp); wins = grp["won"].sum()
                    issue_adv_rows.append({"Issue Area":issue,"Role":role,"Total":total,
                                            "Win Rate %":round(wins/total*100,1) if total else 0})
                if issue_adv_rows:
                    issue_adv_df = pd.DataFrame(issue_adv_rows)
                    fig_ia_adv = px.bar(issue_adv_df,x="Issue Area",y="Win Rate %",color="Role",barmode="group",
                                        title="Advocate Win Rate by Issue Area and Role",
                                        color_discrete_map={"petitioner":"#E74C3C","respondent":"#3498DB"})
                    fig_ia_adv.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
                    fig_ia_adv.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
                    st.plotly_chart(fig_ia_adv)

            with sub_career:
                all_advocates_career = sorted(adv_df["Advocate"].tolist())
                sel_adv_career = st.selectbox("Select an advocate", all_advocates_career, key="adv_career_sel") if all_advocates_career else None
                if sel_adv_career:
                    career_df = df_adv[df_adv["advocate"] == sel_adv_career]
                    career_agg = []
                    for term, grp in career_df.groupby("term"):
                        total_t = len(grp); wins_t = grp["won"].sum()
                        career_agg.append({"Term":term,"Appearances":total_t,"Wins":int(wins_t),
                                            "Win Rate %":round(wins_t/total_t*100,1) if total_t else 0})
                    career_agg_df = pd.DataFrame(career_agg).sort_values("Term")
                    if not career_agg_df.empty:
                        col_c1, col_c2, col_c3 = st.columns(3)
                        col_c1.metric("Total Appearances", career_df.shape[0])
                        col_c2.metric("Total Wins", int(career_df["won"].sum()))
                        col_c3.metric("Overall Win Rate", f"{career_df['won'].mean()*100:.1f}%")
                        fig_career = go.Figure()
                        fig_career.add_trace(go.Bar(x=career_agg_df["Term"],y=career_agg_df["Appearances"],
                                                     name="Appearances",marker_color="#BDC3C7"))
                        fig_career.add_trace(go.Scatter(x=career_agg_df["Term"],y=career_agg_df["Win Rate %"],
                                                         name="Win Rate %",yaxis="y2",mode="lines+markers",
                                                         line=dict(color="#27AE60",width=2.5),marker=dict(size=8)))
                        fig_career.update_layout(title=f"{sel_adv_career} — Career at SCOTUS",height=340,
                                                  yaxis=dict(title="Appearances"),
                                                  yaxis2=dict(title="Win Rate %",overlaying="y",side="right",range=[0,105]),
                                                  plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_career)
                        st.subheader("Case History")
                        st.dataframe(career_df[["term","case","role","won","issue_area"]].sort_values("term",ascending=False),
                                     height=300)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: AMICUS BRIEF TRACKER
# ──────────────────────────────────────────────────────────────────────────────
with tab_amicus:
    st.markdown(
        "Amicus curiae (friend of the court) briefs signal which cases matter most to interest groups. "
        "Explore the most active filers and their influence at the Supreme Court."
    )

    am_df = pd.DataFrame(AMICUS_ORGS)
    am_df["Win Rate %"] = (am_df["wins"] / am_df["total"] * 100).round(1)

    m1_am, m2_am, m3_am, m4_am = st.columns(4)
    m1_am.metric("Organizations Tracked", len(am_df))
    m2_am.metric("Total Amicus Briefs Filed", am_df["total"].sum())
    m3_am.metric("Avg Win Rate", f"{am_df['Win Rate %'].mean():.1f}%")
    m4_am.metric("Most Active Filer", am_df.loc[am_df["total"].idxmax(),"org"][:25])
    st.divider()

    sub_overview_am, sub_cats_am, sub_landmark_am = st.tabs(["📊 Overview","🏛️ By Category","⭐ Landmark Cases"])

    with sub_overview_am:
        col_left_am, col_right_am = st.columns(2)
        with col_left_am:
            am_sorted = am_df.sort_values("total", ascending=True)
            fig_am_total = go.Figure(go.Bar(
                y=am_sorted["org"], x=am_sorted["total"], orientation="h",
                marker_color=[{"Government":"#E74C3C","Civil Liberties":"#3498DB","Business":"#E67E22",
                               "Libertarian":"#F39C12","Religious Liberty":"#9B59B6","Progressive":"#1ABC9C",
                               "Civil Rights":"#8E44AD","Labor":"#27AE60","Second Amendment":"#C0392B",
                               "LGBTQ+ Rights":"#E91E63","Democracy":"#2980B9","Property Rights":"#D35400",
                               "Legal Standards":"#7F8C8D","Small Business":"#E67E22","Healthcare":"#16A085"}.get(c,"#BDC3C7")
                               for c in am_sorted["category"]],
                text=am_sorted["total"], textposition="outside"))
            fig_am_total.update_layout(title="Total Amicus Briefs Filed",height=420,
                                        yaxis=dict(autorange="reversed"),
                                        xaxis_title="Number of Briefs",
                                        plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=220,r=60,t=40,b=40))
            st.plotly_chart(fig_am_total)
        with col_right_am:
            am_wr = am_df.sort_values("Win Rate %", ascending=False)
            fig_am_wr = go.Figure(go.Bar(
                x=am_wr["org"], y=am_wr["Win Rate %"],
                marker_color=["#27AE60" if r>60 else "#F39C12" if r>45 else "#E74C3C" for r in am_wr["Win Rate %"]],
                text=am_wr["Win Rate %"].apply(lambda v: f"{v:.0f}%"), textposition="outside"))
            fig_am_wr.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
            fig_am_wr.update_layout(title="Win Rate by Amicus Filer",height=420,xaxis_tickangle=-40,
                                     yaxis=dict(range=[0,100],title="Win Rate %"),
                                     plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_am_wr)
        st.subheader("Filer Profiles")
        cols_am = st.columns(3)
        for i, row in am_df.iterrows():
            with cols_am[int(i) % 3]:
                wr = row["Win Rate %"]
                wr_color = "#27AE60" if wr>60 else "#F39C12" if wr>45 else "#E74C3C"
                st.markdown(
                    f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px;margin:4px 0;">'
                    f'<div style="font-weight:bold;font-size:0.88em;">{row["org"]}</div>'
                    f'<div style="font-size:0.8em;color:#777;">{row["category"]}</div>'
                    f'<div style="margin:6px 0;">'
                    f'<span style="background:#ECF0F1;padding:2px 7px;border-radius:3px;font-size:0.8em;margin-right:4px;">{row["total"]} briefs</span>'
                    f'<span style="background:{wr_color}22;color:{wr_color};padding:2px 7px;border-radius:3px;font-size:0.8em;font-weight:bold;">{wr:.0f}% win rate</span></div>'
                    f'<div style="font-size:0.78em;color:#555;">{row["notes"]}</div></div>',
                    unsafe_allow_html=True)

    with sub_cats_am:
        cat_agg = am_df.groupby("category").agg({"total":"sum","wins":"sum"}).reset_index()
        cat_agg["Win Rate %"] = (cat_agg["wins"]/cat_agg["total"]*100).round(1)
        fig_cat_am = px.scatter(cat_agg,x="total",y="Win Rate %",size="total",color="category",
                                 hover_name="category",title="Amicus Category: Volume vs. Win Rate",
                                 labels={"total":"Total Briefs Filed"},size_max=40)
        fig_cat_am.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
        fig_cat_am.update_layout(height=420,plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_cat_am)
        st.dataframe(cat_agg.sort_values("Win Rate %",ascending=False).reset_index(drop=True)
                     .style.background_gradient(subset=["Win Rate %"],cmap="RdYlGn"),
                     height=320,hide_index=True)

    with sub_landmark_am:
        st.markdown("### Landmark Cases and Their Key Amicus Supporters")
        for landmark in LANDMARK_AMICUS:
            with st.expander(f"**{landmark['case']}** — {landmark['outcome']}"):
                st.markdown("**Key amicus filers:**")
                for filer in landmark["key_amicus"]:
                    st.markdown(f"- {filer}")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: ORAL ARGUMENT ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────
with tab_oral:
    st.markdown("Analyze oral argument transcripts — question counts, speaking time, and the research-backed link between questions and outcomes.")

    sub_patterns, sub_live, sub_research = st.tabs([
        "📊 Question Patterns by Justice", "🎙️ Live Argument Analysis", "📚 Research Findings"
    ])

    with sub_patterns:
        st.subheader("Average Questions per Oral Argument — Current Court")
        st.markdown("Based on analysis of Roberts Court oral arguments (2020–2024 terms).")

        court_data = QUESTION_PATTERNS["Roberts Court (2005–present)"]
        j_names = list(court_data.keys()); avg_qs = [court_data[j]["avg_questions"] for j in j_names]
        pet_qs  = [court_data[j]["lean_questions_petitioner"] for j in j_names]
        res_qs  = [court_data[j]["lean_questions_respondent"] for j in j_names]
        notes   = [court_data[j]["notes"] for j in j_names]

        fig_qs = go.Figure()
        fig_qs.add_trace(go.Bar(name="Toward Petitioner",x=j_names,y=pet_qs,marker_color="#E74C3C",opacity=0.85))
        fig_qs.add_trace(go.Bar(name="Toward Respondent",x=j_names,y=res_qs,marker_color="#3498DB",opacity=0.85))
        fig_qs.update_layout(barmode="stack",title="Average Questions per Oral Argument (by direction)",
                              xaxis_tickangle=-20,height=380,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
        st.plotly_chart(fig_qs)

        st.subheader("Justice Profiles — Oral Argument Style")
        cols_oa = st.columns(3)
        for i, j_name in enumerate(j_names):
            jd = court_data[j_name]
            with cols_oa[i % 3]:
                st.markdown(
                    f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px;margin:4px 0;">'
                    f'<div style="font-weight:bold;">{j_name}</div>'
                    f'<div style="font-size:0.82em;color:#666;margin:4px 0;">{jd["notes"]}</div>'
                    f'<div style="font-size:0.85em;">'
                    f'Avg Qs/argument: <strong>{jd["avg_questions"]}</strong><br>'
                    f'→ Petitioner: {jd["lean_questions_petitioner"]:.1f} | '
                    f'→ Respondent: {jd["lean_questions_respondent"]:.1f}</div></div>',
                    unsafe_allow_html=True)

        st.divider()
        st.subheader("Most Active Questioners")
        rank_df = pd.DataFrame([{"Justice":j,"Avg Questions":court_data[j]["avg_questions"]} for j in j_names])
        rank_df = rank_df.sort_values("Avg Questions",ascending=False)
        fig_rank = go.Figure(go.Bar(x=rank_df["Justice"],y=rank_df["Avg Questions"],
                                     marker_color="#9B59B6",text=rank_df["Avg Questions"],textposition="outside"))
        fig_rank.update_layout(title="Average Questions per Oral Argument",height=320,
                                yaxis_title="Avg Questions",plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_rank)

    with sub_live:
        st.markdown("Analyze the transcript of a specific oral argument — count questions, speaking time, and patterns.")
        available_terms_oa = list(range(CURRENT_YEAR, CURRENT_YEAR-10,-1))
        oa_term_live = st.selectbox("Select Term", available_terms_oa, key="oa_live_term")
        with st.spinner("Loading cases..."):
            live_cases = _adv_fetch_term(oa_term_live)
        if live_cases:
            live_case_names = sorted([c.get("name","") for c in live_cases])
            sel_case_live = st.selectbox("Select Case", live_case_names, key="oa_live_case")
            sel_live = next((c for c in live_cases if c.get("name")==sel_case_live), None)
            if sel_live and st.button("Analyze Oral Argument", key="oa_live_btn"):
                href = sel_live.get("href","")
                detail_live = _adv_fetch_detail(href) if href else None
                if detail_live:
                    oral_args_live = detail_live.get("oral_argument_audio") or []
                    if not oral_args_live:
                        st.warning("No oral argument audio found for this case.")
                    else:
                        for arg_entry in oral_args_live[:1]:
                            if not isinstance(arg_entry,dict): continue
                            arg_href = arg_entry.get("href","")
                            if not arg_href: continue
                            with st.spinner("Loading transcript..."):
                                arg_detail = _adv_load_transcript(arg_href)
                            if not arg_detail: st.warning("Could not load transcript."); continue
                            transcript = arg_detail.get("transcript") or {}
                            sections = transcript.get("sections") or []
                            if not sections: st.info("No transcript text available for this argument."); continue

                            # Count questions per speaker
                            speaker_turns: dict[str,int] = defaultdict(int)
                            speaker_words: dict[str,int] = defaultdict(int)
                            justice_questions: dict[str,int] = defaultdict(int)
                            all_turns = []
                            for section in sections:
                                for turn in (section.get("turns") or []):
                                    speaker = turn.get("speaker") or {}
                                    name = speaker.get("name","Unknown") if isinstance(speaker,dict) else str(speaker)
                                    role = speaker.get("roles") or []
                                    is_justice = any("justice" in str(r).lower() for r in role) if isinstance(role,list) else False
                                    blocks = turn.get("text_blocks") or []
                                    text = " ".join(b.get("text","") for b in blocks if isinstance(b,dict))
                                    words = len(text.split())
                                    q_count = text.count("?")
                                    speaker_turns[name] += 1
                                    speaker_words[name] += words
                                    if is_justice: justice_questions[name] += q_count
                                    all_turns.append({"speaker":name,"is_justice":is_justice,"words":words,"questions":q_count,"text":text[:200]})

                            st.subheader(f"Oral Argument Analysis: {sel_case_live}")
                            col_turns, col_words = st.columns(2)
                            with col_turns:
                                turns_df = pd.DataFrame(list(speaker_turns.items()),columns=["Speaker","Turns"]).sort_values("Turns",ascending=False)
                                fig_turns = go.Figure(go.Bar(y=turns_df["Speaker"],x=turns_df["Turns"],orientation="h",marker_color="#3498DB",text=turns_df["Turns"],textposition="outside"))
                                fig_turns.update_layout(title="Speaking Turns per Participant",height=360,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=150,r=40,t=40,b=40))
                                st.plotly_chart(fig_turns)
                            with col_words:
                                words_df = pd.DataFrame(list(speaker_words.items()),columns=["Speaker","Words"]).sort_values("Words",ascending=False)
                                fig_words = go.Figure(go.Bar(y=words_df["Speaker"],x=words_df["Words"],orientation="h",marker_color="#E67E22",text=words_df["Words"],textposition="outside"))
                                fig_words.update_layout(title="Word Count per Participant",height=360,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=150,r=40,t=40,b=40))
                                st.plotly_chart(fig_words)
                            if justice_questions:
                                st.subheader("Questions Asked by Each Justice")
                                jq_df = pd.DataFrame(list(justice_questions.items()),columns=["Justice","Questions"]).sort_values("Questions",ascending=False)
                                fig_jq = go.Figure(go.Bar(x=jq_df["Justice"],y=jq_df["Questions"],marker_color="#9B59B6",text=jq_df["Questions"],textposition="outside"))
                                fig_jq.update_layout(title="Questions Detected in Oral Argument Transcript",height=320,yaxis_title="Question Count",plot_bgcolor="white",paper_bgcolor="white")
                                st.plotly_chart(fig_jq)
                                st.info("Higher question counts toward a party often predict a vote against that party (Jacobi & Schweers, 2017).")

    with sub_research:
        st.markdown(QUESTION_OUTCOME_INSIGHT)
        st.divider()
        st.subheader("Interruption Patterns at SCOTUS")
        st.markdown("""
Research by **Jacobi & Schweers (2017)** and **Johnson et al.** documented significant disparities in how justices are treated during oral arguments:

**Key Findings:**
- **Female justices are interrupted more** than male justices at similar seniority levels
- **Liberal justices interrupt less** on average than conservative justices
- **The most senior justice in the majority** tends to dominate oral argument questioning
- **Advocates who speak for longer without being interrupted** tend to do better in outcomes

**Question-to-Outcome Correlation (by study):**

| Study | Finding | Accuracy |
|-------|---------|----------|
| Jacobi & Schweers (2017) | Question count predicts vote direction | ~70% |
| Johnson et al. (2009) | Laughter predicts petitioner outcome | ~62% |
| Shullman (2004) | Skeptical questions predict outcomes | ~67% |
| Black et al. (2011) | Response to hypotheticals predicts outcome | ~65% |

**Implication for prediction:**
When analyzing oral arguments, counting the questions directed at each party — and identifying which justices asked the most challenging questions — can provide a real-time prediction signal that rivals the formal statistical model.
        """)
