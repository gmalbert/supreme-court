import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import networkx as nx
import math

st.set_page_config(page_title="Case Network", page_icon="🕸️", layout="wide")

# ── Curated case data ─────────────────────────────────────────────────────────
# Each case: id, display name, year, area, amendment
CASES = {
    "marbury":     ("Marbury v. Madison",           1803, "Judicial Power",       None),
    "mcculloch":   ("McCulloch v. Maryland",         1819, "Federalism",           None),
    "schenck":     ("Schenck v. United States",      1919, "Free Speech",          "1st"),
    "nyt_sullivan":("NY Times v. Sullivan",          1964, "Free Speech",          "1st"),
    "brandenburg": ("Brandenburg v. Ohio",           1969, "Free Speech",          "1st"),
    "texas_johnson":("Texas v. Johnson",             1989, "Free Speech",          "1st"),
    "citizens_utd":("Citizens United v. FEC",        2010, "Free Speech",          "1st"),
    "snyder_phelps":("Snyder v. Phelps",             2011, "Free Speech",          "1st"),
    "heller":      ("D.C. v. Heller",                2008, "Right to Bear Arms",   "2nd"),
    "mcdonald":    ("McDonald v. Chicago",           2010, "Right to Bear Arms",   "2nd"),
    "bruen":       ("NY Rifle & Pistol v. Bruen",    2022, "Right to Bear Arms",   "2nd"),
    "mapp":        ("Mapp v. Ohio",                  1961, "Search & Seizure",     "4th"),
    "katz":        ("Katz v. United States",         1967, "Search & Seizure",     "4th"),
    "terry":       ("Terry v. Ohio",                 1968, "Search & Seizure",     "4th"),
    "jones":       ("United States v. Jones",        2012, "Search & Seizure",     "4th"),
    "riley":       ("Riley v. California",           2014, "Search & Seizure",     "4th"),
    "carpenter":   ("Carpenter v. United States",    2018, "Search & Seizure",     "4th"),
    "miranda":     ("Miranda v. Arizona",            1966, "Self-Incrimination",   "5th"),
    "kelo":        ("Kelo v. City of New London",    2005, "Takings",              "5th"),
    "gideon":      ("Gideon v. Wainwright",          1963, "Right to Counsel",     "6th"),
    "furman":      ("Furman v. Georgia",             1972, "Cruel & Unusual",      "8th"),
    "gregg":       ("Gregg v. Georgia",              1976, "Cruel & Unusual",      "8th"),
    "atkins":      ("Atkins v. Virginia",            2002, "Cruel & Unusual",      "8th"),
    "roper":       ("Roper v. Simmons",              2005, "Cruel & Unusual",      "8th"),
    "griswold":    ("Griswold v. Connecticut",       1965, "Privacy",              "14th"),
    "roe":         ("Roe v. Wade",                   1973, "Privacy",              "14th"),
    "dobbs":       ("Dobbs v. Jackson",              2022, "Privacy",              "14th"),
    "brown":       ("Brown v. Board of Education",   1954, "Equal Protection",     "14th"),
    "loving":      ("Loving v. Virginia",            1967, "Equal Protection",     "14th"),
    "grutter":     ("Grutter v. Bollinger",          2003, "Equal Protection",     "14th"),
    "sffa":        ("SFFA v. Harvard",               2023, "Equal Protection",     "14th"),
    "obergefell":  ("Obergefell v. Hodges",          2015, "Equal Protection",     "14th"),
}

