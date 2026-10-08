"""Source adapter protocol and resilient HTTP fetching."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from venue_access.domain.enums import ErrorCode
from venue_access.domain.models import FetchResult, ParsedSnapshot

USER_AGENT = "venue-access-eu/0.1 (+https://github.com/Huntsman1756/venue-access-eu; open-data)"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=15.0)


class SourceError(Exception):
    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FetchConfig:
    max_retries: int = 3
    backoff_seconds: float = 2.0
    min_bytes: int = 100
    extra_headers: dict[str, str] | None = None
    referer: str | None = None


def _looks_blocked(body: bytes, content_type: str) -> bool:
    head = body[:4096].lower()
    if b"cloudflare" in head and (b"challenge" in head or b"attention required" in head):
        return True
    if b"<title>access denied" in head or b"request blocked" in head:
        return True
    return b"captcha" in head


def http_fetch(urls: list[str], config: FetchConfig | None = None) -> list[FetchResult]:
    """Fetch URLs with retries/backoff. Returns one FetchResult per URL."""
    cfg = config or FetchConfig()
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if cfg.extra_headers:
        headers.update(cfg.extra_headers)
    if cfg.referer:
        headers["Referer"] = cfg.referer
    out: list[FetchResult] = []
    last_err: Exception | None = None
    with httpx.Client(headers=headers, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        for url in urls:
            result: FetchResult | None = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    resp = client.get(url)
                except httpx.HTTPError as exc:
                    last_err = exc
                    if attempt < cfg.max_retries:
                        time.sleep(cfg.backoff_seconds * (2**attempt))
                        continue
                    raise SourceError(ErrorCode.SOURCE_NETWORK_ERROR, f"{url}: {exc}") from exc
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < cfg.max_retries:
                    time.sleep(cfg.backoff_seconds * (2**attempt))
                    continue
                if resp.status_code == 403:
                    raise SourceError(ErrorCode.SOURCE_BLOCKED, f"{url}: HTTP 403")
                if resp.status_code >= 400:
                    raise SourceError(
                        ErrorCode.SOURCE_NETWORK_ERROR, f"{url}: HTTP {resp.status_code}"
                    )
                if _looks_blocked(resp.content, resp.headers.get("content-type", "")):
                    raise SourceError(ErrorCode.SOURCE_BLOCKED, f"{url}: block page detected")
                result = FetchResult(
                    url=url,
                    final_url=str(resp.url),
                    http_status=resp.status_code,
                    content_type=resp.headers.get("content-type", ""),
                    body=resp.content,
                    retrieved_at=datetime.now(UTC),
                    etag=resp.headers.get("etag"),
                    last_modified=resp.headers.get("last-modified"),
                )
                break
            if result is None:
                raise SourceError(
                    ErrorCode.SOURCE_NETWORK_ERROR, f"{url}: exhausted retries ({last_err})"
                )
            if len(result.body) < cfg.min_bytes:
                raise SourceError(
                    ErrorCode.SOURCE_EMPTY, f"{url}: {len(result.body)} bytes < {cfg.min_bytes}"
                )
            out.append(result)
    return out


class SourceAdapter(ABC):
    """fetch -> parse -> validate contract for a membership source."""

    source_id: str
    parser_version: str

    @abstractmethod
    def fetch(self, config: FetchConfig | None = None) -> list[FetchResult]:
        """Retrieve raw artifact(s). Each result becomes (part of) a snapshot."""

    @abstractmethod
    def parse(self, artifacts: list[FetchResult]) -> ParsedSnapshot:
        """Parse raw bytes into ParticipantRecords."""

    @abstractmethod
    def validate(self, parsed: ParsedSnapshot) -> list[str]:
        """Return a list of contract violations (empty = pass)."""


def artifact_path(root: Path, source_id: str, retrieved_at: datetime, name: str) -> Path:
    return root / "raw" / source_id / retrieved_at.strftime("%Y-%m-%d") / name
