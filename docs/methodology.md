# Methodology

See also: web app `/methodology`, ADRs in `docs/adr/`.

## Semantic contract

> Public evidence of observed European trading-venue membership.

Not: a complete database of every way a firm can access a European market.

## Evidence states

| State | Meaning |
|---|---|
| OBSERVED | Positive listing in a captured, successfully processed official source |
| NOT_OBSERVED | No match in a good snapshot whose documented scope covers the question and whose source allows absence inference |
| UNKNOWN | Source partial/failed/quarantined, venue not covered, or identity unresolved |

Every NOT_OBSERVED answer carries the source that produced it. UNKNOWN
carries the reason.

## Pipeline

1. **fetch** — official machine-readable artifacts only; identifiable UA,
   timeouts, bounded retries, no bypass of access controls.
2. **snapshot** — immutable record: URL, status, content-type, bytes,
   SHA-256 (bundle hash for multi-artifact sources), retrieved_at.
3. **parse** — adapter-specific parser; `source_schema_signature` recorded;
   contract tests enforce minimum plausible structure.
4. **gate** — anomaly detection vs latest good snapshot; QUARANTINED
   snapshots never produce absence events.
5. **normalize** — names/addresses normalized alongside verbatim raw fields;
   legal-form spellings canonicalized but never collapsed.
6. **resolve** — deterministic GLEIF pipeline; fuzzy matches create review
   candidates only; manual overrides are versioned YAML with evidence.
7. **persist** — participants (`lei:`/`unresolved:` ids), aliases,
   observations, segment observations, identity_resolution audit rows.
8. **derive** — intervals + change events recomputed from all good
   snapshots; publish exports + manifest + quality report.

## Reparse test

When a parser changes, re-run it against the previous raw snapshot. If
T-1 counts collapse under the new parser, the regression is ours; if they
match but the new snapshot differs, the change is upstream. Snapshots keep
both `parser_version` and `source_schema_signature` to make this checkable.

## Identity resolution statuses

`EXACT_SOURCE_LEI` → `EXACT_LEGAL_NAME` / `EXACT_NAME_COUNTRY` /
`NAME_ADDRESS_MATCH` → `MANUAL` → `FUZZY_CANDIDATE` → `CONFLICT` →
`UNRESOLVED`. Candidates are persisted for audit.
