import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import networkx as nx
import pandas as pd

st.set_page_config(page_title="Citation Network", page_icon="🔗", layout="wide")

# ── Curated case nodes ────────────────────────────────────────────────────────
# (id, display_name, year, issue_area, oyez_url)
CASES = [
    ("plessy",      "Plessy v. Ferguson",                1896, "Equal Protection",   "https://www.oyez.org/cases/1850-1900/163us537"),
    ("mapp",        "Mapp v. Ohio",                      1961, "Criminal Procedure",  "https://www.oyez.org/cases/1960/236"),
    ("engel",       "Engel v. Vitale",                   1962, "First Amendment",     "https://www.oyez.org/cases/1961/468"),
    ("gideon",      "Gideon v. Wainwright",              1963, "Criminal Procedure",  "https://www.oyez.org/cases/1962/155"),
    ("brown",       "Brown v. Board of Education",       1954, "Equal Protection",    "https://www.oyez.org/cases/1940-1955/347us483"),
    ("griswold",    "Griswold v. Connecticut",           1965, "Privacy",             "https://www.oyez.org/cases/1964/496"),
    ("miranda",     "Miranda v. Arizona",                1966, "Criminal Procedure",  "https://www.oyez.org/cases/1965/759"),
    ("tinker",      "Tinker v. Des Moines",              1969, "First Amendment",     "https://www.oyez.org/cases/1968/21"),
    ("lemon",       "Lemon v. Kurtzman",                 1971, "First Amendment",     "https://www.oyez.org/cases/1970/89"),
    ("roe",         "Roe v. Wade",                       1973, "Privacy",             "https://www.oyez.org/cases/1971/70-18"),
    ("buckley",     "Buckley v. Valeo",                  1976, "First Amendment",     "https://www.oyez.org/cases/1975/75-436"),
    ("bakke",       "Regents v. Bakke",                  1978, "Equal Protection",    "https://www.oyez.org/cases/1979/76-811"),
    ("miller",      "United States v. Miller",           1939, "Second Amendment",    "https://www.oyez.org/cases/1938/696"),
    ("texas_v_j",   "Texas v. Johnson",                  1989, "First Amendment",     "https://www.oyez.org/cases/1988/88-155"),
    ("bowers",      "Bowers v. Hardwick",                1986, "Privacy",             "https://www.oyez.org/cases/1985/85-140"),
    ("casey",       "Planned Parenthood v. Casey",       1992, "Privacy",             "https://www.oyez.org/cases/1991/91-744"),
    ("katzen",      "S. Carolina v. Katzenbach",         1966, "Civil Rights",        "https://www.oyez.org/cases/1965/22-orig"),
    ("chevron",     "Chevron v. NRDC",                   1984, "Federal Power",       "https://www.oyez.org/cases/1983/82-1005"),
    ("grutter",     "Grutter v. Bollinger",              2003, "Equal Protection",    "https://www.oyez.org/cases/2002/02-241"),
    ("lawrence",    "Lawrence v. Texas",                 2003, "Privacy",             "https://www.oyez.org/cases/2002/02-102"),
    ("windsor",     "United States v. Windsor",          2013, "Equal Protection",    "https://www.oyez.org/cases/2012/12-307"),
    ("citizens",    "Citizens United v. FEC",            2010, "First Amendment",     "https://www.oyez.org/cases/2008/08-205"),
    ("heller",      "DC v. Heller",                      2008, "Second Amendment",    "https://www.oyez.org/cases/2007/07-290"),
    ("mcdonald",    "McDonald v. Chicago",               2010, "Second Amendment",    "https://www.oyez.org/cases/2009/08-1521"),
    ("obergefell",  "Obergefell v. Hodges",              2015, "Equal Protection",    "https://www.oyez.org/cases/2014/14-556"),
    ("nfib",        "NFIB v. Sebelius",                  2012, "Federal Power",       "https://www.oyez.org/cases/2011/11-393"),
    ("wickard",     "Wickard v. Filburn",                1942, "Federal Power",       "https://www.oyez.org/cases/1942/49"),
    ("shelby",      "Shelby County v. Holder",           2013, "Civil Rights",        "https://www.oyez.org/cases/2012/12-96"),
    ("dobbs",       "Dobbs v. Jackson",                  2022, "Privacy",             "https://www.oyez.org/cases/2021/19-1392"),
    ("sffa",        "SFFA v. Harvard",                   2023, "Equal Protection",    "https://www.oyez.org/cases/2022/20-1199"),
    ("wv_epa",      "West Virginia v. EPA",              2022, "Federal Power",       "https://www.oyez.org/cases/2021/20-1530"),
    ("kennedy_brem","Kennedy v. Bremerton",              2022, "First Amendment",     "https://www.oyez.org/cases/2021/21-418"),
    ("loper",       "Loper Bright Enterprises v. Raimondo", 2024, "Federal Power",   "https://www.oyez.org/cases/2023/22-451"),
    ("powell",      "Powell v. Alabama",                 1932, "Criminal Procedure",  "https://www.oyez.org/cases/1932/98"),
    ("everson",     "Everson v. Board of Education",     1947, "First Amendment",     "https://www.oyez.org/cases/1946/52"),
    ("bruen",       "NY State Rifle & Pistol v. Bruen",  2022, "Second Amendment",   "https://www.oyez.org/cases/2021/20-843"),
    ("bump_stocks", "Garland v. Cargill",                2024, "Second Amendment",   "https://www.oyez.org/cases/2023/22-976"),
]

