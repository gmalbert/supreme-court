> **AI Onboarding Guide** — See also the project README for background context.

# Supreme Scrutiny (SCOTUS) — Site Summary

## What This App Does

Streamlit analytics app covering all 8,251+ U.S. Supreme Court cases from 71+ terms (sourced from Oyez, served locally from Parquet cache). Features case search (TF-IDF), justice voting patterns, presidential legacy analysis, ML-based outcome prediction, oral argument transcript browsing, and a "Today in History" widget. All data is pre-loaded — no live API calls needed.

## Quick Start

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1        # Windows
source .venv/bin/activate           # macOS/Linux

# 2. Run the app
streamlit run cases.py
```

Data is already in `data/cases_by_term.parquet` and `data/case_detail.parquet`. No scraping needed.

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (multi-page, `st.navigation`) |
| Data storage | Parquet (primary, offline-first) |
| ML | scikit-learn (outcome prediction) |
| Text search | TF-IDF (`utils/text_search.py`) |
| Graph analysis | NetworkX |
| Visualization | Plotly |
| Testing | pytest |

## Key Files

| File | Purpose |
|---|---|
| `cases.py` | Streamlit entry point |
| `utils/oyez_api.py` | Loads case data from local Parquet (Oyez API as fallback) |
| `utils/text_search.py` | TF-IDF search index over case titles and summaries |
| `pages/1_Cases.py` | Case search and detail view |
| `pages/2_Justice_Patterns.py` | Justice voting analysis, ideology scores, agreement matrices |
| `pages/3_Presidential_Legacy.py` | How president-appointed justices ruled by topic |
| `pages/4_Topics.py` | Case topic frequency and term-over-term trends |
| `pages/5_Oral_Arguments.py` | Justice question counts and sentiment proxies |
| `pages/9_Predictions.py` | ML-based outcome prediction for new case scenarios |
| `data/cases_by_term.parquet` | Primary dataset: 8,251+ cases, 71 terms |
| `data/case_detail.parquet` | Full case details, opinions, votes |
| `scripts/build_date_index.py` | Builds "today in history" index |
| `scripts/build_circuit_reversal_rates.py` | Computes per-circuit reversal rates |

## Data Flow

All data is already in local Parquet files. The app operates offline:
1. `utils/oyez_api.py` loads from `data/cases_by_term.parquet` (O(1) Parquet reads)
2. `utils/text_search.py` builds TF-IDF index at startup (cached)
3. Pages query the loaded DataFrames → Plotly charts, filterable tables

## Environment Variables

No API keys or environment variables required. All data is served from local Parquet cache.

## Critical Conventions

- All data access goes through `utils/oyez_api.py` — never read Parquet files directly in page code
- `st.set_page_config()` is called only in `cases.py` — never in page files
- The TF-IDF search index in `utils/text_search.py` is cached with `@st.cache_resource` — do not rebuild it on each page load

## Common Gotchas

- If `data/cases_by_term.parquet` is missing, the app will fail with a file-not-found error — check the `data/` directory first
- ML outcome prediction on `pages/9_Predictions.py` uses a simple scikit-learn classifier — it is illustrative, not production-grade
- NetworkX citation graph: rendering is slow for very large subgraphs; filter by term or topic before computing the network
- `scripts/build_circuit_reversal_rates.py` must be re-run if the Parquet data is refreshed
