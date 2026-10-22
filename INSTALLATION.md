# Local installation and Cloudflare migration

The React application runs entirely on Cloudflare: static case/transcript files
plus an optional Worker for AI answers. Docker is for local use and build/test
reproducibility; Cloudflare does not need to run this Docker image.

## One-command local startup

Install Docker Desktop with Linux containers (Windows/macOS), or Docker Engine
with Compose v2.24+ (Linux). Start Docker before running the command. Allow several
GB of disk space and preferably at least 4 GB of build memory. No local Python,
Node, Cloudflare account, or AI key is required for the basic site.

From the repository root:

```sh
docker compose up --build
```

Open **http://localhost:8787** after the service reports ready. The first build
installs dependencies, exports all 8,251 case records and the transcript corpus,
runs unit tests, and builds React. This takes longer than later cached starts.
There are no prerequisite manual data-export steps, host bind mounts, or database
setup steps. The runtime runs as a non-root user and is published only to local
loopback. The site has a health check at `/api/health`.

For a background service that waits until it is healthy:

```sh
docker compose up --build -d --wait
```

Stop it with `docker compose down`. After source/data changes, use `--build`
again. To change the host port, set `SUPREME_PORT` before starting (PowerShell:
`$env:SUPREME_PORT = '8790'`; shell: `SUPREME_PORT=8790 docker compose up --build`).

### Optional local AI answers

Create **`web/.dev.vars`** with an existing provider key if desired:

```dotenv
GEMINI_API_KEY=your_existing_key
```

This ignored file is optional. Compose supplies it only at runtime; `.dockerignore`
excludes it and other credentials from the build context. The startup script
passes only the approved provider bindings to Wrangler, without logging values.
Keep keys out of `VITE_*` variables and do not commit the file. Restart with
`docker compose up -d --force-recreate` after changing local credentials.

OpenCode remains opt-in: use `CHAT_PROVIDER=opencode` and `OPENCODE_API_KEY` in
that file. The app never switches providers automatically after a failure.

## Testing

With the Compose site running:

```sh
docker compose --profile test run --build --rm e2e
```

This runs the real Playwright suite against the `site` container in desktop and
mobile Chromium. The test service waits for the site's health check; it is not
started by ordinary `docker compose up`. Tests cover real search, saved cases,
transcripts, CSV downloads, prediction changes, all 55 sections, shared links,
reload/cache behavior, missing data, and the unconfigured-AI state. No billable
AI request is made.

For tests without Docker, install Python 3.13 and Node 24, then run from the root:

```sh
python -m pip install -r scripts/requirements-web.txt
npm ci --prefix web
python scripts/export_web_data.py
python scripts/check_python.py
python -m pytest tests/test_web_export.py -q
npm --prefix web test
npm --prefix web run build
node scripts/check_web_release.mjs
cd web
npx playwright install --with-deps chromium
npm run test:e2e
```

`check_python.py` calls `py_compile.compile(..., doraise=True)` for all project
Python files, pruning dependency directories without importing application code.
Playwright allocates free HTTP/debugger ports and starts/stops its own isolated
local Worker. To test an
already running site, set `PLAYWRIGHT_BASE_URL` to its origin. To use installed
Chrome instead of a downloaded Chromium, set `PLAYWRIGHT_CHANNEL=chrome`.
Reports and failure traces go to ignored `web/playwright-report` and
`web/test-results`; use `npx playwright show-report` in `web/` to inspect them.

## Install and publish on Cloudflare

### 1. Prepare a verified release

Use the non-Docker build/test commands above. Alternatively, build and export
the same assets through Docker, requiring only Node 24 on the host for Wrangler:

```sh
docker build --target release --output type=local,dest=./web/cloudflare-package .
npm ci --prefix web
```

The Docker artifact contains `dist/`, `worker/index.ts`, and `wrangler.jsonc`.
It contains no Python runtime, private caches, or credentials.

### 2. Authenticate and verify the Cloudflare package

For a native build:

