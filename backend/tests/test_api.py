"""API contract tests over a small real database."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from venue_access.api.app import app
from venue_access.domain.enums import SnapshotStatus
from venue_access.domain.models import ParticipantRecord, SegmentRecord
from venue_access.ingest import _persist_without_resolution, load_catalog
from venue_access.storage.store import Store


def _rec(key: str, name: str, mic: str, code: str) -> ParticipantRecord:
    return ParticipantRecord(
        source_participant_key=key,
        raw_name=name,
        normalized_name=name,
        segments=[
            SegmentRecord(source_market_code=mic, mic=mic, market_family="Cash", member_code=code)
        ],
    )


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "api.duckdb"
    store = Store(db)
    for s in load_catalog().values():
        store.upsert_source(s)
    d = datetime(2026, 10, 7, tzinfo=UTC)
    snap = f"xetra-participants:{d.strftime('%Y%m%dT%H%M%S')}"
    store.insert_snapshot(
        {
            "snapshot_id": snap,
            "source_id": "xetra-participants",
            "retrieved_at": d,
            "snapshot_status": SnapshotStatus.VALIDATED.value,
        }
    )
    _persist_without_resolution(
        store, "xetra-participants", snap, [_rec("memberid:A", "FIRM A", "XETR", "C1")]
    )
    store.close()
    monkeypatch.setattr("venue_access.api.app.DB_PATH", db)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_health_ready(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/ready").json()["ready"] is True


def test_search_and_firm(client: TestClient) -> None:
    r = client.get("/search?q=FIRM")
    assert r.status_code == 200
    firms = r.json()["firms"]
    assert firms and firms[0]["canonical_name"] == "FIRM A"
    pid = firms[0]["participant_id"]
    m = client.get(f"/participants/{pid}/memberships")
    assert m.status_code == 200
    assert m.json()["observed"][0]["mic"] == "XETR"


def test_meta_semantics_header(client: TestClient) -> None:
    r = client.get("/meta")
    assert r.headers["X-Dataset-Semantics"] == "observed-membership"
    assert "does not prove" in r.json()["semantics"]


def test_sources(client: TestClient) -> None:
    rows = client.get("/sources").json()
    assert any(r["source_id"] == "xetra-participants" for r in rows)
