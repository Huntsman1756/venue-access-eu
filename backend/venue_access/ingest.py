"""Ingestion orchestration: fetch -> snapshot -> parse -> gate -> persist."""

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re

import yaml

from venue_access.domain.enums import ErrorCode, IdentityStatus, SnapshotStatus
from venue_access.domain.models import SourceDefinition
from venue_access.identity.gleif import GleifClient
from venue_access.identity.resolver import (
    RESOLVER_VERSION,
    EntityResolver,
    load_overrides,
)
from venue_access.quality.gates import GateResult, evaluate_snapshot
from venue_access.sources.base import FetchConfig, SourceAdapter, SourceError
from venue_access.sources.bme import BmeAdapter
from venue_access.sources.euronext import EuronextAdapter
from venue_access.sources.iso10383 import Iso10383Adapter, parse_mic_csv
from venue_access.sources.lse import LseAdapter, bundle_sha256
from venue_access.sources.xetra import XetraAdapter
from venue_access.storage.store import GOOD_STATUSES, Store

CATALOG_PATH = Path(__file__).parent / "sources" / "catalog.yaml"

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "xetra-participants": XetraAdapter,
    "euronext-members": EuronextAdapter,
    "bme-equity-members": BmeAdapter,
    "lse-member-directory": LseAdapter,
}
MEMBERSHIP_SOURCES = set(ADAPTERS)


def _slug(url: str, idx: int) -> str:
    tail = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("/")[-1] or "artifact")
    return f"{idx:03d}-{tail[:80]}.bin"


def load_catalog() -> dict[str, SourceDefinition]:
    raw = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        s["id"]: SourceDefinition(
            source_id=s["id"],
            operator=s["operator"],
            source_name=s["source_name"],
            source_url=s["source_url"],
            source_type=s["source_type"],
            coverage_scope=s["coverage_scope"],
            scope_description=s.get("scope_description", ""),
            absence_semantics_allowed=s.get("absence_semantics_allowed", False),
            active=s.get("active", True),
            notes=s.get("notes", ""),
        )
        for s in raw["sources"]
    }


class IngestResult(dict):
    """Per-source outcome for CLI reporting."""