# ── Curated edges ─────────────────────────────────────────────────────────────
# (source_id, target_id, relationship)
# relationship types: "Overrules", "Builds On", "Extends", "Limits", "Reaffirms", "Distinguishes"
EDGES = [
    # Equal Protection / Race
    ("brown",      "plessy",      "Overrules"),
    ("sffa",       "grutter",     "Overrules"),
    ("sffa",       "bakke",       "Limits"),
    ("grutter",    "bakke",       "Builds On"),
    ("shelby",     "katzen",      "Limits"),

    # Privacy / Abortion
    ("roe",        "griswold",    "Builds On"),
    ("casey",      "roe",         "Reaffirms"),
    ("dobbs",      "roe",         "Overrules"),
    ("dobbs",      "casey",       "Overrules"),

    # Privacy / LGBT
    ("lawrence",   "bowers",      "Overrules"),
    ("lawrence",   "griswold",    "Extends"),
    ("obergefell", "lawrence",    "Extends"),
    ("obergefell", "windsor",     "Builds On"),
    ("windsor",    "lawrence",    "Builds On"),

    # Criminal Procedure
    ("miranda",    "mapp",        "Builds On"),
    ("gideon",     "powell",      "Extends"),

    # First Amendment / Religion
    ("engel",      "everson",     "Builds On"),
    ("lemon",      "engel",       "Builds On"),
    ("kennedy_brem","lemon",      "Overrules"),

    # First Amendment / Speech
    ("texas_v_j",  "tinker",      "Extends"),
    ("citizens",   "buckley",     "Extends"),

    # Second Amendment
    ("heller",     "miller",      "Distinguishes"),
    ("mcdonald",   "heller",      "Extends"),
    ("bruen",      "heller",      "Builds On"),
    ("bump_stocks","bruen",       "Builds On"),

    # Federal Power / Commerce
    ("nfib",       "wickard",     "Limits"),

    # Administrative Law / Chevron
    ("wv_epa",     "chevron",     "Limits"),
    ("loper",      "chevron",     "Overrules"),
    ("loper",      "wv_epa",      "Builds On"),
]

# ── Color maps ────────────────────────────────────────────────────────────────
AREA_COLORS = {
    "Equal Protection": "#3498DB",
    "Privacy":          "#9B59B6",
    "First Amendment":  "#E67E22",
    "Criminal Procedure":"#27AE60",
    "Second Amendment": "#E74C3C",
    "Federal Power":    "#F39C12",
    "Civil Rights":     "#1ABC9C",
}

