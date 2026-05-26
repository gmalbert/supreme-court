import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import datetime
from collections import defaultdict
from utils.oyez_api import get_cases_by_term, get_case_detail, get_recent_terms
from utils.charts import build_voting_chart
from utils.local_data import fetch_oyez, infer_issue_area
from utils.export import csv_download_button


from utils import add_sidebar_logo
add_sidebar_logo()

OYEZ_BASE = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Pre-built parquet for ideology drift ─────────────────────────────────────
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DETAIL_PARQUET = os.path.join(_REPO_ROOT, "data", "case_detail.parquet")

@st.cache_data(show_spinner=False)
def _load_ideology_df() -> pd.DataFrame:
    """Extract per-justice per-term ideology scores from local case_detail parquet."""
    try:
        df = pd.read_parquet(_DETAIL_PARQUET, columns=["term", "decisions"])
    except Exception:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        term = row["term"]
        decisions = row["decisions"]
        if not isinstance(decisions, str):
            continue
        try:
            import json as _json
            decs = _json.loads(decisions)
        except Exception:
            continue
        for dec in (decs or []):
            for vote in (dec.get("votes") or []):
                member = vote.get("member") or {}
                name = member.get("name", "") if isinstance(member, dict) else ""
                ideo = vote.get("ideology")
                if name and ideo is not None:
                    rows.append({"term": int(term), "justice": name, "ideology": float(ideo)})

    if not rows:
        return pd.DataFrame()

    out = (
        pd.DataFrame(rows)
        .groupby(["term", "justice"])["ideology"]
        .mean()
        .reset_index()
    )
    return out

# ── Shared fetch helpers ──────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _jh_fetch_justices() -> list[dict]:
    data = fetch_oyez(f"{OYEZ_BASE}/justices")
    return data if isinstance(data, list) else []

@st.cache_data(show_spinner=False)
def _jh_fetch_justice_detail(href: str) -> dict | None:
    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

@st.cache_data(show_spinner=False)
def _jh_fetch_cases_term(term: int) -> list[dict]:
    return get_cases_by_term(term)

@st.cache_data(show_spinner=False)
def _jh_fetch_case_detail(href: str) -> dict | None:
    return get_case_detail(href)

@st.cache_data(show_spinner=False, ttl=3600)
def _jh_load_votes_for_terms(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = get_cases_by_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = get_case_detail(href)
            if not detail: continue
            case_name = detail.get("name","")
            for decision in (detail.get("decisions") or []):
                for vote in (decision.get("votes") or []):
                    member = vote.get("member") or {}
                    justice = member.get("name","") if isinstance(member,dict) else str(member)
                    v = (vote.get("vote") or "").lower().strip()
                    if justice and v:
                        rows.append({"term":term,"case":case_name,"justice":justice,"vote":v})
    return rows

# ── Justice career helpers ─────────────────────────────────────────────────────
def _get_justice_votes(justice_name: str, terms: list[int]) -> pd.DataFrame:
    rows = []
    progress = st.progress(0)
    for idx, term in enumerate(terms):
        cases = _jh_fetch_cases_term(term)
        for c in cases:
            href = c.get("href","")
            if not href: continue
            detail = _jh_fetch_case_detail(href)
            if not detail: continue
            for dec in (detail.get("decisions") or []):
                for vote in (dec.get("votes") or []):
                    member = vote.get("member",{}) or {}
                    name = member.get("name","")
                    if justice_name.lower() in name.lower():
                        rows.append({
                            "Term": term, "Case": detail.get("name",""),
                            "Vote": vote.get("vote",""),
                            "Issue Area": infer_issue_area(detail),
                        })
        progress.progress((idx+1)/len(terms))
    progress.empty()
    return pd.DataFrame(rows)

# ── Agreement matrix helpers ───────────────────────────────────────────────────
KNOWN_JUSTICES = [
    "John G. Roberts","Clarence Thomas","Samuel Alito","Sonia Sotomayor","Elena Kagan",
    "Neil Gorsuch","Brett Kavanaugh","Amy Coney Barrett","Ketanji Brown Jackson",
    "Stephen Breyer","Ruth Bader Ginsburg","Anthony Kennedy","David Souter",
    "John Paul Stevens","Sandra Day O'Connor","Antonin Scalia",
]
JUSTICE_SHORT = {
    "John G. Roberts":"Roberts","John G. Roberts, Jr.":"Roberts",
    "Clarence Thomas":"Thomas","Samuel Alito":"Alito",
    "Sonia Sotomayor":"Sotomayor","Elena Kagan":"Kagan","Neil Gorsuch":"Gorsuch",
    "Brett Kavanaugh":"Kavanaugh","Amy Coney Barrett":"Barrett","Ketanji Brown Jackson":"Jackson",
    "Stephen Breyer":"Breyer","Ruth Bader Ginsburg":"Ginsburg","Anthony Kennedy":"Kennedy",
    "David Souter":"Souter","John Paul Stevens":"Stevens","Sandra Day O'Connor":"O'Connor",
    "Antonin Scalia":"Scalia",
    "Samuel A. Alito, Jr.":"Alito",
}
JUSTICE_LEAN = {
    "Roberts":"Conservative","Thomas":"Conservative","Alito":"Conservative",
    "Gorsuch":"Conservative","Kavanaugh":"Conservative","Barrett":"Conservative",
    "Scalia":"Conservative","Kennedy":"Moderate","O'Connor":"Moderate",
    "Sotomayor":"Liberal","Kagan":"Liberal","Jackson":"Liberal",
    "Breyer":"Liberal","Ginsburg":"Liberal","Stevens":"Liberal","Souter":"Liberal",
}
LEAN_COLORS = {"Conservative":"#E74C3C","Moderate":"#27AE60","Liberal":"#3498DB"}

def _normalize_name(name: str) -> str:
    # Exact match first (handles "Jr." suffixes)
    if name in JUSTICE_SHORT:
        return JUSTICE_SHORT[name]
    # Substring match
    name_l = name.lower()
    for full, short in JUSTICE_SHORT.items():
        if full.lower() in name_l or name_l in full.lower():
            return short
    # Last token, but skip honorific suffixes
    tokens = [t.strip(",") for t in name.split() if t.strip(",") not in ("Jr.", "Sr.", "II", "III")]
    return tokens[-1] if tokens else name

def _build_agreement_matrix(rows: list[dict], min_cases: int = 5) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty: return pd.DataFrame()
    df["justice_short"] = df["justice"].apply(_normalize_name)
    pivot = df.pivot_table(index="case", columns="justice_short", values="vote", aggfunc="first")
    justices = list(pivot.columns)
    agree: dict[tuple,int] = defaultdict(int); total: dict[tuple,int] = defaultdict(int)
    for j1 in justices:
        for j2 in justices:
            if j1 >= j2: continue
            both = pivot[[j1,j2]].dropna(); n = len(both)
            if n < min_cases: continue
            agree[(j1,j2)] = int((both[j1]==both[j2]).sum()); total[(j1,j2)] = n
    all_j = sorted(set(j for pair in total for j in pair))
    mat = pd.DataFrame(index=all_j, columns=all_j, dtype=float)
    for j1 in all_j:
        for j2 in all_j:
            if j1 == j2: mat.at[j1,j2] = 100.0
            else:
                key = (min(j1,j2),max(j1,j2))
                if key in total and total[key]>0:
                    mat.at[j1,j2] = round(agree[key]/total[key]*100,1)
    return mat

def _make_heatmap(mat: pd.DataFrame) -> go.Figure:
    labels = list(mat.index); values = mat.values.tolist()
    text_vals = [[f"{v:.0f}%" if v==v else "" for v in row] for row in values]
    fig = go.Figure(go.Heatmap(
        z=values, x=labels, y=labels, text=text_vals, texttemplate="%{text}",
        colorscale=[[0.0,"#2C3E50"],[0.5,"#F39C12"],[0.7,"#27AE60"],[1.0,"#1ABC9C"]],
        zmin=40, zmax=100, colorbar=dict(title="Agreement %",ticksuffix="%"),
        hovertemplate="<b>%{y}</b> ↔ <b>%{x}</b><br>Agreement: %{z:.1f}%<extra></extra>",
    ))
    fig.update_xaxes(tickfont=dict(size=11), tickangle=-45)
    fig.update_yaxes(tickfont=dict(size=11))
    fig.update_layout(height=600, plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=100,r=60,t=30,b=100))
    return fig