# Edges: (source_id, target_id, relation_type, description)
# Relation types: "Extended", "Overruled", "Relied on", "Distinguished", "Applied"
EDGES = [
    # Judicial review ripple
    ("marbury",      "mcculloch",    "Extended",     "Federal supremacy built on judicial review"),

    # 1st Amendment chain
    ("schenck",      "nyt_sullivan", "Distinguished","Sullivan replaced 'clear and present danger' for press"),
    ("schenck",      "brandenburg",  "Overruled",    "Brandenburg replaced Schenck's 'clear and present danger' test"),
    ("brandenburg",  "texas_johnson","Applied",      "Johnson applied the Brandenburg imminent-lawlessness test"),
    ("nyt_sullivan", "snyder_phelps","Extended",     "Phelps extended public-concern speech protection"),
    ("nyt_sullivan", "citizens_utd", "Relied on",    "Citizens United built on Sullivan's speech-as-protected-expenditure logic"),
    ("texas_johnson","citizens_utd", "Relied on",    "Citizens United cited Johnson for symbolic speech protection"),

    # 2nd Amendment chain
    ("heller",       "mcdonald",     "Extended",     "McDonald incorporated Heller's right against the states"),
    ("heller",       "bruen",        "Extended",     "Bruen expanded Heller; required historical tradition test"),
    ("mcdonald",     "bruen",        "Extended",     "Bruen built on McDonald's incorporation doctrine"),

    # 4th Amendment chain
    ("mapp",         "katz",         "Extended",     "Katz extended Mapp's exclusionary rule to electronic surveillance"),
    ("katz",         "terry",        "Distinguished","Terry allowed stops on reasonable suspicion below Katz's probable cause"),
    ("katz",         "jones",        "Extended",     "Jones applied Katz's reasonable-expectation test to GPS tracking"),
    ("katz",         "riley",        "Extended",     "Riley applied Katz to require warrants for cell phone searches"),
    ("katz",         "carpenter",    "Extended",     "Carpenter extended Katz to cell-site location data"),
    ("riley",        "carpenter",    "Relied on",    "Carpenter cited Riley's digital-privacy reasoning"),

    # Privacy / 14th chain
    ("griswold",     "roe",          "Extended",     "Roe extended Griswold's privacy right to abortion"),
    ("roe",          "dobbs",        "Overruled",    "Dobbs overruled Roe, returning abortion to the states"),
    ("griswold",     "obergefell",   "Relied on",    "Obergefell relied on Griswold's intimate-liberty reasoning"),
    ("loving",       "obergefell",   "Extended",     "Obergefell extended Loving's marriage-as-fundamental-right"),
    ("roe",          "obergefell",   "Relied on",    "Obergefell cited Roe in the substantive due process analysis"),

    # Equal protection chain
    ("brown",        "loving",       "Extended",     "Loving extended Brown's anti-classification principle to marriage"),
    ("brown",        "grutter",      "Relied on",    "Grutter built on Brown's equal protection framework"),
    ("grutter",      "sffa",         "Overruled",    "SFFA overruled Grutter, ending race-conscious admissions"),

    # 8th Amendment chain
    ("furman",       "gregg",        "Distinguished","Gregg allowed reinstated death penalty with guided discretion"),
    ("gregg",        "atkins",       "Extended",     "Atkins carved out intellectual disability from Gregg's death-eligible class"),
    ("atkins",       "roper",        "Extended",     "Roper extended Atkins' reasoning to juveniles"),

    # Cross-amendment links
    ("griswold",     "miranda",      "Relied on",    "Both grounded in substantive due process / privacy of the person"),
    ("gideon",       "miranda",      "Relied on",    "Miranda built on Gideon's right-to-counsel guarantee"),
    ("marbury",      "furman",       "Relied on",    "Court cited its judicial-review authority to reinterpret 8th Amend."),
]

RELATION_COLORS = {
    "Extended":      "#27AE60",
    "Overruled":     "#E74C3C",
    "Relied on":     "#3498DB",
    "Applied":       "#9B59B6",
    "Distinguished": "#F39C12",
}

AREA_COLORS = {
    "Free Speech":        "#2980B9",
    "Right to Bear Arms": "#8E44AD",
    "Search & Seizure":   "#E67E22",
    "Self-Incrimination": "#C0392B",
    "Takings":            "#16A085",
    "Right to Counsel":   "#27AE60",
    "Cruel & Unusual":    "#E74C3C",
    "Privacy":            "#F39C12",
    "Equal Protection":   "#D35400",
    "Judicial Power":     "#7F8C8D",
    "Federalism":         "#BDC3C7",
}