REL_COLORS = {
    "Overrules":     "#E74C3C",
    "Builds On":     "#27AE60",
    "Extends":       "#3498DB",
    "Limits":        "#E67E22",
    "Reaffirms":     "#9B59B6",
    "Distinguishes": "#95A5A6",
}

REL_DASH = {
    "Overrules":     "solid",
    "Builds On":     "solid",
    "Extends":       "dash",
    "Limits":        "dot",
    "Reaffirms":     "solid",
    "Distinguishes": "dash",
}

# ── Build graph ───────────────────────────────────────────────────────────────
def build_graph(cases, edges, focus_id=None, area_filter=None, rel_filter=None):
    G = nx.DiGraph()
    case_map = {c[0]: c for c in cases}

    for cid, name, year, area, url in cases:
        if area_filter and area not in area_filter:
            continue
        G.add_node(cid, name=name, year=year, area=area, url=url)

    for src, tgt, rel in edges:
        if rel_filter and rel not in rel_filter:
            continue
        if src in G.nodes and tgt in G.nodes:
            G.add_edge(src, tgt, rel=rel)

    if focus_id and focus_id in G.nodes:
        neighbors = set(nx.all_neighbors(G, focus_id)) | {focus_id}
        remove = [n for n in list(G.nodes) if n not in neighbors]
        G.remove_nodes_from(remove)

    return G

def make_figure(G: nx.DiGraph) -> go.Figure:
    if len(G.nodes) == 0:
        return go.Figure().add_annotation(text="No cases match filters", showarrow=False)

    pos = nx.spring_layout(G, seed=42, k=2.5)

    fig = go.Figure()

    # Draw edges
    for src, tgt, data in G.edges(data=True):
        rel = data.get("rel", "Builds On")
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        color = REL_COLORS.get(rel, "#95A5A6")
        dash = REL_DASH.get(rel, "solid")

        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color=color, width=2, dash=dash),
            hoverinfo="skip",
            showlegend=False,
        ))

        # Arrow head (small marker at target end)
        fig.add_trace(go.Scatter(
            x=[x1], y=[y1],
            mode="markers",
            marker=dict(
                symbol="arrow", size=12, color=color,
                angleref="previous",
                angle=0,
            ),
            hoverinfo="skip",
            showlegend=False,
        ))

        # Edge label
        fig.add_annotation(
            x=mx, y=my,
            text=rel,
            showarrow=False,
            font=dict(size=8, color=color),
            bgcolor="rgba(255,255,255,0.7)",
        )

    # Draw nodes
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        area = data.get("area", "Other")
        color = AREA_COLORS.get(area, "#BDC3C7")
        name = data.get("name", node)
        year = data.get("year", "")
        url = data.get("url", "")
        in_deg = G.in_degree(node)
        out_deg = G.out_degree(node)
        size = 14 + (in_deg + out_deg) * 4

        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers+text",
            marker=dict(size=size, color=color, line=dict(color="white", width=1.5)),
            text=f"{name}<br>({year})",
            textposition="top center",
            textfont=dict(size=9),
            hovertemplate=(
                f"<b>{name}</b> ({year})<br>"
                f"Issue Area: {area}<br>"
                f"Cites: {out_deg} case(s) | Cited by: {in_deg} case(s)"
                "<extra></extra>"
            ),
            customdata=[url],
            showlegend=False,
        ))

    # Legend for area colors
    shown_areas: set[str] = set()
    for _, data in G.nodes(data=True):
        area = data.get("area", "Other")
        if area not in shown_areas:
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="markers",
                marker=dict(size=10, color=AREA_COLORS.get(area, "#BDC3C7")),
                name=area,
                showlegend=True,
            ))
            shown_areas.add(area)

    # Legend for relationship types
    shown_rels: set[str] = set()
    for _, _, data in G.edges(data=True):
        rel = data.get("rel", "")
        if rel not in shown_rels:
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode="lines",
                line=dict(color=REL_COLORS.get(rel, "#95A5A6"), width=2,
                          dash=REL_DASH.get(rel, "solid")),
                name=rel,
                showlegend=True,
            ))
            shown_rels.add(rel)

    fig.update_layout(
        height=680,
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            title="Legend",
            x=1.01, y=1,
            font=dict(size=10),
        ),
        hovermode="closest",
    )
    return fig

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🔗 SCOTUS Citation Network")
st.markdown(
    "Explore how landmark Supreme Court cases cite, overrule, build on, "
    "and distinguish each other. Arrows point **from citing case → to cited case** "
    "(e.g., *Dobbs → Roe* means Dobbs cited and overruled Roe)."
)

