import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import requests
from utils.charts import build_journey_diagram, build_voting_chart
from utils.oyez_api import extract_court_journey

st.set_page_config(page_title="Landmark Cases", page_icon="⭐", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}

# Curated landmark cases: (display name, Oyez href, category, one-line significance)
LANDMARK_CASES = {
    "Free Speech & Press": [
        ("New York Times v. Sullivan (1964)", "https://api.oyez.org/cases/1963/39",
         "Established 'actual malice' standard for defamation of public officials."),
        ("Brandenburg v. Ohio (1969)", "https://api.oyez.org/cases/1968/492",
         "Protected inflammatory speech unless it incites imminent lawless action."),
        ("Snyder v. Phelps (2011)", "https://api.oyez.org/cases/2010/09-751",
         "Protected Westboro Baptist Church's funeral protests as free speech."),
    ],
    "Privacy & Civil Liberties": [
        ("Griswold v. Connecticut (1965)", "https://api.oyez.org/cases/1964/496",
         "Recognized a constitutional right to marital privacy."),
        ("Roe v. Wade (1973)", "https://api.oyez.org/cases/1971/70-18",
         "Recognized a woman's constitutional right to abortion."),
        ("Dobbs v. Jackson Women's Health (2022)", "https://api.oyez.org/cases/2021/19-1392",
         "Overturned Roe v. Wade; returned abortion regulation to the states."),
    ],
    "Equal Protection & Civil Rights": [
        ("Brown v. Board of Education (1954)", "https://api.oyez.org/cases/1953/1",
         "Declared racial segregation in public schools unconstitutional."),
        ("Loving v. Virginia (1967)", "https://api.oyez.org/cases/1966/395",
         "Struck down laws prohibiting interracial marriage."),
        ("Obergefell v. Hodges (2015)", "https://api.oyez.org/cases/2014/14-556",
         "Recognized same-sex couples' constitutional right to marry."),
    ],
    "Criminal Procedure": [
        ("Miranda v. Arizona (1966)", "https://api.oyez.org/cases/1965/759",
         "Required police to inform suspects of their rights before interrogation."),
        ("Mapp v. Ohio (1961)", "https://api.oyez.org/cases/1960/236",
         "Applied the exclusionary rule to the states."),
        ("Gideon v. Wainwright (1963)", "https://api.oyez.org/cases/1962/155",
         "Guaranteed the right to counsel in all felony criminal cases."),
    ],
    "Government Powers & Federalism": [
        ("Marbury v. Madison (1803)", "https://api.oyez.org/cases/1789-1850/5us137",
         "Established the principle of judicial review."),
        ("McCulloch v. Maryland (1819)", "https://api.oyez.org/cases/1789-1850/17us316",
         "Affirmed Congress's implied powers and federal supremacy over states."),
        ("Citizens United v. FEC (2010)", "https://api.oyez.org/cases/2008/08-205",
         "Ruled political spending by corporations is protected free speech."),
    ],
    "Search & Seizure": [
        ("Katz v. United States (1967)", "https://api.oyez.org/cases/1967/35",
         "Extended Fourth Amendment protections to electronic surveillance."),
        ("Riley v. California (2014)", "https://api.oyez.org/cases/2013/13-132",
         "Required police to get a warrant before searching a cell phone."),
        ("Carpenter v. United States (2018)", "https://api.oyez.org/cases/2017/16-402",
         "Required warrants for cell-site location data."),
    ],
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
st.title("⭐ Landmark Cases Explorer")
st.markdown(
    "A curated collection of landmark Supreme Court rulings. "
    "Select any case to see its full court journey, justice votes, and key facts."
)

category = st.selectbox("Legal Category", list(LANDMARK_CASES.keys()))
cases_in_cat = LANDMARK_CASES[category]

case_options = [c[0] for c in cases_in_cat]
selected_label = st.selectbox("Select a Landmark Case", case_options)
selected = next(c for c in cases_in_cat if c[0] == selected_label)
case_name, case_href, significance = selected

st.info(f"**Why it matters:** {significance}")

with st.spinner("Loading case from Oyez..."):
    detail = fetch_case(case_href)

if not detail:
    st.error("Could not load this case from Oyez. It may have moved. Try refreshing.")
    st.stop()

# ── Case header ───────────────────────────────────────────────────────────────
col_hdr, col_meta = st.columns([2, 1])
with col_hdr:
    st.subheader(detail.get("name", case_name))
    facts = detail.get("facts_of_the_case", "") or detail.get("description", "")
    if facts:
        with st.expander("Facts of the Case", expanded=True):
            st.write(facts)
    question = detail.get("question", "")
    if question:
        with st.expander("Legal Question"):
            st.write(question)
    conclusion = detail.get("conclusion", "")
    if conclusion:
        with st.expander("Court's Conclusion"):
            st.write(conclusion)

with col_meta:
    st.markdown("**Case Details**")
    st.markdown(f"- **Docket:** {detail.get('docket_number', 'N/A')}")
    decided_by = detail.get("decided_by") or {}
    if decided_by:
        st.markdown(f"- **Decided by:** {decided_by.get('name', 'N/A')}")
    disposition = detail.get("disposition") or {}
    if isinstance(disposition, dict) and disposition.get("label"):
        st.markdown(f"- **Disposition:** {disposition['label']}")
    argued = detail.get("argued_on", [])
    if argued:
        arg_val = argued[0]
        arg_str = arg_val.get("date", "") if isinstance(arg_val, dict) else str(arg_val)
        st.markdown(f"- **Argued:** {arg_str}")
    decided = detail.get("decided_on", [])
    if decided:
        dec_val = decided[0]
        dec_str = dec_val.get("date", "") if isinstance(dec_val, dict) else str(dec_val)
        st.markdown(f"- **Decided:** {dec_str}")

st.divider()

# ── Journey diagram ───────────────────────────────────────────────────────────
st.subheader("⬆️ Court Journey")
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
    if dispo_label and steps:
        steps[-1]["decision"] = dispo_label
    fig = build_journey_diagram(steps, detail.get("name", case_name))
    if fig:
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Court journey data not available for this case.")

st.divider()

# ── Justice votes ─────────────────────────────────────────────────────────────
st.subheader("⚖️ Justice Votes")
justices = []
for dec in detail.get("decisions", []):
    winning_party = dec.get("winning_party", "")
    for vote in dec.get("votes", []):
        member = vote.get("member", {}) or {}
        justices.append({
            "name": member.get("name", "Unknown"),
            "vote": vote.get("vote", ""),
            "winning_party": winning_party,
        })

if justices:
    fig2 = build_voting_chart(justices)
    if fig2:
        st.plotly_chart(fig2, use_container_width=True)
    majority = [j["name"] for j in justices if (j.get("vote") or "").lower() in ("majority", "concurrence")]
    dissent = [j["name"] for j in justices if (j.get("vote") or "").lower() == "dissent"]
    winning = justices[0].get("winning_party", "") if justices else ""
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**✅ Majority ({len(majority)}):**")
        for n in majority:
            st.markdown(f"- {n}")
    with c2:
        st.markdown(f"**❌ Dissent ({len(dissent)}):**")
        if dissent:
            for n in dissent:
                st.markdown(f"- {n}")
        else:
            st.markdown("_Unanimous_")
    with c3:
        if winning:
            st.markdown(f"**🏆 Winning Party:**")
            st.markdown(winning)
else:
    st.info("Voting data not available for this case.")

# ── Oral arguments ────────────────────────────────────────────────────────────
oral_args = detail.get("oral_argument_audio", [])
if oral_args:
    st.divider()
    st.subheader("🎙️ Oral Arguments")
    for arg in oral_args[:2]:
        if isinstance(arg, dict) and arg.get("href"):
            st.markdown(f"[{arg.get('title', 'Listen to oral argument')}]({arg['href']})")
