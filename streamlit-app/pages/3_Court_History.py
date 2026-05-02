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

st.set_page_config(page_title="Court History Hub", page_icon="🏛️", layout="wide")

HEADERS      = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Shared fetch ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _ch_fetch_cases_term(term: int) -> list[dict]:
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

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
st.title("🏛️ Court History")
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
        st.plotly_chart(fig_gantt, use_container_width=True)
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
            st.plotly_chart(fig_donut, use_container_width=True)
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
        st.plotly_chart(fig_balance, use_container_width=True)
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
        st.info("Loading era data pulls many terms from Oyez — expect 20–60 seconds per era. Results are cached.")
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
            st.plotly_chart(fig_vol, use_container_width=True)
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
                st.plotly_chart(fig_issue_era, use_container_width=True)
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
                st.plotly_chart(fig_disp_era, use_container_width=True)
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
                st.plotly_chart(fig_time_era, use_container_width=True)

            with st.expander("Browse raw case data by era"):
                era_tab_names = list(era_frames.keys())
                era_tabs_inner = st.tabs(era_tab_names)
                for etab, era in zip(era_tabs_inner, era_tab_names):
                    with etab:
                        st.dataframe(era_frames[era][["Term","Case","Issue Area","Disposition"]]
                                     .sort_values("Term",ascending=False), use_container_width=True, height=350)

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
        st.plotly_chart(fig_conf, use_container_width=True)
        st.caption("Dot size scales with yes-vote count. ★ = seat changed ideological lean.")

    with ctab_votes:
        vote_df_c = conf_df.dropna(subset=["yes"]).sort_values("yes",ascending=False).copy()
        col_top, col_bot = st.columns(2)
        with col_top:
            st.markdown("**Most Unanimous**")
            st.dataframe(vote_df_c.head(10)[["name","conf_year","yes","no","nominated_by"]].reset_index(drop=True),
                         use_container_width=True,height=320,hide_index=True)
        with col_bot:
            st.markdown("**Most Contested**")
            st.dataframe(vote_df_c.tail(10).sort_values("yes")[["name","conf_year","yes","no","nominated_by"]].reset_index(drop=True),
                         use_container_width=True,height=320,hide_index=True)
        vote_sorted_c = vote_df_c.sort_values("conf_year")
        fig_votes_c = go.Figure()
        fig_votes_c.add_trace(go.Bar(name="Yes",x=vote_sorted_c["name"],y=vote_sorted_c["yes"],
                                     marker_color=[PARTY_COLOR.get(p,"#95A5A6") for p in vote_sorted_c["pres_party"]],opacity=0.85))
        fig_votes_c.add_trace(go.Bar(name="No",x=vote_sorted_c["name"],y=vote_sorted_c["no"],marker_color="rgba(150,150,150,0.5)"))
        fig_votes_c.add_hline(y=60,line_dash="dot",line_color="#E67E22")
        fig_votes_c.update_layout(barmode="stack",title="Yes / No Votes by Justice",xaxis_tickangle=-45,
                                   height=420,plot_bgcolor="white",paper_bgcolor="white",legend=dict(x=1.01,y=1))
        st.plotly_chart(fig_votes_c, use_container_width=True)
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
        st.plotly_chart(fig_trend_c, use_container_width=True)

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
        st.plotly_chart(fig_speed_c, use_container_width=True)
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
        st.plotly_chart(fig_scatter_c, use_container_width=True)

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
        st.plotly_chart(fig_bal_c, use_container_width=True)

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
