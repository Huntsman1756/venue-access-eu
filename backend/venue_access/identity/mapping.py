"""Shared mapping helpers: participant ids and resolution stability.

Separated from ingest/apply so both can use them without a circular
dependency.
"""

from venue_access.domain.enums import IdentityStatus
from venue_access.identity.resolver import ResolutionResult
from venue_access.storage.store import Store, spid

# Statuses that yield a lei:-keyed participant. FUZZY_CANDIDATE deliberately
# does NOT: it stays an unresolved: bucket carrying a persisted candidate.
RESOLVED_STATUSES = {
    IdentityStatus.EXACT_SOURCE_LEI,
    IdentityStatus.EXACT_LEGAL_NAME,
    IdentityStatus.EXACT_NAME_COUNTRY,
    IdentityStatus.NAME_ADDRESS_MATCH,
    IdentityStatus.OTHER_DETERMINISTIC,
    IdentityStatus.MANUAL,
}

# Statuses whose lei: mapping is sticky: a later weaker result does not
# silently drop a previously accepted resolution. Contradictory evidence
# (a different resolved LEI, or the candidate set no longer containing the
# previous LEI) still moves the mapping.
STICKY_STATUSES = {
    IdentityStatus.EXACT_SOURCE_LEI.value,
    IdentityStatus.EXACT_LEGAL_NAME.value,
    IdentityStatus.EXACT_NAME_COUNTRY.value,
    IdentityStatus.NAME_ADDRESS_MATCH.value,
    IdentityStatus.MANUAL.value,
}
WEAKER_STATUSES = {
    IdentityStatus.UNRESOLVED.value,
    IdentityStatus.FUZZY_CANDIDATE.value,
    IdentityStatus.CONFLICT.value,
}


def participant_id_for(
    lei: str | None, source_id: str, key: str, status: IdentityStatus | None = None
) -> str:
    """Canonical participant id for a resolution result.

    lei: ids are minted only for statuses that authorize an authoritative
    mapping; candidate/conflict/unresolved never silently become an entity.
    """
    if lei and (status is None or status in RESOLVED_STATUSES):
        return f"lei:{lei}"
    return f"unresolved:{source_id}:{key}"


def stabilize_resolution(
    store: Store, source_id: str, key: str, res: ResolutionResult
) -> ResolutionResult:
    """Persist prior deterministic decisions absent contradictory evidence.

    If the previous resolution was an accepted lei: mapping and the new one
    is weaker (unresolved/fuzzy/conflict), the prior mapping is kept —
    unless the new candidate set actively contradicts it (the previous LEI
    absent from candidates, or a different resolved LEI)."""
    prev = store.latest_resolution(spid(source_id, key))
    if not prev or prev["status"] not in STICKY_STATUSES:
        return res
    new_status = res.status.value
    if new_status in STICKY_STATUSES:
        return res  # real (possibly contradicting) resolution wins
    if new_status in WEAKER_STATUSES:
        candidates = set(res.candidates)
        still_candidate = prev["lei"] in candidates or not res.candidates
        if res.lei and res.lei != prev["lei"] and res.status == IdentityStatus.FUZZY_CANDIDATE:
            still_candidate = res.lei == prev["lei"]
        if still_candidate:
            return ResolutionResult(
                status=IdentityStatus(prev["status"]),
                lei=prev["lei"],
                method=f"{res.method or 'unresolved'}|pinned_to_prior",
                confidence=prev["confidence"] or 0.0,
                candidate_count=res.candidate_count,
                candidates=res.candidates,
                evidence=(res.evidence or "")
                + f"| prior {prev['status']} kept (no contradictory evidence)",
                canonical_name=None,
                country=None,
            )
    return res
