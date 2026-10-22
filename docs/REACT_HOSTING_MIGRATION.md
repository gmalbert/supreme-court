# React migration and hosting assessment

Assessed October 21, 2026. This is a migration proposal; no application or hosting changes have been made.

## Current system

The public application at https://supremescrutiny.com responds through Cloudflare and includes `x-railway-edge` and `x-railway-request-id` headers, confirming Railway behind the Cloudflare proxy at the time of inspection.

`cases.py` registers twelve top-level Streamlit destinations, several of which compose additional feature pages. The application includes case browsing, oral arguments, court history, justice and advocate analysis, geography, networks, presidential legacy, research, predictions, and conversational retrieval.

The core case list and detail Parquet files total approximately 6.8 MB compressed. Seven transcript Parquet files total approximately 178 MB compressed. In-memory dataframes and search indexes require additional memory; file sizes are not RAM estimates. Additional retrieval artifacts exist in this working copy.

Much of the data and ML code can remain Python. UI code, navigation, charts, widget callbacks, and session handling must be rewritten. Some service utilities also depend on Streamlit: search and retrieval use `st.cache_resource`, chat providers use `st.secrets`, and retrieval/chat adapters use session state or UI warnings. A new API must not depend on an active Streamlit session.

## Live inspection and revised Cloudflare-first recommendation

The subsequent live-browser inspection covered Home, Cases, Predictions, and Analytics. The deployed UI differs from this working copy: Home offers "Find Cases by Description", while the local Home also includes grounded AI chat. Do not assume uncommitted local capabilities are already deployed.

- Searching for `student speech in public schools` navigated to Cases and returned fifteen ranked results, including Mahanoy and Bethel, after a server running/searching state.
- Predictions explicitly reported that the ML model is not yet trained and uses the statistical baseline. Generating a prediction with the default inputs returned a 68.4% reversal probability. The matching local `_static_predict` function is arithmetic over fixed constants and can be ported to browser JavaScript. A function called "static" still performs computation; it does not make the existing Streamlit deployment statically hostable.
- Analytics displayed term selection, issue/disposition charts, a case listing, filtering, and CSV export. These are candidates for browser computation over versioned data or prebuilt aggregates.
- The local core Oyez loader sets `LOCAL_ONLY = True`; its data is already predominantly snapshot-based. Transcript helpers have separate live fallback paths, so this is not proof that every feature is offline.
- The repository also includes Python TF-IDF/hybrid retrieval, optional trained-model inference/explanations, and interactive model training. These cannot be preserved by uploading the existing Python files to static hosting.

Conclusion: the current application is a dynamic Streamlit server, not a static site. Much of its observable behavior can be rebuilt as a statically hosted React application. Prioritize Cloudflare Static Assets plus versioned JSON/search artifacts, with R2 as needed for larger files. Build data and indexes in GitHub Actions; load records/transcripts in chunks. Browser-side filtering, charts, watchlists, downloads, and the current statistical prediction baseline need no dedicated VM. Benchmark browser-side ranked search before selecting an implementation or promising parity with Python retrieval.

Use Workers only for features requiring secrets, external AI calls, or server-side queries. Preserve advanced Python retrieval or trained-model behavior through a validated port or Cloudflare Containers if required. Move model training off the public request path. Oracle is not a required dependency. Pure static hosting is not sufficient to preserve every feature in the current working copy without adapting or relocating computation.

The hybrid Oracle design below remains an alternative for maximum Python reuse, rather than the preferred target given the user's Cloudflare preference.

## Alternative: Cloudflare frontend plus Oracle backend

```text
Browser
  -> Cloudflare: React + TypeScript frontend
  -> /api/*: gateway to Python API on Oracle Cloud Compute
                 -> local versioned Parquet and retrieval indexes
                 -> saved prediction models
                 -> configured AI provider

GitHub Actions
  -> refresh data, build indexes/models, validate release
  -> publish immutable data artifacts and application releases
```

Use React with Vite and a router. Cloudflare Workers Static Assets can serve the frontend; an API gateway can keep browser requests on the same origin. Oracle Compute can run a containerized Python API, such as FastAPI, behind HTTPS. Protect direct origin access, keep provider credentials on the server, and set limits on paid AI requests. The same React build and Python container can also both run on Oracle if desired.

This retains the existing Python retrieval and ML behavior while removing Streamlit from the deployed application. It also keeps the backend portable to Cloudflare Containers or another Linux host.

