"""Read-side queries shared by CLI and API. All SQL is static/parametrized."""

from typing import Any

from venue_access.domain.enums import ObservationStatus, SnapshotStatus
from venue_access.storage.store import Store

GOOD = (SnapshotStatus.VALIDATED.value, SnapshotStatus.PUBLISHED.value)


def latest_good_snapshot_ids(store: Store) -> dict[str, str]:
    """source_id -> latest snapshot_id with a good status."""
    rows = store.query(
        """SELECT source_id, snapshot_id, retrieved_at FROM (
             SELECT source_id, snapshot_id, retrieved_at,
                    ROW_NUMBER() OVER (PARTITION BY source_id
                                       ORDER BY retrieved_at DESC) rn
             FROM snapshot
             WHERE snapshot_status IN ('VALIDATED','PUBLISHED')
           ) WHERE rn=1"""
    )
    return {r["source_id"]: r["snapshot_id"] for r in rows}


def covered_mics(store: Store) -> dict[str, set[str]]:
    """source_id -> MICs actually covered by its latest good snapshot."""
    snap_ids = latest_good_snapshot_ids(store)
    out: dict[str, set[str]] = {}
    for sid, snap in snap_ids.items():
        rows = store.query(
            """SELECT DISTINCT s.mic FROM membership_segment_observation s
               JOIN membership_observation o ON s.observation_id=o.observation_id
               WHERE o.snapshot_id=? AND s.mic IS NOT NULL""",
            [snap],
        )
        out[sid] = {r["mic"] for r in rows}
    return out


def source_health(store: Store) -> list[dict[str, Any]]:
    return store.query(
        """SELECT s.source_id, s.operator, s.source_name, s.coverage_scope,
                  (SELECT snapshot_id FROM snapshot WHERE source_id=s.source_id
                    ORDER BY retrieved_at DESC LIMIT 1) AS latest_snapshot,
                  (SELECT snapshot_status FROM snapshot WHERE source_id=s.source_id
                    ORDER BY retrieved_at DESC LIMIT 1) AS latest_status,
                  (SELECT retrieved_at FROM snapshot WHERE source_id=s.source_id
                    ORDER BY retrieved_at DESC LIMIT 1) AS latest_attempt_at,
                  (SELECT retrieved_at FROM snapshot WHERE source_id=s.source_id
                     AND snapshot_status IN ('VALIDATED','PUBLISHED')
                    ORDER BY retrieved_at DESC LIMIT 1) AS latest_good_at,
                  (SELECT source_declared_updated_at FROM snapshot
                    WHERE source_id=s.source_id
                     AND snapshot_status IN ('VALIDATED','PUBLISHED')
                    ORDER BY retrieved_at DESC LIMIT 1) AS declared_updated_at,
                  (SELECT record_count FROM snapshot WHERE source_id=s.source_id
                     AND snapshot_status IN ('VALIDATED','PUBLISHED')
                    ORDER BY retrieved_at DESC LIMIT 1) AS record_count
           FROM source s ORDER BY s.source_id"""
    )


def find_participant(store: Store, q: str) -> list[dict[str, Any]]:
    """Deterministic search: exact LEI > member code > MIC > name."""
    ql = q.strip()
    rows = store.query("SELECT * FROM participant WHERE UPPER(lei)=UPPER(?)", [ql])
    if rows:
        return rows
    rows = store.query(
        """SELECT DISTINCT p.* FROM participant p
           JOIN membership_observation o ON o.participant_id=p.participant_id
           JOIN membership_segment_observation s ON s.observation_id=o.observation_id
           WHERE UPPER(s.member_code)=UPPER(?)
              OR UPPER(s.member_code_normalized)=UPPER(?) LIMIT 50""",
        [ql, ql],
    )
    if rows:
        return rows
    # name / alias (prefix first, then substring)
    rows = store.query(
        """SELECT p.*, a.normalized_name AS matched_name FROM participant p
           LEFT JOIN participant_alias a ON a.participant_id=p.participant_id
           WHERE UPPER(p.canonical_name) LIKE UPPER(?) || '%'
              OR UPPER(a.normalized_name) LIKE UPPER(?) || '%'
           ORDER BY p.canonical_name LIMIT 25""",
        [ql, ql],
    )
    if rows:
        return rows
    return store.query(
        """SELECT DISTINCT p.*, a.normalized_name AS matched_name FROM participant p
           LEFT JOIN participant_alias a ON a.participant_id=p.participant_id
           WHERE UPPER(p.canonical_name) LIKE '%' || UPPER(?) || '%'
              OR UPPER(a.normalized_name) LIKE '%' || UPPER(?) || '%'
           ORDER BY p.canonical_name LIMIT 25""",
        [ql, ql],
    )