all_areas   = sorted(set(c[3] for c in CASES))
all_rels    = sorted(set(e[2] for e in EDGES))
all_names   = ["(Show All)"] + sorted(c[1] for c in CASES)
id_by_name  = {c[1]: c[0] for c in CASES}

with st.sidebar:
    st.header("Filters")
    area_filter = st.multiselect("Issue Areas", all_areas, default=all_areas)
    rel_filter  = st.multiselect("Relationship Types", all_rels, default=all_rels)
    focus_name  = st.selectbox("Focus on Case", all_names)

focus_id = id_by_name.get(focus_name) if focus_name != "(Show All)" else None

G = build_graph(CASES, EDGES,
                focus_id=focus_id,
                area_filter=set(area_filter) if area_filter else None,
                rel_filter=set(rel_filter) if rel_filter else None)

col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = make_figure(G)
    st.plotly_chart(fig, use_container_width=True)

with col_info:
    st.subheader("Network Stats")
    st.metric("Cases shown", len(G.nodes))
    st.metric("Connections", len(G.edges))

    if focus_id and focus_id in G.nodes:
        node_data = G.nodes[focus_id]
        st.divider()
        st.subheader(node_data.get("name", ""))
        st.markdown(f"**Year:** {node_data.get('year', '')}")
        st.markdown(f"**Area:** {node_data.get('area', '')}")

        cites = list(G.successors(focus_id))
        cited_by = list(G.predecessors(focus_id))

        if cites:
            st.markdown("**Cites:**")
            for cid in cites:
                rel = G.edges[focus_id, cid]["rel"]
                name = G.nodes[cid].get("name", cid)
                st.markdown(f"- *{rel}* → {name}")

        if cited_by:
            st.markdown("**Cited by:**")
            for cid in cited_by:
                rel = G.edges[cid, focus_id]["rel"]
                name = G.nodes[cid].get("name", cid)
                st.markdown(f"- *{rel}* ← {name}")

        url = node_data.get("url", "")
        if url:
            st.markdown(f"[Open on Oyez ↗]({url})")

st.divider()

# ── Most-cited table ──────────────────────────────────────────────────────────
st.subheader("Most Influential Cases")
st.caption("Ranked by how many other cases in this network cite them.")
rows = []
for node, data in G.nodes(data=True):
    rows.append({
        "Case": data.get("name", node),
        "Year": data.get("year", ""),
        "Area": data.get("area", ""),
        "Times Cited": G.in_degree(node),
        "Cases It Cites": G.out_degree(node),
    })
if rows:
    inf_df = pd.DataFrame(rows).sort_values("Times Cited", ascending=False)
    st.dataframe(inf_df, use_container_width=True, height=300, hide_index=True)

st.divider()

# ── Edge table ────────────────────────────────────────────────────────────────
with st.expander("All Citation Relationships"):
    edge_rows = []
    for src, tgt, data in G.edges(data=True):
        src_name = G.nodes[src].get("name", src)
        tgt_name = G.nodes[tgt].get("name", tgt)
        edge_rows.append({
            "Citing Case": src_name,
            "Relationship": data.get("rel", ""),
            "Cited Case": tgt_name,
        })
    if edge_rows:
        st.dataframe(pd.DataFrame(edge_rows), use_container_width=True, height=300, hide_index=True)
