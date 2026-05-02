import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from utils.charts import build_journey_diagram, build_voting_chart
from utils.oyez_api import extract_court_journey

st.set_page_config(page_title="Constitutional Amendments Tracker", page_icon="📜", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}

# Mapping of amendment → curated landmark cases
# (display name, oyez href, one-line holding, year)
AMENDMENTS = {
    "1st Amendment — Free Speech, Press, Religion, Assembly": {
        "summary": "Prohibits Congress from abridging freedom of speech, press, religion, or peaceful assembly.",
        "color": "#2980B9",
        "cases": [
            ("Schenck v. United States (1919)", "https://api.oyez.org/cases/1900-1940/249us47",
             "Upheld conviction for anti-draft pamphlets; established 'clear and present danger' test.", 1919),
            ("New York Times v. Sullivan (1964)", "https://api.oyez.org/cases/1963/39",
             "Required 'actual malice' for defamation claims by public officials.", 1964),
            ("Brandenburg v. Ohio (1969)", "https://api.oyez.org/cases/1968/492",
             "Protected inflammatory speech unless directed to incite imminent lawless action.", 1969),
            ("Texas v. Johnson (1989)", "https://api.oyez.org/cases/1988/88-155",
             "Flag burning is protected symbolic speech under the First Amendment.", 1989),
            ("Citizens United v. FEC (2010)", "https://api.oyez.org/cases/2008/08-205",
             "Corporate political spending is protected speech; struck down campaign finance limits.", 2010),
            ("Snyder v. Phelps (2011)", "https://api.oyez.org/cases/2010/09-751",
             "Protected Westboro Baptist Church's anti-gay funeral protests as public concern speech.", 2011),
        ],
    },
    "2nd Amendment — Right to Bear Arms": {
        "summary": "Protects the individual right to keep and bear arms, as interpreted by SCOTUS since 2008.",
        "color": "#8E44AD",
        "cases": [
            ("District of Columbia v. Heller (2008)", "https://api.oyez.org/cases/2007/07-290",
             "Recognized an individual's right to possess firearms independent of militia service.", 2008),
            ("McDonald v. City of Chicago (2010)", "https://api.oyez.org/cases/2009/08-1521",
             "Incorporated the Second Amendment against state and local governments.", 2010),
            ("New York State Rifle & Pistol Assn. v. Bruen (2022)", "https://api.oyez.org/cases/2021/20-843",
             "Struck down NY's 'proper cause' requirement for concealed carry permits.", 2022),
        ],
    },
    "4th Amendment — Search & Seizure": {
        "summary": "Guards against unreasonable searches and seizures; requires warrants based on probable cause.",
        "color": "#E67E22",
        "cases": [
            ("Mapp v. Ohio (1961)", "https://api.oyez.org/cases/1960/236",
             "Applied the exclusionary rule to the states — illegally seized evidence inadmissible.", 1961),
            ("Katz v. United States (1967)", "https://api.oyez.org/cases/1967/35",
             "Extended 4th Amendment to electronic surveillance; created 'reasonable expectation of privacy'.", 1967),
            ("Terry v. Ohio (1968)", "https://api.oyez.org/cases/1967/67",
             "Permitted police 'stop and frisk' based on reasonable suspicion, not full probable cause.", 1968),
            ("United States v. Jones (2012)", "https://api.oyez.org/cases/2011/10-1259",
             "Attaching a GPS device to a vehicle constitutes a search under the 4th Amendment.", 2012),
            ("Riley v. California (2014)", "https://api.oyez.org/cases/2013/13-132",
             "Police must obtain a warrant before searching a cell phone incident to arrest.", 2014),
            ("Carpenter v. United States (2018)", "https://api.oyez.org/cases/2017/16-402",
             "Government needs a warrant to access historical cell-site location information.", 2018),
        ],
    },
    "5th Amendment — Due Process, Self-Incrimination": {
        "summary": "Prohibits double jeopardy, self-incrimination, and deprivation of life/liberty/property without due process.",
        "color": "#C0392B",
        "cases": [
            ("Miranda v. Arizona (1966)", "https://api.oyez.org/cases/1965/759",
             "Police must inform suspects of their rights before custodial interrogation.", 1966),
            ("Kelo v. City of New London (2005)", "https://api.oyez.org/cases/2004/04-108",
             "Upheld government's use of eminent domain for economic development (takings clause).", 2005),
        ],
    },
    "6th Amendment — Right to Counsel & Fair Trial": {
        "summary": "Guarantees the right to a speedy trial, impartial jury, and assistance of counsel.",
        "color": "#27AE60",
        "cases": [
            ("Gideon v. Wainwright (1963)", "https://api.oyez.org/cases/1962/155",
             "States must provide counsel to criminal defendants who cannot afford an attorney.", 1963),
            ("Crawford v. Washington (2004)", "https://api.oyez.org/cases/2003/02-9410",
             "Testimonial statements of absent witnesses are inadmissible unless defendant had prior cross-examination.", 2004),
        ],
    },
    "8th Amendment — Cruel & Unusual Punishment": {
        "summary": "Prohibits excessive bail, excessive fines, and cruel and unusual punishment.",
        "color": "#E74C3C",
        "cases": [
            ("Furman v. Georgia (1972)", "https://api.oyez.org/cases/1971/69-5003",
             "Struck down existing death penalty statutes as arbitrary and therefore unconstitutional.", 1972),
            ("Gregg v. Georgia (1976)", "https://api.oyez.org/cases/1975/74-6257",
             "Upheld revised death penalty statutes with guided discretion.", 1976),
            ("Atkins v. Virginia (2002)", "https://api.oyez.org/cases/2001/00-8452",
             "Executing intellectually disabled persons is unconstitutional.", 2002),
            ("Roper v. Simmons (2005)", "https://api.oyez.org/cases/2004/03-633",
             "Death penalty for crimes committed while under 18 is unconstitutional.", 2005),
        ],
    },
    "14th Amendment — Equal Protection & Due Process": {
        "summary": "Grants citizenship, equal protection, and due process rights; used to incorporate the Bill of Rights against the states.",
        "color": "#F39C12",
        "cases": [
            ("Brown v. Board of Education (1954)", "https://api.oyez.org/cases/1953/1",
             "Racial segregation in public schools is unconstitutional under equal protection.", 1954),
            ("Loving v. Virginia (1967)", "https://api.oyez.org/cases/1966/395",
             "Laws prohibiting interracial marriage violate the Equal Protection and Due Process Clauses.", 1967),
            ("Roe v. Wade (1973)", "https://api.oyez.org/cases/1971/70-18",
             "Recognized a woman's right to abortion under the Due Process Clause.", 1973),
            ("Grutter v. Bollinger (2003)", "https://api.oyez.org/cases/2002/02-241",
             "Upheld race-conscious admissions at University of Michigan Law School.", 2003),
            ("Obergefell v. Hodges (2015)", "https://api.oyez.org/cases/2014/14-556",
             "Same-sex couples have a fundamental right to marry under the 14th Amendment.", 2015),
            ("Dobbs v. Jackson Women's Health (2022)", "https://api.oyez.org/cases/2021/19-1392",
             "Overturned Roe v. Wade; the Constitution does not confer a right to abortion.", 2022),
            ("Students for Fair Admissions v. Harvard (2023)", "https://api.oyez.org/cases/2022/20-1199",
             "Race-conscious admissions programs at Harvard and UNC are unconstitutional.", 2023),
        ],
    },
}