def refresh_source(
    store: Store,
    adapter: SourceAdapter,
    data_root: Path,
    resolver: EntityResolver | None = None,
    config: FetchConfig | None = None,
) -> dict:
    """Run one full ingest cycle for a membership source."""
    source_id = adapter.source_id
    now = datetime.now(UTC)

    # 1. fetch
    try:
        artifacts = adapter.fetch(config)
    except SourceError as exc:
        _record_failed_snapshot(store, source_id, now, exc)
        return {"source": source_id, "status": "FAILED", "error": exc.code.value,
                "detail": exc.message}

    # 2. persist raw artifacts
    raw_dir = data_root / "raw" / source_id / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S")
    raw_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for i, art in enumerate(artifacts):
        (raw_dir / _slug(art.url, i)).write_bytes(art.body)
        total_bytes += len(art.body)
    raw_hash = (
        bundle_sha256(artifacts) if len(artifacts) > 1 else artifacts[0].sha256
    )
    snapshot_id = f"{source_id}:{now.strftime('%Y%m%dT%H%M%S')}"
    snapshot = {
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "retrieved_at": artifacts[0].retrieved_at,
        "http_status": artifacts[0].http_status,
        "content_type": artifacts[0].content_type,
        "final_url": artifacts[0].final_url,
        "raw_sha256": raw_hash,
        "raw_bytes": total_bytes,
        "raw_path": str(raw_dir),
        "parser_name": adapter.parser_version,
        "parser_version": adapter.parser_version,
        "snapshot_status": SnapshotStatus.FETCHED.value,
    }
    store.insert_snapshot(snapshot)

    # 3. parse
    try:
        parsed = adapter.parse(artifacts)
    except SourceError as exc:
        store.set_snapshot_status(snapshot_id, SnapshotStatus.QUARANTINED, exc.message)
        return {"source": source_id, "snapshot": snapshot_id, "status": "QUARANTINED",
                "error": exc.code.value, "detail": exc.message}
    store.con.execute(
        "UPDATE snapshot SET source_declared_updated_at=?, source_schema_signature=?, "
        "record_count=?, segment_count=?, parse_error_count=? WHERE snapshot_id=?",
        [parsed.source_declared_updated_at, parsed.schema_signature,
         len(parsed.records),
         sum(len(r.segments) for r in parsed.records),
         len(parsed.parse_errors), snapshot_id],
    )
    store.set_snapshot_status(snapshot_id, SnapshotStatus.PARSED)

    # 4. contract validation + anomaly gate vs latest good snapshot
    violations = adapter.validate(parsed)
    previous = store.latest_snapshot(source_id, GOOD_STATUSES)
    # exclude the snapshot we just inserted from "previous"
    if previous and previous["snapshot_id"] == snapshot_id:
        previous = None
    gate: GateResult = evaluate_snapshot(parsed, violations, previous)
    store.con.execute(
        "UPDATE snapshot SET snapshot_status=?, validation_report=? WHERE snapshot_id=?",
        [gate.status.value, json.dumps({"reasons": gate.reasons, "metrics": gate.metrics}),
         snapshot_id],
    )
    if not gate.passed:
        return {"source": source_id, "snapshot": snapshot_id,
                "status": gate.status.value, "reasons": gate.reasons,
                "metrics": gate.metrics}

    # 5. identity resolution + participant/alias/observation persistence
    unresolved = 0
    if resolver is not None:
        unresolved = _resolve_and_persist(store, source_id, snapshot_id,
                                          parsed.records, resolver)
    else:
        _persist_without_resolution(store, source_id, snapshot_id, parsed.records)
    store.con.execute(
        "UPDATE snapshot SET unresolved_identity_count=?, membership_count=? "
        "WHERE snapshot_id=?",
        [unresolved, len(parsed.records), snapshot_id],
    )
    store.set_snapshot_status(snapshot_id, SnapshotStatus.VALIDATED)
    return {"source": source_id, "snapshot": snapshot_id,
            "status": SnapshotStatus.VALIDATED.value,
            "records": len(parsed.records),
            "segments": sum(len(r.segments) for r in parsed.records),
            "unresolved": unresolved,
            "warnings": gate.reasons}


def _participant_id(lei: str | None, source_id: str, key: str) -> str:
    if lei:
        return f"lei:{lei}"
    return f"unresolved:{source_id}:{key}"


def _resolve_and_persist(store: Store, source_id: str, snapshot_id: str,
                         records: list, resolver: EntityResolver) -> int:
    unresolved = 0
    gleif = resolver.gleif
    for rec in records:
        res = resolver.resolve(source_id, rec)
        pid = _participant_id(res.lei, source_id, rec.source_participant_key)
        if res.status in (IdentityStatus.UNRESOLVED, IdentityStatus.CONFLICT):
            unresolved += 1
        canonical = res.canonical_name or rec.normalized_name or rec.raw_name
        store.upsert_participant({
            "participant_id": pid,
            "canonical_name": canonical,
            "country": res.country or rec.country,
            "lei": res.lei,
            "identity_status": res.status.value,
            "identity_method": res.method,
            "identity_confidence": res.confidence,
        })
        store.upsert_alias(pid, source_id, rec)
        store.insert_identity_resolution({
            "participant_id": pid,
            "source_id": source_id,
            "source_participant_key": rec.source_participant_key,
            "status": res.status.value,
            "lei": res.lei,
            "method": res.method,
            "confidence": res.confidence,
            "candidate_count": res.candidate_count,
            "candidates_json": json.dumps(res.candidates),
            "evidence": res.evidence,
            "resolver_version": RESOLVER_VERSION,
            "manual_override": res.manual_override,
            "resolved_at": datetime.now(UTC),
        })
        if res.lei:
            _cache_gleif_entity(store, gleif, res.lei)
        obs_id = sha256(
            f"{snapshot_id}|{pid}|{rec.source_participant_key}".encode()
        ).hexdigest()[:32]
        store.insert_observation(obs_id, snapshot_id, pid, rec)
        for j, seg in enumerate(rec.segments):
            seg_id = sha256(f"{obs_id}|{j}|{seg.source_market_code}".encode()).hexdigest()[:32]
            store.insert_segment(seg_id, obs_id, seg)
    return unresolved


