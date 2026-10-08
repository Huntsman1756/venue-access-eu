# ADR 006 — Frontend architecture

## Status
Accepted (v0.1)

## Context
Data explorer for a small dataset; dense tables; provenance drill-down is
the core differentiator.

## Decision
Next.js 16 App Router + TypeScript + Tailwind + TanStack Query/Table.
Server-rendered shell (nav, methodology, static content); all dataset reads
client-side via the read-only FastAPI JSON API (no duplicated data model,
no fake/demo data — fixtures come from real captures).

## Consequences
+ One contract (OpenAPI) for UI and third parties; trivial deploy
  (static-ish shell + API).
- First-paint of data sections depends on API latency (mitigated by small
  dataset + p95 targets).
