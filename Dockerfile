# syntax=docker/dockerfile:1
# Python is used only while building the immutable data release.
FROM node:24-bookworm-slim AS dependencies
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM python:3.13-slim-bookworm AS data
WORKDIR /app
COPY scripts/requirements-web.txt ./scripts/requirements-web.txt
RUN pip install --no-cache-dir -r scripts/requirements-web.txt
COPY scripts/export_web_data.py scripts/train_web_model.py ./scripts/
COPY utils/__init__.py utils/local_data.py ./utils/
COPY pages/*.py pages/legal_data.json ./pages/
COPY data/*.parquet data/web_model.json ./data/
COPY data_files/logo.png data_files/current_justices.json data_files/advocate_stats.parquet data_files/circuit_stats.parquet ./data_files/
COPY data_files/oyez_data/justices/ ./data_files/oyez_data/justices/
COPY --from=dependencies /app/web/node_modules/us-atlas ./web/node_modules/us-atlas
RUN python -m py_compile scripts/export_web_data.py scripts/train_web_model.py utils/__init__.py utils/local_data.py \
    && python scripts/export_web_data.py

FROM dependencies AS build
WORKDIR /app
COPY web/ ./web/
COPY scripts/check_web_release.mjs ./scripts/check_web_release.mjs
COPY --from=data /app/web/public/ ./web/public/
WORKDIR /app/web
RUN npm test && npm run build && node ../scripts/check_web_release.mjs

# Optional artifact export for deployment without installing Python on the host.
FROM scratch AS release
COPY --from=build /app/web/dist /dist
COPY web/worker/index.ts /worker/index.ts
COPY web/wrangler.jsonc /wrangler.jsonc

# Install browsers through the locked runner, avoiding image/runner version drift.
FROM dependencies AS e2e
WORKDIR /app/web
RUN npx playwright install --with-deps chromium
COPY web/package.json web/playwright.config.ts ./
COPY web/e2e/ ./e2e/
COPY web/scripts/run-e2e.mjs ./scripts/run-e2e.mjs
ENV CI=true
CMD ["npm", "run", "test:e2e"]

# Local Cloudflare runtime: no Python, Streamlit, credentials, or source data caches.
FROM node:24-bookworm-slim AS runtime
ENV NODE_ENV=production \
    WRANGLER_SEND_METRICS=false \
    WRANGLER_LOG_PATH=/app/web/.wrangler/logs
WORKDIR /app/web
COPY --from=dependencies --chown=node:node /app/web/node_modules ./node_modules
COPY --chown=node:node web/package.json web/wrangler.jsonc ./
COPY --chown=node:node web/worker/ ./worker/
COPY --chown=node:node web/scripts/container-start.mjs ./scripts/container-start.mjs
COPY --from=build --chown=node:node /app/web/dist ./dist
RUN mkdir -p .wrangler && chown node:node /app/web .wrangler
USER node
EXPOSE 8787
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:8787/api/health',{signal:AbortSignal.timeout(4000)}).then(async r=>{if(!r.ok||!(await r.json()).ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "scripts/container-start.mjs"]
