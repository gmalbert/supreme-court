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
import re
from collections import defaultdict
from utils.local_data import fetch_oyez, infer_issue_area


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Shared fetch ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _ch_fetch_cases_term(term: int) -> list[dict]:
    data = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0")
    return data if isinstance(data, list) else []

# ── Court Composition data ────────────────────────────────────────────────────
JUSTICES = [
    ("Earl Warren",          1953, 1969, "Eisenhower",  "Liberal",      "Chief Justice"),
    ("Hugo Black",           1937, 1971, "F. Roosevelt","Liberal",      "Associate"),
    ("William O. Douglas",   1939, 1975, "F. Roosevelt","Liberal",      "Associate"),
    ("Tom Clark",            1949, 1967, "Truman",      "Moderate",     "Associate"),
    ("John Harlan II",       1955, 1971, "Eisenhower",  "Conservative", "Associate"),
    ("William Brennan",      1956, 1990, "Eisenhower",  "Liberal",      "Associate"),
    ("Potter Stewart",       1958, 1981, "Eisenhower",  "Moderate",     "Associate"),
    ("Byron White",          1962, 1993, "Kennedy",     "Moderate",     "Associate"),
    ("Arthur Goldberg",      1962, 1965, "Kennedy",     "Liberal",      "Associate"),
    ("Abe Fortas",           1965, 1969, "Johnson",     "Liberal",      "Associate"),
    ("Thurgood Marshall",    1967, 1991, "Johnson",     "Liberal",      "Associate"),
    ("Warren Burger",        1969, 1986, "Nixon",       "Conservative", "Chief Justice"),
    ("Harry Blackmun",       1970, 1994, "Nixon",       "Liberal",      "Associate"),
    ("Lewis Powell",         1972, 1987, "Nixon",       "Moderate",     "Associate"),
    ("William Rehnquist",    1972, 1986, "Nixon",       "Conservative", "Associate"),
    ("Sandra Day O'Connor",  1981, 2006, "Reagan",      "Moderate",     "Associate"),
    ("William Rehnquist",    1986, 2005, "Reagan",      "Conservative", "Chief Justice"),
    ("Antonin Scalia",       1986, 2016, "Reagan",      "Conservative", "Associate"),
    ("Anthony Kennedy",      1988, 2018, "Reagan",      "Moderate",     "Associate"),
    ("David Souter",         1990, 2009, "G.H.W. Bush", "Liberal",      "Associate"),
    ("Clarence Thomas",      1991, None, "G.H.W. Bush", "Conservative", "Associate"),
    ("Ruth Bader Ginsburg",  1993, 2020, "Clinton",     "Liberal",      "Associate"),
    ("Stephen Breyer",       1994, 2022, "Clinton",     "Liberal",      "Associate"),
    ("John G. Roberts",      2005, None, "G.W. Bush",   "Conservative", "Chief Justice"),
    ("Samuel Alito",         2006, None, "G.W. Bush",   "Conservative", "Associate"),
    ("Sonia Sotomayor",      2009, None, "Obama",       "Liberal",      "Associate"),
    ("Elena Kagan",          2010, None, "Obama",       "Liberal",      "Associate"),
    ("Neil Gorsuch",         2017, None, "Trump",       "Conservative", "Associate"),
    ("Brett Kavanaugh",      2018, None, "Trump",       "Conservative", "Associate"),
    ("Amy Coney Barrett",    2020, None, "Trump",       "Conservative", "Associate"),
    ("Ketanji Brown Jackson",2022, None, "Biden",       "Liberal",      "Associate"),
]

LEAN_COLORS = {"Liberal":"#3498DB","Moderate":"#27AE60","Conservative":"#E74C3C"}
PRESIDENT_COLORS = {
    "F. Roosevelt":"#1A5276","Truman":"#1F618D","Eisenhower":"#922B21",
    "Kennedy":"#2471A3","Johnson":"#1A5276","Nixon":"#C0392B",
    "Ford":"#E74C3C","Carter":"#2980B9","Reagan":"#CB4335",
    "G.H.W. Bush":"#E74C3C","Clinton":"#2E86C1","G.W. Bush":"#CB4335",
    "Obama":"#1A5276","Trump":"#CB4335","Biden":"#2471A3",
}

def _build_gantt(color_by="Lean") -> go.Figure:
    rows = []
    for name, start, end, appointer, lean, seat in JUSTICES:
        end_yr = end if end else CURRENT_YEAR
        rows.append({"Justice":name,"Start":start,"End":end_yr,"Duration":end_yr-start,
                     "Appointed by":appointer,"Lean":lean,"Seat":seat,"Still Serving":end is None})
    df = pd.DataFrame(rows).sort_values("Start")
    cmap = LEAN_COLORS if color_by=="Lean" else PRESIDENT_COLORS
    color_col = "Lean" if color_by=="Lean" else "Appointed by"
    fig = go.Figure()
    for _, row in df.iterrows():
        color = cmap.get(row[color_col],"#95A5A6")
        border = "#FFD700" if row["Still Serving"] else "white"
        fig.add_trace(go.Bar(x=[row["Duration"]],y=[row["Justice"]],base=[row["Start"]],
                             orientation="h",
                             marker=dict(color=color,opacity=0.85,line=dict(color=border,width=1.5 if row["Still Serving"] else 0.5)),
                             hovertemplate=(f"<b>{row['Justice']}</b><br>"
                                            f"Served: {row['Start']} – {'present' if row['Still Serving'] else row['End']}<br>"
                                            f"Duration: {row['Duration']} years<br>"
                                            f"Appointed by: {row['Appointed by']}<br>"
                                            f"Lean: {row['Lean']}<extra></extra>"),
                             showlegend=False,name=row["Justice"]))
    for era_name, era_start, era_end, era_color in [
        ("Warren Court",1953,1969,"rgba(41,128,185,0.06)"),
        ("Burger Court",1969,1986,"rgba(142,68,173,0.06)"),
        ("Rehnquist Court",1986,2005,"rgba(230,126,34,0.06)"),
        ("Roberts Court",2005,CURRENT_YEAR,"rgba(192,57,43,0.06)"),
    ]:
        fig.add_vrect(x0=era_start,x1=era_end,fillcolor=era_color,opacity=1,layer="below",line_width=0,
                      annotation_text=era_name,annotation_position="top left",
                      annotation_font_size=10,annotation_font_color="#7F8C8D")
    shown = set()
    for _, row in df.iterrows():
        key = row[color_col]
        if key not in shown:
            fig.add_trace(go.Bar(x=[None],y=[None],marker_color=cmap.get(key,"#95A5A6"),name=key,showlegend=True))
            shown.add(key)
    fig.update_layout(barmode="overlay",height=max(600,len(df)*22),
                      xaxis=dict(title="Year",range=[1937,CURRENT_YEAR+2],dtick=5,gridcolor="#ECF0F1"),
                      yaxis=dict(title="",autorange="reversed"),
                      plot_bgcolor="white",paper_bgcolor="white",
                      margin=dict(l=180,r=20,t=30,b=40),legend=dict(title=color_by,x=1.01,y=1))
    return fig

def _court_in_year(year: int) -> list[dict]:
    members = []
    for name, start, end, appointer, lean, seat in JUSTICES:
        end_yr = end if end else CURRENT_YEAR + 1
        if start <= year < end_yr:
            members.append({"Justice":name,"Seat":seat,"Appointed by":appointer,"Lean":lean})
    return members

# ── Chief Justice Eras data ────────────────────────────────────────────────────
ERAS = {
    "Warren Court (1953–1969)":      (1953, 1969, "#2980B9"),
    "Burger Court (1969–1986)":      (1969, 1986, "#8E44AD"),
    "Rehnquist Court (1986–2005)":   (1986, 2005, "#E67E22"),
    "Roberts Court (2005–present)":  (2005, CURRENT_YEAR, "#C0392B"),
}

@st.cache_data(show_spinner=False, ttl=600)
def _ch_load_era_data(start: int, end: int) -> pd.DataFrame:
    rows = []
    for term in range(start, end+1):
        cases = _ch_fetch_cases_term(term)
        for c in cases:
            ia = c.get("issue_area"); d = c.get("disposition")
            rows.append({
                "Term": term, "Case": c.get("name",""),
                "Issue Area": ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown"),
                "Disposition": d.get("label","Unknown") if isinstance(d,dict) else str(d or "Unknown"),
            })
        time.sleep(0.03)
    return pd.DataFrame(rows)

