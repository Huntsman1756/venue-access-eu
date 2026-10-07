# ADR 007 — Publication-rights gate for derived data

## Status

Accepted (v0.1.1)

## Context

Not publishing raw snapshots does not establish that the derived dataset
can be redistributed. Euronext's Terms of Use restrict systematic
retrieval to create collections/databases and derivative works without
prior permission; BME limits web information to internal use and requires
prior authorization for commercial use or redistribution; LSE's
market-data licensing covers redistribution, derived data and non-display
uses. EU sui generis database rights can apply to substantial extraction
even when individual facts are weakly copyrightable.

## Decision

Per-source rights are tracked explicitly in
`data/curation/publication_rights.yml` (statuses
`VERIFIED`/`UNCLEAR`/`RESTRICTED` plus fields for automated_fetch,
internal_processing, raw_storage, raw_redistribution,
derived_dataset_redistribution, public_display, attribution,
commercial_use, evidence_url, reviewed_at). `quality-report.json`,
`venue-access rights`, `GET /api/v1/rights` and the publish manifest all
surface the gate verdict (`publication_status`).

## Consequences

- Internal processing, code publication and local analysis are never
  gated.
- A public dataset release (memberships.parquet + hosted UI) requires
  either VERIFIED status per contributing source or documented written
  permission; until then the dataset is `INTERNAL_ONLY`/`REVIEW`.
- Nothing here is legal advice; it is an honest engineering control so a
  release cannot silently claim rights it does not have.
