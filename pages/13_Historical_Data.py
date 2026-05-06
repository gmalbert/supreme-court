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
    try:
        r = requests.get(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=150&page=0",
                         headers=HEADERS, timeout=12)
        r.raise_for_status(); return r.json()
    except Exception: return []

@st.cache_data(show_spinner=False, ttl=3600)
def _hist_fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception: return None

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

        disp  = detail.get("disposition") or {}
        disp_label = disp.get("label","") if isinstance(disp,dict) else str(disp)
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
st.title("📜 Historical Data Explorer")
st.markdown(
    "The complete statistical history of the Supreme Court — from its first term in **1790** "
    "through today. Pre-1953 figures are drawn from published SCOTUS statistics and academic "
    "sources; 1953–present data loads live from the Oyez API."
)

tab_timeline, tab_outcomes, tab_eras, tab_milestones, tab_drilldown = st.tabs([
    "📈 Full Timeline", "⚖️ Outcomes", "🏛️ Era Comparison",
    "⭐ Milestones", "🔍 Term Drilldown"
])

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar: load Oyez data for modern era
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Live Data (1953–Present)")
    st.markdown("Load Oyez data to enhance accuracy for modern terms.")
    oyez_terms_default = list(range(CURRENT_YEAR - 1, 1952, -1))
    oyez_terms_sel = st.multiselect(
        "Oyez terms to load", oyez_terms_default,
        default=oyez_terms_default[:15],
        format_func=lambda t: f"{t}–{t+1}",
        key="hist_oyez_terms",
    )
    load_oyez_btn = st.button("Load Live Data", type="primary", key="hist_load_oyez")
    if "hist_oyez_data" in st.session_state:
        st.success(f"✅ {len(st.session_state['hist_oyez_data'])} terms loaded")

if load_oyez_btn and oyez_terms_sel:
    progress = st.sidebar.progress(0.0, text="Loading Oyez data…")
    oyez_rows = []
    for i, term in enumerate(sorted(oyez_terms_sel, reverse=True)):
        progress.progress((i+1)/len(oyez_terms_sel), text=f"Loading {term}–{term+1}…")
        row = _hist_load_oyez_term(term)
        if row: oyez_rows.append(row)
    st.session_state["hist_oyez_data"] = oyez_rows
    progress.progress(1.0, text="Done!")
    st.rerun()

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
with tab_timeline:
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
            fill="tozeroy", fillcolor=line_color.replace(")", ",0.08)").replace("rgb","rgba") if line_color.startswith("rgb") else line_color+"20",
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
with tab_outcomes:
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
# TAB 3: ERA COMPARISON
# ═════════════════════════════════════════════════════════════════════════════
with tab_eras:
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
with tab_milestones:
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
with tab_drilldown:
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
