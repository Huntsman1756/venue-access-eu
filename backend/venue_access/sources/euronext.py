"""Euronext Members List adapter.

Official artifact: https://connect2.euronext.com/membership/download/csv

Layout (semicolon CSV, BOM, quoted):
    "Memberlist - Membership Directory"
    "Updated : DD Mon YYYY"
    <blank>
    "Member name";Type;XAMS;XBRU;XDUB;XLIS;XMIL;XOSL;XPAR;
                   DAMS;DBRU;DDUB;DLIS;DMIL;DOSL;DPAR;"Address 1";"Address 2";Contact
    rows...

- X* columns carry cash-market member codes per market;
- D* columns carry derivatives member codes per market;
- member codes may contain a leading TAB and are zero-padded numbers;
- the source provides NO LEI -> entity resolution required.
"""

import csv
from hashlib import sha256
import io
import re

from venue_access.domain.models import (
    FetchResult,
    ParsedSnapshot,
    ParticipantRecord,
    SegmentRecord,
)
from venue_access.domain.normalization import (
    normalize_address,
    normalize_name,
)
from venue_access.sources.base import FetchConfig, SourceAdapter, http_fetch
from venue_access.sources.market_map import euronext_columns

CSV_URL = "https://connect2.euronext.com/membership/download/csv"
LIST_PAGE = "https://connect2.euronext.com/trade/member-list"

_UPDATED_RE = re.compile(r"Updated\s*:\s*([0-9]{1,2}\s+\w+\s+[0-9]{4})")
MIN_PLAUSIBLE_ROWS = 150

_MEMBERSHIP_TYPE_MAP = {
    "TRADING MEMBER (T)": "trading_member",
    "TRADING-CLEARING MEMBER (T)(C)": "trading_clearing_member",
    "CLEARING MEMBER (C)": "clearing_member",
    "SPONSORED PARTICIPANT": "sponsored_participant",
}


def _clean_code(value: str | None) -> str | None:
    if not value:
        return None
    v = value.replace("\t", "").strip()
    return v or None


def _normalize_type(raw: str) -> str:
    t = raw.strip().upper()
    return _MEMBERSHIP_TYPE_MAP.get(t, t.lower().replace(" ", "_"))


class EuronextAdapter(SourceAdapter):
    source_id = "euronext-members"
    parser_version = "euronext-csv-1.0.0"

    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        cfg = config or FetchConfig(min_bytes=5000, referer=LIST_PAGE)
        return http_fetch([CSV_URL], cfg)

    def parse(self, artifacts: list[FetchResult]) -> ParsedSnapshot:
        text = artifacts[0].body.decode("utf-8-sig")
        updated: str | None = None
        m = _UPDATED_RE.search(text[:2000])
        if m:
            updated = m.group(1)
        lines = io.StringIO(text)
        reader = csv.reader(lines, delimiter=";")
        header: list[str] | None = None
        records: list[ParticipantRecord] = []
        errors: list[str] = []
        mapping = euronext_columns()
        for row in reader:
            if not row or not any(c.strip() for c in row):
                continue
            if row[0].strip().strip('"') == "Member name":
                header = [c.strip().strip('"') for c in row]
                continue
            if header is None:
                continue
            row = [c.strip() for c in row]
            row += [""] * (len(header) - len(row))
            rec = dict(zip(header, row, strict=False))
            name = rec.get("Member name", "").strip()
            if not name:
                errors.append(f"row missing Member name: {rec!r}")
                continue
            mtype_raw = rec.get("Type", "").strip()
            segments: list[SegmentRecord] = []
            for col, code in rec.items():
                mm = mapping.get(col)
                if mm is None:
                    continue
                member_code = _clean_code(code)
                if member_code is None:
                    continue
                segments.append(
                    SegmentRecord(
                        source_market_code=mm.token,
                        mic=mm.mic,
                        market_family=mm.family,
                        member_code=member_code,
                        capacity_raw=mtype_raw or None,
                    )
                )
            records.append(
                ParticipantRecord(
                    source_participant_key=f"name:{name}",
                    raw_name=name,
                    normalized_name=normalize_name(name),
                    raw_address=rec.get("Address 1") or None,
                    normalized_address=normalize_address(rec.get("Address 1")),
                    raw_country=None,
                    country=None,
                    membership_type_raw=mtype_raw or None,
                    membership_type_normalized=(
                        _normalize_type(mtype_raw) if mtype_raw else None
                    ),
                    segments=segments,
                    extras={"address2": rec.get("Address 2", "")} if rec.get("Address 2") else {},
                )
            )
        sig = sha256(";".join(header or []).encode()).hexdigest()[:16]
        return ParsedSnapshot(
            source_declared_updated_at=updated,
            records=records,
            parse_errors=errors,
            schema_signature=sig,
        )

    def validate(self, parsed: ParsedSnapshot) -> list[str]:
        violations: list[str] = []
        if not parsed.records:
            violations.append("SOURCE_EMPTY: zero member rows parsed")
        elif len(parsed.records) < MIN_PLAUSIBLE_ROWS:
            violations.append(
                f"SOURCE_PARTIAL: {len(parsed.records)} rows < {MIN_PLAUSIBLE_ROWS} plausible"
            )
        no_seg = sum(1 for r in parsed.records if not r.segments)
        # "no active segment" rows are legitimate but should stay a minority.
        if parsed.records and no_seg / len(parsed.records) > 0.4:
            violations.append(
                f"VALIDATION_ERROR: {no_seg}/{len(parsed.records)} rows with no segment"
            )
        if parsed.parse_errors and len(parsed.parse_errors) > 10:
            violations.append(f"PARSE_ERROR: {len(parsed.parse_errors)} row errors")
        return violations
