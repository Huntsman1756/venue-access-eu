# ADR 001 — DuckDB + Parquet instead of PostgreSQL

## Status
Accepted (v0.1)

## Context
Dataset is ~10⁶ rows/year max. Single-writer batch ingestion, read-only
analytical queries, reproducible-from-artifacts rebuilds.

## Decision
DuckDB as the live store + Parquet as the durable export format. The
`.duckdb` file is a derived artifact: it can always be rebuilt from raw
snapshots + code. No PostgreSQL in v0.1.

## Consequences
- + Zero ops, embedded, columnar analytics, trivial CI.
- + Parquet releases are language-neutral and immutable.
- - Single writer; no concurrent multi-user writes (not needed).
- Revisit if we ever need online multi-writer ingest or row-level ACLs.
