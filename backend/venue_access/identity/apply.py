"""Apply entity resolution over persisted aliases and rewrite participants.

Resolution is a derived step: raw observations are immutable; participant
rows, aliases and identity_resolution records may be recomputed at any time.
"""

import json
from datetime import UTC, datetime
from typing import Any

from venue_access.domain.enums import IdentityStatus
from venue_access.domain.models import ParticipantRecord
from venue_access.domain.normalization import normalize_country
from venue_access.identity.gleif import GleifClient
from venue_access.identity.resolver import RESOLVER_VERSION, EntityResolver
from venue_access.storage.store import Store


def _participant_id(lei: str | None, source_id: str, key: str) -> str:
    return f"lei:{lei}" if lei else f"unresolved:{source_id}:{key}"


def _cache_entity(store: Store, gleif: GleifClient, lei: str) -> None:
    if store.query("SELECT lei FROM gleif_entity WHERE lei=?", [lei]):
        return
    rec = gleif.get_lei(lei)
    if rec is None:
        return
    store.con.execute(
        "INSERT INTO gleif_entity VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            lei,
            gleif.legal_name(rec),
            None,
            gleif.country(rec),
            gleif.city(rec),
            json.dumps(gleif.address_str(rec)),
            gleif.entity_status(rec),
            gleif.registration_status(rec),
            json.dumps(rec),
            datetime.now(UTC),
        ],
    )


def apply_resolution(
    store: Store, resolver: EntityResolver, source_id: str | None = None
) -> dict[str, Any]:
    """Resolve every alias; rewrites participant links. Returns counters."""
    q = "SELECT * FROM participant_alias"
    params: list[str] = []
    if source_id:
        q += " WHERE source_id=?"
        params.append(source_id)
    aliases = store.query(q, params)

    counters = {
        "resolved": 0,
        "unresolved": 0,
        "manual": 0,
        "conflict": 0,
        "candidates": 0,
        "total": len(aliases),
    }
    for a in aliases:
        # Preserve the EXACT_SOURCE_LEI path: the existing participant's LEI
        # (assigned at ingest from the source record) acts as source_lei.
        existing = store.query(
            "SELECT lei FROM participant WHERE participant_id=?",
            [a["participant_id"]],
        )
        existing_lei = existing[0]["lei"] if existing else None
        rec = ParticipantRecord(
            source_participant_key=a["source_participant_key"],
            raw_name=a["raw_name"],
            normalized_name=a["normalized_name"] or "",
            raw_address=a["raw_address"],
            normalized_address=a["normalized_address"] or "",
            raw_country=a["raw_country"],
            country=normalize_country(a["raw_country"]),
            source_lei=existing_lei,
        )
        if rec.country is None and rec.normalized_address:
            # Backfill country from address suffix for sources whose
            # addresses end with a country name (e.g. Euronext).
            from venue_access.sources.euronext import _country_from_address

            rec.country = _country_from_address(a["raw_address"])
            rec.raw_country = rec.country
        res = resolver.resolve(a["source_id"], rec)
        if res.lei:
            _cache_entity(store, resolver.gleif, res.lei)
        new_pid = _participant_id(res.lei, a["source_id"], a["source_participant_key"])
        old_pid = a["participant_id"]
        if res.status in (IdentityStatus.UNRESOLVED,):
            counters["unresolved"] += 1
        elif res.status == IdentityStatus.CONFLICT:
            counters["conflict"] += 1
        elif res.status == IdentityStatus.FUZZY_CANDIDATE:
            counters["candidates"] += 1
        else:
            counters["resolved"] += 1
            if res.manual_override:
                counters["manual"] += 1

        # A stronger existing status is never downgraded by a weaker
        # later alias (e.g. a source-provided LEI outranks a name match).
        existing = store.query(
            "SELECT identity_status FROM participant WHERE participant_id=?",
            [new_pid],
        )
        status_rank = {s.value: i for i, s in enumerate(_STATUS_PRECEDENCE)}
        keep = existing and status_rank.get(existing[0]["identity_status"], -1) > status_rank.get(
            res.status.value, -1
        )
        store.upsert_participant(
            {
                "participant_id": new_pid,
                "canonical_name": res.canonical_name or a["normalized_name"] or a["raw_name"],
                "country": res.country or a["raw_country"],
                "lei": res.lei,
                "identity_status": (existing[0]["identity_status"] if keep else res.status.value),
                "identity_method": res.method,
                "identity_confidence": res.confidence,
            }
        )
        if new_pid != old_pid:
            store.con.execute(
                "UPDATE participant_alias SET participant_id=? "
                "WHERE source_id=? AND source_participant_key=?",
                [new_pid, a["source_id"], a["source_participant_key"]],
            )
            store.con.execute(
                "UPDATE membership_observation SET participant_id=? "
                "WHERE participant_id=? AND source_participant_key=?",
                [new_pid, old_pid, a["source_participant_key"]],
            )
            store.con.execute(
                "DELETE FROM participant WHERE participant_id=? "
                "AND NOT EXISTS (SELECT 1 FROM participant_alias pa "
                "WHERE pa.participant_id=participant.participant_id)",
                [old_pid],
            )
        store.insert_identity_resolution(
            {
                "participant_id": new_pid,
                "source_id": a["source_id"],
                "source_participant_key": a["source_participant_key"],
                "status": res.status.value,
                "lei": res.lei,
                "method": res.method,
                "confidence": res.confidence,
                "candidate_count": res.candidate_count,
                "candidates_json": json.dumps(res.candidates),
                "evidence": res.evidence,
                "resolver_version": RESOLVER_VERSION,
                "manual_override": res.manual_override,
                "resolved_at": datetime.now(UTC),
            }
        )
    # GLEIF is authoritative for the legal entity: a participant's canonical
    # name/country come from the entity record, not from whichever source
    # alias was merged first (e.g. a London-branch row writing country=GB).
    store.con.execute(
        """UPDATE participant SET
               canonical_name=g.legal_name,
               country=g.country
           FROM gleif_entity g
           WHERE participant.lei = g.lei
             AND participant.lei IS NOT NULL"""
    )
    return counters


