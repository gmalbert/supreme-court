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
from utils.export import csv_download_button
from utils.text_search import search as text_search, is_available as text_search_available


from utils import add_sidebar_logo, watchlist_button
add_sidebar_logo()

HEADERS   = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"
TODAY        = datetime.date.today()
CURRENT_YEAR = TODAY.year
CURRENT_TERM = TODAY.year if TODAY.month >= 10 else TODAY.year - 1

# ── Shared fetch helpers ──────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_cases_term(term: int) -> list[dict]:
    return get_cases_by_term(term)

@st.cache_data(show_spinner=False, ttl=3600)
def _fetch_detail(href: str) -> dict | None:
    from utils.oyez_api import get_case_detail
    return get_case_detail(href)

@st.cache_data(show_spinner=False)
def _build_issue_area_index() -> dict[str, list[dict]]:
    """Build {issue_area: [{name, href, term, docket_number}]} from cases_by_term parquet."""
    try:
        _df = pd.read_parquet(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cases_by_term.parquet"),
            columns=["name", "href", "term", "docket_number", "question", "description"],
        )
    except Exception:
        return {}
    index: dict[str, list[dict]] = {}
    for row in _df.itertuples(index=False):
        _q = row.question if isinstance(row.question, str) else ""
        _d = row.description if isinstance(row.description, str) else ""
        area = infer_issue_area({"question": _q, "description": _d})
        entry = {"name": row.name, "href": row.href, "term": row.term, "docket_number": row.docket_number}
        index.setdefault(area, []).append(entry)
    return index

# ── Page ─────────────────────────────────────────────────────────────────────
st.title("⚖️ Cases")

# If navigated from home search box, auto-run the search before rendering tabs
if st.session_state.get("_home_trigger_search") and st.session_state.get("desc_query"):
    _auto_query = st.session_state["desc_query"]
    _auto_n     = st.session_state.pop("_home_desc_n_val", 8) or 8
    st.session_state.pop("_home_trigger_search", None)
    with st.spinner("Searching 8,000+ cases…"):
        _auto_results = text_search(_auto_query, top_k=_auto_n)
    st.session_state["desc_results"] = _auto_results
    st.session_state.pop("desc_selected_href", None)

# If there are description search results in session state, lead with that tab
# so it stays active across reruns (e.g. when clicking View on a result).
_show_desc_first = bool(st.session_state.get("desc_results"))

if _show_desc_first:
    tab_describe, tab_search, tab_timeline, tab_oral, tab_calendar = st.tabs([
        "💬 Find by Description", "🔍 Search Cases", "📅 Timeline Browser", "🎙️ Oral Arguments", "🗓️ Term Calendar"
    ])
else:
    tab_search, tab_describe, tab_timeline, tab_oral, tab_calendar = st.tabs([
        "🔍 Search Cases", "💬 Find by Description", "📅 Timeline Browser", "🎙️ Oral Arguments", "🗓️ Term Calendar"
    ])

# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: SEARCH CASES
# ──────────────────────────────────────────────────────────────────────────────
with tab_search:
    st.markdown("Search by case name across recent terms (2000–present).")
    # ── URL deep-link: read ?q= and ?case= on first load ─────────────────────
    _qp = st.query_params
    if "q" in _qp and "search_query" not in st.session_state:
        st.session_state["search_query"] = _qp["q"]
    # Pre-populate from Today-in-History "Explore" button (uses session state handoff)
    if "_today_case_query" in st.session_state:
        st.session_state["search_query"] = st.session_state.pop("_today_case_query")
    query = st.text_input("Enter case name or keyword",
                          placeholder="e.g. Roe, Citizens United, Obergefell",
                          key="search_query")
    # Keep ?q= in sync with the current query
    if query:
        st.query_params["q"] = query
    else:
        st.query_params.clear()

    if query and len(query) >= 3:
        with st.spinner(f'Searching for "{query}"...'):
            results = search_cases(query)

        if not results:
            st.warning("No cases found. Try a different keyword.")
        else:
            st.success(f"Found {len(results)} matching case(s).")
            case_names = sorted([c.get("name", "Unknown") for c in results])
            # Pre-select from ?case= URL param if present
            _case_param = _qp.get("case", "")
            _default_idx = case_names.index(_case_param) if _case_param in case_names else 0
            selected = st.selectbox("Select a case to view", case_names, index=_default_idx, key="search_sel")
            selected_case = next((c for c in results if c.get("name") == selected), None)

            if selected_case:
                href = selected_case.get("href", "")
                with st.spinner("Loading case details..."):
                    detail = get_case_detail(href) if href else None

                if not detail:
                    st.warning("Could not load case details.")
                else:
                    st.subheader(detail.get("name", selected))
                    # Write ?case= so this exact case is shareable via URL
                    st.query_params["case"] = selected
                    _base_url = os.environ.get("STREAMLIT_SERVER_BASE_URL_PATH", "")
                    st.caption(f"🔗 Shareable URL: `?q={query.replace(' ', '+')}&case={selected.replace(' ', '+')}`")
                    # Watchlist bookmark
                    _api_href_ts = detail.get("href", "")
                    _oyez_url_ts = _api_href_ts.replace("https://api.oyez.org/", "https://www.oyez.org/") if _api_href_ts else ""
                    watchlist_button(selected, oyez_url=_oyez_url_ts, key_suffix="tab_search")
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
                        holding = strip_html(detail.get("conclusion") or "")
                        if holding:
                            with st.expander("⚖️ Holding"):
                                st.write(safe_md(holding))
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
                            st.plotly_chart(fig, )
                    else:
                        st.info("Journey data not available for this case.")

                    _decs = detail.get("decisions") or []
                    _decs_with_votes = [d for d in _decs if d.get("votes")]
                    if _decs_with_votes:
                        _first_votes = _decs_with_votes[0].get("votes") or []
                        _maj = sum(1 for v in _first_votes if (v.get("vote") or "").lower() in ("majority", "concurrence"))
                        _dis = sum(1 for v in _first_votes if (v.get("vote") or "").lower() in ("dissent", "minority"))
                        _vote_label = f" &mdash; {_maj}&ndash;{_dis}" if _maj + _dis > 0 else ""
                        st.subheader(f"⚖️ Justice Votes{_vote_label}")
                    else:
                        st.subheader("⚖️ Justice Votes")
                    if _decs_with_votes:
                        if len(_decs_with_votes) > 1:
                            _dec_labels = []
                            for i, d in enumerate(_decs_with_votes):
                                _desc = (d.get("description") or "").strip()
                                _label = _desc if _desc else f"Question {i + 1}"
                                _dec_labels.append(_label)
                            _sel_label = st.selectbox(
                                "Decision / Question",
                                _dec_labels,
                                key=f"dec_sel_{selected}",
                            )
                            _sel_dec = _decs_with_votes[_dec_labels.index(_sel_label)]
                        else:
                            _sel_dec = _decs_with_votes[0]
                        justices = []
                        for vote in (_sel_dec.get("votes") or []):
                            member = vote.get("member", {}) or {}
                            justices.append({"name": member.get("name", "Unknown"), "vote": vote.get("vote", "")})
                        fig2 = build_voting_chart(justices)
                        if fig2:
                            st.plotly_chart(fig2, )
                    else:
                        st.info("Voting data not available for this case.")
    elif query:
        st.info("Please enter at least 3 characters to search.")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: FIND BY DESCRIPTION (TF-IDF semantic search)
