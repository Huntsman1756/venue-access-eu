-- venue-access-eu DuckDB schema v2 (ADR 008)
-- Observational model: snapshots are immutable; *_observation tables record
-- what a source showed in a given snapshot. Derived state (intervals,
-- changes) is recomputed at publish time.
--
-- v0.1.2: membership temporal identity is anchored to source_participant
-- (source_id + source_participant_key), NOT to the resolved legal entity.
-- GLEIF resolution is a separate, versioned mapping layered on top — so a
-- resolver improvement can never fabricate membership history.

CREATE TABLE IF NOT EXISTS source (
    source_id                VARCHAR PRIMARY KEY,
    operator                 VARCHAR NOT NULL,
    source_name              VARCHAR NOT NULL,
    source_url               VARCHAR NOT NULL,
    source_type              VARCHAR NOT NULL,
    coverage_scope           VARCHAR NOT NULL,
    scope_description        VARCHAR,
    absence_semantics_allowed BOOLEAN NOT NULL,
    active                   BOOLEAN NOT NULL,
    notes                    VARCHAR
);

CREATE TABLE IF NOT EXISTS snapshot (
    snapshot_id              VARCHAR PRIMARY KEY,
    source_id                VARCHAR NOT NULL REFERENCES source(source_id),
    retrieved_at             TIMESTAMPTZ NOT NULL,
    source_declared_updated_at VARCHAR,
    http_status              INTEGER,
    content_type             VARCHAR,
    final_url                VARCHAR,
    raw_sha256               VARCHAR,
    raw_bytes                BIGINT,
    raw_path                 VARCHAR,
    parser_name              VARCHAR,
    parser_version           VARCHAR,
    source_schema_signature  VARCHAR,
    record_count             INTEGER,
    membership_count         INTEGER,
    segment_count            INTEGER,
    parse_error_count        INTEGER,
    unresolved_identity_count INTEGER,
    validation_report        VARCHAR,
    snapshot_status          VARCHAR NOT NULL
);

-- Stable identity within a source: "the row this source keeps publishing".
-- Membership history is attached to this, never to a resolved LEI.
CREATE TABLE IF NOT EXISTS source_participant (
    source_participant_id    VARCHAR PRIMARY KEY,   -- sp:{source_id}:{key}
    source_id                VARCHAR NOT NULL,
    source_participant_key   VARCHAR NOT NULL,
    raw_name                 VARCHAR,
    normalized_name          VARCHAR,
    raw_address              VARCHAR,
    raw_country              VARCHAR,
    source_lei               VARCHAR,   -- LEI provided by the source row itself
    first_seen_at            TIMESTAMPTZ,
    last_seen_at             TIMESTAMPTZ,
    UNIQUE (source_id, source_participant_key)
);

-- Resolved legal entity (current interpretation). lei:-prefixed rows carry a
-- verified/accepted LEI; unresolved: rows are per-source-participant buckets
-- that may carry a persisted fuzzy candidate (candidate_lei).
CREATE TABLE IF NOT EXISTS participant (
    participant_id           VARCHAR PRIMARY KEY,
    canonical_name           VARCHAR NOT NULL,
    country                  VARCHAR,
    lei                      VARCHAR,
    candidate_lei            VARCHAR,   -- top fuzzy candidate when UNRESOLVED
    candidate_confidence     DOUBLE,
    identity_status          VARCHAR NOT NULL,
    identity_method          VARCHAR,
    identity_confidence      DOUBLE,
    created_at               TIMESTAMPTZ NOT NULL,
    updated_at               TIMESTAMPTZ NOT NULL
);

-- Latest source fields as last published + current resolved attribution.
CREATE TABLE IF NOT EXISTS participant_alias (
    -- no FKs: participant attribution changes via UPDATE, which DuckDB
    -- rewrites as DELETE+INSERT and FK references would block; referential
    -- integrity is enforced by `validate` invariant checks
    source_participant_id    VARCHAR NOT NULL,
    participant_id           VARCHAR NOT NULL,
    source_id                VARCHAR NOT NULL,
    source_participant_key   VARCHAR NOT NULL,
    raw_name                 VARCHAR NOT NULL,
    normalized_name          VARCHAR,
    raw_address              VARCHAR,
    normalized_address       VARCHAR,
    raw_country              VARCHAR,
    source_record_id         VARCHAR,
    PRIMARY KEY (source_id, source_participant_key)
);

-- Append-only audit of resolution decisions. History is the point: changing
-- an interpretation creates a new row + an IDENTITY_RESOLUTION_CHANGED event,
-- never a membership event.
CREATE TABLE IF NOT EXISTS identity_resolution (
    source_participant_id    VARCHAR NOT NULL,
    resolution_run_id        VARCHAR NOT NULL,   -- snapshot_id or apply:{ts}
    participant_id           VARCHAR NOT NULL,   -- resolved target (lei:/unresolved:)
    source_id                VARCHAR NOT NULL,
    source_participant_key   VARCHAR NOT NULL,
    status                   VARCHAR NOT NULL,
    lei                      VARCHAR,
    method                   VARCHAR,
    confidence               DOUBLE,
    candidate_count          INTEGER,
    candidates_json          VARCHAR,
    evidence                 VARCHAR,
    resolver_version         VARCHAR,
    manual_override          BOOLEAN,
    resolved_at              TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (source_participant_id, resolution_run_id)
);

