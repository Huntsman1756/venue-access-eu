"""BME Equity Members adapter.

Structured endpoint (AEM GraphQL persisted query):
    https://www.bolsasymercados.es/graphql/execute.json/bme/membersListEquityList_persisted

Discovered from the member-list-equity component of
/en/bme-exchange/trading/participants/equities.html.

Fields per item: name, streetAddress, postalCode, city, phone, website, code,
isLatinAmerican, markets[] (website:bme/markets/* tags), isLiquidityProvider,
isLatibexSpecialist. No LEI.
"""

import json

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
from venue_access.sources.base import FetchConfig, SourceAdapter, SourceError, http_fetch
from venue_access.domain.enums import ErrorCode
from venue_access.sources.market_map import bme_market

API_URL = (
    "https://www.bolsasymercados.es/graphql/execute.json/bme/"
    "membersListEquityList_persisted"
)
MIN_PLAUSIBLE_ROWS = 40


class BmeAdapter(SourceAdapter):
    source_id = "bme-equity-members"
    parser_version = "bme-graphql-1.0.0"

    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        cfg = config or FetchConfig(min_bytes=2000)
        return http_fetch([API_URL], cfg)

    def parse(self, artifacts: list[FetchResult]) -> ParsedSnapshot:
        errors: list[str] = []
        try:
            payload = json.loads(artifacts[0].body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceError(ErrorCode.PARSE_ERROR, f"BME JSON undecodable: {exc}") from exc
        items = (
            payload.get("data", {}).get("membersListEquityList", {}).get("items") or []
        )
        records: list[ParticipantRecord] = []
        for item in items:
            name = (item.get("name") or "").strip()
            code = (item.get("code") or "").strip()
            if not name:
                errors.append(f"item missing name: {item.get('_path')}")
                continue
            address = " ".join(
                p
                for p in [
                    (item.get("streetAddress") or "").strip(),
                    (item.get("postalCode") or "").strip(),
                    (item.get("city") or "").strip(),
                ]
                if p
            )
            segments: list[SegmentRecord] = []
            for tag in item.get("markets") or []:
                mm = bme_market(tag)
                if mm is None:
                    errors.append(f"unmapped market tag {tag!r} on {name!r}")
                    continue
                segments.append(
                    SegmentRecord(
                        source_market_code=tag,
                        mic=mm.mic,
                        market_family=mm.family,
                        member_code=code or None,
                    )
                )
            key = f"code:{code}" if code else f"name:{name}"
            records.append(
                ParticipantRecord(
                    source_participant_key=key,
                    raw_name=name,
                    normalized_name=normalize_name(name),
                    raw_address=address or None,
                    normalized_address=normalize_address(address),
                    raw_country="Spain",
                    country="ES",
                    membership_type_raw="Equity Member",
                    membership_type_normalized="equity_member",
                    source_record_id=item.get("_path"),
                    segments=segments,
                    extras={
                        k: v
                        for k, v in {
                            "is_liquidity_provider": str(item.get("isLiquidityProvider")),
                            "is_latibex_specialist": str(item.get("isLatibexSpecialist")),
                            "is_latin_american": str(item.get("isLatinAmerican")),
                            "website": item.get("website") or "",
                        }.items()
                        if v
                    },
                )
            )
        return ParsedSnapshot(
            records=records, parse_errors=errors, schema_signature="bme-graphql-v1"
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
        if parsed.records and no_seg / len(parsed.records) > 0.2:
            violations.append(
                f"VALIDATION_ERROR: {no_seg}/{len(parsed.records)} rows with no market"
            )
        return violations