def _find_blocs(mat: pd.DataFrame, threshold: float = 72.0) -> list[set]:
    justices = list(mat.index); blocs: list[set] = []; assigned: set[str] = set()
    for j1 in justices:
        if j1 in assigned: continue
        bloc = {j1}
        for j2 in justices:
            if j2 == j1 or j2 in assigned: continue
            v = mat.at[j1,j2]
            if v == v and v >= threshold: bloc.add(j2)
        if len(bloc) > 1: blocs.append(bloc); assigned.update(bloc)
    return blocs

# ── Page ─────────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import datetime
from collections import defaultdict


OYEZ_BASE    = "https://api.oyez.org"
CURRENT_YEAR = datetime.date.today().year

# ── Fetch helpers ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _adv_fetch_term(term: int) -> list[dict]:
    return get_cases_by_term(term)

@st.cache_data(show_spinner=False)
def _adv_fetch_detail(href: str) -> dict | None:
    return get_case_detail(href)

# ── Issue area inference (shared from utils.local_data) ──────────────────────
# infer_issue_area(detail) imported above

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

def _winner_side_from_detail(detail: dict) -> str | None:
    """Determine winning side (petitioner/respondent) from case detail.

    Oyez never populates ``disposition`` on the detail endpoint, so we fall back
    to ``decisions[0].winning_party`` matched against the party names.
    """
    # Legacy path: disposition label (rarely populated)
    disp = detail.get("disposition") or {}
    disp_label = disp.get("label", "") if isinstance(disp, dict) else str(disp or "")
    if disp_label:
        result = _winner_side(disp_label)
        if result:
            return result

    # Primary path: winning_party inside decisions
    decisions = detail.get("decisions") or []
    if not decisions:
        return None
    wp = (decisions[0].get("winning_party") or "").strip()
    if not wp:
        return None

    first_party  = (detail.get("first_party")  or "").strip()
    second_party = (detail.get("second_party") or "").strip()
    first_label  = (detail.get("first_party_label")  or "petitioner").lower()
    second_label = (detail.get("second_party_label") or "respondent").lower()

    _SKIP = {"a", "an", "the", "of", "in", "for", "and", "or", "v", "vs", "at", "to"}

    def _matches(wp: str, party: str) -> bool:
        wp_l, party_l = wp.lower(), party.lower()
        if wp_l in party_l or party_l in wp_l:
            return True
        # Token overlap — skip short stopwords ("of", "v", "the", etc.)
        wp_toks    = {t.strip(".,()") for t in wp_l.split()    if len(t.strip(".,()")) > 2}
        party_toks = {t.strip(".,()") for t in party_l.split() if len(t.strip(".,()")) > 2}
        if wp_toks & party_toks:
            return True
        # Acronym check: "SFFA" → "Students For Fair Admissions", "NFIB" → "National Federation..."
        if len(wp_l) >= 3 and wp_l.isalpha():
            words = [w.strip(".,()") for w in party_l.split() if w.strip(".,()")] 
            initials_all = "".join(w[0] for w in words)
            initials_sig = "".join(w[0] for w in words if w not in _SKIP)
            if wp_l in initials_all or wp_l in initials_sig:
                return True
        return False

    if _matches(wp, first_party):
        return "petitioner" if any(x in first_label for x in ("petitioner", "appellant")) else "respondent"
    if _matches(wp, second_party):
        return "petitioner" if any(x in second_label for x in ("petitioner", "appellant")) else "respondent"
    return None