def firm_memberships(store: Store, participant_id: str) -> list[dict[str, Any]]:
    """Observed segments in the latest good snapshot per source."""
    return store.query(
        """WITH latest AS (
             SELECT source_id, MAX(retrieved_at) m FROM snapshot
             WHERE snapshot_status IN ('VALIDATED','PUBLISHED') GROUP BY source_id)
           SELECT s.mic, s.market_family, s.member_code, s.member_code_normalized,
                  s.capacity_raw,
                  o.membership_type_raw, o.membership_type_normalized,
                  sn.retrieved_at, sn.snapshot_id, sn.source_id, sn.raw_sha256,
                  sn.source_declared_updated_at, sn.parser_version
           FROM membership_segment_observation s
           JOIN membership_observation o ON s.observation_id=o.observation_id
           JOIN snapshot sn ON sn.snapshot_id=o.snapshot_id
           JOIN latest l ON l.source_id=sn.source_id AND l.m=sn.retrieved_at
           WHERE o.participant_id=? AND s.segment_active
           ORDER BY s.mic, s.market_family""",
        [participant_id],
    )


def firm_evidence(store: Store, participant_id: str) -> list[dict[str, Any]]:
    return store.query(
        """SELECT a.source_id, a.source_participant_key, a.raw_name,
                  a.normalized_name, a.raw_address, a.raw_country,
                  a.source_record_id, i.status, i.method, i.confidence,
                  i.candidate_count, i.evidence, i.resolved_at
           FROM participant_alias a
           LEFT JOIN identity_resolution i
             ON i.source_id=a.source_id
            AND i.source_participant_key=a.source_participant_key
           WHERE a.participant_id=?""",
        [participant_id],
    )


def firm_checked_venues(store: Store, participant_id: str) -> list[dict[str, Any]]:
    """OBSERVED / NOT_OBSERVED / UNKNOWN per covered venue+family."""
    observed = {(r["mic"], r["market_family"]) for r in firm_memberships(store, participant_id)}
    out = []
    for sid, _mics in covered_mics(store).items():
        fams = store.query(
            """SELECT DISTINCT s.mic, s.market_family
               FROM membership_segment_observation s
               JOIN membership_observation o ON s.observation_id=o.observation_id
               WHERE o.snapshot_id=? AND s.mic IS NOT NULL""",
            [latest_good_snapshot_ids(store)[sid]],
        )
        for f in fams:
            key = (f["mic"], f["market_family"])
            status = (
                ObservationStatus.OBSERVED.value
                if key in observed
                else ObservationStatus.NOT_OBSERVED.value
            )
            out.append(
                {
                    "source_id": sid,
                    "mic": f["mic"],
                    "market_family": f["market_family"],
                    "status": status,
                }
            )
    # sources with no good snapshot -> UNKNOWN rows
    healthy = set(latest_good_snapshot_ids(store))
    expected = {
        "xetra-participants": [("XETR", "Cash")],
        "euronext-members": [
            ("XAMS", "Cash"),
            ("XBRU", "Cash"),
            ("XDUB", "Cash"),
            ("XLIS", "Cash"),
            ("XMIL", "Cash"),
            ("XOSL", "Cash"),
            ("XPAR", "Cash"),
        ],
        "bme-equity-members": [
            ("XMAD", "Equity"),
            ("XBAR", "Equity"),
            ("XBIL", "Equity"),
            ("XVAL", "Equity"),
            ("MABX", "MTF"),
            ("XLAT", "Latibex"),
        ],
        "lse-member-directory": [("XLON", "Cash")],
    }
    for sid, pairs in expected.items():
        if sid not in healthy:
            for mic, fam in pairs:
                out.append(
                    {
                        "source_id": sid,
                        "mic": mic,
                        "market_family": fam,
                        "status": ObservationStatus.UNKNOWN.value,
                    }
                )
    return out