CREATE TABLE IF NOT EXISTS entity_relationship (
    relationship_id          VARCHAR PRIMARY KEY,
    child_participant_id     VARCHAR,
    child_lei                VARCHAR,
    parent_lei               VARCHAR,
    relationship_type        VARCHAR NOT NULL,
    relationship_source      VARCHAR,
    relationship_method      VARCHAR NOT NULL,
    confidence               DOUBLE,
    source_snapshot_id       VARCHAR
);

CREATE TABLE IF NOT EXISTS venue (
    mic                      VARCHAR PRIMARY KEY,
    operating_mic            VARCHAR NOT NULL,
    mic_type                 VARCHAR NOT NULL,
    market_name              VARCHAR NOT NULL,
    legal_entity_name        VARCHAR,
    operator_lei             VARCHAR,
    market_category          VARCHAR,
    acronym                  VARCHAR,
    country                  VARCHAR,
    city                     VARCHAR,
    website                  VARCHAR,
    mic_status               VARCHAR NOT NULL,
    creation_date            DATE,
    last_update_date         DATE,
    last_validation_date     DATE,
    expiry_date              DATE,
    comments                 VARCHAR,
    source_publication_date  VARCHAR,
    snapshot_id              VARCHAR
);

CREATE TABLE IF NOT EXISTS membership_observation (
    observation_id           VARCHAR PRIMARY KEY,
    snapshot_id              VARCHAR NOT NULL REFERENCES snapshot(snapshot_id),
    source_participant_id    VARCHAR NOT NULL REFERENCES source_participant(source_participant_id),
    source_participant_key   VARCHAR NOT NULL,
    membership_type_raw      VARCHAR,
    membership_type_normalized VARCHAR,
    membership_present       BOOLEAN NOT NULL,
    source_record_hash       VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS membership_segment_observation (
    segment_observation_id   VARCHAR PRIMARY KEY,
    -- no FK: DuckDB rewrites UPDATE as DELETE+INSERT, which would block
    -- participant rewrites during identity re-resolution; referential
    -- integrity is enforced by the `validate` invariant checks instead
    observation_id           VARCHAR NOT NULL,
    source_market_code       VARCHAR NOT NULL,
    mic                      VARCHAR,
    market_family            VARCHAR,
    segment_raw              VARCHAR,
    member_code              VARCHAR,
    member_code_normalized   VARCHAR,   -- zero-pad stripped for lookup; raw kept in member_code
    capacity_raw             VARCHAR,
    capacity_normalized      VARCHAR,
    segment_active           BOOLEAN NOT NULL
);

-- Derived at publish time; never hand-edited. Keyed by source_participant_id:
-- interval continuity survives identity-resolution changes.
CREATE TABLE IF NOT EXISTS membership_interval (
    source_participant_id    VARCHAR NOT NULL,
    source_id                VARCHAR NOT NULL,
    mic                      VARCHAR,
    market_family            VARCHAR,
    member_code              VARCHAR,
    membership_key           VARCHAR NOT NULL,
    first_seen_at            DATE,
    last_seen_at             DATE,
    first_absent_at          DATE,
    reappeared_at            DATE,
    status                   VARCHAR NOT NULL,
    supporting_snapshot_count INTEGER NOT NULL,
    PRIMARY KEY (membership_key, source_participant_id)
);

CREATE TABLE IF NOT EXISTS change_event (
    change_id                VARCHAR PRIMARY KEY,
    observed_at              DATE NOT NULL,
    source_participant_id    VARCHAR NOT NULL,
    membership_key           VARCHAR NOT NULL,
    change_type              VARCHAR NOT NULL,
    old_value                VARCHAR,
    new_value                VARCHAR,
    source_id                VARCHAR NOT NULL,
    confidence               DOUBLE NOT NULL,
    -- provenance of an identity change: RESOLUTION_RUN (resolver re-run),
    -- CURATION (manual override), MIGRATION (model/schema transition whose
    -- rows predate v0.1.2). NULL for membership events.
    origin                   VARCHAR
);

CREATE TABLE IF NOT EXISTS gleif_entity (
    lei                      VARCHAR PRIMARY KEY,
    legal_name               VARCHAR,
    legal_form               VARCHAR,
    country                  VARCHAR,
    city                     VARCHAR,
    address_json             VARCHAR,
    entity_status            VARCHAR,
    registration_status      VARCHAR,
    raw_json                 VARCHAR,
    fetched_at               TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mo_snapshot ON membership_observation(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_mo_sp ON membership_observation(source_participant_id);
CREATE INDEX IF NOT EXISTS idx_mso_obs ON membership_segment_observation(observation_id);
CREATE INDEX IF NOT EXISTS idx_mso_mic ON membership_segment_observation(mic);
CREATE INDEX IF NOT EXISTS idx_mso_code ON membership_segment_observation(member_code);
CREATE INDEX IF NOT EXISTS idx_alias_name ON participant_alias(normalized_name);
CREATE INDEX IF NOT EXISTS idx_participant_lei ON participant(lei);
CREATE INDEX IF NOT EXISTS idx_ir_sp ON identity_resolution(source_participant_id);
CREATE INDEX IF NOT EXISTS idx_ir_pid ON identity_resolution(participant_id);
CREATE INDEX IF NOT EXISTS idx_interval_sp ON membership_interval(source_participant_id);
CREATE INDEX IF NOT EXISTS idx_change_date ON change_event(observed_at);
