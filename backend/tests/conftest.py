import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from venue_access.domain.models import FetchResult

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def artifact(name: str, url: str = "https://example.test/x") -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        http_status=200,
        content_type="application/octet-stream",
        body=load(name),
        retrieved_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


@pytest.fixture()
def xetra_csv() -> bytes:
    return load("xetra_participants.csv")


@pytest.fixture()
def euronext_csv() -> bytes:
    return load("euronext_members.csv")


@pytest.fixture()
def bme_json() -> bytes:
    return load("bme_members.json")


@pytest.fixture()
def lse_firm_json() -> dict:
    return json.loads(load("lse_firm_79.json"))
