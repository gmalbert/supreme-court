import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import requests

st.set_page_config(page_title="Oral Arguments Browser", page_icon="🎙️", layout="wide")

HEADERS = {"Accept": "application/json", "User-Agent": "SCOTUS-Visualizer/1.0"}
OYEZ_BASE = "https://api.oyez.org"

@st.cache_data(show_spinner=False)
def fetch_term_cases(term: int) -> list[dict]:
    try:
        r = requests.get(
            f"{OYEZ_BASE}/cases?filter=term:{term}&per_page=100&page=0",
            headers=HEADERS, timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def fetch_detail(href: str) -> dict | None:
    try:
        r = requests.get(href, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

st.title("🎙️ Oral Arguments Browser")
st.markdown(
    "Browse oral argument recordings from the Oyez archive — "
    "the most comprehensive free source of Supreme Court audio."
)

term = st.selectbox("Select Term", list(range(2023, 1994, -1)))

with st.spinner("Loading cases..."):
    cases = fetch_term_cases(term)

if not cases:
    st.warning("No cases found for this term.")
    st.stop()

# Filter to cases that advertise oral argument audio at the summary level
search = st.text_input("Search by case name", placeholder="e.g. Biden, Chevron, EPA")
if search:
    cases = [c for c in cases if search.lower() in c.get("name", "").lower()]

st.markdown(f"**{len(cases)} case(s) found.** Select one to load oral argument details.")

case_names = [c.get("name", "Unknown") for c in cases]
selected_name = st.selectbox("Select Case", case_names)
selected = next((c for c in cases if c.get("name") == selected_name), None)
if not selected:
    st.stop()

href = selected.get("href", "")
with st.spinner("Loading case details..."):
    detail = fetch_detail(href) if href else None

if not detail:
    st.error("Could not load case details.")
    st.stop()

# ── Case header ───────────────────────────────────────────────────────────────
col_main, col_side = st.columns([2, 1])
with col_main:
    st.subheader(detail.get("name", selected_name))
    question = detail.get("question", "")
    if question:
        with st.expander("Legal Question"):
            st.write(question)

with col_side:
    decided_by = detail.get("decided_by") or {}
    disposition = detail.get("disposition") or {}
    docket = detail.get("docket_number", "N/A")
    st.markdown(f"- **Docket:** {docket}")
    if decided_by:
        st.markdown(f"- **Court:** {decided_by.get('name', 'N/A')}")
    if isinstance(disposition, dict) and disposition.get("label"):
        st.markdown(f"- **Disposition:** {disposition['label']}")

st.divider()

# ── Oral arguments ────────────────────────────────────────────────────────────
oral_args = detail.get("oral_argument_audio") or []

if not oral_args:
    st.info(
        "No oral argument audio is listed for this case in the Oyez database. "
        "This is common for older cases or cases decided without argument."
    )
else:
    st.subheader(f"🎧 {len(oral_args)} Oral Argument Session(s)")
    for i, arg in enumerate(oral_args):
        if not isinstance(arg, dict):
            continue
        title = arg.get("title", f"Session {i+1}")
        arg_href = arg.get("href", "")

        with st.expander(f"**{title}**", expanded=(i == 0)):
            if arg_href:
                st.markdown(
                    f"[🔗 Open on Oyez]({arg_href})",
                )
                # Try loading the argument detail for transcript
                with st.spinner("Loading argument detail..."):
                    arg_detail = fetch_detail(arg_href)

                if arg_detail:
                    duration = arg_detail.get("duration")
                    if duration:
                        mins, secs = divmod(int(duration), 60)
                        st.markdown(f"**Duration:** {mins}m {secs}s")

                    media = arg_detail.get("media_file") or []
                    if isinstance(media, list) and media:
                        for m in media[:3]:
                            if isinstance(m, dict):
                                mime = m.get("mime", "")
                                src = m.get("href", "")
                                if src and "mp3" in (mime + src).lower():
                                    st.audio(src, format="audio/mp3")
                                    break
                    elif isinstance(media, dict):
                        src = media.get("href", "")
                        if src:
                            st.audio(src)

                    # Transcript excerpts
                    transcript = arg_detail.get("transcript") or {}
                    sections = transcript.get("sections") or []
                    if sections:
                        st.markdown("**Transcript Excerpt**")
                        for section in sections[:1]:
                            turns = section.get("turns") or []
                            for turn in turns[:6]:
                                speaker = (turn.get("speaker") or {})
                                speaker_name = speaker.get("name", "Unknown") if isinstance(speaker, dict) else str(speaker)
                                blocks = turn.get("text_blocks") or []
                                text = " ".join(
                                    b.get("text", "") for b in blocks
                                    if isinstance(b, dict)
                                ).strip()
                                if text:
                                    st.markdown(f"**{speaker_name}:** {text[:400]}{'…' if len(text) > 400 else ''}")
            else:
                st.info("No direct audio link available.")

st.divider()

# ── Related cases with audio in this term ─────────────────────────────────────
st.subheader("Other Cases This Term")
st.caption("Showing all cases — those with oral argument recordings are noted below after loading their details.")
preview_rows = [{"Case": c.get("name", ""), "Docket": c.get("docket_number", "")} for c in cases[:30]]
import pandas as pd
st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, height=280)
