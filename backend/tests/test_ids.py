"""LEI checksum + MIC validation tests."""

import pytest

from venue_access.domain.ids import (
    is_lei_format,
    is_valid_mic,
    lei_checksum_ok,
    normalize_lei,
    normalize_mic,
)


@pytest.mark.parametrize(
    "lei",
    [
        "5493006QMFDDMYWIAM13",  # Banco Santander
        "K8MS7FD7N5Z2WQ51AZ71",  # BBVA
        "BFXS5XCH7N0Y05NIXW11",  # ABN AMRO Bank
        "G8ZTNESVNKW4NN761W05",  # ABN AMRO Clearing
        "213800D1EI4B9WTWWD28",  # LSE plc
        "969500HMVSZ0TCV65D58",  # Euronext Paris
    ],
)
def test_valid_lei(lei: str) -> None:
    assert lei_checksum_ok(lei)
    assert normalize_lei(lei.lower()) == lei


@pytest.mark.parametrize(
    "lei",
    [
        "5493006QMFDDMYWIAM14",  # wrong check digit
        "K8MS7FD7N5Z2WQ51AZ7",  # too short
        "5493006QMFDDMYWIAM13X",  # too long
        "I8MS7FD7N5Z2WQ51AZ70",  # I not allowed? (checksum fails anyway)
        "",
        "XXXXXXXXXXXXXXXXXXXX",
    ],
)
def test_invalid_lei(lei: str) -> None:
    assert not lei_checksum_ok(lei)
    assert normalize_lei(lei) is None


def test_lei_format() -> None:
    assert is_lei_format("5493006QMFDDMYWIAM13")
    assert not is_lei_format("5493006QMFDDMYWIAM1!")


@pytest.mark.parametrize(
    ("mic", "ok"),
    [
        ("XETR", True),
        ("XPAR", True),
        ("xlon", False),
        ("XLO", False),
        ("XLONG", False),
        ("X1TR", True),
        ("", False),
        (None, False),
    ],
)
def test_mic(mic: str | None, ok: bool) -> None:
    assert is_valid_mic(mic) == ok


@pytest.mark.parametrize(
    ("mic", "expected"),
    [
        ("xlon", "XLON"),
        ("XETR", "XETR"),
        ("XLO", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_mic(mic: str | None, expected: str | None) -> None:
    assert normalize_mic(mic) == expected
