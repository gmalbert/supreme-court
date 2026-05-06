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

LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#F39C12", "Liberal": "#3498DB"}
PARTY_COLORS = {"R": "#E74C3C", "D": "#3498DB"}

# ── Justice data ───────────────────────────────────────────────────────────────
JUSTICES_RECENT = [
    ("William Rehnquist",   1972, 2005, "Conservative", "Nixon"),
    ("John Paul Stevens",   1975, 2010, "Liberal",      "Ford"),
    ("Sandra Day O'Connor", 1981, 2006, "Moderate",     "Reagan"),
    ("Antonin Scalia",      1986, 2016, "Conservative", "Reagan"),
    ("Anthony Kennedy",     1988, 2018, "Moderate",     "Reagan"),
    ("David Souter",        1990, 2009, "Liberal",      "G.H.W. Bush"),
    ("Clarence Thomas",     1991, None, "Conservative", "G.H.W. Bush"),
    ("Ruth Bader Ginsburg", 1993, 2020, "Liberal",      "Clinton"),
    ("Stephen Breyer",      1994, 2022, "Liberal",      "Clinton"),
    ("John G. Roberts",     2005, None, "Conservative", "G.W. Bush"),
    ("Samuel Alito",        2006, None, "Conservative", "G.W. Bush"),
    ("Sonia Sotomayor",     2009, None, "Liberal",      "Obama"),
    ("Elena Kagan",         2010, None, "Liberal",      "Obama"),
    ("Neil Gorsuch",        2017, None, "Conservative", "Trump"),
    ("Brett Kavanaugh",     2018, None, "Moderate",     "Trump"),
    ("Amy Coney Barrett",   2020, None, "Conservative", "Trump"),
    ("Ketanji Brown Jackson",2022,None, "Liberal",      "Biden"),
]

# Conservative bloc reference for alignment scoring
CONSERVATIVE_BLOC = {"Thomas","Scalia","Rehnquist","Alito","Gorsuch","Barrett"}

@st.cache_data(show_spinner=False)
def _rs_fetch_cases_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _rs_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _last_name(full: str) -> str:
    return (full.strip().split()[-1]) if full.strip() else full

@st.cache_data(show_spinner=False, ttl=3600)
def _rs_load_drift_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = _rs_fetch_cases_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = _rs_fetch_detail(href)
            if not detail: continue
            for decision in (detail.get("decisions") or []):
                votes = decision.get("votes") or []
                # Get conservative bloc votes for this case
                cons_votes = {}
                for vote in votes:
                    member = vote.get("member") or {}
                    j_name = _last_name(member.get("name","") if isinstance(member,dict) else "")
                    if j_name in CONSERVATIVE_BLOC:
                        cons_votes[j_name] = (vote.get("vote") or "").lower()
                # Determine majority conservative position
                cons_majority_vote = None
                if len(cons_votes) >= 3:
                    vote_vals = list(cons_votes.values())
                    if vote_vals.count("majority") + vote_vals.count("concurrence") > len(vote_vals)/2:
                        cons_majority_vote = "majority"
                    elif vote_vals.count("dissent") > len(vote_vals)/2:
                        cons_majority_vote = "dissent"
                if not cons_majority_vote: continue
                for vote in votes:
                    member = vote.get("member") or {}
                    j_full = member.get("name","") if isinstance(member,dict) else ""
                    j_name = _last_name(j_full)
                    v = (vote.get("vote") or "").lower()
                    if j_name in CONSERVATIVE_BLOC: continue  # skip bloc itself
                    aligned = (v in ("majority","concurrence") and cons_majority_vote=="majority") or \
                              (v == "dissent" and cons_majority_vote == "dissent")
                    rows.append({"term": term, "justice": j_name, "justice_full": j_full,
                                  "aligned_with_cons": aligned, "vote": v})
        time.sleep(0.02)
    return rows

