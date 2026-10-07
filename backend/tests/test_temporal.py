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
    rows = store.query("SELECT participant_id, change_type FROM change_event ORDER BY observed_at")
    assert rows[0]["change_type"] == "BASELINE_OBSERVED"
    assert rows[1]["change_type"] == "NEWLY_OBSERVED"
    assert rows[0]["participant_id"] != rows[1]["participant_id"]
    n_new = store.query("SELECT COUNT(*) c FROM change_event WHERE change_type='NEWLY_OBSERVED'")[
        0
    ]["c"]
    n_base = store.query(
        "SELECT COUNT(*) c FROM change_event WHERE change_type='BASELINE_OBSERVED'"
    )[0]["c"]
    assert n_new == 1 and n_base == 1
