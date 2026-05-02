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

st.set_page_config(page_title="Geography & Tools Hub", page_icon="🗺️", layout="wide")

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── State mapping helpers ──────────────────────────────────────────────────────
STATE_ABBREV = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS",
    "Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA",
    "Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT",
    "Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM",
    "New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
    "South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT",
    "Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY",
    "District of Columbia":"DC",
}
STATE_NAMES = list(STATE_ABBREV.keys())

def _extract_state(court_name: str) -> str | None:
    if not court_name: return None
    court_l = court_name.lower()
    # Check for "state of X" or "commonwealth of X"
    for state in STATE_NAMES:
        if state.lower() in court_l:
            return state
    # Common abbreviations and patterns
    if "d.c." in court_l or "district of columbia" in court_l: return "District of Columbia"
    return None

def _classify_disposition_geo(label: str) -> str:
    label_l = label.lower()
    if "affirm" in label_l: return "Affirmed"
    if any(w in label_l for w in ["revers","vacate"]): return "Reversed/Vacated"
    if "remand" in label_l: return "Remanded"
    return "Other"

@st.cache_data(show_spinner=False)
def _geo_fetch_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _geo_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

@st.cache_data(show_spinner=False, ttl=3600)
def _geo_load_state_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = _geo_fetch_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = _geo_fetch_detail(href)
            if not detail: continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name","") if isinstance(lower,dict) else str(lower)
            state = _extract_state(lc_name)
            if not state: continue
            disp  = detail.get("disposition") or {}
            disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
            ia    = detail.get("issue_area") or {}
            issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
            rows.append({
                "term": term, "state": state, "abbrev": STATE_ABBREV.get(state,state),
                "case": detail.get("name",""), "lower_court": lc_name,
                "disposition": disp_label, "outcome": _classify_disposition_geo(disp_label),
                "issue_area": issue,
            })
        time.sleep(0.03)
    return rows

@st.cache_data(show_spinner=False, ttl=1800)
def _geo_load_term_data(term: int) -> list[dict]:
    rows = []
    cases = _geo_fetch_term(term)
    for c in cases:
        href = c.get("href","")
        if not href: continue
        detail = _geo_fetch_detail(href)
        if not detail: continue
        ia = detail.get("issue_area") or {}
        issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
        disp  = detail.get("disposition") or {}
        disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
        decisions = detail.get("decisions") or []
        vote_splits = []
        for dec in decisions:
            votes = dec.get("votes") or []
            maj = sum(1 for v in votes if (v.get("vote") or "").lower() in ("majority","concurrence"))
            dis = sum(1 for v in votes if (v.get("vote") or "").lower() == "dissent")
            if maj + dis >= 7: vote_splits.append(f"{maj}-{dis}")
        split = vote_splits[0] if vote_splits else ""
        margin = int(split.split("-")[0]) - int(split.split("-")[1]) if split and "-" in split else None
        rows.append({
            "case": detail.get("name",""),
            "issue_area": issue, "disposition": disp_label,
            "vote_split": split, "margin": margin,
            "decided_on": detail.get("decided_on",""),
        })
        time.sleep(0.02)
    return rows

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🗺️ Geography & Tools")
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
    available_terms_geo = list(range(CURRENT_YEAR, CURRENT_YEAR-25,-1))
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
            st.plotly_chart(fig_choro, use_container_width=True)

            col_top_geo, col_bot_geo = st.columns(2)
            with col_top_geo:
                st.markdown("**States Most Reviewed**")
                top_states = state_df.sort_values("Cases Reviewed", ascending=False).head(10)
                fig_top = go.Figure(go.Bar(y=top_states["State"],x=top_states["Cases Reviewed"],orientation="h",
                                           marker_color="#3498DB",text=top_states["Cases Reviewed"],textposition="outside"))
                fig_top.update_layout(height=340,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=130,r=40,t=30,b=30))
                st.plotly_chart(fig_top, use_container_width=True)
            with col_bot_geo:
                st.markdown("**Highest Reversal Rates**")
                rev_states = state_df[state_df["Cases Reviewed"]>=3].sort_values("Reversal Rate (%)",ascending=False).head(10)
                fig_rev = go.Figure(go.Bar(y=rev_states["State"],x=rev_states["Reversal Rate (%)"],orientation="h",
                                           marker_color="#E74C3C",text=rev_states["Reversal Rate (%)"].apply(lambda v:f"{v:.0f}%"),
                                           textposition="outside"))
                fig_rev.update_layout(height=340,plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=130,r=40,t=30,b=30))
                st.plotly_chart(fig_rev, use_container_width=True)

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
            st.plotly_chart(fig_si, use_container_width=True)

            st.subheader("State Drilldown")
            sel_state_drill = st.selectbox("Select State",sorted(geo_df["state"].unique()),key="geo_drill")
            state_drill_df = geo_df[geo_df["state"]==sel_state_drill]
            d1,d2,d3 = st.columns(3)
            d1.metric("Cases Reviewed",len(state_drill_df))
            d2.metric("Reversed",(state_drill_df["outcome"]=="Reversed/Vacated").sum())
            d3.metric("Affirmed",(state_drill_df["outcome"]=="Affirmed").sum())
            st.dataframe(state_drill_df[["term","case","lower_court","outcome","issue_area"]]
                         .sort_values("term",ascending=False),use_container_width=True,height=300)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: TERM-TO-TERM COMPARATOR
# ──────────────────────────────────────────────────────────────────────────────
with tab_compare:
    st.markdown("Compare any two SCOTUS terms across 8+ dimensions simultaneously — case volume, issue areas, vote splits, and more.")
    available_terms_cmp = list(range(CURRENT_YEAR, 1993,-1))
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
            st.plotly_chart(fig_radar, use_container_width=True)

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
                st.plotly_chart(fig_ia_cmp, use_container_width=True)

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
                st.plotly_chart(fig_split_cmp, use_container_width=True)

            with sub_cases_cmp:
                col_ca_list, col_cb_list = st.columns(2)
                with col_ca_list:
                    st.markdown(f"**{label_a} Cases ({len(df_a)})**")
                    st.dataframe(df_a[["case","issue_area","vote_split","disposition"]].reset_index(drop=True),
                                 use_container_width=True, height=400)
                with col_cb_list:
                    st.markdown(f"**{label_b} Cases ({len(df_b)})**")
                    st.dataframe(df_b[["case","issue_area","vote_split","disposition"]].reset_index(drop=True),
                                 use_container_width=True, height=400)

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
    st.plotly_chart(fig_cite, use_container_width=True)
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
        st.plotly_chart(fig_bar_cite, use_container_width=True)
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
        st.plotly_chart(fig_domain, use_container_width=True)

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