# ── Doctrine Evolution data ────────────────────────────────────────────────────
DOCTRINES = {
    "Commerce Clause": {
        "color": "#E74C3C",
        "summary": "The Commerce Clause (Art. I §8) gives Congress power to regulate interstate commerce. Its scope has expanded and contracted dramatically.",
        "milestones": [
            (1824, "Gibbons v. Ogden", "Broad interpretation: Congress can regulate navigation between states.", "Expansion"),
            (1895, "US v. E.C. Knight Co.", "Manufacturing ≠ commerce; limited federal antitrust power.", "Contraction"),
            (1937, "NLRB v. Jones & Laughlin Steel", "Commerce Clause revived post-New Deal; 'affecting commerce' standard.", "Expansion"),
            (1942, "Wickard v. Filburn", "Growing wheat for personal use 'affects' interstate commerce. Maximum expansion.", "Expansion"),
            (1995, "United States v. Lopez", "Gun-Free School Zones Act exceeds commerce power. First limit in 60 years.", "Contraction"),
            (2000, "United States v. Morrison", "Violence Against Women Act civil remedy exceeds commerce power.", "Contraction"),
            (2005, "Gonzales v. Raich", "Federal drug law upheld; medical marijuana regulated by Congress.", "Expansion"),
            (2012, "NFIB v. Sebelius", "ACA mandate exceeds commerce power; upheld as tax. Roberts draws new line.", "Contraction"),
            (2022, "West Virginia v. EPA", "Major questions doctrine limits sweeping agency action. Chevron restricted.", "Contraction"),
            (2024, "Loper Bright v. Raimondo", "Chevron deference overruled. Courts interpret statutes independently.", "Contraction"),
        ]},
    "Free Speech (1st Amendment)": {
        "color": "#E67E22",
        "summary": "The First Amendment's free speech guarantee has evolved from wartime restrictions to near-absolute protection for political speech.",
        "milestones": [
            (1919, "Schenck v. United States", "Clear and present danger test: speech can be punished if danger is imminent and probable.", "Restriction"),
            (1925, "Gitlow v. New York", "1st Amendment incorporated against states via 14th Amendment.", "Expansion"),
            (1927, "Whitney v. California", "Brandeis concurrence: speech must pose imminent, serious evil to be restricted.", "Expansion"),
            (1951, "Dennis v. United States", "Communist Party leaders convicted; CPUSA advocacy not protected.", "Restriction"),
            (1957, "Roth v. United States", "Obscenity not protected by 1st Amendment; established obscenity test.", "Restriction"),
            (1964, "New York Times v. Sullivan", "Actual malice standard for public officials; landmark press freedom case.", "Expansion"),
            (1969, "Brandenburg v. Ohio", "Overruled Schenck; speech protected unless directed to incite imminent lawless action.", "Expansion"),
            (1971, "Cohen v. California", "F*** the Draft jacket: offensive but protected speech in public.", "Expansion"),
            (1989, "Texas v. Johnson", "Flag burning is protected symbolic speech.", "Expansion"),
            (2010, "Citizens United v. FEC", "Corporate political spending is protected speech; campaign finance limits struck.", "Expansion"),
            (2011, "Snyder v. Phelps", "Westboro Baptist funeral protests are protected speech on matters of public concern.", "Expansion"),
            (2023, "303 Creative v. Elenis", "Designer cannot be compelled to create websites endorsing same-sex marriage.", "Expansion"),
        ]},
    "Privacy & Abortion (14th Amendment Due Process)": {
        "color": "#9B59B6",
        "summary": "Substantive due process protections for personal liberty, from contraception to abortion to same-sex relationships — and back.",
        "milestones": [
            (1897, "Allgeyer v. Louisiana", "Liberty of contract: early substantive due process.", "Expansion"),
            (1905, "Lochner v. New York", "Maximum hours law invalid; liberty of contract era begins.", "Expansion"),
            (1937, "West Coast Hotel v. Parrish", "Lochner overruled; economic substantive due process ends.", "Contraction"),
            (1965, "Griswold v. Connecticut", "Right to marital privacy protects contraceptive use.", "Expansion"),
            (1973, "Roe v. Wade", "Abortion right derived from privacy/liberty; trimester framework.", "Expansion"),
            (1992, "Planned Parenthood v. Casey", "Roe reaffirmed; trimester framework replaced with undue burden test.", "Mixed"),
            (2003, "Lawrence v. Texas", "Texas sodomy law violates liberty interest; Bowers v. Hardwick overruled.", "Expansion"),
            (2015, "Obergefell v. Hodges", "Same-sex couples have fundamental right to marry under liberty and equality.", "Expansion"),
            (2022, "Dobbs v. Jackson Women's Health Org.", "Roe and Casey overruled; abortion regulation returned to states.", "Contraction"),
        ]},
    "Equal Protection (14th Amendment)": {
        "color": "#3498DB",
        "summary": "The Equal Protection Clause guarantees equality under law. Its application to race, sex, and other classifications has shifted dramatically.",
        "milestones": [
            (1896, "Plessy v. Ferguson", "Separate but equal: racial segregation upheld.", "Contraction"),
            (1944, "Korematsu v. United States", "Japanese internment upheld under strict scrutiny — but in wartime.", "Contraction"),
            (1954, "Brown v. Board of Education", "Separate but equal overruled; racial segregation in schools unconstitutional.", "Expansion"),
            (1967, "Loving v. Virginia", "Anti-miscegenation laws violate equal protection.", "Expansion"),
            (1971, "Reed v. Reed", "First case to apply equal protection to sex discrimination.", "Expansion"),
            (1978, "Regents of Univ. of Cal. v. Bakke", "Race-conscious admissions may be used for diversity; rigid quotas banned.", "Mixed"),
            (1996, "United States v. Virginia (VMI)", "Sex-based exclusion of women from VMI violates equal protection.", "Expansion"),
            (2003, "Grutter v. Bollinger", "Race-conscious admissions at law school upheld under strict scrutiny.", "Expansion"),
            (2015, "Obergefell v. Hodges", "Same-sex marriage right grounded in both due process and equal protection.", "Expansion"),
            (2023, "SFFA v. Harvard / UNC", "Race-conscious admissions unconstitutional; Grutter overruled.", "Contraction"),
        ]},
    "Administrative Law / Chevron Doctrine": {
        "color": "#16A085",
        "summary": "How much deference should courts give federal agencies when they interpret ambiguous statutes? The answer shaped the entire modern regulatory state.",
        "milestones": [
            (1944, "Skidmore v. Swift & Co.", "Agency interpretations get 'weight' based on persuasive power.", "Moderate Deference"),
            (1984, "Chevron v. NRDC", "Two-step: if statute ambiguous, defer to 'reasonable' agency interpretation.", "Expansion (Deference)"),
            (2001, "United States v. Mead Corp.", "Chevron limited to formal agency actions; Skidmore for informal ones.", "Contraction"),
            (2013, "City of Arlington v. FCC", "Chevron applies even when agency is determining scope of its own jurisdiction.", "Expansion (Deference)"),
            (2015, "King v. Burwell", "ACA subsidies: Court decides itself despite Chevron — 'major question' exception.", "Contraction"),
            (2022, "West Virginia v. EPA", "Major questions doctrine: Congress must speak clearly on economically significant issues.", "Contraction"),
            (2024, "Loper Bright v. Raimondo", "Chevron overruled. Courts must interpret statutes de novo.", "Contraction (End of Deference)"),
        ]},
    "Second Amendment": {
        "color": "#8E44AD",
        "summary": "From collective right to individual right — the Second Amendment's transformation over 70 years.",
        "milestones": [
            (1876, "United States v. Cruikshank", "2nd Amendment restrains only Congress, not states.", "Restriction"),
            (1939, "United States v. Miller", "Sawed-off shotgun not protected; 2nd Amendment tied to militia purpose.", "Restriction"),
            (2008, "District of Columbia v. Heller", "Individual right to keep firearms in the home recognized for the first time.", "Expansion"),
            (2010, "McDonald v. City of Chicago", "2nd Amendment incorporated against states via 14th Amendment.", "Expansion"),
            (2022, "New York State Rifle & Pistol Assn. v. Bruen", "Means-ends scrutiny rejected; historical tradition test required.", "Expansion"),
            (2024, "Garland v. Cargill", "Bump stocks do not qualify as machine guns under federal law.", "Expansion"),
        ]},
}

