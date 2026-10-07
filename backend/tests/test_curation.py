"""Validate the manual-override curation file in CI."""

from pathlib import Path

import pytest
import yaml

from venue_access.domain.ids import lei_checksum_ok

CUR = Path(__file__).parent.parent.parent / "data" / "curation" / "entity_overrides.yml"


def test_overrides_file_valid() -> None:
    if not CUR.exists():
        pytest.skip("no curation file")
    raw = yaml.safe_load(CUR.read_text(encoding="utf-8")) or {}
    for i, ov in enumerate(raw.get("overrides", [])):
        assert ov.get("source"), f"override {i}: missing source"
        assert ov.get("lei"), f"override {i}: missing lei"
        assert lei_checksum_ok(ov["lei"]), f"override {i}: bad LEI checksum"
        assert ov.get("reason"), f"override {i}: missing reason"
        assert ov.get("reviewed_at"), f"override {i}: missing reviewed_at"
        assert ov.get("source_participant_key") or ov.get("name_contains"), (
            f"override {i}: needs key or name_contains"
        )
