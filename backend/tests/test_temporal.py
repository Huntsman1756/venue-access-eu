"""Temporal engine tests: appearance, absence, quarantine, reappearance."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from venue_access.domain.enums import IntervalStatus, SnapshotStatus
from venue_access.domain.models import ParticipantRecord, SegmentRecord
from venue_access.history.temporal import recompute_history
from venue_access.ingest import _persist_without_resolution
from venue_access.storage.store import Store


def make_store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "t.duckdb")
    from venue_access.ingest import load_catalog

    for s in load_catalog().values():
        store.upsert_source(s)
    return store


def snap(
    store: Store, source_id: str, day: datetime, status: str = SnapshotStatus.VALIDATED.value
) -> str:
    sid = f"{source_id}:{day.strftime('%Y%m%dT%H%M%S')}"
    store.insert_snapshot(
        {
            "snapshot_id": sid,
            "source_id": source_id,
            "retrieved_at": day,
            "snapshot_status": status,
            "record_count": 0,
            "segment_count": 0,
        }
    )
    return sid


def rec(
    key: str, name: str, mic: str = "XETR", code: str = "CODE1", family: str = "Cash"
) -> ParticipantRecord:
    return ParticipantRecord(
        source_participant_key=key,
        raw_name=name,
        normalized_name=name,
        segments=[
            SegmentRecord(source_market_code=mic, mic=mic, market_family=family, member_code=code)
        ],
    )


D0 = datetime(2026, 10, 1, tzinfo=UTC)
D1 = D0 + timedelta(days=7)
D2 = D0 + timedelta(days=14)
D3 = D0 + timedelta(days=21)


def test_present_present_absent_present(tmp_path: Path) -> None:
    """temporary absence -> POSSIBLY_DISAPPEARED then REAPPEARED, never confirmed."""
    store = make_store(tmp_path)
    r = rec("memberid:AA", "FIRM A")
    s0, s1, s2, s3 = (snap(store, "xetra-participants", d) for d in (D0, D1, D2, D3))
    _persist_without_resolution(store, "xetra-participants", s0, [r])
    _persist_without_resolution(store, "xetra-participants", s1, [r])
    _persist_without_resolution(store, "xetra-participants", s2, [])
    _persist_without_resolution(store, "xetra-participants", s3, [r])
    recompute_history(store, confirm_absences=2)
    rows = store.query("SELECT * FROM membership_interval")
    assert len(rows) == 1
    assert rows[0]["status"] == IntervalStatus.REAPPEARED.value
    types = [
        e["change_type"] for e in store.query("SELECT * FROM change_event ORDER BY observed_at")
    ]
    assert types == ["BASELINE_OBSERVED", "POSSIBLY_DISAPPEARED", "REAPPEARED"]


def test_two_consecutive_absences_confirmed(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    r = rec("memberid:AA", "FIRM A")
    s0, s1, s2, s3 = (snap(store, "xetra-participants", d) for d in (D0, D1, D2, D3))
    _persist_without_resolution(store, "xetra-participants", s0, [r])
    _persist_without_resolution(store, "xetra-participants", s1, [r])
    _persist_without_resolution(store, "xetra-participants", s2, [])
    _persist_without_resolution(store, "xetra-participants", s3, [])
    recompute_history(store)
    row = store.query("SELECT * FROM membership_interval")[0]
    assert row["status"] == IntervalStatus.DISAPPEARED.value
    types = [
        e["change_type"] for e in store.query("SELECT * FROM change_event ORDER BY observed_at")
    ]
    assert "CONFIRMED_DISAPPEARED" in types


def test_quarantined_snapshot_creates_no_absence(tmp_path: Path) -> None:
    """A malformed/quarantined snapshot must not generate disappearance events."""
    store = make_store(tmp_path)
    r = rec("memberid:AA", "FIRM A")
    s0 = snap(store, "xetra-participants", D0)
    _persist_without_resolution(store, "xetra-participants", s0, [r])
    bad = snap(store, "xetra-participants", D1, status=SnapshotStatus.QUARANTINED.value)
    _persist_without_resolution(store, "xetra-participants", bad, [])
    s2 = snap(store, "xetra-participants", D2)
    _persist_without_resolution(store, "xetra-participants", s2, [r])
    recompute_history(store)
    row = store.query("SELECT * FROM membership_interval")[0]
    assert row["status"] == IntervalStatus.CURRENT.value
    assert not store.query("SELECT * FROM change_event WHERE change_type LIKE '%DISAPPEARED%'")


def test_member_code_change_event(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    s0, s1 = snap(store, "xetra-participants", D0), snap(store, "xetra-participants", D1)
    _persist_without_resolution(
        store, "xetra-participants", s0, [rec("memberid:AA", "FIRM A", code="OLD")]
    )
    _persist_without_resolution(
        store, "xetra-participants", s1, [rec("memberid:AA", "FIRM A", code="NEW")]
    )
    recompute_history(store)
    ev = store.query("SELECT * FROM change_event WHERE change_type='MEMBER_CODE_CHANGED'")
    assert len(ev) == 1
    assert ev[0]["old_value"] == "OLD" and ev[0]["new_value"] == "NEW"


def test_first_seen_is_observational(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    s0 = snap(store, "xetra-participants", D0)
    _persist_without_resolution(store, "xetra-participants", s0, [rec("memberid:AA", "FIRM A")])
    recompute_history(store)
    row = store.query("SELECT * FROM membership_interval")[0]
    assert str(row["first_seen_at"]) == "2026-10-01"
    assert row["supporting_snapshot_count"] == 1


def test_second_snapshot_appearance_is_newly_observed(tmp_path: Path) -> None:
    """A firm absent in baseline but present in the next good snapshot is
    NEWLY_OBSERVED; baseline rows are BASELINE_OBSERVED, not 'new'."""
    store = make_store(tmp_path)
    s0, s1 = snap(store, "xetra-participants", D0), snap(store, "xetra-participants", D1)
    _persist_without_resolution(store, "xetra-participants", s0, [rec("memberid:AA", "FIRM A")])
    _persist_without_resolution(
        store,
        "xetra-participants",
        s1,
        [rec("memberid:AA", "FIRM A"), rec("memberid:BB", "FIRM B")],
    )
    recompute_history(store)
    rows = store.query(
        "SELECT source_participant_id, change_type FROM change_event ORDER BY observed_at"
    )
    assert rows[0]["change_type"] == "BASELINE_OBSERVED"
    assert rows[1]["change_type"] == "NEWLY_OBSERVED"
    assert rows[0]["source_participant_id"] != rows[1]["source_participant_id"]
    n_new = store.query("SELECT COUNT(*) c FROM change_event WHERE change_type='NEWLY_OBSERVED'")[
        0
    ]["c"]
    n_base = store.query(
        "SELECT COUNT(*) c FROM change_event WHERE change_type='BASELINE_OBSERVED'"
    )[0]["c"]
    assert n_new == 1 and n_base == 1


def test_resolution_change_never_fabricates_membership_events(tmp_path: Path) -> None:
    """THE invariant: identical source membership records between t0 and t1
    must produce zero membership change events, even if identity resolution
    flips. Resolver churn is an IDENTITY_RESOLUTION_CHANGED, not an
    appearance/disappearance."""
    store = make_store(tmp_path)
    s0, s1 = snap(store, "xetra-participants", D0), snap(store, "xetra-participants", D1)
    _persist_without_resolution(store, "xetra-participants", s0, [rec("memberid:AA", "FIRM A")])
    _persist_without_resolution(store, "xetra-participants", s1, [rec("memberid:AA", "FIRM A")])
    # identity flips between runs: unresolved -> resolved LEI (different
    # participant_id, same source participant)
    sp = "sp:xetra-participants:memberid:AA"
    store.con.execute(
        """INSERT INTO identity_resolution
           (source_participant_id, resolution_run_id, participant_id, source_id,
            source_participant_key, status, resolved_at)
           VALUES (?, 'run0', ?, 'xetra-participants', 'memberid:AA',
                   'UNRESOLVED', ?)""",
        [sp, "unresolved:xetra-participants:memberid:AA", D0],
    )
    store.con.execute(
        """INSERT INTO identity_resolution
           (source_participant_id, resolution_run_id, participant_id, source_id,
            source_participant_key, status, lei, resolved_at)
           VALUES (?, 'run1', 'lei:TESTLEI', 'xetra-participants', 'memberid:AA',
                   'EXACT_SOURCE_LEI', 'TESTLEI', ?)""",
        [sp, D1],
    )
    recompute_history(store)
    memb = store.query(
        "SELECT change_type FROM change_event WHERE change_type <> 'IDENTITY_RESOLUTION_CHANGED'"
    )
    # baseline only — zero real membership changes at t1
    assert {r["change_type"] for r in memb} == {"BASELINE_OBSERVED"}
    ident = store.query(
        "SELECT * FROM change_event WHERE change_type='IDENTITY_RESOLUTION_CHANGED'"
    )
    assert len(ident) == 1
    # interval continuity: single CURRENT interval, uninterrupted
    rows = store.query("SELECT * FROM membership_interval")
    assert len(rows) == 1 and rows[0]["status"] == "CURRENT"
    assert str(rows[0]["first_seen_at"]) == "2026-10-01"
    assert str(rows[0]["last_seen_at"]) == "2026-10-08"


class _NullGleif:
    def get_lei(self, lei: str) -> None:
        return None


class _ScriptedResolver:
    """Deterministic resolver: per-(source,key) sequence of results."""

    gleif = _NullGleif()

    def __init__(self, script: dict[tuple[str, str], list]) -> None:
        self.script = script
        self.calls: dict[tuple[str, str], int] = {}

    def resolve(self, source_id: str, rec: ParticipantRecord):

        key = (source_id, rec.source_participant_key)
        idx = self.calls.get(key, 0)
        self.calls[key] = idx + 1
        return self.script[key][min(idx, len(self.script[key]) - 1)]


def _normalized_dump(store: Store) -> dict[str, list[tuple]]:
    """Deterministic content hash of the relevant tables, minus volatile
    fields (timestamps, run ids)."""

    def rows(q: str) -> list[tuple]:
        return [tuple(r) for r in store.con.execute(q).fetchall()]

    return {
        "source_participant": rows(
            "SELECT source_participant_id, source_id, source_participant_key,"
            " raw_name, source_lei FROM source_participant ORDER BY 1"
        ),
        "latest_identity": rows(
            """SELECT source_participant_id, participant_id, status, lei
               FROM identity_resolution
               QUALIFY ROW_NUMBER() OVER
                 (PARTITION BY source_participant_id
                  ORDER BY resolved_at DESC, resolution_run_id DESC) = 1
               ORDER BY 1"""
        ),
        "participant": rows(
            """SELECT participant_id, canonical_name, country, lei,
                      candidate_lei, identity_status
               FROM participant ORDER BY 1"""
        ),
        "interval": rows(
            "SELECT source_participant_id, mic, market_family, member_code,"
            " first_seen_at, last_seen_at, first_absent_at, status,"
            " supporting_snapshot_count FROM membership_interval ORDER BY 1,2"
        ),
        "membership_events": rows(
            """SELECT source_participant_id, membership_key, change_type,
                      old_value, new_value
               FROM change_event
               WHERE change_type <> 'IDENTITY_RESOLUTION_CHANGED'
               ORDER BY 1,2,3"""
        ),
        "identity_events": rows(
            """SELECT source_participant_id, old_value, new_value
               FROM change_event
               WHERE change_type = 'IDENTITY_RESOLUTION_CHANGED'
               ORDER BY 1,2"""
        ),
    }


def test_identity_full_rebuild_equals_incremental_replay(tmp_path: Path) -> None:
    """Path-independence: replaying the same ingest sequence on a fresh DB
    must produce the same latest identity + membership state as the
    incremental store. The pin's 'previous decision' input is the resolution
    trail persisted per snapshot — it is rebuilt identically on replay."""
    from venue_access.domain.enums import IdentityStatus
    from venue_access.identity.resolver import ResolutionResult
    from venue_access.ingest import _resolve_and_persist

    u = ResolutionResult(status=IdentityStatus.UNRESOLVED, method="no_candidates")
    e1 = ResolutionResult(
        status=IdentityStatus.EXACT_SOURCE_LEI, lei="LEIAAAAAAAAAAAAAAA01", method="source_lei"
    )
    e2 = ResolutionResult(
        status=IdentityStatus.EXACT_SOURCE_LEI, lei="LEIBBBBBBBBBBBBBBBB01", method="source_lei"
    )
    script = {
        ("xetra-participants", "memberid:AA"): [u, e1, u],  # resolves then 'unresolves' -> pin
        ("xetra-participants", "memberid:BB"): [e2, e2, e2],
    }
    days = [D0, D1, D2]

    def build(path: Path) -> Store:
        store = Store(path)
        from venue_access.ingest import load_catalog

        for s in load_catalog().values():
            store.upsert_source(s)
        resolver = _ScriptedResolver({k: list(v) for k, v in script.items()})
        for d in days:
            sid = snap(store, "xetra-participants", d)
            _resolve_and_persist(
                store,
                "xetra-participants",
                sid,
                [rec("memberid:AA", "FIRM A"), rec("memberid:BB", "FIRM B")],
                resolver,
            )
        recompute_history(store)
        return store

    incremental = build(tmp_path / "inc.duckdb")
    fresh_replay = build(tmp_path / "replay.duckdb")
    assert _normalized_dump(incremental) == _normalized_dump(fresh_replay)
    # pin kept AA resolved through the t2 'unresolved' run
    latest = incremental.query(
        "SELECT participant_id, status FROM identity_resolution "
        "WHERE source_participant_id='sp:xetra-participants:memberid:AA' "
        "ORDER BY resolved_at DESC LIMIT 1"
    )[0]
    assert latest["participant_id"] == "lei:LEIAAAAAAAAAAAAAAA01"


def test_same_lei_status_churn_emits_no_identity_event(tmp_path: Path) -> None:
    """Resolution-status churn with the same mapped LEI is not an identity
    change (the interpretation did not move)."""
    store = make_store(tmp_path)
    s0, s1 = snap(store, "xetra-participants", D0), snap(store, "xetra-participants", D1)
    _persist_without_resolution(store, "xetra-participants", s0, [rec("memberid:AA", "FIRM A")])
    _persist_without_resolution(store, "xetra-participants", s1, [rec("memberid:AA", "FIRM A")])
    sp = "sp:xetra-participants:memberid:AA"
    # the two snapshot rows get distinct resolved statuses but the SAME lei;
    # the extra row flips again — still same lei: no identity change
    store.con.execute(
        """UPDATE identity_resolution
           SET status='EXACT_NAME_COUNTRY', lei='LEIX', participant_id='lei:LEIX'
           WHERE resolution_run_id=?""",
        [s0],
    )
    store.con.execute(
        """UPDATE identity_resolution
           SET status='NAME_ADDRESS_MATCH', lei='LEIX', participant_id='lei:LEIX'
           WHERE resolution_run_id=?""",
        [s1],
    )
    store.con.execute(
        """INSERT INTO identity_resolution
           (source_participant_id, resolution_run_id, participant_id,
            source_id, source_participant_key, status, lei, resolved_at)
           VALUES (?,?,?, 'xetra-participants', 'memberid:AA', ?, 'LEIX', ?)""",
        [sp, "r-apply", "lei:LEIX", "EXACT_SOURCE_LEI", D1],
    )
    recompute_history(store)
    n = store.query(
        "SELECT COUNT(*) c FROM change_event WHERE change_type='IDENTITY_RESOLUTION_CHANGED'"
    )[0]["c"]
    assert n == 0