Oracle's free resources are an option to investigate, not an assumed production allocation. Verify account eligibility, regional capacity, architecture compatibility, storage, backups, and reclamation policies before choosing a free shape. A VM also requires OS updates, process supervision, monitoring, and recovery procedures.

## Fully Cloudflare alternatives

### React plus Cloudflare Containers

Host the frontend as static assets and run the Python API in Containers through Worker routing. This can eliminate both Streamlit and Railway while retaining Python. Container disk is ephemeral by default: package immutable data/model releases into the image or retrieve versioned artifacts from R2, and persist necessary writes outside the container. Benchmark startup, memory, active running time, and cost before selecting an instance size.

### React plus Workers, D1, and R2

Use D1 for queryable metadata and R2 for transcripts, downloads, and larger immutable artifacts. Build aggregate chart datasets in GitHub Actions. Implement light API routes and provider calls in Workers. Design and validate lexical, transcript, and semantic retrieval explicitly; a database keyword index is not automatically equivalent to the existing hybrid ranking system. Retain predictions by validating a portable inference runtime, porting model evaluation, or defining the supported prediction inputs and precomputing results where feasible.

This path removes the long-lived Python server, but has the largest migration scope. Ordinary Workers have a 128 MB memory limit and are not a direct substitute for loading the current pandas/scikit-learn application. Python Workers also have package/runtime compatibility constraints. Do not move the complete Parquet corpus into the browser bundle or assume that changing the UI framework solves backend hosting.

## Migration sequence

1. Inventory all currently reachable features and define parity criteria, including retrieval quality and prediction outputs. Use this working copy as an explicit source decision: it contains substantial uncommitted changes beyond the published repository.
2. Extract framework-independent services for case data, retrieval, predictions, and AI providers. Replace Streamlit caching, secret access, session state, and UI errors with service equivalents. Keep the current site running during this work.
3. Define a stable, paginated API: case list/detail, justice records, transcript segments, aggregate analytics, retrieval, chat, and predictions. Validate inputs, bound expensive requests, and version data releases. Never accept arbitrary upstream URLs as unrestricted fetch targets.
4. Build a React vertical slice with real data: search -> results -> case detail -> cited answer -> source case. Implement URL-based filters, accessible loading/error states, and mobile navigation. Stream answers over HTTP if needed; Streamlit's WebSocket protocol is no longer required.
5. Port remaining feature groups and interactive charts. Preserve exports, timeline filters, oral-argument links, and source attribution. Decide whether public case pages need prerendering or server rendering for indexing and link previews.
6. Move data refreshes and model/index builds to CI or controlled background jobs. Publish versioned artifacts with a manifest and rollback support. Public requests should not trigger full model training or corpus rebuilding.
7. Deploy a preview on the selected target. Compare representative API and UI outputs against the old application, run retrieval evaluation queries, and measure memory, latency, concurrency, cold starts, and cost.
8. Switch the production route after parity checks, preserve old public links through redirects, and retain the Railway deployment temporarily for rollback. Remove Railway only after confirming the replacement works.

## Hosting choice

| Target | Rewrite scope beyond React | Main tradeoff |
| --- | --- | --- |
| Cloudflare React + Oracle Python API | Moderate | Reuses Python; requires VM operations |
| Cloudflare React + Cloudflare Python container | Moderate | One hosting provider; measure runtime cost and startup |
| Cloudflare React + Workers/D1/R2 | Largest | Requires a new data-serving and retrieval/inference design |
| Oracle frontend + Python API | Moderate | Portable deployment; VM serves the entire application |

Recommended first milestone: a preview of real case search, detail, and grounded chat using React plus a portable Python API. Keep the API independent of the host so choosing Oracle versus Cloudflare Containers does not require another frontend rewrite.

## Primary references

- React and API hosting: https://developers.cloudflare.com/workers/vite-plugin/tutorial/
- Cloudflare static assets: https://developers.cloudflare.com/workers/static-assets/
- Workers limits: https://developers.cloudflare.com/workers/platform/limits/
- Python Workers packages: https://developers.cloudflare.com/workers/languages/python/packages/
- Cloudflare Containers: https://developers.cloudflare.com/containers/
- Container lifecycle/storage: https://developers.cloudflare.com/containers/concepts/architecture/
- Container pricing: https://developers.cloudflare.com/containers/platform/pricing/
- Oracle Always Free resources and capacity caveats: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
