# venue-access-eu — two images from one Dockerfile:
#   --target api  FastAPI + a synthetic demo dataset generated at build time
#   --target web  Next.js standalone server
# Both run as non-root and expose no host ports; the edge proxy routes to them.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG NODE_IMAGE=node:24-alpine

# ---------- api ----------
FROM ${PYTHON_IMAGE} AS api-build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir "uv==0.11.*"
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/venue_access ./venue_access
RUN uv sync --frozen --no-dev --no-editable
# Deterministic synthetic dataset (ADR 007: the real one is not redistributable yet).
ARG DEMO_SEED=1756
RUN /venv/bin/venue-access demo --seed "${DEMO_SEED}" \
        --db /dataset/venue_access.duckdb --out /dataset/published \
    && rm -f /dataset/venue_access.duckdb.wal

FROM ${PYTHON_IMAGE} AS api
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=api-build /venv /venv
COPY --from=api-build --chown=10001:10001 /dataset /dataset
COPY backend/data/curation/publication_rights.yml data/curation/publication_rights.yml
ENV PATH=/venv/bin:$PATH PYTHONUNBUFFERED=1 \
    VENUE_ACCESS_DB=/dataset/venue_access.duckdb VENUE_ACCESS_MODE=demo
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready',timeout=4).status==200 else 1)"]
CMD ["uvicorn", "venue_access.api.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]

# ---------- web ----------
FROM ${NODE_IMAGE} AS web-build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend .
# Same-origin API by default: the proxy sends /api/* to the api container.
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_SITE_URL=https://venues.h1756.es
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM ${NODE_IMAGE} AS web
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=web-build --chown=node:node /app/.next/standalone ./
COPY --from=web-build --chown=node:node /app/.next/static ./.next/static
COPY --from=web-build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["node", "server.js"]