```sh
cd web
npx wrangler login
npx wrangler deploy --dry-run
npx wrangler deploy
```

For the exported Docker artifact, use the exported configuration instead:

```sh
cd web
npx wrangler login
npx wrangler deploy --config cloudflare-package/wrangler.jsonc --dry-run
npx wrangler deploy --config cloudflare-package/wrangler.jsonc
```

Wrangler opens its normal browser login flow. Select the intended Cloudflare
account if prompted. This publishes a Worker named `supreme-scrutiny` at its
`workers.dev` address; it does not change the production custom domain.
The release currently has roughly 16,600 assets and enforces a 25 MiB per-file
limit. Confirm the account's Workers/static-asset limits and plan before release.
No R2 bucket, D1 database, Oracle VM, or Cloudflare Container is required.

### 3. Configure optional AI secrets

For a native build, run in `web/`:

```sh
npx wrangler secret put GEMINI_API_KEY
```

Add `--config cloudflare-package/wrangler.jsonc` if using the Docker artifact.
Paste the existing key at Wrangler's secret prompt; never put it in an image,
GitHub source file, or frontend build variable. The Gemini model is configurable
through `GEMINI_MODEL` in the selected configuration. For OpenCode, explicitly set
`CHAT_PROVIDER=opencode`, add its Worker secret, and set `OPENCODE_MODEL` if needed.
After changing public variables, redeploy using the same config.

The public AI endpoint has request bounds and a per-IP rate limit. Configure
provider quotas/budgets as well; the per-IP limit is not a total spending cap.

### 4. Verify the hosted release

Check `/api/health`, search-to-case navigation, transcript loading, saved cases,
reloads, maps, CSV downloads, mobile navigation, and the default 68.4% statistical
prediction. Verify a live grounded answer if AI has been enabled. To run the same
automated browser suite against the hosted origin, set `PLAYWRIGHT_BASE_URL` and
run `npm run test:e2e` in `web/`. The tests do not click the paid AI-answer action.

### 5. Move the existing domain off Railway

Only after the hosted release passes acceptance testing:

1. In Cloudflare, open **Workers & Pages → supreme-scrutiny → Settings → Domains
   & Routes** and add `supremescrutiny.com` as a custom domain. Its DNS zone must
   be active in that account. Review the existing Railway-origin DNS record;
   replace it as required by Cloudflare's custom-domain setup.
2. Preserve the existing `www.supremescrutiny.com` redirect to the apex domain.
3. Confirm HTTPS, old `/Cases`, `/People`, etc. links, and shared `?q=&case=` URLs.
4. Retain the Railway deployment temporarily for rollback. If acceptance fails,
   restore the recorded previous DNS/origin configuration while investigating.
5. Remove Railway only after the Cloudflare version is accepted.

The checked-in Wrangler configuration intentionally has no custom-domain route,
so development and preview deployments cannot accidentally cut over production.

## GitHub deployment

Configure `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as secrets in the
repository's `cloudflare-production` environment. Scope the token to the account
and Worker resources needed for deployment; keep zone/DNS changes separate if
performing the cutover through the dashboard. Worker AI keys are configured with
Wrangler, not supplied to frontend builds.

The web workflow runs Python compilation, export checks, unit tests, the React
build, desktop/mobile Playwright, and Worker packaging. A separate job validates
Compose, builds the complete image, starts it, and runs the container browser
suite. Production deployment requires both jobs to pass, and is manual from
`main`/`master` with `deploy=true`. Choose the environment's approval policy in
GitHub. A successful existing data-refresh workflow triggers verification;
publishing an updated release remains an explicit deployment action.

## Platform references

Cloudflare documents the deployment model in [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
and the DNS/HTTPS cutover in [Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

## Verification limits on this machine

Python compilation, the native React build, export checks, unit tests, Playwright,
and Wrangler packaging were run locally. Docker is not installed on this machine,
so container build/start verification is delegated to the checked-in CI job and
should pass before deployment. No production deployment or DNS change was made.
