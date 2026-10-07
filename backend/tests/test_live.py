"""Live source checks — run with `pytest -m live`.

Only plausibility bounds are asserted; exact counts must never be hardcoded.
"""

import pytest

from venue_access.sources.bme import BmeAdapter
from venue_access.sources.euronext import EuronextAdapter
from venue_access.sources.iso10383 import Iso10383Adapter, parse_mic_csv
from venue_access.sources.lse import LseAdapter
from venue_access.sources.xetra import XetraAdapter

pytestmark = pytest.mark.live


def test_xetra_live() -> None:
    a = XetraAdapter()
    parsed = a.parse(a.fetch())
    assert len(parsed.records) > 50
    assert not a.validate(parsed)


def test_euronext_live() -> None:
    a = EuronextAdapter()
    parsed = a.parse(a.fetch())
    assert len(parsed.records) > 150
    assert parsed.source_declared_updated_at
    assert not a.validate(parsed)


def test_bme_live() -> None:
    a = BmeAdapter()
    parsed = a.parse(a.fetch())
    assert len(parsed.records) > 30
    assert not a.validate(parsed)


def test_lse_live() -> None:
    a = LseAdapter()
    a.detail_limit = 10  # smoke: first 10 firm details only
    arts = a.fetch()
    parsed = a.parse(arts)
    assert len(parsed.records) >= 10
    assert any(r.source_lei for r in parsed.records)


def test_mic_live() -> None:
    a = Iso10383Adapter()
    venues = parse_mic_csv(a.fetch()[0].body)
    assert len(venues) > 2000
    assert any(v.mic == "XETR" for v in venues)
