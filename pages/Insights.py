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
from utils.local_data import fetch_oyez, infer_issue_area


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Static Data ───────────────────────────────────────────────────────────────
# (name, start_year, end_year_or_None, appointing_president, president_party, lean, seat)
JUSTICES_DATA = [
    ("Earl Warren",           1953, 1969, "Eisenhower",   "R", "Liberal",       "Chief Justice"),
    ("Hugo Black",            1937, 1971, "F. Roosevelt", "D", "Liberal",       "Associate"),
    ("William O. Douglas",    1939, 1975, "F. Roosevelt", "D", "Liberal",       "Associate"),
    ("Tom Clark",             1949, 1967, "Truman",       "D", "Moderate",      "Associate"),
    ("John Harlan II",        1955, 1971, "Eisenhower",   "R", "Conservative",  "Associate"),
    ("William Brennan",       1956, 1990, "Eisenhower",   "R", "Liberal",       "Associate"),
    ("Potter Stewart",        1958, 1981, "Eisenhower",   "R", "Moderate",      "Associate"),
    ("Byron White",           1962, 1993, "Kennedy",      "D", "Moderate",      "Associate"),
    ("Arthur Goldberg",       1962, 1965, "Kennedy",      "D", "Liberal",       "Associate"),
    ("Abe Fortas",            1965, 1969, "Johnson",      "D", "Liberal",       "Associate"),
    ("Thurgood Marshall",     1967, 1991, "Johnson",      "D", "Liberal",       "Associate"),
    ("Warren Burger",         1969, 1986, "Nixon",        "R", "Conservative",  "Chief Justice"),
    ("Harry Blackmun",        1970, 1994, "Nixon",        "R", "Liberal",       "Associate"),
    ("Lewis Powell",          1972, 1987, "Nixon",        "R", "Moderate",      "Associate"),
    ("William Rehnquist",     1972, 2005, "Nixon",        "R", "Conservative",  "Associate/CJ"),
    ("John Paul Stevens",     1975, 2010, "Ford",         "R", "Liberal",       "Associate"),
    ("Sandra Day O'Connor",   1981, 2006, "Reagan",       "R", "Moderate",      "Associate"),
    ("Antonin Scalia",        1986, 2016, "Reagan",       "R", "Conservative",  "Associate"),
    ("Anthony Kennedy",       1988, 2018, "Reagan",       "R", "Moderate",      "Associate"),
    ("David Souter",          1990, 2009, "G.H.W. Bush",  "R", "Liberal",       "Associate"),
    ("Clarence Thomas",       1991, None, "G.H.W. Bush",  "R", "Conservative",  "Associate"),
    ("Ruth Bader Ginsburg",   1993, 2020, "Clinton",      "D", "Liberal",       "Associate"),
    ("Stephen Breyer",        1994, 2022, "Clinton",      "D", "Liberal",       "Associate"),
    ("John G. Roberts",       2005, None, "G.W. Bush",    "R", "Conservative",  "Chief Justice"),
    ("Samuel Alito",          2006, None, "G.W. Bush",    "R", "Conservative",  "Associate"),
    ("Sonia Sotomayor",       2009, None, "Obama",        "D", "Liberal",       "Associate"),
    ("Elena Kagan",           2010, None, "Obama",        "D", "Liberal",       "Associate"),
    ("Neil Gorsuch",          2017, None, "Trump",        "R", "Conservative",  "Associate"),
    ("Brett Kavanaugh",       2018, None, "Trump",        "R", "Conservative",  "Associate"),
    ("Amy Coney Barrett",     2020, None, "Trump",        "R", "Conservative",  "Associate"),
    ("Ketanji Brown Jackson", 2022, None, "Biden",        "D", "Liberal",       "Associate"),
]

PRESIDENTS_ORDER = [
    "F. Roosevelt","Truman","Eisenhower","Kennedy","Johnson","Nixon",
    "Ford","Carter","Reagan","G.H.W. Bush","Clinton","G.W. Bush","Obama","Trump","Biden",
]
PRESIDENT_PARTY = {p: ("D" if p in {"F. Roosevelt","Truman","Kennedy","Johnson","Carter","Clinton","Obama","Biden"} else "R") for p in PRESIDENTS_ORDER}
PRESIDENT_YEARS = {
    "F. Roosevelt":(1933,1945),"Truman":(1945,1953),"Eisenhower":(1953,1961),
    "Kennedy":(1961,1963),"Johnson":(1963,1969),"Nixon":(1969,1974),
    "Ford":(1974,1977),"Carter":(1977,1981),"Reagan":(1981,1989),
    "G.H.W. Bush":(1989,1993),"Clinton":(1993,2001),"G.W. Bush":(2001,2009),
    "Obama":(2009,2017),"Trump":(2017,2021),"Biden":(2021,2025),
}
PARTY_COLORS = {"R": "#E74C3C", "D": "#3498DB"}
LEAN_COLORS  = {"Liberal": "#3498DB", "Moderate": "#27AE60", "Conservative": "#E74C3C"}

# Pre-compute convenience maps
justice_to_president  = {j[0]: j[3] for j in JUSTICES_DATA}
justice_to_lean       = {j[0]: j[5] for j in JUSTICES_DATA}
justice_to_start      = {j[0]: j[1] for j in JUSTICES_DATA}
justice_to_end        = {j[0]: j[2] or CURRENT_YEAR for j in JUSTICES_DATA}

def _president_cohort(president: str) -> list[str]:
    return [j[0] for j in JUSTICES_DATA if j[3] == president]

def _justices_serving_in_term(term: int) -> list[str]:
    return [j[0] for j in JUSTICES_DATA if j[1] <= term <= (j[2] or CURRENT_YEAR)]

def _normalize_justice_name(name: str) -> str:
    name_l = name.lower()
    for j_name in justice_to_president:
        parts = j_name.lower().split()
        last = parts[-1]
        if last in name_l or name_l in j_name.lower():
            return j_name
    return name

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _pl_fetch_cases_term(term: int) -> list[dict]:
    data = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0")
    return data if isinstance(data, list) else []

@st.cache_data(show_spinner=False)
def _pl_fetch_detail(href: str) -> dict | None:
    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

@st.cache_data(show_spinner=False, ttl=3600)
def _pl_load_vote_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = _pl_fetch_cases_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href: continue
            detail = _pl_fetch_detail(href)
            if not detail: continue
            case_name = detail.get("name", "")
            issue = infer_issue_area(detail)
            dec0 = (detail.get("decisions") or [{}])[0]
            disp_label = (dec0.get("decision_type") or "").strip().title()
            for decision in (detail.get("decisions") or []):
                winning_party = decision.get("winning_party", "")
                for vote in (decision.get("votes") or []):
                    member = vote.get("member") or {}
                    j_name = member.get("name", "") if isinstance(member, dict) else ""
                    v      = (vote.get("vote") or "").lower().strip()
                    if not j_name or not v: continue
                    normalized = _normalize_justice_name(j_name)
                    president  = justice_to_president.get(normalized, "Unknown")
                    lean       = justice_to_lean.get(normalized, "Unknown")
                    rows.append({
                        "term": term, "case": case_name, "justice": normalized,
                        "president": president, "lean": lean, "vote": v,
                        "issue_area": issue, "disposition": disp_label,
                        "winning_party": winning_party,
                    })
            time.sleep(0.02)
    return rows

# ── Page layout ───────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
import datetime
import threading
from collections import defaultdict
from pathlib import Path

from utils.ml_predictor import (
    collect_training_data, train_models, predict, load_meta,
    is_trained, CACHE_CSV, extract_circuit,
)


HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year
TODAY        = datetime.date.today()
CURRENT_TERM = CURRENT_YEAR if TODAY.month >= 10 else CURRENT_YEAR - 1

# ── Court roster for display ──────────────────────────────────────────────────
CURRENT_JUSTICES_DISPLAY = [
    {"short": "Roberts",   "lean": "Conservative", "full": "John G. Roberts"},
    {"short": "Thomas",    "lean": "Conservative", "full": "Clarence Thomas"},
    {"short": "Alito",     "lean": "Conservative", "full": "Samuel Alito"},
    {"short": "Sotomayor", "lean": "Liberal",      "full": "Sonia Sotomayor"},
    {"short": "Kagan",     "lean": "Liberal",      "full": "Elena Kagan"},
    {"short": "Gorsuch",   "lean": "Conservative", "full": "Neil Gorsuch"},
    {"short": "Kavanaugh", "lean": "Moderate",     "full": "Brett Kavanaugh"},
    {"short": "Barrett",   "lean": "Conservative", "full": "Amy Coney Barrett"},
    {"short": "Jackson",   "lean": "Liberal",      "full": "Ketanji Brown Jackson"},
]
LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#F39C12", "Liberal": "#3498DB"}

CIRCUIT_OPTIONS = [
    "1st Circuit","2nd Circuit","3rd Circuit","4th Circuit","5th Circuit",
    "6th Circuit","7th Circuit","8th Circuit","9th Circuit","10th Circuit",
    "11th Circuit","D.C. Circuit","Federal Circuit","State Supreme Court","Other",
]
ISSUE_OPTIONS = [
    "Criminal Procedure","Civil Rights","First Amendment","Due Process","Privacy",
    "Economic Activity","Judicial Power","Federalism","Federal Taxation","Unions",
    "Attorneys","Miscellaneous","Interstate Relations","Private Action",
]
PETITIONER_TYPES = [
    "Federal Government","State / Local Gov't","Corporation / Org","Individual / Other"
]
# Historical stats for the static fallback path
CIRCUIT_REVERSAL_RATES = {
    "9th Circuit":0.76,"6th Circuit":0.74,"11th Circuit":0.72,"5th Circuit":0.68,
    "4th Circuit":0.65,"8th Circuit":0.63,"7th Circuit":0.61,"3rd Circuit":0.60,
    "2nd Circuit":0.58,"1st Circuit":0.56,"10th Circuit":0.62,"D.C. Circuit":0.55,
    "Federal Circuit":0.52,"State Supreme Court":0.60,"Other":0.62,
}
ISSUE_REVERSAL_RATES = {
    "Criminal Procedure":0.72,"Civil Rights":0.65,"First Amendment":0.60,"Due Process":0.64,
    "Privacy":0.58,"Economic Activity":0.55,"Judicial Power":0.70,"Federalism":0.62,
    "Federal Taxation":0.54,"Unions":0.63,"Attorneys":0.60,"Miscellaneous":0.61,
    "Interstate Relations":0.59,"Private Action":0.57,
}
PETITIONER_BONUS = {
    "Federal Government":+0.12,"State / Local Gov't":-0.03,
    "Corporation / Org":+0.02,"Individual / Other":-0.05,
}

