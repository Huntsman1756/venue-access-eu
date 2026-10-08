# ADR 008 — Source participant identity vs resolved entity

## Status

Accepted (v0.1.2)

## Context

v0.1.1 keyed membership observations and temporal history on the resolved
`participant_id`. The second snapshot cycle proved this wrong: when the
resolver returned different results for identical source rows (e.g. Euronext
"BBVA" resolving FUZZY at t0 and UNRESOLVED at t1), the temporal engine
fabricated disappearance + appearance events. No membership changed — only
our interpretation of the entity did.

## Decision

Two separate identity layers:

- `source_participant` — `(source_id, source_participant_key)` →
  `sp:{source}:{key}`. The stable, source-defined identity. Membership
  observations, intervals and change events are keyed on it.
- `identity_resolution` — append-only decision trail
  `(source_participant_id, resolution_run_id)` mapping a source participant
  to a `participant_id` (`lei:...` or `unresolved:...` bucket). Public reads
  join observations to the latest resolution row.

Resolver stability: a prior accepted (sticky) resolution persists across
runs unless contradictory evidence appears — implemented in
`identity/mapping.py::stabilize_resolution`. `FUZZY_CANDIDATE` never mints
a `lei:` participant; it persists `candidate_lei`/`candidate_confidence` on
the unresolved bucket instead.

## Consequences

- `recompute_history` emits `IDENTITY_RESOLUTION_CHANGED` events from the
  resolution trail (only when the mapped LEI/bucket actually changes), and
  membership events are provably independent of resolver churn — enforced
  by `test_resolution_change_never_fabricates_membership_events`.
- `/changes` excludes baseline AND identity events by default;
  `include_baseline`/`include_identity` opt in.
- The `/participants/{id}/identity` endpoint exposes the full audit trail.
- Source-provided LEIs are preserved on `source_participant.source_lei`
  (source evidence, not interpretation).