MILESTONE_COLORS = {
    "Expansion": "#27AE60", "Contraction": "#E74C3C", "Restriction": "#E74C3C",
    "Mixed": "#F39C12", "Moderate Deference": "#F39C12",
    "Expansion (Deference)": "#27AE60", "Contraction": "#E74C3C",
    "End of Deference": "#E74C3C", "Contraction (End of Deference)": "#E74C3C",
}

# ── Congressional Response data ────────────────────────────────────────────────
CONGRESS_RESPONSES = [
    dict(case="Dred Scott v. Sandford", case_year=1857, amendment_or_law="14th Amendment", law_year=1868,
         response_type="Constitutional Amendment", congress="39th Congress",
         description="Overturned Dred Scott directly; granted citizenship to freed slaves and all born on U.S. soil.",
         partisan_context="Post-Civil War Reconstruction Congress, dominated by Republicans.",
         succeeded=True),
    dict(case="Pollock v. Farmers' Loan & Trust Co.", case_year=1895, amendment_or_law="16th Amendment", law_year=1913,
         response_type="Constitutional Amendment", congress="62nd Congress",
         description="Overrode SCOTUS by explicitly authorizing a federal income tax.",
         partisan_context="Bipartisan support after 18 years of political pressure.",
         succeeded=True),
    dict(case="Minor v. Happersett", case_year=1875, amendment_or_law="19th Amendment", law_year=1920,
         response_type="Constitutional Amendment", congress="66th Congress",
         description="Granted women the right to vote, overcoming SCOTUS holding that suffrage wasn't a citizenship right.",
         partisan_context="Passed after decades of suffrage movement advocacy.",
         succeeded=True),
    dict(case="Chisholm v. Georgia", case_year=1793, amendment_or_law="11th Amendment", law_year=1795,
         response_type="Constitutional Amendment", congress="3rd Congress",
         description="Reversed Chisholm, which had allowed citizens of one state to sue another state in federal court.",
         partisan_context="Passed within two years — fastest constitutional response to SCOTUS.",
         succeeded=True),
    dict(case="Oregon v. Mitchell", case_year=1970, amendment_or_law="26th Amendment", law_year=1971,
         response_type="Constitutional Amendment", congress="92nd Congress",
         description="SCOTUS split on whether Congress could lower voting age. 26th Amendment settled it at 18 nationwide.",
         partisan_context="Passage tied to Vietnam War-era politics (18-year-olds could be drafted but not vote).",
         succeeded=True),
    dict(case="Ledbetter v. Goodyear Tire & Rubber Co.", case_year=2007, amendment_or_law="Lilly Ledbetter Fair Pay Act", law_year=2009,
         response_type="Federal Legislation", congress="111th Congress",
         description="Overturned SCOTUS's ruling on pay discrimination statute of limitations. First bill signed by President Obama.",
         partisan_context="Passed on party-line Democratic vote after 2008 election.",
         succeeded=True),
    dict(case="United States v. Lopez", case_year=1995, amendment_or_law="Proposed Gun-Free School Zones Act Amendment", law_year=1996,
         response_type="Federal Legislation", congress="104th Congress",
         description="Congress amended the GFSZA to add the 'jurisdictional element' (affecting interstate commerce) SCOTUS said was missing.",
         partisan_context="Republican Congress reluctantly amended the statute to comply.",
         succeeded=True),
    dict(case="City of Boerne v. Flores", case_year=1997, amendment_or_law="Religious Land Use and Institutionalized Persons Act (RLUIPA)", law_year=2000,
         response_type="Federal Legislation", congress="106th Congress",
         description="After SCOTUS struck down RFRA as applied to states, Congress passed RLUIPA under Spending Clause.",
         partisan_context="Bipartisan response to protect religious land use rights.",
         succeeded=True),
    dict(case="Shelby County v. Holder", case_year=2013, amendment_or_law="John Lewis Voting Rights Advancement Act", law_year=None,
         response_type="Federal Legislation (Failed)", congress="117th/118th Congress",
         description="Multiple bills to restore VRA preclearance have failed to pass the Senate.",
         partisan_context="Blocked by Republican filibuster in the Senate.",
         succeeded=False),
    dict(case="Citizens United v. FEC", case_year=2010, amendment_or_law="DISCLOSE Act / Constitutional Amendment proposals", law_year=None,
         response_type="Federal Legislation (Failed)", congress="111th+ Congress",
         description="Multiple legislative attempts to limit corporate political spending failed in the Senate.",
         partisan_context="Democratic-sponsored legislation blocked by Republican filibuster.",
         succeeded=False),
    dict(case="Burwell v. Hobby Lobby", case_year=2014, amendment_or_law="No Federal Response Enacted", law_year=None,
         response_type="No Action", congress="114th Congress",
         description="Proposed legislation to override Hobby Lobby's RFRA exemption failed in a divided Congress.",
         partisan_context="Republican Congress opposed any rollback of religious exemption.",
         succeeded=False),
    dict(case="AT&T Mobility v. Concepcion", case_year=2011, amendment_or_law="Arbitration Fairness Act (proposed)", law_year=None,
         response_type="Federal Legislation (Failed)", congress="Multiple",
         description="Multiple bills to limit mandatory arbitration clauses have failed to advance.",
         partisan_context="Business community opposition prevented Senate action.",
         succeeded=False),
    dict(case="Loper Bright Enterprises v. Raimondo", case_year=2024, amendment_or_law="Proposed REINS Act / Various regulatory reform bills", law_year=None,
         response_type="Federal Legislation (Pending)", congress="118th/119th Congress",
         description="Bills to codify or modify Chevron's framework pending. Some Republicans want even less deference; Democrats want to restore it.",
         partisan_context="Contested in a divided Congress.",
         succeeded=False),
    dict(case="Dobbs v. Jackson Women's Health Org.", case_year=2022, amendment_or_law="Women's Health Protection Act (proposed)", law_year=None,
         response_type="Federal Legislation (Failed)", congress="117th Congress",
         description="The WHPA would have codified Roe v. Wade into federal law. Failed on Senate cloture vote.",
         partisan_context="50-50 Senate could not break filibuster.",
         succeeded=False),
    dict(case="United States v. Windsor", case_year=2013, amendment_or_law="DOMA Repeal (Respect for Marriage Act)", law_year=2022,
         response_type="Federal Legislation", congress="117th Congress",
         description="While Windsor struck down Section 3 of DOMA, the Respect for Marriage Act (2022) codified same-sex marriage protection after Dobbs fears.",
         partisan_context="Bipartisan passage — 12 Republican senators voted for it.",
         succeeded=True),
]

