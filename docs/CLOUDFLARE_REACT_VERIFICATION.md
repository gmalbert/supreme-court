# Cloudflare React migration verification

Implemented on `codex/cloudflare-react-migration`. Production remains on Railway;
this branch does not change DNS, publish a Worker, or remove the old deployment.

## Architecture

- React/TypeScript app with twelve top-level destinations and stable legacy paths.
- Browser Web Worker for indexed case search; no Python runtime at deployment.
- 8,251 case records, 8,238 full case-detail records, and 8,294 transcript sessions.
- Versioned, reproducible static exports of all original curated content.
- Cloudflare Worker for optional grounded Gemini/OpenCode answers; keys remain in
  Worker secrets. Existing local credentials were not copied or exposed.
- Offline data/model jobs, Cloudflare package configuration, and GitHub CI.

## Automated checks

- 23 Vitest tests: real-corpus named-case and school-speech search, statistical
  baseline parity, bounded calculators, agreement denominators, missing-outcome
  handling, Python/JavaScript trained-model parity, and Worker API behavior.
- 3 Python export checks: negative-epoch dates, safe curated-content extraction,
  source/export counts, unique IDs, Cloudflare asset limits, and every available
  transcript reference.
- Strict TypeScript check and production Vite build.
- Static release completeness/size checks and Wrangler deployment dry run.

## Browser checks

Run against the production build with Wrangler's local Cloudflare runtime:

- Loaded every main route directly, including a full browser reload.
- Opened all 55 feature sections without a rendering error.
- Searched `Obergefell v. Hodges`, verified it ranked first, saved the case, and
  opened its complete record and source links.
- Loaded its oral-argument session with 368 speaking turns and filtered the
  transcript for `equal dignity` (three matching turns).
- Generated the default statistical outcome: 68.4%, matching the original live
  Streamlit application and the Python baseline.
- Verified that optional chat fails gracefully when no Worker AI key is set.

A browser reload exposed a conditional-cache bug: a `304 Not Modified` static
asset response was being converted to a missing-data response. This was fixed
and covered by a regression test. Export testing also caught Windows' negative
Unix timestamp limitation; UTC epoch arithmetic now preserves pre-1970 dates.
Argument records whose transcripts are absent in the source snapshot are labeled
unavailable instead of offering a broken transcript request.

## Intentional deployment changes and limits

- The browser search is an indexed lexical implementation with vocabulary
  expansion and exact-name prioritization. Optional Python BGE dense/hybrid
  retrieval is not shipped or claimed to have identical rankings.
- Public model training moves to offline jobs. The included portable logistic
  model is experimental: held-out accuracy 57.07% versus 71.73% for the
  majority-class reference. It is selectable but is not the default. No validated
  accuracy is claimed for the retained statistical baseline.
- Python SHAP views are replaced by transparent features and held-out model
  metrics. Several related Streamlit subviews are consolidated into shared React
  tables, chart panels, and comparisons rather than reproducing the old widget
  layout. Curated data, estimates, and inferred categories are labeled.
- The old Streamlit application and its requirements remain for rollback; the new
  deployment does not import them. Pre-existing uncommitted work is preserved.
- Actual provider calls were mocked during testing; no billable AI requests were
  made. A real Worker secret is needed to validate live AI responses.
- Desktop browser flows were exercised. A physical/mobile viewport and a hosted
  Cloudflare production deployment still require acceptance testing before DNS
  cutover. Static SPA case pages are not prerendered for search crawlers.

Deployment and local build instructions: [web/README.md](../web/README.md).