# Identity-strength precedence for the participant-level status field. A
# source-provided LEI is the strongest evidence; fuzzy and unresolved never
# overwrite an exact result.
_STATUS_PRECEDENCE = (
    IdentityStatus.UNRESOLVED,
    IdentityStatus.FUZZY_CANDIDATE,
    IdentityStatus.CONFLICT,
    IdentityStatus.OTHER_DETERMINISTIC,
    IdentityStatus.EXACT_LEGAL_NAME,
    IdentityStatus.EXACT_NAME_COUNTRY,
    IdentityStatus.NAME_ADDRESS_MATCH,
    IdentityStatus.EXACT_SOURCE_LEI,
    IdentityStatus.MANUAL,
)


def populate_relationships(store: Store, gleif: GleifClient) -> dict[str, Any]:
    """GLEIF Level-2 (RR) relationships for resolved LEIs.

    Only authoritative relationships are recorded; name similarity alone
    never creates one.
    """
    from hashlib import sha256

    from venue_access.domain.enums import RelationshipMethod, RelationshipType

    rows = store.query("SELECT DISTINCT lei, participant_id FROM participant WHERE lei IS NOT NULL")
    count = 0
    for r in rows:
        lei, pid = r["lei"], r["participant_id"]
        for rel_type, fetch in (
            (RelationshipType.IS_DIRECTLY_CONSOLIDATED_BY, gleif.direct_parent),
            (RelationshipType.IS_ULTIMATELY_CONSOLIDATED_BY, gleif.ultimate_parent),
        ):
            try:
                parent = fetch(lei)
            except Exception:
                parent = None
            if not parent:
                continue
            parent_lei = parent.get("id")
            if not parent_lei:
                continue
            rid = sha256(f"{lei}|{parent_lei}|{rel_type}".encode()).hexdigest()[:32]
            store.con.execute(
                """INSERT INTO entity_relationship VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT (relationship_id) DO NOTHING""",
                [
                    rid,
                    pid,
                    lei,
                    parent_lei,
                    rel_type.value,
                    "GLEIF-RR-API",
                    RelationshipMethod.AUTHORITATIVE.value,
                    1.0,
                    None,
                ],
            )
            count += 1
        # International branch: GLEIF exposes it via the entity's
        # headquarters/legal jurisdiction structure; v0.1 records it via the
        # direct/ultimate parent of branch LEIs only (documented limitation).
    return {"relationships": count, "leis_checked": len(rows)}
