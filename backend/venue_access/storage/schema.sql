-- venue-access-eu DuckDB schema v1
-- Observational model: snapshots are immutable; *_observation tables record
-- what a source showed in a given snapshot. Derived state (intervals,
-- changes) is recomputed at publish time.

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

CREATE TABLE IF NOT EXISTS participant (
    participant_id           VARCHAR PRIMARY KEY,
    canonical_name           VARCHAR NOT NULL,
    country                  VARCHAR,
    lei                      VARCHAR,
    identity_status          VARCHAR NOT NULL,
    identity_method          VARCHAR,
    identity_confidence      DOUBLE,
    created_at               TIMESTAMPTZ NOT NULL,
    updated_at               TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS participant_alias (
    participant_id           VARCHAR NOT NULL REFERENCES participant(participant_id),
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

CREATE TABLE IF NOT EXISTS identity_resolution (
    participant_id           VARCHAR NOT NULL,
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
    PRIMARY KEY (source_id, source_participant_key)
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
    participant_id           VARCHAR NOT NULL REFERENCES participant(participant_id),
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

-- Derived at publish time; never hand-edited.
CREATE TABLE IF NOT EXISTS membership_interval (
    participant_id           VARCHAR NOT NULL,
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
    PRIMARY KEY (membership_key, participant_id)
);

CREATE TABLE IF NOT EXISTS change_event (
    change_id                VARCHAR PRIMARY KEY,
    observed_at              DATE NOT NULL,
    participant_id           VARCHAR NOT NULL,
    membership_key           VARCHAR NOT NULL,
    change_type              VARCHAR NOT NULL,
    old_value                VARCHAR,
    new_value                VARCHAR,
    source_id                VARCHAR NOT NULL,
    confidence               DOUBLE NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_mo_participant ON membership_observation(participant_id);
CREATE INDEX IF NOT EXISTS idx_mso_obs ON membership_segment_observation(observation_id);
CREATE INDEX IF NOT EXISTS idx_mso_mic ON membership_segment_observation(mic);
CREATE INDEX IF NOT EXISTS idx_mso_code ON membership_segment_observation(member_code);
CREATE INDEX IF NOT EXISTS idx_alias_name ON participant_alias(normalized_name);
CREATE INDEX IF NOT EXISTS idx_participant_lei ON participant(lei);
CREATE INDEX IF NOT EXISTS idx_interval_part ON membership_interval(participant_id);
CREATE INDEX IF NOT EXISTS idx_change_date ON change_event(observed_at);
