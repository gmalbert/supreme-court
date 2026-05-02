import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import datetime
from collections import defaultdict

st.set_page_config(page_title="Constitutional Provisions Tracker", page_icon="📜", layout="wide")

# ── Curated constitutional provisions and landmark cases ─────────────────────
# Each provision: id, short_name, full_text, article_amendment, color
PROVISIONS = [
    ("free_speech",    "Free Speech",         "First Amendment — Freedom of Speech & Press",          "Amendment I",   "#E74C3C"),
    ("establishment",  "Establishment Clause","First Amendment — Establishment of Religion",           "Amendment I",   "#E67E22"),
    ("free_exercise",  "Free Exercise",       "First Amendment — Free Exercise of Religion",           "Amendment I",   "#F39C12"),
    ("search_seizure", "Search & Seizure",    "Fourth Amendment — Unreasonable Searches & Seizures",   "Amendment IV",  "#27AE60"),
    ("self_incrim",    "Self-Incrimination",  "Fifth Amendment — Right Against Self-Incrimination",    "Amendment V",   "#1ABC9C"),
    ("due_process_5",  "Due Process (5th)",   "Fifth Amendment — Due Process of Law",                  "Amendment V",   "#16A085"),
    ("takings",        "Takings Clause",      "Fifth Amendment — Just Compensation / Takings",         "Amendment V",   "#2ECC71"),
    ("right_counsel",  "Right to Counsel",    "Sixth Amendment — Right to Counsel",                    "Amendment VI",  "#3498DB"),
    ("confrontation",  "Confrontation",       "Sixth Amendment — Confrontation Clause",                "Amendment VI",  "#2980B9"),
    ("cruel_unusual",  "Cruel & Unusual",     "Eighth Amendment — Cruel and Unusual Punishment",       "Amendment VIII","#9B59B6"),
    ("equal_prot",     "Equal Protection",    "Fourteenth Amendment — Equal Protection Clause",        "Amendment XIV", "#8E44AD"),
    ("due_process_14", "Due Process (14th)",  "Fourteenth Amendment — Due Process / Incorporation",    "Amendment XIV", "#6C3483"),
    ("second_amend",   "Second Amendment",    "Second Amendment — Right to Keep and Bear Arms",        "Amendment II",  "#D35400"),
    ("commerce",       "Commerce Clause",     "Article I, § 8 — Commerce Clause",                     "Article I",     "#C0392B"),
    ("spending",       "Spending Clause",     "Article I, § 8 — Spending Clause",                     "Article I",     "#E74C3C"),
    ("tenth_amend",    "Tenth Amendment",     "Tenth Amendment — Reserved Powers / Federalism",        "Amendment X",   "#7F8C8D"),
    ("eleventh_amend", "Eleventh Amendment",  "Eleventh Amendment — State Sovereign Immunity",         "Amendment XI",  "#95A5A6"),
    ("free_press",     "Freedom of Press",    "First Amendment — Freedom of Press",                    "Amendment I",   "#E74C3C"),
]

PROV_MAP = {p[0]: p for p in PROVISIONS}

