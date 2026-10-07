"""DuckDB persistence layer."""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from venue_access.domain.enums import SnapshotStatus
from venue_access.domain.models import (
    ParticipantRecord,
    SourceDefinition,
)
from venue_access.sources.iso10383 import VenueRecord

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

OPEN_STATUSES = (
    SnapshotStatus.FETCHED.value,
    SnapshotStatus.PARSED.value,
    SnapshotStatus.VALIDATED.value,
)
GOOD_STATUSES = (SnapshotStatus.VALIDATED.value, SnapshotStatus.PUBLISHED.value)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path))
        self.con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    def close(self) -> None:
        self.con.close()

    # ---- catalog --------------------------------------------------------

    def upsert_source(self, s: SourceDefinition) -> None:
        self.con.execute(
            """INSERT INTO source VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_id) DO UPDATE SET
               operator=excluded.operator, source_name=excluded.source_name,
               source_url=excluded.source_url, source_type=excluded.source_type,
               coverage_scope=excluded.coverage_scope,
               scope_description=excluded.scope_description,
               absence_semantics_allowed=excluded.absence_semantics_allowed,
               active=excluded.active, notes=excluded.notes""",
            [
                s.source_id, s.operator, s.source_name, s.source_url, s.source_type,
                s.coverage_scope.value, s.scope_description,
                s.absence_semantics_allowed, s.active, s.notes,
            ],
        )

    # ---- snapshots ------------------------------------------------------

    def insert_snapshot(self, meta: dict[str, Any]) -> None:
        cols = list(meta.keys())
        self.con.execute(
            f"INSERT INTO snapshot ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [meta[c] for c in cols],
        )

    def set_snapshot_status(self, snapshot_id: str, status: SnapshotStatus,
                            report: str | None = None) -> None:
        if report is None:
            self.con.execute(
                "UPDATE snapshot SET snapshot_status=? WHERE snapshot_id=?",
                [status.value, snapshot_id],
            )
        else:
            self.con.execute(
                "UPDATE snapshot SET snapshot_status=?, validation_report=? "
                "WHERE snapshot_id=?",
                [status.value, report, snapshot_id],
            )

    def update_snapshot_counts(self, snapshot_id: str, **counts: int) -> None:
        sets = ",".join(f"{k}=?" for k in counts)
        self.con.execute(
            f"UPDATE snapshot SET {sets} WHERE snapshot_id=?",
            [*counts.values(), snapshot_id],
        )

    def latest_snapshot(self, source_id: str,
                        statuses: tuple[str, ...] | None = None) -> dict | None:
        q = "SELECT * FROM snapshot WHERE source_id=?"
        params: list[Any] = [source_id]
        if statuses:
            q += f" AND snapshot_status IN ({','.join('?' * len(statuses))})"
            params += list(statuses)
        q += " ORDER BY retrieved_at DESC LIMIT 1"
        row = self.con.execute(q, params).fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self.con.description]
        return dict(zip(cols, row, strict=False))

    def snapshots(self, source_id: str | None = None, limit: int = 100) -> list[dict]:
        q = "SELECT * FROM snapshot"
        params: list[Any] = []
        if source_id:
            q += " WHERE source_id=?"
            params.append(source_id)
        q += " ORDER BY retrieved_at DESC LIMIT ?"
        params.append(limit)
        return self._rows(q, params)

    # ---- participants / observations ------------------------------------

    def upsert_participant(self, p: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        self.con.execute(
            """UPDATE participant SET canonical_name=?,
               country=COALESCE(country, ?),
               identity_status=?, identity_method=?, identity_confidence=?,
               updated_at=?
               WHERE participant_id=?""",
            [p["canonical_name"], p.get("country"), p["identity_status"],
             p.get("identity_method", ""), p.get("identity_confidence", 0.0),
             now, p["participant_id"]],
        )
        if not self.con.execute(
            "SELECT 1 FROM participant WHERE participant_id=?",
            [p["participant_id"]],
        ).fetchone():
            self.con.execute(
                """INSERT INTO participant
                   (participant_id, canonical_name, country, lei, identity_status,
                    identity_method, identity_confidence, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                [p["participant_id"], p["canonical_name"], p.get("country"),
                 p.get("lei"), p["identity_status"], p.get("identity_method", ""),
                 p.get("identity_confidence", 0.0), now, now],
            )

    def upsert_alias(self, participant_id: str, source_id: str,
                     rec: ParticipantRecord) -> None:
        self.con.execute(
            """INSERT INTO participant_alias VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_id, source_participant_key) DO UPDATE SET
               participant_id=excluded.participant_id,
               raw_name=excluded.raw_name,
               normalized_name=excluded.normalized_name,
               raw_address=excluded.raw_address,
               normalized_address=excluded.normalized_address,
               raw_country=excluded.raw_country,
               source_record_id=excluded.source_record_id""",
            [participant_id, source_id, rec.source_participant_key, rec.raw_name,
             rec.normalized_name, rec.raw_address, rec.normalized_address,
             rec.raw_country, rec.source_record_id],
        )

    def insert_identity_resolution(self, row: dict[str, Any]) -> None:
        self.con.execute(
            """INSERT INTO identity_resolution VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_id, source_participant_key) DO UPDATE SET
               participant_id=excluded.participant_id, status=excluded.status,
               lei=excluded.lei, method=excluded.method,
               confidence=excluded.confidence,
               candidate_count=excluded.candidate_count,
               candidates_json=excluded.candidates_json,
               evidence=excluded.evidence,
               resolver_version=excluded.resolver_version,
               manual_override=excluded.manual_override,
               resolved_at=excluded.resolved_at""",
            [row["participant_id"], row["source_id"], row["source_participant_key"],
             row["status"], row.get("lei"), row.get("method"), row.get("confidence"),
             row.get("candidate_count", 0), row.get("candidates_json", "[]"),
             row.get("evidence", ""), row.get("resolver_version", ""),
             row.get("manual_override", False), row.get("resolved_at")],
        )

    def insert_observation(self, obs_id: str, snapshot_id: str, participant_id: str,
                           rec: ParticipantRecord) -> str:
        self.con.execute(
            """INSERT INTO membership_observation VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT (observation_id) DO NOTHING""",
            [obs_id, snapshot_id, participant_id, rec.source_participant_key,
             rec.membership_type_raw, rec.membership_type_normalized, True,
             rec.record_hash()],
        )
        return obs_id

    def insert_segment(self, seg_id: str, obs_id: str, seg: Any) -> None:
        self.con.execute(
            """INSERT INTO membership_segment_observation VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (segment_observation_id) DO NOTHING""",
            [seg_id, obs_id, seg.source_market_code, seg.mic, seg.market_family,
             seg.segment_raw, seg.member_code, seg.capacity_raw,
             getattr(seg, "capacity_normalized", None), seg.segment_active],
        )

    # ---- venues ---------------------------------------------------------

    def replace_venues(self, venues: Iterable[VenueRecord], snapshot_id: str,
                       publication_date: str) -> None:
        self.con.execute("DELETE FROM venue")
        self.con.executemany(
            """INSERT INTO venue VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (v.mic, v.operating_mic, v.mic_type, v.market_name,
                 v.legal_entity_name, v.operator_lei, v.market_category, v.acronym,
                 v.country, v.city, v.website, v.status, v.creation_date,
                 v.last_update_date, v.last_validation_date, v.expiry_date,
                 v.comments, publication_date, snapshot_id)
                for v in venues
            ],
        )

    # ---- helpers --------------------------------------------------------

    def _rows(self, q: str, params: list[Any] | None = None) -> list[dict]:
        cur = self.con.execute(q, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]

    def query(self, q: str, params: list[Any] | None = None) -> list[dict]:
        return self._rows(q, params)

    def df(self, q: str, params: list[Any] | None = None) -> Any:
        return self.con.execute(q, params or []).fetchdf()

    def arrow(self, q: str, params: list[Any] | None = None) -> Any:
        return self.con.execute(q, params or []).fetch_arrow_table()