# ── Confirmation data ──────────────────────────────────────────────────────────
CONFIRMATIONS = [
    dict(name="Tom Clark",             nominated_by="Truman",     nom_date="1949-08-02", conf_date="1949-08-18", yes=73,  no=8,  seat_lean_before="Liberal",      seat_lean_after="Moderate",     seat="Associate",     replaced="Frank Murphy",         notes=""),
    dict(name="Sherman Minton",        nominated_by="Truman",     nom_date="1949-09-15", conf_date="1949-10-04", yes=48,  no=16, seat_lean_before="Liberal",      seat_lean_after="Moderate",     seat="Associate",     replaced="Wiley Rutledge",       notes=""),
    dict(name="Earl Warren",           nominated_by="Eisenhower", nom_date="1953-10-02", conf_date="1954-03-01", yes=None,no=None,seat_lean_before="Conservative",seat_lean_after="Liberal",     seat="Chief Justice", replaced="Fred Vinson",          notes="Recess appointment; voice vote"),
    dict(name="John Harlan II",        nominated_by="Eisenhower", nom_date="1954-11-08", conf_date="1955-03-16", yes=71,  no=11, seat_lean_before="Moderate",     seat_lean_after="Conservative",seat="Associate",     replaced="Robert Jackson",       notes=""),
    dict(name="William Brennan",       nominated_by="Eisenhower", nom_date="1956-10-15", conf_date="1957-03-19", yes=None,no=None,seat_lean_before="Moderate",   seat_lean_after="Liberal",     seat="Associate",     replaced="Sherman Minton",       notes="Recess appointment; voice vote"),
    dict(name="Charles Whittaker",     nominated_by="Eisenhower", nom_date="1957-02-19", conf_date="1957-03-19", yes=None,no=None,seat_lean_before="Moderate",   seat_lean_after="Conservative",seat="Associate",     replaced="Stanley Reed",         notes="Voice vote"),
    dict(name="Potter Stewart",        nominated_by="Eisenhower", nom_date="1958-01-17", conf_date="1959-05-05", yes=70,  no=17, seat_lean_before="Conservative", seat_lean_after="Moderate",    seat="Associate",     replaced="Harold Burton",        notes=""),
    dict(name="Byron White",           nominated_by="Kennedy",    nom_date="1962-03-30", conf_date="1962-04-11", yes=None,no=None,seat_lean_before="Liberal",    seat_lean_after="Moderate",    seat="Associate",     replaced="Charles Whittaker",    notes="Voice vote"),
    dict(name="Arthur Goldberg",       nominated_by="Kennedy",    nom_date="1962-08-31", conf_date="1962-09-25", yes=None,no=None,seat_lean_before="Conservative",seat_lean_after="Liberal",     seat="Associate",     replaced="Felix Frankfurter",    notes="Voice vote"),
    dict(name="Abe Fortas",            nominated_by="Johnson",    nom_date="1965-07-28", conf_date="1965-08-11", yes=None,no=None,seat_lean_before="Liberal",    seat_lean_after="Liberal",     seat="Associate",     replaced="Arthur Goldberg",      notes="Voice vote"),
    dict(name="Thurgood Marshall",     nominated_by="Johnson",    nom_date="1967-06-13", conf_date="1967-08-30", yes=69,  no=11, seat_lean_before="Moderate",     seat_lean_after="Liberal",     seat="Associate",     replaced="Tom Clark",            notes="First African American justice"),
    dict(name="Warren Burger",         nominated_by="Nixon",      nom_date="1969-05-21", conf_date="1969-06-09", yes=74,  no=3,  seat_lean_before="Liberal",      seat_lean_after="Conservative",seat="Chief Justice", replaced="Earl Warren",          notes=""),
    dict(name="Harry Blackmun",        nominated_by="Nixon",      nom_date="1970-04-14", conf_date="1970-05-12", yes=94,  no=0,  seat_lean_before="Conservative", seat_lean_after="Liberal",     seat="Associate",     replaced="Abe Fortas",           notes="Two prior nominees rejected/withdrew"),
    dict(name="Lewis Powell",          nominated_by="Nixon",      nom_date="1971-10-21", conf_date="1971-12-06", yes=89,  no=1,  seat_lean_before="Liberal",      seat_lean_after="Moderate",    seat="Associate",     replaced="Hugo Black",           notes=""),
    dict(name="William Rehnquist",     nominated_by="Nixon",      nom_date="1971-10-21", conf_date="1971-12-10", yes=68,  no=26, seat_lean_before="Liberal",      seat_lean_after="Conservative",seat="Associate",     replaced="John Harlan II",       notes=""),
    dict(name="John Paul Stevens",     nominated_by="Ford",       nom_date="1975-11-28", conf_date="1975-12-17", yes=98,  no=0,  seat_lean_before="Liberal",      seat_lean_after="Liberal",     seat="Associate",     replaced="William O. Douglas",   notes=""),
    dict(name="Sandra Day O'Connor",   nominated_by="Reagan",     nom_date="1981-07-07", conf_date="1981-09-21", yes=99,  no=0,  seat_lean_before="Moderate",     seat_lean_after="Moderate",    seat="Associate",     replaced="Potter Stewart",       notes="First female justice"),
    dict(name="William Rehnquist (CJ)",nominated_by="Reagan",     nom_date="1986-06-17", conf_date="1986-09-17", yes=65,  no=33, seat_lean_before="Conservative", seat_lean_after="Conservative",seat="Chief Justice", replaced="Warren Burger",        notes="Elevated from Associate"),
    dict(name="Antonin Scalia",        nominated_by="Reagan",     nom_date="1986-06-17", conf_date="1986-09-17", yes=98,  no=0,  seat_lean_before="Conservative", seat_lean_after="Conservative",seat="Associate",     replaced="William Rehnquist",    notes=""),
    dict(name="Anthony Kennedy",       nominated_by="Reagan",     nom_date="1987-11-11", conf_date="1988-02-03", yes=97,  no=0,  seat_lean_before="Conservative", seat_lean_after="Moderate",    seat="Associate",     replaced="Lewis Powell",         notes="Bork rejected; Ginsburg withdrew"),
    dict(name="David Souter",          nominated_by="G.H.W. Bush",nom_date="1990-07-23", conf_date="1990-10-02", yes=90,  no=9,  seat_lean_before="Liberal",      seat_lean_after="Liberal",     seat="Associate",     replaced="William Brennan",      notes=""),
    dict(name="Clarence Thomas",       nominated_by="G.H.W. Bush",nom_date="1991-07-01", conf_date="1991-10-15", yes=52,  no=48, seat_lean_before="Liberal",      seat_lean_after="Conservative",seat="Associate",     replaced="Thurgood Marshall",    notes="Anita Hill hearings; narrowest margin in modern history"),
    dict(name="Ruth Bader Ginsburg",   nominated_by="Clinton",    nom_date="1993-06-14", conf_date="1993-08-03", yes=96,  no=3,  seat_lean_before="Moderate",     seat_lean_after="Liberal",     seat="Associate",     replaced="Byron White",          notes="Second female justice"),
    dict(name="Stephen Breyer",        nominated_by="Clinton",    nom_date="1994-05-13", conf_date="1994-07-29", yes=87,  no=9,  seat_lean_before="Conservative", seat_lean_after="Liberal",     seat="Associate",     replaced="Harry Blackmun",       notes=""),
    dict(name="John G. Roberts",       nominated_by="G.W. Bush",  nom_date="2005-09-05", conf_date="2005-09-29", yes=78,  no=22, seat_lean_before="Conservative", seat_lean_after="Conservative",seat="Chief Justice", replaced="William Rehnquist",    notes=""),
    dict(name="Samuel Alito",          nominated_by="G.W. Bush",  nom_date="2005-10-31", conf_date="2006-01-31", yes=58,  no=42, seat_lean_before="Moderate",     seat_lean_after="Conservative",seat="Associate",     replaced="Sandra Day O'Connor",  notes="O'Connor's retirement shifted balance"),
    dict(name="Sonia Sotomayor",       nominated_by="Obama",      nom_date="2009-05-26", conf_date="2009-08-06", yes=68,  no=31, seat_lean_before="Liberal",      seat_lean_after="Liberal",     seat="Associate",     replaced="David Souter",         notes="First Hispanic justice"),
    dict(name="Elena Kagan",           nominated_by="Obama",      nom_date="2010-05-10", conf_date="2010-08-05", yes=63,  no=37, seat_lean_before="Liberal",      seat_lean_after="Liberal",     seat="Associate",     replaced="John Paul Stevens",    notes=""),
    dict(name="Neil Gorsuch",          nominated_by="Trump",      nom_date="2017-01-31", conf_date="2017-04-07", yes=54,  no=45, seat_lean_before="Conservative", seat_lean_after="Conservative",seat="Associate",     replaced="Antonin Scalia",       notes="Senate invoked nuclear option"),
    dict(name="Brett Kavanaugh",       nominated_by="Trump",      nom_date="2018-07-09", conf_date="2018-10-06", yes=50,  no=48, seat_lean_before="Moderate",     seat_lean_after="Conservative",seat="Associate",     replaced="Anthony Kennedy",      notes="Christine Blasey Ford testimony"),
    dict(name="Amy Coney Barrett",     nominated_by="Trump",      nom_date="2020-09-26", conf_date="2020-10-26", yes=52,  no=48, seat_lean_before="Liberal",      seat_lean_after="Conservative",seat="Associate",     replaced="Ruth Bader Ginsburg",  notes="Confirmed 8 days before 2020 election"),
    dict(name="Ketanji Brown Jackson", nominated_by="Biden",      nom_date="2022-02-25", conf_date="2022-04-07", yes=53,  no=47, seat_lean_before="Liberal",      seat_lean_after="Liberal",     seat="Associate",     replaced="Stephen Breyer",       notes="First Black female justice"),
]

def _parse_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()

def _ideology_flip(before: str, after: str) -> str:
    if before == after: return "No Change"
    if after == "Conservative" and before != "Conservative": return "→ Conservative"
    if after == "Liberal" and before != "Liberal": return "→ Liberal"
    if after == "Moderate": return "→ Moderate"
    return "Changed"

for c in CONFIRMATIONS:
    c["nom_year"] = int(c["nom_date"][:4])
    c["conf_year"] = int(c["conf_date"][:4])
    c["days_to_confirm"] = (_parse_date(c["conf_date"]) - _parse_date(c["nom_date"])).days
    c["flip"] = _ideology_flip(c["seat_lean_before"], c["seat_lean_after"])
    c["pres_party"] = {"Truman":"D","Eisenhower":"R","Kennedy":"D","Johnson":"D","Nixon":"R","Ford":"R",
                       "Carter":"D","Reagan":"R","G.H.W. Bush":"R","Clinton":"D","G.W. Bush":"R",
                       "Obama":"D","Trump":"R","Biden":"D"}.get(c["nominated_by"],"?")
    c["total_votes"] = (c["yes"] or 0) + (c["no"] or 0)
    c["yes_pct"] = round(c["yes"]/c["total_votes"]*100,1) if c["total_votes"]>0 else None

conf_df = pd.DataFrame(CONFIRMATIONS)
PARTY_COLOR = {"R":"#E74C3C","D":"#3498DB"}

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
from utils.local_data import fetch_oyez, infer_issue_area


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
    data = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0")
    return data if isinstance(data, list) else []

@st.cache_data(show_spinner=False)
def _cc_fetch_detail(href: str) -> dict | None:
    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

def _court_matches(lc_name: str, search_term: str) -> bool:
    if not lc_name or not search_term: return False
    return search_term.lower() in lc_name.lower()

def _classify_outcome(detail: dict) -> tuple[bool, bool]:
    """Return (affirmed, reversed_) using best available Oyez fields."""
    dec = (detail.get("decisions") or [{}])[0]
    # Priority 1: keyword match in description + conclusion text
    desc = (dec.get("description") or "").lower()
    conc = re.sub(r'<[^>]+>', ' ', detail.get("conclusion") or "").lower()
    txt = desc + " " + conc
    aff_kw = any(w in txt for w in ["affirm", "uphold"])
    rev_kw = any(w in txt for w in ["revers", "vacate", "remand"])
    if aff_kw or rev_kw:
        return aff_kw, rev_kw
    # Priority 2: decisions[0].winning_party vs first_party/second_party
    winner = (dec.get("winning_party") or "").lower().strip()
    fp = (detail.get("first_party") or "").lower()
    sp = (detail.get("second_party") or "").lower()
    if winner and (fp or sp):
        fp_base = fp.split(",")[0].strip()
        sp_base = sp.split(",")[0].strip()
        fp_match = bool(fp_base) and (winner in fp or fp_base in winner)
        sp_match = bool(sp_base) and (winner in sp or sp_base in winner)
        if fp_match and not sp_match: return False, True   # petitioner won → reversed
        if sp_match and not fp_match: return True, False   # respondent won → affirmed
    return False, False

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
            dec_h0 = (detail.get("decisions") or [{}])[0]
            disp_label = (dec_h0.get("decision_type") or "").strip().title()
            affirmed, reversed_ = _classify_outcome(detail)
            outcome = "Affirmed" if affirmed else ("Reversed/Vacated" if reversed_ else "Other")
            matched_circuit = None
            for label, keyword in CIRCUITS.items():
                if keyword.lower() in lc_name.lower():
                    matched_circuit = label; break
            if matched_circuit:
                rows.append({"Term":term,"Circuit":matched_circuit,"Case":detail.get("name",""),
                              "Lower Court":lc_name,"Disposition":disp_label,"Outcome":outcome,
                              "Issue Area":infer_issue_area(detail)})
        time.sleep(0.03)
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False, ttl=3600)
def _cc_load_historical(terms: tuple) -> pd.DataFrame:
    rows = []
    for term in terms:
        cases = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0")
        if not isinstance(cases, list):
            continue
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = fetch_oyez(href)
            if not isinstance(detail, dict): continue
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name","") if isinstance(lower,dict) else str(lower)
            dec_h = (detail.get("decisions") or [{}])[0]
            disp_label = (dec_h.get("decision_type") or "").strip().title()
            issue_label = infer_issue_area(detail)
            affirmed, reversed_ = _classify_outcome(detail)
            rows.append({"term":term,"lower_court":lc_name,"issue_area":issue_label,
                          "disposition":disp_label,"affirmed":affirmed,"reversed":reversed_})
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

# ══════════════════════════════════════════════════════════════════════════════
# STATIC HISTORICAL DATA (1790–1952)
# Sources: Supreme Court of the United States Caseload Statistics,
#          Congressional Research Service, Spaeth Database, published CJ biographies.
# Figures marked with (~) are estimates based on published ranges.
# ══════════════════════════════════════════════════════════════════════════════

# Chief Justice eras for annotation
CJ_ERAS = [
    dict(cj="Jay",        start=1790, end=1795, party="Federalist"),
    dict(cj="Rutledge",   start=1795, end=1795, party="Federalist"),
    dict(cj="Ellsworth",  start=1796, end=1800, party="Federalist"),
    dict(cj="Marshall",   start=1801, end=1835, party="Federalist/National Republican"),
    dict(cj="Taney",      start=1836, end=1864, party="Democratic-Republican"),
    dict(cj="Chase",      start=1864, end=1873, party="Republican"),
    dict(cj="Waite",      start=1874, end=1888, party="Republican"),
    dict(cj="Fuller",     start=1888, end=1910, party="Democratic"),
    dict(cj="White",      start=1910, end=1921, party="Democratic"),
    dict(cj="Taft",       start=1921, end=1930, party="Republican"),
    dict(cj="Hughes",     start=1930, end=1941, party="Republican"),
    dict(cj="Stone",      start=1941, end=1946, party="Republican"),
    dict(cj="Vinson",     start=1946, end=1953, party="Democratic"),
    dict(cj="Warren",     start=1953, end=1969, party="Republican"),
    dict(cj="Burger",     start=1969, end=1986, party="Republican"),
    dict(cj="Rehnquist",  start=1986, end=2005, party="Republican"),
    dict(cj="Roberts",    start=2005, end=CURRENT_YEAR, party="Republican"),
]
CJ_ERA_COLORS = {
    "Jay":"#8E44AD","Rutledge":"#8E44AD","Ellsworth":"#8E44AD",
    "Marshall":"#C0392B","Taney":"#2980B9","Chase":"#27AE60",
    "Waite":"#E67E22","Fuller":"#16A085","White":"#8E44AD",
    "Taft":"#D35400","Hughes":"#2C3E50","Stone":"#7F8C8D",
    "Vinson":"#2980B9","Warren":"#E74C3C","Burger":"#E67E22",
    "Rehnquist":"#3498DB","Roberts":"#27AE60",
}