def _persist_without_resolution(store: Store, source_id: str, snapshot_id: str,
                                records: list) -> None:
    for rec in records:
        pid = _participant_id(rec.source_lei, source_id, rec.source_participant_key)
        store.upsert_participant({
            "participant_id": pid,
            "canonical_name": rec.normalized_name or rec.raw_name,
            "country": rec.country,
            "lei": rec.source_lei,
            "identity_status": (IdentityStatus.EXACT_SOURCE_LEI.value
                                if rec.source_lei else IdentityStatus.UNRESOLVED.value),
            "identity_method": "source_lei" if rec.source_lei else "unresolved",
            "identity_confidence": 1.0 if rec.source_lei else 0.0,
        })
        store.upsert_alias(pid, source_id, rec)
        obs_id = sha256(
            f"{snapshot_id}|{pid}|{rec.source_participant_key}".encode()
        ).hexdigest()[:32]
        store.insert_observation(obs_id, snapshot_id, pid, rec)
        for j, seg in enumerate(rec.segments):
            seg_id = sha256(f"{obs_id}|{j}|{seg.source_market_code}".encode()).hexdigest()[:32]
            store.insert_segment(seg_id, obs_id, seg)


def _cache_gleif_entity(store: Store, gleif: GleifClient, lei: str) -> None:
    existing = store.query("SELECT lei FROM gleif_entity WHERE lei=?", [lei])
    if existing:
        return
    rec = gleif.get_lei(lei)
    if rec is None:
        return
    store.con.execute(
        """INSERT INTO gleif_entity VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [lei, gleif.legal_name(rec), None, gleif.country(rec), gleif.city(rec),
         json.dumps(gleif.address_str(rec)), gleif.entity_status(rec),
         gleif.registration_status(rec), json.dumps(rec), datetime.now(UTC)],
    )


def _record_failed_snapshot(store: Store, source_id: str, now: datetime,
                            exc: SourceError) -> None:
    snapshot_id = f"{source_id}:{now.strftime('%Y%m%dT%H%M%S')}"
    store.insert_snapshot({
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "retrieved_at": now,
        "validation_report": json.dumps({"error": exc.code.value,
                                         "detail": exc.message}),
        "snapshot_status": SnapshotStatus.REJECTED.value,
    })


def refresh_mic(store: Store, data_root: Path,
                config: FetchConfig | None = None) -> dict:
    """Refresh the ISO 10383 venue dimension."""
    adapter = Iso10383Adapter()
    artifacts = adapter.fetch(config)
    raw_dir = data_root / "raw" / adapter.source_id / datetime.now(UTC).strftime("%Y-%m-%d")
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "ISO10383_MIC.csv").write_bytes(artifacts[0].body)
    venues = parse_mic_csv(artifacts[0].body)
    snapshot_id = f"{adapter.source_id}:{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    store.insert_snapshot({
        "snapshot_id": snapshot_id,
        "source_id": adapter.source_id,
        "retrieved_at": artifacts[0].retrieved_at,
        "http_status": artifacts[0].http_status,
        "content_type": artifacts[0].content_type,
        "final_url": artifacts[0].final_url,
        "raw_sha256": artifacts[0].sha256,
        "raw_bytes": len(artifacts[0].body),
        "raw_path": str(raw_dir),
        "parser_version": adapter.parser_version,
        "record_count": len(venues),
        "snapshot_status": SnapshotStatus.VALIDATED.value,
    })
    pub_date = max(
        (str(v.last_update_date) for v in venues if v.last_update_date), default=""
    )
    store.replace_venues(venues, snapshot_id, pub_date)
    return {"source": adapter.source_id, "snapshot": snapshot_id,
            "status": "VALIDATED", "venues": len(venues),
            "publication_date": pub_date}
