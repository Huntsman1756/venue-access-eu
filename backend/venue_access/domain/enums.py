"""Domain enumerations for venue-access-eu.

Semantic contract: this dataset models *observed* venue membership backed by
captured public evidence. It never claims absence of market access.
"""

from enum import StrEnum


class ObservationStatus(StrEnum):
    """Evidence state for a membership check."""

    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"


class SnapshotStatus(StrEnum):
    FETCHED = "FETCHED"
    PARSED = "PARSED"
    VALIDATED = "VALIDATED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"


class CoverageScope(StrEnum):
    """How complete a source is within its documented scope."""

    COMPLETE_WITHIN_SCOPE = "COMPLETE_WITHIN_SCOPE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class IdentityStatus(StrEnum):
    """How a participant's legal entity (LEI) was established."""

    EXACT_SOURCE_LEI = "EXACT_SOURCE_LEI"
    EXACT_LEGAL_NAME = "EXACT_LEGAL_NAME"
    EXACT_NAME_COUNTRY = "EXACT_NAME_COUNTRY"
    NAME_ADDRESS_MATCH = "NAME_ADDRESS_MATCH"
    OTHER_DETERMINISTIC = "OTHER_DETERMINISTIC"
    MANUAL = "MANUAL"
    FUZZY_CANDIDATE = "FUZZY_CANDIDATE"
    UNRESOLVED = "UNRESOLVED"
    CONFLICT = "CONFLICT"


class IntervalStatus(StrEnum):
    """Derived temporal status for a membership key."""

    CURRENT = "CURRENT"
    POSSIBLY_DISAPPEARED = "POSSIBLY_DISAPPEARED"
    DISAPPEARED = "DISAPPEARED"
    REAPPEARED = "REAPPEARED"


class ChangeType(StrEnum):
    NEWLY_OBSERVED = "NEWLY_OBSERVED"
    POSSIBLY_DISAPPEARED = "POSSIBLY_DISAPPEARED"
    CONFIRMED_DISAPPEARED = "CONFIRMED_DISAPPEARED"
    REAPPEARED = "REAPPEARED"
    MEMBER_CODE_CHANGED = "MEMBER_CODE_CHANGED"
    MEMBERSHIP_TYPE_CHANGED = "MEMBERSHIP_TYPE_CHANGED"
    SEGMENT_CHANGED = "SEGMENT_CHANGED"
    IDENTITY_RESOLUTION_CHANGED = "IDENTITY_RESOLUTION_CHANGED"


class RelationshipType(StrEnum):
    IS_INTERNATIONAL_BRANCH_OF = "IS_INTERNATIONAL_BRANCH_OF"
    IS_DIRECTLY_CONSOLIDATED_BY = "IS_DIRECTLY_CONSOLIDATED_BY"
    IS_ULTIMATELY_CONSOLIDATED_BY = "IS_ULTIMATELY_CONSOLIDATED_BY"
    INFERRED_BRANCH_OF = "INFERRED_BRANCH_OF"
    OTHER = "OTHER"


class RelationshipMethod(StrEnum):
    """Provenance of a relationship assertion."""

    AUTHORITATIVE = "authoritative"  # e.g. GLEIF Level 2 RR-CDF
    DERIVED = "derived"
    MANUAL = "manual"


class ErrorCode(StrEnum):
    SOURCE_NETWORK_ERROR = "SOURCE_NETWORK_ERROR"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    SOURCE_SCHEMA_CHANGED = "SOURCE_SCHEMA_CHANGED"
    SOURCE_EMPTY = "SOURCE_EMPTY"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    PARSE_ERROR = "PARSE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SNAPSHOT_QUARANTINED = "SNAPSHOT_QUARANTINED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    EXPORT_ERROR = "EXPORT_ERROR"
