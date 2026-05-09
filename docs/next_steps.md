# Supreme Scrutiny — Recommended Next Steps

This document synthesizes the current state of the app (as of May 2026), the two feature
roadmap files, and the live codebase to identify the highest-leverage improvements across
design, features, data, and modeling. Items are grouped by theme and ordered within each
group by impact-to-effort ratio.

---

## Table of Contents

1. [Design & UX Polish](#1-design--ux-polish)
2. [Data Pipeline Improvements](#2-data-pipeline-improvements)
3. [Feature Completions (Partially-Built)](#3-feature-completions-partially-built)
4. [New Features](#4-new-features)
5. [ML & Modeling Enhancements](#5-ml--modeling-enhancements)
6. [Performance & Reliability](#6-performance--reliability)
7. [Priority Matrix](#7-priority-matrix)

---

## 1. Design & UX Polish

### ~~1a. Consistent Navigation & Page Naming~~ ✅ Completed

**Problem:** Pages are numbered (`1_Cases.py`, `10_Research.py`, `11_Advocates.py`) which
creates gaps in the number sequence and alphabetical sorting quirks that confuse users.
Several pages overlap in content (e.g., `Analysis.py` vs. `4_Analytics.py`).

**Recommendation:**
- Audit the full navigation and eliminate or merge duplicate pages
  (`Analysis.py`, `History.py`, `Insights.py`, `People.py`, `Topics.py` appear to be
  legacy/non-numbered alternatives to the numbered pages)
- Rename to a topic-first flat scheme: `cases.py`, `justices.py`, `advocates.py`,
  `analytics.py`, `history.py`, `topics.py`, `predictions.py`, `networks.py`
- Add a consistent `st.Page` navigation group structure in `cases.py`

### ~~1b. Home Page "Today in SCOTUS History" Widget~~ ✅ Completed

**Effort:** Low | **Impact:** High

The `supreme_scrutiny_feature_roadmap.md` has complete working code for this. Pre-build a
`data_files/date_index.json` with `scripts/build_date_index.py` and add the widget to the
top of `cases.py`. This is an instant engagement hook for casual visitors.

### ~~1c. Shareable URL Deep Links~~ ✅ Completed (implemented)

**Effort:** Low | **Impact:** High

Using `st.query_params` (Streamlit ≥1.30), write the selected term + case name to the URL
so users can share a specific case view via URL. Add a "Copy Link" button beneath each case
header. The `supreme_scrutiny_feature_roadmap.md` has the full implementation pattern.

### ~~1d. CSV Export Buttons~~ ✅ Completed

**Effort:** Very Low | **Impact:** Medium

Add a `utils/export.py` helper with a `csv_download_button(df, filename)` function and
drop it beneath every `st.dataframe()` call in Cases, Analysis, and Justices pages.
This is a single utility function + one line per table.

### ~~1e. Mobile-Responsive Layout Audit~~ ✅ Completed

**Problem:** Plotly charts with many columns (e.g., the 9-justice agreement heatmap, the
bench diagram) overflow on small screens. Streamlit's default behavior is to scale down,
which makes text unreadable.

**Recommendation:**
- Set `height` explicitly on tall charts
- Use `st.columns([1])` wrappers with `use_container_width=True` on all `st.plotly_chart`
  calls (already done in many places but inconsistently)
- Add a `st.set_page_config(layout="wide")` check so pages don't compete with the sidebar

### ~~1f. Justice Roster Update Mechanism~~ ✅ Completed

**Problem:** `CURRENT_JUSTICES_DISPLAY` in `9_Predictions.py` is a hardcoded list. When
a justice retires or a new one is confirmed, every page that references this list requires
a manual code edit.

**Recommendation:** Move the current court roster to `data_files/current_justices.json`
(or fetch live from the Oyez `/justices` endpoint filtered to active status) and load it
once in a shared utility function. This prevents stale data after a court change.

---

## 2. Data Pipeline Improvements

### 2a. Build the Missing Index Files

Several features depend on pre-built lookup files that do not yet exist in the repo.
These are one-time batch scripts that should be run and committed:

| Output file | Build script (to create) | Unlocks |
|---|---|---|
| `data_files/date_index.json` | `scripts/build_date_index.py` | Today-in-History widget |
| `data_files/case_text_index.json` | `scripts/build_case_text_index.py` | NLP search (§4a) |
| `data_files/advocate_win_rates.parquet` | extend `scripts/build_cases_parquet.py` | Advocates page enrichment |
| `data_files/circuit_reversal_rates.json` | derived from existing parquet | Cert predictor, prediction model |

### 2b. Supplement Oyez with CourtListener / Free Law Project

Oyez is excellent for case metadata and oral arguments, but has gaps:

- **Amicus brief counts** — CourtListener's `/dockets/` endpoint includes amicus counts
  per case free of charge. Even a partial dataset (2010–present) would enrich the
  prediction model significantly (amicus count is a strong proxy for case salience and
  contested outcomes)
- **Full opinion text** — CourtListener provides the full text of majority, concurring,
  and dissenting opinions. This enables citation extraction, reading-level analysis,
  and opinion length as a feature
- **Cert petition data** — SCOTUSblog publishes granted/denied cert data that Oyez does
  not expose, required for the cert predictor (§4c)

**Recommended integration approach:**
- Add `utils/courtlistener_api.py` with a thin wrapper around the CourtListener REST API
- Cache responses to `data_files/courtlistener/` in the same pattern as `data_files/oyez_data/`
- Build a case-level merge key on `docket_number` (format is the same across sources)

### 2c. Pre-Compute Parquet Snapshots for Heavy Pages

Pages that loop over 20+ terms of Oyez data at runtime (Advocates, Analysis, Presidential
Legacy) are slow on first load. The existing `scripts/build_cases_parquet.py` pattern
should be extended:

- `data_files/justice_votes_all.parquet` — all votes from 1990–present, one row per
  justice-case pair
- `data_files/advocate_appearances.parquet` — all advocate appearances with win/loss flag
- `data_files/term_stats.parquet` — pre-aggregated term-level stats for the Analytics page

Run these as part of a `scripts/refresh_all.py` wrapper (combine the existing
`scripts/refresh_parquet.py` with new scripts).

### ~~2d. Add a `data_files/changelog.json`~~ ✅ Completed

Track when each data file was last refreshed and how many records it contains. Render
a "Data last updated: X days ago" notice in the sidebar. This builds user trust and makes
staleness visible.

---

## 3. Feature Completions (Partially-Built)

These features have code or scaffolding in the repo but are incomplete or have known gaps.

### 3a. Oral Argument Analytics — Real Transcript Data

**Status:** The Oral Arguments page shows duration and a transcript preview, but the
Analytics section (`pages/11_Advocates.py`, Oral Argument Analytics tab) uses manually
curated research data rather than computed metrics from actual transcripts.

**Next step:** Write `utils/transcript_parser.py` that, given a case detail dict, extracts
all `oral_argument_audio[].transcript.sections[].turns` entries, attributes each turn to
its speaker, and counts questions per justice per advocate. Cache output in
`data_files/oyez_data/oral_arguments/`. This produces real question-count data to replace
the static table.

### 3b. Prediction Model — SHAP Explanations

**Status:** The prediction page renders factor bars using a static weight heuristic rather
than real SHAP values.

**Next step:** After training the GradientBoostingClassifier per the `feature_roadmap.md`
spec, add `shap>=0.45` to `requirements.txt`, compute `shap.TreeExplainer` values, and
replace the factor bar section in `9_Predictions.py` with a real SHAP waterfall chart.
This makes the model interpretable and defensible to skeptical users.

### 3c. Networks Page (`7_Networks.py`) — Citation Graph Data

**Status:** Unknown — the page exists but the README does not describe it in detail.

**Next step:** Audit `pages/7_Networks.py`. If it renders static or empty, populate it
using CourtListener's citation graph data (§2b above) to show which cases cite which,
filtered to the user's selected case or justice.

### 3d. Docket Watch — Live Auto-Refresh

**Status:** A "Docket Watch" section exists in the Predictions page but does not
auto-refresh.

**Next step:** Implement the `st.empty()` + `time.sleep(300)` + `st.cache_data(ttl=300)`
auto-refresh loop described in `feature_roadmap.md §15`. Add a "Last updated" timestamp
and a manual refresh button.

---

## 4. New Features

### ~~4a. Natural Language / Semantic Case Search~~ ✅ Completed

**Effort:** Medium | **Impact:** Very High

Allow users to type "cases about police searches of cell phones" and return the most
relevant cases. Two tiers:

1. **TF-IDF (no API key needed):** Build a `data_files/case_text_index.json` with the
   `facts_of_the_case` + `question` fields from all cached case details. Use
   `sklearn.TfidfVectorizer` for cosine similarity search. Fast, fully offline, 
   works on the free Streamlit Community Cloud tier.

2. **Embedding search (optional upgrade):** Use the free `sentence-transformers` library
   (`all-MiniLM-L6-v2`) to build dense embeddings, stored in a `.npy` file. Retrieval is
   much more accurate for paraphrase queries. Requires ~50 MB of model weight but no API key.

Add as a new tab in `pages/1_Cases.py` — "Search by Description".

### ~~4b. Justice Ideology Drift Timeline~~ ✅ Completed

**Effort:** Medium | **Impact:** High

For each justice, compute a `conservative_alignment_score` per term (fraction of votes
cast with the conservative bloc, defined as Thomas + Alito). Plot a rolling 3-term average
as a line chart. This produces the empirically verifiable "drift" chart for justices like
Blackmun, Stevens, Souter, and Kennedy — a compelling visualization not available on Oyez
or SCOTUSblog.

Add to `pages/2_Justices.py` as a new tab: "Ideology Drift".

### ~~4c. Certiorari Grant Predictor~~ ✅ Completed

**Effort:** Medium | **Impact:** High

A companion to the outcome predictor. Train a logistic regression on historical cert
petition data (from SCOTUSblog or CourtListener) with features:

- Circuit of origin
- Issue area
- Whether the Solicitor General filed a brief
- Presence of a circuit split (boolean, user-supplied)
- Whether the case was CVSG

The base rate is ~1–2% grant, so the model's value is in identifying the top quintile of
likely grants. Display as a probability gauge with a context note: "Historically, X% of
cases from this circuit on this issue area were granted cert."

Add as a new tab in `pages/9_Predictions.py` (scaffolding already exists in the README).

### 4d. Justice Replacement Simulator

**Effort:** Medium | **Impact:** High

"What if Merrick Garland had been confirmed?" For every 5–4 decision in the user's
selected term range, show how the outcome would have changed if a replacement justice
of a chosen lean (Liberal / Moderate / Conservative) had held the swing seat. Use the
existing agreement matrix as the prediction backbone.

Add to `pages/2_Justices.py` or as a standalone `pages/Justice_Simulator.py`.

### 4e. Opinion Text Analytics

**Effort:** Medium | **Impact:** Medium**

Using full opinion text from CourtListener (§2b):

- **Reading level** (Flesch-Kincaid) per opinion per justice — is Thomas harder to read
  than Kagan? Has complexity trended upward?
- **Opinion length over time** — word count per majority opinion by term and issue area
- **Most cited phrases** — n-gram frequency analysis of majority opinions by issue area
- **Dissent intensity score** — length of dissent relative to majority opinion length

These charts are unique to this application and have genuine editorial appeal.

### ~~4f. "Related Cases" Panel~~ ✅ Completed (implemented)

**Effort:** Low | **Impact:** Medium

The `supreme_scrutiny_feature_roadmap.md` has complete working code for this. After a
case loads, surface 4–5 cases from the same issue area and similar term range. Add at the
bottom of the case detail view in `cases.py` and `pages/1_Cases.py`.

### 4g. Watchlist + Notification System

**Effort:** Medium | **Impact:** Medium

Let users bookmark cases or justices they want to track. Store state in
`st.session_state` during the session and optionally in browser localStorage via
`streamlit-javascript`. Show a "Your Watchlist" sidebar section. For users who provide
an email, send a notification (via a free SendGrid or Resend.com account) when a watched
case gets a new decision.

---

## 5. ML & Modeling Enhancements

### 5a. Real Training Data Pipeline

**Current state:** The predictor uses a statistical fallback based on historical reversal
rates rather than a trained model in most paths. `data/scotus_training_data.csv` exists
but `data/models/model_meta.json` suggests the model may be partially trained.

**Next steps (in order):**

1. Run `scripts/build_cases_parquet.py` to confirm how many labeled cases exist in
   `scotus_training_data.csv`
2. Add missing features per the `feature_roadmap.md §2.1` spec:
   - `cert_granted_month`
   - `is_circuit_split` (requires CourtListener data or manual labeling)
   - `num_amicus_briefs` (CourtListener)
   - `lower_court_reversal_rate_historical` (compute from existing data)
3. Implement a proper temporal train/validate/test split (train 1990–2018, validate
   2019–2022, test 2023–present) — avoid data leakage
4. Add calibration with `CalibratedClassifierCV(method="isotonic")` so probabilities
   displayed to users are accurate
5. Log model metrics to `data/models/model_meta.json` on each training run

### 5b. Per-Justice Models

**Current state:** A single model predicts the aggregate outcome. Justice-level predictions
use a heuristic based on ideological lean.

**Next step:** Train nine separate binary classifiers (one per current justice) with
justice-specific features:
- `justice_dissent_rate_last_3_terms`
- `justice_agreement_rate_with_median_justice`
- `justice_issue_area_affinity` (per issue area, pre-computed)

This produces calibrated per-justice probabilities instead of lean-based heuristics, and
is the single biggest upgrade to the prediction page's credibility.

### 5c. Oral Argument Features for Prediction

**After completing §3a (real transcript data):**

Add question-count-by-side features to the prediction model:
- `q_count_to_petitioner` — number of justice questions directed at petitioner's counsel
- `q_count_to_respondent` — number of justice questions directed at respondent's counsel
- `q_ratio` = `q_count_to_petitioner / q_count_to_respondent`

Research (Jacobi & Schweers 2017) shows this ratio is predictive of outcome. Adding it
should measurably improve accuracy for cases where argument audio is available.

### ~~5d. Model Card & Transparency Page~~ ✅ Completed

Users (and media) who cite predictions need to understand model limitations.

**Next step:** Add a "Model Card" tab to `9_Predictions.py` that displays:
- Training data date range and sample size
- Feature list with plain-language descriptions
- Validation accuracy with confidence interval
- Known failure modes (e.g., low accuracy on First Amendment cases)
- A clear disclaimer that predictions are statistical, not legal advice

---

## 6. Performance & Reliability

### ~~6a. Background Data Loader~~ ✅ Completed

Heavy pages (Advocates, Presidential Legacy) fetch dozens of case details sequentially
at runtime, causing 30–90 second load times on first visit.

**Recommendation:** Add `utils/background_loader.py` using `concurrent.futures.ThreadPoolExecutor`
with a concurrency cap of 5 to parallelize Oyez API calls. Apply a 50ms delay between
batches to stay within the API's informal rate limit. This alone reduces perceived load
time by 5–10×.

### ~~6b. Graceful API Error Handling~~ ✅ Completed

Several pages crash with an unhandled exception if the Oyez API is unreachable or returns
a non-200 status. Add a shared `utils/api_guard.py` that wraps every Oyez fetch with:
- A retry with exponential backoff (max 3 attempts)
- A `st.warning("Data temporarily unavailable — showing cached version")` fallback if
  a local cache file exists
- A `st.error(...)` with a support link if no cache exists

### 6c. Test Coverage

No test files exist in the repo. Add `tests/` with at minimum:
- `tests/test_ml_predictor.py` — unit tests for feature extraction and model loading
- `tests/test_oyez_api.py` — mock-based tests for the API wrapper functions
- `tests/test_local_data.py` — tests for parquet read/write helpers

Use `pytest` + `pytest-mock`. Run in CI via a simple GitHub Actions workflow.

### ~~6d. Dependency Pinning~~ ✅ Completed

`requirements.txt` should pin major+minor versions (e.g., `streamlit==1.35.*`) to prevent
silent breakage when Streamlit or Plotly release breaking changes. Use `pip-tools` to
maintain a `requirements.in` (unpinned intent) and a `requirements.txt` (pinned lockfile).

---

## 7. Priority Matrix

| # | Item | Effort | Impact | Recommended Next |
|---|------|--------|--------|-----------------|
| ~~1a~~ | ~~Navigation audit & cleanup~~ | Low | High | ✅ Completed |
| ~~1b~~ | ~~Today-in-History widget~~ | Low | High | ✅ Completed |
| ~~1c~~ | ~~Shareable URL deep links~~ | Low | High | ✅ Completed |
| ~~1d~~ | ~~CSV export buttons~~ | Very Low | Medium | ✅ Completed |
| ~~2a~~ | ~~Build circuit reversal rates index~~ | Low | High | ✅ Completed |
| ~~3a~~ | ~~Real oral argument transcript parsing~~ | Medium | High | ✅ Completed |
| ~~3b~~ | ~~SHAP explanations in predictor~~ | Medium | High | ✅ Completed |
| ~~4a~~ | ~~Semantic / NL case search (TF-IDF)~~ | Medium | Very High | ✅ Completed |
| ~~4b~~ | ~~Justice ideology drift timeline~~ | Medium | High | ✅ Completed |
| ~~5a~~ | ~~Real ML training pipeline~~ | High | Very High | ✅ Completed |
| ~~5b~~ | ~~Per-justice models~~ | High | High | ✅ Completed |
| ~~2b~~ | ~~CourtListener integration wrapper~~ | Medium | High | ✅ Completed |
| ~~4c~~ | ~~Cert grant predictor~~ | Medium | High | ✅ Completed |
| ~~4d~~ | ~~Justice replacement simulator~~ | Medium | High | ✅ Completed |
| ~~6a~~ | ~~Background data loader~~ | Medium | High | ✅ Completed |
| ~~4e~~ | ~~Opinion text analytics (FK readability + length trends)~~ | High | Medium | ✅ Completed |
| ~~4f~~ | ~~Related cases panel~~ | Low | Medium | ✅ Completed |
| ~~4g~~ | ~~Watchlist + bookmarks (session state)~~ | High | Medium | ✅ Completed |
| ~~5c~~ | ~~Oral argument features for ML (question counts)~~ | High | Medium | ✅ Completed |
| ~~5d~~ | ~~Model card & transparency page~~ | Low | Medium | ✅ Completed |
| ~~6b~~ | ~~Graceful API error handling~~ | Low | Medium | ✅ Completed |
| ~~6c~~ | ~~Test coverage (61 tests)~~ | Medium | Medium | ✅ Completed |

---

*Last updated: May 2026*
