"""Cross-table invariant tests over a built database."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from venue_access.domain.enums import SnapshotStatus
from venue_access.domain.models import ParticipantRecord, SegmentRecord
from venue_access.history.temporal import recompute_history
from venue_access.ingest import _persist_without_resolution, load_catalog
from venue_access.storage.store import Store


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "db.duckdb")
    for src in load_catalog().values():
        s.upsert_source(src)
    return s


def rec(key: str, name: str, mic: str = "XETR", code: str | None = "C1") -> ParticipantRecord:
    return ParticipantRecord(
        source_participant_key=key, raw_name=name, normalized_name=name,
        segments=[SegmentRecord(source_market_code=mic, mic=mic,
                                market_family="Cash", member_code=code)],
    )


def test_invariants(store: Store) -> None:
    d = datetime(2026, 10, 7, tzinfo=UTC)
    snap = f"xetra-participants:{d.strftime('%Y%m%dT%H%M%S')}"
    store.insert_snapshot({
        "snapshot_id": snap, "source_id": "xetra-participants",
        "retrieved_at": d, "snapshot_status": SnapshotStatus.VALIDATED.value,
    })
    _persist_without_resolution(store, "xetra-participants", snap,
                                [rec("memberid:A", "FIRM A"), rec("memberid:B", "FIRM B")])
    recompute_history(store)

    # no duplicate observation pks
    assert store.query(
        "SELECT COUNT(*)-COUNT(DISTINCT observation_id) c "
        "FROM membership_observation")[0]["c"] == 0
    # all source ids exist
    assert store.query(
        "SELECT COUNT(*) c FROM snapshot s LEFT JOIN source x ON "
        "s.source_id=x.source_id WHERE x.source_id IS NULL")[0]["c"] == 0
    # every segment mic exists in venue or is null
    store.con.execute(
        "INSERT INTO venue (mic, operating_mic, mic_type, market_name, mic_status) "
        "VALUES ('XETR','XETR','OPRT','X','ACTIVE')")
    assert store.query(
        "SELECT COUNT(*) c FROM membership_segment_observation s "
        "LEFT JOIN venue v ON s.mic=v.mic WHERE s.mic IS NOT NULL AND v.mic IS NULL"
    )[0]["c"] == 0
    # interval has a supporting snapshot
    assert store.query(
        "SELECT COUNT(*) c FROM membership_interval "
        "WHERE supporting_snapshot_count < 1")[0]["c"] == 0
