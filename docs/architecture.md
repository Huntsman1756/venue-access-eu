# Architecture

```mermaid
flowchart LR
    subgraph Sources
        X[Xetra CSV] --> F
        E[Euronext CSV] --> F
        B[BME GraphQL] --> F
        L[LSE directory API] --> F
        M[ISO 10383 CSV] --> F
    end
    F[fetch: immutable raw snapshots<br/>sha256, retrieved_at] --> P[parse: ParticipantRecord<br/>schema signature]
    P --> G[anomaly gate<br/>counts, drops, contract]
    G -->|fail| Q[QUARANTINED<br/>forensics only]
    G -->|pass| N[normalize names/addresses]
    N --> R[identity resolution<br/>GLEIF, deterministic]
    R --> S[(DuckDB<br/>observations)]
    S --> T[temporal engine<br/>intervals + change events]
    T --> X1[Parquet + CSV + manifest]
    T --> D[(published duckdb)]
    D --> A[FastAPI /api/v1]
    A --> W[Next.js frontend]
    S --> C[venue-access CLI]
```

## Data model

```mermaid
erDiagram
    source ||--o{ snapshot : captures
    snapshot ||--o{ membership_observation : contains
    participant ||--o{ membership_observation : observed_in
    membership_observation ||--o{ membership_segment_observation : detail
    participant ||--o{ participant_alias : names
    venue ||--o{ membership_segment_observation : mic
    participant ||--o{ entity_relationship : child
```

- `snapshot` — immutable capture metadata (raw_sha256, parser_version, status)
- `participant` — resolved entity keyed `lei:{LEI}` or `unresolved:{src}:{key}`
- `participant_alias` — every raw name/address per source, preserved verbatim
- `membership_observation` — presence of a participant in a snapshot
- `membership_segment_observation` — per-market/family/member-code detail
- `membership_interval` + `change_event` — derived, recomputed deterministically
- `venue` — ISO 10383 dimension (operating/segment MIC hierarchy)
- `entity_relationship` — GLEIF Level-2 relationships only (authoritative)
- `identity_resolution` — full audit trail incl. rejected candidates
- `gleif_entity` — cached GLEIF evidence for resolved LEIs
