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

## v0.1.2 — observation ≠ resolution (2026-10-07)

- **Decoupled identity layers**: `source_participant` (`sp:src:key`) is now
  the temporal anchor for observations, intervals and change events.
  `identity_resolution` is an append-only decision trail keyed by
  (source_participant_id, resolution_run_id); reads join to the latest row.
  Resolver improvements can no longer fabricate membership history.
- **Invariants enforced by tests**: identical source records with a flipped
  resolution produce zero membership events and one
  `IDENTITY_RESOLUTION_CHANGED`; first_seen/last_seen/interval continuity
  are untouched.
- **Second-cycle result**: real membership changes = 0; the 19 spurious
  v0.1.1 "newly observed" events became identity events.
- **Resolution stability**: prior accepted resolutions pin unless
  contradicted (`stabilize_resolution`); `FUZZY_CANDIDATE` stays an
  unresolved bucket with `candidate_lei`/`candidate_confidence` instead of
  silently becoming an entity.
- `GET /participants/{id}/identity` exposes the full resolution audit.
- `/changes` + CLI + UI gained `include_identity` alongside
  `include_baseline`; GLEIF candidate queries strip punctuation (400 fix);
  GLEIF cache + published artifacts purged from git history (rewrite before
  first push).

### Known limitations (post-close notes, not addressed in v0.1.3)

- `refresh-data.yml` treats per-source failures as recoverable (`|| true`)
  and only fails when zero good snapshots exist. A future improvement is an
  explicit `PASS / DEGRADED / FAIL` rollup in the quality report so a
  substantial source regression surfaces as DEGRADED instead of a silent
  partial run. Deliberately not changed in v0.1.3.