# ──────────────────────────────────────────────────────────────────────────────
with tab_describe:
    if not text_search_available():
        st.warning("Semantic search is not available. Ensure `data/case_detail.parquet` exists and scikit-learn is installed.")
    else:
        # ── Search bar (full width) ───────────────────────────────────────────
        desc_query = st.text_area(
            "Describe a legal situation in plain language",
            placeholder=(
                "e.g. police searched a suspect's cell phone without a warrant\n"
                "e.g. government required a license to display a religious symbol\n"
                "e.g. employer fired a worker for union organizing activity"
            ),
            height=100,
            key="desc_query",
        )
        col_ds1, col_ds2 = st.columns([1, 5])
        with col_ds1:
            n_results = st.slider("Results", 3, 20, 8, key="desc_n")
        with col_ds2:
            desc_btn = st.button("🔍 Find Cases", type="primary", key="desc_btn")

        if desc_btn and desc_query and len(desc_query.strip()) >= 10:
            with st.spinner("Searching 8,000+ cases…"):
                desc_results = text_search(desc_query, top_k=n_results)
            st.session_state["desc_results"] = desc_results
            st.session_state.pop("desc_selected_href", None)

        if "desc_results" in st.session_state:
            desc_results = st.session_state["desc_results"]
            if not desc_results:
                st.warning("No matching cases found. Try rephrasing your description.")
            else:
                # ── Two-column layout: list left, detail right ────────────
                col_list, col_detail = st.columns([2, 3], gap="large")

                with col_list:
                    st.markdown(f"**{len(desc_results)} result(s)** — click a case to read it")
                    for rank, res in enumerate(desc_results, 1):
                        sel_href = st.session_state.get("desc_selected_href", "")
                        is_selected = sel_href == res.get("href", "")
                        border_color = "#1f77b4" if is_selected else None
                        with st.container(border=True):
                            if is_selected:
                                st.markdown(
                                    "<div style='position:absolute;width:4px;background:#1f77b4;"
                                    "top:0;left:0;bottom:0;border-radius:4px 0 0 4px'></div>",
                                    unsafe_allow_html=True,
                                )
                            btn_label = "✅ Selected" if is_selected else "View →"
                            btn_type = "primary" if is_selected else "secondary"
                            st.markdown(f"**{rank}. {res['name']}**")
                            st.caption(f"{res['term']} term · score {res['score']:.3f}")
                            if st.button(btn_label, key=f"desc_view_{rank}", type=btn_type):
                                st.session_state["desc_selected_href"] = res.get("href", "")
                                st.rerun()

                with col_detail:
                    def _str(v):
                        return v if isinstance(v, str) else ""

                    sel_href = st.session_state.get("desc_selected_href", "")
                    if not sel_href:
                        st.markdown(
                            "<div style='height:200px;display:flex;align-items:center;"
                            "justify-content:center;border:2px dashed #ccc;border-radius:8px;"
                            "color:#888;font-size:1.1em;'>← Select a case to read it</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        with st.spinner("Loading…"):
                            detail = get_case_detail(sel_href)
                        if not detail:
                            st.warning("Could not load case details.")
                        else:
                            st.subheader(detail.get("name", ""))

                            # Metadata pills row
                            _dec_d = (detail.get("decisions") or [{}])[0]
                            _disp_d = (_dec_d.get("decision_type") or "").strip().title()
                            _wp = (_dec_d.get("winning_party") or "").strip()
                            decided_by = detail.get("decided_by") or {}
                            meta_parts = [f"📅 **{detail.get('term', 'N/A')} term**"]
                            if detail.get("docket_number"):
                                meta_parts.append(f"No. {detail['docket_number']}")
                            if _disp_d:
                                meta_parts.append(f"_{_disp_d}_")
                            if _wp:
                                meta_parts.append(f"Winner: **{_wp}**")
                            st.markdown(" &nbsp;·&nbsp; ".join(meta_parts))
                            if decided_by.get("name"):
                                st.caption(f"Decided by: {decided_by['name']}")
                            # Links
                            _api_href = detail.get("href", "")
                            _oyez_url = _api_href.replace("https://api.oyez.org/", "https://www.oyez.org/") if _api_href else ""
                            _links = []
                            if _oyez_url:
                                _links.append(f"[Oyez case page ↗]({_oyez_url})")
                            if detail.get("justia_url"):
                                _links.append(f"[Justia opinion ↗]({detail['justia_url']})")
                            if _links:
                                st.markdown(" &nbsp;·&nbsp; ".join(_links))
                            watchlist_button(detail.get("name", ""), oyez_url=_oyez_url, key_suffix="tab_describe")
                            st.divider()

                            desc_txt = _str(detail.get("description")) or _str(detail.get("facts_of_the_case"))
                            if desc_txt:
                                with st.expander("📋 Background & Facts", expanded=True):
                                    st.write(safe_md(desc_txt))
                            q_txt = _str(detail.get("question"))
                            if q_txt:
                                with st.expander("❓ Legal Question", expanded=True):
                                    st.write(safe_md(q_txt))
                            conc_txt = _str(detail.get("conclusion"))
                            if conc_txt:
                                with st.expander("⚖️ Conclusion"):
                                    st.write(safe_md(conc_txt))

                            # Voting chart
                            _decs = detail.get("decisions") or []
                            _decs_wv = [d for d in _decs if d.get("votes")]
                            if _decs_wv:
                                justices_d = [
                                    {"name": (v.get("member") or {}).get("name", "Unknown"), "vote": v.get("vote", "")}
                                    for v in (_decs_wv[0].get("votes") or [])
                                ]
                                fig_v = build_voting_chart(justices_d)
                                if fig_v:
                                    st.plotly_chart(fig_v)

                            # Related cases panel
                            _cur_issue = infer_issue_area({
                                "question": _str(detail.get("question")),
                                "description": _str(detail.get("description")),
                            })
                            _issue_idx = _build_issue_area_index()
                            _related = [
                                c for c in _issue_idx.get(_cur_issue, [])
                                if c.get("href") != sel_href
                            ]
                            if _related:
                                import random as _random
                                _sample = _random.sample(_related, min(5, len(_related)))
                                with st.expander(f"🔗 Related cases — {_cur_issue}"):
                                    for _rc in _sample:
                                        _rc_oyez = (_rc.get("href") or "").replace(
                                            "https://api.oyez.org/", "https://www.oyez.org/"
                                        )
                                        _rc_label = f"{_rc['name']} ({_rc.get('term', '')})"
                                        if _rc_oyez:
                                            st.markdown(f"- [{_rc_label}]({_rc_oyez})")

        elif desc_query and len(desc_query.strip()) < 10:
            st.info("Enter at least 10 characters for a meaningful search.")

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: TIMELINE BROWSER
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
            csv_download_button(df, filename=f"scotus_timeline_{start_term}_{end_term}.csv", key="csv_timeline")
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
                    oa_holding = strip_html(oa_detail.get("conclusion") or "")
                    if oa_holding:
                        with st.expander("⚖️ Holding"):
                            st.write(safe_md(oa_holding))
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