# Curated landmark cases mapped to provisions
# (case_name, year, provisions_list, holding_summary, significance)
LANDMARK_CASES = [
    # Free Speech
    ("Schenck v. United States",           1919, ["free_speech"], "Clear and present danger test upheld speech restrictions during wartime.", 3),
    ("Brandenburg v. Ohio",                1969, ["free_speech"], "Imminent lawless action test replaced clear and present danger.", 5),
    ("Texas v. Johnson",                   1989, ["free_speech"], "Flag burning is protected symbolic speech.", 5),
    ("Citizens United v. FEC",             2010, ["free_speech"], "Political spending by corporations is protected speech.", 5),
    ("Snyder v. Phelps",                   2011, ["free_speech"], "Westboro Baptist Church protests near military funerals are protected.", 4),
    ("Matal v. Tam",                       2017, ["free_speech"], "Government may not deny trademarks on 'disparaging' grounds.", 4),
    ("303 Creative v. Elenis",             2023, ["free_speech", "equal_prot"], "Designer cannot be compelled to create websites for same-sex weddings.", 4),
    ("Counterman v. Colorado",             2023, ["free_speech"], "True threats require subjective recklessness, not objective standard.", 4),
    ("Moody v. NetChoice",                 2024, ["free_speech"], "Social media platform content moderation laws sent back for review.", 4),

    # Establishment / Free Exercise
    ("Engel v. Vitale",                    1962, ["establishment"], "School-sponsored prayer violates Establishment Clause.", 5),
    ("Lemon v. Kurtzman",                  1971, ["establishment"], "Three-part Lemon test established for Establishment Clause cases.", 5),
    ("Lee v. Weisman",                     1992, ["establishment"], "Clergy-led prayer at public school graduation is unconstitutional.", 4),
    ("Town of Greece v. Galloway",         2014, ["establishment"], "Legislative prayer before town board meetings is constitutional.", 4),
    ("Kennedy v. Bremerton School District",2022,["establishment","free_exercise"], "Public school coach's personal prayer on field is protected.", 5),
    ("Employment Division v. Smith",       1990, ["free_exercise"], "Neutral, generally applicable laws may burden religion without exemption.", 5),
    ("Church of Lukumi v. Hialeah",        1993, ["free_exercise"], "Laws targeting religion specifically are unconstitutional.", 4),
    ("Burwell v. Hobby Lobby",             2014, ["free_exercise"], "Closely-held corporations may claim religious exemptions under RFRA.", 5),
    ("Fulton v. City of Philadelphia",     2021, ["free_exercise"], "City cannot exclude Catholic Social Services from foster care program.", 4),

    # Fourth Amendment
    ("Mapp v. Ohio",                       1961, ["search_seizure"], "Exclusionary rule applies to states via 14th Amendment.", 5),
    ("Katz v. United States",              1967, ["search_seizure"], "Wiretapping phone booth requires warrant; reasonable expectation of privacy.", 5),
    ("Terry v. Ohio",                      1968, ["search_seizure"], "Stop-and-frisk constitutional under reasonable suspicion standard.", 5),
    ("United States v. Jones",             2012, ["search_seizure"], "GPS tracking of vehicle constitutes a search under 4th Amendment.", 4),
    ("Riley v. California",                2014, ["search_seizure"], "Police must get warrant to search cell phone contents after arrest.", 5),
    ("Carpenter v. United States",         2018, ["search_seizure"], "Warrant required for historical cell-site location information.", 5),
    ("Caniglia v. Strom",                  2021, ["search_seizure"], "No broad 'community caretaking' exception to warrant requirement.", 4),

    # Fifth Amendment
    ("Miranda v. Arizona",                 1966, ["self_incrim", "due_process_5"], "Police must inform suspects of rights before custodial interrogation.", 5),
    ("Kelo v. City of New London",         2005, ["takings"], "Economic development qualifies as public use under Takings Clause.", 5),
    ("Murr v. Wisconsin",                  2017, ["takings"], "Established framework for regulatory takings claims.", 4),
    ("Cedar Point Nursery v. Hassid",      2021, ["takings"], "Regulation granting union access to private property is per se taking.", 4),

    # Sixth Amendment
    ("Gideon v. Wainwright",               1963, ["right_counsel"], "Right to counsel incorporated against states via 14th Amendment.", 5),
    ("Crawford v. Washington",             2004, ["confrontation"], "Testimonial statements of absent witnesses require prior cross-examination.", 5),
    ("Strickland v. Washington",           1984, ["right_counsel"], "Two-part test for ineffective assistance of counsel claims.", 5),

    # Eighth Amendment
    ("Furman v. Georgia",                  1972, ["cruel_unusual"], "Death penalty as then applied was unconstitutional.", 5),
    ("Gregg v. Georgia",                   1976, ["cruel_unusual"], "Death penalty itself is not per se unconstitutional.", 5),
    ("Atkins v. Virginia",                 2002, ["cruel_unusual"], "Executing intellectually disabled persons is unconstitutional.", 5),
    ("Roper v. Simmons",                   2005, ["cruel_unusual"], "Executing juvenile offenders violates Eighth Amendment.", 5),
    ("Graham v. Florida",                  2010, ["cruel_unusual"], "Life without parole for non-homicide juvenile offenses is unconstitutional.", 4),
    ("Kennedy v. Louisiana",               2008, ["cruel_unusual"], "Death penalty for child rape where victim survives is unconstitutional.", 4),

    # Equal Protection / 14th Amendment
    ("Brown v. Board of Education",        1954, ["equal_prot"], "Racial segregation in public schools is unconstitutional.", 5),
    ("Loving v. Virginia",                 1967, ["equal_prot", "due_process_14"], "Anti-miscegenation laws violate Equal Protection and Due Process.", 5),
    ("Reed v. Reed",                       1971, ["equal_prot"], "Sex discrimination must bear rational relationship to state objective.", 4),
    ("Craig v. Boren",                     1976, ["equal_prot"], "Intermediate scrutiny standard established for sex-based classifications.", 4),
    ("Regents of UC v. Bakke",             1978, ["equal_prot"], "Racial quotas in admissions unconstitutional; diversity may be considered.", 5),
    ("Grutter v. Bollinger",               2003, ["equal_prot"], "Race may be a factor in university admissions to achieve diversity.", 5),
    ("SFFA v. Harvard",                    2023, ["equal_prot"], "Race-conscious admissions programs at Harvard and UNC unconstitutional.", 5),
    ("United States v. Windsor",           2013, ["equal_prot", "due_process_5"], "DOMA's definition of marriage unconstitutional.", 5),
    ("Obergefell v. Hodges",               2015, ["equal_prot", "due_process_14"], "Same-sex couples have fundamental right to marry.", 5),

    # Due Process / Privacy
    ("Griswold v. Connecticut",            1965, ["due_process_14"], "Right to marital privacy for contraceptives implied by Bill of Rights.", 5),
    ("Roe v. Wade",                        1973, ["due_process_14"], "Abortion is protected under right to privacy.", 5),
    ("Planned Parenthood v. Casey",        1992, ["due_process_14"], "Undue burden standard replaces trimester framework for abortion.", 5),
    ("Lawrence v. Texas",                  2003, ["due_process_14"], "State sodomy laws violate Due Process liberty interest.", 5),
    ("Dobbs v. Jackson Women's Health",    2022, ["due_process_14"], "Constitution does not confer right to abortion; Roe overruled.", 5),
    ("Substantive Due Process",            1905, ["due_process_14"], "Lochner era: liberty of contract protected under Due Process.", 4),

    # Second Amendment
    ("United States v. Miller",            1939, ["second_amend"], "Sawed-off shotguns lack military use; 2nd Amend. not violated.", 4),
    ("DC v. Heller",                       2008, ["second_amend"], "Second Amendment protects individual right to keep firearms at home.", 5),
    ("McDonald v. City of Chicago",        2010, ["second_amend"], "Second Amendment incorporated against states via 14th Amendment.", 5),
    ("NY State Rifle & Pistol v. Bruen",   2022, ["second_amend"], "Historical tradition test replaces means-ends scrutiny for 2nd Amend.", 5),
    ("Garland v. Cargill",                 2024, ["second_amend"], "Bump stocks do not convert rifles to machine guns; ATF rule vacated.", 4),
    ("United States v. Rahimi",            2024, ["second_amend"], "Domestic violence restraining order gun ban constitutional.", 4),

    # Commerce Clause
    ("NLRB v. Jones & Laughlin Steel",     1937, ["commerce"], "Broad commerce power upheld New Deal labor regulations.", 5),
    ("Wickard v. Filburn",                 1942, ["commerce"], "Growing wheat for personal use affects interstate commerce.", 5),
    ("Heart of Atlanta Motel v. US",       1964, ["commerce"], "Civil Rights Act reaches private discrimination via Commerce Clause.", 5),
    ("Lopez v. United States",             1995, ["commerce"], "Gun-Free School Zones Act exceeds commerce power; first limit in 60 years.", 5),
    ("Morrison v. United States",          2000, ["commerce"], "Violence Against Women Act civil remedy exceeds commerce power.", 4),
    ("Gonzales v. Raich",                  2005, ["commerce"], "Federal drug law applies to home-grown medical marijuana.", 4),
    ("NFIB v. Sebelius",                   2012, ["commerce", "spending"], "ACA individual mandate exceeds commerce power; upheld as tax.", 5),

    # Federalism / 10th Amendment
    ("McCulloch v. Maryland",              1819, ["tenth_amend", "commerce"], "Necessary and Proper Clause gives Congress implied powers.", 5),
    ("New York v. United States",          1992, ["tenth_amend"], "Federal government cannot 'commandeer' state legislatures.", 5),
    ("Printz v. United States",            1997, ["tenth_amend"], "Federal government cannot commandeer state executive officers.", 5),
    ("Shelby County v. Holder",            2013, ["tenth_amend", "equal_prot"], "VRA preclearance formula found unconstitutional as outdated.", 5),

    # Administrative Law (not a single provision, using Commerce)
    ("Chevron v. NRDC",                    1984, ["commerce"], "Courts defer to reasonable agency interpretations of ambiguous statutes.", 5),
    ("West Virginia v. EPA",               2022, ["commerce"], "Major questions doctrine limits EPA's broad regulatory authority.", 5),
    ("Loper Bright v. Raimondo",           2024, ["commerce"], "Chevron deference overruled; courts interpret statutes independently.", 5),
]

