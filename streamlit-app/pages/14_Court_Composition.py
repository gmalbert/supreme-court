import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import datetime

st.set_page_config(page_title="Court Composition Timeline", page_icon="👥", layout="wide")

# Curated justice service records
# (name, start_year, end_year_or_None, appointed_by, party_lean, seat_label)
JUSTICES = [
    # Warren Court (overlapping)
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
    # Burger Court
    ("Warren Burger",        1969, 1986, "Nixon",       "Conservative", "Chief Justice"),
    ("Harry Blackmun",       1970, 1994, "Nixon",       "Liberal",      "Associate"),
    ("Lewis Powell",         1972, 1987, "Nixon",       "Moderate",     "Associate"),
    ("William Rehnquist",    1972, 1986, "Nixon",       "Conservative", "Associate"),
    # Rehnquist Court
    ("Sandra Day O'Connor",  1981, 2006, "Reagan",      "Moderate",     "Associate"),
    ("William Rehnquist",    1986, 2005, "Reagan",      "Conservative", "Chief Justice"),
    ("Antonin Scalia",       1986, 2016, "Reagan",      "Conservative", "Associate"),
    ("Anthony Kennedy",      1988, 2018, "Reagan",      "Moderate",     "Associate"),
    ("David Souter",         1990, 2009, "G.H.W. Bush", "Liberal",     "Associate"),
    ("Clarence Thomas",      1991, None, "G.H.W. Bush", "Conservative","Associate"),
    ("Ruth Bader Ginsburg",  1993, 2020, "Clinton",     "Liberal",      "Associate"),
    ("Stephen Breyer",       1994, 2022, "Clinton",     "Liberal",      "Associate"),
    # Roberts Court
    ("John G. Roberts",      2005, None, "G.W. Bush",   "Conservative", "Chief Justice"),
    ("Samuel Alito",         2006, None, "G.W. Bush",   "Conservative", "Associate"),
    ("Sonia Sotomayor",      2009, None, "Obama",       "Liberal",      "Associate"),
    ("Elena Kagan",          2010, None, "Obama",       "Liberal",      "Associate"),
    ("Neil Gorsuch",         2017, None, "Trump",       "Conservative", "Associate"),
    ("Brett Kavanaugh",      2018, None, "Trump",       "Conservative", "Associate"),
    ("Amy Coney Barrett",    2020, None, "Trump",       "Conservative", "Associate"),
    ("Ketanji Brown Jackson",2022, None, "Biden",       "Liberal",      "Associate"),
]

CURRENT_YEAR = 2024

LEAN_COLORS = {
    "Liberal":      "#3498DB",
    "Moderate":     "#27AE60",
    "Conservative": "#E74C3C",
}

PRESIDENT_COLORS = {
    "F. Roosevelt": "#1A5276", "Truman": "#1F618D", "Eisenhower": "#922B21",
    "Kennedy": "#2471A3", "Johnson": "#1A5276", "Nixon": "#C0392B",
    "Ford": "#E74C3C", "Carter": "#2980B9", "Reagan": "#CB4335",
    "G.H.W. Bush": "#E74C3C", "Clinton": "#2E86C1", "G.W. Bush": "#CB4335",
    "Obama": "#1A5276", "Trump": "#CB4335", "Biden": "#2471A3",
}

def build_gantt(justices, color_by="Lean") -> go.Figure:
    rows = []
    for name, start, end, appointer, lean, seat in justices:
        end_yr = end if end else CURRENT_YEAR
        rows.append({
            "Justice": name,
            "Start": start,
            "End": end_yr,
            "Duration": end_yr - start,
            "Appointed by": appointer,
            "Lean": lean,
            "Seat": seat,
            "Still Serving": end is None,
        })
    df = pd.DataFrame(rows).sort_values("Start")

    if color_by == "Lean":
        color_col = "Lean"
        cmap = LEAN_COLORS
    else:
        color_col = "Appointed by"
        cmap = PRESIDENT_COLORS

    fig = go.Figure()
    for _, row in df.iterrows():
        color = cmap.get(row[color_col], "#95A5A6")
        border = "#FFD700" if row["Still Serving"] else "white"
        fig.add_trace(go.Bar(
            x=[row["Duration"]],
            y=[row["Justice"]],
            base=[row["Start"]],
            orientation="h",
            marker=dict(
                color=color,
                opacity=0.85,
                line=dict(color=border, width=1.5 if row["Still Serving"] else 0.5),
            ),
            hovertemplate=(
                f"<b>{row['Justice']}</b><br>"
                f"Served: {row['Start']} – {'present' if row['Still Serving'] else row['End']}<br>"
                f"Duration: {row['Duration']} years<br>"
                f"Appointed by: {row['Appointed by']}<br>"
                f"Lean: {row['Lean']}<br>"
                f"Seat: {row['Seat']}"
                "<extra></extra>"
            ),
            showlegend=False,
            name=row["Justice"],
        ))

    # Chief Justice era shading
    eras = [
        ("Warren Court",    1953, 1969, "rgba(41,128,185,0.06)"),
        ("Burger Court",    1969, 1986, "rgba(142,68,173,0.06)"),
        ("Rehnquist Court", 1986, 2005, "rgba(230,126,34,0.06)"),
        ("Roberts Court",   2005, CURRENT_YEAR, "rgba(192,57,43,0.06)"),
    ]
    for era_name, era_start, era_end, era_color in eras:
        fig.add_vrect(
            x0=era_start, x1=era_end,
            fillcolor=era_color, opacity=1,
            layer="below", line_width=0,
            annotation_text=era_name,
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="#7F8C8D",
        )

    # Legend traces for lean/president
    shown = set()
    for _, row in df.iterrows():
        key = row[color_col]
        if key not in shown:
            fig.add_trace(go.Bar(
                x=[None], y=[None],
                marker_color=cmap.get(key, "#95A5A6"),
                name=key,
                showlegend=True,
            ))
            shown.add(key)

    fig.update_layout(
        barmode="overlay",
        height=max(600, len(df) * 22),
        xaxis=dict(title="Year", range=[1937, CURRENT_YEAR + 2], dtick=5, gridcolor="#ECF0F1"),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=180, r=20, t=30, b=40),
        legend=dict(title=color_by, x=1.01, y=1),
        hovermode="closest",
    )
    return fig