@st.cache_data(show_spinner=False)
def _adv_load_advocate_data(terms: tuple) -> list[dict]:
    rows = []
    for term in terms:
        cases = _adv_fetch_term(term)
        for c in cases:
            href = c.get("href", "")
            if not href: continue
            detail = _adv_fetch_detail(href)
            if not detail: continue
            # Determine winner using decisions data (disposition is never populated by Oyez)
            winner_side = _winner_side_from_detail(detail)
            advocates = detail.get("advocates") or []
            if not advocates: continue
            issue = infer_issue_area(detail)
            for adv_entry in advocates:
                if not isinstance(adv_entry, dict): continue
                adv = adv_entry.get("advocate") or {}
                adv_name = adv.get("name","") if isinstance(adv,dict) else str(adv)
                description = adv_entry.get("advocate_description","")
                role = _advocate_role(description)
                if not adv_name or role == "other": continue
                # won is None when winner can't be determined (undecided/unknown)
                won = (role == winner_side) if winner_side else None
                rows.append({
                    "term": term, "case": detail.get("name",""),
                    "advocate": adv_name, "role": role, "won": won,
                    "issue_area": issue, "description": description,
                })
    return rows

# ── Oral Argument Analysis helpers ────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _adv_load_transcript(arg_href: str) -> dict | None:
    data = fetch_oyez(arg_href)
    return data if isinstance(data, dict) else None

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

