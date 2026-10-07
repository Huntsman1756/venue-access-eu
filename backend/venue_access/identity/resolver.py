"""Deterministic, auditable entity resolution against GLEIF.

Pipeline per source participant:

    manual override?  -> MANUAL
    source LEI?       -> validate + GLEIF lookup -> EXACT_SOURCE_LEI
    else:
        candidates    -> exact legal-name match (normalized, legal-form aware)
                      -> country / address corroboration
                      -> strict thresholds
                      -> RESOLVED | FUZZY_CANDIDATE | UNRESOLVED | CONFLICT

Rules:
- a fuzzy match NEVER produces an authoritative resolution on its own;
- ambiguous top-scores stay UNRESOLVED with candidates recorded for review;
- rejected candidates are persisted for audit.
"""

import difflib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from venue_access.domain.enums import IdentityStatus
from venue_access.domain.ids import lei_checksum_ok
from venue_access.domain.models import ParticipantRecord
from venue_access.domain.normalization import (
    legal_form_signature,
    name_stem,
    normalize_address,
    normalize_name,
)
from venue_access.identity.gleif import GleifClient

RESOLVER_VERSION = "resolver-1.0.0"

# Thresholds — deliberately strict; misses go to review, not to auto-merge.
AUTO_NAME_MIN = 0.97  # exact normalized legal name
STEM_MIN = 0.90  # stem (without legal form) near-exact
FUZZY_CANDIDATE_MIN = 0.82  # below this: not even a candidate
CONFLICT_MARGIN = 0.06  # second candidate within this of the top -> ambiguous


@dataclass
class Override:
    source_id: str
    source_participant_key: str | None
    name_contains: str | None
    lei: str
    reason: str
    reviewed_at: str


@dataclass
class ResolutionResult:
    status: IdentityStatus
    lei: str | None = None
    method: str = ""
    confidence: float = 0.0
    candidate_count: int = 0
    candidates: list[str] = field(default_factory=list)
    evidence: str = ""
    manual_override: bool = False
    canonical_name: str | None = None  # GLEIF legal name when resolved
    country: str | None = None


def load_overrides(path: Path | None) -> list[Override]:
    if path is None or not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for item in raw.get("overrides", []):
        out.append(
            Override(
                source_id=item["source"],
                source_participant_key=item.get("source_participant_key"),
                name_contains=item.get("name_contains"),
                lei=item["lei"],
                reason=item.get("reason", ""),
                reviewed_at=str(item.get("reviewed_at", "")),
            )
        )
    return out


def _find_override(
    overrides: list[Override], source_id: str, rec: ParticipantRecord
) -> Override | None:
    for ov in overrides:
        if ov.source_id != source_id:
            continue
        if ov.source_participant_key and ov.source_participant_key == rec.source_participant_key:
            return ov
        if ov.name_contains and ov.name_contains.upper() in rec.normalized_name:
            return ov
    return None


