# ---------- backend ----------
FROM python:3.12-slim AS backend
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock* ./
COPY backend/venue_access ./venue_access
RUN uv pip install --system -e . || pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["uvicorn", "venue_access.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- frontend ----------
FROM node:24-alpine AS frontend-build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

FROM node:24-alpine AS frontend
WORKDIR /app
RUN corepack enable
COPY --from=frontend-build /app ./
EXPOSE 3000
CMD ["pnpm", "start"]
