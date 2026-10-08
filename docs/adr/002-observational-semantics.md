# ADR 002 — Observational semantics

## Status
Accepted (v0.1)

## Context
Sources publish current-state directories, not validity intervals. Asserting
"X is a member" or "X left" from a single capture would overclaim.

## Decision
The dataset models *observations*, not memberships:
- `membership_observation` rows are tied to immutable snapshots;
- temporal fields are `first_seen_at`, `last_seen_at`, `first_absent_at`,
  `reappeared_at` — never `valid_from`/`valid_to`;
- answer states are OBSERVED / NOT_OBSERVED / UNKNOWN; NOT_OBSERVED is only
  produced by sources with `absence_semantics_allowed = true`, good status,
  and documented scope;
- UI/API text renders the semantics explicitly.

## Consequences
Users can always answer "how do you know" but cannot ask the dataset "since
when is X a member" — a deliberate limitation.
