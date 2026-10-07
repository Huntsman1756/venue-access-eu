# ADR 004 — Raw snapshot policy: local artifacts, public hashes

## Status
Accepted (v0.1)

## Context
Venue directories are © their operators. Republishing raw downloads in git
or releases is legally risky; deleting them would destroy provenance.

## Decision
- Raw artifacts live under data/raw/ (gitignored, local or object storage).
- Releases publish *derived normalized facts* + snapshot metadata:
  URL, retrieved_at, HTTP status, content-type, byte count, SHA-256.
- Every normalized row carries source_record_hash + snapshot_id so a claim
  can be verified against a privately held artifact or a fresh re-fetch.

## Consequences
+ Provenance without redistribution; claims remain independently checkable.
- Consumers cannot diff raw bytes without re-fetching the source themselves.