def build_graph(case_filter=None, relation_filter=None):
    G = nx.DiGraph()
    for cid, (name, year, area, amend) in CASES.items():
        G.add_node(cid, name=name, year=year, area=area, amend=amend)
    for src, tgt, rel, desc in EDGES:
        if relation_filter and rel not in relation_filter:
            continue
        if case_filter:
            # Only include edges where at least one endpoint is in filter set
            if src not in case_filter and tgt not in case_filter:
                continue
        G.add_edge(src, tgt, relation=rel, description=desc)
    return G

def spring_layout(G: nx.DiGraph, seed=42):
    pos = nx.spring_layout(G, seed=seed, k=2.5, iterations=80)
    return pos

def build_network_figure(G: nx.DiGraph, highlight_id=None) -> go.Figure:
    pos = spring_layout(G)

    edge_traces = []
    for src, tgt, data in G.edges(data=True):
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        rel = data.get("relation", "Relied on")
        color = RELATION_COLORS.get(rel, "#95A5A6")
        desc = data.get("description", "")

        # Draw line
        edge_traces.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(width=2, color=color),
            hoverinfo="none",
            showlegend=False,
        ))

        # Arrowhead dot at target
        edge_traces.append(go.Scatter(
            x=[x1],
            y=[y1],
            mode="markers",
            marker=dict(size=6, color=color, symbol="arrow", angleref="previous"),
            hoverinfo="none",
            showlegend=False,
        ))

    # Node trace
    node_ids = list(G.nodes())
    node_x = [pos[n][0] for n in node_ids]
    node_y = [pos[n][1] for n in node_ids]
    node_names = [G.nodes[n]["name"] for n in node_ids]
    node_years = [G.nodes[n]["year"] for n in node_ids]
    node_areas = [G.nodes[n]["area"] for n in node_ids]
    node_colors = [AREA_COLORS.get(a, "#95A5A6") for a in node_areas]
    node_sizes = []
    for n in node_ids:
        degree = G.degree(n)
        base = 22 + degree * 4
        if n == highlight_id:
            base += 12
        node_sizes.append(min(base, 55))

    node_borders = ["white" if n != highlight_id else "#FFD700" for n in node_ids]
    border_widths = [2 if n != highlight_id else 5 for n in node_ids]

    hover = [
        f"<b>{name}</b> ({year})<br>Area: {area}<br>"
        f"Connections: {G.degree(nid)}"
        for nid, name, year, area in zip(node_ids, node_names, node_years, node_areas)
    ]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(color=node_borders, width=border_widths),
            opacity=0.92,
        ),
        text=[f"<b>{n}</b>" for n in node_names],
        textposition="top center",
        textfont=dict(size=9, color="#2C3E50"),
        hovertext=hover,
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])

    # Legend traces for relation types
    for rel, color in RELATION_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(color=color, width=3),
            name=rel,
            showlegend=True,
        ))

    fig.update_layout(
        title="SCOTUS Case Precedent Network",
        height=680,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(
            title="Relationship Type",
            orientation="v",
            x=1.01, y=1,
            xanchor="left",
        ),
        hovermode="closest",
    )
    return fig

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🕸️ Case Network — Precedent & Influence Map")
st.markdown(
    "An interactive graph of how landmark SCOTUS cases cite, extend, rely on, "
    "or overrule each other. Node size reflects number of connections. "
    "Edge color shows the type of relationship."
)

# ── Filters ───────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    all_areas = sorted(set(v[2] for v in CASES.values()))
    selected_areas = st.multiselect("Filter by Legal Area", all_areas, default=[])

with col2:
    selected_relations = st.multiselect(
        "Filter by Relationship Type",
        list(RELATION_COLORS.keys()),
        default=[],
    )

with col3:
    all_case_names = {v[0]: k for k, v in CASES.items()}
    focus_name = st.selectbox(
        "Focus on a Case (shows its direct neighbors)",
        ["— Show all —"] + sorted(all_case_names.keys()),
    )

# Build filter sets
case_filter = None
if focus_name != "— Show all —":
    focus_id = all_case_names[focus_name]
    # Include the case and all direct neighbors
    G_full = build_graph()
    neighbors = set(G_full.predecessors(focus_id)) | set(G_full.successors(focus_id))
    case_filter = neighbors | {focus_id}
    highlight_id = focus_id
else:
    highlight_id = None
    focus_id = None