def venue_participants(store: Store, mic: str) -> list[dict[str, Any]]:
    return store.query(
        """WITH latest AS (
             SELECT source_id, MAX(retrieved_at) m FROM snapshot
             WHERE snapshot_status IN ('VALIDATED','PUBLISHED') GROUP BY source_id)
           SELECT DISTINCT p.participant_id, p.canonical_name, p.lei, p.country,
                  p.identity_status, s.market_family, s.member_code,
                  o.membership_type_normalized
           FROM membership_segment_observation s
           JOIN membership_observation o ON s.observation_id=o.observation_id
           JOIN participant p ON p.participant_id=o.participant_id
           JOIN snapshot sn ON sn.snapshot_id=o.snapshot_id
           JOIN latest l ON l.source_id=sn.source_id AND l.m=sn.retrieved_at
           WHERE s.mic=? AND s.segment_active
           ORDER BY p.canonical_name""",
        [mic.upper()],
    )


def overlap(store: Store, mic_a: str, mic_b: str) -> dict[str, Any]:
    pa = {r["participant_id"]: r for r in venue_participants(store, mic_a)}
    pb = {r["participant_id"]: r for r in venue_participants(store, mic_b)}
    both = sorted(set(pa) & set(pb), key=lambda p: pa[p]["canonical_name"])
    return {
        "a_only": [pa[p] for p in sorted(set(pa) - set(pb), key=lambda p: pa[p]["canonical_name"])],
        "both": [
            {**pa[p], "member_code_a": pa[p]["member_code"], "member_code_b": pb[p]["member_code"]}
            for p in both
        ],
        "b_only": [pb[p] for p in sorted(set(pb) - set(pa), key=lambda p: pb[p]["canonical_name"])],
        "counts": {"a": len(pa), "b": len(pb), "both": len(both)},
    }


def changes_since(store: Store, since: str, include_baseline: bool = False) -> list[dict[str, Any]]:
    """Change events since a date.

    BASELINE_OBSERVED (first-snapshot presence) is excluded by default: a
    baseline is an initial state, not evidence of a recent admission.
    """
    sql = """SELECT c.*, p.canonical_name, p.lei
           FROM change_event c JOIN participant p USING (participant_id)
           WHERE c.observed_at >= ?"""
    params = [since]
    if not include_baseline:
        sql += " AND c.change_type <> 'BASELINE_OBSERVED'"
    sql += " ORDER BY c.observed_at DESC"
    return store.query(sql, params)


def stats(store: Store) -> dict[str, Any]:
    def q(sql: str) -> int:
        return int(store.query(sql)[0]["c"])

    return {
        "participants": q("SELECT COUNT(*) c FROM participant"),
        "participants_with_lei": q("SELECT COUNT(*) c FROM participant WHERE lei IS NOT NULL"),
        "membership_observations": q("SELECT COUNT(*) c FROM membership_observation"),
        "segment_observations": q("SELECT COUNT(*) c FROM membership_segment_observation"),
        "venues": q("SELECT COUNT(*) c FROM venue"),
        "snapshots": q("SELECT COUNT(*) c FROM snapshot"),
        "quarantined_snapshots": q(
            "SELECT COUNT(*) c FROM snapshot WHERE snapshot_status='QUARANTINED'"
        ),
        "unresolved": q(
            "SELECT COUNT(*) c FROM participant WHERE identity_status IN ('UNRESOLVED','CONFLICT')"
        ),
    }
