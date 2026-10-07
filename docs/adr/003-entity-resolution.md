# ADR 003 — Entity resolution: deterministic pipeline + GLEIF REST API

## Status
Accepted (v0.1)

## Context
Euronext and BME publish no LEI. Name matching to GLEIF is the only honest
identity path; fuzzy auto-merge would corrupt the dataset's trust contract.

## Decision
- Deterministic, auditable resolution: exact source LEI → exact normalized
  legal name → country/address corroboration → strict thresholds.
- Fuzzy scores generate *candidates* for manual review, never merges.
- Ambiguous top-scores → CONFLICT; no match → UNRESOLVED. Rejected
  candidates persisted in identity_resolution.candidates_json.
- GLEIF REST API + persistent JSON cache (data/cache/gleif) instead of the
  multi-GB Golden Copy: the participant set is O(10³), responses are
  self-contained evidence, and the cache makes runs reproducible offline.
- Manual overrides live in data/curation/entity_overrides.yml (CI-validated).
- Legal-form signatures are preserved: "X SA" ≠ "X AG".

## Consequences
+ Auditable, offline-reproducible, no LLM anywhere in the pipeline.
- Some real members stay UNRESOLVED until curated — a feature, not a bug.
- Golden Copy evaluation documented for scale-up (see sources.md).
