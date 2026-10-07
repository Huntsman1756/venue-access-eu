"""Anomaly gate tests."""

from venue_access.domain.enums import SnapshotStatus
from venue_access.domain.models import ParsedSnapshot, ParticipantRecord, SegmentRecord
from venue_access.quality.gates import evaluate_snapshot


def recs(n: int) -> list[ParticipantRecord]:
    return [
        ParticipantRecord(
            source_participant_key=f"k{i}", raw_name=f"FIRM {i}",
            segments=[SegmentRecord(source_market_code="XETR", mic="XETR",
                                    member_code=f"C{i}")])
        for i in range(n)
    ]


def snap_meta(records: int, segments: int, sig: str = "abc") -> dict:
    return {"record_count": records, "segment_count": segments,
            "source_schema_signature": sig}


def parsed(n: int, errors: int = 0) -> ParsedSnapshot:
    return ParsedSnapshot(records=recs(n), parse_errors=[f"e{i}" for i in range(errors)],
                          schema_signature="abc")


def test_zero_records_quarantined() -> None:
    g = evaluate_snapshot(parsed(0), [], None)
    assert not g.passed
    assert g.status == SnapshotStatus.QUARANTINED


def test_mass_drop_quarantined() -> None:
    """100 -> 10 records is a parser/source failure, not 90 resignations."""
    g = evaluate_snapshot(parsed(10), [], snap_meta(100, 100))
    assert not g.passed
    assert g.status == SnapshotStatus.QUARANTINED
    assert any("record drop" in r for r in g.reasons)


def test_small_drop_passes() -> None:
    g = evaluate_snapshot(parsed(95), [], snap_meta(100, 100))
    assert g.passed


def test_growth_spike_quarantined() -> None:
    g = evaluate_snapshot(parsed(200), [], snap_meta(100, 100))
    assert not g.passed


def test_schema_signature_flagged() -> None:
    g = evaluate_snapshot(parsed(100), [], snap_meta(100, 100, sig="different"))
    assert g.metrics.get("schema_signature_changed") == 1.0


def test_validation_violation_quarantines() -> None:
    g = evaluate_snapshot(parsed(100), ["VALIDATION_ERROR: x"], snap_meta(100, 100))
    assert not g.passed


def test_first_snapshot_passes() -> None:
    g = evaluate_snapshot(parsed(100), [], None)
    assert g.passed
