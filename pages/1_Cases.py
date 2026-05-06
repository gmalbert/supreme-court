import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import datetime
import re
import time
from collections import defaultdict
from utils.oyez_api import search_cases, get_case_detail, get_cases_by_term, get_recent_terms, extract_court_journey
from utils.charts import build_journey_diagram, build_voting_chart, build_issue_area_chart, build_decision_trend_chart
from utils.local_data import strip_html, safe_md, fetch_oyez, infer_issue_area


from utils import add_sidebar_logo
add_sidebar_logo()

HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
TODAY        = datetime.date.today()
CURRENT_YEAR = TODAY.year
CURRENT_TERM = TODAY.year if TODAY.month >= 10 else TODAY.year - 1

# ── Shared fetch helpers ──────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_cases_term(term: int) -> list[dict]:
    data = fetch_oyez(f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=300&page=0")
    return data if isinstance(data, list) else []

@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_detail(href: str) -> dict | None:
    data = fetch_oyez(href)
    return data if isinstance(data, dict) else None

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("⚖️ Cases")
tab_search, tab_timeline, tab_oral, tab_calendar = st.tabs([
    "🔍 Search Cases", "📅 Timeline Browser", "🎙️ Oral Arguments", "🗓️ Term Calendar"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: SEARCH CASES
# ──────────────────────────────────────────────────────────────────────────────
with tab_search:
    st.markdown("Search by case name across recent terms (2000–present).")
    query = st.text_input("Enter case name or keyword",
                          placeholder="e.g. Roe, Citizens United, Obergefell",
                          key="search_query")

    if query and len(query) >= 3:
        with st.spinner(f'Searching for "{query}"...'):
            results = search_cases(query)

        if not results:
            st.warning("No cases found. Try a different keyword.")
        else:
            st.success(f"Found {len(results)} matching case(s).")
            case_names = sorted([c.get("name", "Unknown") for c in results])
            selected = st.selectbox("Select a case to view", case_names, key="search_sel")
            selected_case = next((c for c in results if c.get("name") == selected), None)

            if selected_case:
                href = selected_case.get("href", "")
                with st.spinner("Loading case details..."):
                    detail = get_case_detail(href) if href else None

                if not detail:
                    st.warning("Could not load case details.")
                else:
                    st.subheader(detail.get("name", selected))
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        desc = detail.get("description") or detail.get("facts_of_the_case", "")
                        if desc:
                            with st.expander("Background & Facts"):
                                st.write(safe_md(desc))
                        q = detail.get("question", "")
                        if q:
                            with st.expander("Legal Question"):
                                st.write(safe_md(q))
                    with col2:
                        st.markdown("**Metadata**")
                        st.markdown(f"- **Docket:** {detail.get('docket_number', 'N/A')}")
                        _dec_m = (detail.get("decisions") or [{}])[0]
                        _disp_m = (_dec_m.get("decision_type") or "").strip().title()
                        if _disp_m:
                            st.markdown(f"- **Disposition:** {_disp_m}")
                        decided_by = detail.get("decided_by") or {}
                        if decided_by:
                            st.markdown(f"- **Decided by:** {decided_by.get('name', 'N/A')}")

                    st.subheader("⬆️ Case Journey")
                    steps = extract_court_journey(detail)
                    lower = detail.get("lower_court") or {}
                    lc_name = lower.get("name", "") if isinstance(lower, dict) else ""
                    if len(steps) < 2 and lc_name:
                        steps = [
                            {"court": lc_name, "level": "Lower Court", "decision": ""},
                            {"court": "U.S. Supreme Court", "level": "Supreme Court", "decision": ""},
                        ]
                    if steps:
                        if isinstance(detail.get("disposition"), dict):
                            steps[-1]["decision"] = detail["disposition"].get("label", "")
                        fig = build_journey_diagram(steps, detail.get("name", selected))
                        if fig:
                            st.plotly_chart(fig)
                    else:
                        st.info("Journey data not available for this case.")

                    st.subheader("⚖️ Justice Votes")
                    justices = []
                    for dec in (detail.get("decisions") or []):
                        for vote in (dec.get("votes") or []):
                            member = vote.get("member", {}) or {}
                            justices.append({"name": member.get("name", "Unknown"), "vote": vote.get("vote", "")})
                    if justices:
                        fig2 = build_voting_chart(justices)
                        if fig2:
                            st.plotly_chart(fig2)
                    else:
                        st.info("Voting data not available for this case.")
    elif query:
        st.info("Please enter at least 3 characters to search.")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: TIMELINE BROWSER
# ──────────────────────────────────────────────────────────────────────────────
with tab_timeline:
    st.markdown("Browse Supreme Court cases across terms and explore trends.")
    terms_available = get_recent_terms(20)
    col1, col2 = st.columns(2)
    with col1:
        start_term = st.selectbox("From Term", terms_available, index=len(terms_available) - 1, key="tl_start")
    with col2:
        end_term = st.selectbox("To Term", terms_available, index=0, key="tl_end")

    if start_term > end_term:
        start_term, end_term = end_term, start_term
    selected_terms = list(range(start_term, end_term + 1))

    if st.button("Load Timeline", type="primary", key="tl_btn"):
        cases_by_term: dict[int, list] = {}
        progress = st.progress(0)
        for i, t in enumerate(selected_terms):
            with st.spinner(f"Loading term {t}..."):
                cases_by_term[t] = get_cases_by_term(t)
            progress.progress((i + 1) / len(selected_terms))
        st.session_state["tl_cases_by_term"] = cases_by_term
        progress.empty()

    if "tl_cases_by_term" in st.session_state:
        cases_by_term = st.session_state["tl_cases_by_term"]
        trend_fig = build_decision_trend_chart(cases_by_term)
        if trend_fig:
            st.plotly_chart(trend_fig)

        all_cases = []
        for term, cases in cases_by_term.items():
            for c in cases:
                all_cases.append({
                    "Term": term,
                    "Case Name": c.get("name", ""),
                    "Issue Area": infer_issue_area(c),
                    "Decided": c.get("term", ""),
                })

        if all_cases:
            df = pd.DataFrame(all_cases)
            issue_fig = build_issue_area_chart(all_cases)
            if issue_fig:
                st.plotly_chart(issue_fig)
            st.subheader("All Cases")
            issue_filter = st.multiselect("Filter by Issue Area", sorted(df["Issue Area"].unique()), default=[], key="tl_filter")
            if issue_filter:
                df = df[df["Issue Area"].isin(issue_filter)]
            st.dataframe(df, height=400, hide_index=True)
            st.caption(f"Showing {len(df)} cases across {len(cases_by_term)} term(s).")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: ORAL ARGUMENTS BROWSER
# ──────────────────────────────────────────────────────────────────────────────
with tab_oral:
    st.markdown(
        "Browse oral argument recordings from the Oyez archive — "
        "the most comprehensive free source of Supreme Court audio."
    )
    oa_term = st.selectbox("Select Term", list(range(CURRENT_YEAR-1, CURRENT_YEAR - 33, -1)), key="oa_term")

    with st.spinner("Loading cases..."):
        oa_cases = _fetch_cases_term(oa_term)

    if not oa_cases:
        st.warning("No cases found for this term.")
    else:
        oa_search = st.text_input("Search by case name", placeholder="e.g. Biden, Chevron, EPA", key="oa_search")
        if oa_search:
            oa_cases = [c for c in oa_cases if oa_search.lower() in c.get("name", "").lower()]

        st.markdown(f"**{len(oa_cases)} case(s) found.** Select one to load oral argument details.")
        oa_names = sorted([c.get("name", "Unknown") for c in oa_cases])
        oa_selected_name = st.selectbox("Select Case", oa_names, key="oa_sel")
        oa_selected = next((c for c in oa_cases if c.get("name") == oa_selected_name), None)

        if oa_selected:
            oa_href = oa_selected.get("href", "")
            with st.spinner("Loading case details..."):
                oa_detail = _fetch_detail(oa_href) if oa_href else None

            if not oa_detail:
                st.error("Could not load case details.")
            else:
                col_main, col_side = st.columns([2, 1])
                with col_main:
                    st.subheader(oa_detail.get("name", oa_selected_name))
                    question = oa_detail.get("question", "")
                    if question:
                        with st.expander("Legal Question"):
                            st.write(safe_md(question))
                with col_side:
                    decided_by = oa_detail.get("decided_by") or {}
                    _dec_oa = (oa_detail.get("decisions") or [{}])[0]
                    _disp_oa = (_dec_oa.get("decision_type") or "").strip().title()
                    st.markdown(f"- **Docket:** {oa_detail.get('docket_number', 'N/A')}")
                    if decided_by:
                        st.markdown(f"- **Court:** {decided_by.get('name', 'N/A')}")
                    if _disp_oa:
                        st.markdown(f"- **Disposition:** {_disp_oa}")

                st.divider()
                oral_args = oa_detail.get("oral_argument_audio") or []

                if not oral_args:
                    st.info("No oral argument audio is listed for this case in the Oyez database.")
                else:
                    docket = oa_detail.get("docket_number", "")
                    oyez_case_url = f"https://www.oyez.org/cases/{oa_term}/{docket}"
                    st.subheader(f"🎧 {len(oral_args)} Oral Argument Session(s)")
                    for i, arg in enumerate(oral_args):
                        if not isinstance(arg, dict):
                            continue
                        title = arg.get("title", f"Session {i+1}")
                        arg_href = arg.get("href", "")
                        with st.expander(f"**{title}**", expanded=(i == 0)):
                            if arg_href:
                                st.markdown(f"[🎧 Listen on Oyez.org]({oyez_case_url})")
                                with st.spinner("Loading argument detail..."):
                                    arg_detail = _fetch_detail(arg_href)
                                if arg_detail:
                                    duration = arg_detail.get("duration")
                                    if duration:
                                        mins, secs = divmod(int(duration), 60)
                                        st.markdown(f"**Duration:** {mins}m {secs}s")
                                    transcript = arg_detail.get("transcript") or {}
                                    sections = transcript.get("sections") or []
                                    if sections:
                                        st.markdown("**Transcript Excerpt**")
                                        for section in sections[:1]:
                                            for turn in (section.get("turns") or [])[:6]:
                                                speaker = turn.get("speaker") or {}
                                                speaker_name = speaker.get("name", "Unknown") if isinstance(speaker, dict) else str(speaker)
                                                blocks = turn.get("text_blocks") or []
                                                text = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict)).strip()
                                                if text:
                                                    st.markdown(f"**{speaker_name}:** {text[:400]}{'…' if len(text) > 400 else ''}")
                            else:
                                st.info("No direct audio link available.")

                st.divider()
                st.subheader("Other Cases This Term")
                preview_rows = [{"Case": c.get("name", ""), "Docket": c.get("docket_number", "")} for c in oa_cases[:30]]
                st.dataframe(pd.DataFrame(preview_rows), height=280, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: TERM CALENDAR
# ──────────────────────────────────────────────────────────────────────────────
with tab_calendar:
    MONTH_ORDER = ["October","November","December","January","February","March",
                   "April","May","June","July","August","September"]
    STATUS_COLOR = {"Decided":"#27AE60","Argued, Pending Decision":"#3498DB","Scheduled":"#E67E22","Granted, Not Yet Argued":"#9B59B6","Unknown":"#95A5A6"}
    STATUS_ICON  = {"Decided":"✅","Argued, Pending Decision":"🔵","Scheduled":"📅","Granted, Not Yet Argued":"📌","Unknown":"❓"}

    def _parse_unix(ts):
        try:
            if ts: return datetime.date.fromtimestamp(int(ts))
        except Exception: pass
        return None

    def _date_from_timeline(timeline, event_name):
        """Extract the first date for a named timeline event."""
        for event in (timeline or []):
            if event.get("event") == event_name:
                dates = event.get("dates") or []
                if dates:
                    return _parse_unix(dates[0])
        return None

    def _case_status(detail, arg_date, decided_date, dismissed=False):
        if decided_date or dismissed: return "Decided"
        if arg_date and arg_date <= TODAY: return "Argued, Pending Decision"
        if arg_date and arg_date > TODAY: return "Scheduled"
        if detail.get("decisions"): return "Decided"
        if detail.get("oral_argument_audio"): return "Argued, Pending Decision"
        return "Granted, Not Yet Argued"

    cal_terms = list(range(CURRENT_TERM, CURRENT_TERM - 10, -1))
    cal_term = st.selectbox("Select Term", cal_terms, format_func=lambda t: f"{t}–{t+1} Term", key="cal_term")

    with st.spinner(f"Loading {cal_term}–{cal_term+1} term docket…"):
        # Recent two terms: always fetch live for up-to-date statuses
        if cal_term >= CURRENT_TERM - 1:
            try:
                _live = requests.get(
                    f"{OYEZ_BASE}/cases?filter=term:{cal_term}&per_page=300&page=0",
                    headers=HEADERS, timeout=15)
                cal_summary = _live.json() if _live.ok and isinstance(_live.json(), list) else []
            except Exception:
                cal_summary = _fetch_cases_term(cal_term)
        else:
            cal_summary = _fetch_cases_term(cal_term)

    if not cal_summary:
        st.error("Could not load cases for this term.")
    else:
        st.info(f"Found **{len(cal_summary)}** cases.")
        progress_cal = st.progress(0.0, text="Fetching case details…")
        cal_data = []

        for i, c in enumerate(cal_summary):
            # Use the summary timeline for dates — it's fresh for the current term
            sum_tl       = c.get("timeline") or []
            decided_date = _date_from_timeline(sum_tl, "Decided")
            arg_date     = (_date_from_timeline(sum_tl, "Argued") or
                            _date_from_timeline(sum_tl, "Reargued"))
            dismissed    = any(e.get("event") == "Dismissed" for e in sum_tl)

            href   = c.get("href", "")
            detail = _fetch_detail(href) if href else None

            if detail:
                oral_args  = detail.get("oral_argument_audio") or []
                issue      = infer_issue_area(detail)
                _dec_cal   = (detail.get("decisions") or [{}])[0]
                disp_label = (_dec_cal.get("decision_type") or "").strip().title()
                decisions  = detail.get("decisions") or []
                vote_split = ""
                for dec in decisions:
                    votes = dec.get("votes") or []
                    maj = sum(1 for v in votes if (v.get("vote") or "").lower() in ("majority","concurrence"))
                    dis = sum(1 for v in votes if (v.get("vote") or "").lower() in ("dissent","minority"))
                    if maj or dis:
                        vote_split = f"{maj}-{dis}"; break
            else:
                oral_args, issue, disp_label, vote_split = [], "Unknown", "", ""

            cal_data.append({
                "name": c.get("name", ""),
                "docket": c.get("docket_number", ""),
                "issue_area": issue,
                "status": _case_status(detail or {}, arg_date, decided_date, dismissed),
                "arg_date": arg_date, "decided_date": decided_date,
                "disposition": disp_label, "vote_split": vote_split, "href": href,
                "has_audio": bool(oral_args) or bool(c.get("oral_argument_audio")),
            })
            progress_cal.progress((i+1)/len(cal_summary), text=f"Loaded {i+1}/{len(cal_summary)} cases…")

        progress_cal.empty()
        cal_df = pd.DataFrame(cal_data)

        decided_n   = (cal_df["status"] == "Decided").sum()
        argued_n    = (cal_df["status"] == "Argued, Pending Decision").sum()
        scheduled_n = (cal_df["status"] == "Scheduled").sum()
        cert_n      = (cal_df["status"] == "Granted, Not Yet Argued").sum()

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Cases", len(cal_df))
        m2.metric("✅ Decided", decided_n)
        m3.metric("🔵 Argued, Pending", argued_n)
        m4.metric("📅 Scheduled", scheduled_n)
        m5.metric("📌 Granted, Not Argued", cert_n)
        st.divider()

        sub_tl, sub_monthly, sub_list, sub_issue = st.tabs(["🗓️ Timeline","📆 Monthly View","📋 Full Docket","🏛️ Issue Areas"])

        with sub_tl:
            tl_rows = []
            for _, row in cal_df.iterrows():
                anchor = row["decided_date"] or row["arg_date"]
                if anchor:
                    tl_rows.append({"Case": row["name"][:55]+("…" if len(row["name"])>55 else ""),
                                    "Date": pd.Timestamp(anchor), "Status": row["status"],
                                    "Issue": row["issue_area"], "Disposition": row["disposition"], "Vote": row["vote_split"]})
            if tl_rows:
                tl_df2 = pd.DataFrame(tl_rows).sort_values("Date")
                fig_tl = px.scatter(tl_df2, x="Date", y="Status", color="Status",
                                    color_discrete_map=STATUS_COLOR, hover_name="Case",
                                    hover_data={"Date":True,"Issue":True,"Disposition":True,"Vote":True,"Status":False},
                                    title=f"{cal_term}–{cal_term+1} SCOTUS Term — Cases by Date & Status",
                                    category_orders={"Status":["Decided","Argued, Pending Decision","Scheduled","Granted, Not Yet Argued"]})
                fig_tl.update_traces(marker=dict(size=12, opacity=0.85))
                fig_tl.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig_tl)
            else:
                st.info("Not enough date data for a timeline yet.")

            both_dates = cal_df.dropna(subset=["arg_date","decided_date"]).copy()
            if not both_dates.empty:
                st.markdown("**Argued → Decided Duration**")
                both_dates = both_dates.sort_values("arg_date")
                fig_gantt = go.Figure()
                for _, row in both_dates.iterrows():
                    name_short = row["name"][:50]+("…" if len(row["name"])>50 else "")
                    arg_ts = pd.Timestamp(row["arg_date"]); dec_ts = pd.Timestamp(row["decided_date"])
                    days = (row["decided_date"]-row["arg_date"]).days
                    fig_gantt.add_trace(go.Bar(
                        x=[(dec_ts-arg_ts).days], y=[name_short], base=[arg_ts.timestamp()*1000],
                        orientation="h", marker_color=STATUS_COLOR.get(row["status"],"#95A5A6"),
                        hovertemplate=f"<b>{name_short}</b><br>Argued: {row['arg_date']}<br>Decided: {row['decided_date']}<br>Days: {days}<extra></extra>",
                        showlegend=False))
                fig_gantt.update_layout(height=max(250,len(both_dates)*24),
                                        xaxis=dict(type="date",title="Date",tickformat="%b %Y"),
                                        yaxis=dict(autorange="reversed"),
                                        plot_bgcolor="white",paper_bgcolor="white",
                                        margin=dict(l=200,r=20,t=20,b=40))
                st.plotly_chart(fig_gantt)

        with sub_monthly:
            month_buckets: dict[str, list] = defaultdict(list)
            for _, row in cal_df.iterrows():
                if row["arg_date"]: lbl = row["arg_date"].strftime("%B %Y")
                elif row["decided_date"]: lbl = "Decided (no arg date)"
                else: lbl = "Pending / Scheduled"
                month_buckets[lbl].append(row)

            def _sort_month(label):
                try: return datetime.datetime.strptime(label, "%B %Y")
                except Exception: return datetime.datetime(9999,1,1)

            for month_lbl in sorted(month_buckets, key=_sort_month):
                c_list = month_buckets[month_lbl]
                decided_ct = sum(1 for c in c_list if c["status"]=="Decided")
                with st.expander(f"**{month_lbl}** — {len(c_list)} case(s), {decided_ct} decided", expanded=False):
                    for c in c_list:
                        icon = STATUS_ICON.get(c["status"],"❓")
                        vote_str = f"  ·  **{c['vote_split']}**" if c["vote_split"] else ""
                        disp_str = f"  ·  {c['disposition']}" if c["disposition"] else ""
                        st.markdown(f'{icon} <span style="font-weight:bold;">{c["name"]}</span>'
                                    f' <span style="color:#7F8C8D;font-size:0.85em;">({c["issue_area"]})</span>'
                                    f'{vote_str}{disp_str}', unsafe_allow_html=True)

        with sub_list:
            status_options = ["All"] + sorted(cal_df["status"].unique())
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1: cal_status_sel = st.selectbox("Filter by status", status_options, key="cal_status_sel")
            with col_f2: cal_search_q = st.text_input("Search case name", key="cal_search_q")
            view = cal_df.copy()
            if cal_status_sel != "All": view = view[view["status"] == cal_status_sel]
            if cal_search_q: view = view[view["name"].str.contains(cal_search_q, case=False, na=False)]
            view = view.sort_values(["decided_date","arg_date"], ascending=[False,False], na_position="last")
            for _, row in view.iterrows():
                icon = STATUS_ICON.get(row["status"],"❓")
                arg_str = str(row["arg_date"]) if row["arg_date"] else "—"
                dec_str = str(row["decided_date"]) if row["decided_date"] else "pending"
                audio_badge = " 🎙️" if row["has_audio"] else ""
                with st.expander(f'{icon} **{row["name"]}** — {row["status"]}{audio_badge}'):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(f"**Docket:** {row['docket'] or '—'}")
                    c2.markdown(f"**Issue:** {row['issue_area']}")
                    c3.markdown(f"**Argued:** {arg_str}")
                    c4.markdown(f"**Decided:** {dec_str}")
                    if row["disposition"]:
                        st.markdown(f"**Disposition:** {row['disposition']}  |  **Vote:** {row['vote_split'] or '—'}")
                    if row["href"]:
                        st.markdown(f"[Open on Oyez ↗]({row['href'].replace('api.oyez.org/cases','www.oyez.org/cases')})")

        with sub_issue:
            issue_status_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for _, row in cal_df.iterrows():
                issue_status_map[row["issue_area"]][row["status"]] += 1
            issue_rows_cal = [{"Issue Area": a, **s, "Total": sum(s.values())} for a, s in issue_status_map.items()]
            issue_df_cal = pd.DataFrame(issue_rows_cal).fillna(0).sort_values("Total", ascending=False)
            status_cols = [s for s in ["Decided","Argued, Pending Decision","Scheduled","Granted, Not Yet Argued","Unknown"] if s in issue_df_cal.columns]
            fig_issue_cal = go.Figure()
            for s in status_cols:
                fig_issue_cal.add_trace(go.Bar(name=s, x=issue_df_cal["Issue Area"], y=issue_df_cal[s],
                                               marker_color=STATUS_COLOR.get(s,"#95A5A6")))
            fig_issue_cal.update_layout(barmode="stack", title=f"{cal_term}–{cal_term+1} Term — Cases by Issue Area",
                                        xaxis_tickangle=-35, height=400, plot_bgcolor="white", paper_bgcolor="white",
                                        legend=dict(x=1.01, y=1))
            st.plotly_chart(fig_issue_cal)