area_filter_ids = None
if selected_areas:
    area_filter_ids = {k for k, v in CASES.items() if v[2] in selected_areas}
    if case_filter is not None:
        case_filter = case_filter & area_filter_ids
    else:
        case_filter = area_filter_ids

relation_filter = set(selected_relations) if selected_relations else None

G = build_graph(case_filter=case_filter, relation_filter=relation_filter)

if G.number_of_nodes() == 0:
    st.warning("No cases match the selected filters. Try broadening your selection.")
    st.stop()

fig = build_network_figure(G, highlight_id=highlight_id)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Showing {G.number_of_nodes()} cases and {G.number_of_edges()} relationships. "
    "Hover over any node for details."
)

st.divider()

# ── Case detail panel ─────────────────────────────────────────────────────────
st.subheader("Case Detail")
detail_name = st.selectbox(
    "Select a case to inspect its connections",
    sorted(all_case_names.keys()),
    index=sorted(all_case_names.keys()).index(focus_name) if focus_name != "— Show all —" else 0,
)
detail_id = all_case_names[detail_name]
G_full2 = build_graph()

outgoing = [
    (CASES[tgt][0], rel, desc)
    for _, tgt, d in G_full2.out_edges(detail_id, data=True)
    if (rel := d["relation"]) and (desc := d["description"])
]
incoming = [
    (CASES[src][0], rel, desc)
    for src, _, d in G_full2.in_edges(detail_id, data=True)
    if (rel := d["relation"]) and (desc := d["description"])
]

case_info = CASES[detail_id]
st.markdown(f"### {case_info[0]} ({case_info[1]})")
st.markdown(f"**Area:** {case_info[2]}  |  **Amendment:** {case_info[3] or 'N/A'}")

col_out, col_in = st.columns(2)
with col_out:
    st.markdown("**This case influenced →**")
    if outgoing:
        for target, rel, desc in outgoing:
            color = RELATION_COLORS.get(rel, "#95A5A6")
            st.markdown(
                f"<span style='color:{color};font-weight:bold'>{rel}</span> → "
                f"**{target}**<br><small>{desc}</small>",
                unsafe_allow_html=True,
            )
            st.markdown("")
    else:
        st.markdown("_No outgoing links in this dataset._")

with col_in:
    st.markdown("**← This case was influenced by**")
    if incoming:
        for source, rel, desc in incoming:
            color = RELATION_COLORS.get(rel, "#95A5A6")
            st.markdown(
                f"**{source}** → "
                f"<span style='color:{color};font-weight:bold'>{rel}</span><br>"
                f"<small>{desc}</small>",
                unsafe_allow_html=True,
            )
            st.markdown("")
    else:
        st.markdown("_No incoming links in this dataset._")

st.divider()

# ── Most connected cases ──────────────────────────────────────────────────────
st.subheader("Most Connected Cases")
G_all = build_graph()
degree_data = [
    {
        "Case": CASES[n][0],
        "Year": CASES[n][1],
        "Area": CASES[n][2],
        "Amendment": CASES[n][3] or "—",
        "Total Connections": G_all.degree(n),
        "Influenced": G_all.out_degree(n),
        "Influenced by": G_all.in_degree(n),
    }
    for n in G_all.nodes()
]
degree_df = pd.DataFrame(degree_data).sort_values("Total Connections", ascending=False)
st.dataframe(degree_df, use_container_width=True, height=350)

st.divider()

# ── Full edge table ───────────────────────────────────────────────────────────
with st.expander("Full Relationship Table"):
    edge_rows = [
        {
            "From": CASES[s][0],
            "Relationship": r,
            "To": CASES[t][0],
            "Description": d,
        }
        for s, t, r, d in EDGES
    ]
    edge_df = pd.DataFrame(edge_rows)
    rel_filter_table = st.multiselect(
        "Filter relationships",
        list(RELATION_COLORS.keys()),
        default=[],
        key="table_rel_filter",
    )
    display_edges = edge_df[edge_df["Relationship"].isin(rel_filter_table)] if rel_filter_table else edge_df
    st.dataframe(display_edges, use_container_width=True, height=400)
