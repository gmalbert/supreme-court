# Supreme Scrutiny — Architecture

## Overview
Interactive Streamlit app for exploring the full history of the US Supreme Court — cases, justices, voting patterns, legal topics, and predicted outcomes. Data sourced from the Oyez API (no auth required) and cached locally.

## Data Flow
```
Oyez API (api.oyez.org) + CourtListener API
        ↓
utils/oyez_api.py (fetch_case, search_cases, fetch_justice)
utils/courtlistener_api.py (additional opinions/docket data)
        ↓
data_files/ (cached JSON/CSV from Oyez + CourtListener)
data/ (processed datasets)
        ↓
utils/local_data.py → data loading helpers
utils/background_loader.py → pre-loads large datasets at startup
        ↓
cases.py (Streamlit entry) → st.navigation → 13 pages
```

## ML / Prediction
- `utils/ml_predictor.py` — scikit-learn outcome predictor for upcoming cases
  - Features: case topic, circuit origin, petition type, justice composition, presidential appointer
- `utils/text_search.py` — full-text case search index
- `utils/charts.py` — shared Plotly chart builders
- NetworkX citation/coalition network graphs (pages/7_Networks.py)

## Oyez API Details
- Base URL: `https://api.oyez.org`
- No authentication
- Key endpoints: `/cases`, `/cases/{year}/{docket}`, `/justices`, `/courts`
- Courtesy rate-limiting: brief delays between bulk requests

## Key Utilities
| Module | Purpose |
|--------|---------|
| `utils/oyez_api.py` | All Oyez API calls |
| `utils/courtlistener_api.py` | CourtListener docket/opinion data |
| `utils/local_data.py` | Cached local data loading helpers |
| `utils/ml_predictor.py` | ML outcome predictor |
| `utils/charts.py` | Shared Plotly chart builders |
| `utils/today_in_history.py` | "Today in history" feature |
| `utils/transcript_parser.py` | Oral argument transcript parsing |
| `utils/text_search.py` | Full-text case search |
| `utils/export.py` | PDF/CSV export helpers |
| `utils/background_loader.py` | Pre-loading large datasets |

## Pages (13)
| Page | Purpose |
|------|---------|
| `1_Cases.py` | Case explorer (search, filter, detail) |
| `2_Justices.py` | Justice profiles, voting records |
| `3_Court_History.py` | Historical court composition |
| `4_Analytics.py` | Voting patterns, coalition analysis |
| `5_Circuit_Courts.py` | Circuit court breakdowns |
| `6_Legal_Topics.py` | Cases by legal topic/issue area |
| `7_Networks.py` | Citation/coalition network graphs |
| `8_Presidential_Legacy.py` | Presidential appointment impact |
| `9_Predictions.py` | ML-predicted outcomes |
| `10_Research.py` | Deep research tools |
| `11_Advocates.py` | Oral argument advocate stats |
| `12_Geography.py` | Geographic origin of cases |
| `13_Historical_Data.py` | Raw historical data explorer |

## Storage
- `data_files/` — cached JSON/CSV from Oyez/CourtListener
- `data/` — processed datasets
- Local file-based caching to minimise API calls
