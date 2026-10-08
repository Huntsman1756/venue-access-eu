"""Synthetic demo dataset: deterministic, synthetic-only, exercises history."""

import json
from pathlib import Path

from venue_access.demo import build_demo, synthetic_lei
from venue_access.domain.ids import lei_checksum_ok
from venue_access.storage.store import Store


def test_synthetic_lei_is_valid_and_marked() -> None:
    import random

    rng = random.Random(1)  # noqa: S311
    for _ in range(50):
        lei = synthetic_lei(rng)
        assert lei.startswith("DEMO00")
        assert lei_checksum_ok(lei)


def test_demo_build_covers_every_change_type(tmp_path: Path) -> None:
    result = build_demo(tmp_path / "d.duckdb", tmp_path / "pub", firms=24, weeks=6)
    assert result["history"]["events"] > 0
    store = Store(tmp_path / "d.duckdb", read_only=True)
    try:
        rows = store.query("SELECT DISTINCT change_type FROM change_event")
        kinds = {r["change_type"] for r in rows}
        assert {"BASELINE_OBSERVED", "NEWLY_OBSERVED", "MEMBER_CODE_CHANGED"} <= kinds
        assert kinds & {"POSSIBLY_DISAPPEARED", "CONFIRMED_DISAPPEARED"}
        rows = store.query("SELECT snapshot_status FROM snapshot")
        statuses = {r["snapshot_status"] for r in rows}
        assert "QUARANTINED" in statuses
        # every firm is synthetic: demo LEI prefix or no LEI at all
        leis = [r["lei"] for r in store.query("SELECT lei FROM participant WHERE lei IS NOT NULL")]
        assert leis and all(lei.startswith("DEMO00") for lei in leis)
        venues = store.query("SELECT DISTINCT market_name FROM venue")
        assert all("(demo)" in r["market_name"] for r in venues)
    finally:
        store.close()
    manifest = json.loads((tmp_path / "pub" / "manifest.json").read_text())
    assert manifest["dataset_mode"] == "demo"
