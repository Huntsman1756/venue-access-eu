"""Parser contract tests against minimal synthetic fixtures.

Fixtures under tests/fixtures/ are SYNTHETIC by policy (publication gate):
invented names, test LEIs with valid ISO-17442 checksums and invented member
codes — same schemas as the real sources. Real-source coverage lives in the
live tests (pytest -m live), which never ship payload copies.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.conftest import load
from venue_access.domain.models import FetchResult
from venue_access.sources.bme import BmeAdapter
from venue_access.sources.euronext import EuronextAdapter
from venue_access.sources.iso10383 import parse_mic_csv
from venue_access.sources.lse import LseAdapter, _extract_firms
from venue_access.sources.xetra import XetraAdapter


def art(body: bytes, url: str = "https://x.test/") -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        http_status=200,
        content_type="text/csv",
        body=body,
        retrieved_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


# --------------------------------------------------------------- xetra


def test_xetra_parse_synthetic_fixture() -> None:
    a = XetraAdapter()
    parsed = a.parse([art(load("xetra_participants.csv"))])
    assert len(parsed.records) == 7
    # synthetic fixtures are intentionally below the plausibility band:
    # SOURCE_PARTIAL fires, nothing else does
    assert a.validate(parsed) == ["SOURCE_PARTIAL: 7 rows < 50 plausible"]
    # every record carries a source LEI
    assert all(r.source_lei for r in parsed.records)
    # every record has exactly one XETR segment with member code
    assert all(
        len(r.segments) == 1 and r.segments[0].mic == "XETR" and r.segments[0].member_code
        for r in parsed.records
    )


def test_xetra_same_lei_multiple_member_ids() -> None:
    a = XetraAdapter()
    parsed = a.parse([art(load("xetra_participants.csv"))])
    group = [r for r in parsed.records if r.source_lei == "SYNTEST000000000AA97"]
    assert len(group) == 2
    assert {r.segments[0].member_code for r in group} == {"TESTM1", "TESTM2"}


def test_xetra_contract_empty() -> None:
    a = XetraAdapter()
    parsed = a.parse([art(b'"NAME";"LEI";"MEMBER ID"\n')])
    violations = a.validate(parsed)
    assert any("SOURCE_EMPTY" in v for v in violations)


# --------------------------------------------------------------- euronext


def test_euronext_parse_synthetic_fixture() -> None:
    a = EuronextAdapter()
    parsed = a.parse([art(load("euronext_members.csv"))])
    assert parsed.source_declared_updated_at == "07 Oct 2026"
    assert len(parsed.records) == 5
    assert a.validate(parsed) == ["SOURCE_PARTIAL: 5 rows < 150 plausible"]
    # member codes cleaned of leading TAB
    codes = [s.member_code for r in parsed.records for s in r.segments]
    assert codes and all("\t" not in c and c for c in codes)


def test_euronext_cash_and_derivatives_families() -> None:
    a = EuronextAdapter()
    parsed = a.parse([art(load("euronext_members.csv"))])
    fams = {s.market_family for r in parsed.records for s in r.segments}
    assert "Cash" in fams and "Derivatives" in fams
    # SYNTHETIC BANK B carries both cash and derivatives memberships
    assert any(
        {s.market_family for s in r.segments} == {"Cash", "Derivatives"} for r in parsed.records
    )


def test_euronext_multiple_member_codes_same_entity() -> None:
    a = EuronextAdapter()
    parsed = a.parse([art(load("euronext_members.csv"))])
    # SYNTHETIC CAPITAL C carries two distinct codes on derivatives MICs
    multi = [
        r
        for r in parsed.records
        if len({s.member_code for s in r.segments}) >= 2
    ]
    assert multi


def test_euronext_no_active_segment_records_exist() -> None:
    a = EuronextAdapter()
    parsed = a.parse([art(load("euronext_members.csv"))])
    assert any(not r.segments for r in parsed.records)


def test_euronext_membership_types_preserved() -> None:
    a = EuronextAdapter()
    parsed = a.parse([art(load("euronext_members.csv"))])
    types = {r.membership_type_raw for r in parsed.records}
    assert any("Trading Member" in (t or "") for t in types)
    assert any("Trading-Clearing Member" in (t or "") for t in types)
    assert any("Sponsored Participant" in (t or "") for t in types)


# --------------------------------------------------------------- bme


def test_bme_parse_synthetic_fixture() -> None:
    a = BmeAdapter()
    parsed = a.parse([art(load("bme_members.json"))])
    assert len(parsed.records) == 3
    assert a.validate(parsed) == ["SOURCE_PARTIAL: 3 rows < 40 plausible"]
    assert all(r.country == "ES" for r in parsed.records)
    # market tokens mapped to MICs
    mics = {s.mic for r in parsed.records for s in r.segments}
    assert {"XMAD", "XBAR", "XBIL", "XVAL", "MABX", "XLAT"} & mics


def test_bme_member_code_present() -> None:
    a = BmeAdapter()
    parsed = a.parse([art(load("bme_members.json"))])
    with_code = [r for r in parsed.records if r.source_participant_key.startswith("code:")]
    assert len(with_code) == 3


# --------------------------------------------------------------- lse


def test_lse_list_extraction() -> None:
    firms = _extract_firms(load("lse_list_page0.json"))
    assert len(firms) == 3
    assert firms[0]["firmname"] == "SYNTHETIC SECURITIES LIMITED"
    assert firms[0]["firmid"] == "90001"


def test_lse_detail_parse() -> None:
    a = LseAdapter()
    detail = load("lse_firm_79.json")
    parsed = a.parse([art(detail, "https://api.x/api/gw/lse/directories/90002")])
    assert len(parsed.records) == 1
    r = parsed.records[0]
    assert r.raw_name == "SYNTHETIC CLEARING BANK N.V."
    assert r.source_lei == "SYNTEST000000000BB85"
    # deduped settlement variants: distinct member codes only
    codes = {s.member_code for s in r.segments}
    assert codes == {"TSTA", "TSTB", "TSTC", "TSTD"}
    assert all(s.mic == "XLON" for s in r.segments)


# --------------------------------------------------------------- iso10383


def test_mic_parse() -> None:
    venues = parse_mic_csv(load("iso10383_mic.csv"))
    assert len(venues) == 8
    by_mic = {v.mic: v for v in venues}
    assert by_mic["XETR"].mic_type == "OPRT"
    assert by_mic["XMAD"].operating_mic == "BMEX"
    assert by_mic["XMAD"].mic_type == "SGMT"
    assert by_mic["XLON"].status == "ACTIVE"


def test_mic_contract_missing_column() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        parse_mic_csv(b'"MIC","FOO"\n"XETR","x"\n')


# --------------------------------------------------- fixture provenance gate


_FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("fixture", sorted(p.name for p in _FIXTURE_DIR.iterdir()))
def test_fixtures_are_synthetic(fixture: str) -> None:
    """Publication-gate guard: no fixture may contain real source payloads.

    Synthetic fixtures are self-marked: every firm name/entity begins with
    SYNTHETIC/SYNTEST. A fixture without any synthetic marker likely leaks
    real source data and fails the gate."""
    body = (_FIXTURE_DIR / fixture).read_bytes()
    assert (
        b"SYNTHETIC" in body or b"SYNTEST" in body
    ), f"fixture {fixture} has no synthetic marker — real source copy suspected"
