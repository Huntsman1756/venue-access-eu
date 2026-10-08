# Data dictionary — schema v1.0.0

## source
| column | type | meaning |
|---|---|---|
| source_id | varchar PK | stable source identifier |
| operator | varchar | venue/data operator |
| source_name | varchar | human-readable directory name |
| source_url | varchar | canonical public URL |
| source_type | varchar | membership_directory \| reference_data |
| coverage_scope | varchar | COMPLETE_WITHIN_SCOPE \| PARTIAL \| UNKNOWN |
| scope_description | varchar | what the source covers, in words |
| absence_semantics_allowed | bool | may a good snapshot infer NOT_OBSERVED |
| active | bool | ingest enabled |

## snapshot
| column | type | meaning |
|---|---|---|
| snapshot_id | varchar PK | `{source_id}:{UTC timestamp}` |
| retrieved_at | timestamptz | when the artifact was fetched |
| source_declared_updated_at | varchar | update date *declared by the source* (e.g. Euronext "Updated :"), never inferred |
| http_status / content_type / final_url | | transport evidence |
| raw_sha256 | varchar | sha256 of raw bytes (bundle hash for multi-artifact snapshots) |
| raw_bytes | bigint | artifact size |
| raw_path | varchar | local path (not redistributed, ADR 004) |
| parser_version | varchar | parser that produced records |
| source_schema_signature | varchar | structural fingerprint; change = contract test event |
| record_count / membership_count / segment_count | int | counts used by the anomaly gate |
| validation_report | varchar | JSON {reasons, metrics} |
| snapshot_status | varchar | FETCHED→PARSED→VALIDATED→PUBLISHED, or QUARANTINED/REJECTED |

## participant
| column | type | meaning |
|---|---|---|
| participant_id | varchar PK | `lei:{LEI}` when resolved, else `unresolved:{source}:{key}` |
| canonical_name | varchar | GLEIF legal name when resolved, else normalized source name |
| country | varchar | ISO-3166 alpha-2 when derivable |
| lei | varchar? | resolved LEI (checksum-validated) |
| identity_status | varchar | EXACT_SOURCE_LEI / EXACT_LEGAL_NAME / EXACT_NAME_COUNTRY / NAME_ADDRESS_MATCH / OTHER_DETERMINISTIC / MANUAL / FUZZY_CANDIDATE / UNRESOLVED / CONFLICT |
| identity_method / identity_confidence | | resolver audit fields |

## participant_alias — one row per (source, source_participant_key); preserves raw_name/raw_address verbatim.

## membership_observation
| column | type | meaning |
|---|---|---|
| observation_id | varchar PK | deterministic hash of snapshot+participant+key |
| membership_present | bool | true when listed (kept for future negative rows) |
| membership_type_raw / _normalized | varchar | e.g. "Trading-Clearing Member (T)(C)" preserved + mapped |
| source_record_hash | varchar | hash of the normalized record, not of raw bytes |

## membership_segment_observation
| column | type | meaning |
|---|---|---|
| source_market_code | varchar | source token verbatim (XAMS, DAMS, firmid service, website:bme/... tag) |
| mic | varchar? | mapped canonical MIC |
| market_family | varchar? | Cash / Derivatives / Equity / MTF / Latibex |
| member_code | varchar? | exactly as published (tabs stripped) — NOT unique across anything |
| member_code_normalized | varchar? | search form: `trim` + leading zeros stripped for all-numeric codes (Euronext `00004441` → `4441`); alphanumeric codes unchanged. Raw stays authoritative |
| capacity_raw / capacity_normalized | varchar? | e.g. LSE memberid, Euronext (T)/(T)(C) |
| segment_active | bool | false = source listed participant without active segment |

## membership_interval (derived; rebuilt at publish)
first_seen_at / last_seen_at / first_absent_at / reappeared_at are
observation dates, never membership validity dates.
status: CURRENT | POSSIBLY_DISAPPEARED | DISAPPEARED | REAPPEARED.

## source_participant — stable source identity (v0.1.2)

| field | type | semantics |
|---|---|---|
| source_participant_id | `sp:{source_id}:{key}` | temporal anchor — never re-resolved |
| source_participant_key | source-native key (memberid:, firmid:, name:, code:) | stable within the source |
| source_lei | varchar? | LEI the source itself provided — evidence, not interpretation |

## identity_resolution — append-only decision trail (v0.1.2)

`(source_participant_id, resolution_run_id)` unique; `participant_id` =
resolved target (`lei:`/`unresolved:`); latest row per source participant =
current public attribution.

## change_event — BASELINE_OBSERVED / NEWLY_OBSERVED / POSSIBLY_DISAPPEARED /
CONFIRMED_DISAPPEARED / REAPPEARED / MEMBER_CODE_CHANGED /
MEMBERSHIP_TYPE_CHANGED / SEGMENT_CHANGED / IDENTITY_RESOLUTION_CHANGED.

## entity_relationship — only GLEIF Level-2 (authoritative) relationships in
v0.1: IS_DIRECTLY_CONSOLIDATED_BY, IS_ULTIMATELY_CONSOLIDATED_BY.
relationship_method ∈ authoritative | derived | manual.