@st.cache_data(show_spinner=False)
def fetch_case(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📜 Constitutional Amendments Tracker")
st.markdown(
    "Map landmark SCOTUS rulings to the constitutional amendment they interpreted. "
    "See how each amendment's meaning has evolved over time through the cases that shaped it."
)

# ── Amendment selector ────────────────────────────────────────────────────────
amendment = st.selectbox("Select an Amendment", list(AMENDMENTS.keys()))
amend_data = AMENDMENTS[amendment]
color = amend_data["color"]

st.markdown(f"> {amend_data['summary']}")
st.divider()

cases = amend_data["cases"]

# ── Timeline of cases ─────────────────────────────────────────────────────────
st.subheader("Case Timeline")

years = [c[3] for c in cases]
names = [c[0] for c in cases]
holdings = [c[2] for c in cases]

fig_timeline = go.Figure()
fig_timeline.add_trace(go.Scatter(
    x=years,
    y=[0] * len(years),
    mode="markers+text",
    marker=dict(size=18, color=color, line=dict(width=2, color="white")),
    text=[str(y) for y in years],
    textposition="top center",
    textfont=dict(size=10, color="#2C3E50"),
    hovertext=[f"<b>{n}</b><br>{h}" for n, h in zip(names, holdings)],
    hoverinfo="text",
    showlegend=False,
))
# Baseline
fig_timeline.add_shape(
    type="line",
    x0=min(years) - 5, x1=max(years) + 5,
    y0=0, y1=0,
    line=dict(color="#BDC3C7", width=2),
)
fig_timeline.update_layout(
    height=180,
    xaxis=dict(showgrid=False, zeroline=False, range=[min(years) - 8, max(years) + 8]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-0.5, 0.8]),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig_timeline, use_container_width=True)

