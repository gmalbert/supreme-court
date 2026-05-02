import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import datetime
from collections import defaultdict

st.set_page_config(page_title="Justice Confirmation Timeline", page_icon="🏛️", layout="wide")

CURRENT_YEAR = datetime.date.today().year

# ── Curated confirmation data ─────────────────────────────────────────────────
# Fields: name, nominated_by, nom_date, confirmed_date, yes, no, seat_lean_before,
#         seat_lean_after, seat_label, notes, replaced
CONFIRMATIONS = [
    # Modern era (1949–present), ordered chronologically
    dict(name="Tom Clark",            nominated_by="Truman",     nom_date="1949-08-02", conf_date="1949-08-18", yes=73,  no=8,  seat_lean_before="Liberal",      seat_lean_after="Moderate",     seat="Associate",       replaced="Frank Murphy",         notes=""),
    dict(name="Sherman Minton",       nominated_by="Truman",     nom_date="1949-09-15", conf_date="1949-10-04", yes=48,  no=16, seat_lean_before="Liberal",      seat_lean_after="Moderate",     seat="Associate",       replaced="Wiley Rutledge",       notes=""),
    dict(name="Earl Warren",          nominated_by="Eisenhower", nom_date="1953-10-02", conf_date="1954-03-01", yes=None, no=None, seat_lean_before="Conservative", seat_lean_after="Liberal",  seat="Chief Justice",   replaced="Fred Vinson",          notes="Recess appointment; voice vote"),
    dict(name="John Harlan II",       nominated_by="Eisenhower", nom_date="1954-11-08", conf_date="1955-03-16", yes=71,  no=11, seat_lean_before="Moderate",     seat_lean_after="Conservative", seat="Associate",      replaced="Robert Jackson",       notes=""),
    dict(name="William Brennan",      nominated_by="Eisenhower", nom_date="1956-10-15", conf_date="1957-03-19", yes=None, no=None, seat_lean_before="Moderate",  seat_lean_after="Liberal",      seat="Associate",       replaced="Sherman Minton",       notes="Recess appointment; voice vote"),
    dict(name="Charles Whittaker",    nominated_by="Eisenhower", nom_date="1957-02-19", conf_date="1957-03-19", yes=None, no=None, seat_lean_before="Moderate",  seat_lean_after="Conservative", seat="Associate",      replaced="Stanley Reed",         notes="Voice vote"),
    dict(name="Potter Stewart",       nominated_by="Eisenhower", nom_date="1958-01-17", conf_date="1959-05-05", yes=70,  no=17, seat_lean_before="Conservative", seat_lean_after="Moderate",     seat="Associate",       replaced="Harold Burton",        notes=""),
    dict(name="Byron White",          nominated_by="Kennedy",    nom_date="1962-03-30", conf_date="1962-04-11", yes=None, no=None, seat_lean_before="Liberal",   seat_lean_after="Moderate",     seat="Associate",       replaced="Charles Whittaker",    notes="Voice vote"),
    dict(name="Arthur Goldberg",      nominated_by="Kennedy",    nom_date="1962-08-31", conf_date="1962-09-25", yes=None, no=None, seat_lean_before="Conservative",seat_lean_after="Liberal",     seat="Associate",       replaced="Felix Frankfurter",    notes="Voice vote"),
    dict(name="Abe Fortas",           nominated_by="Johnson",    nom_date="1965-07-28", conf_date="1965-08-11", yes=None, no=None, seat_lean_before="Liberal",   seat_lean_after="Liberal",      seat="Associate",       replaced="Arthur Goldberg",      notes="Voice vote"),
    dict(name="Thurgood Marshall",    nominated_by="Johnson",    nom_date="1967-06-13", conf_date="1967-08-30", yes=69,  no=11, seat_lean_before="Moderate",     seat_lean_after="Liberal",      seat="Associate",       replaced="Tom Clark",            notes="First African American justice"),
    dict(name="Warren Burger",        nominated_by="Nixon",      nom_date="1969-05-21", conf_date="1969-06-09", yes=74,  no=3,  seat_lean_before="Liberal",      seat_lean_after="Conservative", seat="Chief Justice",   replaced="Earl Warren",          notes=""),
    dict(name="Harry Blackmun",       nominated_by="Nixon",      nom_date="1970-04-14", conf_date="1970-05-12", yes=94,  no=0,  seat_lean_before="Conservative", seat_lean_after="Liberal",      seat="Associate",       replaced="Abe Fortas",           notes="Two prior nominees rejected/withdrew"),
    dict(name="Lewis Powell",         nominated_by="Nixon",      nom_date="1971-10-21", conf_date="1971-12-06", yes=89,  no=1,  seat_lean_before="Liberal",      seat_lean_after="Moderate",     seat="Associate",       replaced="Hugo Black",           notes=""),
    dict(name="William Rehnquist",    nominated_by="Nixon",      nom_date="1971-10-21", conf_date="1971-12-10", yes=68,  no=26, seat_lean_before="Liberal",      seat_lean_after="Conservative", seat="Associate",       replaced="John Harlan II",       notes=""),
    dict(name="John Paul Stevens",    nominated_by="Ford",       nom_date="1975-11-28", conf_date="1975-12-17", yes=98,  no=0,  seat_lean_before="Liberal",      seat_lean_after="Liberal",      seat="Associate",       replaced="William O. Douglas",   notes=""),
    dict(name="Sandra Day O'Connor",  nominated_by="Reagan",     nom_date="1981-07-07", conf_date="1981-09-21", yes=99,  no=0,  seat_lean_before="Moderate",     seat_lean_after="Moderate",     seat="Associate",       replaced="Potter Stewart",       notes="First female justice"),
    dict(name="William Rehnquist (CJ)",nominated_by="Reagan",   nom_date="1986-06-17", conf_date="1986-09-17", yes=65,  no=33, seat_lean_before="Conservative", seat_lean_after="Conservative", seat="Chief Justice",   replaced="Warren Burger",        notes="Elevated from Associate"),
    dict(name="Antonin Scalia",       nominated_by="Reagan",     nom_date="1986-06-17", conf_date="1986-09-17", yes=98,  no=0,  seat_lean_before="Conservative", seat_lean_after="Conservative", seat="Associate",       replaced="William Rehnquist",    notes=""),
    dict(name="Anthony Kennedy",      nominated_by="Reagan",     nom_date="1987-11-11", conf_date="1988-02-03", yes=97,  no=0,  seat_lean_before="Conservative", seat_lean_after="Moderate",     seat="Associate",       replaced="Lewis Powell",         notes="Bork rejected; Ginsburg withdrew"),
    dict(name="David Souter",         nominated_by="G.H.W. Bush",nom_date="1990-07-23", conf_date="1990-10-02", yes=90,  no=9,  seat_lean_before="Liberal",      seat_lean_after="Liberal",      seat="Associate",       replaced="William Brennan",      notes=""),
    dict(name="Clarence Thomas",      nominated_by="G.H.W. Bush",nom_date="1991-07-01", conf_date="1991-10-15", yes=52,  no=48, seat_lean_before="Liberal",      seat_lean_after="Conservative", seat="Associate",       replaced="Thurgood Marshall",   notes="Anita Hill hearings; narrowest margin in modern history"),
    dict(name="Ruth Bader Ginsburg",  nominated_by="Clinton",    nom_date="1993-06-14", conf_date="1993-08-03", yes=96,  no=3,  seat_lean_before="Moderate",     seat_lean_after="Liberal",      seat="Associate",       replaced="Byron White",          notes="Second female justice"),
    dict(name="Stephen Breyer",       nominated_by="Clinton",    nom_date="1994-05-13", conf_date="1994-07-29", yes=87,  no=9,  seat_lean_before="Conservative", seat_lean_after="Liberal",      seat="Associate",       replaced="Harry Blackmun",      notes=""),
    dict(name="John G. Roberts",      nominated_by="G.W. Bush",  nom_date="2005-09-05", conf_date="2005-09-29", yes=78,  no=22, seat_lean_before="Conservative", seat_lean_after="Conservative", seat="Chief Justice",   replaced="William Rehnquist",   notes=""),
    dict(name="Samuel Alito",         nominated_by="G.W. Bush",  nom_date="2005-10-31", conf_date="2006-01-31", yes=58,  no=42, seat_lean_before="Moderate",     seat_lean_after="Conservative", seat="Associate",       replaced="Sandra Day O'Connor", notes="O'Connor's retirement shifted balance"),
    dict(name="Sonia Sotomayor",      nominated_by="Obama",      nom_date="2009-05-26", conf_date="2009-08-06", yes=68,  no=31, seat_lean_before="Liberal",      seat_lean_after="Liberal",      seat="Associate",       replaced="David Souter",        notes="First Hispanic justice"),
    dict(name="Elena Kagan",          nominated_by="Obama",      nom_date="2010-05-10", conf_date="2010-08-05", yes=63,  no=37, seat_lean_before="Liberal",      seat_lean_after="Liberal",      seat="Associate",       replaced="John Paul Stevens",   notes=""),
    dict(name="Neil Gorsuch",         nominated_by="Trump",      nom_date="2017-01-31", conf_date="2017-04-07", yes=54,  no=45, seat_lean_before="Conservative", seat_lean_after="Conservative", seat="Associate",       replaced="Antonin Scalia",      notes="Senate invoked 'nuclear option' to eliminate filibuster for SCOTUS nominees"),
    dict(name="Brett Kavanaugh",      nominated_by="Trump",      nom_date="2018-07-09", conf_date="2018-10-06", yes=50,  no=48, seat_lean_before="Moderate",     seat_lean_after="Conservative", seat="Associate",       replaced="Anthony Kennedy",     notes="Christine Blasey Ford testimony; second-narrowest modern confirmation"),
    dict(name="Amy Coney Barrett",    nominated_by="Trump",      nom_date="2020-09-26", conf_date="2020-10-26", yes=52,  no=48, seat_lean_before="Liberal",      seat_lean_after="Conservative", seat="Associate",       replaced="Ruth Bader Ginsburg", notes="Confirmed 8 days before 2020 election; no Democratic votes"),
    dict(name="Ketanji Brown Jackson",nominated_by="Biden",      nom_date="2022-02-25", conf_date="2022-04-07", yes=53,  no=47, seat_lean_before="Liberal",      seat_lean_after="Liberal",      seat="Associate",       replaced="Stephen Breyer",      notes="First Black female justice"),
]

