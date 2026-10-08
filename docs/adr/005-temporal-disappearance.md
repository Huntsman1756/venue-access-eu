# ADR 005 — Temporal disappearance policy

## Status
Accepted (v0.1)

## Context
A member vanishing between two captures is ambiguous: real resignation vs
parser regression vs partial response. Single absences overclaim.

## Decision
- Anomaly gate: >15% record/segment drop, >50% growth, zero rows, schema
  signature change + hard violations → QUARANTINED (no absence events).
- One good-snapshot absence → POSSIBLY_DISAPPEARED (confidence 0.5).
- Two consecutive good-snapshot absences → CONFIRMED_DISAPPEARED (0.9).
- Reappearance after absence → REAPPEARED.
- Absence events only from sources with absence_semantics_allowed = true.

## Consequences
Disappearance events lag one refresh cycle — acceptable for weekly cadence.
