"""DuckDB persistence layer."""

import importlib.util
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

# DuckDB probes for pandas on every execute/fetch. Without pandas each probe is
# a full sys.path scan (~4x query overhead, worse on busy disks). Caching the
# miss makes the probe fail fast; installs that do have pandas are unaffected.
if importlib.util.find_spec("pandas") is None:
    sys.modules.setdefault("pandas", None)  # type: ignore[arg-type]

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


def spid(source_id: str, key: str) -> str:
    """Stable source-participant id: temporal anchor for membership history."""
    return f"sp:{source_id}:{key}"


def _normalize_member_code(code: str | None) -> str | None:
    """Search form of a member code: strip zero-padding only when the code is
    fully numeric (Euronext "00004441" -> "4441"); alphanumeric codes (Xetra
    mnemonic IDs, LSE mnemonics) are unchanged."""
    if not code:
        return None
    v = code.strip()
    if v.isdigit():
        return v.lstrip("0") or "0"
    return v


class Store:
    def __init__(self, path: Path | str, read_only: bool = False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path), read_only=read_only)
        if not read_only:
            self._migrate()
            # one transaction: a durable commit per DDL statement costs seconds on disk
            self.con.execute("BEGIN TRANSACTION")
            try:
                self.con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            except Exception:
                self.con.execute("ROLLBACK")
                raise
            self.con.execute("COMMIT")

    def _migrate(self) -> None:
        """In-place migrations for databases created before schema v2."""
        row = self.con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name='membership_observation'"
        ).fetchone()
        if not row or not row[0]:
            return  # fresh database — schema.sql creates everything
        # member_code_normalized (v0.1.1)
        seg_cols = {
            d[0] for d in self.con.execute("DESCRIBE membership_segment_observation").fetchall()
        }
        if "member_code_normalized" not in seg_cols:
            self.con.execute(
                "ALTER TABLE membership_segment_observation "
                "ADD COLUMN member_code_normalized VARCHAR"
            )
            self.con.execute(
                """UPDATE membership_segment_observation
                   SET member_code_normalized = CASE
                     WHEN member_code IS NULL THEN NULL
                     WHEN regexp_matches(trim(member_code),'^[0-9]+$')
                       THEN nullif(regexp_replace(trim(member_code),'^0+',''),'')
                     ELSE trim(member_code) END"""
            )
        # source-provided LEI preserved at the source-participant level (v0.1.2)
        sp_cols = {d[0] for d in self.con.execute("DESCRIBE source_participant").fetchall()}
        if "source_lei" not in sp_cols:
            self.con.execute("ALTER TABLE source_participant ADD COLUMN source_lei VARCHAR")
            self.con.execute(
                """UPDATE source_participant sp SET source_lei=p.lei
                   FROM participant_alias a
                   JOIN participant p ON p.participant_id=a.participant_id
                   WHERE a.source_participant_id=sp.source_participant_id
                     AND p.lei IS NOT NULL"""
            )
        # participant candidate fields (v0.1.2)
        p_cols = {d[0] for d in self.con.execute("DESCRIBE participant").fetchall()}
        if "candidate_lei" not in p_cols:
            self.con.execute("ALTER TABLE participant ADD COLUMN candidate_lei VARCHAR")
            self.con.execute("ALTER TABLE participant ADD COLUMN candidate_confidence DOUBLE")
        # source_participant decoupling (v0.1.2)
        obs_cols = {d[0] for d in self.con.execute("DESCRIBE membership_observation").fetchall()}
        if "participant_id" in obs_cols:
            self.con.execute(
                "ALTER TABLE membership_observation "
                "ADD COLUMN IF NOT EXISTS source_participant_id VARCHAR"
            )
            self.con.execute(
                """UPDATE membership_observation o
                   SET source_participant_id='sp:'||sn.source_id||':'||o.source_participant_key
                   FROM snapshot sn WHERE sn.snapshot_id=o.snapshot_id"""
            )
            # backfill source_participant rows
            self.con.execute(
                """INSERT INTO source_participant
                   (source_participant_id, source_id, source_participant_key,
                    raw_name, normalized_name, raw_address, raw_country)
                   SELECT DISTINCT 'sp:'||sn.source_id||':'||o.source_participant_key,
                          sn.source_id, o.source_participant_key,
                          a.raw_name, a.normalized_name, a.raw_address, a.raw_country
                   FROM membership_observation o
                   JOIN snapshot sn ON sn.snapshot_id=o.snapshot_id
                   LEFT JOIN participant_alias a
                     ON a.source_id=sn.source_id
                    AND a.source_participant_key=o.source_participant_key
                   ON CONFLICT DO NOTHING"""
            )
            # alias gains source_participant_id
            self.con.execute(
                "ALTER TABLE participant_alias ADD COLUMN IF NOT EXISTS "
                "source_participant_id VARCHAR"
            )
            self.con.execute(
                """UPDATE participant_alias
                   SET source_participant_id='sp:'||source_id||':'||source_participant_key
                   WHERE source_participant_id IS NULL"""
            )
            # identity_resolution gains spid + run id; old rows kept as one run
            self.con.execute(
                "ALTER TABLE identity_resolution ADD COLUMN IF NOT EXISTS "
                "source_participant_id VARCHAR"
            )
            self.con.execute(
                "ALTER TABLE identity_resolution ADD COLUMN IF NOT EXISTS resolution_run_id VARCHAR"
            )
            self.con.execute(
                """UPDATE identity_resolution
                   SET source_participant_id='sp:'||source_id||':'||source_participant_key,
                       resolution_run_id=COALESCE(resolution_run_id,'pre-v0.1.2')
                   WHERE source_participant_id IS NULL"""
            )
            # FK on participant_id blocks DROP COLUMN: rebuild the table
            self.con.execute(
                """CREATE TABLE membership_observation_v2 (
                     observation_id VARCHAR PRIMARY KEY,
                     snapshot_id VARCHAR NOT NULL REFERENCES snapshot(snapshot_id),
                     source_participant_id VARCHAR NOT NULL
                       REFERENCES source_participant(source_participant_id),
                     source_participant_key VARCHAR NOT NULL,
                     membership_type_raw VARCHAR,
                     membership_type_normalized VARCHAR,
                     membership_present BOOLEAN NOT NULL,
                     source_record_hash VARCHAR NOT NULL)"""
            )
            self.con.execute(
                """INSERT INTO membership_observation_v2
                   SELECT observation_id, snapshot_id, source_participant_id,
                          source_participant_key, membership_type_raw,
                          membership_type_normalized, membership_present,
                          source_record_hash
                   FROM membership_observation"""
            )
            self.con.execute("DROP TABLE membership_observation")
            self.con.execute(
                "ALTER TABLE membership_observation_v2 RENAME TO membership_observation"
            )
        # participant_alias must lose its FKs: attribution updates are UPDATEs
        # which DuckDB rewrites as DELETE+INSERT -> FK references block them.
        _fks_row = self.con.execute(
            """SELECT COUNT(*) FROM information_schema.referential_constraints rc
               JOIN information_schema.table_constraints tc
                 ON rc.constraint_name=tc.constraint_name
               WHERE tc.table_name='participant_alias'"""
        ).fetchone()
        fks = _fks_row[0] if _fks_row else 0
        if fks:
            self.con.execute(
                """CREATE TABLE participant_alias_v2 (
                     source_participant_id VARCHAR NOT NULL,
                     participant_id VARCHAR NOT NULL,
                     source_id VARCHAR NOT NULL,
                     source_participant_key VARCHAR NOT NULL,
                     raw_name VARCHAR NOT NULL,
                     normalized_name VARCHAR,
                     raw_address VARCHAR,
                     normalized_address VARCHAR,
                     raw_country VARCHAR,
                     source_record_id VARCHAR,
                     PRIMARY KEY (source_id, source_participant_key))"""
            )
            self.con.execute(
                """INSERT INTO participant_alias_v2
                   SELECT source_participant_id, participant_id, source_id,
                          source_participant_key, raw_name, normalized_name,
                          raw_address, normalized_address, raw_country,
                          source_record_id
                   FROM participant_alias"""
            )
            self.con.execute("DROP TABLE participant_alias")
            self.con.execute("ALTER TABLE participant_alias_v2 RENAME TO participant_alias")
        # identity_resolution PK must include resolution_run_id (append-only
        # audit); the pre-v0.1.2 PK (source_id, key) overwrote history
        _ir_row = self.con.execute(
            """SELECT COUNT(*) FROM information_schema.key_column_usage k
                JOIN information_schema.table_constraints tc
                  ON k.constraint_name=tc.constraint_name
                WHERE tc.table_name='identity_resolution'
                  AND tc.constraint_type='PRIMARY KEY'
                  AND k.column_name='resolution_run_id'"""
        ).fetchone()
        ir_pk_has_run = _ir_row[0] if _ir_row else 0
        if not ir_pk_has_run:
            self.con.execute(
                """CREATE TABLE identity_resolution_v2 (
                     source_participant_id VARCHAR NOT NULL,
                     resolution_run_id VARCHAR NOT NULL,
                     participant_id VARCHAR NOT NULL,
                     source_id VARCHAR NOT NULL,
                     source_participant_key VARCHAR NOT NULL,
                     status VARCHAR NOT NULL,
                     lei VARCHAR, method VARCHAR, confidence DOUBLE,
                     candidate_count INTEGER, candidates_json VARCHAR,
                     evidence VARCHAR, resolver_version VARCHAR,
                     manual_override BOOLEAN, resolved_at TIMESTAMPTZ NOT NULL,
                     PRIMARY KEY (source_participant_id, resolution_run_id))"""
            )
            self.con.execute(
                """INSERT INTO identity_resolution_v2
                   SELECT source_participant_id, resolution_run_id,
                          participant_id, source_id, source_participant_key,
                          status, lei, method, confidence, candidate_count,
                          candidates_json, evidence, resolver_version,
                          manual_override, resolved_at
                   FROM identity_resolution"""
            )
            self.con.execute("DROP TABLE identity_resolution")
            self.con.execute("ALTER TABLE identity_resolution_v2 RENAME TO identity_resolution")
        # derived tables carry source_participant_id in v2; older shapes are
        # dropped and rebuilt from observations by recompute_history
        iv_cols = {d[0] for d in self.con.execute("DESCRIBE membership_interval").fetchall()}
        if "source_participant_id" not in iv_cols:
            self.con.execute("DROP TABLE membership_interval")
            self.con.execute("DROP TABLE IF EXISTS change_event")
        else:
            # v0.1.2 origin column on change events
            ce_cols = {d[0] for d in self.con.execute("DESCRIBE change_event").fetchall()}
            if "origin" not in ce_cols:
                self.con.execute("ALTER TABLE change_event ADD COLUMN origin VARCHAR")

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
                s.source_id,
                s.operator,
                s.source_name,
                s.source_url,
                s.source_type,
                s.coverage_scope.value,
                s.scope_description,
                s.absence_semantics_allowed,
                s.active,
                s.notes,
            ],
        )

    # ---- snapshots ------------------------------------------------------

    def insert_snapshot(self, meta: dict[str, Any]) -> None:
        cols = list(meta.keys())
        self.con.execute(
            f"INSERT INTO snapshot ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",  # noqa: S608 - internal field names only
            [meta[c] for c in cols],
        )

    def set_snapshot_status(
        self, snapshot_id: str, status: SnapshotStatus, report: str | None = None
    ) -> None:
        if report is None:
            self.con.execute(
                "UPDATE snapshot SET snapshot_status=? WHERE snapshot_id=?",
                [status.value, snapshot_id],
            )
        else:
            self.con.execute(
                "UPDATE snapshot SET snapshot_status=?, validation_report=? WHERE snapshot_id=?",
                [status.value, report, snapshot_id],
            )

    def update_snapshot_counts(self, snapshot_id: str, **counts: int) -> None:
        sets = ",".join(f"{k}=?" for k in counts)
        self.con.execute(
            f"UPDATE snapshot SET {sets} WHERE snapshot_id=?",  # noqa: S608 - internal field names only
            [*counts.values(), snapshot_id],
        )

    def latest_snapshot(
        self, source_id: str, statuses: tuple[str, ...] | None = None
    ) -> dict[str, Any] | None:
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

    def snapshots(self, source_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        q = "SELECT * FROM snapshot"
        params: list[Any] = []
        if source_id:
            q += " WHERE source_id=?"
            params.append(source_id)
        q += " ORDER BY retrieved_at DESC LIMIT ?"
        params.append(limit)
        return self._rows(q, params)

    # ---- source participants / identity ---------------------------------

    def upsert_source_participant(
        self, source_id: str, rec: ParticipantRecord, seen_at: datetime | None = None
    ) -> str:
        """Create/update the stable source-side identity. Returns spid."""
        sid = spid(source_id, rec.source_participant_key)
        now = seen_at or datetime.now(UTC)
        self.con.execute(
            """INSERT INTO source_participant
               (source_participant_id, source_id, source_participant_key,
                raw_name, normalized_name, raw_address, raw_country,
                source_lei, first_seen_at, last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_participant_id) DO UPDATE SET
                 raw_name=excluded.raw_name,
                 normalized_name=excluded.normalized_name,
                 raw_address=excluded.raw_address,
                 raw_country=excluded.raw_country,
                 source_lei=COALESCE(excluded.source_lei,
                                     source_participant.source_lei),
                 last_seen_at=excluded.last_seen_at""",
            [
                sid,
                source_id,
                rec.source_participant_key,
                rec.raw_name,
                rec.normalized_name,
                rec.raw_address,
                rec.raw_country,
                rec.source_lei,
                now,
                now,
            ],
        )
        return sid

    def upsert_participant(self, p: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        self.con.execute(
            """UPDATE participant SET canonical_name=?,
               country=COALESCE(country, ?), lei=COALESCE(lei, ?),
               candidate_lei=?, candidate_confidence=?,
               identity_status=?, identity_method=?, identity_confidence=?,
               updated_at=?
               WHERE participant_id=?""",
            [
                p["canonical_name"],
                p.get("country"),
                p.get("lei"),
                p.get("candidate_lei"),
                p.get("candidate_confidence"),
                p["identity_status"],
                p.get("identity_method", ""),
                p.get("identity_confidence", 0.0),
                now,
                p["participant_id"],
            ],
        )
        if not self.con.execute(
            "SELECT 1 FROM participant WHERE participant_id=?",
            [p["participant_id"]],
        ).fetchone():
            self.con.execute(
                """INSERT INTO participant
                   (participant_id, canonical_name, country, lei, candidate_lei,
                    candidate_confidence, identity_status, identity_method,
                    identity_confidence, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    p["participant_id"],
                    p["canonical_name"],
                    p.get("country"),
                    p.get("lei"),
                    p.get("candidate_lei"),
                    p.get("candidate_confidence"),
                    p["identity_status"],
                    p.get("identity_method", ""),
                    p.get("identity_confidence", 0.0),
                    now,
                    now,
                ],
            )

    def upsert_alias(
        self, sp_id: str, participant_id: str, source_id: str, rec: ParticipantRecord
    ) -> None:
        self.con.execute(
            """INSERT INTO participant_alias
               (source_participant_id, participant_id, source_id,
                source_participant_key, raw_name, normalized_name, raw_address,
                normalized_address, raw_country, source_record_id)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_id, source_participant_key) DO UPDATE SET
               source_participant_id=excluded.source_participant_id,
               participant_id=excluded.participant_id,
               raw_name=excluded.raw_name,
               normalized_name=excluded.normalized_name,
               raw_address=excluded.raw_address,
               normalized_address=excluded.normalized_address,
               raw_country=excluded.raw_country,
               source_record_id=excluded.source_record_id""",
            [
                sp_id,
                participant_id,
                source_id,
                rec.source_participant_key,
                rec.raw_name,
                rec.normalized_name,
                rec.raw_address,
                rec.normalized_address,
                rec.raw_country,
                rec.source_record_id,
            ],
        )

    def insert_identity_resolution(self, row: dict[str, Any]) -> None:
        self.con.execute(
            """INSERT INTO identity_resolution
               (source_participant_id, resolution_run_id, participant_id,
                source_id, source_participant_key, status, lei, method,
                confidence, candidate_count, candidates_json, evidence,
                resolver_version, manual_override, resolved_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (source_participant_id, resolution_run_id) DO UPDATE SET
               participant_id=excluded.participant_id, status=excluded.status,
               lei=excluded.lei, method=excluded.method,
               confidence=excluded.confidence,
               candidate_count=excluded.candidate_count,
               candidates_json=excluded.candidates_json,
               evidence=excluded.evidence,
               resolver_version=excluded.resolver_version,
               manual_override=excluded.manual_override,
               resolved_at=excluded.resolved_at""",
            [
                row["source_participant_id"],
                row["resolution_run_id"],
                row["participant_id"],
                row["source_id"],
                row["source_participant_key"],
                row["status"],
                row.get("lei"),
                row.get("method"),
                row.get("confidence"),
                row.get("candidate_count", 0),
                row.get("candidates_json", "[]"),
                row.get("evidence", ""),
                row.get("resolver_version", ""),
                row.get("manual_override", False),
                row.get("resolved_at"),
            ],
        )

    def latest_resolution(self, source_participant_id: str) -> dict[str, Any] | None:
        rows = self.query(
            """SELECT * FROM identity_resolution WHERE source_participant_id=?
               ORDER BY resolved_at DESC LIMIT 1""",
            [source_participant_id],
        )
        return rows[0] if rows else None

    # ---- observations ---------------------------------------------------

    def insert_observation(
        self, obs_id: str, snapshot_id: str, source_participant_id: str, rec: ParticipantRecord
    ) -> str:
        self.con.execute(
            """INSERT INTO membership_observation VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT (observation_id) DO NOTHING""",
            [
                obs_id,
                snapshot_id,
                source_participant_id,
                rec.source_participant_key,
                rec.membership_type_raw,
                rec.membership_type_normalized,
                True,
                rec.record_hash(),
            ],
        )
        return obs_id

    def insert_segment(self, seg_id: str, obs_id: str, seg: Any) -> None:
        self.con.execute(
            """INSERT INTO membership_segment_observation (
                 segment_observation_id, observation_id, source_market_code, mic,
                 market_family, segment_raw, member_code, member_code_normalized,
                 capacity_raw, capacity_normalized, segment_active
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT (segment_observation_id) DO NOTHING""",
            [
                seg_id,
                obs_id,
                seg.source_market_code,
                seg.mic,
                seg.market_family,
                seg.segment_raw,
                seg.member_code,
                _normalize_member_code(seg.member_code),
                seg.capacity_raw,
                getattr(seg, "capacity_normalized", None),
                seg.segment_active,
            ],
        )

    # ---- venues ---------------------------------------------------------

    def replace_venues(
        self, venues: Iterable[VenueRecord], snapshot_id: str, publication_date: str
    ) -> None:
        self.con.execute("DELETE FROM venue")
        self.con.executemany(
            """INSERT INTO venue VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    v.mic,
                    v.operating_mic,
                    v.mic_type,
                    v.market_name,
                    v.legal_entity_name,
                    v.operator_lei,
                    v.market_category,
                    v.acronym,
                    v.country,
                    v.city,
                    v.website,
                    v.status,
                    v.creation_date,
                    v.last_update_date,
                    v.last_validation_date,
                    v.expiry_date,
                    v.comments,
                    publication_date,
                    snapshot_id,
                )
                for v in venues
            ],
        )

    # ---- helpers --------------------------------------------------------

    def _rows(self, q: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        cur = self.con.execute(q, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]

    def query(self, q: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        return self._rows(q, params)

    def df(self, q: str, params: list[Any] | None = None) -> Any:
        return self.con.execute(q, params or []).fetchdf()

    def arrow(self, q: str, params: list[Any] | None = None) -> Any:
        return self.con.execute(q, params or []).to_arrow_table()
