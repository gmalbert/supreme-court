# Supreme Scrutiny (SCOTUS) — Next 5 Features to Implement

> **Based on:** Codebase gap analysis as of July 2025

---

## Feature 1: Current Term Live Tracker

**Why:** The app holds 8,251+ historical cases but has no dedicated view for the active SCOTUS term. Adding a "Current Term" section showing pending cases, oral argument dates, and decisions handed down this term would be the most time-relevant feature for researchers and news followers.

**How:**
1. Add `scripts/fetch_current_term.py` that queries the Oyez API for the current term: `https://api.oyez.org/cases?filter=term:{year}&per_page=100`
2. Filter for `status: "decided"` (rendered decision) vs `status: "argued"` (pending) vs `status: "granted"` (cert granted, not yet argued)
3. Add `pages/0_Current_Term.py` as the first page in navigation with a status table: Case | Argued | Decision Date | Outcome
4. GitHub Actions: daily refresh of current term data during October–June (SCOTUS term schedule)

**Complexity:** Medium

---

## Feature 2: Precedent Citation Network

**Why:** The Oyez API includes citation data for many cases. Visualizing how landmark cases are cited creates a unique research tool showing how doctrine evolves — no free public tool offers this for SCOTUS.

**How:**
1. Extend `utils/oyez_api.py` to extract `cited_cases` from the Oyez case detail JSON (available in the API response)
2. Build a directed citation edge list and store in `data/citation_edges.parquet`
3. Add `pages/8_Citation_Network.py` using NetworkX + Plotly scatter graph
4. UI: search by case name → show all cases that cite this case (forward citations) and all cases this decision cites (backward citations)
5. Node size = in-degree (more citations = larger node)

**Complexity:** Medium

---

## Feature 3: Oral Argument Sentiment Analysis

**Why:** Research shows justices who ask more hostile questions to a party tend to vote against that party. The `pages/5_Oral_Arguments.py` already tracks question counts — adding NLP sentiment scoring per justice per argument would add meaningful predictive signal.

**How:**
1. Add `utils/sentiment.py` using `transformers` (HuggingFace) with a pretrained DistilBERT sentiment model (inference-only, no training needed)
2. Apply sentiment scoring to justice question text from Oyez oral argument transcripts
3. Compute `avg_sentiment_per_justice` per case: positive = friendly, negative = hostile
4. Display on `pages/5_Oral_Arguments.py` as a heatmap: justice × party × sentiment score
5. Add `hostile_justice_count` as a feature in `pages/9_Predictions.py`

**Complexity:** High

---

## Feature 4: Amicus Brief Analysis

**Why:** The number and type of amicus curiae filers (government, corporate, NGO, academic) predicts case outcomes — heavily-briefed cases with government amicus support rarely go against the government. This data is available in SCOTUS docket records.

**How:**
1. Add `scripts/fetch_amicus_filings.py` that scrapes the SCOTUS docket for amicus brief filer counts per case (CourtListener API or PACER if accessible)
2. Classify filers by type: US Government (SG office), State government, Corporate, NGO/advocacy, Academic
3. Add `amicus_count`, `govt_amicus_filed`, `corp_amicus_count` as features in `pages/9_Predictions.py`
4. Add an "Amicus Breakdown" display to the case detail view on `pages/1_Cases.py`

**Complexity:** Medium

---

## Feature 5: Justice Replacement Impact Simulator

**Why:** "What if RBG had been replaced by a liberal justice in 2016?" is one of the most common SCOTUS "what-if" questions. A simulator that rereplays historical decisions with a hypothetical justice's voting pattern would be a unique, high-engagement feature.

**How:**
1. Build a `utils/justice_simulator.py` that accepts: replaced justice, replacement ideology score, historical case set
2. For each historical case, substitute the replaced justice's actual vote with a probabilistic vote based on the replacement ideology score (derived from Martin-Quinn scores)
3. Add `pages/10_Simulator.py` with two dropdowns: "Replace" and "Replacement Ideology" slider
4. Display: how many outcomes would have changed, which landmark cases would have gone the other way
5. Use `data/case_detail.parquet` as the source — no new data needed

**Complexity:** Medium