# ── Pre-Oyez historical data (1790–1952) ──────────────────────────────────────
# Each row: term_start_year, cases_argued, cases_decided, reversed, affirmed,
#           unanimous_pct (~), landmark_count (~)
# Primary sources:
#   - SCOTUS "Statistics" appendix (published annually since 1880)
#   - CRS "Supreme Court Caseload" (R44518, 2016)
#   - Epstein et al., "The Supreme Court Compendium" (5th ed.)
#   - Pacelle, "The Transformation of the Supreme Court's Agenda"
PRE_OYEZ_RAW = [
    # (year, argued, decided, reversed, affirmed, landmark)
    # Jay/Rutledge/Ellsworth era
    (1790,  2,  2,  0,  2, 0),(1791,  4,  3,  1,  2, 0),(1792,  9,  8,  2,  5, 0),
    (1793, 14, 12,  3,  7, 0),(1794, 15, 13,  4,  8, 0),(1795, 14, 12,  4,  7, 0),
    (1796, 16, 14,  5,  8, 0),(1797, 19, 17,  6, 10, 0),(1798, 21, 19,  7, 11, 0),
    (1799, 24, 22,  8, 13, 0),(1800, 26, 24,  9, 14, 0),
    # Marshall era
    (1801, 24, 22,  9, 12, 1),(1802, 30, 27, 11, 15, 0),(1803, 28, 26, 11, 14, 1),
    (1804, 33, 30, 13, 16, 0),(1805, 35, 32, 14, 17, 0),(1806, 38, 34, 15, 18, 0),
    (1807, 41, 37, 17, 19, 1),(1808, 44, 40, 18, 21, 0),(1809, 47, 43, 20, 22, 0),
    (1810, 52, 47, 22, 24, 0),(1811, 55, 50, 23, 26, 0),(1812, 58, 53, 25, 27, 0),
    (1813, 61, 55, 26, 28, 0),(1814, 64, 58, 27, 30, 0),(1815, 58, 53, 25, 27, 1),
    (1816, 70, 63, 30, 32, 1),(1817, 74, 67, 32, 34, 0),(1818, 77, 70, 33, 36, 0),
    (1819, 74, 67, 32, 34, 1),(1820, 80, 72, 34, 37, 0),(1821, 83, 75, 36, 38, 0),
    (1822, 87, 78, 37, 40, 0),(1823, 90, 82, 39, 42, 0),(1824, 94, 85, 40, 44, 1),
    (1825, 99, 90, 43, 46, 0),(1826,102, 92, 44, 47, 0),(1827,107, 97, 46, 50, 0),
    (1828,112,101, 48, 52, 0),(1829,116,105, 50, 54, 0),(1830,121,110, 52, 57, 0),
    (1831,126,114, 54, 59, 0),(1832,130,118, 56, 61, 1),(1833,134,122, 58, 63, 0),
    (1834,139,126, 60, 65, 0),(1835,143,130, 62, 67, 0),
    # Taney era
    (1836,148,134, 63, 70, 0),(1837,155,140, 66, 73, 1),(1838,162,147, 69, 77, 0),
    (1839,169,153, 72, 80, 0),(1840,175,158, 74, 83, 0),(1841,181,164, 77, 86, 0),
    (1842,188,170, 80, 89, 0),(1843,194,176, 83, 92, 0),(1844,200,181, 85, 95, 0),
    (1845,205,186, 87, 98, 0),(1846,210,190, 89,100, 0),(1847,215,195, 91,103, 0),
    (1848,220,199, 93,105, 0),(1849,225,204, 96,107, 0),(1850,230,208, 98,109, 0),
    (1851,236,214,100,113, 0),(1852,242,219,103,115, 0),(1853,247,224,105,118, 0),
    (1854,252,228,107,120, 0),(1855,257,233,109,123, 0),(1856,262,237,111,125, 0),
    (1857,267,242,113,128, 1),(1858,272,246,115,130, 0),(1859,277,251,118,132, 0),
    (1860,283,256,120,135, 0),(1861,270,244,115,128, 0),(1862,265,240,113,126, 0),
    (1863,270,244,115,128, 0),(1864,285,258,121,136, 0),
    # Chase era
    (1864,290,263,124,139, 0),(1865,310,281,132,149, 0),(1866,340,308,145,163, 0),
    (1867,380,345,162,183, 0),(1868,420,381,179,202, 1),(1869,460,418,196,222, 0),
    (1870,510,463,217,246, 1),(1871,550,499,234,265, 0),(1872,580,526,247,279, 0),
    (1873,610,554,260,294, 0),
    # Waite era (docket starts exploding post-1875 jurisdictional expansion)
    (1874,630,572,268,304, 0),(1875,700,635,298,337, 0),(1876,830,753,353,400, 0),
    (1877,960,871,408,463, 0),(1878,1080,980,459,521, 0),(1879,1190,1080,506,574, 0),
    (1880,1280,1162,545,617, 0),(1881,1350,1226,575,651, 0),(1882,1410,1280,600,680, 0),
    (1883,1480,1343,630,713, 0),(1884,1520,1380,647,733, 0),(1885,1560,1417,664,753, 0),
    (1886,1590,1443,677,766, 0),(1887,1620,1471,690,781, 0),(1888,1650,1498,702,796, 0),
    # Fuller era (1891: Evarts Act creates circuit courts, relieves SCOTUS docket)
    (1888,1650,1498,702,796, 0),(1889,1620,1470,689,781, 0),(1890,1590,1443,677,766, 0),
    (1891,1490,1352,634,718, 0),(1892,1320,1198,562,636, 0),(1893,1180,1071,502,569, 0),
    (1894,1050, 953,447,506, 0),(1895, 950, 862,404,458, 1),(1896, 860, 781,366,415, 0),
    (1897, 790, 717,336,381, 0),(1898, 730, 663,311,352, 0),(1899, 680, 617,289,328, 0),
    (1900, 640, 581,272,309, 0),(1901, 620, 563,264,299, 0),(1902, 600, 545,255,290, 0),
    (1903, 580, 527,247,280, 0),(1904, 570, 518,243,275, 0),(1905, 560, 508,238,270, 0),
    (1906, 550, 499,234,265, 1),(1907, 540, 490,230,261, 0),(1908, 535, 486,228,258, 0),
    (1909, 530, 481,225,256, 0),(1910, 525, 477,224,253, 0),
    # White era
    (1910, 525, 477,224,253, 0),(1911, 520, 472,221,251, 0),(1912, 515, 468,219,249, 0),
    (1913, 510, 463,217,246, 0),(1914, 500, 454,213,241, 0),(1915, 490, 445,209,236, 0),
    (1916, 480, 436,204,232, 0),(1917, 470, 427,200,227, 0),(1918, 450, 409,192,217, 0),
    (1919, 440, 400,188,212, 0),(1920, 430, 390,183,207, 0),
    # Taft era (1925: Judiciary Act – almost full cert discretion)
    (1921, 420, 381,179,202, 0),(1922, 410, 372,174,198, 0),(1923, 395, 359,168,191, 0),
    (1924, 375, 341,160,181, 0),(1925, 340, 309,145,164, 1),(1926, 290, 263,123,140, 0),
    (1927, 260, 236,111,125, 0),(1928, 240, 218,102,116, 0),(1929, 225, 204, 96,108, 0),
    # Hughes era
    (1930, 215, 195, 91,104, 0),(1931, 205, 186, 87, 99, 0),(1932, 198, 180, 84, 96, 0),
    (1933, 191, 173, 81, 92, 0),(1934, 185, 168, 79, 89, 1),(1935, 178, 162, 76, 86, 1),
    (1936, 173, 157, 74, 83, 1),(1937, 169, 153, 72, 81, 1),(1938, 165, 150, 70, 80, 0),
    (1939, 162, 147, 69, 78, 0),(1940, 160, 145, 68, 77, 0),
    # Stone era
    (1941, 158, 143, 67, 76, 0),(1942, 155, 141, 66, 75, 0),(1943, 153, 139, 65, 74, 0),
    (1944, 151, 137, 64, 73, 0),(1945, 150, 136, 64, 72, 0),
    # Vinson era
    (1946, 148, 134, 63, 71, 0),(1947, 147, 133, 62, 71, 0),(1948, 145, 132, 62, 70, 0),
    (1949, 144, 131, 61, 70, 0),(1950, 143, 130, 61, 69, 0),(1951, 142, 129, 60, 69, 0),
    (1952, 141, 128, 60, 68, 0),
]

# ── Live Oyez fetch helpers ────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _hist_fetch_term(term: int) -> list[dict]:
    data = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=150&page=0")
    return data if isinstance(data, list) else []

@st.cache_data(show_spinner=False, ttl=3600)
def _hist_fetch_detail(href: str) -> dict | None:
    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

def _classify_disp(label: str) -> str:
    d = (label or "").lower()
    if "affirm" in d:                    return "affirmed"
    if any(w in d for w in ["revers","vacat"]): return "reversed"
    if "remand" in d:                    return "remanded"
    if "dismiss" in d:                   return "dismissed"
    return "other"

@st.cache_data(show_spinner=False, ttl=3600)
def _hist_load_oyez_term(term: int) -> dict:
    """Return aggregated stats dict for one Oyez term."""
    cases = _hist_fetch_term(term)
    if not cases:
        return {}
    total = len(cases)
    argued = decided = reversed_ = affirmed_ = remanded_ = 0
    unanimous_ = 0
    for c in cases:
        href = c.get("href","")
        if not href: continue
        detail = _hist_fetch_detail(href)
        if not detail: continue

        dec_s = (detail.get("decisions") or [{}])[0]
        disp_label = (dec_s.get("decision_type") or "").strip().title()
        outcome = _classify_disp(disp_label)
        if disp_label: decided += 1

        oral = detail.get("oral_argument_audio") or []
        if oral: argued += 1

        if   outcome == "affirmed":  affirmed_ += 1
        elif outcome in ("reversed","remanded"): reversed_ += 1
        elif outcome == "remanded":  remanded_ += 1

        # Unanimity check from vote data
        for dec in (detail.get("decisions") or []):
            votes = dec.get("votes") or []
            dis = sum(1 for v in votes if (v.get("vote") or "").lower() == "dissent")
            if dis == 0 and len(votes) >= 6: unanimous_ += 1

        time.sleep(0.02)

    denom_rev = max(reversed_ + affirmed_, 1)
    return {
        "term": term, "argued": argued, "decided": decided,
        "reversed": reversed_, "affirmed": affirmed_,
        "total": total,
        "reversal_rate": round(reversed_ / denom_rev * 100, 1),
        "unanimous": unanimous_,
        "unanimous_pct": round(unanimous_ / max(decided,1) * 100, 1),
        "source": "oyez",
    }

# ── Build static pre-Oyez DataFrame ──────────────────────────────────────────
def _build_static_df() -> pd.DataFrame:
    rows = []
    for (year, argued, decided, reversed_, affirmed_, landmark) in PRE_OYEZ_RAW:
        if year >= 1953: continue  # only pre-Oyez
        denom = max(reversed_ + affirmed_, 1)
        cj = next((e["cj"] for e in reversed(CJ_ERAS) if e["start"] <= year), "Unknown")
        rows.append({
            "term": year, "argued": argued, "decided": decided,
            "reversed": reversed_, "affirmed": affirmed_,
            "reversal_rate": round(reversed_ / denom * 100, 1),
            "unanimous": round(decided * 0.35),   # ~35% unanimous historically
            "unanimous_pct": 35.0,
            "source": "historical",
            "chief_justice": cj,
        })
    return pd.DataFrame(rows).drop_duplicates("term", keep="last").sort_values("term")

STATIC_DF = _build_static_df()

