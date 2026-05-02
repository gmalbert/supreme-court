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

st.set_page_config(page_title="Presidential Legacy", page_icon="🏛️", layout="wide")

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
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False)
def _pl_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

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
            ia = detail.get("issue_area") or {}
            issue = ia.get("label", "Unknown") if isinstance(ia, dict) else "Unknown"
            disp  = detail.get("disposition") or {}
            disp_label = disp.get("label", "") if isinstance(disp, dict) else ""
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
st.title("🏛️ Presidential Legacy")
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
    st.plotly_chart(fig_gantt_ov, use_container_width=True)
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
    st.plotly_chart(fig_pres_ov, use_container_width=True)

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
    st.plotly_chart(fig_tenure, use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: COHORT ANALYSIS — Live vote data
# ──────────────────────────────────────────────────────────────────────────────
with tab_cohort:
    st.markdown("Compare how each president's court appointees voted across terms. Requires live data from Oyez.")
    available_terms_pl = list(range(CURRENT_YEAR, CURRENT_YEAR - 25, -1))

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
                st.plotly_chart(fig_cohort, use_container_width=True)

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
                st.plotly_chart(fig_trend_ca, use_container_width=True)

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
                    st.plotly_chart(fig_j, use_container_width=True)
                    st.dataframe(j_df.reset_index(drop=True), use_container_width=True, height=200)

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
        st.plotly_chart(fig_ia_infl, use_container_width=True)

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
            st.plotly_chart(fig_hm, use_container_width=True)
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
                st.plotly_chart(fig_cx, use_container_width=True)
            with col_right_cx:
                st.dataframe(cross_df.head(20).reset_index(drop=True),
                             use_container_width=True, height=320)

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
        st.plotly_chart(fig_bloc_hm, use_container_width=True)

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
            col_top_b, col_bot_b = st.columns(2)
            with col_top_b:
                st.markdown("**Most Aligned Cross-Cohort Pairs**")
                st.dataframe(pair_df_b.head(10).reset_index(drop=True)
                             .style.background_gradient(subset=["Agreement %"], cmap="Greens"),
                             use_container_width=True, height=300, hide_index=True)
            with col_bot_b:
                st.markdown("**Least Aligned Cross-Cohort Pairs**")
                st.dataframe(pair_df_b.tail(10).sort_values("Agreement %").reset_index(drop=True)
                             .style.background_gradient(subset=["Agreement %"], cmap="Reds_r"),
                             use_container_width=True, height=300, hide_index=True)

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
    st.plotly_chart(fig_legacy, use_container_width=True)
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
    st.plotly_chart(fig_breakdown, use_container_width=True)

    with st.expander("Full Legacy Score Table"):
        display_cols = ["President","Party","Appointees","Total Service-Years","Avg Tenure",
                        "Still Serving","Dominant Lean","Legacy Score"]
        st.dataframe(legacy_df[display_cols].sort_values("Legacy Score", ascending=False)
                     .reset_index(drop=True)
                     .style.background_gradient(subset=["Legacy Score"], cmap="YlOrRd"),
                     use_container_width=True, height=460, hide_index=True)

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
    st.plotly_chart(fig_shift, use_container_width=True)
