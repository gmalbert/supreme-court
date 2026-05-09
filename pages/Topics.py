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
from utils.oyez_api import extract_court_journey, get_cases_by_term, get_case_detail
from utils.local_data import strip_html, safe_md, infer_issue_area


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

@st.cache_data(show_spinner=False)
def _lt_fetch_cases_term(term: int) -> list[dict]:
    return get_cases_by_term(term)

@st.cache_data(show_spinner=False)
def _lt_fetch_case(href: str) -> dict | None:
    return get_case_detail(href)

@st.cache_data(show_spinner=False)
def _lt_load_dispositions() -> dict:
    """Load precomputed dispositions cache (built once from all local detail files).
    Returns {href: {name, term, decision_type, winning_party}}."""
    import json as _json
    from utils.local_data import DATA_DIR
    cache_path = os.path.join(DATA_DIR, "dispositions_cache.json")
    if os.path.isfile(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            return _json.load(fh)
    return {}
    return result

def _lt_issue_label(c: dict) -> str:
    return infer_issue_area(c)

def _lt_disp_label(c: dict) -> str:
    d = c.get("disposition")
    if isinstance(d, dict): return d.get("label","Unknown")
    return str(d) if d else "Unknown"

# ── Page ─────────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import networkx as nx
import pandas as pd


# ── Page ─────────────────────────────────────────────────────────────────────

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
            (2024, "United States v. Rahimi", "Federal firearms ban for those under domestic violence restraining orders upheld.", "Restriction"),
            (2024, "Garland v. Cargill", "Bump stocks do not qualify as machine guns under federal law.", "Expansion"),

        ]},
    "Criminal Procedure (4th–6th Amendments)": {
        "color": "#27AE60",
        "summary": "The Warren Court revolution in criminal rights — and subsequent limits — transformed police procedure and trial rights.",
        "milestones": [
            (1961, "Mapp v. Ohio", "Exclusionary rule applied to states: illegally seized evidence inadmissible.", "Expansion"),
            (1963, "Gideon v. Wainwright", "Right to counsel in all felony cases incorporated against states.", "Expansion"),
            (1966, "Miranda v. Arizona", "Police must warn suspects of rights before custodial interrogation.", "Expansion"),
            (1968, "Terry v. Ohio", "Stop-and-frisk under reasonable suspicion permitted; limit on expansion.", "Restriction"),
            (1984, "United States v. Leon", "Good-faith exception to exclusionary rule created.", "Restriction"),
            (1984, "Strickland v. Washington", "Two-part test for ineffective assistance of counsel; high bar to overturn convictions.", "Restriction"),
            (2004, "Crawford v. Washington", "Testimonial hearsay rule strengthened; Confrontation Clause revitalized.", "Expansion"),
            (2010, "Padilla v. Kentucky", "Defense counsel must advise on deportation consequences of guilty plea.", "Expansion"),
            (2012, "Missouri v. Frye", "Sixth Amendment right to counsel applies to plea bargaining.", "Expansion"),
            (2014, "Riley v. California", "Cell phone search incident to arrest requires warrant.", "Expansion"),
            (2018, "Carpenter v. United States", "Warrant required for historical cell-site location data.", "Expansion"),
            (2020, "Ramos v. Louisiana", "Unanimous jury verdict required; non-unanimous convictions overturned.", "Expansion"),
        ]},
    "Voting Rights": {
        "color": "#2C3E50",
        "summary": "From 'one person, one vote' to the decline of federal oversight — the shifting boundaries of voting rights.",
        "milestones": [
            (1962, "Baker v. Carr", "Malapportionment of legislative districts is a justiciable issue.", "Expansion"),
            (1964, "Reynolds v. Sims", "One person, one vote: state legislative districts must be roughly equal.", "Expansion"),
            (1966, "Harper v. Virginia Board of Elections", "Poll taxes in state elections violate equal protection.", "Expansion"),
            (1966, "South Carolina v. Katzenbach", "Voting Rights Act preclearance requirements upheld under 15th Amendment.", "Expansion"),
            (1993, "Shaw v. Reno", "Racial gerrymandering can itself be unconstitutional; strict scrutiny applies.", "Mixed"),
            (2000, "Bush v. Gore", "Florida presidential recount halted; equal protection violation in inconsistent standards.", "Restriction"),
            (2009, "Northwest Austin Municipal Utility District v. Holder", "Preclearance requirements questioned; VRA not struck but signal sent.", "Mixed"),
            (2013, "Shelby County v. Holder", "VRA coverage formula struck down; preclearance rendered ineffective.", "Contraction"),
            (2019, "Rucho v. Common Cause", "Partisan gerrymandering is a political question beyond federal court reach.", "Contraction"),
            (2021, "Brnovich v. Democratic National Committee", "Arizona voting restrictions upheld; Section 2 VRA interpreted narrowly.", "Contraction"),
            (2023, "Allen v. Milligan", "Alabama congressional map violates VRA Section 2; Roberts joins liberals.", "Expansion"),
            (2023, "Moore v. Harper", "Independent state legislature theory rejected; federal courts may review state election law decisions.", "Expansion"),
        ]},
    "Separation of Powers": {
        "color": "#5D6D7E",
        "summary": "Defining the limits of presidential, congressional, and judicial power across 70+ years.",
        "milestones": [
            (1952, "Youngstown Sheet & Tube v. Sawyer", "President cannot seize steel mills without Congress; Jackson's three-zone framework.", "Contraction"),
            (1974, "United States v. Nixon", "Executive privilege is not absolute; President must comply with judicial subpoena.", "Contraction"),
            (1983, "INS v. Chadha", "Legislative veto by one chamber is unconstitutional.", "Contraction"),
            (1988, "Morrison v. Olson", "Independent counsel statute upheld; Scalia's dissent becomes doctrine later.", "Expansion"),
            (1997, "Printz v. United States", "Federal government cannot commandeer state executive officers.", "Contraction"),
            (1998, "Clinton v. City of New York", "Line Item Veto Act struck down.", "Contraction"),
            (2004, "Hamdi v. Rumsfeld", "President cannot indefinitely detain U.S. citizens without meaningful review.", "Contraction"),
            (2008, "Boumediene v. Bush", "Guantanamo detainees have habeas corpus rights; Congress cannot strip jurisdiction.", "Contraction"),
            (2014, "NLRB v. Noel Canning", "President's recess appointments invalid during pro forma Senate sessions.", "Contraction"),
            (2020, "Seila Law v. CFPB", "CFPB single-director removal restriction violates separation of powers.", "Contraction"),
            (2024, "Trump v. United States", "Former presidents have absolute immunity for core constitutional acts.", "Expansion"),
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
    dict(case="Bostock v. Clayton County", case_year=2020, amendment_or_law="Equality Act (proposed)", law_year=None,
         response_type="Federal Legislation (Failed)", congress="117th Congress",
         description="Proposed legislation to expand explicit anti-discrimination protections for LGBTQ+ people. Passed the House but stalled in the Senate.",
         partisan_context="Senate filibuster blocked passage; no Republican support.",
         succeeded=False),
    dict(case="Rucho v. Common Cause", case_year=2019, amendment_or_law="For the People Act / Freedom to Vote Act (proposed)", law_year=None,
         response_type="Federal Legislation (Failed)", congress="117th Congress",
         description="Bills that would have created federal standards for redistricting and limiting partisan gerrymandering. Failed to overcome the Senate filibuster.",
         partisan_context="No Republican support; Democrat Joe Manchin opposed carving out a filibuster exception.",
         succeeded=False),
    dict(case="West Virginia v. EPA", case_year=2022, amendment_or_law="Inflation Reduction Act (IRA)", law_year=2022,
         response_type="Federal Legislation", congress="117th Congress",
         description="The IRA was passed weeks after West Virginia v. EPA, explicitly delegating authority to EPA for climate-related programs through the tax code and clean energy incentives.",
         partisan_context="Passed on party-line vote via budget reconciliation.",
         succeeded=True),
    dict(case="Kelo v. City of New London", case_year=2005, amendment_or_law="State eminent domain reform laws (40+ states)", law_year=2006,
         response_type="State Legislation", congress="State level",
         description="Over 40 states passed laws restricting eminent domain for economic development purposes within 2 years of Kelo, making it one of the most repudiated SCOTUS decisions at the state level.",
         partisan_context="Bipartisan state-level backlash; unusual coalition of conservatives and liberals.",
         succeeded=True),
    dict(case="Dobbs v. Jackson Women's Health Org.", case_year=2022, amendment_or_law="State abortion bans and protections", law_year=2022,
         response_type="State Legislation", congress="State level",
         description="21 states enacted or enforced abortion bans within 2 years; 7 states plus DC codified or expanded abortion rights into state law or constitution.",
         partisan_context="Sharply polarized state-level response along party lines.",
         succeeded=True),
    dict(case="Gonzales v. Raich", case_year=2005, amendment_or_law="State marijuana legalization (24 states + DC)", law_year=2012,
         response_type="State Legislation", congress="State level",
         description="Colorado and Washington (2012) became first states to legalize recreational marijuana; 24 states have since followed. Federal law unchanged despite SCOTUS upholding federal authority.",
         partisan_context="State-level democratic override of federal policy; Congress has not decriminalized.",
         succeeded=True),
    dict(case="Loper Bright Enterprises v. Raimondo", case_year=2024, amendment_or_law="Proposed REINS Act / regulatory reform bills", law_year=None,
         response_type="Federal Legislation (Pending)", congress="118th/119th Congress",
         description="Bills to codify or modify the post-Chevron framework are pending. Some Republicans want even less deference; Democrats want to restore a Chevron-like regime.",
         partisan_context="Contested in a divided Congress.",
         succeeded=False),
     
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
    dict(case="Trump v. United States", term=2023, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Executive Power / Presidential Immunity", outcome="Absolute immunity for core presidential acts; presumptive immunity for official acts"),
    dict(case="Garland v. Cargill (bump stocks)", term=2023, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Second Amendment / Administrative Law", outcome="Bump stocks not classified as machine guns under federal law"),
    dict(case="Corner Post v. Board of Governors", term=2023, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Administrative Law / APA", outcome="APA statute of limitations runs from plaintiff's injury, not rule issuance"),
    dict(case="United States v. Rahimi", term=2023, split="8-1",
         majority=["Roberts","Sotomayor","Kagan","Kavanaugh","Barrett","Jackson","Gorsuch","Alito"],
         dissent=["Thomas"],
         issue="Second Amendment", outcome="Federal domestic violence firearm ban upheld under historical tradition test"),
    dict(case="Moore v. Harper", term=2022, split="6-3",
         majority=["Roberts","Sotomayor","Kagan","Kavanaugh","Barrett","Jackson"],
         dissent=["Thomas","Alito","Gorsuch"],
         issue="Elections / State Power", outcome="Independent state legislature theory rejected"),
    dict(case="Allen v. Milligan", term=2022, split="5-4",
         majority=["Roberts","Sotomayor","Kagan","Kavanaugh","Jackson"],
         dissent=["Thomas","Alito","Gorsuch","Barrett"],
         issue="Voting Rights / Racial Gerrymandering", outcome="Alabama congressional map violates VRA Section 2"),
    dict(case="National Pork Producers Council v. Ross", term=2022, split="5-4",
         majority=["Gorsuch","Thomas","Sotomayor","Kagan","Jackson"],
         dissent=["Roberts","Alito","Kavanaugh","Barrett"],
         issue="Commerce Clause / Dormant Commerce Clause", outcome="California pork regulations upheld; Proposition 12 constitutional"),
    dict(case="Sackett v. EPA", term=2022, split="9-0 (5-4 on scope)",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett","Sotomayor","Kagan","Jackson"],
         dissent=[],
         issue="Administrative Law / Environment", outcome="EPA wetlands jurisdiction requires continuous surface connection to navigable waters"),
    dict(case="Haaland v. Brackeen", term=2022, split="7-2",
         majority=["Roberts","Sotomayor","Kagan","Kavanaugh","Barrett","Jackson","Thomas"],
         dissent=["Alito","Gorsuch"],
         issue="Federal Indian Law / Federalism", outcome="Indian Child Welfare Act upheld as valid exercise of federal power"),
    dict(case="Counterman v. Colorado", term=2022, split="7-2",
         majority=["Kagan","Roberts","Sotomayor","Kavanaugh","Barrett","Jackson","Alito"],
         dissent=["Thomas","Gorsuch"],
         issue="First Amendment / True Threats", outcome="'True threats' require recklessness as to threatening nature, not just objective standard"),
    dict(case="Biden v. Nebraska (student debt)", term=2022, split="6-3",
         majority=["Roberts","Thomas","Alito","Gorsuch","Kavanaugh","Barrett"],
         dissent=["Sotomayor","Kagan","Jackson"],
         issue="Education / Executive Power / Major Questions", outcome="$400B student debt cancellation blocked; major questions doctrine applied"),
]    


# ── Page ─────────────────────────────────────────────────────────────────────

def _page_legal_topics():
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
        _term_range_ia = list(range(CURRENT_YEAR-1, 1989, -1))
        with col1_ia: issue_ia = st.selectbox("Legal Issue Area",ISSUE_AREAS_LT,key="ia_issue")
        with col2_ia: start_term_ia = st.selectbox("From Term",_term_range_ia,index=10,key="ia_start")
        with col3_ia: end_term_ia   = st.selectbox("To Term",_term_range_ia,index=0,key="ia_end")
        if start_term_ia > end_term_ia: start_term_ia, end_term_ia = end_term_ia, start_term_ia
        terms_ia = list(range(start_term_ia, end_term_ia+1))

        if st.button("Load Decisions",type="primary",key="ia_btn"):
            rows_ia = []
            progress_ia = st.progress(0)
            disp_cache = _lt_load_dispositions()
            for idx, term in enumerate(sorted(terms_ia,reverse=True)):
                cases = _lt_fetch_cases_term(term)
                for c in cases:
                    label = _lt_issue_label(c)
                    if issue_ia.lower() in label.lower():
                        href = c.get("href","")
                        cached = disp_cache.get(href, {})
                        dec_type = (cached.get("decision_type") or "").strip()
                        winner   = (cached.get("winning_party") or "").strip()
                        disp     = f"{dec_type.title()} \u2014 {winner}" if dec_type and winner else (dec_type.title() or winner or "Unknown")
                        chart_cat = dec_type.title() or "Unknown"
                        rows_ia.append({"Term":term,"Case":c.get("name",""),
                                        "Disposition":disp,"Decision Type":chart_cat,
                                        "Issue Area":label,"href":href})
                progress_ia.progress((idx+1)/len(terms_ia))
            progress_ia.empty()
            st.session_state["ia_rows"] = rows_ia; st.session_state["ia_area"] = issue_ia

        if "ia_rows" in st.session_state and st.session_state.get("ia_area") == issue_ia:
            rows_ia_data = st.session_state["ia_rows"]
            if not rows_ia_data:
                st.warning(f"No cases found for '{issue_ia}' in the selected range.")
            else:
                df_ia = pd.DataFrame(rows_ia_data)
                # Back-compat: old session state rows may lack "Decision Type"
                if "Decision Type" not in df_ia.columns:
                    _VALID_DEC_TYPES = {"Majority Opinion", "Per Curiam", "Plurality Opinion",
                                        "Dismissal - Improvidently Granted", "Equally Divided", "Unknown"}
                    _derived = df_ia["Disposition"].str.split(" \u2014 ").str[0].str.strip().fillna("Unknown")
                    df_ia["Decision Type"] = _derived.where(_derived.isin(_VALID_DEC_TYPES), "Unknown")
                st.success(f"Found **{len(df_ia)}** decisions in **{issue_ia}** from {start_term_ia}–{end_term_ia}.")
                col_pie_ia, col_trend_ia = st.columns(2)
                with col_pie_ia:
                    dt_counts_ia = df_ia["Decision Type"].value_counts().reset_index()
                    dt_counts_ia.columns = ["Decision Type","Count"]
                    fig_pie_ia = px.pie(dt_counts_ia, names="Decision Type", values="Count",
                                        title=f"{issue_ia} — Decision Outcomes", hole=0.4,
                                        color_discrete_sequence=px.colors.qualitative.Set2)
                    fig_pie_ia.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pie_ia.update_layout(height=330, showlegend=False)
                    st.plotly_chart(fig_pie_ia)
                with col_trend_ia:
                    term_counts_ia = df_ia.groupby("Term").size().reset_index(name="Cases")
                    fig_trend_ia = px.bar(term_counts_ia.sort_values("Term"),x="Term",y="Cases",
                                          title=f"{issue_ia} — Cases per Term",color="Cases",color_continuous_scale="Blues")
                    fig_trend_ia.update_layout(height=330,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_trend_ia)
                st.subheader("Case List")
                disp_filter_ia = st.multiselect("Filter by Decision Type",sorted(df_ia["Decision Type"].unique()),default=[],key="ia_disp_filter")
                display_ia = df_ia[df_ia["Decision Type"].isin(disp_filter_ia)] if disp_filter_ia else df_ia
                display_ia = display_ia[["Term","Case","Disposition"]].sort_values("Term",ascending=False)
                st.dataframe(display_ia, hide_index=True, height=400)
                st.divider(); st.subheader("Case Drilldown")
                case_names_ia = sorted(df_ia["Case"].tolist())
                sel_case_ia = st.selectbox("Select a case to inspect",case_names_ia,key="ia_case_sel")
                row_ia = df_ia[df_ia["Case"]==sel_case_ia].iloc[0]
                if row_ia.get("href"):
                    with st.spinner("Loading case details..."):
                        detail_ia = _lt_fetch_case(row_ia["href"])
                    if detail_ia:
                        question_ia = detail_ia.get("question",""); facts_ia = detail_ia.get("facts_of_the_case","") or detail_ia.get("description","")
                        col_q_ia, col_f_ia = st.columns(2)
                        with col_q_ia:
                            if question_ia: st.markdown("**Legal Question**"); st.write(safe_md(question_ia))
                        with col_f_ia:
                            if facts_ia: st.markdown("**Background**"); st.write(safe_md(facts_ia))
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
            "1st Amendment — Free Speech & Press": {
                "summary":"Prohibits Congress from abridging freedom of speech or press.",
                "color":"#2980B9",
                "cases":[
                    ("Schenck v. United States (1919)","https://api.oyez.org/cases/1900-1940/249us47","Upheld anti-draft pamphlet conviction; established 'clear and present danger' test.",1919),
                    ("New York Times v. Sullivan (1964)","https://api.oyez.org/cases/1963/39","Required 'actual malice' for defamation claims by public officials.",1964),
                    ("Tinker v. Des Moines (1969)","https://api.oyez.org/cases/1968/21","Student anti-war armbands protected; schools cannot suppress speech without substantial disruption.",1969),
                    ("Brandenburg v. Ohio (1969)","https://api.oyez.org/cases/1968/492","Protected inflammatory speech unless directed to incite imminent lawless action.",1969),
                    ("New York Times v. United States (1971)","https://api.oyez.org/cases/1970/1873","Prior restraint on Pentagon Papers publication rejected.",1971),
                    ("Cohen v. California (1971)","https://api.oyez.org/cases/1970/299","Offensive language on clothing in public spaces is protected speech.",1971),
                    ("Buckley v. Valeo (1976)","https://api.oyez.org/cases/1975/75-436","Campaign expenditures are protected speech; contribution limits narrowly upheld.",1976),
                    ("Hustler Magazine v. Falwell (1988)","https://api.oyez.org/cases/1987/86-1278","Public figures cannot recover for intentional infliction of emotional distress from parody.",1988),
                    ("Hazelwood School District v. Kuhlmeier (1988)","https://api.oyez.org/cases/1987/86-836","Schools may exercise editorial control over school-sponsored newspapers.",1988),
                    ("Texas v. Johnson (1989)","https://api.oyez.org/cases/1988/88-155","Flag burning is protected symbolic speech.",1989),
                    ("R.A.V. v. City of St. Paul (1992)","https://api.oyez.org/cases/1991/90-7675","Hate speech ordinance targeting only certain topics of fighting words is unconstitutional.",1992),
                    ("Reno v. ACLU (1997)","https://api.oyez.org/cases/1996/96-511","CDA indecency provisions unconstitutionally restricted online speech.",1997),
                    ("United States v. Stevens (2010)","https://api.oyez.org/cases/2009/08-769","Federal law criminalizing depictions of animal cruelty struck down as overbroad.",2010),
                    ("Citizens United v. FEC (2010)","https://api.oyez.org/cases/2008/08-205","Corporate political spending is protected speech; campaign finance limits struck.",2010),
                    ("Snyder v. Phelps (2011)","https://api.oyez.org/cases/2010/09-751","Westboro Baptist Church's funeral protests are protected speech on public concern.",2011),
                    ("United States v. Alvarez (2012)","https://api.oyez.org/cases/2011/11-210","Stolen Valor Act's ban on lying about military medals violates the First Amendment.",2012),
                    ("McCullen v. Coakley (2014)","https://api.oyez.org/cases/2013/12-1168","Fixed buffer zones around abortion clinics violate free speech rights of protesters.",2014),
                    ("Matal v. Tam (2017)","https://api.oyez.org/cases/2016/15-1293","Government cannot deny trademark registration based on group disparagement.",2017),
                    ("303 Creative v. Elenis (2023)","https://api.oyez.org/cases/2022/21-476","Designer cannot be compelled to create content for same-sex weddings.",2023),
                    ("Moody v. NetChoice (2024)","https://api.oyez.org/cases/2023/22-555","State social-media content moderation laws remanded for full First Amendment analysis.",2024),
                ]},
            "1st Amendment — Establishment & Free Exercise": {
                "summary":"Prohibits establishment of religion; guarantees free exercise thereof.",
                "color":"#1A6FA3",
                "cases":[
                    ("Engel v. Vitale (1962)","https://api.oyez.org/cases/1961/468","State-composed school prayer violates Establishment Clause.",1962),
                    ("Abington School District v. Schempp (1963)","https://api.oyez.org/cases/1962/142","Bible readings in public schools unconstitutional.",1963),
                    ("Lemon v. Kurtzman (1971)","https://api.oyez.org/cases/1970/89","Three-part Lemon test established for Establishment Clause cases.",1971),
                    ("Wisconsin v. Yoder (1972)","https://api.oyez.org/cases/1971/70-110","Amish families cannot be compelled to send children to school past 8th grade.",1972),
                    ("Lee v. Weisman (1992)","https://api.oyez.org/cases/1991/90-1014","Clergy-led prayers at public school graduation ceremonies unconstitutional.",1992),
                    ("Church of Lukumi Babalu Aye v. City of Hialeah (1993)","https://api.oyez.org/cases/1992/91-948","Ordinance targeting Santeria animal sacrifice violates Free Exercise Clause.",1993),
                    ("Employment Division v. Smith (1990)","https://api.oyez.org/cases/1989/88-1213","Neutral, generally applicable laws may burden religion without requiring exemption.",1990),
                    ("Rosenberger v. University of Virginia (1995)","https://api.oyez.org/cases/1994/94-329","University violated free speech by denying funding to student religious magazine.",1995),
                    ("Santa Fe Independent School District v. Doe (2000)","https://api.oyez.org/cases/1999/99-62","Student-led prayer over school PA before football games violates Establishment Clause.",2000),
                    ("Good News Club v. Milford Central School (2001)","https://api.oyez.org/cases/2000/99-2036","Excluding religious clubs from after-school access is unconstitutional viewpoint discrimination.",2001),
                    ("Zelman v. Simmons-Harris (2002)","https://api.oyez.org/cases/2001/00-1751","School voucher programs including parochial schools do not violate Establishment Clause.",2002),
                    ("Gonzales v. O Centro Espirita (2006)","https://api.oyez.org/cases/2005/04-1084","RFRA requires exemption for religious use of hoasca tea despite drug laws.",2006),
                    ("Town of Greece v. Galloway (2014)","https://api.oyez.org/cases/2013/12-696","Legislative prayer at town board meetings does not violate Establishment Clause.",2014),
                    ("Burwell v. Hobby Lobby (2014)","https://api.oyez.org/cases/2013/13-354","Closely-held corporations may claim religious exemptions under RFRA.",2014),
                    ("Trinity Lutheran Church v. Comer (2017)","https://api.oyez.org/cases/2016/15-577","State cannot deny church access to public playground resurfacing grant.",2017),
                    ("Masterpiece Cakeshop v. Colorado Civil Rights Commission (2018)","https://api.oyez.org/cases/2017/16-111","Commission showed religious hostility toward baker who refused same-sex wedding cake.",2018),
                    ("American Legion v. American Humanist Association (2019)","https://api.oyez.org/cases/2018/17-1717","40-foot WWI cross on public land permitted as long-standing historical monument.",2019),
                    ("Our Lady of Guadalupe School v. Morrissey-Berru (2020)","https://api.oyez.org/cases/2019/19-267","Ministerial exception bars employment discrimination claims by Catholic school teachers.",2020),
                    ("Fulton v. City of Philadelphia (2021)","https://api.oyez.org/cases/2020/19-123","City violated Free Exercise by excluding Catholic foster agency.",2021),
                    ("Carson v. Makin (2022)","https://api.oyez.org/cases/2021/20-1088","Maine cannot exclude religious schools from tuition assistance program.",2022),
                    ("Kennedy v. Bremerton School District (2022)","https://api.oyez.org/cases/2021/21-418","Public school coach's personal prayer on field protected; Lemon test abandoned.",2022),
                ]},
            "2nd Amendment — Right to Bear Arms": {
                "summary":"Protects the individual right to keep and bear arms.",
                "color":"#8E44AD",
                "cases":[
                    ("United States v. Miller (1939)","https://api.oyez.org/cases/1938/696","Sawed-off shotgun not protected; 2nd Amendment tied to militia purpose.",1939),
                    ("District of Columbia v. Heller (2008)","https://api.oyez.org/cases/2007/07-290","Recognized individual right to keep firearms in the home independent of militia service.",2008),
                    ("McDonald v. City of Chicago (2010)","https://api.oyez.org/cases/2009/08-1521","Incorporated the Second Amendment against state and local governments.",2010),
                    ("New York State Rifle & Pistol Assn. v. Bruen (2022)","https://api.oyez.org/cases/2021/20-843","Struck down NY concealed carry requirement; adopted historical tradition test.",2022),
                    ("United States v. Rahimi (2024)","https://api.oyez.org/cases/2023/22-915","Federal firearms ban for those under domestic violence restraining orders is constitutional.",2024),
                    ("Garland v. Cargill (2024)","https://api.oyez.org/cases/2023/22-976","Bump stocks do not qualify as machine guns under federal law.",2024),
                ]},
            "4th Amendment — Search & Seizure": {
                "summary":"Guards against unreasonable searches and seizures; requires warrants based on probable cause.",
                "color":"#E67E22",
                "cases":[
                    ("Mapp v. Ohio (1961)","https://api.oyez.org/cases/1960/236","Applied the exclusionary rule to the states — illegally seized evidence inadmissible.",1961),
                    ("Katz v. United States (1967)","https://api.oyez.org/cases/1967/35","Extended 4th Amendment to electronic surveillance; created 'reasonable expectation of privacy'.",1967),
                    ("Terry v. Ohio (1968)","https://api.oyez.org/cases/1967/67","Permitted police 'stop and frisk' based on reasonable suspicion.",1968),
                    ("Illinois v. Gates (1983)","https://api.oyez.org/cases/1982/81-430","Totality of circumstances test replaces rigid two-pronged test for probable cause.",1983),
                    ("United States v. Leon (1984)","https://api.oyez.org/cases/1983/82-1771","Good-faith exception: evidence obtained under defective warrant may be admissible.",1984),
                    ("New Jersey v. T.L.O. (1985)","https://api.oyez.org/cases/1984/83-712","School officials need only reasonable suspicion — not probable cause — to search students.",1985),
                    ("California v. Greenwood (1988)","https://api.oyez.org/cases/1987/86-684","No reasonable expectation of privacy in garbage left for collection.",1988),
                    ("Florida v. Bostick (1991)","https://api.oyez.org/cases/1990/89-1717","Police may board buses and ask for consent to search without 4th Amendment violation.",1991),
                    ("Vernonia School District v. Acton (1995)","https://api.oyez.org/cases/1994/94-590","Random drug testing of student athletes does not violate 4th Amendment.",1995),
                    ("Whren v. United States (1996)","https://api.oyez.org/cases/1995/95-5841","Traffic stop valid if officer observes any traffic violation regardless of subjective intent.",1996),
                    ("Illinois v. Caballes (2005)","https://api.oyez.org/cases/2004/03-923","Dog sniff of vehicle exterior during lawful traffic stop is not a search.",2005),
                    ("Georgia v. Randolph (2006)","https://api.oyez.org/cases/2005/04-1067","Co-occupant who refuses consent blocks warrantless search even if other consents.",2006),
                    ("Safford Unified School District v. Redding (2009)","https://api.oyez.org/cases/2008/08-479","Strip-searching a 13-year-old for ibuprofen violated the 4th Amendment.",2009),
                    ("Kentucky v. King (2011)","https://api.oyez.org/cases/2010/09-1272","Exigent circumstances exception applies when police create the situation prompting it.",2011),
                    ("United States v. Jones (2012)","https://api.oyez.org/cases/2011/10-1259","Attaching a GPS device to a vehicle constitutes a 4th Amendment search.",2012),
                    ("Florida v. Jardines (2013)","https://api.oyez.org/cases/2012/11-564","Using drug-sniffing dog at the front door of a home is a 4th Amendment search.",2013),
                    ("Missouri v. McNeely (2013)","https://api.oyez.org/cases/2012/11-1425","Police generally must obtain a warrant before drawing blood from a DUI suspect.",2013),
                    ("Riley v. California (2014)","https://api.oyez.org/cases/2013/13-132","Police must obtain a warrant before searching a cell phone incident to arrest.",2014),
                    ("Utah v. Strieff (2016)","https://api.oyez.org/cases/2015/14-1373","Evidence discovered after unlawful stop admissible where outstanding arrest warrant exists.",2016),
                    ("Carpenter v. United States (2018)","https://api.oyez.org/cases/2017/16-402","Government needs a warrant to access historical cell-site location information.",2018),
                    ("Kansas v. Glover (2020)","https://api.oyez.org/cases/2019/18-556","Reasonable for officer to assume registered owner is the driver of a vehicle.",2020),
                ]},
            "5th Amendment — Due Process, Self-Incrimination & Takings": {
                "summary":"Prohibits double jeopardy, self-incrimination, and deprivation of life/liberty/property without due process; requires just compensation for takings.",
                "color":"#C0392B",
                "cases":[
                    ("Miranda v. Arizona (1966)","https://api.oyez.org/cases/1965/759","Police must inform suspects of their rights before custodial interrogation.",1966),
                    ("Garrity v. New Jersey (1967)","https://api.oyez.org/cases/1966/13","Statements compelled under threat of job loss cannot be used in criminal prosecution.",1967),
                    ("Kastigar v. United States (1972)","https://api.oyez.org/cases/1971/70-117","Use immunity sufficient to compel testimony; transactional immunity not required.",1972),
                    ("Dolan v. City of Tigard (1994)","https://api.oyez.org/cases/1993/93-518","Government must show rough proportionality between development conditions and project impact.",1994),
                    ("Dickerson v. United States (2000)","https://api.oyez.org/cases/1999/99-5525","Congress cannot overrule Miranda with a statute; Miranda is a constitutional rule.",2000),
                    ("Kelo v. City of New London (2005)","https://api.oyez.org/cases/2004/04-108","Economic development qualifies as a public use under the Takings Clause.",2005),
                    ("Salinas v. Texas (2013)","https://api.oyez.org/cases/2012/12-246","Suspect must explicitly invoke 5th Amendment; pre-arrest silence can be used against them.",2013),
                    ("Horne v. Department of Agriculture (2015)","https://api.oyez.org/cases/2014/14-275","Government raisin reserve requirement constitutes a per se physical taking.",2015),
                    ("Gamble v. United States (2019)","https://api.oyez.org/cases/2017/17-646","Separate-sovereigns doctrine: federal and state prosecutions for same conduct not double jeopardy.",2019),
                ]},
            "6th Amendment — Right to Counsel & Fair Trial": {
                "summary":"Guarantees the right to a speedy trial, impartial jury, confrontation of witnesses, and assistance of counsel.",
                "color":"#27AE60",
                "cases":[
                    ("Gideon v. Wainwright (1963)","https://api.oyez.org/cases/1962/155","States must provide counsel to criminal defendants who cannot afford an attorney.",1963),
                    ("Pointer v. Texas (1965)","https://api.oyez.org/cases/1964/577","Confrontation Clause incorporated against states via 14th Amendment.",1965),
                    ("Barker v. Wingo (1972)","https://api.oyez.org/cases/1971/71-5255","Four-factor balancing test established for speedy trial claims.",1972),
                    ("Faretta v. California (1975)","https://api.oyez.org/cases/1974/73-5772","Defendants have a constitutional right to represent themselves at trial.",1975),
                    ("Strickland v. Washington (1984)","https://api.oyez.org/cases/1983/82-1554","Two-part test for ineffective assistance: deficient performance + resulting prejudice.",1984),
                    ("Batson v. Kentucky (1986)","https://api.oyez.org/cases/1985/84-6263","Prosecutors cannot use peremptory challenges to exclude jurors solely based on race.",1986),
                    ("Maryland v. Craig (1990)","https://api.oyez.org/cases/1989/89-478","Child abuse victims may testify via one-way closed-circuit TV in some circumstances.",1990),
                    ("Crawford v. Washington (2004)","https://api.oyez.org/cases/2003/02-9410","Testimonial statements of absent witnesses inadmissible without prior cross-examination.",2004),
                    ("Blakely v. Washington (2004)","https://api.oyez.org/cases/2003/02-1632","Sentence enhancements beyond statutory maximum must be submitted to a jury.",2004),
                    ("United States v. Booker (2005)","https://api.oyez.org/cases/2004/04-104","Federal Sentencing Guidelines are advisory, not mandatory.",2005),
                    ("Melendez-Diaz v. Massachusetts (2009)","https://api.oyez.org/cases/2008/07-591","Lab analysts must testify in person; lab certificates alone violate Confrontation Clause.",2009),
                    ("Padilla v. Kentucky (2010)","https://api.oyez.org/cases/2009/08-651","Defense counsel must advise noncitizen clients of deportation consequences of a guilty plea.",2010),
                    ("Missouri v. Frye (2012)","https://api.oyez.org/cases/2011/10-444","Sixth Amendment right to counsel applies to plea bargaining; counsel must communicate offers.",2012),
                    ("Ramos v. Louisiana (2020)","https://api.oyez.org/cases/2019/18-5924","Unanimous jury verdict required for serious criminal convictions.",2020),
                ]},
            "8th Amendment — Cruel & Unusual Punishment": {
                "summary":"Prohibits excessive bail, excessive fines, and cruel and unusual punishment.",
                "color":"#E74C3C",
                "cases":[
                    ("Furman v. Georgia (1972)","https://api.oyez.org/cases/1971/69-5003","Struck down existing death penalty statutes as arbitrarily applied.",1972),
                    ("Gregg v. Georgia (1976)","https://api.oyez.org/cases/1975/74-6257","Upheld revised death penalty statutes with guided discretion.",1976),
                    ("Coker v. Georgia (1977)","https://api.oyez.org/cases/1976/75-5444","Death penalty for rape of an adult woman is disproportionate and unconstitutional.",1977),
                    ("Solem v. Helm (1983)","https://api.oyez.org/cases/1982/82-492","Proportionality review applies to prison sentences, not just the death penalty.",1983),
                    ("Hudson v. McMillian (1992)","https://api.oyez.org/cases/1991/90-6531","Excessive force against prisoners can violate 8th Amendment even without serious injury.",1992),
                    ("Atkins v. Virginia (2002)","https://api.oyez.org/cases/2001/00-8452","Executing intellectually disabled persons is unconstitutional.",2002),
                    ("Roper v. Simmons (2005)","https://api.oyez.org/cases/2004/03-633","Death penalty for crimes committed while under 18 is unconstitutional.",2005),
                    ("Kennedy v. Louisiana (2008)","https://api.oyez.org/cases/2007/07-343","Death penalty for child rape where victim survives is unconstitutional.",2008),
                    ("Graham v. Florida (2010)","https://api.oyez.org/cases/2009/08-7412","Life without parole for non-homicide juvenile offenders is unconstitutional.",2010),
                    ("Miller v. Alabama (2012)","https://api.oyez.org/cases/2011/10-9646","Mandatory life without parole for juvenile homicide offenders is unconstitutional.",2012),
                    ("Glossip v. Gross (2015)","https://api.oyez.org/cases/2014/14-7955","Oklahoma's lethal injection protocol does not constitute cruel and unusual punishment.",2015),
                    ("Timbs v. Indiana (2019)","https://api.oyez.org/cases/2018/17-1091","Excessive Fines Clause incorporated against states; limits civil asset forfeiture.",2019),
                    ("Jones v. Mississippi (2021)","https://api.oyez.org/cases/2020/18-1259","Miller does not require a finding of permanent incorrigibility before juvenile life sentence.",2021),
                ]},
            "14th Amendment — Equal Protection & Due Process": {
                "summary":"Grants citizenship, equal protection, due process rights; incorporates Bill of Rights against states.",
                "color":"#F39C12",
                "cases":[
                    ("Brown v. Board of Education (1954)","https://api.oyez.org/cases/1953/1","Racial segregation in public schools is unconstitutional under equal protection.",1954),
                    ("Loving v. Virginia (1967)","https://api.oyez.org/cases/1966/395","Laws prohibiting interracial marriage violate the Equal Protection and Due Process Clauses.",1967),
                    ("Shapiro v. Thompson (1969)","https://api.oyez.org/cases/1967/9","State residency requirements for welfare benefits violate equal protection.",1969),
                    ("Reed v. Reed (1971)","https://api.oyez.org/cases/1971/70-4","First Equal Protection ruling striking down a law that discriminated based on sex.",1971),
                    ("Frontiero v. Richardson (1973)","https://api.oyez.org/cases/1972/71-1694","Sex-based distinctions in military benefits are unconstitutional.",1973),
                    ("Roe v. Wade (1973)","https://api.oyez.org/cases/1971/70-18","Recognized a woman's right to abortion under the Due Process Clause.",1973),
                    ("San Antonio v. Rodriguez (1973)","https://api.oyez.org/cases/1972/71-1332","Education is not a fundamental right; school funding inequalities survive rational basis.",1973),
                    ("Regents of UC v. Bakke (1978)","https://api.oyez.org/cases/1977/76-811","Race can be a factor in admissions but rigid quotas are unconstitutional.",1978),
                    ("Plyler v. Doe (1982)","https://api.oyez.org/cases/1981/80-1538","States may not deny public education to undocumented immigrant children.",1982),
                    ("Planned Parenthood v. Casey (1992)","https://api.oyez.org/cases/1991/91-744","Reaffirmed core of Roe; replaced trimester framework with undue burden standard.",1992),
                    ("Romer v. Evans (1996)","https://api.oyez.org/cases/1995/94-1039","Colorado amendment stripping gay rights protections violates equal protection.",1996),
                    ("Adarand Constructors v. Pena (1995)","https://api.oyez.org/cases/1994/93-1841","Federal racial classifications must survive strict scrutiny.",1995),
                    ("United States v. Virginia (1996)","https://api.oyez.org/cases/1995/94-1941","Virginia Military Institute's male-only admissions policy violates equal protection.",1996),
                    ("Grutter v. Bollinger (2003)","https://api.oyez.org/cases/2002/02-241","Race may be a factor in holistic university admissions to achieve diversity.",2003),
                    ("Gratz v. Bollinger (2003)","https://api.oyez.org/cases/2002/02-516","Automatic point system for race in undergraduate admissions is unconstitutional.",2003),
                    ("Lawrence v. Texas (2003)","https://api.oyez.org/cases/2002/02-102","State sodomy laws criminalizing same-sex intimacy violate due process liberty interest.",2003),
                    ("Parents Involved in Community Schools v. Seattle (2007)","https://api.oyez.org/cases/2006/05-908","Race-based student assignment plans in non-unitary districts violate equal protection.",2007),
                    ("United States v. Windsor (2013)","https://api.oyez.org/cases/2012/12-307","DOMA's opposite-sex-only definition of marriage violated equal protection.",2013),
                    ("Obergefell v. Hodges (2015)","https://api.oyez.org/cases/2014/14-556","Same-sex couples have a fundamental right to marry under the 14th Amendment.",2015),
                    ("Whole Woman's Health v. Hellerstedt (2016)","https://api.oyez.org/cases/2015/15-274","Texas abortion clinic regulations struck down as imposing an undue burden.",2016),
                    ("Bostock v. Clayton County (2020)","https://api.oyez.org/cases/2019/17-1618","Title VII prohibits employment discrimination based on sexual orientation and gender identity.",2020),
                    ("Dobbs v. Jackson Women's Health (2022)","https://api.oyez.org/cases/2021/19-1392","Overturned Roe v. Wade; the Constitution does not confer a right to abortion.",2022),
                    ("Students for Fair Admissions v. Harvard (2023)","https://api.oyez.org/cases/2022/20-1199","Race-conscious admissions programs at Harvard and UNC are unconstitutional.",2023),
                ]},
            "Article I — Commerce Clause & Federal Power": {
                "summary":"Art. I §8 grants Congress power to regulate interstate commerce; core cases on federal power and its limits.",
                "color":"#117864",
                "cases":[
                    ("Gibbons v. Ogden (1824)","https://api.oyez.org/cases/1789-1850/22us1","Broad interpretation: Congress can regulate navigation between states.",1824),
                    ("Wickard v. Filburn (1942)","https://api.oyez.org/cases/1940-1955/317us111","Growing wheat for personal use substantially affects interstate commerce.",1942),
                    ("Heart of Atlanta Motel v. United States (1964)","https://api.oyez.org/cases/1964/515","Civil Rights Act of 1964 is valid Commerce Clause legislation.",1964),
                    ("Katzenbach v. McClung (1964)","https://api.oyez.org/cases/1964/543","Civil Rights Act applies to restaurants because food travels in interstate commerce.",1964),
                    ("Garcia v. San Antonio Metropolitan Transit (1985)","https://api.oyez.org/cases/1984/82-1913","States not immune from federal minimum wage requirements under the FLSA.",1985),
                    ("United States v. Lopez (1995)","https://api.oyez.org/cases/1994/93-1260","Gun-Free School Zones Act exceeds Commerce Clause; first limit in 60 years.",1995),
                    ("Seminole Tribe v. Florida (1996)","https://api.oyez.org/cases/1995/94-12","Congress cannot abrogate state sovereign immunity under Commerce Clause alone.",1996),
                    ("United States v. Morrison (2000)","https://api.oyez.org/cases/1999/99-5","Violence Against Women Act civil remedy exceeds Commerce Clause power.",2000),
                    ("Gonzales v. Raich (2005)","https://api.oyez.org/cases/2004/03-1454","Congress may ban personal marijuana cultivation under Commerce Clause.",2005),
                    ("NFIB v. Sebelius (2012)","https://api.oyez.org/cases/2011/11-393","ACA individual mandate exceeds Commerce Clause; upheld as a valid tax.",2012),
                    ("West Virginia v. EPA (2022)","https://api.oyez.org/cases/2021/20-1530","Major questions doctrine limits EPA authority over power sector transformation.",2022),
                    ("Loper Bright Enterprises v. Raimondo (2024)","https://api.oyez.org/cases/2023/22-1219","Chevron deference overruled; courts must independently interpret ambiguous statutes.",2024),
                ]},
            "Article II — Executive Power & Separation of Powers": {
                "summary":"Defines presidential authority; core separation of powers decisions.",
                "color":"#5D6D7E",
                "cases":[
                    ("Youngstown Sheet & Tube Co. v. Sawyer (1952)","https://api.oyez.org/cases/1951/745","President cannot seize steel mills without congressional authorization.",1952),
                    ("United States v. Nixon (1974)","https://api.oyez.org/cases/1974/73-1766","Executive privilege is not absolute; President must comply with judicial subpoena.",1974),
                    ("INS v. Chadha (1983)","https://api.oyez.org/cases/1982/80-1832","Legislative veto by one house of Congress is unconstitutional.",1983),
                    ("Morrison v. Olson (1988)","https://api.oyez.org/cases/1987/87-1279","Independent counsel statute does not violate separation of powers.",1988),
                    ("Clinton v. City of New York (1998)","https://api.oyez.org/cases/1997/97-1374","Line Item Veto Act is unconstitutional; President cannot cancel spending provisions.",1998),
                    ("Bush v. Gore (2000)","https://api.oyez.org/cases/2000/00-949","Florida presidential recount halted; inconsistent standards violated equal protection.",2000),
                    ("Hamdi v. Rumsfeld (2004)","https://api.oyez.org/cases/2003/03-6696","U.S. citizen enemy combatants must have meaningful opportunity to challenge detention.",2004),
                    ("Hamdan v. Rumsfeld (2006)","https://api.oyez.org/cases/2005/05-184","Military commissions at Guantanamo violated UCMJ and Geneva Conventions.",2006),
                    ("Boumediene v. Bush (2008)","https://api.oyez.org/cases/2007/06-1195","Guantanamo detainees have constitutional right to habeas corpus.",2008),
                    ("Free Enterprise Fund v. PCAOB (2010)","https://api.oyez.org/cases/2009/08-861","Double layer of for-cause removal protection for PCAOB members unconstitutional.",2010),
                    ("NLRB v. Noel Canning (2014)","https://api.oyez.org/cases/2013/12-1281","President's recess appointments invalid; Senate not in recess during pro forma sessions.",2014),
                    ("Seila Law v. CFPB (2020)","https://api.oyez.org/cases/2019/19-7","CFPB's single-director removal-only-for-cause structure violates separation of powers.",2020),
                    ("Trump v. Mazars USA (2020)","https://api.oyez.org/cases/2019/19-715","Congressional subpoenas for presidential financial records must meet heightened standard.",2020),
                    ("Trump v. United States (2024)","https://api.oyez.org/cases/2023/23-939","Former presidents have absolute immunity for core constitutional acts.",2024),
                ]},
            "Voting Rights & Elections": {
                "summary":"Cases defining the right to vote, redistricting, and election regulation.",
                "color":"#2C3E50",
                "cases":[
                    ("Baker v. Carr (1962)","https://api.oyez.org/cases/1961/6","Legislative apportionment is a justiciable issue; opened door to redistricting reform.",1962),
                    ("Reynolds v. Sims (1964)","https://api.oyez.org/cases/1963/23","State legislative districts must be roughly equal in population.",1964),
                    ("Harper v. Virginia Board of Elections (1966)","https://api.oyez.org/cases/1965/48","Poll taxes in state elections violate equal protection.",1966),
                    ("Kramer v. Union Free School District (1969)","https://api.oyez.org/cases/1968/498","Restrictions on voting in school district elections violate equal protection.",1969),
                    ("Shaw v. Reno (1993)","https://api.oyez.org/cases/1992/92-357","Racial gerrymandering itself can be unconstitutional; strict scrutiny applies.",1993),
                    ("Bush v. Gore (2000)","https://api.oyez.org/cases/2000/00-949","Florida presidential recount halted; inconsistent standards violated equal protection.",2000),
                    ("Shelby County v. Holder (2013)","https://api.oyez.org/cases/2012/12-96","Struck down VRA coverage formula; gutted preclearance requirements.",2013),
                    ("Rucho v. Common Cause (2019)","https://api.oyez.org/cases/2018/18-422","Partisan gerrymandering claims are nonjusticiable political questions.",2019),
                    ("Brnovich v. Democratic National Committee (2021)","https://api.oyez.org/cases/2020/19-1257","Arizona voting restrictions upheld; Section 2 of VRA interpreted narrowly.",2021),
                    ("Allen v. Milligan (2023)","https://api.oyez.org/cases/2022/21-1086","Alabama congressional map violates VRA Section 2; race-neutral lines upheld.",2023),
                    ("Moore v. Harper (2023)","https://api.oyez.org/cases/2022/21-1271","Rejected independent state legislature theory; federal courts may review state election law decisions.",2023),
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
        st.subheader("Case Timeline"); st.plotly_chart(fig_tl_amend)
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
                        if facts_am: st.markdown("**Facts**"); st.write(safe_md(facts_am[:800])+("…" if len(facts_am or "")>800 else ""))
                        conclusion_am = detail_amend.get("conclusion","")
                        if conclusion_am: st.markdown("**Conclusion**"); st.write(safe_md(conclusion_am[:600])+("…" if len(conclusion_am or "")>600 else ""))
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
        _max_cases = summary_df_amend["Cases"].max()
        fig_overview_amend = go.Figure(go.Bar(x=summary_df_amend["Amendment"],y=summary_df_amend["Cases"],
                                               marker_color=summary_df_amend["Color"].tolist(),
                                               text=summary_df_amend["Cases"],textposition="outside"))
        fig_overview_amend.update_layout(height=380,xaxis_title="",yaxis_title="Landmark Cases Tracked",
                                          yaxis=dict(range=[0, _max_cases * 1.25]),
                                          plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30,
                                          margin=dict(t=40,b=80))
        st.caption("Counts reflect the curated landmark cases listed above, not all cases in the Oyez database.")
        st.plotly_chart(fig_overview_amend)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: CONSTITUTIONAL PROVISIONS TRACKER
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_provisions:
        PROVISIONS = [
            # First Amendment
            ("free_speech","Free Speech","First Amendment — Freedom of Speech & Press","Amendment I","#E74C3C"),
            ("free_press","Freedom of Press","First Amendment — Freedom of Press","Amendment I","#C0392B"),
            ("establishment","Establishment Clause","First Amendment — Establishment of Religion","Amendment I","#E67E22"),
            ("free_exercise","Free Exercise","First Amendment — Free Exercise of Religion","Amendment I","#F39C12"),
            ("assembly","Freedom of Assembly","First Amendment — Freedom of Peaceful Assembly","Amendment I","#D4AC0D"),
            ("petition","Right to Petition","First Amendment — Right to Petition Government","Amendment I","#F1948A"),
            # Second Amendment
            ("second_amend","Second Amendment","Second Amendment — Right to Keep and Bear Arms","Amendment II","#D35400"),
            # Fourth Amendment
            ("search_seizure","Search & Seizure","Fourth Amendment — Unreasonable Searches & Seizures","Amendment IV","#27AE60"),
            ("warrant","Warrant Requirement","Fourth Amendment — Warrant Clause","Amendment IV","#1E8449"),
            # Fifth Amendment
            ("self_incrim","Self-Incrimination","Fifth Amendment — Right Against Self-Incrimination","Amendment V","#1ABC9C"),
            ("due_process_5","Due Process (5th)","Fifth Amendment — Due Process of Law","Amendment V","#16A085"),
            ("takings","Takings Clause","Fifth Amendment — Just Compensation / Takings","Amendment V","#2ECC71"),
            ("double_jeopardy","Double Jeopardy","Fifth Amendment — Double Jeopardy Clause","Amendment V","#148F77"),
            # Sixth Amendment
            ("right_counsel","Right to Counsel","Sixth Amendment — Right to Counsel","Amendment VI","#3498DB"),
            ("confrontation","Confrontation","Sixth Amendment — Confrontation Clause","Amendment VI","#2980B9"),
            ("speedy_trial","Speedy Trial","Sixth Amendment — Speedy & Public Trial","Amendment VI","#1A5276"),
            ("jury_trial","Jury Trial","Sixth Amendment — Right to Jury Trial","Amendment VI","#2471A3"),
            # Eighth Amendment
            ("cruel_unusual","Cruel & Unusual","Eighth Amendment — Cruel and Unusual Punishment","Amendment VIII","#9B59B6"),
            ("excessive_fines","Excessive Fines","Eighth Amendment — Excessive Fines Clause","Amendment VIII","#7D3C98"),
            # Fourteenth Amendment
            ("equal_prot","Equal Protection","Fourteenth Amendment — Equal Protection Clause","Amendment XIV","#8E44AD"),
            ("due_process_14","Due Process (14th)","Fourteenth Amendment — Due Process / Incorporation","Amendment XIV","#6C3483"),
            ("privileges","Privileges or Immunities","Fourteenth Amendment — Privileges or Immunities Clause","Amendment XIV","#4A235A"),
            # Article I
            ("commerce","Commerce Clause","Article I, § 8 — Commerce Clause","Article I","#C0392B"),
            ("spending","Spending Clause","Article I, § 8 — Spending Clause","Article I","#A93226"),
            ("necessary_proper","Necessary & Proper","Article I, § 8 — Necessary and Proper Clause","Article I","#922B21"),
            ("non_delegation","Non-Delegation","Article I — Non-Delegation Doctrine","Article I","#E74C3C"),
            # Article II
            ("exec_power","Executive Power","Article II — Executive Power & Commander-in-Chief","Article II","#5D6D7E"),
            ("exec_privilege","Executive Privilege","Article II — Executive Privilege","Article II","#717D8A"),
            # Article III
            ("judicial_review","Judicial Review","Article III — Judicial Review & Standing","Article III","#2C3E50"),
            ("standing","Standing","Article III — Case or Controversy / Standing","Article III","#34495E"),
            # Other Amendments
            ("tenth_amend","Tenth Amendment","Tenth Amendment — Reserved Powers / Federalism","Amendment X","#7F8C8D"),
            ("eleventh_amend","Eleventh Amendment","Eleventh Amendment — State Sovereign Immunity","Amendment XI","#95A5A6"),
        ]

        PROV_MAP = {p[0]:p for p in PROVISIONS}

        LANDMARK_CASES_PROV = [
            # FREE SPEECH
            ("Schenck v. United States",1919,["free_speech"],"Clear and present danger test upheld speech restrictions during wartime.",3),
            ("Gitlow v. New York",1925,["free_speech"],"First Amendment incorporated against states via 14th Amendment.",4),
            ("Tinker v. Des Moines",1969,["free_speech"],"Student anti-war armbands protected; schools need substantial disruption to restrict speech.",5),
            ("Brandenburg v. Ohio",1969,["free_speech"],"Imminent lawless action test replaced clear and present danger.",5),
            ("Cohen v. California",1971,["free_speech"],"State cannot ban offensive language on clothing in public spaces.",4),
            ("Buckley v. Valeo",1976,["free_speech"],"Campaign expenditures are protected speech; contribution limits narrowly upheld.",5),
            ("Hazelwood School District v. Kuhlmeier",1988,["free_speech"],"Schools may exercise editorial control over school-sponsored newspapers.",4),
            ("Texas v. Johnson",1989,["free_speech"],"Flag burning is protected symbolic speech.",5),
            ("R.A.V. v. City of St. Paul",1992,["free_speech"],"Hate speech ordinance targeting only certain topics of fighting words is unconstitutional.",5),
            ("Reno v. ACLU",1997,["free_speech"],"CDA indecency provisions unconstitutionally restricted online speech.",5),
            ("United States v. Stevens",2010,["free_speech"],"Federal law criminalizing depictions of animal cruelty struck down as overbroad.",4),
            ("Citizens United v. FEC",2010,["free_speech"],"Political spending by corporations is protected speech.",5),
            ("Snyder v. Phelps",2011,["free_speech"],"Westboro Baptist Church protests near military funerals are protected.",4),
            ("United States v. Alvarez",2012,["free_speech"],"Stolen Valor Act criminalization of lying about military medals violates First Amendment.",4),
            ("McCullen v. Coakley",2014,["free_speech"],"Fixed buffer zones around abortion clinics violate free speech rights.",4),
            ("Matal v. Tam",2017,["free_speech"],"Government cannot deny trademark registration based on group disparagement.",4),
            ("303 Creative v. Elenis",2023,["free_speech","equal_prot"],"Designer cannot be compelled to create websites for same-sex weddings.",4),
            ("Moody v. NetChoice",2024,["free_speech"],"State social-media content moderation laws remanded for full First Amendment analysis.",4),
            # FREE PRESS
            ("New York Times v. Sullivan",1964,["free_speech","free_press"],"Actual malice standard for defamation of public officials.",5),
            ("New York Times v. United States",1971,["free_press"],"Pentagon Papers prior restraint rejected.",5),
            ("Branzburg v. Hayes",1972,["free_press"],"Reporters have no First Amendment privilege to refuse grand jury testimony.",4),
            ("Hustler Magazine v. Falwell",1988,["free_press","free_speech"],"Public figures cannot recover for intentional infliction of emotional distress from parody.",4),
            # ESTABLISHMENT
            ("Engel v. Vitale",1962,["establishment"],"School-sponsored prayer violates Establishment Clause.",5),
            ("Abington School District v. Schempp",1963,["establishment"],"Bible readings in public schools unconstitutional.",5),
            ("Lemon v. Kurtzman",1971,["establishment"],"Three-part Lemon test established for Establishment Clause cases.",5),
            ("Lee v. Weisman",1992,["establishment"],"Clergy-led prayers at public school graduation ceremonies unconstitutional.",5),
            ("Santa Fe Independent School District v. Doe",2000,["establishment"],"Student-led prayer over school PA before football games violates Establishment Clause.",5),
            ("Zelman v. Simmons-Harris",2002,["establishment"],"School voucher programs including parochial schools do not violate Establishment Clause.",5),
            ("Town of Greece v. Galloway",2014,["establishment"],"Legislative prayer at town board meetings constitutional.",5),
            ("American Legion v. American Humanist Association",2019,["establishment"],"40-foot WWI cross on public land permitted as historical monument.",4),
            ("Kennedy v. Bremerton School District",2022,["establishment","free_exercise"],"Public school coach's personal prayer on field protected; Lemon test abandoned.",5),
            # FREE EXERCISE
            ("Wisconsin v. Yoder",1972,["free_exercise"],"Amish families cannot be compelled to send children to school past 8th grade.",5),
            ("Employment Division v. Smith",1990,["free_exercise"],"Neutral, generally applicable laws may burden religion without exemption.",5),
            ("Church of Lukumi Babalu Aye v. City of Hialeah",1993,["free_exercise"],"Ordinance targeting Santeria animal sacrifice violates Free Exercise Clause.",5),
            ("Gonzales v. O Centro Espirita",2006,["free_exercise"],"RFRA requires exemption for religious use of hoasca tea.",4),
            ("Burwell v. Hobby Lobby",2014,["free_exercise"],"Closely-held corporations may claim religious exemptions under RFRA.",5),
            ("Trinity Lutheran Church v. Comer",2017,["free_exercise"],"State cannot deny church access to public playground resurfacing grant.",5),
            ("Masterpiece Cakeshop v. Colorado Civil Rights Commission",2018,["free_exercise"],"Commission showed religious hostility; baker's free exercise claim warranted neutral consideration.",4),
            ("Fulton v. City of Philadelphia",2021,["free_exercise"],"City violated Free Exercise by excluding Catholic foster agency.",5),
            ("Carson v. Makin",2022,["free_exercise"],"Maine cannot exclude religious schools from tuition assistance program.",5),
            # SEARCH & SEIZURE
            ("Mapp v. Ohio",1961,["search_seizure"],"Exclusionary rule applies to states via 14th Amendment.",5),
            ("Katz v. United States",1967,["search_seizure","warrant"],"Wiretapping phone booth requires warrant; reasonable expectation of privacy test.",5),
            ("Terry v. Ohio",1968,["search_seizure"],"Stop-and-frisk constitutional under reasonable suspicion standard.",5),
            ("Illinois v. Gates",1983,["search_seizure","warrant"],"Totality of circumstances test for probable cause replaces rigid two-pronged test.",4),
            ("New Jersey v. T.L.O.",1985,["search_seizure"],"Reasonable suspicion — not probable cause — required for school searches.",4),
            ("United States v. Leon",1984,["search_seizure","warrant"],"Good-faith exception: evidence obtained under defective warrant may be admissible.",4),
            ("California v. Greenwood",1988,["search_seizure"],"No reasonable expectation of privacy in garbage left for collection.",4),
            ("Florida v. Bostick",1991,["search_seizure"],"Police may board buses and ask for consent to search without 4th Amendment violation.",3),
            ("Vernonia School District v. Acton",1995,["search_seizure"],"Random drug testing of student athletes does not violate 4th Amendment.",4),
            ("Whren v. United States",1996,["search_seizure"],"Traffic stop valid if officer observes any traffic violation regardless of subjective intent.",4),
            ("Illinois v. Caballes",2005,["search_seizure"],"Dog sniff of vehicle exterior during lawful traffic stop is not a search.",4),
            ("Georgia v. Randolph",2006,["search_seizure"],"Co-occupant who refuses consent blocks warrantless search even if other consents.",4),
            ("Safford Unified School District v. Redding",2009,["search_seizure"],"Strip-searching a 13-year-old for ibuprofen violated 4th Amendment.",5),
            ("Kentucky v. King",2011,["search_seizure"],"Exigent circumstances exception applies when police create the situation prompting it.",4),
            ("United States v. Jones",2012,["search_seizure"],"Attaching GPS device to vehicle constitutes a 4th Amendment search.",5),
            ("Florida v. Jardines",2013,["search_seizure"],"Using drug-sniffing dog at front door is a 4th Amendment search.",5),
            ("Missouri v. McNeely",2013,["search_seizure","warrant"],"Police generally must obtain warrant before drawing blood from DUI suspect.",5),
            ("Riley v. California",2014,["search_seizure","warrant"],"Police must get warrant to search cell phone contents after arrest.",5),
            ("Utah v. Strieff",2016,["search_seizure"],"Evidence after unlawful stop admissible where outstanding arrest warrant existed.",4),
            ("Carpenter v. United States",2018,["search_seizure","warrant"],"Warrant required for historical cell-site location information.",5),
            ("Kansas v. Glover",2020,["search_seizure"],"Reasonable for officer to assume registered owner is driver of vehicle.",3),
            # SELF-INCRIMINATION
            ("Miranda v. Arizona",1966,["self_incrim","due_process_5"],"Police must inform suspects of rights before custodial interrogation.",5),
            ("Garrity v. New Jersey",1967,["self_incrim"],"Statements compelled under threat of job loss cannot be used in criminal prosecution.",4),
            ("Kastigar v. United States",1972,["self_incrim"],"Use immunity sufficient to compel testimony; transactional immunity not required.",3),
            ("Dickerson v. United States",2000,["self_incrim"],"Congress cannot overrule Miranda with a statute; Miranda is a constitutional rule.",5),
            ("Salinas v. Texas",2013,["self_incrim"],"Suspect must explicitly invoke 5th Amendment; pre-arrest silence can be used against them.",4),
            # DOUBLE JEOPARDY
            ("Blockburger v. United States",1932,["double_jeopardy"],"Same-elements test determines whether two offenses are the same for double jeopardy.",3),
            ("Ashe v. Swenson",1970,["double_jeopardy"],"Collateral estoppel is embedded in the Double Jeopardy Clause.",4),
            ("Gamble v. United States",2019,["double_jeopardy"],"Separate-sovereigns doctrine: federal and state prosecutions for same conduct not double jeopardy.",4),
            # TAKINGS
            ("Dolan v. City of Tigard",1994,["takings"],"Rough proportionality test for development exaction conditions.",4),
            ("Kelo v. City of New London",2005,["takings"],"Economic development qualifies as public use under Takings Clause.",5),
            ("Horne v. Department of Agriculture",2015,["takings"],"Government raisin reserve requirement is a per se physical taking.",4),
            # RIGHT TO COUNSEL
            ("Gideon v. Wainwright",1963,["right_counsel"],"Right to counsel incorporated against states.",5),
            ("Faretta v. California",1975,["right_counsel"],"Defendants have a constitutional right to represent themselves.",4),
            ("Strickland v. Washington",1984,["right_counsel"],"Two-part test for ineffective assistance of counsel.",5),
            ("Padilla v. Kentucky",2010,["right_counsel"],"Defense counsel must advise noncitizen clients of deportation consequences of plea.",5),
            ("Missouri v. Frye",2012,["right_counsel"],"Sixth Amendment right to counsel applies to plea bargaining.",5),
            # CONFRONTATION
            ("Pointer v. Texas",1965,["confrontation"],"Confrontation Clause incorporated against states.",4),
            ("Crawford v. Washington",2004,["confrontation"],"Testimonial statements of absent witnesses require prior cross-examination.",5),
            ("Melendez-Diaz v. Massachusetts",2009,["confrontation"],"Lab analysts must testify in person; lab certificates alone violate Confrontation Clause.",4),
            # SPEEDY TRIAL / JURY
            ("Barker v. Wingo",1972,["speedy_trial"],"Four-factor balancing test for speedy trial claims.",4),
            ("Batson v. Kentucky",1986,["jury_trial","equal_prot"],"Prosecutors cannot use peremptory challenges to exclude jurors based on race.",5),
            ("Blakely v. Washington",2004,["jury_trial"],"Sentence enhancements beyond statutory maximum must be submitted to a jury.",5),
            ("United States v. Booker",2005,["jury_trial"],"Federal Sentencing Guidelines are advisory, not mandatory.",5),
            ("Ramos v. Louisiana",2020,["jury_trial"],"Unanimous jury verdict required for serious criminal convictions.",5),
            # CRUEL & UNUSUAL
            ("Furman v. Georgia",1972,["cruel_unusual"],"Death penalty as then applied was unconstitutional.",5),
            ("Gregg v. Georgia",1976,["cruel_unusual"],"Death penalty itself is not per se unconstitutional.",5),
            ("Coker v. Georgia",1977,["cruel_unusual"],"Death penalty for rape of adult woman is disproportionate.",4),
            ("Solem v. Helm",1983,["cruel_unusual"],"Proportionality review applies to prison sentences, not just death penalty.",4),
            ("Atkins v. Virginia",2002,["cruel_unusual"],"Executing intellectually disabled persons is unconstitutional.",5),
            ("Roper v. Simmons",2005,["cruel_unusual"],"Executing juvenile offenders violates Eighth Amendment.",5),
            ("Kennedy v. Louisiana",2008,["cruel_unusual"],"Death penalty for child rape where victim survives is unconstitutional.",5),
            ("Graham v. Florida",2010,["cruel_unusual"],"Life without parole for non-homicide juvenile offenders is unconstitutional.",5),
            ("Miller v. Alabama",2012,["cruel_unusual"],"Mandatory life without parole for juvenile homicide offenders is unconstitutional.",5),
            ("Glossip v. Gross",2015,["cruel_unusual"],"Oklahoma's lethal injection protocol does not constitute cruel and unusual punishment.",4),
            ("Jones v. Mississippi",2021,["cruel_unusual"],"Miller does not require finding of permanent incorrigibility before juvenile life sentence.",4),
            # EXCESSIVE FINES
            ("Timbs v. Indiana",2019,["excessive_fines"],"Excessive Fines Clause incorporated against states; limits civil asset forfeiture.",5),
            # EQUAL PROTECTION
            ("Brown v. Board of Education",1954,["equal_prot"],"Racial segregation in public schools is unconstitutional.",5),
            ("Loving v. Virginia",1967,["equal_prot","due_process_14"],"Anti-miscegenation laws violate Equal Protection and Due Process.",5),
            ("Reed v. Reed",1971,["equal_prot"],"First Equal Protection ruling striking down a law that discriminated based on sex.",4),
            ("Frontiero v. Richardson",1973,["equal_prot"],"Sex-based distinctions in military benefits are unconstitutional.",4),
            ("San Antonio v. Rodriguez",1973,["equal_prot"],"Education is not a fundamental right; school funding inequality survives rational basis.",4),
            ("Regents of UC v. Bakke",1978,["equal_prot"],"Race may be a factor in admissions but rigid quotas are unconstitutional.",5),
            ("Plyler v. Doe",1982,["equal_prot"],"States may not deny public education to undocumented immigrant children.",5),
            ("Batson v. Kentucky",1986,["jury_trial","equal_prot"],"Race-based peremptory challenges violate equal protection.",5),
            ("Adarand Constructors v. Pena",1995,["equal_prot"],"Federal racial classifications must survive strict scrutiny.",5),
            ("United States v. Virginia",1996,["equal_prot"],"Virginia Military Institute's male-only admissions policy violates equal protection.",5),
            ("Romer v. Evans",1996,["equal_prot"],"Colorado amendment stripping gay rights protections violates equal protection.",5),
            ("Grutter v. Bollinger",2003,["equal_prot"],"Race may be used as a factor in holistic university admissions.",5),
            ("Gratz v. Bollinger",2003,["equal_prot"],"Automatic point system for race in undergraduate admissions is unconstitutional.",4),
            ("Parents Involved in Community Schools v. Seattle",2007,["equal_prot"],"Race-based student assignment in non-unitary districts violates equal protection.",5),
            ("United States v. Windsor",2013,["equal_prot","due_process_14"],"DOMA's opposite-sex-only definition of marriage violated equal protection.",5),
            ("Obergefell v. Hodges",2015,["equal_prot","due_process_14"],"Same-sex couples have fundamental right to marry.",5),
            ("Bostock v. Clayton County",2020,["equal_prot"],"Title VII prohibits employment discrimination based on sexual orientation and gender identity.",5),
            ("303 Creative v. Elenis",2023,["free_speech","equal_prot"],"Compelled speech doctrine limits public accommodation laws.",4),
            ("SFFA v. Harvard",2023,["equal_prot"],"Race-conscious admissions programs at Harvard and UNC unconstitutional.",5),
            # DUE PROCESS (14th)
            ("Griswold v. Connecticut",1965,["due_process_14"],"Right to marital privacy for contraceptives established.",5),
            ("Roe v. Wade",1973,["due_process_14"],"Abortion protected under right to privacy.",5),
            ("Planned Parenthood v. Casey",1992,["due_process_14"],"Reaffirmed Roe; undue burden standard established.",5),
            ("Washington v. Glucksberg",1997,["due_process_14"],"No fundamental due process right to physician-assisted suicide.",4),
            ("Lawrence v. Texas",2003,["due_process_14"],"State sodomy laws criminalizing same-sex intimacy violate due process.",5),
            ("Whole Woman's Health v. Hellerstedt",2016,["due_process_14"],"Texas abortion clinic regulations struck down as imposing undue burden.",5),
            ("Dobbs v. Jackson Women's Health",2022,["due_process_14"],"Constitution does not confer right to abortion; Roe overruled.",5),
            # SECOND AMENDMENT
            ("DC v. Heller",2008,["second_amend"],"Second Amendment protects individual right to keep firearms at home.",5),
            ("McDonald v. City of Chicago",2010,["second_amend","due_process_14"],"Second Amendment incorporated against states via 14th Amendment.",5),
            ("NY State Rifle & Pistol v. Bruen",2022,["second_amend"],"Historical tradition test replaces means-ends scrutiny for gun regulations.",5),
            ("United States v. Rahimi",2024,["second_amend"],"Federal firearms ban for those under domestic violence restraining orders is constitutional.",5),
            ("Garland v. Cargill",2024,["second_amend"],"Bump stocks do not qualify as machine guns under federal law.",4),
            # COMMERCE CLAUSE
            ("Wickard v. Filburn",1942,["commerce"],"Growing wheat for personal use substantially affects interstate commerce.",5),
            ("Heart of Atlanta Motel v. United States",1964,["commerce"],"Civil Rights Act of 1964 is valid Commerce Clause legislation.",5),
            ("Katzenbach v. McClung",1964,["commerce"],"Civil Rights Act applies to restaurants via Commerce Clause.",4),
            ("Garcia v. San Antonio Metropolitan Transit",1985,["commerce","tenth_amend"],"States are not immune from federal wage laws; political process is the protection.",4),
            ("Lopez v. United States",1995,["commerce"],"Gun-Free School Zones Act exceeds Commerce Clause; first limit in 60 years.",5),
            ("United States v. Morrison",2000,["commerce","equal_prot"],"Violence Against Women Act civil remedy exceeds Commerce Clause power.",5),
            ("Gonzales v. Raich",2005,["commerce"],"Congress may ban personal marijuana cultivation under Commerce Clause.",5),
            ("NFIB v. Sebelius",2012,["commerce","spending"],"ACA individual mandate exceeds Commerce Clause; upheld as tax.",5),
            ("West Virginia v. EPA",2022,["commerce"],"Major questions doctrine limits EPA authority to mandate broad power sector transformation.",5),
            ("Loper Bright v. Raimondo",2024,["commerce"],"Chevron deference overruled; courts interpret statutes independently.",5),
            # SPENDING CLAUSE
            ("South Dakota v. Dole",1987,["spending"],"Congress may condition highway funds on states raising drinking age.",4),
            # NECESSARY & PROPER
            ("McCulloch v. Maryland",1819,["necessary_proper","tenth_amend","commerce"],"Necessary and Proper Clause gives Congress implied powers.",5),
            # NON-DELEGATION
            ("Schechter Poultry Corp. v. United States",1935,["non_delegation","commerce"],"NIRA struck down; Congress cannot delegate unfettered legislative power to executive.",4),
            ("Gundy v. United States",2019,["non_delegation"],"SORNA sex-offender registration delegation upheld 4-3; non-delegation doctrine's future uncertain.",3),
            # TENTH AMENDMENT / FEDERALISM
            ("New York v. United States",1992,["tenth_amend"],"Federal government cannot commandeer states to enact regulatory programs.",5),
            ("Printz v. United States",1997,["tenth_amend"],"Federal government cannot commandeer state executive officers.",5),
            ("Murphy v. NCAA",2018,["tenth_amend"],"Anti-commandeering doctrine prevents Congress from ordering states to maintain sports gambling ban.",5),
            # ELEVENTH AMENDMENT
            ("Seminole Tribe v. Florida",1996,["eleventh_amend","commerce"],"Congress cannot abrogate state sovereign immunity under Commerce Clause alone.",4),
            ("Alden v. Maine",1999,["eleventh_amend"],"State sovereign immunity bars suits against states in state court under federal law.",4),
            # EXECUTIVE POWER
            ("Youngstown Sheet & Tube v. Sawyer",1952,["exec_power"],"President cannot seize steel mills without Congress; Jackson three-zone framework.",5),
            ("United States v. Nixon",1974,["exec_privilege","judicial_review"],"Executive privilege is not absolute; President must comply with judicial subpoena.",5),
            ("INS v. Chadha",1983,["non_delegation"],"Legislative veto by one house of Congress is unconstitutional.",5),
            ("Morrison v. Olson",1988,["exec_power"],"Independent counsel statute does not violate separation of powers.",4),
            ("Clinton v. City of New York",1998,["exec_power"],"Line Item Veto Act is unconstitutional.",5),
            ("Hamdi v. Rumsfeld",2004,["exec_power","due_process_5"],"U.S. citizen enemy combatants must have meaningful opportunity to challenge detention.",5),
            ("Boumediene v. Bush",2008,["exec_power","judicial_review"],"Guantanamo detainees have constitutional right to habeas corpus.",5),
            ("Seila Law v. CFPB",2020,["exec_power"],"CFPB single-director removal-only-for-cause structure violates separation of powers.",4),
            ("Trump v. United States",2024,["exec_privilege","exec_power"],"Former presidents have absolute immunity for core constitutional acts.",5),
            # JUDICIAL REVIEW / STANDING
            ("Baker v. Carr",1962,["judicial_review","standing"],"Legislative apportionment is a justiciable issue; opened door to redistricting reform.",5),
            ("Lujan v. Defenders of Wildlife",1992,["standing"],"Environmental groups lacked standing without concrete injury from agency action abroad.",4),
            ("Bush v. Gore",2000,["equal_prot","judicial_review"],"Florida recount halted; inconsistent standards violated equal protection.",5),
            ("Massachusetts v. EPA",2007,["standing","commerce"],"States have standing to challenge EPA's refusal to regulate greenhouse gases.",4),
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
                    with st.expander("Facts of the Case",expanded=True): st.write(safe_md(facts_lt))
                question_lt = detail_lt.get("question","")
                if question_lt:
                    with st.expander("Legal Question"): st.write(safe_md(question_lt))
                conclusion_lt = detail_lt.get("conclusion","")
                if conclusion_lt:
                    with st.expander("Court's Conclusion"): st.write(safe_md(conclusion_lt))
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
            _decs_lt = detail_lt.get("decisions") or []
            if _decs_lt:
                def _dc_lt(d): return sum(1 for v in (d.get("votes") or []) if (v.get("vote") or "").lower() in ("dissent", "minority"))
                _, _primary_lt = max(enumerate(_decs_lt), key=lambda x: (_dc_lt(x[1]), len(x[1].get("votes") or []), x[0]))
                winning_party_lt = _primary_lt.get("winning_party","")
                for vote in (_primary_lt.get("votes") or []):
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

def _page_networks():
    tab_citation, tab_precedent = st.tabs([
        "🔗 Citation Network", "🕸️ Case Precedent Network"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: CITATION NETWORK (16_Citation_Network)
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_citation:
        st.markdown(
            "Explore how landmark Supreme Court cases cite, overrule, build on, "
            "and distinguish each other. Arrows point **from citing case → to cited case**."
        )

        CASES_CN = [
            ("plessy","Plessy v. Ferguson",1896,"Equal Protection","https://www.oyez.org/cases/1850-1900/163us537"),
            ("mapp","Mapp v. Ohio",1961,"Criminal Procedure","https://www.oyez.org/cases/1960/236"),
            ("engel","Engel v. Vitale",1962,"First Amendment","https://www.oyez.org/cases/1961/468"),
            ("gideon","Gideon v. Wainwright",1963,"Criminal Procedure","https://www.oyez.org/cases/1962/155"),
            ("brown","Brown v. Board of Education",1954,"Equal Protection","https://www.oyez.org/cases/1940-1955/347us483"),
            ("griswold","Griswold v. Connecticut",1965,"Privacy","https://www.oyez.org/cases/1964/496"),
            ("miranda","Miranda v. Arizona",1966,"Criminal Procedure","https://www.oyez.org/cases/1965/759"),
            ("tinker","Tinker v. Des Moines",1969,"First Amendment","https://www.oyez.org/cases/1968/21"),
            ("lemon","Lemon v. Kurtzman",1971,"First Amendment","https://www.oyez.org/cases/1970/89"),
            ("roe","Roe v. Wade",1973,"Privacy","https://www.oyez.org/cases/1971/70-18"),
            ("buckley","Buckley v. Valeo",1976,"First Amendment","https://www.oyez.org/cases/1975/75-436"),
            ("bakke","Regents v. Bakke",1978,"Equal Protection","https://www.oyez.org/cases/1979/76-811"),
            ("miller","United States v. Miller",1939,"Second Amendment","https://www.oyez.org/cases/1938/696"),
            ("texas_v_j","Texas v. Johnson",1989,"First Amendment","https://www.oyez.org/cases/1988/88-155"),
            ("bowers","Bowers v. Hardwick",1986,"Privacy","https://www.oyez.org/cases/1985/85-140"),
            ("casey","Planned Parenthood v. Casey",1992,"Privacy","https://www.oyez.org/cases/1991/91-744"),
            ("katzen","S. Carolina v. Katzenbach",1966,"Civil Rights","https://www.oyez.org/cases/1965/22-orig"),
            ("chevron","Chevron v. NRDC",1984,"Federal Power","https://www.oyez.org/cases/1983/82-1005"),
            ("grutter","Grutter v. Bollinger",2003,"Equal Protection","https://www.oyez.org/cases/2002/02-241"),
            ("lawrence","Lawrence v. Texas",2003,"Privacy","https://www.oyez.org/cases/2002/02-102"),
            ("windsor","United States v. Windsor",2013,"Equal Protection","https://www.oyez.org/cases/2012/12-307"),
            ("citizens","Citizens United v. FEC",2010,"First Amendment","https://www.oyez.org/cases/2008/08-205"),
            ("heller","DC v. Heller",2008,"Second Amendment","https://www.oyez.org/cases/2007/07-290"),
            ("mcdonald","McDonald v. Chicago",2010,"Second Amendment","https://www.oyez.org/cases/2009/08-1521"),
            ("obergefell","Obergefell v. Hodges",2015,"Equal Protection","https://www.oyez.org/cases/2014/14-556"),
            ("nfib","NFIB v. Sebelius",2012,"Federal Power","https://www.oyez.org/cases/2011/11-393"),
            ("wickard","Wickard v. Filburn",1942,"Federal Power","https://www.oyez.org/cases/1942/49"),
            ("shelby","Shelby County v. Holder",2013,"Civil Rights","https://www.oyez.org/cases/2012/12-96"),
            ("dobbs","Dobbs v. Jackson",2022,"Privacy","https://www.oyez.org/cases/2021/19-1392"),
            ("sffa","SFFA v. Harvard",2023,"Equal Protection","https://www.oyez.org/cases/2022/20-1199"),
            ("wv_epa","West Virginia v. EPA",2022,"Federal Power","https://www.oyez.org/cases/2021/20-1530"),
            ("kennedy_brem","Kennedy v. Bremerton",2022,"First Amendment","https://www.oyez.org/cases/2021/21-418"),
            ("loper","Loper Bright v. Raimondo",2024,"Federal Power","https://www.oyez.org/cases/2023/22-451"),
            ("powell","Powell v. Alabama",1932,"Criminal Procedure","https://www.oyez.org/cases/1932/98"),
            ("everson","Everson v. Board of Education",1947,"First Amendment","https://www.oyez.org/cases/1946/52"),
            ("bruen","NY State Rifle & Pistol v. Bruen",2022,"Second Amendment","https://www.oyez.org/cases/2021/20-843"),
            ("bump_stocks","Garland v. Cargill",2024,"Second Amendment","https://www.oyez.org/cases/2023/22-976"),
        ]

        EDGES_CN = [
            ("brown","plessy","Overrules"),("sffa","grutter","Overrules"),("sffa","bakke","Limits"),
            ("grutter","bakke","Builds On"),("shelby","katzen","Limits"),
            ("roe","griswold","Builds On"),("casey","roe","Reaffirms"),("dobbs","roe","Overrules"),("dobbs","casey","Overrules"),
            ("lawrence","bowers","Overrules"),("lawrence","griswold","Extends"),("obergefell","lawrence","Extends"),
            ("obergefell","windsor","Builds On"),("windsor","lawrence","Builds On"),
            ("miranda","mapp","Builds On"),("gideon","powell","Extends"),
            ("engel","everson","Builds On"),("lemon","engel","Builds On"),("kennedy_brem","lemon","Overrules"),
            ("texas_v_j","tinker","Extends"),("citizens","buckley","Extends"),
            ("heller","miller","Distinguishes"),("mcdonald","heller","Extends"),("bruen","heller","Builds On"),
            ("bump_stocks","bruen","Builds On"),
            ("nfib","wickard","Limits"),("wv_epa","chevron","Limits"),("loper","chevron","Overrules"),("loper","wv_epa","Builds On"),
        ]

        AREA_COLORS_CN = {"Equal Protection":"#3498DB","Privacy":"#9B59B6","First Amendment":"#E67E22",
                          "Criminal Procedure":"#27AE60","Second Amendment":"#E74C3C","Federal Power":"#F39C12","Civil Rights":"#1ABC9C"}
        REL_COLORS_CN  = {"Overrules":"#E74C3C","Builds On":"#27AE60","Extends":"#3498DB","Limits":"#E67E22","Reaffirms":"#9B59B6","Distinguishes":"#95A5A6"}
        REL_DASH_CN    = {"Overrules":"solid","Builds On":"solid","Extends":"dash","Limits":"dot","Reaffirms":"solid","Distinguishes":"dash"}

        def _build_graph_cn(cases, edges, focus_id=None, area_filter=None, rel_filter=None):
            G = nx.DiGraph()
            for cid, name, year, area, url in cases:
                if area_filter and area not in area_filter: continue
                G.add_node(cid, name=name, year=year, area=area, url=url)
            for src, tgt, rel in edges:
                if rel_filter and rel not in rel_filter: continue
                if src in G.nodes and tgt in G.nodes: G.add_edge(src, tgt, rel=rel)
            if focus_id and focus_id in G.nodes:
                neighbors = set(nx.all_neighbors(G, focus_id)) | {focus_id}
                G.remove_nodes_from([n for n in list(G.nodes) if n not in neighbors])
            return G

        def _make_figure_cn(G: nx.DiGraph) -> go.Figure:
            if len(G.nodes) == 0:
                return go.Figure().add_annotation(text="No cases match filters", showarrow=False)
            pos = nx.spring_layout(G, seed=42, k=2.5)
            fig = go.Figure()
            for src, tgt, data in G.edges(data=True):
                rel = data.get("rel","Builds On")
                x0,y0 = pos[src]; x1,y1 = pos[tgt]
                mx,my = (x0+x1)/2,(y0+y1)/2
                color = REL_COLORS_CN.get(rel,"#95A5A6"); dash = REL_DASH_CN.get(rel,"solid")
                fig.add_trace(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],mode="lines",
                                         line=dict(color=color,width=2,dash=dash),hoverinfo="skip",showlegend=False))
                fig.add_trace(go.Scatter(x=[x1],y=[y1],mode="markers",
                                         marker=dict(symbol="arrow",size=12,color=color,angleref="previous",angle=0),
                                         hoverinfo="skip",showlegend=False))
                fig.add_annotation(x=mx,y=my,text=rel,showarrow=False,font=dict(size=8,color=color),bgcolor="rgba(255,255,255,0.7)")
            for node, data in G.nodes(data=True):
                x,y = pos[node]; area = data.get("area","Other"); color = AREA_COLORS_CN.get(area,"#BDC3C7")
                name = data.get("name",node); year = data.get("year",""); url = data.get("url","")
                in_deg = G.in_degree(node); out_deg = G.out_degree(node)
                size = 14+(in_deg+out_deg)*4
                fig.add_trace(go.Scatter(x=[x],y=[y],mode="markers+text",
                                         marker=dict(size=size,color=color,line=dict(color="white",width=1.5)),
                                         text=f"{name}<br>({year})",textposition="top center",textfont=dict(size=9),
                                         hovertemplate=f"<b>{name}</b> ({year})<br>Issue Area: {area}<br>Cites: {out_deg} | Cited by: {in_deg}<extra></extra>",
                                         customdata=[url],showlegend=False))
            shown_areas: set[str] = set()
            for _, data in G.nodes(data=True):
                area = data.get("area","Other")
                if area not in shown_areas:
                    fig.add_trace(go.Scatter(x=[None],y=[None],mode="markers",marker=dict(size=10,color=AREA_COLORS_CN.get(area,"#BDC3C7")),name=area,showlegend=True))
                    shown_areas.add(area)
            shown_rels: set[str] = set()
            for _,_,data in G.edges(data=True):
                rel = data.get("rel","")
                if rel not in shown_rels:
                    fig.add_trace(go.Scatter(x=[None],y=[None],mode="lines",
                                             line=dict(color=REL_COLORS_CN.get(rel,"#95A5A6"),width=2,dash=REL_DASH_CN.get(rel,"solid")),
                                             name=rel,showlegend=True))
                    shown_rels.add(rel)
            fig.update_layout(height=680,plot_bgcolor="white",paper_bgcolor="white",
                              xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                              yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                              margin=dict(l=10,r=10,t=10,b=10),
                              legend=dict(title="Legend",x=1.01,y=1,font=dict(size=10)),hovermode="closest")
            return fig

        all_areas_cn   = sorted(set(c[3] for c in CASES_CN))
        all_rels_cn    = sorted(set(e[2] for e in EDGES_CN))
        all_names_cn   = ["(Show All)"] + sorted(c[1] for c in CASES_CN)
        id_by_name_cn  = {c[1]:c[0] for c in CASES_CN}

        col_f1_cn, col_f2_cn, col_f3_cn = st.columns(3)
        with col_f1_cn: area_filter_cn = st.multiselect("Issue Areas",all_areas_cn,default=all_areas_cn,key="cn_areas")
        with col_f2_cn: rel_filter_cn  = st.multiselect("Relationship Types",all_rels_cn,default=all_rels_cn,key="cn_rels")
        with col_f3_cn: focus_name_cn  = st.selectbox("Focus on Case",all_names_cn,key="cn_focus")

        focus_id_cn = id_by_name_cn.get(focus_name_cn) if focus_name_cn != "(Show All)" else None
        G_cn = _build_graph_cn(CASES_CN,EDGES_CN,
                                focus_id=focus_id_cn,
                                area_filter=set(area_filter_cn) if area_filter_cn else None,
                                rel_filter=set(rel_filter_cn) if rel_filter_cn else None)

        col_graph_cn, col_info_cn = st.columns([3,1])
        with col_graph_cn:
            fig_cn = _make_figure_cn(G_cn)
            st.plotly_chart(fig_cn)
        with col_info_cn:
            st.subheader("Network Stats")
            st.metric("Cases shown",len(G_cn.nodes)); st.metric("Connections",len(G_cn.edges))
            if focus_id_cn and focus_id_cn in G_cn.nodes:
                node_data_cn = G_cn.nodes[focus_id_cn]; st.divider()
                st.subheader(node_data_cn.get("name",""))
                st.markdown(f"**Year:** {node_data_cn.get('year','')}"); st.markdown(f"**Area:** {node_data_cn.get('area','')}")
                cites_cn = list(G_cn.successors(focus_id_cn)); cited_by_cn = list(G_cn.predecessors(focus_id_cn))
                if cites_cn:
                    st.markdown("**Cites:**")
                    for cid in cites_cn:
                        rel_cn = G_cn.edges[focus_id_cn,cid]["rel"]; name_cn = G_cn.nodes[cid].get("name",cid)
                        st.markdown(f"- *{rel_cn}* → {name_cn}")
                if cited_by_cn:
                    st.markdown("**Cited by:**")
                    for cid in cited_by_cn:
                        rel_cn = G_cn.edges[cid,focus_id_cn]["rel"]; name_cn = G_cn.nodes[cid].get("name",cid)
                        st.markdown(f"- *{rel_cn}* ← {name_cn}")
                url_cn = node_data_cn.get("url","")
                if url_cn: st.markdown(f"[Open on Oyez ↗]({url_cn})")

        st.divider(); st.subheader("Most Influential Cases")
        rows_cn = [{"Case":d.get("name",n),"Year":d.get("year",""),"Area":d.get("area",""),
                    "Times Cited":G_cn.in_degree(n),"Cases It Cites":G_cn.out_degree(n)} for n,d in G_cn.nodes(data=True)]
        if rows_cn:
            inf_df_cn = pd.DataFrame(rows_cn).sort_values("Times Cited",ascending=False)
            st.dataframe(inf_df_cn,height=300,hide_index=True)

        with st.expander("All Citation Relationships"):
            edge_rows_cn = [{"Citing Case":G_cn.nodes[s].get("name",s),"Relationship":d.get("rel",""),"Cited Case":G_cn.nodes[t].get("name",t)}
                            for s,t,d in G_cn.edges(data=True)]
            if edge_rows_cn: st.dataframe(pd.DataFrame(edge_rows_cn),height=300,hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: CASE PRECEDENT NETWORK (11_Case_Network)
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_precedent:
        st.markdown(
            "An interactive graph of how landmark SCOTUS cases cite, extend, rely on, or overrule each other. "
            "Node size reflects number of connections. Edge color shows the type of relationship."
        )

        CASES_PN = {
            "marbury":     ("Marbury v. Madison",           1803, "Judicial Power",       None),
            "mcculloch":   ("McCulloch v. Maryland",         1819, "Federalism",           None),
            "schenck":     ("Schenck v. United States",      1919, "Free Speech",          "1st"),
            "nyt_sullivan":("NY Times v. Sullivan",          1964, "Free Speech",          "1st"),
            "brandenburg": ("Brandenburg v. Ohio",           1969, "Free Speech",          "1st"),
            "texas_johnson":("Texas v. Johnson",             1989, "Free Speech",          "1st"),
            "citizens_utd":("Citizens United v. FEC",        2010, "Free Speech",          "1st"),
            "snyder_phelps":("Snyder v. Phelps",             2011, "Free Speech",          "1st"),
            "heller_pn":   ("D.C. v. Heller",                2008, "Right to Bear Arms",   "2nd"),
            "mcdonald_pn": ("McDonald v. Chicago",           2010, "Right to Bear Arms",   "2nd"),
            "bruen_pn":    ("NY Rifle & Pistol v. Bruen",    2022, "Right to Bear Arms",   "2nd"),
            "mapp_pn":     ("Mapp v. Ohio",                  1961, "Search & Seizure",     "4th"),
            "katz":        ("Katz v. United States",         1967, "Search & Seizure",     "4th"),
            "terry":       ("Terry v. Ohio",                 1968, "Search & Seizure",     "4th"),
            "jones_pn":    ("United States v. Jones",        2012, "Search & Seizure",     "4th"),
            "riley_pn":    ("Riley v. California",           2014, "Search & Seizure",     "4th"),
            "carpenter_pn":("Carpenter v. United States",    2018, "Search & Seizure",     "4th"),
            "miranda_pn":  ("Miranda v. Arizona",            1966, "Self-Incrimination",   "5th"),
            "kelo":        ("Kelo v. City of New London",    2005, "Takings",              "5th"),
            "gideon_pn":   ("Gideon v. Wainwright",          1963, "Right to Counsel",     "6th"),
            "furman":      ("Furman v. Georgia",             1972, "Cruel & Unusual",      "8th"),
            "gregg":       ("Gregg v. Georgia",              1976, "Cruel & Unusual",      "8th"),
            "atkins":      ("Atkins v. Virginia",            2002, "Cruel & Unusual",      "8th"),
            "roper":       ("Roper v. Simmons",              2005, "Cruel & Unusual",      "8th"),
            "griswold_pn": ("Griswold v. Connecticut",       1965, "Privacy",              "14th"),
            "roe_pn":      ("Roe v. Wade",                   1973, "Privacy",              "14th"),
            "dobbs_pn":    ("Dobbs v. Jackson",              2022, "Privacy",              "14th"),
            "brown_pn":    ("Brown v. Board of Education",   1954, "Equal Protection",     "14th"),
            "loving":      ("Loving v. Virginia",            1967, "Equal Protection",     "14th"),
            "grutter_pn":  ("Grutter v. Bollinger",          2003, "Equal Protection",     "14th"),
            "sffa_pn":     ("SFFA v. Harvard",               2023, "Equal Protection",     "14th"),
            "obergefell_pn":("Obergefell v. Hodges",         2015, "Equal Protection",     "14th"),
        }

        EDGES_PN = [
            ("marbury","mcculloch","Extended","Federal supremacy built on judicial review"),
            ("schenck","nyt_sullivan","Distinguished","Sullivan replaced clear and present danger for press"),
            ("schenck","brandenburg","Overruled","Brandenburg replaced Schenck's test"),
            ("brandenburg","texas_johnson","Applied","Johnson applied the Brandenburg test"),
            ("nyt_sullivan","snyder_phelps","Extended","Phelps extended public-concern speech protection"),
            ("nyt_sullivan","citizens_utd","Relied on","Citizens United built on Sullivan's speech logic"),
            ("texas_johnson","citizens_utd","Relied on","Citizens United cited Johnson for symbolic speech"),
            ("heller_pn","mcdonald_pn","Extended","McDonald incorporated Heller against the states"),
            ("heller_pn","bruen_pn","Extended","Bruen expanded Heller; required historical tradition test"),
            ("mcdonald_pn","bruen_pn","Extended","Bruen built on McDonald's incorporation doctrine"),
            ("mapp_pn","katz","Extended","Katz extended exclusionary rule to electronic surveillance"),
            ("katz","terry","Distinguished","Terry allowed stops on reasonable suspicion"),
            ("katz","jones_pn","Extended","Jones applied Katz to GPS tracking"),
            ("katz","riley_pn","Extended","Riley applied Katz to cell phone searches"),
            ("katz","carpenter_pn","Extended","Carpenter extended Katz to cell-site location data"),
            ("riley_pn","carpenter_pn","Relied on","Carpenter cited Riley's digital-privacy reasoning"),
            ("griswold_pn","roe_pn","Extended","Roe extended Griswold's privacy right to abortion"),
            ("roe_pn","dobbs_pn","Overruled","Dobbs overruled Roe"),
            ("griswold_pn","obergefell_pn","Relied on","Obergefell relied on Griswold's intimate-liberty reasoning"),
            ("loving","obergefell_pn","Extended","Obergefell extended Loving's marriage-as-fundamental-right"),
            ("roe_pn","obergefell_pn","Relied on","Obergefell cited Roe in substantive due process analysis"),
            ("brown_pn","loving","Extended","Loving extended Brown's anti-classification principle"),
            ("brown_pn","grutter_pn","Relied on","Grutter built on Brown's equal protection framework"),
            ("grutter_pn","sffa_pn","Overruled","SFFA overruled Grutter"),
            ("furman","gregg","Distinguished","Gregg allowed reinstated death penalty with guided discretion"),
            ("gregg","atkins","Extended","Atkins carved out intellectual disability from Gregg"),
            ("atkins","roper","Extended","Roper extended Atkins' reasoning to juveniles"),
            ("griswold_pn","miranda_pn","Relied on","Both grounded in substantive due process"),
            ("gideon_pn","miranda_pn","Relied on","Miranda built on Gideon's right-to-counsel guarantee"),
            ("marbury","furman","Relied on","Court cited judicial-review authority to reinterpret 8th Amend."),
        ]

        RELATION_COLORS_PN = {"Extended":"#27AE60","Overruled":"#E74C3C","Relied on":"#3498DB","Applied":"#9B59B6","Distinguished":"#F39C12"}
        AREA_COLORS_PN = {
            "Free Speech":"#2980B9","Right to Bear Arms":"#8E44AD","Search & Seizure":"#E67E22",
            "Self-Incrimination":"#C0392B","Takings":"#16A085","Right to Counsel":"#27AE60",
            "Cruel & Unusual":"#E74C3C","Privacy":"#F39C12","Equal Protection":"#D35400",
            "Judicial Power":"#7F8C8D","Federalism":"#BDC3C7",
        }

        def _build_graph_pn(case_filter=None, relation_filter=None):
            G = nx.DiGraph()
            for cid, (name,year,area,amend) in CASES_PN.items():
                G.add_node(cid,name=name,year=year,area=area,amend=amend)
            for src, tgt, rel, desc in EDGES_PN:
                if relation_filter and rel not in relation_filter: continue
                if case_filter:
                    if src not in case_filter and tgt not in case_filter: continue
                G.add_edge(src,tgt,relation=rel,description=desc)
            return G

        def _build_network_figure_pn(G: nx.DiGraph, highlight_id=None) -> go.Figure:
            pos = nx.spring_layout(G,seed=42,k=2.5,iterations=80)
            edge_traces = []
            for src,tgt,data in G.edges(data=True):
                x0,y0 = pos[src]; x1,y1 = pos[tgt]
                rel = data.get("relation","Relied on"); color = RELATION_COLORS_PN.get(rel,"#95A5A6")
                edge_traces.append(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],mode="lines",
                                              line=dict(width=2,color=color),hoverinfo="none",showlegend=False))
                edge_traces.append(go.Scatter(x=[x1],y=[y1],mode="markers",
                                               marker=dict(size=6,color=color,symbol="arrow",angleref="previous"),
                                               hoverinfo="none",showlegend=False))
            node_ids   = list(G.nodes())
            node_names = [G.nodes[n]["name"] for n in node_ids]
            node_years = [G.nodes[n]["year"] for n in node_ids]
            node_areas = [G.nodes[n]["area"] for n in node_ids]
            node_colors  = [AREA_COLORS_PN.get(a,"#95A5A6") for a in node_areas]
            node_sizes   = [min(22+G.degree(n)*4+(12 if n==highlight_id else 0),55) for n in node_ids]
            node_borders = ["white" if n!=highlight_id else "#FFD700" for n in node_ids]
            border_widths= [2 if n!=highlight_id else 5 for n in node_ids]
            hover = [f"<b>{name}</b> ({year})<br>Area: {area}<br>Connections: {G.degree(nid)}"
                     for nid,name,year,area in zip(node_ids,node_names,node_years,node_areas)]
            node_trace = go.Scatter(
                x=[pos[n][0] for n in node_ids],y=[pos[n][1] for n in node_ids],
                mode="markers+text",
                marker=dict(size=node_sizes,color=node_colors,line=dict(color=node_borders,width=border_widths),opacity=0.92),
                text=[f"<b>{n}</b>" for n in node_names],textposition="top center",textfont=dict(size=9,color="#2C3E50"),
                hovertext=hover,hoverinfo="text",showlegend=False)
            fig = go.Figure(data=edge_traces+[node_trace])
            for rel, color in RELATION_COLORS_PN.items():
                fig.add_trace(go.Scatter(x=[None],y=[None],mode="lines",line=dict(color=color,width=3),name=rel,showlegend=True))
            fig.update_layout(title="SCOTUS Case Precedent Network",height=680,
                              xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                              yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                              plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=20,r=20,t=50,b=20),
                              legend=dict(title="Relationship Type",orientation="v",x=1.01,y=1,xanchor="left"),
                              hovermode="closest")
            return fig

        col1_pn, col2_pn, col3_pn = st.columns(3)
        with col1_pn:
            all_areas_pn = sorted(set(v[2] for v in CASES_PN.values()))
            sel_areas_pn = st.multiselect("Filter by Legal Area",all_areas_pn,default=[],key="pn_areas")
        with col2_pn:
            sel_rels_pn = st.multiselect("Filter by Relationship Type",list(RELATION_COLORS_PN.keys()),default=[],key="pn_rels")
        with col3_pn:
            all_case_names_pn = {v[0]:k for k,v in CASES_PN.items()}
            focus_name_pn = st.selectbox("Focus on a Case (shows direct neighbors)",["— Show all —"]+sorted(all_case_names_pn.keys()),key="pn_focus")

        pn_case_filter = None; pn_highlight_id = None
        if focus_name_pn != "— Show all —":
            focus_id_pn = all_case_names_pn[focus_name_pn]
            G_full_pn = _build_graph_pn()
            neighbors_pn = set(G_full_pn.predecessors(focus_id_pn)) | set(G_full_pn.successors(focus_id_pn))
            pn_case_filter = neighbors_pn | {focus_id_pn}; pn_highlight_id = focus_id_pn

        if sel_areas_pn:
            area_filter_ids_pn = {k for k,v in CASES_PN.items() if v[2] in sel_areas_pn}
            pn_case_filter = (pn_case_filter & area_filter_ids_pn) if pn_case_filter is not None else area_filter_ids_pn

        G_pn = _build_graph_pn(case_filter=pn_case_filter, relation_filter=set(sel_rels_pn) if sel_rels_pn else None)

        if G_pn.number_of_nodes() == 0:
            st.warning("No cases match the selected filters.")
        else:
            fig_pn = _build_network_figure_pn(G_pn, highlight_id=pn_highlight_id)
            st.plotly_chart(fig_pn)
            st.caption(f"Showing {G_pn.number_of_nodes()} cases and {G_pn.number_of_edges()} relationships. Hover for details.")
            st.divider(); st.subheader("Case Detail")
            detail_name_pn = st.selectbox("Select a case to inspect its connections",sorted(all_case_names_pn.keys()),
                                           index=sorted(all_case_names_pn.keys()).index(focus_name_pn) if focus_name_pn != "— Show all —" else 0,
                                           key="pn_detail_sel")
            detail_id_pn = all_case_names_pn[detail_name_pn]
            G_full2_pn = _build_graph_pn()
            outgoing_pn = [(CASES_PN[tgt][0],d["relation"],d["description"]) for _,tgt,d in G_full2_pn.out_edges(detail_id_pn,data=True)]
            incoming_pn = [(CASES_PN[src][0],d["relation"],d["description"]) for src,_,d in G_full2_pn.in_edges(detail_id_pn,data=True)]
            case_info_pn = CASES_PN[detail_id_pn]
            st.markdown(f"### {case_info_pn[0]} ({case_info_pn[1]})")
            st.markdown(f"**Area:** {case_info_pn[2]}  |  **Amendment:** {case_info_pn[3] or 'N/A'}")
            col_out_pn, col_in_pn = st.columns(2)
            with col_out_pn:
                st.markdown("**This case influenced →**")
                if outgoing_pn:
                    for target,rel,desc in outgoing_pn:
                        color = RELATION_COLORS_PN.get(rel,"#95A5A6")
                        st.markdown(f"<span style='color:{color};font-weight:bold'>{rel}</span> → **{target}**<br><small>{desc}</small>",unsafe_allow_html=True); st.markdown("")
                else: st.markdown("_No outgoing links in this dataset._")
            with col_in_pn:
                st.markdown("**← This case was influenced by**")
                if incoming_pn:
                    for source,rel,desc in incoming_pn:
                        color = RELATION_COLORS_PN.get(rel,"#95A5A6")
                        st.markdown(f"**{source}** → <span style='color:{color};font-weight:bold'>{rel}</span><br><small>{desc}</small>",unsafe_allow_html=True); st.markdown("")
                else: st.markdown("_No incoming links in this dataset._")

            st.divider(); st.subheader("Most Connected Cases")
            G_all_pn = _build_graph_pn()
            degree_data_pn = [{"Case":CASES_PN[n][0],"Year":CASES_PN[n][1],"Area":CASES_PN[n][2],
                                "Amendment":CASES_PN[n][3] or "—","Total Connections":G_all_pn.degree(n),
                                "Influenced":G_all_pn.out_degree(n),"Influenced by":G_all_pn.in_degree(n)}
                               for n in G_all_pn.nodes()]
            degree_df_pn = pd.DataFrame(degree_data_pn).sort_values("Total Connections",ascending=False)
            st.dataframe(degree_df_pn,height=350)
            with st.expander("Full Relationship Table"):
                edge_rows_pn = [{"From":CASES_PN[s][0],"Relationship":r,"To":CASES_PN[t][0],"Description":d}
                                for s,t,r,d in EDGES_PN]
                edge_df_pn = pd.DataFrame(edge_rows_pn)
                rel_filter_pn = st.multiselect("Filter relationships",list(RELATION_COLORS_PN.keys()),default=[],key="pn_rel_filter")
                display_edges_pn = edge_df_pn[edge_df_pn["Relationship"].isin(rel_filter_pn)] if rel_filter_pn else edge_df_pn
                st.dataframe(display_edges_pn,height=400)

def _page_research():
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

        available_terms_d = list(range(CURRENT_YEAR-1, CURRENT_YEAR-31,-1))
        all_justice_names = [j[0] for j in JUSTICES_RECENT if j[0].split()[-1] not in CONSERVATIVE_BLOC]

        col1_d, col2_d = st.columns([2,1])
        with col1_d:
            terms_sel_d = st.multiselect("Terms to include", available_terms_d, default=available_terms_d[:12],
                                          max_selections=15, key="drift_terms")
        with col2_d:
            justices_sel_d = st.multiselect("Justices to show", [j.split()[-1] for j in all_justice_names],
                                             default=[j for j in ["Stevens","O'Connor","Kennedy","Souter","Roberts",
                                                      "Sotomayor","Kagan","Kavanaugh","Jackson"]
                                                      if j in [n.split()[-1] for n in all_justice_names]],
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

# ── Page ─────────────────────────────────────────────────────────────────────
_tab_0, _tab_1 = st.tabs(["📚 Legal Topics", "🕸️ Networks"])
with _tab_0:
    _page_legal_topics()
with _tab_1:
    _page_networks()
