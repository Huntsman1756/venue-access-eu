"""Normalization contract tests."""

import pytest

from venue_access.domain.normalization import (
    has_branch_marker,
    legal_form_signature,
    name_stem,
    normalize_address,
    normalize_country,
    normalize_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Banco Santander, S.A.", "BANCO SANTANDER SA"),
        ("BANCO SANTANDER SA", "BANCO SANTANDER SA"),
        ("ABN AMRO Bank N.V.", "ABN AMRO BANK NV"),
        ("ABN AMRO BANK NV", "ABN AMRO BANK NV"),
        ("Banca Akros S.p.A.", "BANCA AKROS SPA"),
        ("Foo Bar Limited", "FOO BAR LTD"),
        ("Foo Bar Ltd.", "FOO BAR LTD"),
        ("Foo Bar PLC", "FOO BAR PLC"),
        ("Müller & Co. GmbH", "MULLER CO GMBH"),
        ("  extra   spaces\t here ", "EXTRA SPACES HERE"),
        ("Société Générale", "SOCIETE GENERALE"),
        ("ALLIANZGI - S.A.", "ALLIANZGI SA"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    ("a", "b", "equal"),
    [
        ("BANK A SA", "BANK A S.A.", True),        # same legal form, spelling
        ("BANK A SA", "BANK A AG", False),          # different legal form
        ("BANK A LIMITED", "BANK A LTD", True),
        ("BANK A PLC", "BANK A LIMITED", False),   # PLC != LTD
    ],
)
def test_legal_forms_not_collapsed(a: str, b: str, equal: bool) -> None:
    na, nb = normalize_name(a), normalize_name(b)
    assert (legal_form_signature(na) == legal_form_signature(nb)) == equal


def test_stem_drops_legal_form() -> None:
    assert name_stem(normalize_name("Banco Santander, S.A.")) == "BANCO SANTANDER"
    assert name_stem(normalize_name("ABN AMRO Bank N.V.")) == "ABN AMRO BANK"


@pytest.mark.parametrize(
    "raw",
    [
        "Banco Santander S.A. London Branch",
        "Bank of China Limited Zweigniederlassung",
        "Foo Bank Sucursal en España",
    ],
)
def test_branch_markers(raw: str) -> None:
    assert has_branch_marker(normalize_name(raw))


def test_no_branch_marker() -> None:
    assert not has_branch_marker(normalize_name("Banco Santander S.A."))


def test_normalize_country() -> None:
    assert normalize_country("Netherlands") == "NL"
    assert normalize_country("United Kingdom") == "GB"
    assert normalize_country("Spain") == "ES"
    assert normalize_country("The Netherlands") == "NL"


def test_normalize_address() -> None:
    assert normalize_address("Gustav Mahlerlaan 10, 1082 PP Amsterdam") == (
        "GUSTAV MAHLERLAAN 10 1082 PP AMSTERDAM"
    )