st.divider()

# ── Case cards ────────────────────────────────────────────────────────────────
st.subheader("Key Cases")
for i, (name, href, holding, year) in enumerate(cases):
    with st.expander(f"**{name}** — {holding[:80]}{'…' if len(holding) > 80 else ''}"):
        st.markdown(f"**Holding:** {holding}")
        st.markdown(f"**Year:** {year}")

        col_load, _ = st.columns([1, 3])
        with col_load:
            load_key = f"load_{amendment}_{i}"
            if st.button("Load Full Details", key=load_key):
                st.session_state[f"detail_{amendment}_{i}"] = fetch_case(href)

        detail_key = f"detail_{amendment}_{i}"
        if detail_key in st.session_state:
            detail = st.session_state[detail_key]
            if not detail:
                st.warning("Could not load case. Try again.")
                continue

            col_facts, col_meta = st.columns([2, 1])
            with col_facts:
                facts = detail.get("facts_of_the_case", "") or detail.get("description", "")
                if facts:
                    st.markdown("**Facts**")
                    st.write(facts[:800] + ("…" if len(facts or "") > 800 else ""))
                conclusion = detail.get("conclusion", "")
                if conclusion:
                    st.markdown("**Conclusion**")
                    st.write(conclusion[:600] + ("…" if len(conclusion or "") > 600 else ""))

            with col_meta:
                decided_by = detail.get("decided_by") or {}
                if decided_by:
                    st.markdown(f"**Court:** {decided_by.get('name', '')}")
                disposition = detail.get("disposition") or {}
                if isinstance(disposition, dict) and disposition.get("label"):
                    st.markdown(f"**Disposition:** {disposition['label']}")

            # Journey
            steps = extract_court_journey(detail)
            lower = detail.get("lower_court") or {}
            lc_name = lower.get("name", "") if isinstance(lower, dict) else ""
            if len(steps) < 2 and lc_name:
                steps = [
                    {"court": lc_name, "level": "Lower Court", "decision": ""},
                    {"court": "U.S. Supreme Court", "level": "Supreme Court", "decision": ""},
                ]
            if steps:
                dispo_label = (detail.get("disposition") or {}).get("label", "") if isinstance(detail.get("disposition"), dict) else ""
                if dispo_label:
                    steps[-1]["decision"] = dispo_label
                fig_j = build_journey_diagram(steps, detail.get("name", name))
                if fig_j:
                    st.plotly_chart(fig_j, use_container_width=True)

            # Votes
            justices = []
            for dec in detail.get("decisions", []):
                for vote in dec.get("votes", []):
                    member = vote.get("member", {}) or {}
                    justices.append({"name": member.get("name", "?"), "vote": vote.get("vote", "")})
            if justices:
                fig_v = build_voting_chart(justices)
                if fig_v:
                    st.plotly_chart(fig_v, use_container_width=True)
                majority = [j["name"] for j in justices if (j.get("vote") or "").lower() in ("majority", "concurrence")]
                dissent = [j["name"] for j in justices if (j.get("vote") or "").lower() == "dissent"]
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**✅ Majority:** {', '.join(majority)}")
                with c2:
                    st.markdown(f"**❌ Dissent:** {', '.join(dissent) if dissent else 'None (unanimous)'}")

st.divider()

# ── Cross-amendment overview ──────────────────────────────────────────────────
st.subheader("All Amendments — Case Count Overview")
summary_rows = [
    {"Amendment": k.split("—")[0].strip(), "Cases": len(v["cases"]), "Color": v["color"]}
    for k, v in AMENDMENTS.items()
]
summary_df = pd.DataFrame(summary_rows)
fig_overview = go.Figure(go.Bar(
    x=summary_df["Amendment"],
    y=summary_df["Cases"],
    marker_color=summary_df["Color"].tolist(),
    text=summary_df["Cases"],
    textposition="outside",
))
fig_overview.update_layout(
    height=340,
    xaxis_title="",
    yaxis_title="Landmark Cases Tracked",
    plot_bgcolor="white",
    paper_bgcolor="white",
    xaxis_tickangle=-30,
)
st.plotly_chart(fig_overview, use_container_width=True)
st.caption("Showing curated landmark cases per amendment. Coverage is representative, not exhaustive.")