def _page_justices():
    tab_voting, tab_career, tab_matrix, tab_ideology = st.tabs([
        "⚖️ Voting Patterns", "📊 Justice Career", "🤝 Agreement Matrix", "📈 Ideology Drift"
    ])

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 1: JUSTICE VOTING PATTERNS
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_voting:
        st.markdown("Explore how individual justices voted on Supreme Court cases.")
        jv_term = st.selectbox("Select Term", get_recent_terms(15), key="jv_term")
        with st.spinner("Loading cases..."):
            jv_cases = get_cases_by_term(jv_term)
        if not jv_cases:
            st.warning("No cases found for the selected term.")
        else:
            jv_case_names = sorted([c.get("name","Unknown") for c in jv_cases])
            jv_selected_name = st.selectbox("Select a Case", jv_case_names, key="jv_case")
            jv_selected = next((c for c in jv_cases if c.get("name")==jv_selected_name), None)
            if jv_selected:
                jv_href = jv_selected.get("href","")
                if jv_href:
                    with st.spinner("Loading case details..."):
                        jv_detail = get_case_detail(jv_href)
                    if not jv_detail:
                        st.warning("Could not load case details.")
                    else:
                        decisions = jv_detail.get("decisions") or []
                        if not decisions:
                            st.info("No voting data available for this case.")
                        else:
                            for decision in decisions:
                                winning_party = decision.get("winning_party","Unknown")
                                votes = decision.get("votes",[])
                                if votes:
                                    n_maj = sum(1 for v in votes if (v.get("vote") or "").lower() in ("majority","concurrence"))
                                    n_dis = sum(1 for v in votes if (v.get("vote") or "").lower() in ("dissent","minority"))
                                    split_str = f" ({n_maj}–{n_dis})" if n_maj or n_dis else ""
                                    st.subheader(f"Winning Party: {winning_party}{split_str}")
                                    fig = build_voting_chart(votes)
                                    if fig: st.plotly_chart(fig)
                                    rows = []
                                    for v in votes:
                                        member = v.get("member",{}) or {}
                                        rows.append({"Justice":member.get("name","Unknown"),"Vote":v.get("vote","")})
                                    if rows:
                                        df = pd.DataFrame(rows)
                                        majority = df[df["Vote"].str.lower().isin(["majority","concurrence"])]
                                        dissent  = df[df["Vote"].str.lower().isin(["dissent","minority"])]
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            st.markdown("**Majority/Concurrence**")
                                            for _, row in majority.iterrows():
                                                st.markdown(f"- {row['Justice']} ({row['Vote'].title()})")
                                        with c2:
                                            st.markdown("**Dissent**")
                                            if dissent.empty: st.markdown("_No dissents_")
                                            else:
                                                for _, row in dissent.iterrows():
                                                    st.markdown(f"- {row['Justice']} ({row['Vote'].title()})")
                                else:
                                    winning_party = decision.get("winning_party","Unknown")
                                    st.subheader(f"Winning Party: {winning_party}")
                                st.divider()

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 2: JUSTICE CAREER OVERVIEW
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_career:
        st.markdown("Explore a justice's voting history, issue area tendencies, and notable cases.")
        with st.spinner("Loading justices..."):
            justices_list = _jh_fetch_justices()
        if not justices_list:
            st.error("Could not load justices from Oyez.")
        else:
            justices_sorted = sorted(justices_list, key=lambda j: j.get("name","").split()[-1])
            justice_names = [j.get("name","Unknown") for j in justices_sorted]
            jc_selected_name = st.selectbox("Select a Justice", justice_names, key="jc_sel")
            jc_selected = next((j for j in justices_sorted if j.get("name")==jc_selected_name), None)

            if jc_selected:
                jc_href = jc_selected.get("href","")
                with st.spinner("Loading justice profile..."):
                    jc_detail = _jh_fetch_justice_detail(jc_href) if jc_href else None

                col_bio, col_stats = st.columns([2,1])
                with col_bio:
                    st.subheader(jc_selected_name)
                    if jc_detail:
                        for role in (jc_detail.get("roles") or []):
                            court = role.get("institution_name","")
                            date_start = role.get("date_start",0); date_end = role.get("date_end",0)
                            title = role.get("role_title","Justice")
                            def _ts_to_year(ts):
                                if ts:
                                    try: return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).year
                                    except Exception: return "?"
                                return "present"
                            start_yr = _ts_to_year(date_start)
                            end_yr   = _ts_to_year(date_end) if date_end else "present"
                            st.markdown(f"- **{title}**, {court} ({start_yr} – {end_yr})")
                        desc = jc_detail.get("description","")
                        if desc:
                            with st.expander("Biography"): st.write(desc)
                with col_stats:
                    st.markdown("**Quick Info**")
                    if jc_detail:
                        roles = jc_detail.get("roles",[])
                        if roles:
                            latest = roles[-1]
                            appointer = latest.get("appointing_president","")
                            if appointer: st.markdown(f"- **Appointed by:** {appointer}")
                            party = latest.get("party_affiliation",{})
                            if isinstance(party,dict) and party.get("label"):
                                st.markdown(f"- **Party:** {party['label']}")

                st.divider()
                st.subheader("Voting History Analysis")
                st.info("Fetches live case data. Selecting many terms will take longer to load.")
                available_terms = list(range(CURRENT_YEAR-1, CURRENT_YEAR-28,-1))
                jc_sel_terms = st.multiselect("Select Terms to Analyze", available_terms,
                                               default=available_terms[:5], max_selections=10, key="jc_terms")
                if not jc_sel_terms:
                    st.warning("Please select at least one term.")
                elif st.button("Load Voting History", type="primary", key="jc_load"):
                    with st.spinner(f"Fetching voting records for {jc_selected_name}…"):
                        jc_df = _get_justice_votes(jc_selected_name, sorted(jc_sel_terms, reverse=True))
                    st.session_state["jc_df"] = jc_df
                    st.session_state["jc_name"] = jc_selected_name

                if "jc_df" in st.session_state and st.session_state.get("jc_name")==jc_selected_name:
                    jc_df = st.session_state["jc_df"]
                    if jc_df.empty:
                        st.warning("No voting data found for this justice in the selected terms.")
                    else:
                        total = len(jc_df)
                        majority = len(jc_df[jc_df["Vote"].str.lower().isin(["majority","concurrence"])])
                        dissent  = len(jc_df[jc_df["Vote"].str.lower().isin(["dissent","minority"])])
                        st.success(f"Found {total} votes across {jc_df['Term'].nunique()} term(s).")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Total Votes", total)
                        m2.metric("Majority/Concurrence", majority, f"{majority/total*100:.0f}%")
                        m3.metric("Dissents", dissent, f"{dissent/total*100:.0f}%")

                        col_left, col_right = st.columns(2)
                        with col_left:
                            vote_counts = jc_df["Vote"].value_counts().reset_index()
                            vote_counts.columns = ["Vote Type","Count"]
                            color_map = {"majority":"#27AE60","concurrence":"#2ECC71","dissent":"#E74C3C","minority":"#E74C3C","recusal":"#95A5A6"}
                            colors = [color_map.get(v.lower(),"#BDC3C7") for v in vote_counts["Vote Type"]]
                            vote_counts["Vote Type"] = vote_counts["Vote Type"].str.title()
                            fig_votes = go.Figure(go.Bar(x=vote_counts["Vote Type"],y=vote_counts["Count"],
                                                         marker_color=colors,text=vote_counts["Count"],
                                                         textposition="auto",
                                                         textfont=dict(color="white", size=13)))
                            fig_votes.update_layout(title="Vote Type Breakdown",height=320,
                                                    margin=dict(t=50,b=20,l=20,r=20),
                                                    plot_bgcolor="white",paper_bgcolor="white")
                            st.plotly_chart(fig_votes)
                        with col_right:
                            issue_counts = jc_df["Issue Area"].value_counts().reset_index()
                            issue_counts.columns = ["Issue Area","Count"]
                            fig_issues = px.pie(issue_counts,names="Issue Area",values="Count",
                                                title="Cases by Issue Area",hole=0.3)
                            fig_issues.update_layout(height=320)
                            st.plotly_chart(fig_issues)

                        if jc_df["Term"].nunique() > 1:
                            term_stats = []
                            for term, grp in jc_df.groupby("Term"):
                                total_t = len(grp)
                                dissent_t = len(grp[grp["Vote"].str.lower().isin(["dissent","minority"])])
                                rate = dissent_t / total_t * 100 if total_t else 0
                                term_stats.append({"Term":term,"Dissent Rate (%)":rate,
                                                   "_display":max(rate, 0.25),
                                                   "label":f"{dissent_t}/{total_t}","Cases":total_t})
                            term_df = pd.DataFrame(term_stats).sort_values("Term")
                            max_rate = term_df["Dissent Rate (%)"].max() or 1
                            bar_colors = px.colors.sample_colorscale(
                                "Reds", [min(r / max_rate, 1.0) for r in term_df["Dissent Rate (%)"]]
                            )
                            fig_trend = go.Figure(go.Bar(
                                x=term_df["Term"], y=term_df["_display"],
                                text=term_df["label"], textposition="outside",
                                marker_color=bar_colors,
                                customdata=list(zip(term_df["Dissent Rate (%)"].round(1), term_df["Cases"])),
                                hovertemplate="%{x}: %{customdata[0]:.1f}% dissent rate (%{customdata[1]} cases)<extra></extra>",
                            ))
                            y_max = max(term_df["_display"].max() * 1.35, 2)
                            fig_trend.update_layout(
                                title=f"{jc_selected_name} — Dissent Rate by Term",
                                height=320, plot_bgcolor="white", paper_bgcolor="white",
                                yaxis=dict(title="Dissent Rate (%)", range=[0, y_max]),
                                xaxis=dict(tickmode="array", tickvals=term_df["Term"].tolist()),
                                margin=dict(t=50, b=20, l=20, r=20),
                            )
                            st.plotly_chart(fig_trend)

                        st.subheader("Dissenting Votes")
                        dissents_df = jc_df[jc_df["Vote"].str.lower().isin(["dissent","minority"])][["Term","Case","Issue Area"]].drop_duplicates()
                        if dissents_df.empty: st.info("No dissenting votes found in the selected terms.")
                        else:
                            st.dataframe(dissents_df.sort_values("Term",ascending=False),height=300, hide_index=True)
                            csv_download_button(dissents_df.sort_values("Term",ascending=False), filename=f"{jc_selected_name.replace(' ','_')}_dissents.csv", key="csv_dissents")
                        with st.expander("Full Voting Record"):
                            st.dataframe(jc_df.sort_values(["Term","Case"],ascending=[False,True]),height=400, hide_index=True)
                            csv_download_button(jc_df.sort_values(["Term","Case"],ascending=[False,True]), filename=f"{jc_selected_name.replace(' ','_')}_votes.csv", key="csv_full_votes")

    # ──────────────────────────────────────────────────────────────────────────────
    # TAB 3: JUSTICE AGREEMENT MATRIX
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_matrix:
        st.markdown("How often do pairs of justices vote the same way? Computed from live Oyez data.")
        available_terms_m = list(range(CURRENT_YEAR-1, CURRENT_YEAR-26,-1))

        with st.form("matrix_form"):
            col1, col2 = st.columns([2,1])
            with col1:
                sel_terms_m = st.multiselect("Terms to include", available_terms_m,
                                              default=available_terms_m[:6], max_selections=12, key="matrix_terms")
            with col2:
                min_cases_m = st.slider("Min shared cases per pair", 2, 20, 5, key="matrix_min")
            submitted_m = st.form_submit_button("Build Matrix", type="primary")

        if submitted_m and sel_terms_m:
            with st.spinner(f"Loading vote data for {len(sel_terms_m)} term(s)…"):
                matrix_rows = _jh_load_votes_for_terms(tuple(sorted(sel_terms_m, reverse=True)))
            st.session_state["matrix_rows"] = matrix_rows
            st.session_state["matrix_terms_loaded"] = sel_terms_m
            st.session_state["matrix_min_cases"] = min_cases_m

        if "matrix_rows" not in st.session_state:
            st.info("Select terms above and click **Build Matrix** to load the data.")
        else:
            matrix_rows = st.session_state["matrix_rows"]
            terms_loaded = st.session_state.get("matrix_terms_loaded",[])
            min_cases_val = st.session_state.get("matrix_min_cases",5)

            if not matrix_rows:
                st.warning("No vote data found.")
            else:
                df_all = pd.DataFrame(matrix_rows)
                n_cases = df_all["case"].nunique(); n_terms_loaded = df_all["term"].nunique()
                st.success(f"Loaded **{len(matrix_rows):,}** votes across **{n_cases}** cases from **{n_terms_loaded}** term(s).")

                mat = _build_agreement_matrix(matrix_rows, min_cases=min_cases_val)
                if mat.empty:
                    st.warning("Not enough shared cases to build a matrix.")
                else:
                    st.subheader("Agreement Heatmap")
                    st.caption("Dark = lower agreement, teal = high agreement. Diagonal = 100%.")
                    lean_cols = st.columns(3)
                    for i, (lean, color) in enumerate(LEAN_COLORS.items()):
                        lean_cols[i].markdown(f'<span style="color:{color};font-weight:bold;">■</span> {lean}', unsafe_allow_html=True)
                    st.plotly_chart(_make_heatmap(mat))

                    st.divider()
                    st.subheader("Most & Least Aligned Pairs")
                    pair_rows = []
                    jj = list(mat.index)
                    for i, j1 in enumerate(jj):
                        for j2 in jj[i+1:]:
                            v = mat.at[j1,j2]
                            if v == v: pair_rows.append({"Justice A":j1,"Justice B":j2,"Agreement %":v})
                    if pair_rows:
                        pair_df = pd.DataFrame(pair_rows).sort_values("Agreement %",ascending=False)
                        col_top, col_bot = st.columns(2)
                        with col_top:
                            st.markdown("**Highest Agreement**")
                            st.dataframe(pair_df.head(10).reset_index(drop=True)
                                         .style.format({"Agreement %": "{:.2f}"})
                                         .background_gradient(subset=["Agreement %"],cmap="Greens"),
                                         height=320, hide_index=True)
                        with col_bot:
                            st.markdown("**Lowest Agreement**")
                            st.dataframe(pair_df.tail(10).sort_values("Agreement %").reset_index(drop=True)
                                         .style.format({"Agreement %": "{:.2f}"})
                                         .background_gradient(subset=["Agreement %"],cmap="Reds_r"),
                                         height=320, hide_index=True)

                    st.divider()
                    st.subheader("Detected Voting Blocs")
                    threshold_m = st.slider("Agreement threshold for bloc membership", 55, 90, 72, step=1,
                                            format="%d%%", key="bloc_thresh")
                    blocs = _find_blocs(mat, threshold=float(threshold_m))
                    if blocs:
                        for i, bloc in enumerate(blocs,1):
                            members = sorted(bloc)
                            leans = [JUSTICE_LEAN.get(j,"Moderate") for j in members]
                            dominant = max(set(leans), key=leans.count)
                            color = LEAN_COLORS.get(dominant,"#7F8C8D")
                            st.markdown(f'<div style="border-left:4px solid {color};padding-left:10px;margin-bottom:8px;">'
                                        f'<strong>Bloc {i}:</strong> {" · ".join(members)}</div>', unsafe_allow_html=True)
                    else:
                        st.info("No blocs found at this threshold. Try lowering the agreement %.")

                    st.divider()
                    st.subheader("Average Agreement by Justice")
                    avg_rows = []
                    for j in mat.index:
                        valid = [mat.at[j,j2] for j2 in mat.columns if j2!=j and mat.at[j,j2]==mat.at[j,j2]]
                        if valid: avg_rows.append({"Justice":j,"Avg Agreement %":round(sum(valid)/len(valid),1)})
                    if avg_rows:
                        avg_df = pd.DataFrame(avg_rows).sort_values("Avg Agreement %",ascending=False)
                        avg_df["Lean"]  = avg_df["Justice"].map(lambda j: JUSTICE_LEAN.get(j,"Moderate"))
                        avg_df["Color"] = avg_df["Lean"].map(LEAN_COLORS)
                        fig_avg = go.Figure(go.Bar(
                            x=avg_df["Justice"], y=avg_df["Avg Agreement %"],
                            marker_color=avg_df["Color"].tolist(),
                            text=avg_df["Avg Agreement %"].apply(lambda v: f"{v:.1f}%"),
                            textposition="outside"))
                        fig_avg.update_layout(height=340, yaxis=dict(title="Avg Agreement %",range=[40,100]),
                                              xaxis_tickangle=-30, plot_bgcolor="white", paper_bgcolor="white")
                        st.plotly_chart(fig_avg)

    # TAB 4: IDEOLOGY DRIFT
    # ──────────────────────────────────────────────────────────────────────────────
    with tab_ideology:
        st.markdown(
            "Track how each justice's ideological position has shifted over time, "
            "based on Martin–Quinn-style scores embedded in the Oyez vote data. "
            "**Negative = more liberal, Positive = more conservative.** "
            "Hover over any point to see the term and score."
        )

        ideo_df = _load_ideology_df()
        if ideo_df.empty:
            st.warning("Ideology data not available. Ensure `data/case_detail.parquet` is present.")
        else:
            all_justices = sorted(ideo_df["justice"].unique())
            # Default to the current 9 justices if they appear in the data
            _current_short_names = [
                "John G. Roberts", "Clarence Thomas", "Samuel A. Alito, Jr.",
                "Sonia Sotomayor", "Elena Kagan", "Neil M. Gorsuch",
                "Brett M. Kavanaugh", "Amy Coney Barrett", "Ketanji Brown Jackson",
            ]
            _defaults = [j for j in all_justices if any(s in j for s in ["Roberts","Thomas","Alito","Sotomayor","Kagan","Gorsuch","Kavanaugh","Barrett","Jackson"])][:9]
            if not _defaults:
                _defaults = all_justices[:9]

            col_sel, col_opts = st.columns([3, 1])
            with col_sel:
                selected_justices = st.multiselect(
                    "Select justices to display",
                    all_justices,
                    default=_defaults,
                    key="ideo_justices",
                )
            with col_opts:
                show_rolling = st.checkbox("Show 3-term rolling avg", value=True, key="ideo_rolling")
                show_zero = st.checkbox("Show neutral line", value=True, key="ideo_zero")

            if not selected_justices:
                st.info("Select at least one justice.")
            else:
                filtered = ideo_df[ideo_df["justice"].isin(selected_justices)].copy()
                filtered = filtered.sort_values(["justice", "term"])

                # Compute 3-term rolling average per justice
                filtered["rolling_avg"] = (
                    filtered.groupby("justice")["ideology"]
                    .transform(lambda s: s.rolling(3, min_periods=1).mean())
                )

                _JUSTICE_COLORS = px.colors.qualitative.D3 + px.colors.qualitative.Plotly
                color_map = {j: _JUSTICE_COLORS[i % len(_JUSTICE_COLORS)] for i, j in enumerate(all_justices)}

                fig_drift = go.Figure()

                for justice in selected_justices:
                    jdf = filtered[filtered["justice"] == justice]
                    col = color_map[justice]

                    # Raw per-term dots
                    fig_drift.add_trace(go.Scatter(
                        x=jdf["term"], y=jdf["ideology"],
                        mode="markers",
                        marker=dict(color=col, size=5, opacity=0.4),
                        showlegend=False,
                        hovertemplate=f"<b>{justice}</b><br>Term: %{{x}}<br>Score: %{{y:.3f}}<extra></extra>",
                    ))

                    if show_rolling:
                        fig_drift.add_trace(go.Scatter(
                            x=jdf["term"], y=jdf["rolling_avg"],
                            mode="lines+markers",
                            name=justice,
                            line=dict(color=col, width=2),
                            marker=dict(size=7),
                            hovertemplate=f"<b>{justice}</b><br>Term: %{{x}}<br>3-term avg: %{{y:.3f}}<extra></extra>",
                        ))
                    else:
                        fig_drift.add_trace(go.Scatter(
                            x=jdf["term"], y=jdf["ideology"],
                            mode="lines+markers",
                            name=justice,
                            line=dict(color=col, width=2),
                            marker=dict(size=7),
                            hovertemplate=f"<b>{justice}</b><br>Term: %{{x}}<br>Score: %{{y:.3f}}<extra></extra>",
                        ))

                if show_zero:
                    fig_drift.add_hline(y=0, line_dash="dash", line_color="#95A5A6",
                                        annotation_text="Neutral", annotation_position="right")

                # Add shaded regions
                fig_drift.add_hrect(y0=-6, y1=0, fillcolor="rgba(52,152,219,0.05)", line_width=0)
                fig_drift.add_hrect(y0=0, y1=6, fillcolor="rgba(231,76,60,0.05)", line_width=0)
                fig_drift.add_annotation(x=filtered["term"].min(), y=3.5, text="Conservative →",
                                          showarrow=False, font=dict(color="#E74C3C", size=10), xanchor="left")
                fig_drift.add_annotation(x=filtered["term"].min(), y=-3.5, text="← Liberal",
                                          showarrow=False, font=dict(color="#3498DB", size=10), xanchor="left")

                fig_drift.update_layout(
                    title="Justice Ideology Scores by Term (Oyez Martin–Quinn data)",
                    xaxis_title="SCOTUS Term",
                    yaxis_title="Ideology Score",
                    height=500,
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    legend=dict(orientation="v", x=1.01, y=0.5),
                    hovermode="x unified" if len(selected_justices) <= 4 else "closest",
                )
                st.plotly_chart(fig_drift)
                st.caption(
                    "Scores are Martin–Quinn-style ideology estimates from Oyez vote data. "
                    "Negative values indicate a justice voted more often with the liberal bloc; "
                    "positive values with the conservative bloc. "
                    "Data covers terms where vote-level ideology data is available in the Oyez API."
                )


