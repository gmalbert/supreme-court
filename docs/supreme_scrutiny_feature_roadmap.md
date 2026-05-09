# Supreme Scrutiny — Feature Roadmap & Implementation Guide

This document contains prioritized feature suggestions for the Supreme Scrutiny Streamlit app,
with working or near-working code for each. Features are grouped by effort and impact.

---

## Table of Contents

1. [Quick Wins (Low Effort, High Impact)](#1-quick-wins)
   - 1a. "Today in SCOTUS History" Widget
   - 1b. Export to CSV
   - 1c. Shareable State via URL Query Params
2. [Medium Effort, High Value](#2-medium-effort-high-value)
   - 2a. Justice Side-by-Side Comparator
   - 2b. "Related Cases" Panel
   - 2c. Current Term Dashboard (Live Home Widget)
3. [Ambitious / Differentiating](#3-ambitious--differentiating)
   - 3a. Natural Language Case Search (AI-powered)
   - 3b. Oral Argument Sentiment Analyzer
   - 3c. Watchlist + Email Alerts

---

## A Note on Streamlit Deep Linking

Streamlit doesn't support true deep links to internal state (e.g., `/cases?name=Dobbs`),
but you can use `st.query_params` (Streamlit 1.30+) to read and write URL parameters.
This lets you build "copy link" buttons that pre-populate dropdowns when the URL is shared.

```python
# Write to URL (e.g., after a user selects a case)
st.query_params["term"] = selected_term
st.query_params["case"] = selected_case_name

# Read from URL (e.g., at page load, before showing dropdowns)
params = st.query_params
preselect_term = params.get("term", None)
preselect_case = params.get("case", None)
```

Use this pattern in every feature below that involves selectable state.

---

## 1. Quick Wins

### 1a. "Today in SCOTUS History" Widget

**Where to add it:** `cases.py` home page, below the main title, above the sidebar controls.

**What it does:** Finds cases decided or argued on today's calendar date (month + day) across
all terms, picks one at random, and shows a teaser card with a link to explore it.

**Implementation:**

Add a `data_files/decisions_by_date.json` lookup file (generated once from Oyez data), or
query the cache at runtime. The simplest approach uses the existing `get_cases_by_term` loop
over cached terms and filters by date. For performance, pre-build an index.

```python
# utils/today_in_history.py

import json
import os
import random
from datetime import date

CACHE_PATH = "data_files/date_index.json"   # build this once (see build script below)

def get_today_in_history() -> dict | None:
    """Return a random case decided or argued on today's month/day."""
    if not os.path.exists(CACHE_PATH):
        return None
    with open(CACHE_PATH) as f:
        index = json.load(f)
    today_key = date.today().strftime("%m-%d")   # e.g. "06-26"
    matches = index.get(today_key, [])
    return random.choice(matches) if matches else None
```

```python
# scripts/build_date_index.py  — run once, commit the output to data_files/

import json, requests
from datetime import datetime

TERMS = list(range(2000, 2025))
BASE = "https://api.oyez.org/cases?per_page=100&filter=term:{term}"

index = {}

for term in TERMS:
    url = BASE.format(term=term)
    resp = requests.get(url, timeout=15)
    if not resp.ok:
        continue
    for case in resp.json():
        for date_field in ["decided_on", "argued_on"]:
            raw = case.get(date_field)
            if not raw:
                continue
            dates = raw if isinstance(raw, list) else [raw]
            for d in dates:
                date_str = d.get("date") if isinstance(d, dict) else d
                if not date_str:
                    continue
                try:
                    dt = datetime.fromisoformat(date_str[:10])
                    key = dt.strftime("%m-%d")
                    index.setdefault(key, []).append({
                        "name": case.get("name"),
                        "term": term,
                        "href": case.get("href", ""),
                        "date_field": date_field,
                        "date": date_str[:10],
                    })
                except ValueError:
                    pass

with open("data_files/date_index.json", "w") as f:
    json.dump(index, f)

print(f"Built index with {len(index)} date keys.")
```

```python
# In cases.py home_page(), after st.title():

from utils.today_in_history import get_today_in_history
from datetime import date

today_case = get_today_in_history()
if today_case:
    event_type = "decided" if today_case["date_field"] == "decided_on" else "argued"
    with st.container(border=True):
        st.markdown(
            f"📅 **On this day ({date.today().strftime('%B %d')})** — "
            f"*{today_case['name']}* was **{event_type}** in {today_case['term']}"
        )
        if st.button("Explore this case →", key="today_btn"):
            st.query_params["term"] = str(today_case["term"])
            st.query_params["case"] = today_case["name"]
            st.rerun()
```

---

### 1b. Export to CSV

**Where to add it:** Any page that renders a `st.dataframe()` or case list —
Cases timeline, Analysis term stats, Justice voting history.

**What it does:** Adds a one-line download button beneath any DataFrame.

```python
# utils/export.py

import pandas as pd
import streamlit as st

def csv_download_button(df: pd.DataFrame, filename: str, label: str = "⬇️ Download as CSV"):
    """Drop-in download button for any DataFrame."""
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )
```

```python
# Usage — drop this directly below any st.dataframe() call:
from utils.export import csv_download_button

st.dataframe(df_cases)
csv_download_button(df_cases, filename=f"scotus_cases_{term}.csv")
```

For the justice voting history table, pass the voting records DataFrame:

```python
csv_download_button(df_votes, filename=f"{justice_name.replace(' ', '_')}_votes.csv")
```

---

### 1c. Shareable State via URL Query Params

**Where to add it:** `cases.py` home page and `pages/1_Cases.py` Search Cases tab.

**What it does:** Writes the selected term + case name to the URL after selection,
and reads them back on load to pre-populate dropdowns. Users can copy the browser URL
to share a specific case view.

```python
# In cases.py home_page() — replace the term/case selectbox block with this:

params = st.query_params

# --- Term selector ---
terms = get_recent_terms(25)
default_term_idx = 0
if params.get("term") and params["term"] in [str(t) for t in terms]:
    default_term_idx = [str(t) for t in terms].index(params["term"])

term = st.selectbox("Select Term", terms, index=default_term_idx)

# --- Load cases ---
cases = get_cases_by_term(term)
case_names = sorted([c.get("name", "Unknown") for c in cases])

default_case_idx = 0
if params.get("case") and params["case"] in case_names:
    default_case_idx = case_names.index(params["case"])

selected_name = st.selectbox(
    f"Select a Case ({len(cases)} cases in {term} term)",
    case_names,
    index=default_case_idx,
    key="main_case_select",
)

# Write selections back to URL whenever they change
st.query_params["term"] = str(term)
st.query_params["case"] = selected_name
```

```python
# Add a "Copy Link" hint beneath the case header in col_info:
import urllib.parse
base_url = "https://supreme-court.streamlit.app"
link = f"{base_url}/?term={urllib.parse.quote(str(term))}&case={urllib.parse.quote(selected_name)}"
st.caption(f"🔗 Share this case: `{link}`")
```

> **Note:** Streamlit Cloud resets `st.query_params` on each full rerun. The pattern above
> works for same-session sharing and for users who open a link fresh. It does not survive
> navigating between pages and back, which is a Streamlit limitation.

---

## 2. Medium Effort, High Value

### 2a. Justice Side-by-Side Comparator

**Where to add it:** New tab in `pages/People.py` — "Compare Justices".

**What it does:** User picks two justices and a term range. The page renders side-by-side
stat cards, a grouped bar chart of vote-type breakdowns, and a line chart of dissent rate
over time for both.

```python
# pages/people_compare.py  (or add as a tab inside People.py)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.oyez_api import get_justices, get_justice_votes  # your existing helpers

def render_compare_tab():
    st.subheader("⚖️ Compare Two Justices")

    justices_list = get_justices()   # returns list of {"name": ..., "id": ...}
    names = [j["name"] for j in justices_list]

    col1, col2 = st.columns(2)
    with col1:
        j1 = st.selectbox("Justice 1", names, index=0, key="cmp_j1")
    with col2:
        j2 = st.selectbox("Justice 2", names, index=1, key="cmp_j2")

    term_range = st.slider("Term Range", 2000, 2024, (2015, 2024), key="cmp_terms")

    if st.button("Compare", key="cmp_btn"):
        terms = list(range(term_range[0], term_range[1] + 1))

        with st.spinner("Loading voting records..."):
            data1 = get_justice_votes(j1, terms)   # returns list of vote dicts
            data2 = get_justice_votes(j2, terms)

        def summarize(votes):
            total = len(votes)
            if total == 0:
                return {}
            majority = sum(1 for v in votes if v.get("vote", "").lower() in ("majority", "concurrence"))
            dissent  = sum(1 for v in votes if v.get("vote", "").lower() == "dissent")
            return {
                "Total Votes": total,
                "Majority Rate": f"{majority/total*100:.1f}%",
                "Dissent Rate":  f"{dissent/total*100:.1f}%",
                "Dissents":      dissent,
            }

        s1, s2 = summarize(data1), summarize(data2)

        # Stat cards
        hdr1, hdr2 = st.columns(2)
        with hdr1:
            st.markdown(f"### {j1}")
            for k, v in s1.items():
                st.metric(k, v)
        with hdr2:
            st.markdown(f"### {j2}")
            for k, v in s2.items():
                st.metric(k, v)

        st.markdown("---")

        # Grouped bar: vote type breakdown
        def vote_counts(votes):
            counts = {"Majority": 0, "Concurrence": 0, "Dissent": 0, "Other": 0}
            for v in votes:
                vt = v.get("vote", "").lower()
                if vt == "majority":       counts["Majority"] += 1
                elif vt == "concurrence":  counts["Concurrence"] += 1
                elif vt == "dissent":      counts["Dissent"] += 1
                else:                      counts["Other"] += 1
            return counts

        vc1, vc2 = vote_counts(data1), vote_counts(data2)
        categories = list(vc1.keys())

        fig = go.Figure(data=[
            go.Bar(name=j1, x=categories, y=list(vc1.values()), marker_color="#1f77b4"),
            go.Bar(name=j2, x=categories, y=list(vc2.values()), marker_color="#d62728"),
        ])
        fig.update_layout(
            barmode="group",
            title="Vote Type Breakdown",
            xaxis_title="Vote Type",
            yaxis_title="Count",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Dissent rate over time
        def dissent_by_term(votes):
            by_term = {}
            for v in votes:
                t = v.get("term")
                if not t:
                    continue
                by_term.setdefault(t, {"total": 0, "dissent": 0})
                by_term[t]["total"] += 1
                if v.get("vote", "").lower() == "dissent":
                    by_term[t]["dissent"] += 1
            return {t: d["dissent"] / d["total"] * 100 for t, d in by_term.items() if d["total"] > 0}

        dr1, dr2 = dissent_by_term(data1), dissent_by_term(data2)
        all_terms = sorted(set(dr1) | set(dr2))

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=all_terms, y=[dr1.get(t, None) for t in all_terms],
            mode="lines+markers", name=j1, line=dict(color="#1f77b4")
        ))
        fig2.add_trace(go.Scatter(
            x=all_terms, y=[dr2.get(t, None) for t in all_terms],
            mode="lines+markers", name=j2, line=dict(color="#d62728")
        ))
        fig2.update_layout(
            title="Dissent Rate by Term (%)",
            xaxis_title="Term",
            yaxis_title="Dissent Rate (%)",
        )
        st.plotly_chart(fig2, use_container_width=True)
```

---

### 2b. Related Cases Panel

**Where to add it:** Bottom of the case detail view in `cases.py` and `pages/1_Cases.py`.

**What it does:** After a case loads, surface 4–5 cases from the same issue area and
similar term range, sorted by vote-split similarity. All data is already in your cache.

```python
# utils/related_cases.py

def get_related_cases(
    current_case: dict,
    all_cases_same_term: list[dict],
    cases_adjacent_terms: list[dict] | None = None,
    n: int = 5,
) -> list[dict]:
    """
    Find cases related to current_case by issue area and vote split.

    current_case:         the detail dict from get_case_detail()
    all_cases_same_term:  list from get_cases_by_term() for same term
    cases_adjacent_terms: optionally pass in ±1 term cases for richer results
    """
    target_issue = (current_case.get("issue_area") or {})
    target_issue_id = target_issue.get("id") if isinstance(target_issue, dict) else None

    target_votes = current_case.get("decisions", [{}])[0].get("votes", []) if current_case.get("decisions") else []
    majority_count = sum(1 for v in target_votes if (v.get("vote") or "").lower() in ("majority", "concurrence"))
    dissent_count  = len(target_votes) - majority_count

    pool = list(all_cases_same_term)
    if cases_adjacent_terms:
        pool += cases_adjacent_terms

    scored = []
    for c in pool:
        if c.get("name") == current_case.get("name"):
            continue
        score = 0
        c_issue = (c.get("issue_area") or {})
        c_issue_id = c_issue.get("id") if isinstance(c_issue, dict) else None
        if target_issue_id and c_issue_id == target_issue_id:
            score += 3   # strong signal: same legal domain
        # Rough vote-split match from summary data
        c_votes = c.get("votes", {})
        if isinstance(c_votes, dict):
            c_maj = c_votes.get("majority", 0)
            c_dis = c_votes.get("minority", 0)
            if abs(c_maj - majority_count) <= 1 and abs(c_dis - dissent_count) <= 1:
                score += 1
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:n]]
```

```python
# In cases.py home_page(), after the oral arguments section:

from utils.related_cases import get_related_cases

st.markdown("---")
st.subheader("📎 Related Cases")

with st.spinner("Finding related cases..."):
    related = get_related_cases(detail, cases)

if related:
    cols = st.columns(len(related))
    for col, rc in zip(cols, related):
        with col:
            with st.container(border=True):
                st.markdown(f"**{rc.get('name', 'Unknown')}**")
                issue = rc.get("issue_area") or {}
                if isinstance(issue, dict) and issue.get("name"):
                    st.caption(issue["name"])
                if st.button("View →", key=f"rel_{rc.get('name', '')}"):
                    st.query_params["term"] = str(term)
                    st.query_params["case"] = rc.get("name", "")
                    st.rerun()
else:
    st.caption("No closely related cases found in this term.")
```

---

### 2c. Current Term Dashboard

**Where to add it:** New page `pages/CurrentTerm.py`, added to the navigation in `cases.py`.

**What it does:** A single-page live view of the current term — argument schedule,
recently decided cases, pending decisions, and ML reversal probabilities if the model is trained.
Designed to be the go-to page for users following the Court in real time.

```python
# pages/CurrentTerm.py

import streamlit as st
from datetime import date
from utils.oyez_api import get_cases_by_term, get_case_detail

CURRENT_TERM = date.today().year if date.today().month >= 10 else date.today().year - 1

def render():
    st.title(f"🔴 Live — {CURRENT_TERM} Term")
    st.caption(f"Auto-refreshes on load. Data from Oyez API.")

    with st.spinner("Loading current term docket..."):
        cases = get_cases_by_term(CURRENT_TERM)

    if not cases:
        st.error("Could not load current term data.")
        return

    # Bucket cases by status
    decided, argued_pending, scheduled, granted = [], [], [], []
    for c in cases:
        decided_on  = c.get("decided_on")  or c.get("term_decided")
        argued_on   = c.get("argued_on")   or c.get("oral_argument_audio")
        granted_on  = c.get("granted_on")

        if decided_on:
            decided.append(c)
        elif argued_on:
            argued_pending.append(c)
        elif granted_on:
            granted.append(c)
        else:
            scheduled.append(c)

    # Headline metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cases", len(cases))
    m2.metric("✅ Decided",   len(decided))
    m3.metric("⏳ Argued / Awaiting Decision", len(argued_pending))
    m4.metric("📋 Granted / Scheduled", len(granted) + len(scheduled))

    st.markdown("---")

    tab_decided, tab_pending, tab_upcoming = st.tabs(
        ["Recently Decided", "Argued — Awaiting Decision", "Upcoming Arguments"]
    )

    with tab_decided:
        if decided:
            for c in sorted(decided, key=lambda x: x.get("decided_on") or "", reverse=True)[:20]:
                with st.expander(c.get("name", "Unknown")):
                    st.markdown(f"**Decided:** {c.get('decided_on', 'N/A')}")
                    issue = (c.get("issue_area") or {})
                    if isinstance(issue, dict):
                        st.markdown(f"**Issue Area:** {issue.get('name', 'N/A')}")
                    votes = c.get("votes", {})
                    if isinstance(votes, dict):
                        maj = votes.get("majority", "?")
                        dis = votes.get("minority", "?")
                        st.markdown(f"**Vote:** {maj}–{dis}")
                    docket = c.get("docket_number", "")
                    if docket:
                        oyez_url = f"https://www.oyez.org/cases/{CURRENT_TERM}/{docket}"
                        st.markdown(f"[View on Oyez ↗]({oyez_url})")
        else:
            st.info("No decided cases yet this term.")

    with tab_pending:
        if argued_pending:
            st.markdown(f"**{len(argued_pending)} cases** have been argued but not yet decided.")
            for c in argued_pending:
                st.markdown(f"- **{c.get('name')}** — argued {c.get('argued_on', 'date unknown')}")
        else:
            st.info("No cases in this status.")

    with tab_upcoming:
        if granted or scheduled:
            for c in (granted + scheduled):
                st.markdown(f"- **{c.get('name')}**")
        else:
            st.info("No upcoming cases found in current data.")

render()
```

Register the new page in `cases.py` navigation:

```python
# In cases.py, inside st.navigation(), add to the "" section or create a new group:
st.Page("pages/CurrentTerm.py", title="Current Term", icon="🔴"),
```

---

## 3. Ambitious / Differentiating

### 3a. Natural Language Case Search (AI-powered)

**Where to add it:** New tab in `pages/1_Cases.py` — "Search by Description".

**What it does:** User types a plain-English description ("cases about free speech on social media")
and the app uses the Oyez `description` / `facts_of_the_case` fields + simple TF-IDF or
embedding similarity to return the most relevant cases.

**Two implementation paths:**

**Path A — Lightweight (no API key, runs locally):**

```python
# utils/semantic_search.py

import json, os, re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

INDEX_PATH = "data_files/case_text_index.json"

def _load_index():
    if not os.path.exists(INDEX_PATH):
        return [], []
    with open(INDEX_PATH) as f:
        records = json.load(f)
    texts = [r.get("text", "") for r in records]
    return records, texts

def keyword_search(query: str, top_n: int = 8) -> list[dict]:
    records, texts = _load_index()
    if not records:
        return []
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    matrix = vectorizer.fit_transform(texts + [query])
    scores = cosine_similarity(matrix[-1], matrix[:-1])[0]
    top_idx = np.argsort(scores)[::-1][:top_n]
    return [
        {**records[i], "score": float(scores[i])}
        for i in top_idx if scores[i] > 0.05
    ]
```

```python
# scripts/build_text_index.py — run once, commit output

import json, requests

TERMS = list(range(2000, 2025))
records = []

for term in TERMS:
    resp = requests.get(f"https://api.oyez.org/cases?per_page=100&filter=term:{term}", timeout=15)
    if not resp.ok:
        continue
    for c in resp.json():
        text = " ".join(filter(None, [
            c.get("name", ""),
            c.get("description", ""),
            c.get("facts_of_the_case", ""),
            c.get("question", ""),
            (c.get("issue_area") or {}).get("name", "") if isinstance(c.get("issue_area"), dict) else "",
        ]))
        records.append({
            "name": c.get("name"),
            "term": term,
            "href": c.get("href", ""),
            "docket_number": c.get("docket_number", ""),
            "issue_area": (c.get("issue_area") or {}).get("name", "") if isinstance(c.get("issue_area"), dict) else "",
            "text": text,
        })

with open("data_files/case_text_index.json", "w") as f:
    json.dump(records, f)
print(f"Indexed {len(records)} cases.")
```

```python
# In pages/1_Cases.py, inside a new "Search by Description" tab:

from utils.semantic_search import keyword_search

st.subheader("🔍 Search by Description")
query = st.text_input(
    "Describe what you're looking for",
    placeholder="e.g. free speech social media, police search without warrant, affirmative action universities",
)
if query:
    with st.spinner("Searching..."):
        results = keyword_search(query, top_n=8)
    if results:
        st.markdown(f"**{len(results)} results** for: *{query}*")
        for r in results:
            with st.expander(f"{r['name']} ({r['term']}) — {r.get('issue_area', '')}"):
                st.caption(f"Relevance score: {r['score']:.2f}")
                docket = r.get("docket_number", "")
                if docket:
                    st.markdown(f"[View on Oyez ↗](https://www.oyez.org/cases/{r['term']}/{docket})")
                if st.button("Load in Case Explorer →", key=f"nlp_{r['name']}"):
                    st.query_params["term"] = str(r["term"])
                    st.query_params["case"] = r["name"]
                    st.switch_page("cases.py")
    else:
        st.info("No matches found. Try different keywords.")
```

**Path B — Richer (uses sentence-transformers embeddings, better quality):**

```python
# requirements.txt additions:
# sentence-transformers>=2.6.0

from sentence_transformers import SentenceTransformer
import numpy as np

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")  # ~80MB, fast
    return _model

def semantic_search(query: str, top_n: int = 8) -> list[dict]:
    records, texts = _load_index()
    if not records:
        return []
    model = _get_model()
    # Cache embeddings to disk for speed
    emb_path = "data_files/case_embeddings.npy"
    if os.path.exists(emb_path):
        corpus_emb = np.load(emb_path)
    else:
        corpus_emb = model.encode(texts, show_progress_bar=True)
        np.save(emb_path, corpus_emb)
    query_emb = model.encode([query])
    scores = cosine_similarity(query_emb, corpus_emb)[0]
    top_idx = np.argsort(scores)[::-1][:top_n]
    return [{**records[i], "score": float(scores[i])} for i in top_idx]
```

> **Recommendation:** Start with Path A (TF-IDF). It requires only `scikit-learn` which you
> likely already have. Upgrade to Path B later if search quality feels poor.

---

### 3b. Oral Argument Sentiment Analyzer

**Where to add it:** New sub-tab inside the existing Oral Arguments Browser tab in `pages/1_Cases.py`.

**What it does:** For a selected oral argument, parses the transcript already available via Oyez,
attributes each turn to either petitioner-side or respondent-side, and scores the tone of
each justice's questions using a lightweight sentiment model. Outputs a per-justice "hostility index"
toward each side — a documented predictor of voting outcomes.

```python
# utils/argument_sentiment.py

from textblob import TextBlob   # pip install textblob  (lightweight, no API key)
# Alternative: use transformers pipeline("sentiment-analysis") for better accuracy

def score_argument_transcript(transcript: list[dict]) -> dict:
    """
    transcript: list of {"speaker": "...", "text": "...", "side": "petitioner"|"respondent"|"justice"|"unknown"}
    Returns per-justice sentiment scores toward each side.
    """
    justice_scores: dict[str, dict] = {}

    current_side = None  # tracks whose advocate is currently speaking
    for turn in transcript:
        speaker = turn.get("speaker", "")
        text    = turn.get("text", "")
        role    = turn.get("role", "").lower()

        # Update which side is currently arguing
        if "petitioner" in role or "appellant" in role:
            current_side = "petitioner"
        elif "respondent" in role or "appellee" in role:
            current_side = "respondent"

        # Score justice questions directed at the current side
        if role == "justice" and current_side and text:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity   # -1 (hostile) to +1 (friendly)
            subjectivity = blob.sentiment.subjectivity

            justice_scores.setdefault(speaker, {"petitioner": [], "respondent": []})
            if current_side in justice_scores[speaker]:
                justice_scores[speaker][current_side].append(polarity)

    # Average scores
    result = {}
    for justice, sides in justice_scores.items():
        result[justice] = {
            side: sum(scores) / len(scores) if scores else 0.0
            for side, scores in sides.items()
        }
    return result
```

```python
# In the Oral Arguments Browser tab, after showing the transcript preview:

import plotly.graph_objects as go
from utils.argument_sentiment import score_argument_transcript

if st.checkbox("🧠 Show Argument Sentiment Analysis (experimental)", key="arg_sentiment"):
    # transcript is already loaded from Oyez — it's the list of speaker turns
    # Oyez transcript format: list of {"speaker": {"name": "...", "roles": [...]}, "text_blocks": [...]}
    flat_transcript = []
    for turn in raw_transcript:   # raw_transcript = detail["oral_argument_audio"][0]["transcript"]["sections"][0]["turns"]
        speaker_info = turn.get("speaker") or {}
        name = speaker_info.get("name", "Unknown")
        roles = speaker_info.get("roles") or []
        role_str = roles[0].get("role_title", "").lower() if roles else ""
        text = " ".join(
            block.get("text", "") for block in (turn.get("text_blocks") or [])
        )
        flat_transcript.append({"speaker": name, "text": text, "role": role_str})

    scores = score_argument_transcript(flat_transcript)

    if scores:
        justices_scored = list(scores.keys())
        pet_scores = [scores[j].get("petitioner", 0) for j in justices_scored]
        res_scores = [scores[j].get("respondent", 0) for j in justices_scored]

        fig = go.Figure(data=[
            go.Bar(name="Toward Petitioner", x=justices_scored, y=pet_scores,
                   marker_color=["green" if s > 0 else "red" for s in pet_scores]),
            go.Bar(name="Toward Respondent", x=justices_scored, y=res_scores,
                   marker_color=["green" if s > 0 else "red" for s in res_scores]),
        ])
        fig.update_layout(
            barmode="group",
            title="Justice Question Sentiment (positive = friendly, negative = hostile)",
            yaxis_title="Avg. Sentiment Polarity",
            yaxis=dict(range=[-1, 1]),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "⚠️ Experimental. Sentiment is estimated from question text using TextBlob. "
            "Research shows justices ask more questions of the side they ultimately rule against."
        )
```

---

### 3c. Watchlist + Email Alerts

**Where to add it:** New page `pages/Watchlist.py`. Requires a free [Resend](https://resend.com)
or SendGrid account for email delivery, and Streamlit's `st.secrets` for credentials.

**What it does:** Users enter their email and select cases they want to follow.
A GitHub Actions workflow (already in your `.github/workflows/` directory) runs daily,
checks for newly decided cases, and sends a digest email.

```python
# pages/Watchlist.py

import streamlit as st
import json, os
from datetime import date

WATCHLIST_PATH = "data_files/watchlist.json"   # simple flat file; swap for a DB later

def load_watchlist():
    if not os.path.exists(WATCHLIST_PATH):
        return {}
    with open(WATCHLIST_PATH) as f:
        return json.load(f)

def save_watchlist(wl):
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(wl, f, indent=2)

def render():
    st.title("🔔 Case Watchlist")
    st.markdown(
        "Enter your email to receive a notification when a case you're following is decided. "
        "Your email is stored only in this app and never shared."
    )

    email = st.text_input("Your email address", placeholder="you@example.com")
    if not email or "@" not in email:
        st.stop()

    from utils.oyez_api import get_cases_by_term
    CURRENT_TERM = date.today().year if date.today().month >= 10 else date.today().year - 1
    cases = get_cases_by_term(CURRENT_TERM)
    undecided = [c for c in cases if not c.get("decided_on")]
    case_names = sorted([c.get("name", "") for c in undecided])

    selected = st.multiselect("Cases to watch (current term, not yet decided)", case_names)

    if st.button("Save Watchlist"):
        wl = load_watchlist()
        wl[email] = {
            "cases": selected,
            "added": str(date.today()),
        }
        save_watchlist(wl)
        st.success(f"✅ Watching {len(selected)} case(s). We'll email {email} when decisions come in.")

render()
```

```python
# scripts/send_decision_alerts.py — run via GitHub Actions on a cron schedule

import json, os, requests

WATCHLIST_PATH = "data_files/watchlist.json"
RESEND_API_KEY = os.environ["RESEND_API_KEY"]   # set in GitHub Actions secrets
CURRENT_TERM   = 2024

def get_newly_decided(cases):
    """Return cases that are now decided."""
    return [c for c in cases if c.get("decided_on")]

def send_email(to: str, subject: str, body: str):
    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": "alerts@yourdomain.com", "to": to, "subject": subject, "text": body},
    )

resp = requests.get(f"https://api.oyez.org/cases?per_page=100&filter=term:{CURRENT_TERM}", timeout=15)
all_cases = {c["name"]: c for c in resp.json()}

with open(WATCHLIST_PATH) as f:
    watchlist = json.load(f)

for email, entry in watchlist.items():
    hits = []
    for name in entry.get("cases", []):
        c = all_cases.get(name)
        if c and c.get("decided_on"):
            hits.append(f"  • {name} — decided {c['decided_on']}")
    if hits:
        body = "The following cases on your Supreme Scrutiny watchlist have been decided:\n\n"
        body += "\n".join(hits)
        body += "\n\nVisit https://supreme-court.streamlit.app to explore the decisions."
        send_email(email, "🏛️ Supreme Scrutiny — New Decisions", body)
        print(f"Sent alert to {email} for {len(hits)} case(s).")
```

```yaml
# .github/workflows/decision_alerts.yml

name: Decision Alerts

on:
  schedule:
    - cron: "0 14 * * *"   # 10am ET daily
  workflow_dispatch:

jobs:
  alert:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install requests
      - run: python scripts/send_decision_alerts.py
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
```

> **Setup:** Create a free account at [resend.com](https://resend.com), verify a sending domain,
> and add `RESEND_API_KEY` to your GitHub repository secrets. The GitHub Actions workflow
> you already have in `.github/workflows/` makes this straightforward.

---

## Dependency Summary

| Feature | New Dependencies |
|---|---|
| Today in History | none (uses existing Oyez helpers) |
| CSV Export | none (`pandas` already present) |
| URL Sharing | none (`st.query_params` built into Streamlit 1.30+) |
| Justice Comparator | none (uses existing helpers + plotly) |
| Related Cases | none |
| Current Term Dashboard | none |
| NL Search (TF-IDF) | `scikit-learn` |
| NL Search (semantic) | `sentence-transformers` |
| Sentiment Analyzer | `textblob` |
| Email Alerts | `resend` (or `sendgrid`) |

---

## Suggested Implementation Order

1. **URL Query Params** — no code risk, immediate UX win, enables all "copy link" patterns.
2. **CSV Export** — one utility function, drop-in everywhere.
3. **Today in History** — needs one-time index build script, then trivial to display.
4. **Current Term Dashboard** — high visibility, mostly reorganizes data you already fetch.
5. **Related Cases** — contained utility, no new data sources.
6. **Justice Comparator** — good use of existing voting data, popular with users.
7. **NL Search (TF-IDF)** — one build script + one utility; upgrade to embeddings later.
8. **Sentiment Analyzer** — experimental, add behind a checkbox so it doesn't break the page.
9. **Watchlist / Alerts** — requires external email service setup, tackle last.
