"""Core record types flowing through the ingestion pipeline."""

from datetime import date, datetime
from hashlib import sha256
import json

from pydantic import BaseModel, Field

from venue_access.domain.enums import (
    CoverageScope,
    IdentityStatus,
    IntervalStatus,
    ObservationStatus,
    RelationshipMethod,
    RelationshipType,
    SnapshotStatus,
)


class SourceDefinition(BaseModel):
    """A registered public source (venue directory or reference dataset)."""

    source_id: str
    operator: str
    source_name: str
    source_url: str
    source_type: str  # membership_directory | reference_data
    coverage_scope: CoverageScope = CoverageScope.UNKNOWN
    scope_description: str = ""
    absence_semantics_allowed: bool = False
    active: bool = True
    notes: str = ""


class FetchResult(BaseModel):
    """Bytes + transport metadata captured by an adapter fetch."""

    url: str
    final_url: str
    http_status: int
    content_type: str
    body: bytes
    retrieved_at: datetime
    etag: str | None = None
    last_modified: str | None = None

    @property
    def sha256(self) -> str:
        return sha256(self.body).hexdigest()


class SegmentRecord(BaseModel):
    """One market/segment membership row inside a raw participant record."""

    source_market_code: str  # e.g. "XAMS", "DAMS", "madrid-stock-exchange"
    mic: str | None = None
    market_family: str | None = None  # Cash | Derivatives | Equity | ...
    segment_raw: str | None = None
    member_code: str | None = None
    capacity_raw: str | None = None
    segment_active: bool = True


class ParticipantRecord(BaseModel):
    """One normalized raw participant row from a source snapshot."""

    source_participant_key: str
    raw_name: str
    normalized_name: str = ""
    raw_address: str | None = None
    normalized_address: str = ""
    raw_country: str | None = None
    country: str | None = None
    source_lei: str | None = None  # LEI provided by the source, if any
    membership_type_raw: str | None = None
    membership_type_normalized: str | None = None
    source_record_id: str | None = None  # upstream id (firmid, path, ...)
    segments: list[SegmentRecord] = Field(default_factory=list)
    extras: dict[str, str] = Field(default_factory=dict)

    def record_hash(self) -> str:
        """Structural hash of the normalized record (not of raw bytes)."""
        payload = self.model_dump(exclude={"extras"}, mode="json")
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class ParsedSnapshot(BaseModel):
    """Output of an adapter parse step."""

    source_declared_updated_at: str | None = None
    records: list[ParticipantRecord] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)
    schema_signature: str = ""


class SnapshotMeta(BaseModel):
    snapshot_id: str
    source_id: str
    retrieved_at: datetime
    source_declared_updated_at: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    final_url: str | None = None
    raw_sha256: str | None = None
    raw_bytes: int | None = None
    raw_path: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    source_schema_signature: str | None = None
    record_count: int = 0
    membership_count: int = 0
    segment_count: int = 0
    parse_error_count: int = 0
    unresolved_identity_count: int = 0
    validation_report: str = ""
    snapshot_status: SnapshotStatus = SnapshotStatus.FETCHED


class IdentityResolution(BaseModel):
    """Result of matching a source participant to a GLEIF legal entity."""

    status: IdentityStatus
    lei: str | None = None
    method: str = ""
    confidence: float = 0.0
    candidate_count: int = 0
    candidates: list[str] = Field(default_factory=list)  # rejected candidate LEIs
    evidence: str = ""
    resolver_version: str = ""
    manual_override: bool = False


class Participant(BaseModel):
    participant_id: str
    canonical_name: str
    country: str | None = None
    lei: str | None = None
    identity_status: IdentityStatus = IdentityStatus.UNRESOLVED
    identity_method: str = ""
    identity_confidence: float = 0.0


class MembershipObservation(BaseModel):
    observation_id: str
    snapshot_id: str
    participant_key: str  # stable source participant key
    source_participant_key: str
    membership_type_raw: str | None = None
    membership_type_normalized: str | None = None
    membership_present: bool = True
    source_record_hash: str = ""


class MembershipInterval(BaseModel):
    participant_id: str
    membership_key: str
    first_seen_at: date | None = None
    last_seen_at: date | None = None
    first_absent_at: date | None = None
    reappeared_at: date | None = None
    status: IntervalStatus = IntervalStatus.CURRENT
    supporting_snapshot_count: int = 0


class ChangeEvent(BaseModel):
    change_id: str
    observed_at: date
    participant_id: str
    membership_key: str
    change_type: str
    old_value: str | None = None
    new_value: str | None = None
    source_id: str
    confidence: float = 1.0


class EntityRelationship(BaseModel):
    relationship_id: str
    child_participant_id: str | None = None
    child_lei: str | None = None
    parent_lei: str | None = None
    relationship_type: RelationshipType
    relationship_source: str = "GLEIF-RR"
    relationship_method: RelationshipMethod = RelationshipMethod.AUTHORITATIVE
    confidence: float = 1.0
    source_snapshot_id: str | None = None
