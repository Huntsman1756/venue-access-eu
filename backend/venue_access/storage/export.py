"""Publication: export Parquet datasets + manifest + standalone DuckDB file."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from venue_access.domain.enums import SnapshotStatus
from venue_access.quality.rights import load_rights, publication_gate
from venue_access.storage.store import Store

SCHEMA_VERSION = "1.0.0"

DATASETS = {
    "sources": "SELECT * FROM source",
    "snapshots": "SELECT * FROM snapshot ORDER BY retrieved_at",
    "participants": "SELECT * FROM participant",
    "participant_aliases": "SELECT * FROM participant_alias",
    "venues": "SELECT * FROM venue",
    "memberships": """
        SELECT o.*, s.retrieved_at AS observed_at
        FROM membership_observation o JOIN snapshot s USING (snapshot_id)
    """,
    "membership_segments": """
        SELECT s.*, o.participant_id, o.snapshot_id
        FROM membership_segment_observation s
        JOIN membership_observation o USING (observation_id)
    """,
    "membership_intervals": "SELECT * FROM membership_interval",
    "entity_relationships": "SELECT * FROM entity_relationship",
    "change_events": "SELECT * FROM change_event ORDER BY observed_at",
    "identity_resolutions": "SELECT * FROM identity_resolution",
}


def publish(store: Store, out_dir: Path, publish_db: Path | None = None) -> dict[str, Any]:
    """Write parquet exports + manifest + quality report. Returns manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC)

    files: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for name, sql in DATASETS.items():
        table = store.arrow(sql)
        counts[name] = table.num_rows
        pq = out_dir / f"{name}.parquet"
        import pyarrow.parquet as papq  # type: ignore[import-untyped]

        papq.write_table(table, pq)
        h = sha256(pq.read_bytes()).hexdigest()
        files[name] = {"parquet": pq.name, "sha256": h, "rows": table.num_rows}
        csv_path = out_dir / f"{name}.csv"
        _write_csv(table, csv_path)
        files[name]["csv"] = csv_path.name

    # Mark good snapshots as published.
    store.con.execute(
        "UPDATE snapshot SET snapshot_status=? WHERE snapshot_status=?",
        [SnapshotStatus.PUBLISHED.value, SnapshotStatus.VALIDATED.value],
    )

    quality = quality_report(store)
    (out_dir / "quality-report.json").write_text(
        json.dumps(quality, indent=2, default=str), encoding="utf-8"
    )

    manifest = {
        "dataset_version": generated_at.strftime("%Y-%m-%d"),
        "generated_at": generated_at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "files": files,
        "record_counts": counts,
        "quality_status": quality["status"],
        "quality": quality,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    if publish_db is not None:
        # Export a standalone duckdb file for distribution.
        publish_db.parent.mkdir(parents=True, exist_ok=True)
        if publish_db.exists():
            publish_db.unlink()
        store.con.execute(f"EXPORT DATABASE '{publish_db.parent / '_export_tmp'}' (FORMAT PARQUET)")
        import shutil

        tmp = publish_db.parent / "_export_tmp"
        import duckdb

        pub = duckdb.connect(str(publish_db))
        pub.execute(f"IMPORT DATABASE '{tmp}'")
        pub.close()
        shutil.rmtree(tmp)
        files["duckdb"] = {
            "file": publish_db.name,
            "sha256": sha256(publish_db.read_bytes()).hexdigest(),
        }
    return manifest


def _write_csv(table: Any, path: Path) -> None:
    import pyarrow.csv as pcsv  # type: ignore[import-untyped]

    pcsv.write_csv(table, path)


def quality_report(store: Store) -> dict[str, Any]:
    snaps = store.query(
        """SELECT source_id, snapshot_status, COUNT(*) AS n FROM snapshot
           GROUP BY source_id, snapshot_status"""
    )
    by_source: dict[str, dict[str, Any]] = {}
    for r in snaps:
        by_source.setdefault(r["source_id"], {})[r["snapshot_status"]] = r["n"]
    ids = store.query(
        """SELECT identity_status, COUNT(*) n FROM participant GROUP BY identity_status"""
    )
    alias_ids = store.query(
        """SELECT ir.status, COUNT(*) n FROM (
             SELECT source_id, source_participant_key, status FROM identity_resolution
             QUALIFY ROW_NUMBER() OVER
               (PARTITION BY source_id, source_participant_key
                ORDER BY resolved_at DESC) = 1
           ) ir GROUP BY ir.status"""
    )
    quarantined = sum(v.get("QUARANTINED", 0) for v in by_source.values())
    published = sum(v.get("PUBLISHED", 0) + v.get("VALIDATED", 0) for v in by_source.values())
    totals = {
        "participants": store.query("SELECT COUNT(*) c FROM participant")[0]["c"],
        "memberships": store.query("SELECT COUNT(*) c FROM membership_observation")[0]["c"],
        "segments": store.query("SELECT COUNT(*) c FROM membership_segment_observation")[0]["c"],
        "venues": store.query("SELECT COUNT(*) c FROM venue")[0]["c"],
        "lei_resolved": store.query("SELECT COUNT(*) c FROM participant WHERE lei IS NOT NULL")[0][
            "c"
        ],
    }
    identity_counts = {r["identity_status"]: r["n"] for r in ids}
    alias_counts = {r["status"]: r["n"] for r in alias_ids}
    alias_total = store.query("SELECT COUNT(*) c FROM participant_alias")[0]["c"]
    # The identity taxonomy must be a partition: every participant and every
    # alias carries exactly one status, so counts must sum to their totals.
    checks = {
        "identity_partition_closed": sum(identity_counts.values()) == totals["participants"],
        "alias_partition_closed": sum(alias_counts.values()) == alias_total,
    }
    status = "PASS" if (quarantined == 0 or published > 0) and all(checks.values()) else "REVIEW"
    # Publication rights are tracked honestly: unclear/restricted sources
    # never block internal use, but the report surfaces the gate so a public
    # dataset release requires explicit clearance per source.
    rights = publication_gate(load_rights())
    return {
        "status": status,
        "publication_rights": rights,
        "snapshots_by_source": by_source,
        "identity_counts": identity_counts,
        "alias_counts": alias_counts,
        "checks": checks,
        "totals": totals,
    }