LEAN_COLORS = {"Conservative": "#E74C3C", "Moderate": "#27AE60", "Liberal": "#3498DB"}
PRES_PARTY  = {
    "Truman": "D", "Eisenhower": "R", "Kennedy": "D", "Johnson": "D",
    "Nixon": "R", "Ford": "R", "Carter": "D", "Reagan": "R",
    "G.H.W. Bush": "R", "Clinton": "D", "G.W. Bush": "R",
    "Obama": "D", "Trump": "R", "Biden": "D",
}
PARTY_COLOR = {"R": "#E74C3C", "D": "#3498DB"}


def parse_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


def days_between(s1: str, s2: str) -> int:
    return (parse_date(s2) - parse_date(s1)).days


def ideology_flip(before: str, after: str) -> str:
    if before == after:
        return "No Change"
    lib_to_con = {"Liberal", "Moderate"} - {after}  # if after is Conservative
    if after == "Conservative" and before != "Conservative":
        return "→ Conservative"
    if after == "Liberal" and before != "Liberal":
        return "→ Liberal"
    if after == "Moderate":
        return "→ Moderate"
    return "Changed"


# Enrich data
for c in CONFIRMATIONS:
    c["nom_year"] = int(c["nom_date"][:4])
    c["conf_year"] = int(c["conf_date"][:4])
    c["days_to_confirm"] = days_between(c["nom_date"], c["conf_date"])
    c["flip"] = ideology_flip(c["seat_lean_before"], c["seat_lean_after"])
    c["pres_party"] = PRES_PARTY.get(c["nominated_by"], "?")
    c["total_votes"] = (c["yes"] or 0) + (c["no"] or 0)
    c["yes_pct"] = round(c["yes"] / c["total_votes"] * 100, 1) if c["total_votes"] > 0 else None