def _page_advocates():
    tab_advocates, tab_amicus, tab_oral = st.tabs([
        "🎓 Advocate Win Rates", "📄 Amicus Brief Tracker", "🎙️ Oral Argument Analytics"
    ])
    with tab_advocates:
        st.markdown(
            "Track individual Supreme Court advocates — which attorneys win most often, "
            "what issue areas they specialize in, and how their careers have evolved."
        )
        available_terms_adv = list(range(CURRENT_YEAR-1, CURRENT_YEAR-21,-1))
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
                    total = len(grp)
                    decided = grp[grp["won"].notna()]   # only rows where win/loss is known
                    wins    = int(decided["won"].sum()) if not decided.empty else 0
                    losses  = len(decided) - wins
                    undecided = total - wins - losses   # pending / outcome unknown
                    win_rate = round(wins / len(decided) * 100, 1) if not decided.empty else None
                    terms_active = sorted(grp["term"].unique())
                    issue_areas  = [ia for ia in grp["issue_area"].value_counts().index[:3].tolist()
                                    if ia != "Unknown"]
                    roles = grp["role"].value_counts()
                    pet_pct = int(roles.get("petitioner",0)/total*100)
                    adv_agg.append({
                        "Advocate": adv, "Total Appearances": total,
                        "Wins": wins, "Losses": losses, "Undecided": undecided,
                        "Win Rate %": win_rate, "Terms Active": len(terms_active),
                        "First Term": min(terms_active),
                        "Issue Specialization": ", ".join(issue_areas) if issue_areas else "Unknown",
                        "% as Petitioner": pet_pct,
                    })
                adv_df = pd.DataFrame(adv_agg)
                adv_df = adv_df[adv_df["Total Appearances"] >= min_cases_adv].copy()
                # Sort: advocates with known win rates first (by win rate), then by appearances
                adv_df = adv_df.sort_values(
                    ["Win Rate %", "Total Appearances"], ascending=[False, False], na_position="last"
                )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Advocates (min appearances)", len(adv_df))
                top_wr = adv_df.dropna(subset=["Win Rate %"])
                m2.metric("Top Win Rate",
                          f"{top_wr.iloc[0]['Win Rate %']:.0f}%" if not top_wr.empty else "N/A",
                          top_wr.iloc[0]["Advocate"][:25] if not top_wr.empty else "")
                if not adv_df.empty:
                    top_app_idx = adv_df["Total Appearances"].idxmax()
                    m3.metric("Most Appearances", str(adv_df["Total Appearances"].max()),
                              adv_df.loc[top_app_idx, "Advocate"][:25])
                else:
                    m3.metric("Most Appearances", "N/A")
                avg_wr = adv_df["Win Rate %"].mean()
                m4.metric("Avg Win Rate", f"{avg_wr:.1f}%" if pd.notna(avg_wr) else "N/A")
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
                    st.dataframe(adv_df.head(25)[["Advocate","Total Appearances","Wins","Losses","Undecided","Win Rate %","Issue Specialization","First Term"]]
                                 .reset_index(drop=True).style.background_gradient(subset=["Win Rate %"],cmap="RdYlGn"),
                                 height=380, hide_index=True)
                    csv_download_button(adv_df[["Advocate","Total Appearances","Wins","Losses","Undecided","Win Rate %","Issue Specialization","First Term"]].reset_index(drop=True), filename="scotus_advocate_win_rates.csv", key="csv_advocates")
                    csv_download_button(adv_df[["Advocate","Total Appearances","Wins","Losses","Undecided","Win Rate %","Issue Specialization","First Term"]].reset_index(drop=True), filename="scotus_advocate_win_rates.csv", key="csv_advocates")

                with sub_issue:
                    issue_adv_rows = []
                    for (issue, role), grp in df_adv.groupby(["issue_area","role"]):
                        if role == "other" or issue == "Unknown": continue
                        decided_grp = grp[grp["won"].notna()]
                        if decided_grp.empty: continue
                        wins = int(decided_grp["won"].sum())
                        issue_adv_rows.append({"Issue Area":issue,"Role":role,
                                                "Decided":len(decided_grp),
                                                "Win Rate %":round(wins/len(decided_grp)*100,1)})
                    if issue_adv_rows:
                        issue_adv_df = pd.DataFrame(issue_adv_rows)
                        fig_ia_adv = px.bar(issue_adv_df,x="Issue Area",y="Win Rate %",color="Role",barmode="group",
                                            title="Advocate Win Rate by Issue Area and Role",
                                            color_discrete_map={"petitioner":"#E74C3C","respondent":"#3498DB"})
                        fig_ia_adv.add_hline(y=50,line_dash="dot",line_color="#BDC3C7")
                        fig_ia_adv.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white",xaxis_tickangle=-30)
                        st.plotly_chart(fig_ia_adv)
                        n_unknown = (df_adv["issue_area"] == "Unknown").sum()
                        if n_unknown:
                            st.caption(f"Note: {n_unknown} case appearances could not be categorized and are excluded.")
                    else:
                        st.info(
                            "No issue area data available for the loaded terms. "
                            "Click **Load Advocate Data** again to refresh with updated keyword matching."
                        )
                        n_total = len(df_adv)
                        n_unknown = (df_adv["issue_area"] == "Unknown").sum()
                        st.caption(f"Debug: {n_unknown}/{n_total} case appearances returned 'Unknown' issue area.")

                with sub_career:
                    all_advocates_career = sorted(adv_df["Advocate"].tolist())
                    sel_adv_career = st.selectbox("Select an advocate", all_advocates_career, key="adv_career_sel") if all_advocates_career else None
                    if sel_adv_career:
                        career_df = df_adv[df_adv["advocate"] == sel_adv_career]
                        career_agg = []
                        for term, grp in career_df.groupby("term"):
                            total_t = len(grp)
                            dec_t = grp[grp["won"].notna()]
                            wins_t = int(dec_t["won"].sum()) if not dec_t.empty else 0
                            career_agg.append({"Term":term,"Appearances":total_t,"Wins":wins_t,
                                                "Win Rate %":round(wins_t/len(dec_t)*100,1) if not dec_t.empty else None})
                        career_agg_df = pd.DataFrame(career_agg).sort_values("Term")
                        if not career_agg_df.empty:
                            col_c1, col_c2, col_c3 = st.columns(3)
                            all_decided = career_df[career_df["won"].notna()]
                            total_wins = int(all_decided["won"].sum()) if not all_decided.empty else 0
                            overall_wr = round(total_wins/len(all_decided)*100,1) if not all_decided.empty else None
                            col_c1.metric("Total Appearances", career_df.shape[0])
                            col_c2.metric("Total Wins", total_wins)
                            col_c3.metric("Overall Win Rate", f"{overall_wr:.1f}%" if overall_wr is not None else "N/A")
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
            fig_rank.update_layout(title="Average Questions per Oral Argument",height=340,
                                    yaxis=dict(title="Avg Questions", range=[0, rank_df["Avg Questions"].max() * 1.25]),
                                    margin=dict(t=50,b=60,l=20,r=20),
                                    plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig_rank)

        with sub_live:
            st.markdown("Analyze the transcript of a specific oral argument — count questions, speaking time, and patterns.")
            available_terms_oa = list(range(CURRENT_YEAR-1, 1955,-1))
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
                                st.caption("Includes both justices and advocates.")
                                col_turns, col_words = st.columns(2)
                                with col_turns:
                                    turns_df = pd.DataFrame(list(speaker_turns.items()),columns=["Speaker","Turns"]).sort_values("Turns",ascending=False)
                                    fig_turns = go.Figure(go.Bar(y=turns_df["Speaker"],x=turns_df["Turns"],orientation="h",marker_color="#3498DB",text=turns_df["Turns"],textposition="outside"))
                                    turns_max = turns_df["Turns"].max() if not turns_df.empty else 1
                                    fig_turns.update_layout(title="Speaking Turns per Participant",height=360,plot_bgcolor="white",paper_bgcolor="white",
                                                            margin=dict(l=150,r=60,t=40,b=40),
                                                            xaxis=dict(range=[0, turns_max * 1.25]))
                                    st.plotly_chart(fig_turns)
                                with col_words:
                                    words_df = pd.DataFrame(list(speaker_words.items()),columns=["Speaker","Words"]).sort_values("Words",ascending=False)
                                    fig_words = go.Figure(go.Bar(y=words_df["Speaker"],x=words_df["Words"],orientation="h",marker_color="#E67E22",text=words_df["Words"],textposition="outside"))
                                    words_max = words_df["Words"].max() if not words_df.empty else 1
                                    fig_words.update_layout(title="Word Count per Participant",height=360,plot_bgcolor="white",paper_bgcolor="white",
                                                            margin=dict(l=150,r=80,t=40,b=40),
                                                            xaxis=dict(range=[0, words_max * 1.35]))
                                    st.plotly_chart(fig_words)
                                if justice_questions:
                                    st.subheader("Questions Asked by Each Justice")
                                    jq_df = pd.DataFrame(list(justice_questions.items()),columns=["Justice","Questions"]).sort_values("Questions",ascending=False)
                                    fig_jq = go.Figure(go.Bar(x=jq_df["Justice"],y=jq_df["Questions"],marker_color="#9B59B6",text=jq_df["Questions"],textposition="outside"))
                                    jq_max = jq_df["Questions"].max() if not jq_df.empty else 1
                                    fig_jq.update_layout(title="Questions Detected in Oral Argument Transcript",height=340,
                                                         yaxis=dict(title="Question Count", range=[0, jq_max * 1.25]),
                                                         margin=dict(t=50,b=80,l=20,r=20),
                                                         plot_bgcolor="white",paper_bgcolor="white")
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

# ── Page ─────────────────────────────────────────────────────────────────────
_tab_0, _tab_1 = st.tabs(["👨‍⚖️ Justices", "⚖️ Advocates & Arguments"])
with _tab_0:
    _page_justices()
with _tab_1:
    _page_advocates()


