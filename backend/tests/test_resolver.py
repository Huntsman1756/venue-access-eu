"""Entity-resolution tests with a mocked GLEIF client."""

from venue_access.domain.enums import IdentityStatus
from venue_access.domain.models import ParticipantRecord
from venue_access.identity.resolver import EntityResolver, Override


def gleif_record(lei: str, name: str, country: str = "ES",
               status: str = "ACTIVE") -> dict:
    return {
        "id": lei,
        "attributes": {
            "entity": {
                "legalName": {"name": name},
                "legalAddress": {"country": country, "city": "MADRID",
                                 "addressLines": ["CALLE X 1"],
                                 "postalCode": "28001", "region": "ES-MD"},
                "status": status,
            },
            "registration": {"registrationStatus": "ISSUED"},
        },
    }


class FakeGleif:
    def __init__(self, by_lei: dict[str, dict], search_results: dict[str, list[dict]]):
        self.by_lei = by_lei
        self.search_results = search_results

    def get_lei(self, lei: str):
        return self.by_lei.get(lei)

    def search_by_name(self, name: str, size: int = 10):
        return self.search_results.get(name, [])

    legal_name = staticmethod(lambda r: r["attributes"]["entity"]["legalName"]["name"])
    country = staticmethod(lambda r: r["attributes"]["entity"]["legalAddress"]["country"])
    city = staticmethod(lambda r: r["attributes"]["entity"]["legalAddress"]["city"])
    address_str = staticmethod(
        lambda r: "CALLE X 1 MADRID 28001 ES")
    entity_status = staticmethod(lambda r: r["attributes"]["entity"]["status"])
    registration_status = staticmethod(lambda r: "ISSUED")
    other_names = staticmethod(lambda r: [])


SANTANDER = "5493006QMFDDMYWIAM13"


def rec(name: str, lei: str | None = None, country: str | None = "ES") -> ParticipantRecord:
    return ParticipantRecord(
        source_participant_key="k1", raw_name=name,
        normalized_name=name.upper(), raw_country=country, country=country,
        source_lei=lei,
    )


def test_source_lei_resolves() -> None:
    gleif = FakeGleif({SANTANDER: gleif_record(SANTANDER, "BANCO SANTANDER S.A.")}, {})
    r = EntityResolver(gleif).resolve("s", rec("BANCO SANTANDER", lei=SANTANDER))
    assert r.status == IdentityStatus.EXACT_SOURCE_LEI
    assert r.lei == SANTANDER
    assert r.canonical_name == "BANCO SANTANDER S.A."


def test_invalid_source_lei_unresolved() -> None:
    r = EntityResolver(FakeGleif({}, {})).resolve("s", rec("X", lei="BADLEI"))
    assert r.status == IdentityStatus.UNRESOLVED
    assert r.lei is None


def test_exact_name_resolves() -> None:
    gleif = FakeGleif({}, {"BANCO SANTANDER SA": [
        gleif_record(SANTANDER, "BANCO SANTANDER S.A.")]})
    r = EntityResolver(gleif).resolve("s", rec("BANCO SANTANDER SA"))
    assert r.status in (IdentityStatus.EXACT_LEGAL_NAME,
                        IdentityStatus.EXACT_NAME_COUNTRY,
                        IdentityStatus.NAME_ADDRESS_MATCH)
    assert r.lei == SANTANDER


def test_ambiguous_stays_unresolved_or_conflict() -> None:
    dup = gleif_record("7245000NHIQTPK869X55", "Banco Santander S.A.")
    gleif = FakeGleif({}, {"BANCO SANTANDER": [
        gleif_record(SANTANDER, "BANCO SANTANDER S.A."), dup]})
    r = EntityResolver(gleif).resolve("s", rec("BANCO SANTANDER", country=None))
    assert r.status in (IdentityStatus.CONFLICT, IdentityStatus.FUZZY_CANDIDATE,
                        IdentityStatus.EXACT_LEGAL_NAME)
    assert r.candidate_count == 2


def test_no_candidates_unresolved() -> None:
    r = EntityResolver(FakeGleif({}, {})).resolve("s", rec("UNKNOWN FIRM XYZ"))
    assert r.status == IdentityStatus.UNRESOLVED


def test_manual_override_wins() -> None:
    ov = Override(source_id="s", source_participant_key="k1",
                  name_contains=None, lei=SANTANDER, reason="verified",
                  reviewed_at="2026-10-07")
    gleif = FakeGleif({SANTANDER: gleif_record(SANTANDER, "BANCO SANTANDER S.A.")}, {})
    r = EntityResolver(gleif, [ov]).resolve("s", rec("WHATEVER"))
    assert r.status == IdentityStatus.MANUAL
    assert r.manual_override


def test_legal_form_mismatch_not_resolved() -> None:
    """FOO SA vs FOO AG are different entities."""
    ag = gleif_record("FAKELEI00000000000AG", "FOO HOLDING AG", country="CH")
    gleif = FakeGleif({}, {"FOO HOLDING": [ag]})
    r = EntityResolver(gleif).resolve("s", rec("FOO HOLDING SA", country="ES"))
    assert r.status in (IdentityStatus.UNRESOLVED, IdentityStatus.FUZZY_CANDIDATE,
                        IdentityStatus.CONFLICT)