df = pd.DataFrame(CONFIRMATIONS)

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("🏛️ Justice Confirmation Timeline")
st.markdown(
    "The full history of Senate confirmations from 1949 to today — vote margins, "
    "days to confirm, ideological seat shifts, and the growing partisan divide."
)

tab_timeline, tab_votes, tab_speed, tab_shifts, tab_cards = st.tabs([
    "📅 Timeline", "🗳️ Vote Margins", "⏱️ Days to Confirm", "↔️ Seat Shifts", "👤 Justice Cards"
])

# ── Timeline ─────────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader("Confirmation History at a Glance")

    fig = go.Figure()

    for party, color in PARTY_COLOR.items():
        sub = df[df["pres_party"] == party]
        fig.add_trace(go.Scatter(
            x=sub["conf_year"],
            y=sub["yes"],
            mode="markers+text",
            name=f"{'Republican' if party=='R' else 'Democrat'} President",
            marker=dict(
                size=sub["yes"].fillna(50).clip(lower=30).apply(lambda v: max(8, v * 0.18)),
                color=color,
                opacity=0.85,
                line=dict(color="white", width=1),
            ),
            text=sub["name"].apply(lambda n: n.split()[0]),
            textposition="top center",
            textfont=dict(size=8),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Confirmed: %{x}<br>"
                "Vote: %{y}–%{customdata[1]}<br>"
                "Nominated by: %{customdata[2]}<br>"
                "Days to confirm: %{customdata[3]}"
                "<extra></extra>"
            ),
            customdata=list(zip(
                sub["name"], sub["no"].fillna("?"),
                sub["nominated_by"], sub["days_to_confirm"]
            )),
        ))

    # Mark ideology-flipping nominees
    flipped = df[df["flip"] != "No Change"]
    fig.add_trace(go.Scatter(
        x=flipped["conf_year"],
        y=flipped["yes"],
        mode="markers",
        marker=dict(
            symbol="star", size=16,
            color=[LEAN_COLORS.get(r["seat_lean_after"], "#95A5A6") for _, r in flipped.iterrows()],
            line=dict(color="gold", width=1.5),
        ),
        name="Seat Ideology Shifted ★",
        hovertemplate="<b>%{customdata}</b> — seat shifted<extra></extra>",
        customdata=flipped["name"],
    ))

    fig.add_hline(y=60, line_dash="dot", line_color="#E67E22",
                  annotation_text="Filibuster threshold (60)", annotation_position="top right")
    fig.add_hline(y=50, line_dash="dot", line_color="#E74C3C",
                  annotation_text="Simple majority (50)", annotation_position="bottom right")
    fig.add_vline(x=2017, line_dash="dash", line_color="#95A5A6",
                  annotation_text="Filibuster eliminated (2017)", annotation_position="top left")

    fig.update_layout(
        title="Senate Confirmation Votes Over Time",
        xaxis=dict(title="Year Confirmed", dtick=5),
        yaxis=dict(title="Yes Votes", range=[0, 105]),
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(x=1.01, y=1),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Dot size scales with yes-vote count. ★ = seat changed ideological lean. "
        "Marker color = nominating president's party."
    )