CASE_MAP = {c[0]: c for c in LANDMARK_CASES}

CURRENT_YEAR = datetime.date.today().year

# ── Helper ─────────────────────────────────────────────────────────────────────
def provision_label(pid: str) -> str:
    return PROV_MAP.get(pid, ("", pid, "", "", ""))[1]

def provision_color(pid: str) -> str:
    return PROV_MAP.get(pid, ("", "", "", "", "#95A5A6"))[4]

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📜 Constitutional Provisions Tracker")
st.markdown(
    "Explore which constitutional provisions have generated the most landmark litigation, "
    "trace how the Court's interpretation of each clause has evolved over time, "
    "and find the major cases that shaped each provision."
)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    amendment_options = sorted(set(p[3] for p in PROVISIONS))
    sel_amendments = st.multiselect("Filter by Article / Amendment",
                                    amendment_options, default=amendment_options)
    year_range = st.slider("Year range", 1800, CURRENT_YEAR, (1900, CURRENT_YEAR))
    min_sig = st.slider("Min. significance (1–5 stars)", 1, 5, 3)

all_prov_ids = [p[0] for p in PROVISIONS if p[3] in sel_amendments]
filtered_cases = [
    c for c in LANDMARK_CASES
    if year_range[0] <= c[1] <= year_range[1]
    and c[4] >= min_sig
    and any(pid in all_prov_ids for pid in c[2])
]