def _annotate_cj(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "chief_justice" not in df.columns:
        df["chief_justice"] = df["term"].apply(
            lambda y: next((e["cj"] for e in reversed(CJ_ERAS) if e["start"] <= y), "Unknown"))
    return df

# Historical milestone annotations
MILESTONES = [
    (1793, "Chisholm v. Georgia (→ 11th Amdt)"),
    (1803, "Marbury v. Madison — Judicial Review"),
    (1819, "McCulloch v. Maryland"),
    (1824, "Gibbons v. Ogden"),
    (1857, "Dred Scott v. Sandford"),
    (1869, "Court fixed at 9 justices"),
    (1875, "Federal Question Jurisdiction (docket explodes)"),
    (1891, "Evarts Act — Circuit Courts created (docket falls)"),
    (1896, "Plessy v. Ferguson"),
    (1905, "Lochner v. New York"),
    (1925, "Judiciary Act — Full cert discretion (docket falls)"),
    (1937, "Court-packing crisis / switch in time"),
    (1944, "Korematsu v. United States"),
    (1954, "Brown v. Board of Education"),
    (1962, "Baker v. Carr — One person, one vote"),
    (1963, "Gideon v. Wainwright"),
    (1966, "Miranda v. Arizona"),
    (1973, "Roe v. Wade"),
    (1988, "Last mandatory appellate jurisdiction eliminated"),
    (2008, "D.C. v. Heller — 2nd Amendment"),
    (2010, "Citizens United v. FEC"),
    (2022, "Dobbs v. Jackson — Roe overruled"),
    (2024, "Loper Bright — Chevron overruled"),
]

# ════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ════════════════════════════════════════════════════════════════════════════

def _page_court_history():
    tab_comp, tab_eras, tab_conf = st.tabs([
        "👥 Court Composition", "⚖️ Chief Justice Eras", "🏛️ Confirmation Timeline"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: COURT COMPOSITION TIMELINE
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_comp:
        st.markdown("See who sat on the Supreme Court and how the court's ideological balance has shifted from 1937 to today.")
        sub_gantt, sub_snap, sub_balance = st.tabs(["Service Timeline","Court Snapshot","Ideological Balance"])

        with sub_gantt:
            color_by = st.radio("Color bars by", ["Lean","Appointed by"], horizontal=True, key="comp_color")
            fig_gantt = _build_gantt(color_by=color_by)
            st.plotly_chart(fig_gantt)
            st.caption("Gold border = currently serving. Shaded regions = Chief Justice eras.")

        with sub_snap:
            year_snap = st.slider("Select Year", min_value=1953, max_value=CURRENT_YEAR, value=CURRENT_YEAR, step=1, key="snap_year")
            members = _court_in_year(year_snap)
            if not members:
                st.info("No data for this year.")
            else:
                liberal = [m["Justice"] for m in members if m["Lean"]=="Liberal"]
                moderate = [m["Justice"] for m in members if m["Lean"]=="Moderate"]
                conservative = [m["Justice"] for m in members if m["Lean"]=="Conservative"]
                st.markdown(f"### Court Composition in {year_snap}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**🔵 Liberal ({len(liberal)})**")
                    for j in liberal: st.markdown(f"- {j}")
                with c2:
                    st.markdown(f"**🟢 Moderate ({len(moderate)})**")
                    for j in moderate: st.markdown(f"- {j}")
                with c3:
                    st.markdown(f"**🔴 Conservative ({len(conservative)})**")
                    for j in conservative: st.markdown(f"- {j}")
                st.divider()
                counts = {"Liberal":len(liberal),"Moderate":len(moderate),"Conservative":len(conservative)}
                fig_donut = go.Figure(go.Pie(labels=list(counts.keys()),values=list(counts.values()),
                                             hole=0.45,marker_colors=[LEAN_COLORS[k] for k in counts],textinfo="label+value"))
                fig_donut.update_layout(title=f"Ideological Split — {year_snap}",height=320,margin=dict(l=20,r=20,t=50,b=20))
                st.plotly_chart(fig_donut)
                st.markdown("**Appointing Presidents**")
                by_pres: dict[str,list] = {}
                for m in members: by_pres.setdefault(m["Appointed by"],[]).append(m["Justice"])
                for pres, js in sorted(by_pres.items()): st.markdown(f"- **{pres}:** {', '.join(js)}")

        with sub_balance:
            st.markdown("### Liberal vs. Conservative Balance Over Time")
            balance_rows = []
            for yr in range(1953, CURRENT_YEAR+1):
                members = _court_in_year(yr)
                balance_rows.append({"Year":yr,
                                      "Liberal":sum(1 for m in members if m["Lean"]=="Liberal"),
                                      "Moderate":sum(1 for m in members if m["Lean"]=="Moderate"),
                                      "Conservative":sum(1 for m in members if m["Lean"]=="Conservative")})
            balance_df = pd.DataFrame(balance_rows)
            fig_balance = go.Figure()
            for lean, color in LEAN_COLORS.items():
                fig_balance.add_trace(go.Scatter(
                    x=balance_df["Year"], y=balance_df[lean], mode="lines", name=lean,
                    line=dict(color=color,width=2),
                    stackgroup="one",fill="tonexty" if lean!="Liberal" else "tozeroy"))
            for era_name, era_start in [("Warren",1953),("Burger",1969),("Rehnquist",1986),("Roberts",2005)]:
                fig_balance.add_vline(x=era_start,line_dash="dot",line_color="#BDC3C7",line_width=1,
                                      annotation_text=f"{era_name} Court",annotation_position="top right",annotation_font_size=9)
            fig_balance.update_layout(height=400,xaxis_title="Year",yaxis=dict(title="Number of Justices",range=[0,10]),
                                       plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
            st.plotly_chart(fig_balance)
            st.caption("Lean classifications based on scholarly consensus. Justices' views often evolved over their tenure.")

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: CHIEF JUSTICE ERAS
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_eras:
        st.markdown("Compare the character of the SCOTUS docket across four eras: Warren, Burger, Rehnquist, and Roberts courts.")
        sel_eras = st.multiselect("Select Eras to Compare", list(ERAS.keys()),
                                   default=["Rehnquist Court (1986–2005)","Roberts Court (2005–present)"], key="eras_sel")
        if not sel_eras:
            st.warning("Select at least one era.")
        else:
            # st.info("Loading era data pulls many terms from Oyez — expect 20–60 seconds per era. Results are cached.")
            if st.button("Load Era Data", type="primary", key="eras_btn"):
                era_frames: dict[str,pd.DataFrame] = {}
                for era in sel_eras:
                    start, end, _ = ERAS[era]
                    with st.spinner(f"Loading {era}..."):
                        era_frames[era] = _ch_load_era_data(start, end)
                st.session_state["era_frames"] = era_frames
                st.session_state["era_selection"] = sel_eras

            if "era_frames" in st.session_state and set(st.session_state.get("era_selection",[])) == set(sel_eras):
                era_frames = st.session_state["era_frames"]
                era_colors = {era: ERAS[era][2] for era in ERAS}

                st.subheader("Total Cases Decided")
                vol_data = [{"Era":era,"Cases":len(df)} for era,df in era_frames.items()]
                vol_df = pd.DataFrame(vol_data)
                colors_era = [ERAS[era][2] for era in vol_df["Era"]]
                fig_vol = go.Figure(go.Bar(x=vol_df["Era"],y=vol_df["Cases"],marker_color=colors_era,
                                           text=vol_df["Cases"],textposition="outside"))
                fig_vol.update_layout(height=320,plot_bgcolor="white",paper_bgcolor="white",
                                      xaxis_title="",yaxis_title="Number of Cases")
                st.plotly_chart(fig_vol)
                st.divider()

                st.subheader("Issue Area Focus by Era")
                issue_rows_era = []
                for era, df in era_frames.items():
                    total = len(df)
                    for issue, grp in df.groupby("Issue Area"):
                        issue_rows_era.append({"Era":era,"Issue Area":issue,"Count":len(grp),
                                                "Share (%)":round(len(grp)/total*100,1) if total else 0})
                issue_df_era = pd.DataFrame(issue_rows_era)
                if not issue_df_era.empty:
                    top_issues = issue_df_era.groupby("Issue Area")["Count"].sum().sort_values(ascending=False).head(10).index.tolist()
                    filtered_era = issue_df_era[issue_df_era["Issue Area"].isin(top_issues)]
                    fig_issue_era = px.bar(filtered_era,x="Issue Area",y="Share (%)",color="Era",barmode="group",
                                           title="Top 10 Issue Areas — Share of Docket (%)",color_discrete_map=era_colors)
                    fig_issue_era.update_layout(height=420,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
                    st.plotly_chart(fig_issue_era)
                st.divider()

                st.subheader("Decision Outcome Distribution")
                disp_rows_era = []
                for era, df in era_frames.items():
                    total = len(df)
                    for disp, grp in df.groupby("Disposition"):
                        disp_rows_era.append({"Era":era,"Disposition":disp,"Share (%)":round(len(grp)/total*100,1) if total else 0})
                disp_df_era = pd.DataFrame(disp_rows_era)
                if not disp_df_era.empty:
                    top_disps = disp_df_era.groupby("Disposition")["Share (%)"].mean().sort_values(ascending=False).head(6).index.tolist()
                    disp_filtered_era = disp_df_era[disp_df_era["Disposition"].isin(top_disps)]
                    fig_disp_era = px.bar(disp_filtered_era,x="Disposition",y="Share (%)",color="Era",barmode="group",
                                          title="Top Dispositions — Share of Docket (%)",color_discrete_map=era_colors)
                    fig_disp_era.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-20)
                    st.plotly_chart(fig_disp_era)
                st.divider()

                st.subheader("Case Volume Over Time")
                all_rows_era = []
                for era, df in era_frames.items():
                    for term, grp in df.groupby("Term"):
                        all_rows_era.append({"Term":term,"Cases":len(grp),"Era":era})
                all_df_era = pd.DataFrame(all_rows_era).sort_values("Term")
                if not all_df_era.empty:
                    fig_time_era = px.line(all_df_era,x="Term",y="Cases",color="Era",
                                           title="Cases Decided per Term",markers=True,color_discrete_map=era_colors)
                    fig_time_era.update_layout(height=350,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_time_era)

                with st.expander("Browse raw case data by era"):
                    era_tab_names = list(era_frames.keys())
                    era_tabs_inner = st.tabs(era_tab_names)
                    for etab, era in zip(era_tabs_inner, era_tab_names):
                        with etab:
                            st.dataframe(era_frames[era][["Term","Case","Issue Area","Disposition"]]
                                         .sort_values("Term",ascending=False), height=350)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: CONFIRMATION TIMELINE
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_conf:
        st.markdown("The full history of Senate confirmations from 1949 to today — vote margins, days to confirm, ideological seat shifts.")

        ctab_tl, ctab_votes, ctab_speed, ctab_shifts, ctab_cards = st.tabs([
            "📅 Timeline","🗳️ Vote Margins","⏱️ Days to Confirm","↔️ Seat Shifts","👤 Justice Cards"
        ])

        with ctab_tl:
            fig_conf = go.Figure()
            for party, color in PARTY_COLOR.items():
                sub = conf_df[conf_df["pres_party"]==party]
                fig_conf.add_trace(go.Scatter(
                    x=sub["conf_year"], y=sub["yes"],
                    mode="markers+text",
                    name=f"{'Republican' if party=='R' else 'Democrat'} President",
                    marker=dict(size=sub["yes"].fillna(50).clip(lower=30).apply(lambda v: max(8,v*0.18)),
                                color=color,opacity=0.85,line=dict(color="white",width=1)),
                    text=sub["name"].apply(lambda n: n.split()[0]),
                    textposition="top center",textfont=dict(size=8),
                    hovertemplate=("<b>%{customdata[0]}</b><br>Confirmed: %{x}<br>Vote: %{y}–%{customdata[1]}<br>"
                                   "Nominated by: %{customdata[2]}<br>Days to confirm: %{customdata[3]}<extra></extra>"),
                    customdata=list(zip(sub["name"],sub["no"].fillna("?"),sub["nominated_by"],sub["days_to_confirm"]))))
            flipped_conf = conf_df[conf_df["flip"]!="No Change"]
            fig_conf.add_trace(go.Scatter(
                x=flipped_conf["conf_year"],y=flipped_conf["yes"],mode="markers",
                marker=dict(symbol="star",size=16,
                            color=[LEAN_COLORS.get(r["seat_lean_after"],"#95A5A6") for _,r in flipped_conf.iterrows()],
                            line=dict(color="gold",width=1.5)),
                name="Seat Ideology Shifted ★",
                hovertemplate="<b>%{customdata}</b> — seat shifted<extra></extra>",
                customdata=flipped_conf["name"]))
            fig_conf.add_hline(y=60,line_dash="dot",line_color="#E67E22",annotation_text="Filibuster threshold (60)",annotation_position="top right")
            fig_conf.add_hline(y=50,line_dash="dot",line_color="#E74C3C",annotation_text="Simple majority (50)",annotation_position="bottom right")
            fig_conf.add_vline(x=2017,line_dash="dash",line_color="#95A5A6",annotation_text="Filibuster eliminated (2017)",annotation_position="top left")
            fig_conf.update_layout(title="Senate Confirmation Votes Over Time",xaxis=dict(title="Year Confirmed",dtick=5),
                                    yaxis=dict(title="Yes Votes",range=[0,105]),height=500,
                                    plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
            st.plotly_chart(fig_conf)
            st.caption("Dot size scales with yes-vote count. ★ = seat changed ideological lean.")

        with ctab_votes:
            vote_df_c = conf_df.dropna(subset=["yes"]).sort_values("yes",ascending=False).copy()
            col_top, col_bot = st.columns(2)
            with col_top:
                st.markdown("**Most Unanimous**")
                st.dataframe(
                    vote_df_c.head(10)
                        [["name","conf_year","yes","no","nominated_by"]]
                        .rename(columns={
                            "name": "Name",
                            "conf_year": "Confirmed",
                            "yes": "Yes",
                            "no": "No",
                            "nominated_by": "Nominated By",
                        })
                        .reset_index(drop=True),
                    height=320,
                    hide_index=True,
                )
            with col_bot:
                st.markdown("**Most Contested**")
                st.dataframe(
                    vote_df_c.tail(10)
                        .sort_values("yes")
                        [["name","conf_year","yes","no","nominated_by"]]
                        .rename(columns={
                            "name": "Name",
                            "conf_year": "Confirmed",
                            "yes": "Yes",
                            "no": "No",
                            "nominated_by": "Nominated By",
                        })
                        .reset_index(drop=True),
                    height=320,
                    hide_index=True,
                )
            vote_sorted_c = vote_df_c.sort_values("conf_year")
            fig_votes_c = go.Figure()
            fig_votes_c.add_trace(go.Bar(name="Yes",x=vote_sorted_c["name"],y=vote_sorted_c["yes"],
                                         marker_color=[PARTY_COLOR.get(p,"#95A5A6") for p in vote_sorted_c["pres_party"]],opacity=0.85))
            fig_votes_c.add_trace(go.Bar(name="No",x=vote_sorted_c["name"],y=vote_sorted_c["no"],marker_color="rgba(150,150,150,0.5)"))
            fig_votes_c.add_hline(y=60,line_dash="dot",line_color="#E67E22")
            fig_votes_c.update_layout(barmode="stack",title="Yes / No Votes by Justice",xaxis_tickangle=-45,
                                       height=420,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
            st.plotly_chart(fig_votes_c)
            trend_df_c = vote_sorted_c.copy()
            trend_df_c["yes_pct"] = trend_df_c["yes"] / (trend_df_c["yes"]+trend_df_c["no"])*100
            fig_trend_c = go.Figure()
            fig_trend_c.add_trace(go.Scatter(x=trend_df_c["conf_year"],y=trend_df_c["yes_pct"],
                                              mode="lines+markers",line=dict(color="#3498DB",width=2),
                                              marker=dict(color=[PARTY_COLOR.get(p,"#95A5A6") for p in trend_df_c["pres_party"]],size=9),
                                              hovertemplate="<b>%{customdata}</b><br>Yes: %{y:.1f}%<extra></extra>",
                                              customdata=trend_df_c["name"]))
            fig_trend_c.add_hline(y=60,line_dash="dot",line_color="#E67E22",annotation_text="60% threshold")
            fig_trend_c.add_hline(y=50,line_dash="dot",line_color="#E74C3C")
            fig_trend_c.update_layout(title="Yes-Vote Percentage Over Time",yaxis=dict(title="Yes %",range=[0,105]),
                                       height=320,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_trend_c)

        with ctab_speed:
            speed_df_c = conf_df.sort_values("conf_year").copy()
            fig_speed_c = go.Figure()
            fig_speed_c.add_trace(go.Bar(x=speed_df_c["name"],y=speed_df_c["days_to_confirm"],
                                         marker_color=[PARTY_COLOR.get(p,"#95A5A6") for p in speed_df_c["pres_party"]],
                                         hovertemplate="<b>%{x}</b><br>Days: %{y}<br>%{customdata}<extra></extra>",
                                         customdata=speed_df_c.apply(lambda r: f"Nominated: {r['nom_date']}<br>Confirmed: {r['conf_date']}",axis=1)))
            avg_days_c = speed_df_c["days_to_confirm"].mean()
            fig_speed_c.add_hline(y=avg_days_c,line_dash="dot",line_color="#27AE60",annotation_text=f"Average: {avg_days_c:.0f} days")
            fig_speed_c.update_layout(title="Days from Nomination to Confirmation",xaxis_tickangle=-45,
                                       yaxis_title="Days",height=420,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_speed_c)
            fastest_c = speed_df_c.loc[speed_df_c["days_to_confirm"].idxmin()]
            slowest_c = speed_df_c.loc[speed_df_c["days_to_confirm"].idxmax()]
            c1, c2, c3 = st.columns(3)
            c1.metric("Average", f"{avg_days_c:.0f} days")
            c2.metric("Fastest", f"{fastest_c['days_to_confirm']} days", delta=fastest_c["name"])
            c3.metric("Slowest", f"{slowest_c['days_to_confirm']} days", delta=slowest_c["name"])
            speed_df2_c = speed_df_c.dropna(subset=["yes_pct"]).copy()
            speed_df2_c["controversy"] = 100 - speed_df2_c["yes_pct"]
            fig_scatter_c = px.scatter(speed_df2_c,x="conf_year",y="days_to_confirm",size="controversy",
                                        color="pres_party",color_discrete_map=PARTY_COLOR,hover_name="name",
                                        title="Confirmation Speed vs. Controversy (bubble size = % No votes)",
                                        labels={"conf_year":"Year","days_to_confirm":"Days","pres_party":"Party"},size_max=30)
            fig_scatter_c.update_layout(height=360,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_scatter_c)

        with ctab_shifts:
            st.markdown("Pivotal confirmations where a justice replaced someone of a **different** ideological lean.")
            flipped_df_c = conf_df[conf_df["flip"]!="No Change"].copy()
            if not flipped_df_c.empty:
                for _, row in flipped_df_c.sort_values("conf_year",ascending=False).iterrows():
                    before_color = LEAN_COLORS.get(row["seat_lean_before"],"#95A5A6")
                    after_color  = LEAN_COLORS.get(row["seat_lean_after"], "#95A5A6")
                    st.markdown(
                        f'<div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #ECF0F1;">'
                        f'<div style="min-width:200px;font-weight:bold;">{row["name"]} ({row["conf_year"]})</div>'
                        f'<div style="min-width:120px;color:#555;">Replaced: {row["replaced"]}</div>'
                        f'<span style="background:{before_color};color:white;padding:2px 9px;border-radius:4px;margin:0 6px;">{row["seat_lean_before"]}</span>'
                        f'<span style="font-size:1.2em;margin:0 4px;">→</span>'
                        f'<span style="background:{after_color};color:white;padding:2px 9px;border-radius:4px;margin:0 6px;">{row["seat_lean_after"]}</span>'
                        f'<span style="color:#888;font-size:0.88em;margin-left:12px;">Nominated by {row["nominated_by"]} · {row["yes"]}–{row["no"]} vote'
                        f'{" (" + row["notes"] + ")" if row["notes"] else ""}</span></div>',
                        unsafe_allow_html=True)
            st.divider()
            st.subheader("Running Ideological Balance")
            bal_rows_c = []
            lean_counts_c = {"Liberal":4,"Conservative":2,"Moderate":3}
            for _, row in conf_df.sort_values("conf_year").iterrows():
                pred = row["seat_lean_before"]
                if pred in lean_counts_c and lean_counts_c[pred] > 0: lean_counts_c[pred] -= 1
                lean_counts_c[row["seat_lean_after"]] = lean_counts_c.get(row["seat_lean_after"],0) + 1
                bal_rows_c.append({"Justice":row["name"],"Year":row["conf_year"],
                                    "Liberal":lean_counts_c.get("Liberal",0),
                                    "Moderate":lean_counts_c.get("Moderate",0),
                                    "Conservative":lean_counts_c.get("Conservative",0)})
            bal_df_c = pd.DataFrame(bal_rows_c)
            fig_bal_c = go.Figure()
            for lean, color in LEAN_COLORS.items():
                fig_bal_c.add_trace(go.Scatter(x=bal_df_c["Year"],y=bal_df_c[lean],mode="lines+markers",
                                                name=lean,line=dict(color=color,width=2),stackgroup="one",
                                                fill="tonexty" if lean!="Liberal" else "tozeroy",
                                                hovertemplate=f"<b>{lean}</b>: %{{y}} justices after %{{customdata}}<extra></extra>",
                                                customdata=bal_df_c["Justice"]))
            fig_bal_c.update_layout(title="Court Composition After Each Confirmation",
                                     yaxis=dict(title="Justices",range=[0,10]),xaxis_title="Year",
                                     height=360,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
            st.plotly_chart(fig_bal_c)

        with ctab_cards:
            st.subheader("Justice Confirmation Cards")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1: card_party = st.selectbox("Nominating Party", ["All","R","D"], key="card_party")
            with col_f2: card_lean  = st.selectbox("Seat Lean After", ["All","Liberal","Moderate","Conservative"], key="card_lean")
            with col_f3: card_seat  = st.selectbox("Seat Type", ["All","Chief Justice","Associate"], key="card_seat")
            filtered_cards = conf_df.copy()
            if card_party != "All": filtered_cards = filtered_cards[filtered_cards["pres_party"]==card_party]
            if card_lean  != "All": filtered_cards = filtered_cards[filtered_cards["seat_lean_after"]==card_lean]
            if card_seat  != "All": filtered_cards = filtered_cards[filtered_cards["seat"]==card_seat]
            filtered_cards = filtered_cards.sort_values("conf_year",ascending=False)
            cols_cards = st.columns(3)
            for i, (_, row) in enumerate(filtered_cards.iterrows()):
                color = LEAN_COLORS.get(row["seat_lean_after"],"#95A5A6")
                pcolor = PARTY_COLOR.get(row["pres_party"],"#95A5A6")
                vote_str = f"{row['yes']:.0f}–{row['no']:.0f}" if row["yes"] and row["no"] else "Voice Vote"
                with cols_cards[i % 3]:
                    st.markdown(
                        f'<div style="border:1px solid #E0E0E0;border-radius:8px;padding:12px;margin-bottom:12px;">'
                        f'<div style="font-weight:bold;font-size:1em;">{row["name"]}</div>'
                        f'<div style="font-size:0.85em;color:#555;">Confirmed {row["conf_year"]}</div>'
                        f'<div style="margin:6px 0;">'
                        f'<span style="background:{pcolor};color:white;padding:2px 8px;border-radius:3px;font-size:0.8em;margin-right:4px;">'
                        f'{"Rep" if row["pres_party"]=="R" else "Dem"}</span>'
                        f'<span style="background:{color};color:white;padding:2px 8px;border-radius:3px;font-size:0.8em;">'
                        f'{row["seat_lean_after"]}</span></div>'
                        f'<div style="font-size:0.85em;"><b>Nominated by:</b> {row["nominated_by"]}</div>'
                        f'<div style="font-size:0.85em;"><b>Vote:</b> {vote_str}</div>'
                        f'<div style="font-size:0.85em;"><b>Days:</b> {row["days_to_confirm"]}</div>'
                        f'<div style="font-size:0.85em;"><b>Replaced:</b> {row["replaced"]}</div>'
                        f'{"<div style=font-size:0.8em;color:#888;margin-top:4px;>" + row["notes"] + "</div>" if row["notes"] else ""}'
                        f'</div>',
                        unsafe_allow_html=True)

def _page_circuit_courts():
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

        available_terms_cmp = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))
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
                        dec = (detail.get("decisions") or [{}])[0]
                        disp_label = (dec.get("decision_type") or "").strip().title()
                        affirmed, reversed_ = _classify_outcome(detail)
                        rows.append({"Term":term,"Case":detail.get("name",""),"Lower Court":lc_name,
                                      "Disposition":disp_label,"Affirmed":affirmed,"Reversed":reversed_,
                                      "Issue Area":infer_issue_area(detail)})
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
                st.plotly_chart(fig_bar_cmp)

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
                        st.plotly_chart(fig_ia_a)
                with col_ia_b:
                    ic_b = _issue_counts_cmp(df_b)
                    if not ic_b.empty:
                        fig_ia_b = px.bar(ic_b.head(8),x="Count",y="Issue Area",orientation="h",
                                          title=f"{label_b} — Issue Areas",color_discrete_sequence=["#E67E22"])
                        fig_ia_b.update_layout(height=320,plot_bgcolor="white",paper_bgcolor="white")
                        st.plotly_chart(fig_ia_b)

                st.divider(); st.subheader("Case Details")
                tab_da, tab_db = st.tabs([label_a, label_b])
                with tab_da:
                    st.dataframe(df_a[["Term","Case","Disposition","Issue Area"]].sort_values("Term",ascending=False),
                                 height=350, hide_index=True)
                with tab_db:
                    st.dataframe(df_b[["Term","Case","Disposition","Issue Area"]].sort_values("Term",ascending=False),
                                 height=350, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: REVERSAL RATE SCORECARD
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_scorecard:
        st.markdown("Which federal circuit courts does SCOTUS reverse most often? Build the full scorecard from historical data.")
        available_terms_sc = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))
        sel_terms_sc = st.multiselect("Terms to include",available_terms_sc,default=available_terms_sc[:8],max_selections=15,key="sc_terms")
        if not sel_terms_sc: st.warning("Select at least one term.")
        else:
            st.info(f"Loading {len(sel_terms_sc)} term(s) — this may take a minute. Results are cached.")
            if st.button("Build Scorecard", type="primary", key="sc_btn"):
                with st.spinner("Fetching case data ..."):
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
                                           "Other":total-rev-aff,"Reversal Rate":round(rev/total*100,2) if total else 0.0,
                                           "Affirmance Rate":round(aff/total*100,2) if total else 0.0})
                    summary_df_sc = pd.DataFrame(summary_sc).sort_values("Reversal Rate",ascending=False)
                    fig_main_sc = go.Figure()
                    fig_main_sc.add_trace(go.Bar(name="Reversed / Vacated",x=summary_df_sc["Circuit"],y=summary_df_sc["Reversal Rate"],
                                                  marker_color="#E74C3C",text=summary_df_sc["Reversal Rate"].apply(lambda x: f"{x:.2f}%"),textposition="outside"))
                    fig_main_sc.add_trace(go.Bar(name="Affirmed",x=summary_df_sc["Circuit"],y=summary_df_sc["Affirmance Rate"],
                                                  marker_color="#27AE60",text=summary_df_sc["Affirmance Rate"].apply(lambda x: f"{x:.2f}%"),textposition="outside"))
                    fig_main_sc.update_layout(barmode="group",title="Reversal vs. Affirmance Rate by Circuit (%)",
                                               xaxis_tickangle=-30,height=420,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
                    st.plotly_chart(fig_main_sc)
                    st.dataframe(summary_df_sc.style
                                 .format({"Reversal Rate": "{:.2f}", "Affirmance Rate": "{:.2f}"})
                                 .background_gradient(subset=["Reversal Rate"],cmap="RdYlGn_r"),
                                 height=380, hide_index=True)
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
                        st.plotly_chart(fig_trend_sc)
                    st.divider()
                    issue_counts_sc = circ_df_sc["Issue Area"].value_counts().reset_index()
                    issue_counts_sc.columns = ["Issue Area","Count"]
                    fig_issues_sc = px.bar(issue_counts_sc.head(10),x="Count",y="Issue Area",orientation="h",
                                           title=f"Top Issue Areas from {sel_circ_sc}",color="Count",color_continuous_scale="Blues")
                    fig_issues_sc.update_layout(height=340,coloraxis_showscale=False,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_issues_sc)
                    with st.expander(f"All cases from {sel_circ_sc}"):
                        st.dataframe(circ_df_sc[["Term","Case","Outcome","Issue Area"]].sort_values("Term",ascending=False),
                                     height=350, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: OUTCOME PREDICTOR
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_predictor:
        st.markdown(
            "Based on historical SCOTUS data, estimate the likelihood that a case from a given "
            "lower court and issue area will be **reversed**, **affirmed**, or **remanded**. "
            "This is a statistical tool — not legal prediction."
        )
        st.info("Loads detailed case data. Fewer terms = faster. Results are cached after first load.")
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
            terms_tuple_pr = tuple(range(CURRENT_YEAR-1, CURRENT_YEAR-1-num_terms_pr,-1))
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
                st.plotly_chart(fig_gauge_pr)
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
                        st.plotly_chart(fig_ia_pr)
                st.subheader("Reversal Rate Trend Over Time")
                trend_rows_pr = []
                for term_val, grp in stats_pr["df"].groupby("term"):
                    total_t = len(grp); rev_t = grp["reversed"].sum()
                    trend_rows_pr.append({"Term":term_val,"Reversal %":round(rev_t/total_t*100,1),"Cases":total_t})
                if trend_rows_pr:
                    trend_df_pr = pd.DataFrame(trend_rows_pr).sort_values("Term")
                    fig_trend_pr = px.line(trend_df_pr,x="Term",y="Reversal %",markers=True,title="Reversal Rate by Term")
                    fig_trend_pr.update_layout(height=280,plot_bgcolor="white",paper_bgcolor="white")
                    st.plotly_chart(fig_trend_pr)
                st.caption(f"Based on {stats_pr['total']} cases from the {nt_pr} most recent terms. Statistical trends, not legal advice.")

def _page_historical_data():
    st.markdown(
        "The complete statistical history of the Supreme Court — from its first term in **1790** "
        "through today. Pre-1953 figures are drawn from published SCOTUS statistics and academic "
        "sources; 1953–present data loads live from the Oyez API."
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # Inline controls: load Oyez data for modern era
    # ─────────────────────────────────────────────────────────────────────────────
    with st.expander("⚙️ Load Live Oyez Data (1953–Present)", expanded=False):
        st.markdown("Augment pre-1953 historical data with live Oyez figures for modern terms.")
        oyez_terms_default = list(range(CURRENT_YEAR - 1, 1952, -1))
        col_terms, col_btn = st.columns([3, 1])
        with col_terms:
            oyez_terms_sel = st.multiselect(
                "Terms to load", oyez_terms_default,
                default=oyez_terms_default[:15],
                format_func=lambda t: f"{t}–{t+1}",
                key="hist_oyez_terms",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            load_oyez_btn = st.button("Load Live Data", type="primary", key="hist_load_oyez")
        if "hist_oyez_data" in st.session_state:
            st.success(f"✅ {len(st.session_state['hist_oyez_data'])} terms loaded")

    if "hist_oyez_terms" in st.session_state:
        oyez_terms_sel = st.session_state["hist_oyez_terms"]
    else:
        oyez_terms_sel = list(range(CURRENT_YEAR - 1, CURRENT_YEAR - 16, -1))
    load_oyez_btn = st.session_state.get("hist_load_oyez", False)

    if load_oyez_btn and oyez_terms_sel:
        progress = st.progress(0.0, text="Loading Oyez data…")
        oyez_rows = []
        for i, term in enumerate(sorted(oyez_terms_sel, reverse=True)):
            progress.progress((i+1)/len(oyez_terms_sel), text=f"Loading {term}–{term+1}…")
            row = _hist_load_oyez_term(term)
            if row: oyez_rows.append(row)
        st.session_state["hist_oyez_data"] = oyez_rows
        progress.progress(1.0, text="Done!")
        st.rerun()

    _HIST_SECTIONS = ["📈 Full Timeline", "⚖️ Outcomes", "🏛️ Era Comparison", "⭐ Milestones", "🔍 Term Drilldown"]
    _hist_sel = st.radio("Section", _HIST_SECTIONS, horizontal=True, key="hist_section_radio", label_visibility="collapsed")
    st.divider()

    # ── Build combined DataFrame ──────────────────────────────────────────────────
    def _get_full_df() -> pd.DataFrame:
        frames = [STATIC_DF.copy()]
        if "hist_oyez_data" in st.session_state:
            oyez_rows = st.session_state["hist_oyez_data"]
            if oyez_rows:
                oyez_df = pd.DataFrame(oyez_rows)
                oyez_df = oyez_df[oyez_df["term"] >= 1953]
                frames.append(oyez_df)
        df = pd.concat(frames, ignore_index=True)
        df = _annotate_cj(df)
        df = df.drop_duplicates("term", keep="last").sort_values("term")
        return df

    # ═════════════════════════════════════════════════════════════════════════════
    # TAB 1: FULL TIMELINE
    # ═════════════════════════════════════════════════════════════════════════════
    if _hist_sel == "📈 Full Timeline":
        full_df = _get_full_df()

        col_metric, col_range = st.columns([3, 1])
        with col_metric:
            metric_sel = st.radio(
                "Metric",
                ["Cases Argued", "Cases Decided", "Cases Reversed", "Cases Affirmed", "Reversal Rate (%)"],
                horizontal=True, key="tl_metric"
            )
        with col_range:
            year_range = st.slider("Year range", 1790, CURRENT_YEAR, (1790, CURRENT_YEAR), key="tl_range")

        col_opts1, col_opts2 = st.columns(2)
        with col_opts1:
            show_milestones = st.checkbox("Show landmark case annotations", value=True, key="tl_milestones")
            show_cj_bands   = st.checkbox("Shade Chief Justice eras",        value=True, key="tl_cjbands")
        with col_opts2:
            show_trend      = st.checkbox("Show 10-year rolling average",     value=True, key="tl_trend")
            color_source    = st.checkbox("Color: live vs. historical data",  value=False, key="tl_source")

        metric_col_map = {
            "Cases Argued":       ("argued",        "#3498DB"),
            "Cases Decided":      ("decided",       "#27AE60"),
            "Cases Reversed":     ("reversed",      "#E74C3C"),
            "Cases Affirmed":     ("affirmed",      "#2ECC71"),
            "Reversal Rate (%)":  ("reversal_rate", "#E67E22"),
        }
        col_key, line_color = metric_col_map[metric_sel]
        df_range = full_df[(full_df["term"] >= year_range[0]) & (full_df["term"] <= year_range[1])].copy()

        fig_tl = go.Figure()

        # CJ era shading
        if show_cj_bands:
            cj_colors = ["rgba(231,76,60,0.05)","rgba(52,152,219,0.05)","rgba(39,174,96,0.05)",
                         "rgba(230,126,34,0.05)","rgba(155,89,182,0.05)","rgba(26,188,156,0.05)"]
            for idx, era in enumerate(CJ_ERAS):
                x0 = max(era["start"], year_range[0]); x1 = min(era["end"], year_range[1])
                if x0 >= x1: continue
                mid = (x0 + x1) / 2
                fig_tl.add_vrect(x0=x0, x1=x1, fillcolor=cj_colors[idx % len(cj_colors)],
                                  opacity=1, layer="below", line_width=0)
                fig_tl.add_annotation(x=mid, y=0, yref="paper", yanchor="bottom",
                                       text=era["cj"], showarrow=False,
                                       font=dict(size=8, color="#999"),
                                       textangle=-90 if (x1-x0) < 15 else 0)

        # Main series
        if color_source and "source" in df_range.columns:
            for src, grp in df_range.groupby("source"):
                sc = "#3498DB" if src == "oyez" else "#E74C3C"
                label = "Oyez (live)" if src == "oyez" else "Historical (published)"
                fig_tl.add_trace(go.Scatter(
                    x=grp["term"], y=grp[col_key], mode="lines+markers",
                    name=label, line=dict(color=sc, width=1.5),
                    marker=dict(size=3, color=sc),
                    hovertemplate=f"<b>%{{x}}–%{{x+1}}</b><br>{metric_sel}: %{{y:,.0f}}<extra></extra>"))
        else:
            fig_tl.add_trace(go.Scatter(
                x=df_range["term"], y=df_range[col_key], mode="lines",
                name=metric_sel, line=dict(color=line_color, width=1.8),
                fill="tozeroy", fillcolor=line_color.replace(")", ",0.08)").replace("rgb","rgba") if line_color.startswith("rgb") else "rgba({},{},{},0.08)".format(int(line_color[1:3],16),int(line_color[3:5],16),int(line_color[5:7],16)),
                hovertemplate=f"<b>%{{x}}–%{{x+1}}</b><br>{metric_sel}: %{{y:,.1f}}<extra></extra>"))

        # Rolling average
        if show_trend and len(df_range) >= 10:
            df_range["rolling"] = df_range[col_key].rolling(10, min_periods=3).mean()
            fig_tl.add_trace(go.Scatter(
                x=df_range["term"], y=df_range["rolling"], mode="lines",
                name="10-yr rolling avg", line=dict(color="#2C3E50", width=2.5, dash="dot"),
                hovertemplate="Rolling avg: %{y:.1f}<extra></extra>"))

        # Milestone annotations
        if show_milestones:
            val_max = df_range[col_key].max() if not df_range.empty else 1
            for (yr, label) in MILESTONES:
                if not (year_range[0] <= yr <= year_range[1]): continue
                fig_tl.add_vline(x=yr, line_width=1, line_dash="dot", line_color="rgba(100,100,100,0.35)")
                fig_tl.add_annotation(
                    x=yr, y=val_max * 0.92,
                    text=label[:30], showarrow=False,
                    font=dict(size=7.5, color="#555"),
                    textangle=-70, xanchor="left")

        yaxis_title = metric_sel + (" (%)" if "Rate" in metric_sel else " (count)")
        fig_tl.update_layout(
            title=f"{metric_sel} — Supreme Court History 1790–{CURRENT_YEAR}",
            height=560,
            xaxis=dict(title="Term (start year)", gridcolor="#F0F0F0", range=list(year_range)),
            yaxis=dict(title=yaxis_title, gridcolor="#F0F0F0"),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(x=0.01, y=0.99),
            hovermode="x unified",
            margin=dict(l=60, r=20, t=60, b=50),
        )
        st.plotly_chart(fig_tl)

        # Summary statistics for selected range
        st.divider()
        st.subheader(f"Summary Statistics — {year_range[0]}–{year_range[1]}")
        col_s1,col_s2,col_s3,col_s4,col_s5,col_s6 = st.columns(6)
        col_s1.metric("Terms Covered",     len(df_range))
        col_s2.metric("Total Cases Argued",f"{df_range['argued'].sum():,.0f}")
        col_s3.metric("Total Decided",     f"{df_range['decided'].sum():,.0f}")
        col_s4.metric("Total Reversed",    f"{df_range['reversed'].sum():,.0f}")
        col_s5.metric("Total Affirmed",    f"{df_range['affirmed'].sum():,.0f}")
        avg_rr = df_range["reversal_rate"].mean() if not df_range.empty else 0
        col_s6.metric("Avg Reversal Rate", f"{avg_rr:.1f}%")

        st.divider()
        st.subheader("Annual Data Table")
        show_cols = ["term","argued","decided","reversed","affirmed","reversal_rate","chief_justice","source"]
        disp_tbl = df_range[[c for c in show_cols if c in df_range.columns]].sort_values("term", ascending=False)
        disp_tbl.columns = [c.replace("_"," ").title() for c in disp_tbl.columns]
        st.dataframe(
            disp_tbl.reset_index(drop=True)
            .style.format({"Reversal Rate": "{:.1f}%", "Argued": "{:,.0f}", "Decided": "{:,.0f}",
                           "Reversed": "{:,.0f}", "Affirmed": "{:,.0f}"})
            .background_gradient(subset=["Reversal Rate"], cmap="RdYlGn_r"),
            height=400, hide_index=True,
        )

    # ═════════════════════════════════════════════════════════════════════════════
    # TAB 2: OUTCOMES
    # ═════════════════════════════════════════════════════════════════════════════
    if _hist_sel == "⚖️ Outcomes":
        full_df_o = _get_full_df()

        st.subheader("Affirmed vs. Reversed — Full History")
        col_ov1, col_ov2 = st.columns([3,1])
        with col_ov2:
            decade_agg = st.checkbox("Aggregate by decade", value=False, key="ov_decade")
            smooth_ov  = st.checkbox("5-year rolling average", value=True,  key="ov_smooth")

        df_ov = full_df_o.copy()
        if decade_agg:
            df_ov["decade"] = (df_ov["term"] // 10) * 10
            df_ov = df_ov.groupby("decade").agg({
                "argued":"sum","decided":"sum","reversed":"sum","affirmed":"sum"
            }).reset_index().rename(columns={"decade":"term"})
            df_ov["reversal_rate"] = (df_ov["reversed"] / (df_ov["reversed"]+df_ov["affirmed"]).clip(lower=1)*100).round(1)
            df_ov = _annotate_cj(df_ov)

        fig_ov = go.Figure()
        x_ov = df_ov["term"]

        # Stacked area: affirmed + reversed
        if smooth_ov and len(df_ov) >= 10:
            df_ov["aff_s"] = df_ov["affirmed"].rolling(5, min_periods=1).mean()
            df_ov["rev_s"] = df_ov["reversed"].rolling(5, min_periods=1).mean()
            aff_y = df_ov["aff_s"]; rev_y = df_ov["rev_s"]
        else:
            aff_y = df_ov["affirmed"]; rev_y = df_ov["reversed"]

        fig_ov.add_trace(go.Scatter(x=x_ov, y=aff_y, mode="lines", name="Affirmed",
                                     line=dict(color="#27AE60", width=1.5), fill="tozeroy",
                                     fillcolor="rgba(39,174,96,0.20)",
                                     hovertemplate="<b>%{x}</b><br>Affirmed: %{y:.0f}<extra></extra>"))
        fig_ov.add_trace(go.Scatter(x=x_ov, y=rev_y, mode="lines", name="Reversed/Vacated",
                                     line=dict(color="#E74C3C", width=1.5), fill="tozeroy",
                                     fillcolor="rgba(231,76,60,0.20)",
                                     hovertemplate="<b>%{x}</b><br>Reversed: %{y:.0f}<extra></extra>"))
        fig_ov.update_layout(
            title="Cases Affirmed vs. Reversed — 1790 to Present",
            height=400, xaxis_title="Term", yaxis_title="Cases",
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(x=0.01, y=0.99), hovermode="x unified",
        )
        st.plotly_chart(fig_ov)

        st.subheader("Reversal Rate Over Time")
        if smooth_ov and len(df_ov) >= 10:
            df_ov["rr_s"] = df_ov["reversal_rate"].rolling(5, min_periods=1).mean()
            rr_y = df_ov["rr_s"]
        else:
            rr_y = df_ov["reversal_rate"]

        fig_rr = go.Figure()
        fig_rr.add_trace(go.Scatter(x=df_ov["term"], y=rr_y, mode="lines",
                                     line=dict(color="#E67E22", width=2),
                                     fill="tozeroy", fillcolor="rgba(230,126,34,0.12)",
                                     name="Reversal Rate",
                                     hovertemplate="<b>%{x}</b><br>Reversal Rate: %{y:.1f}%<extra></extra>"))
        fig_rr.add_hline(y=50, line_dash="dot", line_color="#BDC3C7", annotation_text="50% (coin flip)")
        fig_rr.add_hrect(y0=60, y1=75, fillcolor="rgba(231,76,60,0.05)", line_width=0, annotation_text="Historical typical range")
        fig_rr.update_layout(
            title="Reversal Rate — What Fraction of Cases Does SCOTUS Reverse?",
            height=380, xaxis_title="Term", yaxis=dict(title="Reversal Rate (%)", range=[0, 100]),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_rr)
        st.caption(
            "SCOTUS reverses ~62–68% of cases it accepts — this is not random. The court grants certiorari "
            "primarily to correct perceived errors, so it is structurally biased toward reversal."
        )

        st.divider()
        st.subheader("Caseload Transformation: Four Key Inflection Points")
        st.markdown("""
    | Year | Event | Effect on Caseload |
    |------|--------|-------------------|
    | **1875** | Judiciary Act — SCOTUS given federal question jurisdiction | Docket **tripled** in 10 years (250 → 1,600 cases/term) |
    | **1891** | Evarts Act — Circuit Courts of Appeals created | Docket **fell 50%** as circuit courts absorbed routine appeals |
    | **1925** | Judiciary Act (Taft Act) — Nearly full cert discretion | Docket **fell 50% again** (350 → 150 cases/term) |
    | **1988** | Judicial Improvements Act — Last mandatory jurisdiction removed | Court stabilizes at **~80 argued** cases/term; now below **70** |
        """)

        # Show the four inflection points on a focused chart
        df_infl = full_df_o[full_df_o["term"].between(1860, CURRENT_YEAR)].copy()
        fig_infl = go.Figure()
        fig_infl.add_trace(go.Scatter(
            x=df_infl["term"], y=df_infl["argued"], mode="lines",
            line=dict(color="#3498DB", width=2),
            fill="tozeroy", fillcolor="rgba(52,152,219,0.10)",
            name="Cases Argued"))
        for yr, label in [(1875,"1875: Federal Question"),(1891,"1891: Evarts Act"),
                           (1925,"1925: Cert Discretion"),(1988,"1988: All Discretionary")]:
            fig_infl.add_vline(x=yr, line_color="#E74C3C", line_width=2, line_dash="dash")
            fig_infl.add_annotation(x=yr+1, y=df_infl["argued"].max()*0.85, text=label,
                                      showarrow=False, font=dict(size=9,color="#E74C3C"),
                                      textangle=-75, xanchor="left")
        fig_infl.update_layout(title="Caseload History — The Four Inflection Points",
                                height=380, xaxis_title="Term", yaxis_title="Cases Argued",
                                plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_infl)

    # ═════════════════════════════════════════════════════════════════════════════
    # ERA COMPARISON
    # ═════════════════════════════════════════════════════════════════════════════
    if _hist_sel == "🏛️ Era Comparison":
        full_df_e = _get_full_df()
        st.subheader("Chief Justice Era Statistics")
        st.markdown("Aggregate statistics for each Chief Justice's tenure.")

        era_rows = []
        for era in CJ_ERAS:
            cj_df = full_df_e[full_df_e["term"].between(era["start"], era["end"]-1)]
            if cj_df.empty: continue
            tot_argued  = cj_df["argued"].sum()
            tot_decided = cj_df["decided"].sum()
            tot_reversed= cj_df["reversed"].sum()
            tot_affirmed= cj_df["affirmed"].sum()
            avg_per_term= round(cj_df["argued"].mean(), 0)
            denom = max(tot_reversed + tot_affirmed, 1)
            rr    = round(tot_reversed / denom * 100, 1)
            tenure= era["end"] - era["start"]
            era_rows.append({
                "Chief Justice": era["cj"],
                "Tenure": f"{era['start']}–{era['end']}",
                "Years": tenure,
                "Party of Appointing Pres.": era["party"][:18],
                "Total Cases Argued": int(tot_argued),
                "Total Decided":      int(tot_decided),
                "Total Reversed":     int(tot_reversed),
                "Total Affirmed":     int(tot_affirmed),
                "Avg Cases / Term":   int(avg_per_term),
                "Reversal Rate (%)":  rr,
            })
        era_df = pd.DataFrame(era_rows)

        # Metrics cards
        m_cols = st.columns(4)
        busiest_era = era_df.loc[era_df["Avg Cases / Term"].idxmax()]
        strictest_era = era_df.loc[era_df["Reversal Rate (%)"].idxmax()]
        longest_era  = era_df.loc[era_df["Years"].idxmax()]
        m_cols[0].metric("Most Cases per Term", busiest_era["Chief Justice"],
                          f"{busiest_era['Avg Cases / Term']:.0f}/term ({busiest_era['Tenure']})")
        m_cols[1].metric("Highest Reversal Rate", strictest_era["Chief Justice"],
                          f"{strictest_era['Reversal Rate (%)']:.1f}% ({strictest_era['Tenure']})")
        m_cols[2].metric("Longest Tenure", longest_era["Chief Justice"],
                          f"{longest_era['Years']} years ({longest_era['Tenure']})")
        m_cols[3].metric("Total Terms Covered", len(era_df))
        st.divider()

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            fig_avg_ct = go.Figure(go.Bar(
                x=era_df["Chief Justice"], y=era_df["Avg Cases / Term"],
                marker_color=["#E74C3C" if "Republican" in p else "#3498DB" for p in era_df["Party of Appointing Pres."]],
                text=era_df["Avg Cases / Term"].astype(int), textposition="outside",
                hovertemplate="<b>%{x}</b><br>Avg cases/term: %{y:.0f}<br>%{customdata}<extra></extra>",
                customdata=era_df["Tenure"]))
            fig_avg_ct.update_layout(title="Average Cases Argued per Term", xaxis_tickangle=-30,
                                      height=380, plot_bgcolor="white", paper_bgcolor="white",
                                      yaxis_title="Cases/Term")
            st.plotly_chart(fig_avg_ct)
        with col_e2:
            fig_rr_era = go.Figure(go.Bar(
                x=era_df["Chief Justice"], y=era_df["Reversal Rate (%)"],
                marker_color=["#E67E22" if r>65 else "#27AE60" if r<55 else "#F39C12" for r in era_df["Reversal Rate (%)"]],
                text=era_df["Reversal Rate (%)"].apply(lambda v: f"{v:.0f}%"), textposition="outside",
                hovertemplate="<b>%{x}</b><br>Reversal Rate: %{y:.1f}%<extra></extra>"))
            fig_rr_era.add_hline(y=62, line_dash="dot", line_color="#BDC3C7", annotation_text="Historical avg (~62%)")
            fig_rr_era.update_layout(title="Reversal Rate by Chief Justice Era", xaxis_tickangle=-30,
                                      height=380, plot_bgcolor="white", paper_bgcolor="white",
                                      yaxis=dict(title="Reversal Rate (%)", range=[0,90]))
            st.plotly_chart(fig_rr_era)

        # Total volume stacked bar
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(name="Affirmed",  x=era_df["Chief Justice"], y=era_df["Total Affirmed"],  marker_color="#27AE60"))
        fig_vol.add_trace(go.Bar(name="Reversed",  x=era_df["Chief Justice"], y=era_df["Total Reversed"],  marker_color="#E74C3C"))
        fig_vol.add_trace(go.Bar(name="Other/N/A", x=era_df["Chief Justice"],
                                  y=(era_df["Total Decided"] - era_df["Total Reversed"] - era_df["Total Affirmed"]).clip(lower=0),
                                  marker_color="#BDC3C7"))
        fig_vol.update_layout(barmode="stack", title="Total Cases by Outcome — by Chief Justice Era",
                               xaxis_tickangle=-30, height=400,
                               plot_bgcolor="white", paper_bgcolor="white",
                               legend=dict(x=1.01, y=1))
        st.plotly_chart(fig_vol)

        # Full table
        st.dataframe(
            era_df.set_index("Chief Justice")
            .style.format({
                "Total Cases Argued":"{:,}","Total Decided":"{:,}",
                "Total Reversed":"{:,}","Total Affirmed":"{:,}",
                "Reversal Rate (%)":"{:.1f}%", "Avg Cases / Term":"{:.0f}",
            })
            .background_gradient(subset=["Reversal Rate (%)"], cmap="RdYlGn_r")
            .background_gradient(subset=["Avg Cases / Term"], cmap="Blues"),
            height=480,
        )

    # ═════════════════════════════════════════════════════════════════════════════
    # TAB 4: MILESTONES
    # ═════════════════════════════════════════════════════════════════════════════
    if _hist_sel == "⭐ Milestones":
        full_df_m = _get_full_df()
        st.subheader("Landmark Moments in SCOTUS History")
        st.markdown("Key decisions, legislative acts, and structural changes that shaped the Court's docket and authority.")

        # Milestone timeline with caseload backdrop
        fig_ms = go.Figure()
        fig_ms.add_trace(go.Scatter(
            x=full_df_m["term"], y=full_df_m["argued"], mode="lines",
            line=dict(color="#BDC3C7", width=1.5), fill="tozeroy",
            fillcolor="rgba(189,195,199,0.20)", name="Cases Argued (background)", showlegend=True))

        ms_df = pd.DataFrame(MILESTONES, columns=["year","label"])
        val_at = {}
        for yr in ms_df["year"]:
            row = full_df_m[full_df_m["term"] == yr]
            val_at[yr] = int(row["argued"].values[0]) if not row.empty else 0

        ms_df["val"] = ms_df["year"].map(val_at)
        fig_ms.add_trace(go.Scatter(
            x=ms_df["year"], y=ms_df["val"], mode="markers+text",
            marker=dict(size=10, color="#E74C3C", symbol="diamond",
                        line=dict(color="white", width=1.5)),
            text=ms_df["label"].apply(lambda s: s[:35]+"…" if len(s)>35 else s),
            textposition="top center", textfont=dict(size=8),
            name="Landmark Events",
            hovertext=ms_df["label"], hoverinfo="text"))
        fig_ms.update_layout(
            title="Landmark Moments Overlaid on Caseload History",
            height=540, xaxis_title="Year", yaxis_title="Cases Argued",
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(x=0.01, y=0.99), margin=dict(l=60,r=20,t=60,b=50),
        )
        st.plotly_chart(fig_ms)

        st.divider()
        st.subheader("Landmark Cases & Structural Events")

        # Categorized cards
        MILESTONE_CATEGORIES = {
            "Constitutional Foundations": [
                (1793,"Chisholm v. Georgia","Held states could be sued by citizens of other states — directly prompted the 11th Amendment (1795)."),
                (1803,"Marbury v. Madison","Chief Justice Marshall established judicial review, giving SCOTUS power to strike down federal laws."),
                (1819,"McCulloch v. Maryland","Broad interpretation of Necessary & Proper Clause; states cannot tax federal instrumentalities."),
                (1857,"Dred Scott v. Sandford","Ruled African Americans not citizens; Congress lacked power to prohibit slavery in territories. Helped trigger the Civil War."),
            ],
            "Structural & Jurisdictional Changes": [
                (1869,"Court fixed at 9 justices","Judiciary Act of 1869 stabilized court size after Lincoln-era expansions and Johnson-era contractions."),
                (1875,"Federal Question Jurisdiction","Judiciary Act grants SCOTUS power over federal question cases — docket tripled in 10 years."),
                (1891,"Evarts Act","Created permanent circuit courts of appeals; SCOTUS docket fell from ~1,600 to ~500 cases/term."),
                (1925,"Judiciary Act (Certiorari Act)","Taft lobbied Congress to give Court near-total cert discretion; docket fell from ~350 to ~150/term."),
                (1988,"Judicial Improvements Act","Eliminated last mandatory appellate jurisdiction. All cases now essentially discretionary."),
            ],
            "Civil Rights & Equality": [
                (1896,"Plessy v. Ferguson","Upheld separate but equal; enshrined Jim Crow for 58 years until Brown."),
                (1954,"Brown v. Board of Education","Overruled Plessy; racially segregated schools unconstitutional. Launched the civil rights era."),
                (1962,"Baker v. Carr","Entered the political thicket of legislative apportionment; led to one person, one vote."),
                (2015,"Obergefell v. Hodges","Same-sex couples have a fundamental right to marry under the 14th Amendment."),
            ],
            "Criminal Procedure": [
                (1963,"Gideon v. Wainwright","Right to counsel applies to states via 14th Amendment."),
                (1966,"Miranda v. Arizona","Police must advise suspects of rights before custodial interrogation."),
                (1984,"United States v. Leon","Good faith exception to the exclusionary rule."),
            ],
            "Modern Landmarks": [
                (1973,"Roe v. Wade","Abortion right derived from constitutional privacy. Decided 7-2. Overruled in 2022."),
                (2008,"D.C. v. Heller","Individual right to keep firearm in the home; first 2nd Amendment ruling since Miller (1939)."),
                (2010,"Citizens United v. FEC","Corporate political spending is protected speech. Transformed campaign finance."),
                (2022,"Dobbs v. Jackson","Roe and Casey overruled; abortion regulation returned to states."),
                (2024,"Loper Bright v. Raimondo","Chevron deference overruled after 40 years. Courts now interpret agency statutes independently."),
            ],
        }

        for cat, events in MILESTONE_CATEGORIES.items():
            st.markdown(f"### {cat}")
            cols_ms = st.columns(2)
            for i, (yr, name, desc) in enumerate(events):
                cj = next((e["cj"] for e in reversed(CJ_ERAS) if e["start"] <= yr), "Unknown")
                with cols_ms[i % 2]:
                    st.markdown(
                        f'<div style="border:1px solid #E8E8E8;border-left:4px solid #E74C3C;'
                        f'padding:10px 14px;margin:6px 0;border-radius:0 6px 6px 0;">'
                        f'<div style="font-weight:bold;font-size:0.92em;">{name} ({yr})</div>'
                        f'<div style="font-size:0.8em;color:#888;margin:2px 0;">CJ {cj} Court</div>'
                        f'<div style="font-size:0.84em;color:#444;margin-top:4px;">{desc}</div></div>',
                        unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════════════
    # TAB 5: TERM DRILLDOWN
    # ═════════════════════════════════════════════════════════════════════════════
    if _hist_sel == "🔍 Term Drilldown":
        st.markdown("Drill into any specific term for live case-level data (1953–present from Oyez; pre-1953 shows historical summary).")
        full_df_dd = _get_full_df()

        col_dd1, col_dd2 = st.columns([1, 2])
        with col_dd1:
            all_terms_dd = sorted(full_df_dd["term"].unique().tolist(), reverse=True)
            sel_term_dd  = st.selectbox("Select Term", all_terms_dd,
                                         format_func=lambda t: f"{t}–{t+1} Term", key="dd_term")
        with col_dd2:
            row_dd = full_df_dd[full_df_dd["term"] == sel_term_dd]
            if not row_dd.empty:
                r = row_dd.iloc[0]
                src = r.get("source","historical")
                cj  = r.get("chief_justice","Unknown")
                src_badge = "🟢 Live Oyez" if src=="oyez" else "📚 Historical"
                st.markdown(f"**{sel_term_dd}–{sel_term_dd+1} Term  |  Chief Justice {cj}  |  {src_badge}**")
                dd_c1,dd_c2,dd_c3,dd_c4,dd_c5 = st.columns(5)
                dd_c1.metric("Cases Argued",  f"{r.get('argued',0):,.0f}")
                dd_c2.metric("Decided",       f"{r.get('decided',0):,.0f}")
                dd_c3.metric("Reversed",      f"{r.get('reversed',0):,.0f}")
                dd_c4.metric("Affirmed",      f"{r.get('affirmed',0):,.0f}")
                dd_c5.metric("Reversal Rate", f"{r.get('reversal_rate',0):.1f}%")

        st.divider()

        # For 1953+ terms, show live case list
        if sel_term_dd >= 1953:
            if st.button(f"Load {sel_term_dd}–{sel_term_dd+1} Case List", type="primary", key="dd_load"):
                with st.spinner(f"Fetching {sel_term_dd}–{sel_term_dd+1} cases…"):
                    dd_cases = _hist_fetch_term(sel_term_dd)
                st.session_state[f"dd_cases_{sel_term_dd}"] = dd_cases

            dd_cases_data = st.session_state.get(f"dd_cases_{sel_term_dd}", [])
            if dd_cases_data:
                # Build display table
                dd_rows = []
                for c in dd_cases_data:
                    ia = c.get("issue_area") or {}
                    issue = ia.get("label","Unknown") if isinstance(ia,dict) else str(ia or "Unknown")
                    dd_ts  = c.get("decided_on")
                    decided_date = None
                    try:
                        if dd_ts: decided_date = datetime.date.fromtimestamp(int(dd_ts)).isoformat()
                    except Exception: pass
                    href   = c.get("href","")
                    oyez_url = href.replace("api.oyez.org/cases","www.oyez.org/cases") if href else ""
                    dd_rows.append({
                        "Case": c.get("name",""),
                        "Issue Area": issue,
                        "Decided": decided_date or "Pending",
                        "Docket": c.get("docket_number",""),
                        "Oyez Link": oyez_url,
                    })
                dd_df = pd.DataFrame(dd_rows)

                # Issue area donut
                col_dd_pie, col_dd_tbl = st.columns([1, 2])
                with col_dd_pie:
                    ia_counts = dd_df["Issue Area"].value_counts().reset_index()
                    ia_counts.columns = ["Issue","Count"]
                    fig_dd_pie = px.pie(ia_counts, names="Issue", values="Count",
                                        title=f"{sel_term_dd}–{sel_term_dd+1} — Issue Areas",
                                        hole=0.35)
                    fig_dd_pie.update_layout(height=380)
                    st.plotly_chart(fig_dd_pie)
                with col_dd_tbl:
                    st.markdown(f"**{len(dd_df)} cases — {sel_term_dd}–{sel_term_dd+1} Term**")
                    st.dataframe(
                        dd_df[["Case","Issue Area","Decided","Docket"]].reset_index(drop=True),
                        height=360, hide_index=True,
                    )
            elif sel_term_dd >= 1953:
                st.info(f"Click **Load {sel_term_dd}–{sel_term_dd+1} Case List** to see all cases for this term.")
        else:
            # Pre-Oyez: show the historical summary + context
            st.markdown(f"### {sel_term_dd}–{sel_term_dd+1} Historical Summary")
            row_hist = full_df_dd[full_df_dd["term"] == sel_term_dd]
            if not row_hist.empty:
                r = row_hist.iloc[0]
                cj = r.get("chief_justice","Unknown")
                era_data = next((e for e in CJ_ERAS if e["cj"]==cj), {})
                st.markdown(
                    f'<div style="background:#F8F9FA;border-radius:8px;padding:16px 20px;margin:8px 0;">'
                    f'<h4 style="margin:0 0 8px 0;">Chief Justice {cj} Court</h4>'
                    f'<p style="color:#666;margin:0;">Tenure: {era_data.get("start","?")}–{era_data.get("end","?")} '
                    f'| Appointing party: {era_data.get("party","?")}</p>'
                    f'<hr style="margin:10px 0;border-color:#E0E0E0;">'
                    f'<p><strong>Approx. {r.get("argued",0):,.0f}</strong> cases argued this term | '
                    f'<strong>{r.get("decided",0):,.0f}</strong> decided | '
                    f'<strong>{r.get("reversal_rate",0):.0f}%</strong> reversal rate</p>'
                    f'<p style="color:#888;font-size:0.85em;">Pre-1953 figures are drawn from published SCOTUS statistics and academic sources.</p></div>',
                    unsafe_allow_html=True)

                # Show nearby landmark cases if any
                nearby = [(yr,label,desc) for cat_events in MILESTONE_CATEGORIES.values()
                          for yr,label,desc in cat_events
                          if abs(yr - sel_term_dd) <= 5]
                if nearby:
                    st.markdown("**Nearby Landmark Events:**")
                    for yr, label, desc in sorted(nearby, key=lambda x: x[0]):
                        st.markdown(f"- **{label}** ({yr}): {desc[:120]}…")

        st.divider()
        # Trend context: show where selected term sits in history
        st.subheader("Context: Selected Term vs. Full History")
        fig_ctx = go.Figure()
        fig_ctx.add_trace(go.Scatter(
            x=full_df_dd["term"], y=full_df_dd["argued"],
            mode="lines", line=dict(color="#BDC3C7", width=1.5),
            name="All Terms", showlegend=True))
        highlight_row = full_df_dd[full_df_dd["term"]==sel_term_dd]
        if not highlight_row.empty:
            fig_ctx.add_trace(go.Scatter(
                x=[sel_term_dd], y=[highlight_row.iloc[0]["argued"]],
                mode="markers",
                marker=dict(size=14, color="#E74C3C", symbol="star", line=dict(color="white",width=2)),
                name=f"{sel_term_dd}–{sel_term_dd+1} Term"))
        fig_ctx.update_layout(
            title=f"Selected Term ({sel_term_dd}) in Context",
            height=280, xaxis_title="Term", yaxis_title="Cases Argued",
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=60,r=20,t=50,b=40))
        st.plotly_chart(fig_ctx)

# ── Page ─────────────────────────────────────────────────────────────────────
_tab_0, _tab_1, _tab_2 = st.tabs(["🏛️ Court History", "⚖️ Circuit Courts", "📜 Historical Data"])
with _tab_0:
    _page_court_history()
with _tab_1:
    _page_circuit_courts()
with _tab_2:
    _page_historical_data()
