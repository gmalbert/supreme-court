# Supreme Scrutiny — GitHub Copilot Instructions

## Project Overview

**App name:** Supreme Scrutiny
**Purpose:** Interactive web application for exploring the full history of the United States Supreme Court — cases, justices, voting patterns, legal topics, and predicted outcomes.
**Entry point:** `streamlit run cases.py`
**Data source:** Oyez API (api.oyez.org) — free, no API key required

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit ≥ 1.36 (multi-page via `st.navigation`) |
| Data | pandas, Oyez API, CourtListener API |
| ML | scikit-learn (outcome prediction in `utils/ml_predictor.py`) |
| Search | Full-text search via `utils/text_search.py` |
| Viz | Plotly, NetworkX |
| Config | None needed — Oyez API is public |
| Python | 3.9+ |

---

## File Conventions

### Key files
- `cases.py` — entry point; sets `st.set_page_config` ONCE; wires `st.navigation`.
- `utils/oyez_api.py` — all Oyez API calls (`fetch_case()`, `search_cases()`, `fetch_justice()`).
- `utils/courtlistener_api.py` — CourtListener API (additional opinions/docket data).
- `utils/local_data.py` — cached local data loading helpers.
- `utils/ml_predictor.py` — ML outcome predictor for upcoming cases.
- `utils/charts.py` — shared Plotly chart builders.
- `utils/today_in_history.py` — "today in history" feature.
- `utils/transcript_parser.py` — oral argument transcript parsing.
- `utils/text_search.py` — full-text case search.
- `utils/export.py` — PDF/CSV export helpers.
- `utils/background_loader.py` — background data pre-loading.

### Pages
- `pages/1_Cases.py` — case explorer (search, filter, detail)
- `pages/2_Justices.py` — justice profiles, voting records
- `pages/3_Court_History.py` — historical court composition
- `pages/4_Analytics.py` — voting patterns, coalition analysis
- `pages/5_Circuit_Courts.py` — circuit court breakdowns
- `pages/6_Legal_Topics.py` — cases by legal topic/issue area
- `pages/7_Networks.py` — citation/coalition network graphs
- `pages/8_Presidential_Legacy.py` — presidential appointment impact
- `pages/9_Predictions.py` — ML-predicted outcomes
- `pages/10_Research.py` — deep research tools
- `pages/11_Advocates.py` — oral argument advocate stats
- `pages/12_Geography.py` — geographic origin of cases
- `pages/13_Historical_Data.py` — raw historical data explorer

### Data files
- `data_files/` — cached JSON/CSV data from Oyez/CourtListener
- `data/` — processed datasets

---

## Domain Knowledge

### Oyez API
- Base URL: `https://api.oyez.org`
- No authentication required
- Key endpoints: `/cases`, `/cases/{year}/{docket}`, `/justices`, `/courts`
- Rate-limit courtesy: add brief delays between bulk requests

### Case structure
- `docket_number` (e.g. `"23-456"`) is the primary identifier
- `term` is the Supreme Court term year (October Term YYYY)
- `decision_type`: "majority opinion", "per curiam", "dismissal", etc.
- `winning_party`: "petitioner" or "respondent"
- Vote splits: stored as `first_party_votes`/`second_party_votes`

### Justices
- Identified by name + `href` from Oyez
- `roles` list shows court tenure dates
- Voting alignment analysis uses Poole-Rosenthal scores

---

## Coding Conventions

### Streamlit patterns
```python
@st.cache_data(ttl=3600)
def load_cases() -> pd.DataFrame: ...
```
- `st.set_page_config()` called ONCE in `cases.py` only
- Sub-pages must NOT call `st.set_page_config`
- Use `width='stretch'` for dataframes/charts (not deprecated `use_container_width`)
- Use `utils/background_loader.py` for pre-loading large datasets

### API conventions
- Always cache API responses in `data_files/` to minimize external calls
- Wrap every API call in try/except; return empty dict/list on failure
- Log failures with `st.warning()` rather than crashing

### Error handling
- Check for empty responses before feature engineering
- Never display raw Python exceptions to users — show friendly `st.error()` messages