tab_overview, tab_provision, tab_timeline, tab_compare = st.tabs([
    "📊 Overview", "🔍 Provision Detail", "📅 Timeline", "⚔️ Cross-Provision"
])

# ── Overview ─────────────────────────────────────────────────────────────────
with tab_overview:
    st.subheader("Most Litigated Constitutional Provisions")

    prov_counts: dict[str, int] = defaultdict(int)
    for c in filtered_cases:
        for pid in c[2]:
            if pid in all_prov_ids:
                prov_counts[pid] += 1

    if prov_counts:
        count_df = pd.DataFrame([
            {"Provision": provision_label(pid), "Cases": cnt,
             "Amendment": PROV_MAP[pid][3], "Color": provision_color(pid)}
            for pid, cnt in sorted(prov_counts.items(), key=lambda x: -x[1])
        ])

        fig_bar = go.Figure(go.Bar(
            x=count_df["Cases"],
            y=count_df["Provision"],
            orientation="h",
            marker_color=count_df["Color"].tolist(),
            text=count_df["Cases"],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} landmark cases<extra></extra>",
        ))
        fig_bar.update_layout(
            title="Landmark Cases per Constitutional Provision",
            height=max(350, len(count_df) * 28),
            xaxis_title="Number of Cases",
            yaxis=dict(autorange="reversed"),
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin=dict(l=160, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Group by amendment
    st.subheader("Cases per Amendment")
    amend_counts: dict[str, int] = defaultdict(int)
    for c in filtered_cases:
        seen_amends: set[str] = set()
        for pid in c[2]:
            amend = PROV_MAP.get(pid, ("","","","",""))[3]
            if amend not in seen_amends:
                amend_counts[amend] += 1
                seen_amends.add(amend)

    amend_df = pd.DataFrame([
        {"Amendment": a, "Cases": n}
        for a, n in sorted(amend_counts.items(), key=lambda x: -x[1])
    ])
    fig_donut = go.Figure(go.Pie(
        labels=amend_df["Amendment"],
        values=amend_df["Cases"],
        hole=0.45,
        textinfo="label+value",
        marker_colors=px.colors.qualitative.Set3,
    ))
    fig_donut.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig_donut, use_container_width=True)

    # Era breakdown
    st.subheader("Cases by Era")
    era_bins = [(1800, 1932, "Pre-New Deal"), (1933, 1952, "New Deal Era"),
                (1953, 1968, "Warren Court"), (1969, 1985, "Burger Court"),
                (1986, 2004, "Rehnquist Court"), (2005, CURRENT_YEAR, "Roberts Court")]
    era_data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in filtered_cases:
        for start, end, era in era_bins:
            if start <= c[1] <= end:
                for pid in c[2]:
                    if pid in all_prov_ids:
                        era_data[era][provision_label(pid)] += 1

    era_rows = []
    for era, pvs in era_data.items():
        for prov, cnt in pvs.items():
            era_rows.append({"Era": era, "Provision": prov, "Cases": cnt})

    if era_rows:
        era_df = pd.DataFrame(era_rows)
        fig_era = px.bar(
            era_df,
            x="Era",
            y="Cases",
            color="Provision",
            barmode="stack",
            title="Cases per Era by Constitutional Provision",
            category_orders={"Era": [e[2] for e in era_bins]},
            color_discrete_sequence=px.colors.qualitative.Alphabet,
        )
        fig_era.update_layout(
            height=380,
            xaxis_tickangle=-20,
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(x=1.01, y=1, font=dict(size=9)),
        )
        st.plotly_chart(fig_era, use_container_width=True)

# ── Provision detail ──────────────────────────────────────────────────────────
with tab_provision:
    st.subheader("Deep Dive: Single Provision")

    visible_provs = [(p[1], p[0]) for p in PROVISIONS if p[0] in all_prov_ids]
    sel_prov_label, sel_prov_id = st.selectbox(
        "Select provision",
        visible_provs,
        format_func=lambda x: x[0],
    )

    prov_data = PROV_MAP[sel_prov_id]
    color = prov_data[4]

    st.markdown(
        f'<div style="border-left:5px solid {color};padding:10px 16px;'
        f'background:#F8F9FA;margin-bottom:16px;">'
        f'<strong style="font-size:1.1em;">{prov_data[2]}</strong>'
        f'</div>',
        unsafe_allow_html=True,
    )

    prov_cases = [c for c in filtered_cases if sel_prov_id in c[2]]
    prov_cases.sort(key=lambda x: x[1])

    st.markdown(f"**{len(prov_cases)} landmark cases** touch this provision (filtered range).")

    if prov_cases:
        stars = lambda n: "★" * n + "☆" * (5 - n)
        for case in prov_cases:
            sig_color = "#E74C3C" if case[4] == 5 else "#E67E22" if case[4] >= 4 else "#27AE60"
            other_provs = [provision_label(pid) for pid in case[2] if pid != sel_prov_id]
            also_str = f"  ·  *Also: {', '.join(other_provs)}*" if other_provs else ""
            st.markdown(
                f'<div style="border-left:3px solid {sig_color};padding:6px 12px;margin-bottom:6px;">'
                f'<strong>{case[0]}</strong> ({case[1]}) '
                f'<span style="color:{sig_color}">{stars(case[4])}</span>'
                f'{also_str}<br>'
                f'<span style="color:#555;">{case[3]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Scatter over time
        pc_df = pd.DataFrame([
            {"Case": c[0], "Year": c[1], "Significance": c[4], "Holding": c[3]}
            for c in prov_cases
        ])
        fig_scatter = px.scatter(
            pc_df, x="Year", y="Significance",
            size="Significance",
            hover_name="Case",
            hover_data={"Year": True, "Holding": True, "Significance": False},
            title=f"{sel_prov_label} — Cases Over Time",
            color_discrete_sequence=[color],
        )
        fig_scatter.update_layout(
            height=280,
            yaxis=dict(title="Significance", range=[0, 6], dtick=1),
            plot_bgcolor="white",
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# ── Timeline ─────────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader("All Cases on a Constitutional Timeline")

    tl_rows = []
    for c in filtered_cases:
        for pid in c[2]:
            if pid in all_prov_ids:
                tl_rows.append({
                    "Case": c[0],
                    "Year": c[1],
                    "Provision": provision_label(pid),
                    "Significance": c[4],
                    "Holding": c[3],
                    "Color": provision_color(pid),
                })

    if tl_rows:
        tl_df = pd.DataFrame(tl_rows)
        fig_tl = px.scatter(
            tl_df,
            x="Year",
            y="Provision",
            size="Significance",
            color="Provision",
            hover_name="Case",
            hover_data={"Year": True, "Holding": True, "Significance": True, "Provision": False},
            title="Constitutional Provisions Litigation Timeline",
            size_max=18,
        )
        fig_tl.update_layout(
            height=max(450, len(all_prov_ids) * 30),
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis=dict(title=""),
            xaxis=dict(title="Year"),
            showlegend=False,
            margin=dict(l=170, r=20, t=40, b=40),
        )
        st.plotly_chart(fig_tl, use_container_width=True)
        st.caption("Dot size = significance rating (1–5). Hover for case name and holding.")

# ── Cross-provision ───────────────────────────────────────────────────────────
with tab_compare:
    st.subheader("Cross-Provision Cases")
    st.markdown(
        "These cases implicate **multiple constitutional provisions**, "
        "highlighting the Court's frequent need to balance competing rights."
    )

    multi = [c for c in filtered_cases if len(c[2]) >= 2
             and all(pid in all_prov_ids for pid in c[2][:2])]
    multi.sort(key=lambda x: (-len(x[2]), -x[4]))

    if multi:
        # Chord / connection summary
        pairs: dict[tuple, int] = defaultdict(int)
        for c in multi:
            pids = [pid for pid in c[2] if pid in all_prov_ids]
            for i in range(len(pids)):
                for j in range(i+1, len(pids)):
                    key = (min(pids[i], pids[j]), max(pids[i], pids[j]))
                    pairs[key] += 1

        pair_rows = [
            {"Provision A": provision_label(a), "Provision B": provision_label(b), "Shared Cases": n}
            for (a, b), n in sorted(pairs.items(), key=lambda x: -x[1])
        ]
        pair_df = pd.DataFrame(pair_rows)

        fig_pairs = px.bar(
            pair_df.head(12),
            x="Shared Cases",
            y=pair_df.head(12).apply(lambda r: f"{r['Provision A']} ↔ {r['Provision B']}", axis=1),
            orientation="h",
            title="Most Common Provision Pairings in Single Cases",
            color="Shared Cases",
            color_continuous_scale="Viridis",
        )
        fig_pairs.update_layout(
            height=380,
            coloraxis_showscale=False,
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis=dict(autorange="reversed"),
            margin=dict(l=240, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_pairs, use_container_width=True)

        st.markdown("**Notable Multi-Provision Cases**")
        for c in multi[:20]:
            pids_shown = [pid for pid in c[2] if pid in all_prov_ids]
            badges = "  ".join(
                f'<span style="background:{provision_color(pid)};color:white;'
                f'padding:2px 7px;border-radius:3px;font-size:0.8em;">'
                f'{provision_label(pid)}</span>'
                for pid in pids_shown
            )
            st.markdown(
                f'<div style="padding:7px 0;border-bottom:1px solid #ECF0F1;">'
                f'<strong>{c[0]}</strong> ({c[1]})<br>'
                f'{badges}<br>'
                f'<span style="color:#555;font-size:0.9em;">{c[3]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No multi-provision cases match your current filters.")

    st.divider()

    # Full searchable case table
    st.subheader("Search All Cases")
    search_q = st.text_input("Search by case name or holding keyword")
    search_src = filtered_cases
    if search_q:
        q = search_q.lower()
        search_src = [c for c in search_src
                      if q in c[0].lower() or q in c[3].lower()]

    for c in sorted(search_src, key=lambda x: -x[1]):
        pids_shown = [pid for pid in c[2] if pid in all_prov_ids]
        badges = "  ".join(
            f'<span style="background:{provision_color(pid)};color:white;'
            f'padding:2px 6px;border-radius:3px;font-size:0.78em;">'
            f'{provision_label(pid)}</span>'
            for pid in pids_shown
        )
        st.markdown(
            f'<div style="padding:5px 0;border-bottom:1px solid #F0F0F0;">'
            f'<strong>{c[0]}</strong> ({c[1]}) '
            f'{"★"*c[4]}{"☆"*(5-c[4])}<br>'
            f'{badges}<br>'
            f'<span style="color:#555;font-size:0.88em;">{c[3]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
