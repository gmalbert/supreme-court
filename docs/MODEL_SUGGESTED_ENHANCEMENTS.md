# Supreme Scrutiny — Enhancement Suggestions

## Priority 1: ML Outcome Predictor

### Feature Engineering
- Current predictor uses basic case metadata. Add: `petitioner_type` (individual, corporation, government), `lower_court_ideology_score` (using the Judicial Common Space scores), `issue_area_code`, `cert_reason`.

### Voting Bloc Detection
- Use agglomerative clustering on the 5×5 justice agreement matrix to identify stable voting coalitions.
- Visualise blocs on the Analytics page with a dendrogram.

### Term-by-Term Calibration
- Model accuracy changes as court composition shifts. Retrain every October Term and track accuracy drift.

## Priority 2: Network Analysis

### Citation Network Centrality
- Use NetworkX `pagerank` to identify the most influential cases by citation count.
- Render top-20 most-cited cases as a ranked table and force-directed graph.

### Coalition Evolution
- Show how justice agreement blocs have changed after each court composition change.

## Priority 3: Search & Discovery

### Semantic Case Search
- Use `sentence-transformers` to embed opinion text and case headnotes.
- Allow natural-language queries: "cases about police searches of cell phones".

### "Oyez Explorer" Deep Links
- Link every case to its Oyez oral argument audio page.

## Priority 4: Data Pipeline

### Incremental Updates
- Track the last-fetched term. Only re-fetch current-term cases on each run to reduce Oyez API load.
- Add error recovery: if a case fetch fails, log it and retry on the next run.
