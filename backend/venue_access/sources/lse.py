"""London Stock Exchange Member Firm Directory adapter.

Public CMS endpoints (discovered from the LSE SPA, no auth required):
- list:  api.londonstockexchange.com/api/v1/pages?path=member-directory
         &parameters=page%3D{N}   -> 20 firms/page inside
         components[0].content[0].value.content
- detail: api.londonstockexchange.com/api/gw/lse/directories/{firmid}
         -> leicode, codes[] (mnemonic, memberid, firmcode, crestcode,
            dtccode, euroclearbankcode), branches[], status.

The fetch phase downloads the paginated list, then one detail document per
firm (~266 requests with polite pacing). All artifacts form one snapshot
bundle: raw_sha256 is computed over sorted per-artifact hashes.
"""

import json
import time

from venue_access.domain.enums import ErrorCode
from venue_access.domain.ids import normalize_lei
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
from venue_access.sources.base import (
    FetchConfig,
    SourceAdapter,
    SourceError,
    http_fetch,
)
from venue_access.sources.market_map import lse_market

LIST_URL = "https://api.londonstockexchange.com/api/v1/pages?path=member-directory"
DETAIL_URL = "https://api.londonstockexchange.com/api/gw/lse/directories/{firmid}"
PAGE_SIZE = 20
DETAIL_DELAY_S = 0.15
MIN_PLAUSIBLE_FIRMS = 150


def _list_page_url(page: int) -> str:
    return f"{LIST_URL}&parameters=page%3D{page}"


def _extract_firms(body: bytes) -> list[dict[str, object]]:
    try:
        doc = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(ErrorCode.PARSE_ERROR, f"LSE page JSON undecodable: {exc}") from exc
    components = doc.get("components") or []
    if not components:
        return []
    for content in components[0].get("content") or []:
        if content.get("name") == "memberdirectorysearch":
            value = content.get("value") or {}
            return list(value.get("content") or [])
    return []


class LseAdapter(SourceAdapter):
    source_id = "lse-member-directory"
    parser_version = "lse-api-1.0.0"
    detail_limit: int | None = None  # test hook

    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        cfg = config or FetchConfig(min_bytes=200)
        artifacts = http_fetch([_list_page_url(0)], cfg)
        firms = _extract_firms(artifacts[0].body)
        page = 1
        while len(firms) == PAGE_SIZE:
            res = http_fetch([_list_page_url(page)], cfg)
            artifacts.extend(res)
            firms = _extract_firms(res[0].body)
            page += 1
            if page > 100:  # safety bound
                raise SourceError(ErrorCode.SOURCE_PARTIAL, "LSE pagination unbounded")
        firm_ids = self._firm_ids(artifacts)
        if self.detail_limit is not None:
            firm_ids = firm_ids[: self.detail_limit]
        for firm_id in firm_ids:
            time.sleep(DETAIL_DELAY_S)
            res = http_fetch([DETAIL_URL.format(firmid=firm_id)], cfg)
            artifacts.extend(res)
        return artifacts

    @staticmethod
    def _firm_ids(list_artifacts: list[FetchResult]) -> list[str]:
        ids: list[str] = []
        for art in list_artifacts:
            for f in _extract_firms(art.body):
                fid = str(f.get("firmid") or "").strip()
                if fid and fid not in ids:
                    ids.append(fid)
        return ids

    def parse(self, artifacts: list[FetchResult]) -> ParsedSnapshot:
        records: list[ParticipantRecord] = []
        errors: list[str] = []
        for art in artifacts:
            if "/api/v1/pages" in art.url:
                continue  # list pages only seed firm ids
            try:
                firm = json.loads(art.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append(f"{art.url}: undecodable detail JSON")
                continue
            if firm.get("firmid") is None:
                errors.append(f"{art.url}: no firmid ({firm.get('message')})")
                continue
            status = str(firm.get("status") or "")
            if status != "Active":
                # Inactive firms are kept but marked not-present.
                present = False
            else:
                present = True
            address = " ".join(
                p
                for p in [
                    str(firm.get("registeredofficeaddress") or "").strip(),
                    str(firm.get("registeredofficecity") or "").strip(),
                    str(firm.get("registeredofficezipcode") or "").strip(),
                ]
                if p
            )
            segments: list[SegmentRecord] = []
            seen_segments: set[tuple[str, str | None, str | None]] = set()
            for code in firm.get("codes") or []:
                service = str(code.get("servicename") or "cash")
                mm = lse_market(service)
                if mm is None:
                    errors.append(f"firm {firm['firmid']}: unmapped service {service!r}")
                    continue
                mnemonic = str(code.get("mnemonic") or "").strip()
                memberid = str(code.get("memberid") or "").strip()
                member_code = mnemonic or memberid or None
                dedup_key = (service, member_code, memberid or None)
                if dedup_key in seen_segments:
                    # Same member code with different settlement codes is one
                    # membership observation, not several.
                    continue
                seen_segments.add(dedup_key)
                segments.append(
                    SegmentRecord(
                        source_market_code=service,
                        mic=mm.mic,
                        market_family=mm.family,
                        member_code=member_code,
                        capacity_raw=memberid or None,
                    )
                )
            name = str(firm.get("firmname") or "").strip()
            records.append(
                ParticipantRecord(
                    source_participant_key=f"firmid:{firm['firmid']}",
                    raw_name=name,
                    normalized_name=normalize_name(name),
                    raw_address=address or None,
                    normalized_address=normalize_address(address),
                    raw_country=str(firm.get("registeredofficecountryid") or "") or None,
                    country=str(firm.get("registeredofficecountryid") or "") or None,
                    source_lei=normalize_lei(str(firm.get("leicode") or "")),
                    membership_type_raw=f"LSE member firm ({status or 'unknown'})",
                    membership_type_normalized="member_firm",
                    source_record_id=str(firm["firmid"]),
                    segments=segments,
                    extras={
                        k: v
                        for k, v in {
                            "status": status,
                            "statusdate": str(firm.get("statusdate") or ""),
                            "lastupdate": str(firm.get("lastupdate") or ""),
                            "isbroker": str(firm.get("isbroker")),
                            "ismarketmaker": str(firm.get("ismarketmaker")),
                            "isaimadviser": str(firm.get("isaimadviser")),
                        }.items()
                        if v
                    },
                )
            )
            if not present:
                records[-1].segments = []
        return ParsedSnapshot(records=records, parse_errors=errors,
                              schema_signature="lse-api-v1")

    def validate(self, parsed: ParsedSnapshot) -> list[str]:
        violations: list[str] = []
        if not parsed.records:
            violations.append("SOURCE_EMPTY: zero firm records parsed")
        elif len(parsed.records) < MIN_PLAUSIBLE_FIRMS:
            violations.append(
                f"SOURCE_PARTIAL: {len(parsed.records)} firms < {MIN_PLAUSIBLE_FIRMS} plausible"
            )
        no_lei = sum(1 for r in parsed.records if not r.source_lei)
        if parsed.records and no_lei / len(parsed.records) > 0.5:
            violations.append(f"VALIDATION_ERROR: {no_lei}/{len(parsed.records)} lack LEI")
        return violations


def bundle_sha256(artifacts: list[FetchResult]) -> str:
    """Deterministic hash over a multi-artifact snapshot bundle."""
    from hashlib import sha256

    h = sha256()
    for art in sorted(artifacts, key=lambda a: a.url):
        h.update(art.url.encode())
        h.update(art.sha256.encode())
    return h.hexdigest()