def _name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _token_jaccard(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class EntityResolver:
    def __init__(self, gleif: GleifClient, overrides: list[Override] | None = None):
        self.gleif = gleif
        self.overrides = overrides or []

    # ------------------------------------------------------------------

    def resolve(self, source_id: str, rec: ParticipantRecord) -> ResolutionResult:
        ov = _find_override(self.overrides, source_id, rec)
        if ov:
            gleif_rec = self.gleif.get_lei(ov.lei)
            name = self.gleif.legal_name(gleif_rec) if gleif_rec else None
            return ResolutionResult(
                status=IdentityStatus.MANUAL,
                lei=ov.lei,
                method="manual_override",
                confidence=1.0,
                evidence=f"override: {ov.reason} (reviewed {ov.reviewed_at})",
                manual_override=True,
                canonical_name=name or rec.normalized_name,
                country=self.gleif.country(gleif_rec) if gleif_rec else rec.country,
            )

        if rec.source_lei:
            return self._resolve_source_lei(rec)
        return self._resolve_by_name(rec)

    # ------------------------------------------------------------------

    def _resolve_source_lei(self, rec: ParticipantRecord) -> ResolutionResult:
        lei = rec.source_lei or ""
        if not lei_checksum_ok(lei):
            return ResolutionResult(
                status=IdentityStatus.UNRESOLVED,
                method="source_lei_invalid",
                evidence=f"source-provided LEI {lei!r} fails checksum",
            )
        gleif_rec = self.gleif.get_lei(lei)
        if gleif_rec is None:
            return ResolutionResult(
                status=IdentityStatus.UNRESOLVED,
                method="source_lei_not_in_gleif",
                evidence=f"source-provided LEI {lei} not found in GLEIF",
            )
        gname = self.gleif.legal_name(gleif_rec)
        sim = _name_similarity(rec.normalized_name, normalize_name(gname))
        evidence = (
            f"source LEI verified in GLEIF; source name vs GLEIF legal name similarity {sim:.2f}"
        )
        status = IdentityStatus.EXACT_SOURCE_LEI
        if sim < 0.45:
            # LEI valid but name wildly different — still resolved via source
            # LEI (venue assertion) but flagged for review as a conflict note.
            evidence += "; NAME_MISMATCH_FLAG"
        return ResolutionResult(
            status=status,
            lei=lei,
            method="source_lei",
            confidence=1.0 if sim >= 0.45 else 0.9,
            evidence=evidence,
            canonical_name=gname or rec.normalized_name,
            country=self.gleif.country(gleif_rec),
        )

    # ------------------------------------------------------------------

    def _score(
        self,
        rec: ParticipantRecord,
        gleif_rec: dict[str, Any],
    ) -> tuple[float, list[str], list[str]]:
        """Return (score, matching_names, reasons)."""
        reasons: list[str] = []
        names: list[str] = []
        src = rec.normalized_name
        gname = self.gleif.legal_name(gleif_rec)
        gnorm = normalize_name(gname)
        names.append(gnorm)
        for other in self.gleif.other_names(gleif_rec):
            names.append(normalize_name(other))

        best = max((_name_similarity(src, n) for n in names if n), default=0.0)
        reasons.append(f"name_similarity={best:.2f}")
        if best >= AUTO_NAME_MIN:
            reasons.append("exact_normalized_name")
        else:
            # stem comparison (drops legal form on both sides)
            s_stem = name_stem(src)
            g_stem = name_stem(gnorm)
            stem_sim = _name_similarity(s_stem, g_stem)
            reasons.append(f"stem_similarity={stem_sim:.2f}")
            if stem_sim >= STEM_MIN:
                lf_src = legal_form_signature(src)
                lf_g = legal_form_signature(gnorm)
                if lf_src and lf_g and lf_src != lf_g:
                    reasons.append(f"legal_form_mismatch({lf_src}!={lf_g})")
                    best = min(best, 0.6)
                else:
                    best = max(best, stem_sim * 0.95)

        # Country corroboration.
        gcountry = self.gleif.country(gleif_rec)
        if rec.country and gcountry:
            if rec.country == gcountry:
                reasons.append(f"country_match({gcountry})")
                best += 0.05
            else:
                reasons.append(f"country_mismatch({rec.country}!={gcountry})")
                best -= 0.15

        # Address corroboration.
        if rec.normalized_address and gcountry:
            gaddr = normalize_address(self.gleif.address_str(gleif_rec))
            j = _token_jaccard(rec.normalized_address, gaddr)
            if j >= 0.4:
                reasons.append(f"address_match(jaccard={j:.2f})")
                best += 0.05
            elif j < 0.05 and rec.country == gcountry:
                reasons.append(f"address_disjoint(jaccard={j:.2f})")

        status = self.gleif.entity_status(gleif_rec)
        if status and status != "ACTIVE":
            reasons.append(f"entity_status={status}")
            best -= 0.10

        return min(best, 1.0), names, reasons

    def _candidates(self, rec: ParticipantRecord) -> list[dict[str, Any]]:
        """Ordered candidate-generation attempts (all recorded as evidence)."""
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for query in self._candidate_queries(rec):
            for c in self.gleif.search_by_name(query, size=10):
                lei = c.get("id")
                if lei and lei not in seen:
                    seen.add(lei)
                    out.append(c)
            # A variant that produced candidates wins only if one of them
            # is good; otherwise keep trying later variants (e.g. the
            # trailing-token drop that removes a BME exchange suffix).
            if out and any(self._score(rec, c)[0] >= AUTO_NAME_MIN for c in out):
                break
        return out

    def _disambiguate(
        self,
        rec: ParticipantRecord,
        tied: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Return the single candidate corroborated by country and/or address.

        Rules:
        - if source country is known, discard candidates in other countries;
        - if source address exists, require a token-Jaccard >= 0.3 on the
          legal address;
        - resolve only when exactly one candidate survives.
        """
        pool = tied
        if rec.country:
            same = [c for c in pool if self.gleif.country(c) == rec.country]
            if len(same) == 1:
                pool = same
        if rec.normalized_address:
            scored_addr = []
            for c in pool:
                gaddr = normalize_address(self.gleif.address_str(c))
                scored_addr.append((_token_jaccard(rec.normalized_address, gaddr), c))
            best = max(scored_addr, key=lambda t: t[0], default=(0.0, None))
            if best[0] >= 0.3 and sum(1 for j, _ in scored_addr if j >= 0.3) == 1:
                return best[1]
            return None
        return pool[0] if len(pool) == 1 and rec.country else None

    @staticmethod
    def _candidate_queries(rec: ParticipantRecord) -> list[str]:
        queries = [rec.raw_name]
        if rec.normalized_name and rec.normalized_name != rec.raw_name:
            queries.append(rec.normalized_name)
        stem = name_stem(rec.normalized_name)
        if stem and stem != rec.normalized_name:
            queries.append(stem)
        # BME-style trailing exchange suffix: "X S.A. - BARCELONA" -> "X SA".
        # The segment/member code still identifies the exchange office; the
        # legal entity is unchanged.
        norm = (rec.normalized_name or "").split()
        for drop in (2, 1):
            if len(norm) > drop:
                queries.append(" ".join(norm[:-drop]))
        # GLEIF rejects punctuation like trailing commas; strip it from queries
        return [q.strip(" ,").strip() for q in queries if q.strip(" ,")]

    def _resolve_by_name(self, rec: ParticipantRecord) -> ResolutionResult:
        candidates = self._candidates(rec)
        if not candidates:
            return ResolutionResult(
                status=IdentityStatus.UNRESOLVED,
                method="no_gleif_candidates",
                candidate_count=0,
                evidence="GLEIF name search returned no candidates",
            )

        scored: list[tuple[float, dict[str, Any], list[str]]] = []
        for c in candidates:
            score, _names, reasons = self._score(rec, c)
            scored.append((score, c, reasons))
        scored.sort(key=lambda t: -t[0])
        top_score, top, top_reasons = scored[0]
        top_lei = top.get("id", "")
        close = [s for s, _c, _r in scored if s >= top_score - CONFLICT_MARGIN]

        if top_score >= AUTO_NAME_MIN and len(close) == 1:
            status = (
                IdentityStatus.EXACT_NAME_COUNTRY
                if rec.country and self.gleif.country(top) == rec.country
                else IdentityStatus.EXACT_LEGAL_NAME
            )
            return ResolutionResult(
                status=status,
                lei=top_lei,
                method="name_match",
                confidence=top_score,
                candidate_count=len(scored),
                candidates=[c.get("id", "") for _s, c, _r in scored[1:4]],
                evidence="; ".join(top_reasons),
                canonical_name=self.gleif.legal_name(top),
                country=self.gleif.country(top),
            )

        if len(close) > 1 and top_score >= FUZZY_CANDIDATE_MIN:
            # Try to break the tie with corroborating evidence before
            # declaring a conflict: exactly one candidate may match the
            # source address or country.
            winner = self._disambiguate(rec, [c for s, c, _r in scored[: len(close)]])
            if winner is not None:
                return ResolutionResult(
                    status=IdentityStatus.NAME_ADDRESS_MATCH,
                    lei=winner.get("id", ""),
                    method="ambiguous_name_address_tiebreak",
                    confidence=top_score,
                    candidate_count=len(scored),
                    candidates=[
                        c.get("id", "") for _s, c, _r in scored if c.get("id") != winner.get("id")
                    ][:4],
                    evidence="resolved among near-tied candidates by country/address corroboration",
                    canonical_name=self.gleif.legal_name(winner),
                    country=self.gleif.country(winner),
                )
            return ResolutionResult(
                status=IdentityStatus.CONFLICT,
                method="ambiguous_candidates",
                confidence=top_score,
                candidate_count=len(scored),
                candidates=[c.get("id", "") for _s, c, _r in scored[:5]],
                evidence=f"ambiguous: {len(close)} candidates within {CONFLICT_MARGIN}; "
                + "; ".join(top_reasons),
            )

        if top_score >= FUZZY_CANDIDATE_MIN + 0.10:
            # strong but not exact — needs country/address to auto-resolve
            if rec.country and self.gleif.country(top) == rec.country:
                return ResolutionResult(
                    status=IdentityStatus.NAME_ADDRESS_MATCH
                    if rec.normalized_address
                    else IdentityStatus.EXACT_NAME_COUNTRY,
                    lei=top_lei,
                    method="name_plus_country",
                    confidence=top_score,
                    candidate_count=len(scored),
                    candidates=[c.get("id", "") for _s, c, _r in scored[1:4]],
                    evidence="; ".join(top_reasons),
                    canonical_name=self.gleif.legal_name(top),
                    country=self.gleif.country(top),
                )
            return ResolutionResult(
                status=IdentityStatus.FUZZY_CANDIDATE,
                lei=top_lei,
                method="fuzzy_single_candidate",
                confidence=top_score,
                candidate_count=len(scored),
                candidates=[c.get("id", "") for _s, c, _r in scored[1:4]],
                evidence="; ".join(top_reasons),
                canonical_name=self.gleif.legal_name(top),
                country=self.gleif.country(top),
            )

        return ResolutionResult(
            status=IdentityStatus.UNRESOLVED,
            method="below_threshold",
            confidence=top_score,
            candidate_count=len(scored),
            candidates=[c.get("id", "") for _s, c, _r in scored[:5]],
            evidence="; ".join(top_reasons),
        )


def resolved_at() -> datetime:
    return datetime.now(UTC)
