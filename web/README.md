# Supreme Scrutiny on Cloudflare

React/TypeScript replaces the Streamlit runtime. Cases, transcripts, charts, search,
saved cases, and the statistical prediction calculator run from static assets.
An optional Cloudflare Worker calls the configured AI provider for grounded chat.
No Oracle VM, Railway service, Python server, database, or R2 bucket is required.

The original Streamlit source remains available during migration and rollback.

## Build and run

For one-command local startup, run `docker compose up --build` from the repository
root and open `http://localhost:8787`. Docker builds the data release automatically;
no host Python or Node installation is needed. See [INSTALLATION.md](../INSTALLATION.md)
for Compose tests, optional AI credentials, and the Cloudflare installation/cutover
procedure. The native build commands below remain available without Docker.

From the repository root (Python 3.13 and Node 24):

```powershell
python -m pip install -r scripts/requirements-web.txt
npm ci --prefix web
python scripts/export_web_data.py
npm --prefix web test
python -m pytest tests/test_web_export.py -q
npm --prefix web run build
node scripts/check_web_release.mjs
cd web
npm run preview
```

Open `http://127.0.0.1:8787`. This preview runs the real Worker with the built
static assets. For frontend hot reload, run `npm run dev` in a second terminal;
Vite forwards `/api` to the Wrangler preview. Do not run `--skip-transcripts`
for a production release. Generated `public/data`, `dist`, dependencies, and
local credentials are ignored; CI regenerates assets from the tracked snapshots.

## Deployment

`wrangler.jsonc` deploys to a Workers preview URL without changing the live domain.
The static release fits the 20,000-file / 25 MiB-per-file limits checked by the
release script. Transcripts are fetched by session, never bundled into the app JS.
Use a paid Workers plan if the account's limits require it for this release.

1. Authenticate Wrangler with your Cloudflare account, or configure scoped
   `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in CI.
2. Run `npx wrangler deploy --dry-run` in `web/` to inspect the package.
3. Run `npx wrangler deploy` to publish the app at its Workers URL.
4. Test the preview URL, including case links, the browser search Worker,
   arguments, mobile navigation, CSV downloads, and prediction parity.
5. Only after verification, bind `supremescrutiny.com` as a Worker custom domain
   in Cloudflare and update its existing Railway-origin configuration as needed.
   Preserve the existing `www` redirect to the apex domain.
6. Retain Railway temporarily for rollback; remove it after acceptance.

The GitHub Actions workflow builds/tests pushes and PRs. Production deployment is
manual (`workflow_dispatch` with `deploy=true`) from `main` or `master` and uses
the `cloudflare-production` environment. It does not cut over the custom domain.
Configure that environment's approval policy as appropriate for your repository.

## Optional grounded AI answers

Default provider: Gemini. Keep provider keys in Worker secrets, never `VITE_*`
variables or static data:

```powershell
cd web
npx wrangler secret put GEMINI_API_KEY
```

For local development, create ignored `web/.dev.vars` containing your existing
provider configuration. Do not commit it. The app works without any AI credential;
Research shows retrieved case records and explains when answers are unavailable.
No live provider request is made by the automated tests.

`GEMINI_MODEL` is configurable in Wrangler. OpenCode remains an explicit option:
set `CHAT_PROVIDER=opencode`, store `OPENCODE_API_KEY` as a Worker secret, and
optionally set `OPENCODE_MODEL`. Provider errors never trigger a paid fallback.

The API accepts bounded case IDs, hydrates evidence from its own static assets,
validates conversation roles, enforces a request-size bound and same-origin
browser access, and applies Cloudflare's per-IP rate-limiter binding. IP limits
are not an account-wide spending cap; set provider budgets/quotas appropriate to
public traffic. Responses and errors never include API keys.

## Data and search

`scripts/export_web_data.py` exports all case records, per-case detail, per-session
speaker-attributed transcripts, legacy curated collections, and a TF-IDF inverted
index. It interprets literal legacy content without executing the Streamlit pages.
Browser search runs in a Web Worker, with exact-name/docket prioritization and
topic vocabulary expansion. The optional local BGE dense-embedding corpus is not
required or shipped. The browser index is a lexical replacement, not a claim of
identical ranking to optional Python hybrid/dense retrieval. Tests check named
cases and landmark recall on the actual export.

Core metadata covers 1955–2025 terms in the current snapshot. Earlier timeline
figures and landmark references are curated. Views label estimates, inferred
issue/party categories, and missing records. The location map uses case-location
metadata; it does not imply complete state coverage. Citation networks are
curated reference relationships, not an exhaustive citator or current-law check.

The existing Oyez refresh workflow updates tracked source snapshots; the web
workflow builds from their content. GitHub push events created with `GITHUB_TOKEN`
do not trigger another workflow. A successful refresh triggers verification through `workflow_run`; production
deployment still requires the manual deployment action.

## Offline training

`python scripts/train_web_model.py` trains logistic models on the existing
case/vote CSV and exports `data/web_model.json`. The latest 20% of unique cases
are held out before fitting (case IDs, not vote rows, define the split). Exported
coefficients are evaluated directly by JavaScript; tests compare Python-generated
probability fixtures to browser inference. The manual training workflow publishes
an artifact for review; it does not automatically promote a model.

The included experimental release underperformed the majority-class reference
on its held-out set. The original statistical baseline remains the default and
is explicitly labeled as an unvalidated heuristic. Neither output is legal advice
or a calibrated forecast. Full Python SHAP explanations and interactive public
training are replaced by offline metrics and transparent baseline features.

## Verification

- `npm test`: real-corpus search, data arithmetic, baseline/model parity, and
  mocked Worker API, provider failure, validation, and secret handling checks.
- `python -m pytest tests/test_web_export.py -q`: source/export counts, curated
  catalog extraction, timezone-safe dates, asset limits, and argument links.
- `npm run build`: strict TypeScript checking and optimized lazy route bundles.
- `node scripts/check_web_release.mjs`: production completeness and asset limits.
- `npx wrangler deploy --dry-run`: actual Cloudflare Worker packaging validation.
- `npm run test:e2e`: reproducible desktop/mobile Playwright tests against the
  real Worker (allocates free local ports unless `PLAYWRIGHT_BASE_URL` is supplied).
- `python scripts/check_python.py` from the root: `py_compile` for project Python.

Legacy route paths such as `/Cases`, `/People`, and `/Predictions` are preserved.
New case links use `/case/<term>/<docket>`. Selected sections use the `view` query
parameter; description search uses `q`. Saved cases remain in browser storage.
An SPA requires JavaScript; case-specific search indexing/SEO can be added with
prerendered pages if that becomes a requirement.
