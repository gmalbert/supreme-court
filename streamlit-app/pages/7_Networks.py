import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import networkx as nx
import pandas as pd

st.set_page_config(page_title="Networks Hub", page_icon="🕸️", layout="wide")

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🕸️ Networks")
tab_citation, tab_precedent = st.tabs([
    "🔗 Citation Network", "🕸️ Case Precedent Network"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: CITATION NETWORK (16_Citation_Network)
# ──────────────────────────────────────────────────────────────────────────────
with tab_citation:
    st.markdown(
        "Explore how landmark Supreme Court cases cite, overrule, build on, "
        "and distinguish each other. Arrows point **from citing case → to cited case**."
    )

    CASES_CN = [
        ("plessy","Plessy v. Ferguson",1896,"Equal Protection","https://www.oyez.org/cases/1850-1900/163us537"),
        ("mapp","Mapp v. Ohio",1961,"Criminal Procedure","https://www.oyez.org/cases/1960/236"),
        ("engel","Engel v. Vitale",1962,"First Amendment","https://www.oyez.org/cases/1961/468"),
        ("gideon","Gideon v. Wainwright",1963,"Criminal Procedure","https://www.oyez.org/cases/1962/155"),
        ("brown","Brown v. Board of Education",1954,"Equal Protection","https://www.oyez.org/cases/1940-1955/347us483"),
        ("griswold","Griswold v. Connecticut",1965,"Privacy","https://www.oyez.org/cases/1964/496"),
        ("miranda","Miranda v. Arizona",1966,"Criminal Procedure","https://www.oyez.org/cases/1965/759"),
        ("tinker","Tinker v. Des Moines",1969,"First Amendment","https://www.oyez.org/cases/1968/21"),
        ("lemon","Lemon v. Kurtzman",1971,"First Amendment","https://www.oyez.org/cases/1970/89"),
        ("roe","Roe v. Wade",1973,"Privacy","https://www.oyez.org/cases/1971/70-18"),
        ("buckley","Buckley v. Valeo",1976,"First Amendment","https://www.oyez.org/cases/1975/75-436"),
        ("bakke","Regents v. Bakke",1978,"Equal Protection","https://www.oyez.org/cases/1979/76-811"),
        ("miller","United States v. Miller",1939,"Second Amendment","https://www.oyez.org/cases/1938/696"),
        ("texas_v_j","Texas v. Johnson",1989,"First Amendment","https://www.oyez.org/cases/1988/88-155"),
        ("bowers","Bowers v. Hardwick",1986,"Privacy","https://www.oyez.org/cases/1985/85-140"),
        ("casey","Planned Parenthood v. Casey",1992,"Privacy","https://www.oyez.org/cases/1991/91-744"),
        ("katzen","S. Carolina v. Katzenbach",1966,"Civil Rights","https://www.oyez.org/cases/1965/22-orig"),
        ("chevron","Chevron v. NRDC",1984,"Federal Power","https://www.oyez.org/cases/1983/82-1005"),
        ("grutter","Grutter v. Bollinger",2003,"Equal Protection","https://www.oyez.org/cases/2002/02-241"),
        ("lawrence","Lawrence v. Texas",2003,"Privacy","https://www.oyez.org/cases/2002/02-102"),
        ("windsor","United States v. Windsor",2013,"Equal Protection","https://www.oyez.org/cases/2012/12-307"),
        ("citizens","Citizens United v. FEC",2010,"First Amendment","https://www.oyez.org/cases/2008/08-205"),
        ("heller","DC v. Heller",2008,"Second Amendment","https://www.oyez.org/cases/2007/07-290"),
        ("mcdonald","McDonald v. Chicago",2010,"Second Amendment","https://www.oyez.org/cases/2009/08-1521"),
        ("obergefell","Obergefell v. Hodges",2015,"Equal Protection","https://www.oyez.org/cases/2014/14-556"),
        ("nfib","NFIB v. Sebelius",2012,"Federal Power","https://www.oyez.org/cases/2011/11-393"),
        ("wickard","Wickard v. Filburn",1942,"Federal Power","https://www.oyez.org/cases/1942/49"),
        ("shelby","Shelby County v. Holder",2013,"Civil Rights","https://www.oyez.org/cases/2012/12-96"),
        ("dobbs","Dobbs v. Jackson",2022,"Privacy","https://www.oyez.org/cases/2021/19-1392"),
        ("sffa","SFFA v. Harvard",2023,"Equal Protection","https://www.oyez.org/cases/2022/20-1199"),
        ("wv_epa","West Virginia v. EPA",2022,"Federal Power","https://www.oyez.org/cases/2021/20-1530"),
        ("kennedy_brem","Kennedy v. Bremerton",2022,"First Amendment","https://www.oyez.org/cases/2021/21-418"),
        ("loper","Loper Bright v. Raimondo",2024,"Federal Power","https://www.oyez.org/cases/2023/22-451"),
        ("powell","Powell v. Alabama",1932,"Criminal Procedure","https://www.oyez.org/cases/1932/98"),
        ("everson","Everson v. Board of Education",1947,"First Amendment","https://www.oyez.org/cases/1946/52"),
        ("bruen","NY State Rifle & Pistol v. Bruen",2022,"Second Amendment","https://www.oyez.org/cases/2021/20-843"),
        ("bump_stocks","Garland v. Cargill",2024,"Second Amendment","https://www.oyez.org/cases/2023/22-976"),
    ]

    EDGES_CN = [
        ("brown","plessy","Overrules"),("sffa","grutter","Overrules"),("sffa","bakke","Limits"),
        ("grutter","bakke","Builds On"),("shelby","katzen","Limits"),
        ("roe","griswold","Builds On"),("casey","roe","Reaffirms"),("dobbs","roe","Overrules"),("dobbs","casey","Overrules"),
        ("lawrence","bowers","Overrules"),("lawrence","griswold","Extends"),("obergefell","lawrence","Extends"),
        ("obergefell","windsor","Builds On"),("windsor","lawrence","Builds On"),
        ("miranda","mapp","Builds On"),("gideon","powell","Extends"),
        ("engel","everson","Builds On"),("lemon","engel","Builds On"),("kennedy_brem","lemon","Overrules"),
        ("texas_v_j","tinker","Extends"),("citizens","buckley","Extends"),
        ("heller","miller","Distinguishes"),("mcdonald","heller","Extends"),("bruen","heller","Builds On"),
        ("bump_stocks","bruen","Builds On"),
        ("nfib","wickard","Limits"),("wv_epa","chevron","Limits"),("loper","chevron","Overrules"),("loper","wv_epa","Builds On"),
    ]

    AREA_COLORS_CN = {"Equal Protection":"#3498DB","Privacy":"#9B59B6","First Amendment":"#E67E22",
                      "Criminal Procedure":"#27AE60","Second Amendment":"#E74C3C","Federal Power":"#F39C12","Civil Rights":"#1ABC9C"}
    REL_COLORS_CN  = {"Overrules":"#E74C3C","Builds On":"#27AE60","Extends":"#3498DB","Limits":"#E67E22","Reaffirms":"#9B59B6","Distinguishes":"#95A5A6"}
    REL_DASH_CN    = {"Overrules":"solid","Builds On":"solid","Extends":"dash","Limits":"dot","Reaffirms":"solid","Distinguishes":"dash"}

    def _build_graph_cn(cases, edges, focus_id=None, area_filter=None, rel_filter=None):
        G = nx.DiGraph()
        for cid, name, year, area, url in cases:
            if area_filter and area not in area_filter: continue
            G.add_node(cid, name=name, year=year, area=area, url=url)
        for src, tgt, rel in edges:
            if rel_filter and rel not in rel_filter: continue
            if src in G.nodes and tgt in G.nodes: G.add_edge(src, tgt, rel=rel)
        if focus_id and focus_id in G.nodes:
            neighbors = set(nx.all_neighbors(G, focus_id)) | {focus_id}
            G.remove_nodes_from([n for n in list(G.nodes) if n not in neighbors])
        return G

    def _make_figure_cn(G: nx.DiGraph) -> go.Figure:
        if len(G.nodes) == 0:
            return go.Figure().add_annotation(text="No cases match filters", showarrow=False)
        pos = nx.spring_layout(G, seed=42, k=2.5)
        fig = go.Figure()
        for src, tgt, data in G.edges(data=True):
            rel = data.get("rel","Builds On")
            x0,y0 = pos[src]; x1,y1 = pos[tgt]
            mx,my = (x0+x1)/2,(y0+y1)/2
            color = REL_COLORS_CN.get(rel,"#95A5A6"); dash = REL_DASH_CN.get(rel,"solid")
            fig.add_trace(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],mode="lines",
                                     line=dict(color=color,width=2,dash=dash),hoverinfo="skip",showlegend=False))
            fig.add_trace(go.Scatter(x=[x1],y=[y1],mode="markers",
                                     marker=dict(symbol="arrow",size=12,color=color,angleref="previous",angle=0),
                                     hoverinfo="skip",showlegend=False))
            fig.add_annotation(x=mx,y=my,text=rel,showarrow=False,font=dict(size=8,color=color),bgcolor="rgba(255,255,255,0.7)")
        for node, data in G.nodes(data=True):
            x,y = pos[node]; area = data.get("area","Other"); color = AREA_COLORS_CN.get(area,"#BDC3C7")
            name = data.get("name",node); year = data.get("year",""); url = data.get("url","")
            in_deg = G.in_degree(node); out_deg = G.out_degree(node)
            size = 14+(in_deg+out_deg)*4
            fig.add_trace(go.Scatter(x=[x],y=[y],mode="markers+text",
                                     marker=dict(size=size,color=color,line=dict(color="white",width=1.5)),
                                     text=f"{name}<br>({year})",textposition="top center",textfont=dict(size=9),
                                     hovertemplate=f"<b>{name}</b> ({year})<br>Issue Area: {area}<br>Cites: {out_deg} | Cited by: {in_deg}<extra></extra>",
                                     customdata=[url],showlegend=False))
        shown_areas: set[str] = set()
        for _, data in G.nodes(data=True):
            area = data.get("area","Other")
            if area not in shown_areas:
                fig.add_trace(go.Scatter(x=[None],y=[None],mode="markers",marker=dict(size=10,color=AREA_COLORS_CN.get(area,"#BDC3C7")),name=area,showlegend=True))
                shown_areas.add(area)
        shown_rels: set[str] = set()
        for _,_,data in G.edges(data=True):
            rel = data.get("rel","")
            if rel not in shown_rels:
                fig.add_trace(go.Scatter(x=[None],y=[None],mode="lines",
                                         line=dict(color=REL_COLORS_CN.get(rel,"#95A5A6"),width=2,dash=REL_DASH_CN.get(rel,"solid")),
                                         name=rel,showlegend=True))
                shown_rels.add(rel)
        fig.update_layout(height=680,plot_bgcolor="white",paper_bgcolor="white",
                          xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                          yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                          margin=dict(l=10,r=10,t=10,b=10),
                          legend=dict(title="Legend",x=1.01,y=1,font=dict(size=10)),hovermode="closest")
        return fig

    all_areas_cn   = sorted(set(c[3] for c in CASES_CN))
    all_rels_cn    = sorted(set(e[2] for e in EDGES_CN))
    all_names_cn   = ["(Show All)"] + sorted(c[1] for c in CASES_CN)
    id_by_name_cn  = {c[1]:c[0] for c in CASES_CN}

    col_f1_cn, col_f2_cn, col_f3_cn = st.columns(3)
    with col_f1_cn: area_filter_cn = st.multiselect("Issue Areas",all_areas_cn,default=all_areas_cn,key="cn_areas")
    with col_f2_cn: rel_filter_cn  = st.multiselect("Relationship Types",all_rels_cn,default=all_rels_cn,key="cn_rels")
    with col_f3_cn: focus_name_cn  = st.selectbox("Focus on Case",all_names_cn,key="cn_focus")

    focus_id_cn = id_by_name_cn.get(focus_name_cn) if focus_name_cn != "(Show All)" else None
    G_cn = _build_graph_cn(CASES_CN,EDGES_CN,
                            focus_id=focus_id_cn,
                            area_filter=set(area_filter_cn) if area_filter_cn else None,
                            rel_filter=set(rel_filter_cn) if rel_filter_cn else None)

    col_graph_cn, col_info_cn = st.columns([3,1])
    with col_graph_cn:
        fig_cn = _make_figure_cn(G_cn)
        st.plotly_chart(fig_cn,use_container_width=True)
    with col_info_cn:
        st.subheader("Network Stats")
        st.metric("Cases shown",len(G_cn.nodes)); st.metric("Connections",len(G_cn.edges))
        if focus_id_cn and focus_id_cn in G_cn.nodes:
            node_data_cn = G_cn.nodes[focus_id_cn]; st.divider()
            st.subheader(node_data_cn.get("name",""))
            st.markdown(f"**Year:** {node_data_cn.get('year','')}"); st.markdown(f"**Area:** {node_data_cn.get('area','')}")
            cites_cn = list(G_cn.successors(focus_id_cn)); cited_by_cn = list(G_cn.predecessors(focus_id_cn))
            if cites_cn:
                st.markdown("**Cites:**")
                for cid in cites_cn:
                    rel_cn = G_cn.edges[focus_id_cn,cid]["rel"]; name_cn = G_cn.nodes[cid].get("name",cid)
                    st.markdown(f"- *{rel_cn}* → {name_cn}")
            if cited_by_cn:
                st.markdown("**Cited by:**")
                for cid in cited_by_cn:
                    rel_cn = G_cn.edges[cid,focus_id_cn]["rel"]; name_cn = G_cn.nodes[cid].get("name",cid)
                    st.markdown(f"- *{rel_cn}* ← {name_cn}")
            url_cn = node_data_cn.get("url","")
            if url_cn: st.markdown(f"[Open on Oyez ↗]({url_cn})")

    st.divider(); st.subheader("Most Influential Cases")
    rows_cn = [{"Case":d.get("name",n),"Year":d.get("year",""),"Area":d.get("area",""),
                "Times Cited":G_cn.in_degree(n),"Cases It Cites":G_cn.out_degree(n)} for n,d in G_cn.nodes(data=True)]
    if rows_cn:
        inf_df_cn = pd.DataFrame(rows_cn).sort_values("Times Cited",ascending=False)
        st.dataframe(inf_df_cn,use_container_width=True,height=300,hide_index=True)

    with st.expander("All Citation Relationships"):
        edge_rows_cn = [{"Citing Case":G_cn.nodes[s].get("name",s),"Relationship":d.get("rel",""),"Cited Case":G_cn.nodes[t].get("name",t)}
                        for s,t,d in G_cn.edges(data=True)]
        if edge_rows_cn: st.dataframe(pd.DataFrame(edge_rows_cn),use_container_width=True,height=300,hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: CASE PRECEDENT NETWORK (11_Case_Network)
# ──────────────────────────────────────────────────────────────────────────────
with tab_precedent:
    st.markdown(
        "An interactive graph of how landmark SCOTUS cases cite, extend, rely on, or overrule each other. "
        "Node size reflects number of connections. Edge color shows the type of relationship."
    )

    CASES_PN = {
        "marbury":     ("Marbury v. Madison",           1803, "Judicial Power",       None),
        "mcculloch":   ("McCulloch v. Maryland",         1819, "Federalism",           None),
        "schenck":     ("Schenck v. United States",      1919, "Free Speech",          "1st"),
        "nyt_sullivan":("NY Times v. Sullivan",          1964, "Free Speech",          "1st"),
        "brandenburg": ("Brandenburg v. Ohio",           1969, "Free Speech",          "1st"),
        "texas_johnson":("Texas v. Johnson",             1989, "Free Speech",          "1st"),
        "citizens_utd":("Citizens United v. FEC",        2010, "Free Speech",          "1st"),
        "snyder_phelps":("Snyder v. Phelps",             2011, "Free Speech",          "1st"),
        "heller_pn":   ("D.C. v. Heller",                2008, "Right to Bear Arms",   "2nd"),
        "mcdonald_pn": ("McDonald v. Chicago",           2010, "Right to Bear Arms",   "2nd"),
        "bruen_pn":    ("NY Rifle & Pistol v. Bruen",    2022, "Right to Bear Arms",   "2nd"),
        "mapp_pn":     ("Mapp v. Ohio",                  1961, "Search & Seizure",     "4th"),
        "katz":        ("Katz v. United States",         1967, "Search & Seizure",     "4th"),
        "terry":       ("Terry v. Ohio",                 1968, "Search & Seizure",     "4th"),
        "jones_pn":    ("United States v. Jones",        2012, "Search & Seizure",     "4th"),
        "riley_pn":    ("Riley v. California",           2014, "Search & Seizure",     "4th"),
        "carpenter_pn":("Carpenter v. United States",    2018, "Search & Seizure",     "4th"),
        "miranda_pn":  ("Miranda v. Arizona",            1966, "Self-Incrimination",   "5th"),
        "kelo":        ("Kelo v. City of New London",    2005, "Takings",              "5th"),
        "gideon_pn":   ("Gideon v. Wainwright",          1963, "Right to Counsel",     "6th"),
        "furman":      ("Furman v. Georgia",             1972, "Cruel & Unusual",      "8th"),
        "gregg":       ("Gregg v. Georgia",              1976, "Cruel & Unusual",      "8th"),
        "atkins":      ("Atkins v. Virginia",            2002, "Cruel & Unusual",      "8th"),
        "roper":       ("Roper v. Simmons",              2005, "Cruel & Unusual",      "8th"),
        "griswold_pn": ("Griswold v. Connecticut",       1965, "Privacy",              "14th"),
        "roe_pn":      ("Roe v. Wade",                   1973, "Privacy",              "14th"),
        "dobbs_pn":    ("Dobbs v. Jackson",              2022, "Privacy",              "14th"),
        "brown_pn":    ("Brown v. Board of Education",   1954, "Equal Protection",     "14th"),
        "loving":      ("Loving v. Virginia",            1967, "Equal Protection",     "14th"),
        "grutter_pn":  ("Grutter v. Bollinger",          2003, "Equal Protection",     "14th"),
        "sffa_pn":     ("SFFA v. Harvard",               2023, "Equal Protection",     "14th"),
        "obergefell_pn":("Obergefell v. Hodges",         2015, "Equal Protection",     "14th"),
    }

    EDGES_PN = [
        ("marbury","mcculloch","Extended","Federal supremacy built on judicial review"),
        ("schenck","nyt_sullivan","Distinguished","Sullivan replaced clear and present danger for press"),
        ("schenck","brandenburg","Overruled","Brandenburg replaced Schenck's test"),
        ("brandenburg","texas_johnson","Applied","Johnson applied the Brandenburg test"),
        ("nyt_sullivan","snyder_phelps","Extended","Phelps extended public-concern speech protection"),
        ("nyt_sullivan","citizens_utd","Relied on","Citizens United built on Sullivan's speech logic"),
        ("texas_johnson","citizens_utd","Relied on","Citizens United cited Johnson for symbolic speech"),
        ("heller_pn","mcdonald_pn","Extended","McDonald incorporated Heller against the states"),
        ("heller_pn","bruen_pn","Extended","Bruen expanded Heller; required historical tradition test"),
        ("mcdonald_pn","bruen_pn","Extended","Bruen built on McDonald's incorporation doctrine"),
        ("mapp_pn","katz","Extended","Katz extended exclusionary rule to electronic surveillance"),
        ("katz","terry","Distinguished","Terry allowed stops on reasonable suspicion"),
        ("katz","jones_pn","Extended","Jones applied Katz to GPS tracking"),
        ("katz","riley_pn","Extended","Riley applied Katz to cell phone searches"),
        ("katz","carpenter_pn","Extended","Carpenter extended Katz to cell-site location data"),
        ("riley_pn","carpenter_pn","Relied on","Carpenter cited Riley's digital-privacy reasoning"),
        ("griswold_pn","roe_pn","Extended","Roe extended Griswold's privacy right to abortion"),
        ("roe_pn","dobbs_pn","Overruled","Dobbs overruled Roe"),
        ("griswold_pn","obergefell_pn","Relied on","Obergefell relied on Griswold's intimate-liberty reasoning"),
        ("loving","obergefell_pn","Extended","Obergefell extended Loving's marriage-as-fundamental-right"),
        ("roe_pn","obergefell_pn","Relied on","Obergefell cited Roe in substantive due process analysis"),
        ("brown_pn","loving","Extended","Loving extended Brown's anti-classification principle"),
        ("brown_pn","grutter_pn","Relied on","Grutter built on Brown's equal protection framework"),
        ("grutter_pn","sffa_pn","Overruled","SFFA overruled Grutter"),
        ("furman","gregg","Distinguished","Gregg allowed reinstated death penalty with guided discretion"),
        ("gregg","atkins","Extended","Atkins carved out intellectual disability from Gregg"),
        ("atkins","roper","Extended","Roper extended Atkins' reasoning to juveniles"),
        ("griswold_pn","miranda_pn","Relied on","Both grounded in substantive due process"),
        ("gideon_pn","miranda_pn","Relied on","Miranda built on Gideon's right-to-counsel guarantee"),
        ("marbury","furman","Relied on","Court cited judicial-review authority to reinterpret 8th Amend."),
    ]

    RELATION_COLORS_PN = {"Extended":"#27AE60","Overruled":"#E74C3C","Relied on":"#3498DB","Applied":"#9B59B6","Distinguished":"#F39C12"}
    AREA_COLORS_PN = {
        "Free Speech":"#2980B9","Right to Bear Arms":"#8E44AD","Search & Seizure":"#E67E22",
        "Self-Incrimination":"#C0392B","Takings":"#16A085","Right to Counsel":"#27AE60",
        "Cruel & Unusual":"#E74C3C","Privacy":"#F39C12","Equal Protection":"#D35400",
        "Judicial Power":"#7F8C8D","Federalism":"#BDC3C7",
    }

    def _build_graph_pn(case_filter=None, relation_filter=None):
        G = nx.DiGraph()
        for cid, (name,year,area,amend) in CASES_PN.items():
            G.add_node(cid,name=name,year=year,area=area,amend=amend)
        for src, tgt, rel, desc in EDGES_PN:
            if relation_filter and rel not in relation_filter: continue
            if case_filter:
                if src not in case_filter and tgt not in case_filter: continue
            G.add_edge(src,tgt,relation=rel,description=desc)
        return G

    def _build_network_figure_pn(G: nx.DiGraph, highlight_id=None) -> go.Figure:
        pos = nx.spring_layout(G,seed=42,k=2.5,iterations=80)
        edge_traces = []
        for src,tgt,data in G.edges(data=True):
            x0,y0 = pos[src]; x1,y1 = pos[tgt]
            rel = data.get("relation","Relied on"); color = RELATION_COLORS_PN.get(rel,"#95A5A6")
            edge_traces.append(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],mode="lines",
                                          line=dict(width=2,color=color),hoverinfo="none",showlegend=False))
            edge_traces.append(go.Scatter(x=[x1],y=[y1],mode="markers",
                                           marker=dict(size=6,color=color,symbol="arrow",angleref="previous"),
                                           hoverinfo="none",showlegend=False))
        node_ids   = list(G.nodes())
        node_names = [G.nodes[n]["name"] for n in node_ids]
        node_years = [G.nodes[n]["year"] for n in node_ids]
        node_areas = [G.nodes[n]["area"] for n in node_ids]
        node_colors  = [AREA_COLORS_PN.get(a,"#95A5A6") for a in node_areas]
        node_sizes   = [min(22+G.degree(n)*4+(12 if n==highlight_id else 0),55) for n in node_ids]
        node_borders = ["white" if n!=highlight_id else "#FFD700" for n in node_ids]
        border_widths= [2 if n!=highlight_id else 5 for n in node_ids]
        hover = [f"<b>{name}</b> ({year})<br>Area: {area}<br>Connections: {G.degree(nid)}"
                 for nid,name,year,area in zip(node_ids,node_names,node_years,node_areas)]
        node_trace = go.Scatter(
            x=[pos[n][0] for n in node_ids],y=[pos[n][1] for n in node_ids],
            mode="markers+text",
            marker=dict(size=node_sizes,color=node_colors,line=dict(color=node_borders,width=border_widths),opacity=0.92),
            text=[f"<b>{n}</b>" for n in node_names],textposition="top center",textfont=dict(size=9,color="#2C3E50"),
            hovertext=hover,hoverinfo="text",showlegend=False)
        fig = go.Figure(data=edge_traces+[node_trace])
        for rel, color in RELATION_COLORS_PN.items():
            fig.add_trace(go.Scatter(x=[None],y=[None],mode="lines",line=dict(color=color,width=3),name=rel,showlegend=True))
        fig.update_layout(title="SCOTUS Case Precedent Network",height=680,
                          xaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                          yaxis=dict(showgrid=False,zeroline=False,showticklabels=False),
                          plot_bgcolor="white",paper_bgcolor="white",margin=dict(l=20,r=20,t=50,b=20),
                          legend=dict(title="Relationship Type",orientation="v",x=1.01,y=1,xanchor="left"),
                          hovermode="closest")
        return fig

    col1_pn, col2_pn, col3_pn = st.columns(3)
    with col1_pn:
        all_areas_pn = sorted(set(v[2] for v in CASES_PN.values()))
        sel_areas_pn = st.multiselect("Filter by Legal Area",all_areas_pn,default=[],key="pn_areas")
    with col2_pn:
        sel_rels_pn = st.multiselect("Filter by Relationship Type",list(RELATION_COLORS_PN.keys()),default=[],key="pn_rels")
    with col3_pn:
        all_case_names_pn = {v[0]:k for k,v in CASES_PN.items()}
        focus_name_pn = st.selectbox("Focus on a Case (shows direct neighbors)",["— Show all —"]+sorted(all_case_names_pn.keys()),key="pn_focus")

    pn_case_filter = None; pn_highlight_id = None
    if focus_name_pn != "— Show all —":
        focus_id_pn = all_case_names_pn[focus_name_pn]
        G_full_pn = _build_graph_pn()
        neighbors_pn = set(G_full_pn.predecessors(focus_id_pn)) | set(G_full_pn.successors(focus_id_pn))
        pn_case_filter = neighbors_pn | {focus_id_pn}; pn_highlight_id = focus_id_pn

    if sel_areas_pn:
        area_filter_ids_pn = {k for k,v in CASES_PN.items() if v[2] in sel_areas_pn}
        pn_case_filter = (pn_case_filter & area_filter_ids_pn) if pn_case_filter is not None else area_filter_ids_pn

    G_pn = _build_graph_pn(case_filter=pn_case_filter, relation_filter=set(sel_rels_pn) if sel_rels_pn else None)

    if G_pn.number_of_nodes() == 0:
        st.warning("No cases match the selected filters.")
    else:
        fig_pn = _build_network_figure_pn(G_pn, highlight_id=pn_highlight_id)
        st.plotly_chart(fig_pn, use_container_width=True)
        st.caption(f"Showing {G_pn.number_of_nodes()} cases and {G_pn.number_of_edges()} relationships. Hover for details.")
        st.divider(); st.subheader("Case Detail")
        detail_name_pn = st.selectbox("Select a case to inspect its connections",sorted(all_case_names_pn.keys()),
                                       index=sorted(all_case_names_pn.keys()).index(focus_name_pn) if focus_name_pn != "— Show all —" else 0,
                                       key="pn_detail_sel")
        detail_id_pn = all_case_names_pn[detail_name_pn]
        G_full2_pn = _build_graph_pn()
        outgoing_pn = [(CASES_PN[tgt][0],d["relation"],d["description"]) for _,tgt,d in G_full2_pn.out_edges(detail_id_pn,data=True)]
        incoming_pn = [(CASES_PN[src][0],d["relation"],d["description"]) for src,_,d in G_full2_pn.in_edges(detail_id_pn,data=True)]
        case_info_pn = CASES_PN[detail_id_pn]
        st.markdown(f"### {case_info_pn[0]} ({case_info_pn[1]})")
        st.markdown(f"**Area:** {case_info_pn[2]}  |  **Amendment:** {case_info_pn[3] or 'N/A'}")
        col_out_pn, col_in_pn = st.columns(2)
        with col_out_pn:
            st.markdown("**This case influenced →**")
            if outgoing_pn:
                for target,rel,desc in outgoing_pn:
                    color = RELATION_COLORS_PN.get(rel,"#95A5A6")
                    st.markdown(f"<span style='color:{color};font-weight:bold'>{rel}</span> → **{target}**<br><small>{desc}</small>",unsafe_allow_html=True); st.markdown("")
            else: st.markdown("_No outgoing links in this dataset._")
        with col_in_pn:
            st.markdown("**← This case was influenced by**")
            if incoming_pn:
                for source,rel,desc in incoming_pn:
                    color = RELATION_COLORS_PN.get(rel,"#95A5A6")
                    st.markdown(f"**{source}** → <span style='color:{color};font-weight:bold'>{rel}</span><br><small>{desc}</small>",unsafe_allow_html=True); st.markdown("")
            else: st.markdown("_No incoming links in this dataset._")

        st.divider(); st.subheader("Most Connected Cases")
        G_all_pn = _build_graph_pn()
        degree_data_pn = [{"Case":CASES_PN[n][0],"Year":CASES_PN[n][1],"Area":CASES_PN[n][2],
                            "Amendment":CASES_PN[n][3] or "—","Total Connections":G_all_pn.degree(n),
                            "Influenced":G_all_pn.out_degree(n),"Influenced by":G_all_pn.in_degree(n)}
                           for n in G_all_pn.nodes()]
        degree_df_pn = pd.DataFrame(degree_data_pn).sort_values("Total Connections",ascending=False)
        st.dataframe(degree_df_pn,use_container_width=True,height=350)
        with st.expander("Full Relationship Table"):
            edge_rows_pn = [{"From":CASES_PN[s][0],"Relationship":r,"To":CASES_PN[t][0],"Description":d}
                            for s,t,r,d in EDGES_PN]
            edge_df_pn = pd.DataFrame(edge_rows_pn)
            rel_filter_pn = st.multiselect("Filter relationships",list(RELATION_COLORS_PN.keys()),default=[],key="pn_rel_filter")
            display_edges_pn = edge_df_pn[edge_df_pn["Relationship"].isin(rel_filter_pn)] if rel_filter_pn else edge_df_pn
            st.dataframe(display_edges_pn,use_container_width=True,height=400)
