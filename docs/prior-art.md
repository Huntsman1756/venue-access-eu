# Prior art review

## Own projects (Huntsman1756)
- **OpenInstrument** — instrument→venues inverse of this project (firm→venues).
  Patterns reused conceptually: immutable snapshots, provenance-first,
  Parquet+DuckDB, versioned data releases. No code dependency (would add
  coupling for little reuse).
- **venue-rule-diff** — snapshot/diff/provenance patterns for venue documents;
  same observational-honesty discipline applied here to memberships.

## Entity resolution / data plumbing
- **opensanctions (nomenklatura, followthemoney)** — studied for lineage and
  dedup patterns; ontology too heavy for this model. Reused only the
  principle: every fact carries source + method, candidates are data.
- **ByronWilliamsCPA/gleif**, **ggravlingen/pygleif** — evaluated for GLEIF
  access. Chose a small native httpx client + JSON disk cache: ~150 LOC,
  full control of caching/pacing, fewer transitive deps than either.

## Reference data
- **diurn-cli, w3stling/mic, micbenner/iso10383** — MIC handling
  cross-checked against the official ISO20022 CSV; the official artifact is
  the authority (fetched directly).
- **simonw/datasette** — UX inspiration for data exploration: reproducible
  URLs, table-first density, downloads. Not used as a component.

## Full-stack
- **fastapi/full-stack-fastapi-template** — reviewed for repo layout and
  FastAPI/React separation; Postgres/auth/user-management deliberately not
  adopted.

## Findings adopted
- Multi-artifact snapshot bundling (LSE: list pages + firm details) with a
  deterministic bundle hash.
- "Source-declared update" as a first-class field (Euronext embeds it).
- Explicit source-token→MIC mapping table instead of heuristic MIC inference.
