# SCOTUS Visualizer — Feature Roadmap & Development Guide

This document tracks every proposed feature for the SCOTUS Visualizer app, with implementation details, data sources, and technical notes for each one.

---

## Table of Contents

1. [Presidential Legacy Tracker](#1-presidential-legacy-tracker)
2. [Case Outcome Prediction Model](#2-case-outcome-prediction-model)
3. [Justice Ideology Drift](#3-justice-ideology-drift)
4. [Constitutional Doctrine Evolution](#4-constitutional-doctrine-evolution)
5. [SCOTUS Certiorari Predictor](#5-scotus-certiorari-predictor)
6. [Oral Argument Analytics](#6-oral-argument-analytics)
7. [Advocate / Attorney Win Rates](#7-advocate--attorney-win-rates)
8. [Amicus Brief Tracker](#8-amicus-brief-tracker)
9. [State Law Impact Dashboard](#9-state-law-impact-dashboard)
10. [Congressional Response Tracker](#10-congressional-response-tracker)
11. [Justice Replacement Simulator](#11-justice-replacement-simulator)
12. [Term-to-Term Comparator](#12-term-to-term-comparator)
13. [Oral Argument Sentiment Analysis](#13-oral-argument-sentiment-analysis)
14. [Cross-Court Citation Network](#14-cross-court-citation-network)
15. [Docket Watch — Live Term Tracker](#15-docket-watch--live-term-tracker)

---

## 1. Presidential Legacy Tracker

**Status:** In development  
**Priority:** High

### Description
Show which president's Supreme Court appointees have had the most measurable impact on American law — measured by majority opinion authorship, dissent rates, landmark rulings, and ideological influence.

### Key Visualizations
- **Gantt chart** of each president's appointees and their service overlap
- **Influence score** per president = (majority opinions authored by appointees) / (total cases in their era)
- **Ideological shift** map: did the court move left or right under each president's appointments?
- **Win rate by presidential legacy**: how often do appointees vote as a bloc?
- **Breakdown by issue area**: Civil Rights, First Amendment, Commerce Clause, etc.

### Data Sources
- Oyez `/justices` endpoint for appointment data
- Oyez case decision/vote data per term
- Static curated data for pre-1953 era justices

### Implementation Notes
- Use `streamlit-app/pages/8_Presidential_Legacy.py`
- Cache vote data by president using `@st.cache_data(ttl=3600)`
- Map each justice to their appointing president, then aggregate votes per president's cohort
- For "impact score": weight by whether the justice wrote the majority opinion (`writing_for_majority` field in Oyez decisions)

---

## 2. Case Outcome Prediction Model

**Status:** Proposed — High complexity  
**Priority:** High

### Description
A machine learning system that predicts, for any upcoming Supreme Court case:
1. **Binary outcome**: Affirmed vs. Reversed/Vacated
2. **Vote split**: predicted margin (e.g., 6-3, 5-4)
3. **Per-justice vote**: probability that each current justice votes majority vs. dissent

This is the most technically ambitious feature in the roadmap.

---

### 2.1 Data Pipeline

#### Training Data Source
- **Oyez API**: `/cases?filter=term:{year}` for terms 1990–present
- For each case extract:
  - `lower_court.name` → circuit of origin
  - `issue_area.label` → legal domain
  - `petitioner` / `respondent` names → party type classification
  - `oral_argument_audio` presence → whether oral argument occurred
  - `decisions[].votes[].member.name` + `.vote` → ground truth labels
  - `decisions[].winning_party` → outcome label
  - `decided_on` timestamp → term year
  - `docket_number` → for deduplication

#### Feature Engineering

| Feature | Type | Notes |
|---|---|---|
| `circuit` | Categorical (13 classes) | One-hot or target encode |
| `issue_area` | Categorical (14 classes) | One-hot encode |
| `petitioner_type` | Categorical (4 classes) | Federal Gov / State / Corp / Individual |
| `respondent_type` | Categorical (4 classes) | Same |
| `cert_granted_month` | Ordinal (1–12) | Cases granted cert later in term may be more contested |
| `is_unanimous_lower_court` | Boolean | Was the lower court decision en banc/unanimous? |
| `current_court_conservative_count` | Integer (0–9) | At time of decision |
| `current_court_liberal_count` | Integer (0–9) | At time of decision |
| `days_between_cert_and_argument` | Integer | Proxy for case complexity |
| `term_year` | Integer | Controls for era drift |
| `num_amicus_briefs` | Integer (if available) | Proxy for case salience |
| `lower_court_reversal_rate_historical` | Float | Pre-computed reversal rate for that circuit |

#### Label Definition
- **Outcome label** (binary): `1 = Reversed/Vacated`, `0 = Affirmed`
- **Split label** (multi-class): `{9-0, 8-1, 7-2, 6-3, 5-4, 5-3, 6-2}`
- **Per-justice label** (binary per justice): `1 = majority/concurrence`, `0 = dissent`

---

### 2.2 Model Architecture

#### Option A — Logistic Regression Baseline (recommended first pass)
```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

# For outcome prediction
model = Pipeline([
    ("enc", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ("clf", LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced"))
])
```

**Why start here**: interpretable coefficients, works well on small datasets (~3,000–5,000 cases), fast to iterate.

#### Option B — Random Forest / Gradient Boosting (recommended main model)
```python
from sklearn.ensemble import GradientBoostingClassifier

model = GradientBoostingClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    random_state=42
)
```

**Why**: handles non-linear interactions between circuit + issue area + court composition. Gives feature importances.

#### Option C — Per-Justice Model (one model per justice)
For each of the 9 sitting justices, train a separate binary classifier:
- Input: case features (same as above) + justice-specific features:
  - `justice_dissent_rate_last_3_terms` (float)
  - `justice_agreement_rate_with_median_justice` (float)
  - `justice_issue_area_affinity` (float per issue area)
  - `is_authored_opinion_likely` (boolean, for senior justices in majority)
- Output: P(justice votes majority)
- This gives a per-justice probability vector summing (roughly) to 5–6

---

### 2.3 Training & Validation

#### Train/Test Split
- **Temporal split**: train on 1990–2018, validate on 2019–2022, test on 2023–present
- Never use future data to predict past — avoid leakage
- Use `GroupShuffleSplit` with group = `docket_number` to avoid case-level leakage

#### Metrics
| Metric | Target |
|---|---|
| Outcome accuracy (affirm/reverse) | > 68% (baseline: ~62% reverse rate historically) |
| Vote split top-1 accuracy | > 35% (7 classes) |
| Vote split top-2 accuracy | > 60% |
| Per-justice AUC | > 0.70 per justice |
| Per-justice calibration (Brier score) | < 0.20 |

#### Calibration
- Use `CalibratedClassifierCV(method="isotonic")` to ensure output probabilities are well-calibrated
- Display confidence intervals in the UI (e.g., 95% CI via bootstrap)

---

### 2.4 Streamlit UI Design

**Page**: `streamlit-app/pages/8_Case_Predictor.py`

**Tabs**:
1. **Predict a Case** — user inputs case characteristics via dropdowns/sliders → model outputs prediction
2. **Current Term Predictions** — batch predictions for all pending cases this term
3. **Model Performance** — accuracy, confusion matrix, feature importances
4. **Justice Probabilities** — radar chart of per-justice P(majority) for the predicted case

**Predict a Case tab UI**:
```
Circuit of Origin:     [9th Circuit ▼]
Issue Area:            [First Amendment ▼]
Petitioner Type:       [Individual / Other ▼]
Respondent Type:       [State / Local Gov't ▼]
Currently Conservative Justices: [6 ▼]

[Predict Outcome →]

┌─────────────────────────────────┐
│  PREDICTED OUTCOME              │
│                                 │
│  REVERSED    72%                │
│  ████████████████░░░░░░ 28%     │
│                                 │
│  Most Likely Split: 6-3         │
│                                 │
│  Justice Breakdown:             │
│  Roberts   ██░░ 68% Majority    │
│  Thomas    ███░ 84% Majority    │
│  Alito     ███░ 81% Majority    │
│  ...                            │
└─────────────────────────────────┘
```

**Visualizations**:
- Horizontal probability bar for outcome (affirm/reverse)
- Stacked bar for split distribution (5-4, 6-3, 7-2…)
- Court bench diagram showing each justice's P(majority) as a heat gradient
- SHAP waterfall chart showing which features drove the prediction

---

### 2.5 Implementation Roadmap

```
Phase 1 — Data Collection (1–2 days)
  └─ Script: scripts/src/collect_training_data.py
  └─ Output: data/scotus_votes_1990_2024.csv

Phase 2 — Feature Engineering (1 day)
  └─ Script: scripts/src/feature_engineering.py
  └─ Output: data/features_matrix.csv

Phase 3 — Model Training (1 day)
  └─ Script: scripts/src/train_models.py
  └─ Output: data/models/outcome_model.pkl
             data/models/split_model.pkl
             data/models/justice_models/{name}.pkl

Phase 4 — Streamlit Integration (1–2 days)
  └─ Page: streamlit-app/pages/8_Case_Predictor.py
  └─ Utils: streamlit-app/utils/predictor.py

Phase 5 — Calibration & Evaluation (1 day)
  └─ Notebook: notebooks/model_evaluation.ipynb
```

---

### 2.6 Dependencies to Add
```toml
# In requirements.txt or pyproject.toml
scikit-learn>=1.4
shap>=0.45
joblib>=1.3
pandas>=2.0
numpy>=1.26
```

---

## 3. Justice Ideology Drift

**Status:** Proposed  
**Priority:** Medium

### Description
Track how each justice's voting record has shifted over time across issue areas. Some justices (e.g., Blackmun, Stevens, Souter) began as moderate conservatives and drifted decisively liberal. Visualize this empirically from vote data.

### Key Visualizations
- **Ideology timeline**: rolling 3-term window dissent-from-conservative-bloc rate
- **Issue area heatmap**: per-justice, per-issue affinity score by decade
- **Comparison slider**: pick two justices, see how their voting alignment changed over time

### Implementation Notes
- Compute `conservative_alignment_score` per term = fraction of votes aligned with Thomas/Scalia/Alito
- Smooth with a 3-term rolling average to reduce noise
- Add a "legacy score": change in score from first term to last

---

## 4. Constitutional Doctrine Evolution

**Status:** Proposed  
**Priority:** Medium

### Description
Show how specific legal doctrines (e.g., "clear and present danger" → "imminent lawless action", or Chevron deference → major questions doctrine → Loper Bright) have evolved through a sequence of cases.

### Key Visualizations
- **Doctrine timeline** with annotated case nodes
- **Doctrinal shift score** (measured by how many prior precedents were distinguished or overruled)
- **Subject index** (Commerce Clause, 1st Amendment, Takings, etc.)

### Implementation Notes
- Data is primarily curated (static JSON per doctrine)
- Add user-submitted doctrine suggestions (stored in session state or a JSON file)
- Use the existing citation network as the graph backbone

---

## 5. SCOTUS Certiorari Predictor

**Status:** Proposed  
**Priority:** Medium

### Description
Predict whether a petition for certiorari (cert) is likely to be granted. SCOTUS grants cert in ~1–2% of ~10,000 annual petitions. The predictor would estimate probability based on:
- Circuit of origin
- Issue area
- Presence of circuit split
- Whether the Solicitor General filed a brief
- Whether the case was CVSG (call for views from the SG)

### Implementation Notes
- This requires data beyond Oyez (SCOTUSblog tracks cert petitions and grants more comprehensively)
- Could scrape SCOTUSblog's database or use their API if available
- Model: logistic regression with circuit + issue + SG_support features

---

## 6. Oral Argument Analytics

**Status:** Proposed  
**Priority:** Medium

### Description
Analyze oral argument transcripts to extract:
- **Speaking time by justice** (who dominates oral arguments?)
- **Question count per justice per term**
- **Question sentiment**: hostile vs. favorable to petitioner/respondent (using NLP)
- **Speaking-time predictor of outcome**: does a justice asking more questions of the petitioner predict a win for the respondent?

### Implementation Notes
- Transcript data is available via Oyez API under `oral_argument_audio[].href` → transcript sections
- NLP: use a simple Hugging Face sentiment model (e.g., `distilbert-base-uncased-finetuned-sst-2-english`)
- For question direction, count turns by speaker type (justice vs. advocate)
- Correlate question count with eventual vote

### Key Finding from Literature
Research by Jacobi & Schweers (2017) found that the justice who asks the most questions of a party tends to vote against that party. Build a visualization of this correlation.

---

## 7. Advocate / Attorney Win Rates

**Status:** Proposed  
**Priority:** Medium

### Description
Track individual Supreme Court advocates — which attorneys have the highest win rates? Who appears most frequently? How does their win rate vary by issue area?

### Key Visualizations
- **Leaderboard**: top 20 attorneys by appearance count
- **Win rate bar chart**: sorted by win rate (min 10 appearances)
- **Career timeline**: appearances per term for top advocates

### Data Sources
- Oyez includes attorney information in case details under `advocates` field
- Each advocate entry has `advocate.name`, `advocate_description` (petitioner's counsel / respondent's counsel), `href`
- Win is determined by matching `winning_party` to petitioner/respondent role

### Implementation Notes
- This requires fetching detail for every case, so a background data collector script is advisable
- Cache results in a local CSV to avoid re-fetching

---

## 8. Amicus Brief Tracker

**Status:** Proposed  
**Priority:** Low-Medium

### Description
Amicus curiae ("friend of the court") briefs signal the salience of a case. Track:
- How many amicus briefs were filed per case?
- Which organizations file amicus briefs most often?
- Does amicus brief count correlate with closer decisions?

### Data Sources
- Oyez does not provide full amicus data — this would require:
  - SCOTUSblog case pages (scraping)
  - PACER federal court records (paid)
  - CourtListener / Free Law Project API (free, partial)

### Implementation Notes
- Start with a curated static dataset of high-salience cases and their amicus counts
- Future: integrate CourtListener's `/docket-entries/` endpoint

---

## 9. State Law Impact Dashboard

**Status:** Proposed  
**Priority:** Medium

### Description
For each U.S. state, show:
- How many of that state's laws (or state court decisions) were reviewed by SCOTUS?
- What was the reversal rate?
- Which issue areas were most challenged?

### Key Visualizations
- **Choropleth map** of states colored by number of SCOTUS reviews
- **State drilldown**: click a state, see all cases from that state's courts
- **State vs. federal government** win rates when a state is the respondent vs. petitioner

### Data Sources
- Lower court field in Oyez (`lower_court.name`) contains state court names
- Parse state name from the lower court string
- Use Plotly's `choropleth` with `locationmode='USA-states'`

---

## 10. Congressional Response Tracker

**Status:** Proposed  
**Priority:** Low

### Description
When SCOTUS strikes down a law, Congress sometimes responds with new legislation. Track these "constitutional dialogues":
- Cases that prompted constitutional amendments (Pollock → 16th Amendment, etc.)
- Cases that prompted new legislation (Ledbetter → Lilly Ledbetter Fair Pay Act)
- Cases that Congress has attempted but failed to respond to

### Implementation Notes
- Fully curated static dataset (no API available for this)
- Rich narrative text with expandable cards per case

---

## 11. Justice Replacement Simulator

**Status:** Proposed  
**Priority:** Medium

### Description
"What if" tool: simulate how SCOTUS outcomes would have changed if a different justice had been appointed to a seat. For example:
- What if Merrick Garland had been confirmed instead of Neil Gorsuch?
- How would key 5-4 decisions have turned out?

### Key Visualizations
- **Counterfactual vote table**: for every 5-4 decision, show the current majority, then the "flipped" outcome if justice X was replaced by justice Y
- **Agreement-based estimation**: use the agreement matrix to estimate how a hypothetical justice would have voted

### Implementation Notes
- For the "replacement" justice, allow user to pick any past justice or a custom lean (Liberal/Moderate/Conservative)
- Use agreement matrix data to predict how the replacement would vote on each case
- Simple heuristic: Conservative replacement votes with Thomas/Alito 90% of time; Liberal with Sotomayor/Kagan 90%

---

## 12. Term-to-Term Comparator

**Status:** Proposed  
**Priority:** Low-Medium

### Description
Compare any two SCOTUS terms across multiple dimensions simultaneously:
- Number of cases decided
- Issue area distribution
- Average vote split (5-4 vs. unanimous)
- Reversal rate
- Win rates by party type
- Top justice by majority opinion authorship

### Implementation Notes
- Simple parallel-coordinates or radar chart comparing the two terms
- Drop-down selectors for Term A and Term B
- Data from existing Oyez term-level cache

---

## 13. Oral Argument Sentiment Analysis

**Status:** Proposed  
**Priority:** Low (requires NLP infrastructure)

### Description
Use natural language processing on oral argument transcripts to score:
- **Hostility toward petitioner/respondent**: negative sentiment in justice questions
- **Confusion indicators**: "I don't understand…", "help me understand…"
- **Favorable indicators**: justice completing advocate's argument, hypotheticals that favor advocate's position

### Implementation Notes
- Use `transformers` library with a lightweight model (DistilBERT)
- Process transcript turn-by-turn, score each justice turn
- Group scores by petitioner-facing vs. respondent-facing turns
- Correlate with eventual outcome for a "sentiment predicts outcome" analysis

### Dependencies
```toml
transformers>=4.40
torch>=2.2
```

---

## 14. Cross-Court Citation Network

**Status:** Proposed  
**Priority:** Low

### Description
Extend the existing citation network to include lower federal courts (circuit courts) and show how SCOTUS opinions ripple down through the system:
- Which SCOTUS cases are cited most in circuit court opinions?
- Which circuits adopt SCOTUS reasoning fastest vs. slowest?

### Data Sources
- CourtListener API provides full text of federal circuit court opinions
- Free Law Project's `citation-graph` dataset (bulk download available)

---

## 15. Docket Watch — Live Term Tracker

**Status:** Proposed  
**Priority:** High (user-facing, high value)

### Description
A live dashboard that auto-refreshes and shows the status of every pending case in the current SCOTUS term:
- Color-coded status: Cert Granted / Argued / Decided / Pending
- Countdown to next scheduled argument date
- One-click to case detail
- Alert when a new decision drops (using Streamlit's `st.rerun()` with a timer)

### Implementation Notes
- Use `st.empty()` + `time.sleep(300)` + `st.rerun()` for auto-refresh
- Cache busting: set `ttl=300` on the Oyez term fetch
- Display last-updated timestamp
- This already partially exists in the Term Calendar tab — expand it with live alerts

---

## Prioritized Backlog

| # | Feature | Priority | Complexity | Value |
|---|---------|----------|------------|-------|
| 2 | Case Outcome Prediction Model | 🔴 High | 🔴 High | 🔴 High |
| 1 | Presidential Legacy Tracker | 🔴 High | 🟡 Medium | 🔴 High |
| 15 | Docket Watch | 🔴 High | 🟢 Low | 🔴 High |
| 6 | Oral Argument Analytics | 🟡 Medium | 🟡 Medium | 🔴 High |
| 7 | Advocate Win Rates | 🟡 Medium | 🟡 Medium | 🟡 Medium |
| 3 | Justice Ideology Drift | 🟡 Medium | 🟡 Medium | 🟡 Medium |
| 11 | Justice Replacement Simulator | 🟡 Medium | 🟡 Medium | 🟡 Medium |
| 9 | State Law Impact Dashboard | 🟡 Medium | 🟡 Medium | 🟡 Medium |
| 5 | Certiorari Predictor | 🟡 Medium | 🔴 High | 🟡 Medium |
| 4 | Doctrine Evolution | 🟡 Medium | 🟢 Low | 🟡 Medium |
| 12 | Term Comparator | 🟢 Low | 🟢 Low | 🟡 Medium |
| 8 | Amicus Brief Tracker | 🟢 Low | 🔴 High | 🟡 Medium |
| 10 | Congressional Response | 🟢 Low | 🟢 Low | 🟢 Low |
| 13 | Sentiment Analysis | 🟢 Low | 🔴 High | 🟡 Medium |
| 14 | Cross-Court Citation | 🟢 Low | 🔴 High | 🟢 Low |

---

## Technical Notes

### Caching Strategy
- All Oyez API calls use `@st.cache_data(ttl=1800)` (30-min cache)
- Training data for the prediction model should be cached as a local CSV, not re-fetched each session
- Large datasets (e.g., 30 terms of vote data) should use `st.session_state` after first load

### Rate Limiting
- Oyez API has no published rate limit but add `time.sleep(0.05)` between requests
- Bulk data fetching (for ML training) should be done in a background script, not inline

### Reproducibility
- Model files (`.pkl`) should be committed to the repo or stored in a `data/models/` directory
- Model training script should accept a `--seed` argument and log parameters

### Testing
- Add `streamlit-app/tests/test_features.py` with unit tests for feature engineering functions
- Test the ML pipeline with `pytest` via the validation skill

---

*Last updated: May 2026*