# ── Justice Replacement data ───────────────────────────────────────────────────
CURRENT_COURT = [
    {"name": "Roberts",   "lean": "Conservative"},
    {"name": "Thomas",    "lean": "Conservative"},
    {"name": "Alito",     "lean": "Conservative"},
    {"name": "Sotomayor", "lean": "Liberal"},
    {"name": "Kagan",     "lean": "Liberal"},
    {"name": "Gorsuch",   "lean": "Conservative"},
    {"name": "Kavanaugh", "lean": "Moderate"},
    {"name": "Barrett",   "lean": "Conservative"},
    {"name": "Jackson",   "lean": "Liberal"},
]

KEY_FIVE_FOUR = [
    dict(case="Dobbs v. Jackson Women's Health Org.", term=2021, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Privacy / Abortion", outcome="Roe and Casey overruled"),
    dict(case="West Virginia v. EPA", term=2021, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Administrative Law", outcome="EPA carbon rule struck"),
    dict(case="SFFA v. Harvard", term=2022, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Equal Protection", outcome="Race-conscious admissions struck"),
    dict(case="Bruen (NY Rifle & Pistol Assn.)", term=2021, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Second Amendment", outcome="Historical tradition test adopted"),
    dict(case="Moore v. Harper", term=2022, split="6-3",
         majority=["Roberts","Sotomayor","Kagan","Kavanaugh","Barrett","Jackson"],
         dissent=["Thomas","Alito","Gorsuch"],
         issue="Elections / State Power", outcome="Independent state legislature theory rejected"),
    dict(case="Loper Bright v. Raimondo", term=2023, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Administrative Law", outcome="Chevron overruled"),
    dict(case="Biden v. Nebraska (student debt)", term=2022, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Education / Executive Power", outcome="$400B debt cancellation blocked"),
    dict(case="Kennedy v. Bremerton School District", term=2021, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="First Amendment / Religion", outcome="Public school coach's personal prayer protected"),
    dict(case="303 Creative v. Elenis", term=2022, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="First Amendment / LGBTQ+", outcome="Designer need not create same-sex wedding websites"),
    dict(case="Snyder v. United States (gratuities)", term=2023, split="5-4",
         majority=["Roberts","Thomas","Alito","Gorsuch","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson","Kavanaugh"],
         issue="Criminal / Anti-Corruption", outcome="Federal gratuity statute interpreted narrowly"),
]

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🔬 Research")
tab_drift, tab_doctrine, tab_congress, tab_replace = st.tabs([
    "📉 Justice Ideology Drift", "📚 Doctrine Evolution",
    "🏛️ Congressional Response", "🔄 Justice Replacement Simulator"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: JUSTICE IDEOLOGY DRIFT
# ──────────────────────────────────────────────────────────────────────────────
with tab_drift:
    st.markdown(
        "Track how each justice's voting alignment with the conservative bloc shifts over their tenure. "
        "High alignment = votes frequently with Thomas/Scalia/Alito. Low = diverges from conservative bloc."
    )
    st.info("Alignment is computed from live Oyez vote data vs. the Thomas-Scalia-Alito bloc. "
            "Justices in the bloc are excluded from the chart.")

    available_terms_d = list(range(CURRENT_YEAR, CURRENT_YEAR-30,-1))
    all_justice_names = [j[0] for j in JUSTICES_RECENT if j[0].split()[-1] not in CONSERVATIVE_BLOC]

    col1_d, col2_d = st.columns([2,1])
    with col1_d:
        terms_sel_d = st.multiselect("Terms to include", available_terms_d, default=available_terms_d[:12],
                                      max_selections=15, key="drift_terms")
    with col2_d:
        justices_sel_d = st.multiselect("Justices to show", [j.split()[-1] for j in all_justice_names],
                                         default=["Stevens","O'Connor","Kennedy","Souter","Roberts",
                                                  "Sotomayor","Kagan","Gorsuch","Kavanaugh","Jackson"],
                                         key="drift_justices")

    if st.button("Load Drift Data", type="primary", key="drift_btn"):
        with st.spinner(f"Fetching vote data for {len(terms_sel_d)} terms…"):
            drift_rows = _rs_load_drift_data(tuple(sorted(terms_sel_d, reverse=True)))
        st.session_state["drift_rows"] = drift_rows

    if "drift_rows" not in st.session_state:
        st.info("Select terms and click **Load Drift Data** to begin.")
    else:
        drift_rows = st.session_state["drift_rows"]
        if not drift_rows:
            st.warning("No drift data found.")
        else:
            df_drift = pd.DataFrame(drift_rows)
            # Filter to selected justices
            if justices_sel_d:
                df_drift = df_drift[df_drift["justice"].isin(justices_sel_d)]

            # Rolling 3-term alignment
            drift_agg = []
            for (justice, term), grp in df_drift.groupby(["justice","term"]):
                total = len(grp); aligned = grp["aligned_with_cons"].sum()
                drift_agg.append({"Justice": justice, "Term": term, "Alignment": round(aligned/total*100,1), "Votes": total})
            drift_agg_df = pd.DataFrame(drift_agg).sort_values(["Justice","Term"])

            # Compute rolling 3-term average
            smooth_rows = []
            for justice, grp in drift_agg_df.groupby("Justice"):
                grp = grp.sort_values("Term")
                grp["Alignment (3-term rolling)"] = grp["Alignment"].rolling(3, min_periods=1).mean().round(1)
                smooth_rows.append(grp)
            smooth_df = pd.concat(smooth_rows) if smooth_rows else pd.DataFrame()

            if not smooth_df.empty:
                fig_drift = px.line(smooth_df, x="Term", y="Alignment (3-term rolling)", color="Justice",
                                    markers=True, title="Conservative Bloc Alignment — 3-Term Rolling Average",
                                    labels={"Alignment (3-term rolling)": "% Alignment with Conservative Bloc"})
                fig_drift.add_hline(y=50, line_dash="dot", line_color="#BDC3C7", annotation_text="50% (neither bloc)")
                fig_drift.update_layout(height=460, plot_bgcolor="white", paper_bgcolor="white",
                                         yaxis=dict(range=[0,105], title="Conservative Alignment %"),
                                         legend=dict(x=1.01, y=1))
                st.plotly_chart(fig_drift)
                st.caption("Values above 50% = tends to agree with conservatives. Below 50% = disagrees more often. Based on Thomas/Scalia/Rehnquist/Alito/Gorsuch/Barrett as reference bloc.")

            # Drift summary
            st.subheader("Ideological Drift Summary")
            drift_summary = []
            for justice, grp in drift_agg_df.groupby("Justice"):
                if len(grp) < 3: continue
                grp = grp.sort_values("Term")
                first_three = grp.head(3)["Alignment"].mean()
                last_three  = grp.tail(3)["Alignment"].mean()
                drift_val   = last_three - first_three
                drift_summary.append({"Justice": justice, "Early Alignment (%)": round(first_three,1),
                                       "Recent Alignment (%)": round(last_three,1), "Drift": round(drift_val,1)})
            if drift_summary:
                ds_df = pd.DataFrame(drift_summary).sort_values("Drift")
                ds_df["Direction"] = ds_df["Drift"].apply(lambda v: "→ More Liberal" if v < -5 else "→ More Conservative" if v > 5 else "Stable")
                fig_ds = go.Figure(go.Bar(
                    x=ds_df["Justice"], y=ds_df["Drift"],
                    marker_color=["#3498DB" if v < -5 else "#E74C3C" if v > 5 else "#95A5A6" for v in ds_df["Drift"]],
                    text=ds_df["Direction"], textposition="outside"))
                fig_ds.add_hline(y=0, line_color="#BDC3C7")
                fig_ds.update_layout(title="Ideological Drift (Recent − Early Conservative Alignment)",
                                      height=340, plot_bgcolor="white", paper_bgcolor="white",
                                      yaxis_title="Drift (% points)")
                st.plotly_chart(fig_ds)
                st.dataframe(ds_df.reset_index(drop=True), height=260, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: CONSTITUTIONAL DOCTRINE EVOLUTION
# ──────────────────────────────────────────────────────────────────────────────
with tab_doctrine:
    st.markdown("Trace the arc of major constitutional doctrines — from founding-era interpretations through modern retrenchments.")

    doctrine_sel = st.selectbox("Select Doctrine", list(DOCTRINES.keys()), key="doc_sel")
    doc_data = DOCTRINES[doctrine_sel]
    doc_color = doc_data["color"]

    st.markdown(f'<div style="border-left:5px solid {doc_color};padding:10px 16px;background:#F8F9FA;border-radius:0 6px 6px 0;">'
                f'{doc_data["summary"]}</div>', unsafe_allow_html=True)
    st.markdown("")

    milestones = doc_data["milestones"]
    years = [m[0] for m in milestones]; names = [m[1] for m in milestones]
    holdings = [m[2] for m in milestones]; directions = [m[3] for m in milestones]
    dot_colors = [MILESTONE_COLORS.get(d, "#F39C12") for d in directions]

    # Timeline figure
    fig_doc = go.Figure()
    # Spine
    fig_doc.add_trace(go.Scatter(x=years, y=[0]*len(years), mode="lines",
                                  line=dict(color="#BDC3C7", width=2), hoverinfo="skip", showlegend=False))
    # Dots
    fig_doc.add_trace(go.Scatter(x=years, y=[0]*len(years), mode="markers+text",
                                  marker=dict(size=18, color=dot_colors, line=dict(color="white", width=2)),
                                  text=[str(y) for y in years],
                                  textposition="top center", textfont=dict(size=9),
                                  hovertext=[f"<b>{n}</b> ({y})<br>{h}<br><i>{d}</i>"
                                             for n,y,h,d in zip(names,years,holdings,directions)],
                                  hoverinfo="text", showlegend=False))
    # Direction legend
    for dir_label, color in [("Expansion / Pro-Right","#27AE60"),("Contraction / Restriction","#E74C3C"),("Mixed / Other","#F39C12")]:
        fig_doc.add_trace(go.Scatter(x=[None],y=[None],mode="markers",
                                      marker=dict(size=10,color=color),name=dir_label,showlegend=True))
    fig_doc.update_layout(
        height=220, showlegend=True,
        xaxis=dict(range=[min(years)-8, max(years)+8], showgrid=False, zeroline=False, title="Year"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 0.8]),
        plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=20, r=20, t=20, b=30),
        legend=dict(x=0, y=1.1, orientation="h"),
    )
    st.plotly_chart(fig_doc)

    st.divider()
    st.subheader("Case-by-Case Breakdown")
    for i, (year, name, holding, direction) in enumerate(milestones):
        dir_color = MILESTONE_COLORS.get(direction, "#F39C12")
        with st.expander(f"**{name}** ({year}) — {direction}"):
            st.markdown(f'<span style="background:{dir_color};color:white;padding:2px 9px;'
                        f'border-radius:3px;font-size:0.85em;">{direction}</span>', unsafe_allow_html=True)
            st.markdown("")
            st.markdown(f"**Holding:** {holding}")
            if i > 0:
                prev_year, prev_name = milestones[i-1][0], milestones[i-1][1]
                st.markdown(f"*Previous milestone: {prev_name} ({prev_year})*")
            if i < len(milestones)-1:
                next_year, next_name = milestones[i+1][0], milestones[i+1][1]
                st.markdown(f"*Next milestone: {next_name} ({next_year})*")

    st.divider()
    st.subheader("All Doctrines — Direction Summary")
    all_doc_rows = []
    for doc_name, ddata in DOCTRINES.items():
        expansions = sum(1 for m in ddata["milestones"] if "expan" in m[3].lower() or "protection" in m[3].lower())
        contractions = sum(1 for m in ddata["milestones"] if "contract" in m[3].lower() or "restrict" in m[3].lower())
        total = len(ddata["milestones"])
        all_doc_rows.append({"Doctrine":doc_name,"Total Cases":total,
                              "Expansions":expansions,"Contractions":contractions})
    all_doc_df = pd.DataFrame(all_doc_rows)
    fig_all_doc = go.Figure()
    fig_all_doc.add_trace(go.Bar(name="Expansions",x=all_doc_df["Doctrine"],y=all_doc_df["Expansions"],marker_color="#27AE60"))
    fig_all_doc.add_trace(go.Bar(name="Contractions",x=all_doc_df["Doctrine"],y=all_doc_df["Contractions"],marker_color="#E74C3C"))
    fig_all_doc.update_layout(barmode="group",title="Doctrinal Direction Across All Tracked Doctrines",
                               xaxis_tickangle=-20,height=360,plot_bgcolor="white",paper_bgcolor="white",
                               legend=dict(x=1.01,y=1))
    st.plotly_chart(fig_all_doc)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: CONGRESSIONAL RESPONSE TRACKER
# ──────────────────────────────────────────────────────────────────────────────
with tab_congress:
    st.markdown(
        "When SCOTUS rules, Congress sometimes responds — through constitutional amendments, new legislation, "
        "or sometimes… nothing at all. Explore the history of the constitutional dialogue between the two branches."
    )

    # Summary metrics
    c_df = pd.DataFrame(CONGRESS_RESPONSES)
    succeeded_n = c_df["succeeded"].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total SCOTUS Responses Tracked", len(c_df))
    m2.metric("✅ Successful Legislative Responses", int(succeeded_n))
    m3.metric("❌ Failed / No Action", int(len(c_df) - succeeded_n))
    m4.metric("Constitutional Amendments", int((c_df["response_type"]=="Constitutional Amendment").sum()))
    st.divider()

    # Filter
    col_f_cr, col_f_rt = st.columns(2)
    with col_f_cr: show_succeeded = st.selectbox("Filter by outcome", ["All","Succeeded","Failed / No Action"], key="cr_filter")
    with col_f_rt: resp_type_filter = st.selectbox("Filter by type", ["All"] + sorted(c_df["response_type"].unique().tolist()), key="cr_type")

    filtered_cr = CONGRESS_RESPONSES
    if show_succeeded == "Succeeded":   filtered_cr = [r for r in filtered_cr if r["succeeded"]]
    elif show_succeeded == "Failed / No Action": filtered_cr = [r for r in filtered_cr if not r["succeeded"]]
    if resp_type_filter != "All": filtered_cr = [r for r in filtered_cr if r["response_type"]==resp_type_filter]

    # Timeline
    tl_df_cr = pd.DataFrame([r for r in filtered_cr if r.get("law_year")])
    if not tl_df_cr.empty:
        tl_df_cr["Response Time (years)"] = tl_df_cr["law_year"] - tl_df_cr["case_year"]
        fig_tl_cr = px.scatter(tl_df_cr, x="law_year", y="response_type",
                                size="Response Time (years)", color="response_type",
                                hover_name="case", hover_data={"case_year":True,"amendment_or_law":True},
                                title="Congressional Responses Timeline",
                                category_orders={"response_type":["Constitutional Amendment","Federal Legislation"]},
                                color_discrete_sequence=["#E74C3C","#3498DB"])
        fig_tl_cr.update_traces(marker=dict(opacity=0.8))
        fig_tl_cr.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white",
                                  xaxis_title="Year Response Enacted", yaxis_title="",
                                  showlegend=False, margin=dict(l=20,r=20,t=50,b=40))
        st.plotly_chart(fig_tl_cr)

    # Response cards
    for r in sorted(filtered_cr, key=lambda x: -x["case_year"]):
        succeed_color = "#27AE60" if r["succeeded"] else "#E74C3C"
        succeed_icon  = "✅" if r["succeeded"] else "❌"
        years_elapsed = f"{r['law_year'] - r['case_year']} years later" if r.get("law_year") else "Not enacted"
        with st.expander(f"{succeed_icon} **{r['case']}** ({r['case_year']}) → **{r['amendment_or_law']}**"):
            col1_cr, col2_cr = st.columns([2,1])
            with col1_cr:
                st.markdown(f"**Description:** {r['description']}")
                st.markdown(f"**Partisan context:** *{r['partisan_context']}*")
            with col2_cr:
                st.markdown(f'<div style="background:{succeed_color}18;border-left:4px solid {succeed_color};padding:8px;border-radius:4px;">'
                             f'<strong>Outcome:</strong> {"Succeeded" if r["succeeded"] else "Failed / Not enacted"}<br>'
                             f'<strong>Type:</strong> {r["response_type"]}<br>'
                             f'<strong>Congress:</strong> {r["congress"]}<br>'
                             f'<strong>Timing:</strong> {years_elapsed}</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Response Time Distribution")
    responded_df = pd.DataFrame([r for r in CONGRESS_RESPONSES if r.get("law_year") and r["succeeded"]])
    if not responded_df.empty:
        responded_df["Years to Respond"] = responded_df["law_year"] - responded_df["case_year"]
        responded_df = responded_df.sort_values("Years to Respond")
        fig_rt = go.Figure(go.Bar(x=responded_df["case"], y=responded_df["Years to Respond"],
                                   marker_color=["#27AE60" if y<=5 else "#F39C12" if y<=20 else "#E74C3C"
                                                 for y in responded_df["Years to Respond"]],
                                   text=responded_df["Years to Respond"].apply(lambda v: f"{v}yr"),
                                   textposition="outside"))
        fig_rt.update_layout(title="Years Between SCOTUS Decision and Congressional Response",
                              xaxis_tickangle=-30, height=360, plot_bgcolor="white", paper_bgcolor="white",
                              yaxis_title="Years")
        st.plotly_chart(fig_rt)
        fast = responded_df.loc[responded_df["Years to Respond"].idxmin()]
        slow = responded_df.loc[responded_df["Years to Respond"].idxmax()]
        col_rt1, col_rt2, col_rt3 = st.columns(3)
        col_rt1.metric("Average Response Time", f"{responded_df['Years to Respond'].mean():.0f} years")
        col_rt2.metric("Fastest Response", f"{fast['Years to Respond']}yr", fast["case"][:30])
        col_rt3.metric("Slowest Response", f"{slow['Years to Respond']}yr", slow["case"][:30])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: JUSTICE REPLACEMENT SIMULATOR
# ──────────────────────────────────────────────────────────────────────────────
with tab_replace:
    st.markdown(
        "**Counterfactual analysis:** Select a sitting justice and a hypothetical replacement ideology. "
        "See how key recent decisions would have turned out differently."
    )

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        replace_justice = st.selectbox("Justice to Replace", [j["name"] for j in CURRENT_COURT], key="rep_j")
    with col_r2:
        new_lean = st.selectbox("Replacement Lean", ["Liberal","Moderate","Conservative"], key="rep_lean")
    with col_r3:
        show_all = st.checkbox("Show all tracked cases (not just flipped)", value=False, key="rep_all")

    def _simulate_outcome(case_dict: dict, replace_name: str, new_lean: str) -> dict:
        majority = list(case_dict["majority"]); dissent = list(case_dict["dissent"])
        total = len(majority) + len(dissent)
        original_outcome = "Majority wins" # simplified

        # Replace the justice with the new lean
        new_majority = [j for j in majority if j != replace_name]
        new_dissent  = [j for j in dissent  if j != replace_name]
        orig_lean = next((j["lean"] for j in CURRENT_COURT if j["name"]==replace_name), "Moderate")

        # Determine how the replacement votes
        # Replacement votes like their lean
        if new_lean == "Conservative":
            # Votes with the majority if it's conservative
            cons_majority = sum(1 for j in majority if any(jj["name"]==j and jj["lean"]=="Conservative" for jj in CURRENT_COURT))
            lib_majority  = sum(1 for j in majority if any(jj["name"]==j and jj["lean"]=="Liberal"       for jj in CURRENT_COURT))
            if cons_majority >= lib_majority: new_majority.append("Replacement")
            else:                              new_dissent.append("Replacement")
        elif new_lean == "Liberal":
            lib_majority = sum(1 for j in majority if any(jj["name"]==j and jj["lean"]=="Liberal" for jj in CURRENT_COURT))
            cons_majority= sum(1 for j in majority if any(jj["name"]==j and jj["lean"]=="Conservative" for jj in CURRENT_COURT))
            if lib_majority >= cons_majority: new_majority.append("Replacement")
            else:                              new_dissent.append("Replacement")
        else:  # Moderate
            if len(majority) >= len(dissent): new_majority.append("Replacement")
            else:                              new_dissent.append("Replacement")

        new_maj_count = len(new_majority); new_dis_count = len(new_dissent)
        # Check if outcome flipped
        original_margin = len(majority) - len(dissent)
        new_margin       = new_maj_count - new_dis_count
        flipped = (original_margin > 0 and new_margin <= 0) or (original_margin < 0 and new_margin >= 0)
        return {
            "new_majority": new_majority, "new_dissent": new_dissent,
            "new_split": f"{new_maj_count}-{new_dis_count}",
            "flipped": flipped, "original_margin": original_margin, "new_margin": new_margin,
        }

    # Run simulation
    sim_results = []
    for case_d in KEY_FIVE_FOUR:
        sim = _simulate_outcome(case_d, replace_justice, new_lean)
        sim_results.append({**case_d, **sim})

    flipped_n = sum(1 for s in sim_results if s["flipped"])
    st.markdown(f"**Replacing {replace_justice} with a {new_lean} justice would flip {flipped_n}/{len(sim_results)} recent decisions.**")

    if flipped_n > 0:
        st.markdown(f'<div style="background:#E74C3C18;border-left:4px solid #E74C3C;padding:10px 16px;border-radius:4px;">'
                    f'⚠️ <strong>{flipped_n} cases would have been decided differently</strong> with a {new_lean} replacement for {replace_justice}.</div>',
                    unsafe_allow_html=True)
        st.markdown("")

    # Court balance bar
    cur_court_leans = [j["lean"] for j in CURRENT_COURT if j["name"] != replace_justice]
    cur_court_leans.append(new_lean)
    new_cons = cur_court_leans.count("Conservative"); new_lib = cur_court_leans.count("Liberal"); new_mod = cur_court_leans.count("Moderate")
    orig_cons = sum(1 for j in CURRENT_COURT if j["lean"]=="Conservative")
    orig_lib  = sum(1 for j in CURRENT_COURT if j["lean"]=="Liberal")
    orig_mod  = sum(1 for j in CURRENT_COURT if j["lean"]=="Moderate")
    col_orig, col_new = st.columns(2)
    with col_orig:
        st.markdown("**Current Court**")
        fig_orig = go.Figure(go.Bar(x=["Conservative","Moderate","Liberal"],y=[orig_cons,orig_mod,orig_lib],
                                     marker_color=["#E74C3C","#F39C12","#3498DB"],text=[orig_cons,orig_mod,orig_lib],textposition="outside"))
        fig_orig.update_layout(height=200,yaxis=dict(range=[0,8]),plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=20,r=20,t=10,b=30))
        st.plotly_chart(fig_orig)
    with col_new:
        st.markdown(f"**After Replacing {replace_justice} with {new_lean}**")
        fig_new = go.Figure(go.Bar(x=["Conservative","Moderate","Liberal"],y=[new_cons,new_mod,new_lib],
                                    marker_color=["#E74C3C","#F39C12","#3498DB"],text=[new_cons,new_mod,new_lib],textposition="outside"))
        fig_new.update_layout(height=200,yaxis=dict(range=[0,8]),plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=20,r=20,t=10,b=30))
        st.plotly_chart(fig_new)

    st.divider()
    st.subheader("Case-by-Case Simulation Results")
    for s in sorted(sim_results, key=lambda x: (-x["flipped"], x["case"])):
        if not show_all and not s["flipped"]: continue
        flip_color = "#E74C3C" if s["flipped"] else "#27AE60"
        flip_label = "⚠️ FLIPPED" if s["flipped"] else "✅ Same Outcome"
        orig_split = f"{len(s['majority'])}-{len(s['dissent'])}"
        new_split_val = s["new_split"]
        with st.expander(f'{flip_label} — **{s["case"]}** ({s["term"]}) | {s["issue"]} | Originally {orig_split} → Now {new_split_val}'):
            c1_sim, c2_sim = st.columns(2)
            with c1_sim:
                st.markdown("**Original Outcome**")
                st.markdown(f'<span style="background:#27AE60;color:white;padding:3px 10px;border-radius:3px;">Majority ({len(s["majority"])}): {", ".join(s["majority"])}</span>', unsafe_allow_html=True)
                st.markdown(f'<span style="background:#E74C3C;color:white;padding:3px 10px;border-radius:3px;">Dissent ({len(s["dissent"])}): {", ".join(s["dissent"])}</span>', unsafe_allow_html=True)
                st.markdown(f"**Outcome:** {s['outcome']}")
            with c2_sim:
                st.markdown(f"**With {new_lean} Replacement for {replace_justice}**")
                new_maj_color = "#27AE60" if s["new_margin"] > 0 else "#E74C3C"
                new_dis_color = "#E74C3C" if s["new_margin"] > 0 else "#27AE60"
                st.markdown(f'<span style="background:{new_maj_color};color:white;padding:3px 10px;border-radius:3px;">New Majority ({len(s["new_majority"])}): {", ".join(s["new_majority"])}</span>', unsafe_allow_html=True)
                st.markdown(f'<span style="background:{new_dis_color};color:white;padding:3px 10px;border-radius:3px;">New Dissent ({len(s["new_dissent"])}): {", ".join(s["new_dissent"])}</span>', unsafe_allow_html=True)
                if s["flipped"]:
                    st.markdown(f'<div style="background:#E74C3C22;padding:6px;border-radius:4px;"><strong>⚠️ Outcome Reversed</strong></div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Sensitivity Analysis: All Possible Replacements")
    st.markdown("How many tracked decisions would flip for each possible replacement?")
    sensitivity_rows = []
    for j in CURRENT_COURT:
        for lean in ["Liberal","Moderate","Conservative"]:
            if j["lean"] == lean: continue  # no change
            flipped_count = sum(1 for case_d in KEY_FIVE_FOUR if _simulate_outcome(case_d, j["name"], lean)["flipped"])
            sensitivity_rows.append({"Replace": j["name"], "With": lean, "Cases Flipped": flipped_count})
    sens_df = pd.DataFrame(sensitivity_rows)
    fig_sens = px.density_heatmap(sens_df, x="Replace", y="With", z="Cases Flipped",
                                   color_continuous_scale="RdYlGn_r", title="Sensitivity: Cases Flipped by Replacement Scenario",
                                   text_auto=True)
    fig_sens.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig_sens)
