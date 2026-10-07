"""ISO 10383 MIC registry adapter (reference data, not membership).

Official artifact (Registration Authority: SWIFT):
    https://www.iso20022.org/sites/default/files/ISO10383_MIC/ISO10383_MIC.csv

Parsed into VenueRecord rows preserving operating/segment hierarchy.
"""

import csv
import io
from datetime import date

from pydantic import BaseModel

from venue_access.domain.ids import normalize_lei, normalize_mic
from venue_access.domain.models import FetchResult
from venue_access.sources.base import FetchConfig, http_fetch

CSV_URL = "https://www.iso20022.org/sites/default/files/ISO10383_MIC/ISO10383_MIC.csv"

EXPECTED_COLUMNS = [
    "MIC",
    "OPERATING MIC",
    "OPRT/SGMT",
    "MARKET NAME-INSTITUTION DESCRIPTION",
    "LEGAL ENTITY NAME",
    "LEI",
    "MARKET CATEGORY CODE",
    "ACRONYM",
    "ISO COUNTRY CODE (ISO 3166)",
    "CITY",
    "WEBSITE",
    "STATUS",
    "CREATION DATE",
    "LAST UPDATE DATE",
    "LAST VALIDATION DATE",
    "EXPIRY DATE",
    "COMMENTS",
]


class VenueRecord(BaseModel):
    mic: str
    operating_mic: str
    mic_type: str  # OPRT | SGMT
    market_name: str
    legal_entity_name: str | None = None
    operator_lei: str | None = None
    market_category: str | None = None
    acronym: str | None = None
    country: str | None = None
    city: str | None = None
    website: str | None = None
    status: str
    creation_date: date | None = None
    last_update_date: date | None = None
    last_validation_date: date | None = None
    expiry_date: date | None = None
    comments: str | None = None


def _d(v: str) -> date | None:
    v = v.strip()
    if len(v) == 8 and v.isdigit():
        return date(int(v[:4]), int(v[4:6]), int(v[6:8]))
    return None


def parse_mic_csv(body: bytes) -> list[VenueRecord]:
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"MIC CSV missing columns: {missing}")
    out: list[VenueRecord] = []
    for row in reader:
        mic = normalize_mic(row.get("MIC"))
        if mic is None:
            continue
        out.append(
            VenueRecord(
                mic=mic,
                operating_mic=normalize_mic(row.get("OPERATING MIC")) or mic,
                mic_type=(row.get("OPRT/SGMT") or "").strip().upper() or "OPRT",
                market_name=(row.get("MARKET NAME-INSTITUTION DESCRIPTION") or "").strip(),
                legal_entity_name=(row.get("LEGAL ENTITY NAME") or "").strip() or None,
                operator_lei=normalize_lei(row.get("LEI")),
                market_category=(row.get("MARKET CATEGORY CODE") or "").strip() or None,
                acronym=(row.get("ACRONYM") or "").strip() or None,
                country=(row.get("ISO COUNTRY CODE (ISO 3166)") or "").strip() or None,
                city=(row.get("CITY") or "").strip() or None,
                website=(row.get("WEBSITE") or "").strip() or None,
                status=(row.get("STATUS") or "").strip().upper(),
                creation_date=_d(row.get("CREATION DATE") or ""),
                last_update_date=_d(row.get("LAST UPDATE DATE") or ""),
                last_validation_date=_d(row.get("LAST VALIDATION DATE") or ""),
                expiry_date=_d(row.get("EXPIRY DATE") or ""),
                comments=(row.get("COMMENTS") or "").strip() or None,
            )
        )
    return out


class Iso10383Adapter:
    source_id = "iso-10383-mic"
    parser_version = "iso10383-csv-1.0.0"

    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        cfg = config or FetchConfig(min_bytes=100_000)
        return http_fetch([CSV_URL], cfg)