CERT_FACTORS = {
    "Circuit Split":0.045,"Federal Gov't Petitioner (SG)":0.038,
    "Civil Rights / Equal Protection Issue":0.032,"First Amendment Issue":0.030,
    "Judicial Power / Separation of Powers Issue":0.035,
    "Lower Court Struck Down Federal Law":0.040,"CVSG (Call for Views from SG)":0.060,
    "Prior SCOTUS Case Needs Clarification":0.028,"Significant Economic Impact":0.020,
    "Long-standing Circuit Disagreement (5+ yrs)":0.050,
}
ISSUE_CERT_RATES = {
    "Criminal Procedure":0.028,"Civil Rights":0.025,"First Amendment":0.030,
    "Due Process":0.022,"Privacy":0.027,"Economic Activity":0.018,
    "Judicial Power":0.035,"Federalism":0.032,"Federal Taxation":0.016,
    "Unions":0.021,"Attorneys":0.013,"Miscellaneous":0.010,
    "Interstate Relations":0.015,"Private Action":0.012,
}
CIRCUIT_CERT_MULT = {
    "9th Circuit":1.8,"D.C. Circuit":2.2,"2nd Circuit":1.6,"4th Circuit":1.3,
    "5th Circuit":1.5,"6th Circuit":1.4,"7th Circuit":1.3,"8th Circuit":1.1,
    "10th Circuit":1.1,"11th Circuit":1.3,"3rd Circuit":1.2,"1st Circuit":1.0,
    "Federal Circuit":0.9,"State Supreme Court":0.7,"Other":0.8,
}

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=150&page=0",
                         headers=HEADERS, timeout=12)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False, ttl=600)
def _pred_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

def _parse_date(ts) -> datetime.date | None:
    try:
        if ts: return datetime.date.fromtimestamp(int(ts))
    except Exception: pass
    return None

# ── Static fallback predictor ─────────────────────────────────────────────────
def _static_predict(circuit, issue_area, petitioner_type, sg_support, circuit_split, n_conservative):
    base       = 0.62
    circ_rate  = CIRCUIT_REVERSAL_RATES.get(circuit, 0.62)
    issue_rate = ISSUE_REVERSAL_RATES.get(issue_area, 0.62)
    pet_bonus  = PETITIONER_BONUS.get(petitioner_type, 0.0)
    p_reverse  = (base*0.15 + circ_rate*0.35 + issue_rate*0.25 + pet_bonus
                  + (0.10 if sg_support else 0) + (0.08 if circuit_split else 0)
                  + (n_conservative - 5) * 0.025)
    p_reverse  = max(0.05, min(0.95, p_reverse))

    split_dist = {
        "9-0": max(0, 0.08), "8-1": max(0, 0.10), "7-2": max(0, 0.15),
        "6-3": max(0, p_reverse*0.28 + (1-p_reverse)*0.20),
        "5-4": max(0, p_reverse*0.39 + (1-p_reverse)*0.47),
    }
    total = sum(split_dist.values())
    split_dist = {k: v/total for k, v in split_dist.items()}
    split_label = max(split_dist, key=split_dist.get)

    _JUST_TEND = {
        "Roberts":   {"Criminal Procedure":0.68,"Civil Rights":0.55,"First Amendment":0.60,"default":0.60},
        "Thomas":    {"Criminal Procedure":0.82,"Civil Rights":0.50,"First Amendment":0.62,"default":0.72},
        "Alito":     {"Criminal Procedure":0.78,"Civil Rights":0.52,"First Amendment":0.65,"default":0.68},
        "Sotomayor": {"Criminal Procedure":0.45,"Civil Rights":0.75,"First Amendment":0.62,"default":0.48},
        "Kagan":     {"Criminal Procedure":0.48,"Civil Rights":0.72,"First Amendment":0.65,"default":0.50},
        "Gorsuch":   {"Criminal Procedure":0.72,"Civil Rights":0.48,"First Amendment":0.70,"default":0.65},
        "Kavanaugh": {"Criminal Procedure":0.62,"Civil Rights":0.55,"First Amendment":0.60,"default":0.58},
        "Barrett":   {"Criminal Procedure":0.70,"Civil Rights":0.50,"First Amendment":0.65,"default":0.63},
        "Jackson":   {"Criminal Procedure":0.42,"Civil Rights":0.78,"First Amendment":0.64,"default":0.46},
    }
    cons_adj = (n_conservative - 5) * 0.025
    justice_probs = {}
    for j in CURRENT_JUSTICES_DISPLAY:
        sh = j["short"]
        tend = _JUST_TEND.get(sh, {})
        rate = tend.get(issue_area, tend.get("default", 0.60))
        rate = rate + cons_adj * 0.3
        if j["lean"] == "Liberal": rate = 1 - (1 - rate) * (1 + cons_adj * 0.2)
        rate = max(0.10, min(0.90, rate))
        if p_reverse < 0.5: rate = 1 - rate
        justice_probs[sh] = rate

    return {"p_reverse": round(p_reverse,4), "p_affirm": round(1-p_reverse,4),
            "split_probs": split_dist, "split_label": split_label,
            "justice_probs": justice_probs, "source": "statistical"}

# ── Page header ───────────────────────────────────────────────────────────────