# ── Snapshot: who was on the court in a given year ────────────────────────────
def court_in_year(year: int) -> list[dict]:
    members = []
    for name, start, end, appointer, lean, seat in JUSTICES:
        end_yr = end if end else CURRENT_YEAR + 1
        if start <= year < end_yr:
            members.append({"Justice": name, "Seat": seat, "Appointed by": appointer, "Lean": lean})
    return members

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("👥 Court Composition Timeline")
st.markdown(
    "See who sat on the Supreme Court, when they served, and how the court's "
    "ideological balance has shifted from 1937 to today."
)

tab_gantt, tab_snapshot, tab_balance = st.tabs(["Service Timeline", "Court Snapshot", "Ideological Balance"])

with tab_gantt:
    color_by = st.radio("Color bars by", ["Lean", "Appointed by"], horizontal=True)
    fig = build_gantt(JUSTICES, color_by=color_by)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Gold border = currently serving. Shaded regions = Chief Justice eras.")

with tab_snapshot:
    year = st.slider("Select Year", min_value=1953, max_value=CURRENT_YEAR, value=2024, step=1)
    members = court_in_year(year)
    if not members:
        st.info("No data for this year.")
    else:
        df_snap = pd.DataFrame(members)
        liberal = [m["Justice"] for m in members if m["Lean"] == "Liberal"]
        moderate = [m["Justice"] for m in members if m["Lean"] == "Moderate"]
        conservative = [m["Justice"] for m in members if m["Lean"] == "Conservative"]

        st.markdown(f"### Court Composition in {year}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**🔵 Liberal ({len(liberal)})**")
            for j in liberal:
                st.markdown(f"- {j}")
        with c2:
            st.markdown(f"**🟢 Moderate ({len(moderate)})**")
            for j in moderate:
                st.markdown(f"- {j}")
        with c3:
            st.markdown(f"**🔴 Conservative ({len(conservative)})**")
            for j in conservative:
                st.markdown(f"- {j}")

        st.divider()

        # Donut of composition
        counts = {"Liberal": len(liberal), "Moderate": len(moderate), "Conservative": len(conservative)}
        fig_donut = go.Figure(go.Pie(
            labels=list(counts.keys()),
            values=list(counts.values()),
            hole=0.45,
            marker_colors=[LEAN_COLORS[k] for k in counts],
            textinfo="label+value",
        ))
        fig_donut.update_layout(
            title=f"Ideological Split — {year}",
            height=320,
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(fig_donut, use_container_width=True)

        # Appointing presidents
        st.markdown("**Appointing Presidents**")
        by_president: dict[str, list] = {}
        for m in members:
            by_president.setdefault(m["Appointed by"], []).append(m["Justice"])
        for pres, justices in sorted(by_president.items()):
            st.markdown(f"- **{pres}:** {', '.join(justices)}")

with tab_balance:
    st.markdown("### Liberal vs. Conservative Balance Over Time")
    balance_rows = []
    for yr in range(1953, CURRENT_YEAR + 1):
        members = court_in_year(yr)
        lib = sum(1 for m in members if m["Lean"] == "Liberal")
        mod = sum(1 for m in members if m["Lean"] == "Moderate")
        con = sum(1 for m in members if m["Lean"] == "Conservative")
        balance_rows.append({"Year": yr, "Liberal": lib, "Moderate": mod, "Conservative": con, "Total": len(members)})

    balance_df = pd.DataFrame(balance_rows)

    fig_balance = go.Figure()
    for lean, color in LEAN_COLORS.items():
        fig_balance.add_trace(go.Scatter(
            x=balance_df["Year"],
            y=balance_df[lean],
            mode="lines",
            name=lean,
            line=dict(color=color, width=2),
            stackgroup="one",
            fill="tonexty" if lean != "Liberal" else "tozeroy",
        ))

    # Chief Justice era lines
    for era_name, era_start, era_end, _ in [
        ("Warren", 1953, 1969, ""),
        ("Burger", 1969, 1986, ""),
        ("Rehnquist", 1986, 2005, ""),
        ("Roberts", 2005, CURRENT_YEAR, ""),
    ]:
        fig_balance.add_vline(
            x=era_start, line_dash="dot", line_color="#BDC3C7", line_width=1,
            annotation_text=f"{era_name} Court",
            annotation_position="top right",
            annotation_font_size=9,
        )

    fig_balance.update_layout(
        height=400,
        xaxis_title="Year",
        yaxis_title="Number of Justices",
        yaxis=dict(range=[0, 10]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(x=1.01, y=1),
        margin=dict(l=20, r=20, t=20, b=40),
    )
    st.plotly_chart(fig_balance, use_container_width=True)
    st.caption(
        "Lean classifications are broadly based on scholarly and legal consensus. "
        "Justices' views often evolved over their tenure."
    )
