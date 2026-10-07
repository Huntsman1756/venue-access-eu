"""Deutsche Börse / Xetra Trading Participants CSV adapter.

Official artifact: .../xetra-participants/4086838!all-csv
Columns: NAME;LEI;MEMBER ID;STREET;NUMBER;ZIP CODE;CITY;COUNTRY;WEBSITE;PHONE

Key structural facts:
- one row per Member ID; the same legal entity (same LEI) may hold several
  Member IDs (e.g. ABN AMRO Bank N.V. -> DELFR + HAUFR);
- LEI is provided by the source -> EXACT_SOURCE_LEI resolution path.
"""

import csv
from hashlib import sha256
import io

from venue_access.domain.ids import normalize_lei
from venue_access.domain.models import (
    FetchResult,
    ParsedSnapshot,
    ParticipantRecord,
    SegmentRecord,
)
from venue_access.domain.normalization import (
    normalize_address,
    normalize_country,
    normalize_name,
)
from venue_access.sources.base import FetchConfig, SourceAdapter, http_fetch
from venue_access.sources.market_map import xetra_market

CSV_URL = (
    "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/"
    "admission-to-trading/xetra-participants/4086838!all-csv"
)

EXPECTED_COLUMNS = {
    "NAME", "LEI", "MEMBER ID", "STREET", "NUMBER", "ZIP CODE", "CITY",
    "COUNTRY", "WEBSITE", "PHONE",
}
MIN_PLAUSIBLE_ROWS = 50


class XetraAdapter(SourceAdapter):
    source_id = "xetra-participants"
    parser_version = "xetra-csv-1.0.0"

    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        cfg = config or FetchConfig(min_bytes=500)
        return http_fetch([CSV_URL], cfg)

    def parse(self, artifacts: list[FetchResult]) -> ParsedSnapshot:
        text = artifacts[0].body.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        sig = sha256(";".join(sorted(reader.fieldnames or [])).encode()).hexdigest()[:16]
        errors: list[str] = []
        records: list[ParticipantRecord] = []
        for i, row in enumerate(reader):
            name = (row.get("NAME") or "").strip()
            member_id = (row.get("MEMBER ID") or "").strip()
            if not name or not member_id:
                errors.append(f"row {i + 2}: missing NAME or MEMBER ID")
                continue
            address = " ".join(
                p
                for p in [
                    (row.get("STREET") or "").strip(),
                    (row.get("NUMBER") or "").strip(),
                    (row.get("ZIP CODE") or "").strip(),
                    (row.get("CITY") or "").strip(),
                ]
                if p
            )
            records.append(
                ParticipantRecord(
                    source_participant_key=f"memberid:{member_id}",
                    raw_name=name,
                    normalized_name=normalize_name(name),
                    raw_address=address or None,
                    normalized_address=normalize_address(address),
                    raw_country=(row.get("COUNTRY") or "").strip() or None,
                    country=normalize_country(row.get("COUNTRY")),
                    source_lei=normalize_lei(row.get("LEI")),
                    membership_type_raw="Trading Participant",
                    membership_type_normalized="trading_member",
                    source_record_id=member_id,
                    segments=[
                        SegmentRecord(
                            source_market_code="XETR",
                            mic=xetra_market().mic,
                            market_family=xetra_market().family,
                            member_code=member_id,
                        )
                    ],
                )
            )
        return ParsedSnapshot(records=records, parse_errors=errors, schema_signature=sig)

    def validate(self, parsed: ParsedSnapshot) -> list[str]:
        violations: list[str] = []
        if not parsed.records:
            violations.append("SOURCE_EMPTY: zero participant rows parsed")
        elif len(parsed.records) < MIN_PLAUSIBLE_ROWS:
            violations.append(
                f"SOURCE_PARTIAL: {len(parsed.records)} rows < {MIN_PLAUSIBLE_ROWS} plausible"
            )
        if parsed.parse_errors and len(parsed.parse_errors) > max(5, len(parsed.records) // 10):
            violations.append(f"PARSE_ERROR: {len(parsed.parse_errors)} row errors")
        no_lei = sum(1 for r in parsed.records if not r.source_lei)
        if parsed.records and no_lei / len(parsed.records) > 0.2:
            violations.append(f"VALIDATION_ERROR: {no_lei}/{len(parsed.records)} rows lack LEI")
        dup = len(parsed.records) - len({r.source_participant_key for r in parsed.records})
        if dup:
            violations.append(f"VALIDATION_ERROR: {dup} duplicate Member IDs")
        return violations