def _page_presidential_legacy():
    st.markdown(
        "How do the Supreme Court appointees of each president shape American law? "
        "Compare cohorts by voting patterns, ideological influence, and impact across issue areas."
    )

    tab_overview, tab_cohort, tab_influence, tab_bloc, tab_legacy = st.tabs([
        "📊 Overview", "👥 Cohort Analysis", "⚖️ Influence by Issue Area",
        "🤝 Voting Blocs", "🏆 Legacy Score"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: OVERVIEW — Static Gantt + Appointee Summary
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_overview:
        st.subheader("Supreme Court Appointees by President")
        col_color, col_seat = st.columns(2)
        with col_color: color_by = st.radio("Color by", ["Ideology", "Party", "President"], horizontal=True, key="ov_color")
        with col_seat:  seat_filter = st.radio("Seat", ["All", "Chief Justice", "Associate"], horizontal=True, key="ov_seat")

        rows_ov = []
        for name, start, end, pres, party, lean, seat in JUSTICES_DATA:
            if seat_filter != "All" and seat_filter.lower() not in seat.lower(): continue
            rows_ov.append({"Justice": name, "Start": start, "End": end or CURRENT_YEAR,
                             "Duration": (end or CURRENT_YEAR) - start,
                             "President": pres, "Party": party, "Lean": lean, "Seat": seat,
                             "Current": end is None})

        df_ov = pd.DataFrame(rows_ov).sort_values("Start")

        def _ov_color(row):
            if color_by == "Ideology": return LEAN_COLORS.get(row["Lean"], "#95A5A6")
            if color_by == "Party": return PARTY_COLORS.get(row["Party"], "#95A5A6")
            hues = ["#E74C3C","#3498DB","#27AE60","#F39C12","#9B59B6","#1ABC9C","#E67E22","#2ECC71","#E91E63","#00BCD4","#795548","#607D8B","#FF5722","#8BC34A","#673AB7"]
            pres_list = list(dict.fromkeys(row["President"] for _, row in df_ov.iterrows()))
            idx = pres_list.index(row["President"]) if row["President"] in pres_list else 0
            return hues[idx % len(hues)]

        fig_gantt_ov = go.Figure()
        for _, row in df_ov.iterrows():
            color = _ov_color(row)
            border = "#FFD700" if row["Current"] else "white"
            bw = 2 if row["Current"] else 0.5
            fig_gantt_ov.add_trace(go.Bar(
                x=[row["Duration"]], y=[row["Justice"]], base=[row["Start"]],
                orientation="h",
                marker=dict(color=color, opacity=0.88, line=dict(color=border, width=bw)),
                hovertemplate=(f"<b>{row['Justice']}</b><br>Served: {row['Start']} – "
                               f"{'present' if row['Current'] else row['End']}<br>"
                               f"Duration: {row['Duration']} years<br>Appointed by: {row['President']}<br>"
                               f"Lean: {row['Lean']}<extra></extra>"),
                showlegend=False, name=row["Justice"]))

        # President tenure shading
        for pres in PRESIDENTS_ORDER:
            py1, py2 = PRESIDENT_YEARS[pres]
            pp = PRESIDENT_PARTY.get(pres, "R")
            fig_gantt_ov.add_vrect(x0=py1, x1=py2,
                                    fillcolor="rgba(52,152,219,0.05)" if pp=="D" else "rgba(231,76,60,0.05)",
                                    opacity=1, layer="below", line_width=0,
                                    annotation_text=pres, annotation_position="top left",
                                    annotation_font_size=8, annotation_font_color="#7F8C8D")

        # Legend for ideology/party/president
        if color_by == "Ideology":
            for lean, color in LEAN_COLORS.items():
                fig_gantt_ov.add_trace(go.Bar(x=[None], y=[None], marker_color=color, name=lean, showlegend=True))
        elif color_by == "Party":
            fig_gantt_ov.add_trace(go.Bar(x=[None], y=[None], marker_color=PARTY_COLORS["R"], name="Republican", showlegend=True))
            fig_gantt_ov.add_trace(go.Bar(x=[None], y=[None], marker_color=PARTY_COLORS["D"], name="Democrat", showlegend=True))

        fig_gantt_ov.update_layout(
            barmode="overlay",
            height=max(560, len(df_ov) * 20),
            xaxis=dict(title="Year", range=[1937, CURRENT_YEAR + 2], dtick=5, gridcolor="#ECF0F1"),
            yaxis=dict(title="", autorange="reversed"),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=180, r=20, t=30, b=40),
            legend=dict(title="Legend", x=1.01, y=1),
        )
        st.plotly_chart(fig_gantt_ov)
        st.caption("Gold border = currently serving. Shaded bands = presidential terms (blue = Democrat, red = Republican).")

        st.divider()
        st.subheader("Appointee Count & Ideological Breakdown by President")
        pres_rows_ov = []
        for pres in PRESIDENTS_ORDER:
            cohort = _president_cohort(pres)
            if not cohort: continue
            leans = [justice_to_lean[j] for j in cohort]
            pres_rows_ov.append({
                "President": pres, "Party": PRESIDENT_PARTY.get(pres, "?"),
                "Appointees": len(cohort),
                "Conservative": leans.count("Conservative"),
                "Moderate": leans.count("Moderate"),
                "Liberal": leans.count("Liberal"),
            })
        pres_df_ov = pd.DataFrame(pres_rows_ov)
        pres_df_ov["President"] = pd.Categorical(pres_df_ov["President"], categories=PRESIDENTS_ORDER, ordered=True)
        pres_df_ov = pres_df_ov.sort_values("President")

        fig_pres_ov = go.Figure()
        for lean, color in LEAN_COLORS.items():
            fig_pres_ov.add_trace(go.Bar(name=lean, x=pres_df_ov["President"], y=pres_df_ov[lean],
                                          marker_color=color))
        fig_pres_ov.update_layout(barmode="stack", title="Appointees by Ideology & President",
                                   xaxis_tickangle=-30, height=380,
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   legend=dict(x=1.01, y=1))
        st.plotly_chart(fig_pres_ov)

        st.divider()
        st.subheader("Average Tenure by President")
        tenure_rows = []
        for pres in PRESIDENTS_ORDER:
            cohort = _president_cohort(pres)
            if not cohort: continue
            avg_tenure = sum((justice_to_end[j] - justice_to_start[j]) for j in cohort) / len(cohort)
            tenure_rows.append({"President": pres, "Party": PRESIDENT_PARTY.get(pres, "?"),
                                  "Avg Tenure (yrs)": round(avg_tenure, 1), "Appointees": len(cohort)})
        tenure_df = pd.DataFrame(tenure_rows)
        fig_tenure = go.Figure(go.Bar(
            x=tenure_df["President"], y=tenure_df["Avg Tenure (yrs)"],
            marker_color=[PARTY_COLORS.get(p, "#95A5A6") for p in tenure_df["Party"]],
            text=tenure_df["Avg Tenure (yrs)"], textposition="outside",
            hovertemplate="<b>%{x}</b><br>Avg tenure: %{y} years<br>Appointees: %{customdata}<extra></extra>",
            customdata=tenure_df["Appointees"]))
        fig_tenure.update_layout(title="Average Justice Tenure by Appointing President",
                                  xaxis_tickangle=-30, height=360,
                                  plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_tenure)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: COHORT ANALYSIS — Live vote data
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_cohort:
        st.markdown("Compare how each president's court appointees voted across terms. Requires live data from Oyez.")
        available_terms_pl = list(range(CURRENT_YEAR-1, CURRENT_YEAR - 26, -1))

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pres_sel_ca = st.multiselect("Select Presidents", PRESIDENTS_ORDER,
                                          default=["Obama", "Trump", "Biden"], key="ca_pres")
        with col_p2:
            terms_sel_ca = st.multiselect("Terms to analyze", available_terms_pl,
                                           default=available_terms_pl[:8], max_selections=12, key="ca_terms")

        if st.button("Load Voting Data", type="primary", key="ca_load"):
            with st.spinner(f"Fetching vote data for {len(terms_sel_ca)} terms…"):
                vote_rows = _pl_load_vote_data(tuple(sorted(terms_sel_ca, reverse=True)))
            st.session_state["pl_vote_rows"] = vote_rows
            st.session_state["pl_terms_loaded"] = terms_sel_ca

        if "pl_vote_rows" not in st.session_state:
            st.info("Select presidents and terms above, then click **Load Voting Data**.")
        else:
            vote_rows_data = st.session_state["pl_vote_rows"]
            if not vote_rows_data:
                st.warning("No vote data found.")
            else:
                df_votes = pd.DataFrame(vote_rows_data)
                df_votes_filtered = df_votes[df_votes["president"].isin(pres_sel_ca)] if pres_sel_ca else df_votes
                st.success(f"Loaded **{len(df_votes):,}** votes. Showing {len(df_votes_filtered):,} from selected presidents.")

                st.subheader("Majority Rate by President's Cohort")
                cohort_rows = []
                for pres, grp in df_votes_filtered.groupby("president"):
                    total = len(grp)
                    maj   = len(grp[grp["vote"].isin(["majority", "concurrence", "concurring"])])
                    dis   = len(grp[grp["vote"] == "dissent"])
                    cohort_rows.append({"President": pres, "Total Votes": total,
                                         "Majority/Concurrence": maj, "Dissent": dis,
                                         "Majority Rate (%)": round(maj / total * 100, 1) if total else 0,
                                         "Dissent Rate (%)": round(dis / total * 100, 1) if total else 0})
                if cohort_rows:
                    cohort_df = pd.DataFrame(cohort_rows).sort_values("Majority Rate (%)", ascending=False)
                    cohort_df["Party"] = cohort_df["President"].map(PRESIDENT_PARTY)
                    fig_cohort = go.Figure()
                    fig_cohort.add_trace(go.Bar(name="Majority/Concurrence", x=cohort_df["President"],
                                                 y=cohort_df["Majority Rate (%)"],
                                                 marker_color=[PARTY_COLORS.get(p, "#95A5A6") for p in cohort_df["Party"]],
                                                 text=cohort_df["Majority Rate (%)"].apply(lambda v: f"{v:.0f}%"),
                                                 textposition="outside"))
                    fig_cohort.add_trace(go.Bar(name="Dissent", x=cohort_df["President"],
                                                 y=cohort_df["Dissent Rate (%)"],
                                                 marker_color="rgba(150,150,150,0.4)"))
                    fig_cohort.add_hline(y=50, line_dash="dot", line_color="#BDC3C7")
                    fig_cohort.update_layout(barmode="group", title="Majority vs. Dissent Rate by Presidential Cohort",
                                              xaxis_tickangle=-20, height=380,
                                              plot_bgcolor="white", paper_bgcolor="white", legend=dict(x=1.01, y=1))
                    st.plotly_chart(fig_cohort)

                st.subheader("Dissent Rate per Term — Cohort Trend")
                trend_rows_ca = []
                for (pres, term), grp in df_votes_filtered.groupby(["president", "term"]):
                    total = len(grp); dis = len(grp[grp["vote"] == "dissent"])
                    trend_rows_ca.append({"President": pres, "Term": term,
                                           "Dissent Rate (%)": round(dis / total * 100, 1) if total else 0,
                                           "Cases": grp["case"].nunique()})
                if trend_rows_ca:
                    trend_df_ca = pd.DataFrame(trend_rows_ca).sort_values("Term")
                    party_map_ca = {pres: PARTY_COLORS.get(PRESIDENT_PARTY.get(pres, "R"), "#95A5A6") for pres in pres_sel_ca}
                    fig_trend_ca = px.line(trend_df_ca, x="Term", y="Dissent Rate (%)", color="President",
                                           markers=True, title="Cohort Dissent Rate Per Term",
                                           color_discrete_map=party_map_ca)
                    fig_trend_ca.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white")
                    st.plotly_chart(fig_trend_ca)

                st.subheader("Individual Justice Voting Within Cohort")
                for pres in (pres_sel_ca or df_votes_filtered["president"].unique()):
                    pres_df = df_votes_filtered[df_votes_filtered["president"] == pres]
                    if pres_df.empty: continue
                    pcolor = PARTY_COLORS.get(PRESIDENT_PARTY.get(pres, "R"), "#95A5A6")
                    with st.expander(f"**{pres}** ({len(pres_df):,} votes, {pres_df['justice'].nunique()} justices)",
                                      expanded=False):
                        j_rows = []
                        for j, jgrp in pres_df.groupby("justice"):
                            total_j = len(jgrp); maj_j = len(jgrp[jgrp["vote"].isin(["majority","concurrence","concurring"])])
                            dis_j   = len(jgrp[jgrp["vote"] == "dissent"])
                            j_rows.append({"Justice": j, "Total Votes": total_j, "Majority": maj_j, "Dissent": dis_j,
                                            "Majority %": round(maj_j/total_j*100,1) if total_j else 0,
                                            "Dissent %": round(dis_j/total_j*100,1) if total_j else 0})
                        j_df = pd.DataFrame(j_rows).sort_values("Dissent %", ascending=False)
                        fig_j = go.Figure(go.Bar(x=j_df["Justice"], y=j_df["Dissent %"],
                                                 marker_color=pcolor, text=j_df["Dissent %"].apply(lambda v: f"{v:.0f}%"),
                                                 textposition="outside"))
                        fig_j.update_layout(title=f"{pres}'s Appointees — Dissent Rate", height=280,
                                             yaxis=dict(title="Dissent %", range=[0, min(100, j_df["Dissent %"].max() + 15)]),
                                             plot_bgcolor="white", paper_bgcolor="white")
                        st.plotly_chart(fig_j)
                        st.dataframe(j_df.reset_index(drop=True), height=200, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: INFLUENCE BY ISSUE AREA
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_influence:
        st.markdown("Which president's appointees dominated the most critical legal domains?")
        if "pl_vote_rows" not in st.session_state:
            st.info("Load voting data first from the **Cohort Analysis** tab.")
        else:
            df_votes_infl = pd.DataFrame(st.session_state["pl_vote_rows"])
            df_maj_infl   = df_votes_infl[df_votes_infl["vote"].isin(["majority","concurrence","concurring"])]

            st.subheader("Majority Votes by Issue Area — Stacked by Presidential Cohort")
            issue_pres = df_maj_infl.groupby(["issue_area","president"]).size().reset_index(name="count")
            top_issues_infl = issue_pres.groupby("issue_area")["count"].sum().sort_values(ascending=False).head(12).index.tolist()
            issue_pres_filtered = issue_pres[issue_pres["issue_area"].isin(top_issues_infl)]
            fig_ia_infl = px.bar(issue_pres_filtered, x="issue_area", y="count", color="president",
                                  title="Majority Opinions by Issue Area — Contribution by Presidential Cohort",
                                  category_orders={"issue_area": top_issues_infl,
                                                   "president": PRESIDENTS_ORDER},
                                  color_discrete_map={p: PARTY_COLORS.get(PRESIDENT_PARTY.get(p,"R"),"#95A5A6") for p in PRESIDENTS_ORDER})
            fig_ia_infl.update_layout(height=440, plot_bgcolor="white", paper_bgcolor="white",
                                       xaxis_tickangle=-30, barmode="stack",
                                       legend=dict(title="Appointing President", x=1.01, y=1))
            st.plotly_chart(fig_ia_infl)

            st.divider()
            st.subheader("Issue Area Heatmap — Majority Rate by President")
            pres_issue_rows = []
            for (pres, issue), grp in df_votes_infl.groupby(["president","issue_area"]):
                total = len(grp); maj = len(grp[grp["vote"].isin(["majority","concurrence","concurring"])])
                pres_issue_rows.append({"President":pres,"Issue Area":issue,
                                         "Majority Rate":round(maj/total*100,1) if total else 0,
                                         "Votes":total})
            if pres_issue_rows:
                pres_issue_df = pd.DataFrame(pres_issue_rows)
                top_issues_hm = pres_issue_df.groupby("Issue Area")["Votes"].sum().sort_values(ascending=False).head(10).index.tolist()
                pres_issue_hm = pres_issue_df[pres_issue_df["Issue Area"].isin(top_issues_hm)]
                pivot_hm = pres_issue_hm.pivot_table(index="President", columns="Issue Area", values="Majority Rate", aggfunc="mean")
                pivot_hm = pivot_hm.reindex([p for p in PRESIDENTS_ORDER if p in pivot_hm.index])
                fig_hm = go.Figure(go.Heatmap(
                    z=pivot_hm.values.tolist(),
                    x=list(pivot_hm.columns),
                    y=list(pivot_hm.index),
                    text=[[f"{v:.0f}%" if v==v else "" for v in row] for row in pivot_hm.values.tolist()],
                    texttemplate="%{text}",
                    colorscale=[[0.0,"#2C3E50"],[0.45,"#E67E22"],[0.6,"#27AE60"],[1.0,"#1ABC9C"]],
                    zmin=30, zmax=80,
                    colorbar=dict(title="Majority %", ticksuffix="%"),
                    hovertemplate="<b>%{y}</b> in <b>%{x}</b><br>Majority Rate: %{z:.1f}%<extra></extra>",
                ))
                fig_hm.update_layout(
                    title="Cohort Majority Rate — By Issue Area (heatmap)",
                    height=max(300, len(pivot_hm) * 38),
                    xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
                    plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=130, r=60, t=60, b=100),
                )
                st.plotly_chart(fig_hm)
                st.caption("Cells show the fraction of that cohort's votes that were majority/concurrence in the given issue area.")

            st.divider()
            st.subheader("Cross-Ideological Majority Votes")
            st.markdown("When conservative appointees voted with liberal ones — bipartisan majorities.")
            cons_pres = {p for p,party in PRESIDENT_PARTY.items() if party == "R"}
            lib_pres  = {p for p,party in PRESIDENT_PARTY.items() if party == "D"}
            df_maj_all = df_votes_infl[df_votes_infl["vote"].isin(["majority","concurrence","concurring"])]
            cross_rows = []
            for case, case_grp in df_maj_all.groupby("case"):
                pres_in_maj = set(case_grp["president"].tolist())
                if pres_in_maj & cons_pres and pres_in_maj & lib_pres:
                    ia = case_grp["issue_area"].mode()[0] if not case_grp["issue_area"].empty else "Unknown"
                    cross_rows.append({"Case": case, "Issue Area": ia,
                                        "Rep Appointees in Majority": len(case_grp[case_grp["president"].isin(cons_pres)]),
                                        "Dem Appointees in Majority": len(case_grp[case_grp["president"].isin(lib_pres)]),
                                        "Total Majority": len(case_grp)})
            if cross_rows:
                cross_df = pd.DataFrame(cross_rows).sort_values("Total Majority", ascending=False)
                unanimous_n = len(cross_df[cross_df["Total Majority"] >= 9])
                st.info(f"**{len(cross_df)}** cases had cross-party appointees in the majority | **{unanimous_n}** were unanimous.")
                col_left_cx, col_right_cx = st.columns(2)
                with col_left_cx:
                    issue_cx = cross_df["Issue Area"].value_counts().reset_index()
                    issue_cx.columns = ["Issue Area","Count"]
                    fig_cx = px.pie(issue_cx.head(8), names="Issue Area", values="Count",
                                     title="Cross-Party Majority — Issue Areas", hole=0.3)
                    fig_cx.update_layout(height=320)
                    st.plotly_chart(fig_cx)
                with col_right_cx:
                    st.dataframe(cross_df.head(20).reset_index(drop=True),
                                 height=320, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 4: VOTING BLOCS — Who votes together across party lines?
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_bloc:
        st.markdown("Discover which justices from different presidential cohorts vote together most frequently.")
        if "pl_vote_rows" not in st.session_state:
            st.info("Load voting data first from the **Cohort Analysis** tab.")
        else:
            df_votes_bloc = pd.DataFrame(st.session_state["pl_vote_rows"])
            pivot_bloc = df_votes_bloc.pivot_table(index="case", columns="justice", values="vote", aggfunc="first")
            justices_bloc = list(pivot_bloc.columns)

            agree_b: dict[tuple, int] = defaultdict(int)
            total_b: dict[tuple, int] = defaultdict(int)
            for j1 in justices_bloc:
                for j2 in justices_bloc:
                    if j1 >= j2: continue
                    both = pivot_bloc[[j1, j2]].dropna()
                    n = len(both)
                    if n < 3: continue
                    total_b[(j1, j2)] = n
                    agree_b[(j1, j2)] = int((both[j1] == both[j2]).sum())

            mat_data = []
            all_j_b = sorted(set(j for pair in total_b for j in pair))
            for j1 in all_j_b:
                for j2 in all_j_b:
                    if j1 == j2: mat_data.append({"j1": j1, "j2": j2, "agreement": 100.0})
                    else:
                        key = (min(j1, j2), max(j1, j2))
                        pct = round(agree_b[key] / total_b[key] * 100, 1) if key in total_b and total_b[key] > 0 else None
                        mat_data.append({"j1": j1, "j2": j2, "agreement": pct})

            mat_df = pd.DataFrame(mat_data)
            mat_pivot = mat_df.pivot(index="j1", columns="j2", values="agreement")

            fig_bloc_hm = go.Figure(go.Heatmap(
                z=mat_pivot.values.tolist(),
                x=list(mat_pivot.columns),
                y=list(mat_pivot.index),
                text=[[f"{v:.0f}%" if v==v else "—" for v in row] for row in mat_pivot.values.tolist()],
                texttemplate="%{text}",
                colorscale=[[0, "#2C3E50"],[0.5,"#E67E22"],[0.75,"#27AE60"],[1,"#1ABC9C"]],
                zmin=40, zmax=100,
                colorbar=dict(title="Agreement %"),
                hovertemplate="<b>%{y}</b> ↔ <b>%{x}</b><br>Agreement: %{z:.1f}%<extra></extra>",
            ))
            # Annotate each cell with appointing president initial
            fig_bloc_hm.update_layout(
                title="Inter-Justice Agreement — Color-coded by appointment cohort",
                height=max(500, len(all_j_b) * 28),
                xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
                yaxis=dict(tickfont=dict(size=10)),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=140, r=60, t=60, b=120),
            )
            st.plotly_chart(fig_bloc_hm)

            st.subheader("Cross-Cohort Agreement Pairs")
            pair_rows_b = []
            for j1 in all_j_b:
                for j2 in all_j_b:
                    if j1 >= j2: continue
                    p1 = justice_to_president.get(j1, "?"); p2 = justice_to_president.get(j2, "?")
                    if p1 == p2: continue  # skip same-cohort pairs
                    key = (min(j1, j2), max(j1, j2))
                    if key not in total_b or total_b[key] < 5: continue
                    pct = round(agree_b[key] / total_b[key] * 100, 1)
                    pair_rows_b.append({
                        "Justice A": j1, "Appointed by": p1,
                        "Justice B": j2, "Appointed by (B)": p2,
                        "Agreement %": pct, "Cases": total_b[key]
                    })
            if pair_rows_b:
                pair_df_b = pd.DataFrame(pair_rows_b).sort_values("Agreement %", ascending=False)
                pair_df_b["Agreement %"] = pair_df_b["Agreement %"].round(2)
                col_top_b, col_bot_b = st.columns(2)
                with col_top_b:
                    st.markdown("**Most Aligned Cross-Cohort Pairs**")
                    st.dataframe(pair_df_b.head(10).reset_index(drop=True)
                                 .style.background_gradient(subset=["Agreement %"], cmap="Greens")
                                 .format({"Agreement %": "{:.2f}"}),
                                 height=300, hide_index=True)
                with col_bot_b:
                    st.markdown("**Least Aligned Cross-Cohort Pairs**")
                    st.dataframe(pair_df_b.tail(10).sort_values("Agreement %").reset_index(drop=True)
                                 .style.background_gradient(subset=["Agreement %"], cmap="Reds_r")
                                 .format({"Agreement %": "{:.2f}"}),
                                 height=300, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 5: LEGACY SCORE
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_legacy:
        st.markdown(
            "A composite **Presidential Legacy Score** measuring the enduring influence of each president's "
            "Supreme Court appointments based on: total years of service, ideological reach, issue area breadth, "
            "and voting impact."
        )

        legacy_rows = []
        for pres in PRESIDENTS_ORDER:
            cohort = _president_cohort(pres)
            if not cohort: continue
            party = PRESIDENT_PARTY.get(pres, "?")

            total_years = sum(justice_to_end[j] - justice_to_start[j] for j in cohort)
            n_appointees = len(cohort)
            avg_tenure   = total_years / n_appointees if n_appointees else 0

            leans = [justice_to_lean[j] for j in cohort]
            cons = leans.count("Conservative"); lib = leans.count("Liberal"); mod = leans.count("Moderate")
            dom_lean = max(set(leans), key=leans.count) if leans else "Moderate"

            still_serving = sum(1 for j in cohort if justice_to_end[j] == CURRENT_YEAR)

            # Service-years score: log-scale so 1 appointee ≠ 2x score of another
            service_score = min(total_years / 5, 20)  # max 20 pts

            # Appointee count score
            count_score = min(n_appointees * 3, 15)  # max 15 pts

            # Ideological purity score (how many same-lean appointees)
            purity_score = max(cons, lib, mod) / n_appointees * 10 if n_appointees else 0  # max 10 pts

            # Still-serving bonus (current influence)
            active_score = still_serving * 5  # 5 pts per active justice

            # Historical era multiplier (earlier appts have longer track record)
            min_start = min(justice_to_start[j] for j in cohort)
            era_score = max(0, min(15, (CURRENT_YEAR - min_start) / 6))  # max 15 pts

            total_score = service_score + count_score + purity_score + active_score + era_score

            legacy_rows.append({
                "President": pres, "Party": party, "Appointees": n_appointees,
                "Total Service-Years": total_years, "Avg Tenure": round(avg_tenure, 1),
                "Still Serving": still_serving, "Dominant Lean": dom_lean,
                "Conservative": cons, "Liberal": lib, "Moderate": mod,
                "Service Score": round(service_score, 1), "Count Score": round(count_score, 1),
                "Purity Score": round(purity_score, 1), "Active Score": round(active_score, 1),
                "Era Score": round(era_score, 1), "Legacy Score": round(total_score, 1),
            })

        legacy_df = pd.DataFrame(legacy_rows).sort_values("Legacy Score", ascending=False)

        col_ls1, col_ls2, col_ls3 = st.columns(3)
        col_ls1.metric("Most Appointees", legacy_df.loc[legacy_df["Appointees"].idxmax(), "President"],
                       f"{legacy_df['Appointees'].max()} justices")
        col_ls2.metric("Longest Serving Cohort", legacy_df.loc[legacy_df["Total Service-Years"].idxmax(), "President"],
                       f"{legacy_df['Total Service-Years'].max()} yrs combined")
        col_ls3.metric("Highest Legacy Score", legacy_df.iloc[0]["President"],
                       f"{legacy_df.iloc[0]['Legacy Score']:.0f} pts")
        st.divider()

        fig_legacy = go.Figure(go.Bar(
            x=legacy_df["President"], y=legacy_df["Legacy Score"],
            marker_color=[PARTY_COLORS.get(p, "#95A5A6") for p in legacy_df["Party"]],
            text=legacy_df["Legacy Score"].apply(lambda v: f"{v:.0f}"),
            textposition="outside",
            hovertemplate=(
                "<b>%{x}</b><br>Legacy Score: %{y:.1f}<br>"
                "Appointees: %{customdata[0]}<br>Avg Tenure: %{customdata[1]} yrs<br>"
                "Still Serving: %{customdata[2]}<extra></extra>"
            ),
            customdata=list(zip(legacy_df["Appointees"], legacy_df["Avg Tenure"], legacy_df["Still Serving"])),
        ))
        fig_legacy.update_layout(
            title="Presidential Supreme Court Legacy Score",
            yaxis=dict(title="Legacy Score (composite)", range=[0, legacy_df["Legacy Score"].max() * 1.18]),
            xaxis_tickangle=-30, height=420,
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_legacy)
        st.caption("Score = service-years + appointee count + ideological cohesion + currently-serving bonus + historical era. Red = Republican appointees, Blue = Democratic.")

        st.divider()
        st.subheader("Score Breakdown")
        score_cols = ["Service Score", "Count Score", "Purity Score", "Active Score", "Era Score"]
        fig_breakdown = go.Figure()
        colors_breakdown = ["#3498DB","#27AE60","#E67E22","#9B59B6","#E74C3C"]
        for sc, color in zip(score_cols, colors_breakdown):
            fig_breakdown.add_trace(go.Bar(name=sc, x=legacy_df["President"], y=legacy_df[sc],
                                            marker_color=color))
        fig_breakdown.update_layout(barmode="stack", title="Legacy Score Component Breakdown",
                                     xaxis_tickangle=-30, height=400,
                                     plot_bgcolor="white", paper_bgcolor="white",
                                     legend=dict(title="Score Component", x=1.01, y=1))
        st.plotly_chart(fig_breakdown)

        with st.expander("Full Legacy Score Table"):
            display_cols = ["President","Party","Appointees","Total Service-Years","Avg Tenure",
                            "Still Serving","Dominant Lean","Legacy Score"]
            st.dataframe(legacy_df[display_cols].sort_values("Legacy Score", ascending=False)
                         .reset_index(drop=True)
                         .style.background_gradient(subset=["Legacy Score"], cmap="YlOrRd"),
                         height=460, hide_index=True)

        st.divider()
        st.subheader("Ideological Shift Map")
        st.markdown("How much did each president move the court's center of gravity?")
        shift_rows = []
        for pres in PRESIDENTS_ORDER:
            cohort = _president_cohort(pres)
            if not cohort: continue
            leans = [justice_to_lean[j] for j in cohort]
            lean_score = sum({"Conservative": 1, "Moderate": 0, "Liberal": -1}[l] for l in leans) / len(leans)
            shift_rows.append({"President": pres, "Party": PRESIDENT_PARTY.get(pres, "?"),
                                "Lean Score": round(lean_score, 2),
                                "Appointees": len(cohort)})
        shift_df = pd.DataFrame(shift_rows)
        shift_df["President"] = pd.Categorical(shift_df["President"], categories=PRESIDENTS_ORDER, ordered=True)
        shift_df = shift_df.sort_values("President")

        fig_shift = go.Figure()
        fig_shift.add_trace(go.Bar(
            x=shift_df["President"], y=shift_df["Lean Score"],
            marker_color=[PARTY_COLORS.get(p, "#95A5A6") for p in shift_df["Party"]],
            text=shift_df["Lean Score"].apply(lambda v: f"{v:+.2f}"),
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Lean Score: %{y:+.2f}<br>Appointees: %{customdata}<extra></extra>",
            customdata=shift_df["Appointees"]
        ))
        fig_shift.add_hline(y=0, line_dash="solid", line_color="#BDC3C7", line_width=2)
        fig_shift.add_annotation(x=PRESIDENTS_ORDER[-1], y=0.15, text="Conservative ▲", showarrow=False,
                                  font=dict(color=PARTY_COLORS["R"], size=10))
        fig_shift.add_annotation(x=PRESIDENTS_ORDER[-1], y=-0.15, text="Liberal ▼", showarrow=False,
                                  font=dict(color=PARTY_COLORS["D"], size=10))
        fig_shift.update_layout(
            title="Ideological Lean of Appointees (+1 = all Conservative, −1 = all Liberal)",
            xaxis_tickangle=-30, height=380,
            yaxis=dict(title="Lean Score", range=[-1.3, 1.3]),
            plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_shift)

def _page_predictions():

    meta = load_meta()
    model_ready = is_trained()

    if model_ready:
        trained_at     = meta.get("trained_at","?")[:16].replace("T"," ")
        total_cases    = meta.get("total_cases", "?")
        total_votes    = meta.get("total_votes", "?")
        terms_in_data  = meta.get("terms_in_data", [])
        term_range     = f"{min(terms_in_data)}–{max(terms_in_data)}" if terms_in_data else "?"
        out_acc        = meta.get("outcome_accuracy_cv5", None)
        st.success(
            f"✅ **ML model active** — trained on **{total_cases:,} cases** "
            f"({total_votes:,} votes, {term_range} terms)  |  "
            f"5-fold CV accuracy: **{out_acc*100:.1f}%**  |  trained {trained_at}"
        )
    else:
        st.warning("⚠️ ML model not yet trained. Predictions will use the statistical baseline. "
                   "Open **⚙️ Model Training** below to train on real Oyez data.")

    tab_predictor, tab_performance, tab_training, tab_cert, tab_docket = st.tabs([
        "🎯 Case Outcome Predictor", "📈 Model Performance",
        "⚙️ Model Training", "📋 Cert Grant Predictor", "🔴 Docket Watch",
    ])

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 1: CASE OUTCOME PREDICTOR
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_predictor:
        source_badge = ("🤖 **ML model**" if model_ready else "📊 **Statistical baseline**")
        st.markdown(f"Using {source_badge}. Enter case characteristics to generate a prediction.")
        if not model_ready:
            st.info("Train the ML model in the **⚙️ Model Training** tab for higher accuracy predictions.")

        with st.form("predictor_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                circuit_sel    = st.selectbox("Circuit of Origin", CIRCUIT_OPTIONS, index=8)
                issue_area_sel = st.selectbox("Issue Area", ISSUE_OPTIONS, index=0)
            with col2:
                pet_type_sel   = st.selectbox("Petitioner Type", PETITIONER_TYPES, index=0)
                sg_support     = st.checkbox("Solicitor General Supporting Petitioner")
            with col3:
                circuit_split  = st.checkbox("Circuit Split Exists")
                n_cons         = st.slider("Conservative Justices on Court", 4, 7, 6)
                case_name_inp  = st.text_input("Case Name (optional)", placeholder="e.g. Smith v. Jones")
            submitted = st.form_submit_button("Generate Prediction →", type="primary")

        if submitted:
            if model_ready:
                try:
                    result = predict(
                        circuit=circuit_sel, issue_area=issue_area_sel,
                        n_conservative=n_cons, term_year=CURRENT_YEAR,
                        sg_support=sg_support, circuit_split=circuit_split,
                    )
                    result["source"] = "ml"
                except Exception as e:
                    st.warning(f"ML model error ({e}). Falling back to statistical baseline.")
                    result = _static_predict(circuit_sel, issue_area_sel, pet_type_sel,
                                             sg_support, circuit_split, n_cons)
            else:
                result = _static_predict(circuit_sel, issue_area_sel, pet_type_sel,
                                         sg_support, circuit_split, n_cons)
            st.session_state["pred_result"] = result
            st.session_state["pred_inputs"] = (circuit_sel, issue_area_sel, pet_type_sel,
                                                sg_support, circuit_split, n_cons, case_name_inp)

        if "pred_result" in st.session_state:
            result = st.session_state["pred_result"]
            inputs = st.session_state.get("pred_inputs", ())
            c_sel, ia_sel, pt_sel, sg_sel, cs_sel, nc_sel, cn_inp = inputs

            p_rev = result["p_reverse"]; p_aff = result["p_affirm"]
            if   p_rev > 0.66: verdict_label, verdict_color = "🔴 LIKELY REVERSED",   "#E74C3C"
            elif p_rev > 0.54: verdict_label, verdict_color = "🟠 LEAN REVERSE",       "#E67E22"
            elif p_aff > 0.66: verdict_label, verdict_color = "🟢 LIKELY AFFIRMED",    "#27AE60"
            elif p_aff > 0.54: verdict_label, verdict_color = "🟡 LEAN AFFIRM",        "#F39C12"
            else:               verdict_label, verdict_color = "⚖️ TOSS-UP",            "#9B59B6"

            src_label  = "ML Model" if result.get("source") == "ml" else "Statistical Baseline"
            case_title = cn_inp if cn_inp else f"{c_sel} → {ia_sel} case"

            st.markdown(
                f'<div style="background:{verdict_color}18;border-left:5px solid {verdict_color};'
                f'padding:16px 20px;border-radius:6px;margin:12px 0;">'
                f'<span style="font-size:1.35em;font-weight:bold;color:{verdict_color};">{verdict_label}</span>'
                f'<span style="color:#555;margin-left:16px;">{case_title}</span>'
                f'<span style="float:right;font-size:0.8em;color:#888;background:#f0f0f0;'
                f'padding:2px 8px;border-radius:3px;">{src_label}</span></div>',
                unsafe_allow_html=True)

            col_gauge, col_split_chart, col_factors = st.columns(3)

            with col_gauge:
                fig_g = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=round(p_rev*100,1),
                    title={"text":"Reversal Probability","font":{"size":13}},
                    number={"suffix":"%","font":{"size":26}},
                    delta={"reference":50,"valueformat":".1f","suffix":"% vs 50%"},
                    gauge={
                        "axis":{"range":[0,100],"ticksuffix":"%"},
                        "bar":{"color":verdict_color},
                        "steps":[{"range":[0,45],"color":"#D5F5E3"},
                                  {"range":[45,55],"color":"#FCF3CF"},
                                  {"range":[55,100],"color":"#FADBD8"}],
                        "threshold":{"line":{"color":"#2C3E50","width":3},"thickness":0.75,"value":50},
                    }))
                fig_g.update_layout(height=250,margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig_g)

            with col_split_chart:
                split_d  = result["split_probs"]
                split_df = pd.DataFrame(list(split_d.items()), columns=["Split","Prob"])
                split_df["Prob %"] = (split_df["Prob"]*100).round(1)
                split_label_pred   = result["split_label"]
                bar_colors = ["#27AE60" if s==split_label_pred else "#BDC3C7" for s in split_df["Split"]]
                fig_sp = go.Figure(go.Bar(
                    x=split_df["Split"], y=split_df["Prob %"],
                    marker_color=bar_colors,
                    text=split_df["Prob %"].apply(lambda v: f"{v:.0f}%"),
                    textposition="outside"))
                fig_sp.update_layout(
                    title=f"Most Likely Split: {split_label_pred}",
                    yaxis=dict(title="Probability %",range=[0,65]),
                    height=250,plot_bgcolor="white",paper_bgcolor="white",
                    margin=dict(l=20,r=20,t=40,b=40))
                st.plotly_chart(fig_sp)

            with col_factors:
                st.markdown("**Input Summary**")
                factors = [
                    (f"{c_sel}", CIRCUIT_REVERSAL_RATES.get(c_sel,0.62)*100, "#3498DB"),
                    (f"{ia_sel}", ISSUE_REVERSAL_RATES.get(ia_sel,0.62)*100, "#9B59B6"),
                    ("SG Support", (60 if sg_sel else 50), "#E67E22"),
                    ("Circuit Split", (58 if cs_sel else 50), "#27AE60"),
                    (f"{nc_sel} conservatives", 50 + (nc_sel-5)*2.5, "#E74C3C"),
                ]
                for label, val, color in factors:
                    st.markdown(
                        f'<div style="margin:4px 0;">'
                        f'<span style="font-size:0.82em;color:#555;">{label}</span><br>'
                        f'<div style="background:#ECF0F1;border-radius:4px;height:14px;margin-top:2px;">'
                        f'<div style="background:{color};width:{min(val,100):.0f}%;height:100%;border-radius:4px;"></div></div>'
                        f'<span style="font-size:0.8em;color:{color};">{val:.0f}%</span></div>',
                        unsafe_allow_html=True)

            st.divider()
            # Per-justice section
            st.subheader("Per-Justice Vote Probabilities")
            direction = "Reverse" if p_rev > 0.5 else "Affirm"
            st.caption(f"Probability each justice votes with the predicted {direction} majority.")
            justice_probs = result.get("justice_probs", {})

            j_cols = st.columns(3)
            for i, j in enumerate(CURRENT_JUSTICES_DISPLAY):
                sh = j["short"]
                prob = justice_probs.get(sh, 0.5)
                lean_color = LEAN_COLORS[j["lean"]]
                if   prob > 0.65: badge = "✅ Likely Majority";  bar_c = lean_color
                elif prob < 0.35: badge = "❌ Likely Dissent";   bar_c = "#95A5A6"
                else:             badge = "🤔 Uncertain";        bar_c = "#BDC3C7"
                with j_cols[i % 3]:
                    st.markdown(
                        f'<div style="border:1px solid #E0E0E0;border-radius:6px;padding:10px;margin:4px 0;">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<span style="font-weight:bold;font-size:0.95em;">{sh}</span>'
                        f'<span style="color:{lean_color};font-size:0.78em;">{j["lean"]}</span></div>'
                        f'<div style="background:#ECF0F1;border-radius:4px;height:10px;margin:5px 0;">'
                        f'<div style="background:{bar_c};width:{prob*100:.0f}%;height:100%;border-radius:4px;"></div></div>'
                        f'<div style="font-size:0.82em;color:#555;display:flex;justify-content:space-between;">'
                        f'<span>P({direction}): <b>{prob*100:.0f}%</b></span>'
                        f'<span>{badge}</span></div></div>',
                        unsafe_allow_html=True)

            st.divider()
            # Bench diagram
            st.subheader("Court Bench — Predicted Alignment")
            bench = sorted(
                [(j["short"], justice_probs.get(j["short"],0.5), j["lean"])
                 for j in CURRENT_JUSTICES_DISPLAY],
                key=lambda x: -x[1])
            fig_bench = go.Figure()
            fig_bench.add_trace(go.Scatter(
                x=list(range(9)), y=[1]*9,
                mode="markers+text",
                marker=dict(
                    size=[40+int(p*20) for _,p,_ in bench],
                    color=[LEAN_COLORS[lean] for _,_,lean in bench],
                    opacity=[0.9 if p>0.5 else 0.35 for _,p,_ in bench],
                    line=dict(color="white",width=2),
                    symbol=["circle" if p>0.5 else "x" for _,p,_ in bench]),
                text=[f"{sh}<br>{int(p*100)}%" for sh,p,_ in bench],
                textposition="bottom center",
                textfont=dict(size=13, color="#222"),
                hovertemplate="%{text}<extra></extra>"))
            fig_bench.update_layout(
                title=f"Predicted to {direction} (filled circle = majority, ✕ = dissent)",
                height=300,showlegend=False,
                xaxis=dict(showticklabels=False,showgrid=False,zeroline=False,range=[-0.5,8.5]),
                yaxis=dict(showticklabels=False,showgrid=False,zeroline=False,range=[0.3,1.7]),
                plot_bgcolor="white",paper_bgcolor="white",
                margin=dict(l=20,r=20,t=50,b=90))
            st.plotly_chart(fig_bench)

            # Historical circuit context
            st.divider()
            st.subheader("Historical Context")
            all_circs = sorted(CIRCUIT_REVERSAL_RATES.items(), key=lambda x: -x[1])
            hist_df   = pd.DataFrame(all_circs, columns=["Circuit","Reversal Rate"])
            fig_hist = go.Figure(go.Bar(
                x=hist_df["Circuit"], y=(hist_df["Reversal Rate"]*100).round(1),
                marker_color=["#E74C3C" if c==c_sel else "#BDC3C7" for c in hist_df["Circuit"]],
                text=(hist_df["Reversal Rate"]*100).round(0).astype(int).astype(str)+"%",
                textposition="outside"))
            fig_hist.update_layout(
                title="Historical Reversal Rate by Circuit (1990–2024)",
                xaxis_tickangle=-30, height=320,
                yaxis=dict(title="Reversal %",range=[0,100]),
                plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_hist)

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 2: MODEL PERFORMANCE
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_performance:
        if not model_ready:
            st.info("No trained model yet. Go to **⚙️ Model Training** to train one.")
        else:
            st.subheader("Model Performance Summary")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Outcome Accuracy (5-fold CV)", f"{meta.get('outcome_accuracy_cv5',0)*100:.1f}%")
            c2.metric("Outcome Accuracy (hold-out)", f"{meta.get('outcome_accuracy_holdout',0)*100:.1f}%")
            c3.metric("Vote-Split Accuracy (hold-out)", f"{meta.get('split_accuracy_holdout',0)*100:.1f}%")
            c4.metric("Training Cases", f"{meta.get('total_cases',0):,}")
            st.caption(
                f"Hold-out = last 2 terms ({', '.join(str(t) for t in meta.get('test_terms',[]))}).  "
                f"Baseline (always predict Reverse): ~62%."
            )
            st.divider()

            # Per-justice performance
            j_results = meta.get("justice_results", {})
            if j_results:
                st.subheader("Per-Justice Model Accuracy")
                j_rows = [{"Justice": j, "Accuracy": v.get("accuracy"), "Training Votes": v.get("n",0)}
                          for j, v in j_results.items() if v.get("accuracy") is not None]
                j_perf_df = pd.DataFrame(j_rows).sort_values("Accuracy", ascending=False)
                if not j_perf_df.empty:
                    fig_jp = go.Figure(go.Bar(
                        x=j_perf_df["Justice"],
                        y=(j_perf_df["Accuracy"]*100).round(1),
                        marker_color=["#27AE60" if a>0.65 else "#F39C12" if a>0.55 else "#E74C3C"
                                      for a in j_perf_df["Accuracy"]],
                        text=(j_perf_df["Accuracy"]*100).round(1).astype(str)+"%",
                        textposition="outside",
                        customdata=j_perf_df["Training Votes"],
                        hovertemplate="<b>%{x}</b><br>Accuracy: %{y:.1f}%<br>Training votes: %{customdata}<extra></extra>"))
                    fig_jp.add_hline(y=50, line_dash="dot", line_color="#BDC3C7", annotation_text="Coin flip")
                    fig_jp.update_layout(
                        title="Per-Justice Classifier Accuracy (hold-out set)",
                        yaxis=dict(title="Accuracy %", range=[0,100]),
                        height=360, plot_bgcolor="white", paper_bgcolor="white")
                    st.plotly_chart(fig_jp)
                    st.dataframe(j_perf_df.reset_index(drop=True)
                                 .style.format({"Accuracy":"{:.1%}","Training Votes":"{:,}"})
                                 .background_gradient(subset=["Accuracy"],cmap="RdYlGn"),
                                 height=300, hide_index=True)

            st.divider()
            # Feature importances
            fi = meta.get("feature_importances", {})
            if fi:
                st.subheader("Feature Importances — Outcome Model")
                fi_df = pd.DataFrame(list(fi.items()), columns=["Feature","Importance"])
                fi_df = fi_df.sort_values("Importance", ascending=False).head(20)
                # Shorten one-hot names
                fi_df["Feature"] = fi_df["Feature"].str.replace("cat__","").str.replace("num__","")
                fig_fi = go.Figure(go.Bar(
                    y=fi_df["Feature"], x=fi_df["Importance"],
                    orientation="h", marker_color="#3498DB",
                    text=fi_df["Importance"].apply(lambda v: f"{v:.3f}"),
                    textposition="outside"))
                fig_fi.update_layout(
                    title="Top 20 Feature Importances (Gradient Boosting)",
                    height=500, plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=200,r=60,t=40,b=40),
                    xaxis_title="Importance")
                st.plotly_chart(fig_fi)

            st.divider()
            # Outcome classification report
            oc_report = meta.get("outcome_report", {})
            if oc_report:
                st.subheader("Outcome Model — Classification Report (hold-out)")
                report_rows = []
                for cls_key in ["0","1"]:
                    if cls_key in oc_report:
                        r = oc_report[cls_key]
                        report_rows.append({
                            "Class": "Affirmed (0)" if cls_key=="0" else "Reversed (1)",
                            "Precision": round(r.get("precision",0)*100,1),
                            "Recall": round(r.get("recall",0)*100,1),
                            "F1-Score": round(r.get("f1-score",0)*100,1),
                            "Support": int(r.get("support",0)),
                        })
                if report_rows:
                    rep_df = pd.DataFrame(report_rows)
                    st.dataframe(rep_df.style.format({"Precision":"{:.1f}%","Recall":"{:.1f}%","F1-Score":"{:.1f}%"})
                                 .background_gradient(subset=["F1-Score"],cmap="RdYlGn"),
                                 hide_index=True)

            st.divider()
            # Training data stats
            st.subheader("Training Data")
            terms_list = meta.get("terms_in_data", [])
            col_td1, col_td2, col_td3, col_td4 = st.columns(4)
            col_td1.metric("Terms covered", len(terms_list))
            col_td2.metric("Term range", f"{min(terms_list)}–{max(terms_list)}" if terms_list else "—")
            col_td3.metric("Total votes", f"{meta.get('total_votes',0):,}")
            col_td4.metric("Trained at", meta.get("trained_at","?")[:10])

            if CACHE_CSV.exists():
                if st.button("Show training data sample"):
                    try:
                        sample = pd.read_csv(CACHE_CSV).head(100)
                        st.dataframe(sample, height=300, hide_index=True)
                    except Exception as e:
                        st.error(str(e))

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 3: MODEL TRAINING
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_training:
        st.markdown(
            "Train the ML prediction model on historical SCOTUS data from the Oyez API. "
            "Data is cached locally after the first fetch — retraining is fast."
        )

        avail_terms = list(range(2023, 1999, -1))

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            train_terms = st.multiselect(
                "Terms to include in training data",
                avail_terms,
                default=avail_terms[:18],
                format_func=lambda t: f"{t}–{t+1}",
                help="More terms = more data = better accuracy, but slower fetch. 15–20 terms is a good starting point.",
                key="train_terms_sel",
            )
            st.caption(f"Selected: {len(train_terms)} terms. "
                       f"Estimated cases: ~{len(train_terms)*70:,}. "
                       f"Fetch time (first run): ~{len(train_terms)*50//60+1} min.")
        with col_t2:
            cached_terms_info = ""
            if CACHE_CSV.exists():
                try:
                    cached_df = pd.read_csv(CACHE_CSV)
                    cached_ts = sorted(cached_df["term"].unique().astype(int))
                    cached_terms_info = (f"**{len(cached_ts)} terms already cached** "
                                         f"({min(cached_ts)}–{max(cached_ts)}, "
                                         f"{len(cached_df):,} rows). "
                                         f"Only missing terms will be fetched.")
                except Exception:
                    pass
            if cached_terms_info:
                st.info(cached_terms_info)
            else:
                st.info("No cached data yet. First run will fetch from Oyez API.")

            clear_cache = st.checkbox("Clear cached data and re-fetch everything", value=False)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            fetch_btn = st.button("Step 1: Collect Training Data", type="primary",
                                  disabled=not train_terms)
        with col_btn2:
            train_btn = st.button("Step 2: Train Models",
                                  disabled=not (CACHE_CSV.exists() or "training_df" in st.session_state))

        # ── Data collection ───────────────────────────────────────────────────────
        if fetch_btn:
            if clear_cache and CACHE_CSV.exists():
                CACHE_CSV.unlink()
                st.toast("Cache cleared.")

            progress_bar  = st.progress(0.0, text="Starting data collection…")
            status_text   = st.empty()
            rows_count    = st.empty()

            def _progress(done, total, msg):
                pct = done / total if total else 0
                progress_bar.progress(pct, text=msg)
                status_text.markdown(f"*{msg}*")

            with st.spinner("Fetching SCOTUS case data from Oyez…"):
                try:
                    df_train = collect_training_data(
                        terms=sorted(train_terms, reverse=True),
                        progress_cb=_progress,
                    )
                    st.session_state["training_df"] = df_train
                    progress_bar.progress(1.0, text="Data collection complete!")
                    n_cases  = df_train["docket"].nunique() if not df_train.empty else 0
                    n_votes  = len(df_train)
                    n_terms  = df_train["term"].nunique() if not df_train.empty else 0
                    st.success(
                        f"✅ Collected **{n_cases:,} cases**, **{n_votes:,} justice votes** "
                        f"across **{n_terms}** terms."
                    )
                    rows_count.dataframe(
                        df_train.groupby("term").agg(
                            cases=("docket","nunique"),
                            votes=("justice","count"),
                        ).reset_index().sort_values("term",ascending=False).head(10)
                        .rename(columns={"term":"Term","cases":"Cases","votes":"Votes"})
                        if not df_train.empty else pd.DataFrame(columns=["Term","Cases","Votes"]),
                        height=250, hide_index=True,
                    )
                except Exception as e:
                    st.error(f"Data collection failed: {e}")

        # ── Model training ────────────────────────────────────────────────────────
        if train_btn:
            df_for_train = st.session_state.get("training_df", None)
            if df_for_train is None and CACHE_CSV.exists():
                try:
                    df_for_train = pd.read_csv(CACHE_CSV)
                except Exception:
                    df_for_train = None

            if df_for_train is None or df_for_train.empty:
                st.error("No training data found. Run Step 1 first.")
            else:
                st.info(f"Training on {len(df_for_train):,} vote rows from {df_for_train['term'].nunique()} terms…")
                train_progress = st.progress(0.0)
                train_status   = st.empty()

                def _train_progress(done, total, msg):
                    pct = (done+1) / (total+1)
                    train_progress.progress(pct, text=msg)
                    train_status.markdown(f"*{msg}*")

                with st.spinner("Training ML models — this takes ~30–60 seconds…"):
                    try:
                        results = train_models(df_for_train, progress_cb=_train_progress)
                        train_progress.progress(1.0, text="Training complete!")
                        train_status.empty()

                        out_cv   = results.get("outcome_accuracy_cv5", 0)
                        out_hold = results.get("outcome_accuracy_holdout", 0)
                        spl_hold = results.get("split_accuracy_holdout", 0)
                        j_res    = results.get("justice_results", {})
                        j_with_acc = [(j,v["accuracy"]) for j,v in j_res.items() if v.get("accuracy")]

                        st.success(
                            f"✅ **Models trained successfully!**  "
                            f"Outcome CV accuracy: **{out_cv*100:.1f}%** | "
                            f"Hold-out: **{out_hold*100:.1f}%** | "
                            f"Split hold-out: **{spl_hold*100:.1f}%** | "
                            f"Per-justice models: **{len(j_with_acc)}** justices"
                        )
                        st.balloons()

                        # Summary table
                        sum_rows = [
                            {"Model":"Outcome (Affirm/Reverse)","Type":"GradientBoosting + Calibration",
                             "CV Accuracy":f"{out_cv*100:.1f}%","Hold-out Accuracy":f"{out_hold*100:.1f}%","Classes":"2"},
                            {"Model":"Vote Split","Type":"GradientBoosting + Calibration",
                             "CV Accuracy":"—","Hold-out Accuracy":f"{spl_hold*100:.1f}%","Classes":"5"},
                        ]
                        for j, acc in sorted(j_with_acc, key=lambda x: -x[1]):
                            sum_rows.append({
                                "Model":f"Justice: {j}","Type":"LogisticRegression + Calibration",
                                "CV Accuracy":"—","Hold-out Accuracy":f"{acc*100:.1f}%","Classes":"2",
                            })
                        st.dataframe(pd.DataFrame(sum_rows), hide_index=True)
                        st.markdown("**Reload the page to activate the trained model.**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Training failed: {e}")
                        import traceback; st.code(traceback.format_exc())

        # ── Architecture description ──────────────────────────────────────────────
        with st.expander("📐 Model Architecture Details"):
            st.markdown("""
    **Data pipeline**
    - Source: Oyez API (`/cases?filter=term:YYYY`) — free, no API key
    - Features extracted per case: circuit of origin, issue area, term year, conservative bench count
    - Labels: binary outcome (0=Affirm, 1=Reverse), vote split (5-4/6-3/7-2/8-1/9-0), per-justice majority indicator
    - Temporal train/test split: held-out last 2 terms to prevent leakage

    **Feature engineering**
    | Feature | Type | Encoding |
    |---|---|---|
    | `circuit` | Categorical (15) | OneHotEncoder |
    | `issue_area` | Categorical (14) | OneHotEncoder |
    | `n_conservative` | Numeric | StandardScaler |
    | `term_year_norm` | Numeric (centered on 2005) | StandardScaler |

    **Models**
    | Model | Algorithm | Notes |
    |---|---|---|
    | Outcome | `GradientBoostingClassifier` (150 trees, depth 3) | Calibrated with Platt scaling |
    | Vote Split | `GradientBoostingClassifier` (150 trees, depth 3) | 5-class multiclass |
    | Per-Justice (×9) | `LogisticRegression` (C=0.8) | One per current justice |

    **Calibration**: `CalibratedClassifierCV(method="sigmoid", cv="prefit")` ensures probabilities are reliable.

    **Post-hoc adjustments** (not in features, applied after model):
    - SG support: +7pp reversal probability
    - Circuit split: +5pp reversal probability
            """)

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 4: CERT GRANT PREDICTOR
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_cert:
        st.markdown(
            "The Supreme Court grants cert in about **1–2%** of ~10,000 annual petitions. "
            "Estimate whether a petition will be accepted based on key factors."
        )
        with st.form("cert_form"):
            c1_cf, c2_cf = st.columns(2)
            with c1_cf:
                cert_circuit = st.selectbox("Circuit of Origin", CIRCUIT_OPTIONS, key="cert_circuit")
                cert_issue   = st.selectbox("Issue Area", ISSUE_OPTIONS, key="cert_issue")
            with c2_cf:
                cert_sg     = st.checkbox("Solicitor General is Petitioner or Supports Grant")
                cert_split  = st.checkbox("Circuit Split Exists")
                cert_cvsg   = st.checkbox("CVSG (Court invited SG view)")
                cert_flaw   = st.checkbox("Lower Court Struck Down Federal Law")
            extra_factors = st.multiselect("Additional Favorable Factors", list(CERT_FACTORS.keys()))
            cert_sub = st.form_submit_button("Estimate Cert Probability", type="primary")

        if cert_sub:
            base  = ISSUE_CERT_RATES.get(cert_issue, 0.015)
            mult  = CIRCUIT_CERT_MULT.get(cert_circuit, 1.0)
            if cert_sg:    base += 0.038
            if cert_split: base += 0.045
            if cert_cvsg:  base += 0.060
            if cert_flaw:  base += 0.040
            for f in extra_factors: base += CERT_FACTORS.get(f, 0)
            cp = max(0.005, min(0.85, base * mult))

            if   cp < 0.05: cv, cc = "🔴 Very Unlikely", "#E74C3C"
            elif cp < 0.10: cv, cc = "🟠 Unlikely",       "#E67E22"
            elif cp < 0.20: cv, cc = "🟡 Possible",        "#F39C12"
            elif cp < 0.40: cv, cc = "🟢 Likely",          "#27AE60"
            else:           cv, cc = "🟢 Very Likely",     "#1ABC9C"

            st.markdown(
                f'<div style="background:{cc}18;border-left:5px solid {cc};padding:16px 20px;border-radius:6px;">'
                f'<span style="font-size:1.2em;font-weight:bold;color:{cc};">{cv}</span><br>'
                f'<span style="font-size:2em;color:{cc};font-weight:bold;">{cp*100:.1f}%</span>'
                f' <span style="color:#888;">cert grant probability</span></div>',
                unsafe_allow_html=True)

            c1_cm, c2_cm = st.columns([1, 2])
            with c1_cm:
                st.metric("Estimated Probability", f"{cp*100:.1f}%")
                st.metric("Base rate (all petitions)", "1.5%")
                st.metric("Circuit multiplier", f"{mult:.1f}×")
            with c2_cm:
                fig_cg = go.Figure(go.Indicator(
                    mode="gauge+number", value=round(cp*100,1),
                    number={"suffix":"%","font":{"size":36}},
                    title={"text":"Cert Grant Probability","font":{"size":14}},
                    gauge={"axis":{"range":[0,85]},
                           "bar":{"color":cc},
                           "steps":[{"range":[0,5],"color":"#FADBD8"},
                                     {"range":[5,15],"color":"#FDEBD0"},
                                     {"range":[15,85],"color":"#D5F5E3"}],
                           "threshold":{"line":{"color":"#E74C3C","width":2},"thickness":0.75,"value":5}}))
                fig_cg.update_layout(height=300, margin=dict(l=30,r=30,t=50,b=20))
                st.plotly_chart(fig_cg, use_container_width=True)

            st.divider()
            issue_cert_df = pd.DataFrame(list(ISSUE_CERT_RATES.items()), columns=["Issue","Rate"])
            fig_ir = go.Figure(go.Bar(
                x=issue_cert_df["Issue"],
                y=(issue_cert_df["Rate"]*100).round(2),
                marker_color=["#E67E22" if i==cert_issue else "#BDC3C7" for i in issue_cert_df["Issue"]],
                text=(issue_cert_df["Rate"]*100).apply(lambda v: f"{v:.1f}%"),
                textposition="outside"))
            fig_ir.update_layout(title="Baseline Cert Rate by Issue Area",xaxis_tickangle=-30,
                                  height=320,yaxis_title="Base Rate (%)",
                                  plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_ir)

    # ══════════════════════════════════════════════════════════════════════════════
    # TAB 5: DOCKET WATCH
    # ══════════════════════════════════════════════════════════════════════════════
    with tab_docket:
        st.markdown(f"**Live tracker** for the **{CURRENT_TERM}–{CURRENT_TERM+1} SCOTUS Term.**")
        col_rf, col_inf = st.columns([1,3])
        with col_rf:
            if st.button("🔄 Refresh", type="primary"):
                st.cache_data.clear(); st.rerun()
        with col_inf:
            st.caption(f"Last checked: {datetime.datetime.now().strftime('%B %d, %Y %H:%M')}")

        with st.spinner("Loading current term docket…"):
            docket_cases = _pred_fetch_term(CURRENT_TERM)

        if not docket_cases:
            st.error("Could not load term from Oyez.")
        else:
            decided = sum(1 for c in docket_cases if c.get("decided_on"))
            total   = len(docket_cases)
            m1,m2,m3,m4 = st.columns(4)
            m1.metric("Total Cases", total)
            m2.metric("✅ Decided", decided)
            m3.metric("⏳ Pending", total-decided)
            m4.metric("Term Progress", f"{decided/total*100:.0f}%" if total else "0%")
            st.progress(decided/total if total else 0)
            st.divider()

            col_f1,col_f2 = st.columns(2)
            with col_f1: status_f = st.selectbox("Status", ["All","Decided","Pending"], key="dw_sf")
            with col_f2: search_f = st.text_input("Search", placeholder="EPA, gun, Trump…", key="dw_ss")

            dw_rows = []
            for c in docket_cases:
                issue = infer_issue_area(c) if (c.get("question") or c.get("description")) else "Unknown"
                dd = _parse_date(c.get("decided_on"))
                status = "Decided" if dd else "Pending"
                href   = c.get("href","")
                oyez_url = href.replace("api.oyez.org/cases","www.oyez.org/cases") if href else ""
                dw_rows.append({"name":c.get("name",""),"issue":issue,"status":status,
                                 "decided":dd,"oyez_url":oyez_url})

            disp = dw_rows
            if status_f == "Decided":   disp = [r for r in disp if r["status"]=="Decided"]
            elif status_f == "Pending": disp = [r for r in disp if r["status"]=="Pending"]
            if search_f: disp = [r for r in disp if search_f.lower() in r["name"].lower()]
            disp = sorted(disp, key=lambda x: (x["status"]=="Pending", x["name"]))

            STATUS_COLORS = {"Decided":"#27AE60","Pending":"#E67E22"}
            cols_dw = st.columns(2)
            for i, row in enumerate(disp):
                sc = STATUS_COLORS.get(row["status"],"#95A5A6")
                icon = "✅" if row["status"]=="Decided" else "⏳"
                link = f' · <a href="{row["oyez_url"]}" target="_blank">Oyez ↗</a>' if row["oyez_url"] else ""
                with cols_dw[i%2]:
                    st.markdown(
                        f'<div style="border:1px solid #E8E8E8;border-left:4px solid {sc};'
                        f'border-radius:6px;padding:10px 14px;margin:4px 0;">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<span style="font-weight:bold;font-size:0.9em;">{icon} {row["name"][:55]}{"…" if len(row["name"])>55 else ""}</span>'
                        f'<span style="background:{sc};color:white;padding:1px 6px;border-radius:3px;font-size:0.75em;">{row["status"]}</span></div>'
                        f'<div style="font-size:0.8em;color:#666;margin-top:3px;">📁 {row["issue"]}'
                        f'{" · " + str(row["decided"]) if row["decided"] else ""}{link}</div></div>',
                        unsafe_allow_html=True)

            st.divider()
            st.subheader("Issue Area Breakdown — Current Term")
            ic = defaultdict(int)
            for r in dw_rows: ic[r["issue"]] += 1
            ic_df = pd.DataFrame(list(ic.items()), columns=["Issue","Count"]).sort_values("Count",ascending=False)
            fig_ic = go.Figure(go.Bar(x=ic_df["Issue"],y=ic_df["Count"],marker_color="#3498DB",
                                       text=ic_df["Count"],textposition="outside"))
            fig_ic.update_layout(title=f"{CURRENT_TERM}–{CURRENT_TERM+1} Term Cases by Issue Area",
                                  xaxis_tickangle=-30,height=320,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_ic)

# ── Page ─────────────────────────────────────────────────────────────────────
_tab_0, _tab_1 = st.tabs(["🎖️ Presidential Legacy", "🔮 Predictions"])
with _tab_0:
    _page_presidential_legacy()
with _tab_1:
    _page_predictions()
