# Changelog

## v0.1.1 — hardening (2026-10-07)

- **Temporal semantics**: first good snapshot per source now emits
  `BASELINE_OBSERVED`, not `NEWLY_OBSERVED`. `NEWLY_OBSERVED` requires
  absence in an earlier good snapshot. `/changes` API + CLI + UI exclude
  baseline rows unless `include_baseline`/`--include-baseline` is set.
- **Identity metrics**: `quality-report.json` now asserts both partitions
  close arithmetically — `identity_counts` sums to participants and
  `alias_counts` (latest resolution per alias) sums to aliases. Report
  shows REVIEW if a partition does not close.
- **member_code_normalized**: non-destructive search form (zero-padding
  stripped for numeric codes: `00004441` → `4441`); `member_code` stays
  verbatim. Search matches both; UI shows normalized form in parentheses.
- **Publication-rights gate**: `data/curation/publication_rights.yml` +
  `venue-access rights` + `GET /api/v1/rights` + quality-report +
  manifest. Euronext/BME/LSE marked RESTRICTED pending legal review;
  dataset distribution status is `CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY`
  until cleared. See `docs/licenses.md`, ADR 007.
- Second snapshot cycle executed to verify real diff detection end-to-end.

## v0.1.0 — initial release (2026-10-07)

First working release: adapters (Xetra, Euronext, BME, LSE, ISO10383),
GLEIF identity resolution, temporal engine, DuckDB/Parquet publish, CLI,
FastAPI, Next.js frontend, tests, CI, Docker.