# ── Vote margins ──────────────────────────────────────────────────────────────
with tab_votes:
    st.subheader("Vote Margins — Most & Least Contested Confirmations")

    vote_df = df.dropna(subset=["yes"]).sort_values("yes", ascending=False).copy()

    col_top, col_bot = st.columns(2)
    with col_top:
        st.markdown("**Most Unanimous**")
        top = vote_df.head(10)[["name", "conf_year", "yes", "no", "nominated_by"]]
        st.dataframe(top.reset_index(drop=True), use_container_width=True, height=320, hide_index=True)

    with col_bot:
        st.markdown("**Most Contested**")
        bot = vote_df.tail(10).sort_values("yes")[["name", "conf_year", "yes", "no", "nominated_by"]]
        st.dataframe(bot.reset_index(drop=True), use_container_width=True, height=320, hide_index=True)

    # Stacked yes/no bar
    fig_votes = go.Figure()
    vote_sorted = vote_df.sort_values("conf_year")
    fig_votes.add_trace(go.Bar(
        name="Yes",
        x=vote_sorted["name"],
        y=vote_sorted["yes"],
        marker_color=[PARTY_COLOR.get(p, "#95A5A6") for p in vote_sorted["pres_party"]],
        opacity=0.85,
    ))
    fig_votes.add_trace(go.Bar(
        name="No",
        x=vote_sorted["name"],
        y=vote_sorted["no"],
        marker_color="rgba(150,150,150,0.5)",
    ))
    fig_votes.add_hline(y=60, line_dash="dot", line_color="#E67E22")
    fig_votes.update_layout(
        barmode="stack",
        title="Yes / No Votes by Justice (chronological)",
        xaxis_tickangle=-45,
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(x=1.01, y=1),
    )
    st.plotly_chart(fig_votes, use_container_width=True)

    # Partisanship trend: rolling average of yes %
    trend_df = vote_sorted.copy()
    trend_df["yes_pct"] = trend_df["yes"] / (trend_df["yes"] + trend_df["no"]) * 100
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_df["conf_year"],
        y=trend_df["yes_pct"],
        mode="lines+markers",
        line=dict(color="#3498DB", width=2),
        marker=dict(
            color=[PARTY_COLOR.get(p, "#95A5A6") for p in trend_df["pres_party"]],
            size=9,
        ),
        hovertemplate="<b>%{customdata}</b><br>Yes: %{y:.1f}%<extra></extra>",
        customdata=trend_df["name"],
    ))
    fig_trend.add_hline(y=60, line_dash="dot", line_color="#E67E22",
                        annotation_text="60% threshold")
    fig_trend.add_hline(y=50, line_dash="dot", line_color="#E74C3C")
    fig_trend.update_layout(
        title="Yes-Vote Percentage Over Time (Growing Partisan Divide)",
        yaxis=dict(title="Yes %", range=[0, 105]),
        xaxis=dict(title="Year"),
        height=320,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    st.caption("Marker color = nominating president's party (red = Republican, blue = Democrat).")

# ── Days to confirm ───────────────────────────────────────────────────────────
with tab_speed:
    st.subheader("Days from Nomination to Confirmation")

    speed_df = df.sort_values("conf_year").copy()

    fig_speed = go.Figure()
    fig_speed.add_trace(go.Bar(
        x=speed_df["name"],
        y=speed_df["days_to_confirm"],
        marker_color=[PARTY_COLOR.get(p, "#95A5A6") for p in speed_df["pres_party"]],
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Days: %{y}<br>"
            "%{customdata}"
            "<extra></extra>"
        ),
        customdata=speed_df.apply(
            lambda r: f"Nominated: {r['nom_date']}<br>Confirmed: {r['conf_date']}", axis=1
        ),
    ))

    avg_days = speed_df["days_to_confirm"].mean()
    fig_speed.add_hline(y=avg_days, line_dash="dot", line_color="#27AE60",
                        annotation_text=f"Average: {avg_days:.0f} days")

    fig_speed.update_layout(
        title="Days from Nomination to Confirmation",
        xaxis_tickangle=-45,
        yaxis_title="Days",
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig_speed, use_container_width=True)

    # Metrics
    fastest = speed_df.loc[speed_df["days_to_confirm"].idxmin()]
    slowest = speed_df.loc[speed_df["days_to_confirm"].idxmax()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Average", f"{avg_days:.0f} days")
    c2.metric("Fastest", f"{fastest['days_to_confirm']} days", delta=fastest["name"])
    c3.metric("Slowest", f"{slowest['days_to_confirm']} days", delta=slowest["name"])

    # Scatter: days vs year, sized by controversy (100 - yes%)
    speed_df2 = speed_df.dropna(subset=["yes_pct"]).copy()
    speed_df2["controversy"] = 100 - speed_df2["yes_pct"]
    fig_scatter = px.scatter(
        speed_df2,
        x="conf_year",
        y="days_to_confirm",
        size="controversy",
        color="pres_party",
        color_discrete_map=PARTY_COLOR,
        hover_name="name",
        hover_data={"conf_year": True, "days_to_confirm": True, "yes": True, "no": True},
        title="Confirmation Speed vs. Controversy (bubble size = % of No votes)",
        labels={"conf_year": "Year", "days_to_confirm": "Days", "pres_party": "Party"},
        size_max=30,
    )
    fig_scatter.update_layout(
        height=360, plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── Seat shifts ───────────────────────────────────────────────────────────────
with tab_shifts:
    st.subheader("Ideological Seat Shifts")
    st.markdown(
        "When a justice is confirmed to replace a justice of a **different** ideological lean, "
        "the court's balance can tip. These are the pivotal confirmations."
    )

    flipped_df = df[df["flip"] != "No Change"].copy()
    flipped_df["shift_label"] = flipped_df.apply(
        lambda r: f"{r['seat_lean_before']} → {r['seat_lean_after']}", axis=1
    )

    if not flipped_df.empty:
        for _, row in flipped_df.sort_values("conf_year", ascending=False).iterrows():
            before_color = LEAN_COLORS.get(row["seat_lean_before"], "#95A5A6")
            after_color  = LEAN_COLORS.get(row["seat_lean_after"],  "#95A5A6")
            st.markdown(
                f'<div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #ECF0F1;">'
                f'<div style="min-width:200px;font-weight:bold;">{row["name"]} ({row["conf_year"]})</div>'
                f'<div style="min-width:120px;color:#555;">Replaced: {row["replaced"]}</div>'
                f'<span style="background:{before_color};color:white;padding:2px 9px;border-radius:4px;margin:0 6px;">'
                f'{row["seat_lean_before"]}</span>'
                f'<span style="font-size:1.2em;margin:0 4px;">→</span>'
                f'<span style="background:{after_color};color:white;padding:2px 9px;border-radius:4px;margin:0 6px;">'
                f'{row["seat_lean_after"]}</span>'
                f'<span style="color:#888;font-size:0.88em;margin-left:12px;">'
                f'Nominated by {row["nominated_by"]}  ·  '
                f'{row["yes"]}–{row["no"]} vote'
                f'{" (" + row["notes"] + ")" if row["notes"] else ""}'
                f'</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.subheader("Running Ideological Balance of the Court")

    # Simulate the court's ideological breakdown after each confirmation
    balance_rows = []
    # Starting composition before 1949 (approximate)
    lean_counts = {"Liberal": 4, "Conservative": 2, "Moderate": 3}

    for _, row in df.sort_values("conf_year").iterrows():
        # Remove predecessor's lean
        pred_lean = row["seat_lean_before"]
        if pred_lean in lean_counts and lean_counts[pred_lean] > 0:
            lean_counts[pred_lean] -= 1
        # Add new justice's lean
        new_lean = row["seat_lean_after"]
        lean_counts[new_lean] = lean_counts.get(new_lean, 0) + 1

        balance_rows.append({
            "Justice": row["name"],
            "Year": row["conf_year"],
            "Liberal": lean_counts.get("Liberal", 0),
            "Moderate": lean_counts.get("Moderate", 0),
            "Conservative": lean_counts.get("Conservative", 0),
        })

    bal_df = pd.DataFrame(balance_rows)
    fig_bal = go.Figure()
    for lean, color in LEAN_COLORS.items():
        fig_bal.add_trace(go.Scatter(
            x=bal_df["Year"],
            y=bal_df[lean],
            mode="lines+markers",
            name=lean,
            line=dict(color=color, width=2),
            stackgroup="one",
            fill="tonexty" if lean != "Liberal" else "tozeroy",
            hovertemplate=f"<b>{lean}</b>: %{{y}} justices after %{{customdata}}<extra></extra>",
            customdata=bal_df["Justice"],
        ))
    fig_bal.update_layout(
        title="Court Composition After Each Confirmation",
        yaxis=dict(title="Justices", range=[0, 10]),
        xaxis_title="Year",
        height=360,
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(x=1.01, y=1),
    )
    st.plotly_chart(fig_bal, use_container_width=True)

# ── Justice cards ─────────────────────────────────────────────────────────────
with tab_cards:
    st.subheader("Justice Confirmation Cards")

    search_j = st.text_input("Search by name or nominating president")
    card_src = CONFIRMATIONS
    if search_j:
        q = search_j.lower()
        card_src = [c for c in card_src
                    if q in c["name"].lower() or q in c["nominated_by"].lower()]

    for c in sorted(card_src, key=lambda x: x["conf_year"], reverse=True):
        after_color  = LEAN_COLORS.get(c["seat_lean_after"],  "#95A5A6")
        pres_color   = PARTY_COLOR.get(c["pres_party"], "#95A5A6")
        vote_str = f"{c['yes']}–{c['no']}" if c["yes"] else "Voice vote"
        yes_pct  = f" ({c['yes_pct']}%)" if c["yes_pct"] else ""

        with st.expander(
            f"**{c['name']}** — {c['nom_date'][:4]} | {vote_str} | {c['flip']}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Nominated by:** {c['nominated_by']}")
            col1.markdown(f"**Nomination date:** {c['nom_date']}")
            col1.markdown(f"**Confirmed:** {c['conf_date']}")
            col1.markdown(f"**Days to confirm:** {c['days_to_confirm']}")

            col2.markdown(f"**Vote:** {vote_str}{yes_pct}")
            col2.markdown(f"**Seat:** {c['seat']}")
            col2.markdown(f"**Replaced:** {c['replaced']}")

            col3.markdown(
                f'**Lean before:** <span style="color:{LEAN_COLORS.get(c["seat_lean_before"],"#95A5A6")}">'
                f'■ {c["seat_lean_before"]}</span>',
                unsafe_allow_html=True,
            )
            col3.markdown(
                f'**Lean after:** <span style="color:{after_color}">■ {c["seat_lean_after"]}</span>',
                unsafe_allow_html=True,
            )
            col3.markdown(
                f'**Seat shift:** <span style="font-weight:bold;">{c["flip"]}</span>',
                unsafe_allow_html=True,
            )
            if c["notes"]:
                st.info(c["notes"])
