"""Synthetic demo dataset for public display.

The real aggregated dataset stays internal while source redistribution rights
are under review (ADR 007). This module builds a fully synthetic dataset that
exercises the real pipeline end to end: snapshots, the anomaly gate, the
temporal engine and publish. Firm names, LEIs and member codes are invented;
venue codes are ISO 10383 MICs (identifiers only, no venue-supplied data).

The output is deterministic for a given seed so the demo image is
reproducible and diffable.
"""

import csv
import io
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from venue_access.domain.enums import IdentityStatus, SnapshotStatus
from venue_access.domain.ids import lei_checksum_ok
from venue_access.domain.models import ParticipantRecord, SegmentRecord
from venue_access.history.temporal import recompute_history
from venue_access.identity.resolver import EntityResolver, ResolutionResult
from venue_access.ingest import _resolve_and_persist, load_catalog
from venue_access.sources.iso10383 import EXPECTED_COLUMNS, parse_mic_csv
from venue_access.storage.export import publish
from venue_access.storage.store import Store

DEMO_MARKER = "SYNTHETIC DEMO DATA"

# (mic, operating mic, country, city, description) — descriptions are generic
# on purpose; nothing here is copied from a venue publication.
VENUES: list[tuple[str, str, str, str, str]] = [
    ("XETR", "XETR", "DE", "FRANKFURT", "Frankfurt electronic cash venue"),
    ("XAMS", "XAMS", "NL", "AMSTERDAM", "Amsterdam regulated market"),
    ("XBRU", "XBRU", "BE", "BRUSSELS", "Brussels regulated market"),
    ("XDUB", "XDUB", "IE", "DUBLIN", "Dublin regulated market"),
    ("XLIS", "XLIS", "PT", "LISBON", "Lisbon regulated market"),
    ("XMIL", "XMIL", "IT", "MILAN", "Milan regulated market"),
    ("XOSL", "XOSL", "NO", "OSLO", "Oslo regulated market"),
    ("XPAR", "XPAR", "FR", "PARIS", "Paris regulated market"),
    ("BMEX", "BMEX", "ES", "MADRID", "Spanish exchanges group"),
    ("XMAD", "BMEX", "ES", "MADRID", "Madrid equity segment"),
    ("XBAR", "BMEX", "ES", "BARCELONA", "Barcelona equity segment"),
    ("XBIL", "BMEX", "ES", "BILBAO", "Bilbao equity segment"),
    ("XVAL", "BMEX", "ES", "VALENCIA", "Valencia equity segment"),
    ("XLON", "XLON", "GB", "LONDON", "London regulated market"),
]

SOURCE_VENUES: dict[str, list[tuple[str, str]]] = {
    "xetra-participants": [("XETR", "Cash")],
    "euronext-members": [
        (m, f)
        for m in ("XAMS", "XBRU", "XDUB", "XLIS", "XMIL", "XOSL", "XPAR")
        for f in ("Cash", "Derivatives")
    ],
    "bme-equity-members": [(m, "Equity") for m in ("XMAD", "XBAR", "XBIL", "XVAL")],
    "lse-member-directory": [("XLON", "Cash")],
}
# Sources that publish an LEI next to the member; the rest go through the
# (synthetic) name-matching resolver below.
SOURCE_HAS_LEI = {"xetra-participants", "lse-member-directory"}

_PREFIX = ["Alder", "Birch", "Cobalt", "Dunmore", "Elm", "Fjord", "Granite", "Harbor",
           "Iris", "Juniper", "Kestrel", "Linden", "Meridian", "Northgate", "Orchard",
           "Pinecrest", "Quarry", "Rowan", "Saltmarsh", "Tidewater", "Umber", "Vale",
           "Westbrook", "Yarrow", "Zephyr"]  # fmt: skip
_SUFFIX = [("Securities", "GmbH", "DE"), ("Capital Markets", "S.A.", "FR"),
           ("Bank", "N.V.", "NL"), ("Brokerage", "S.p.A.", "IT"), ("Trading", "Ltd", "GB"),
           ("Valores", "S.V., S.A.", "ES"), ("Markets", "AB", "SE"),
           ("Finance", "AS", "NO")]  # fmt: skip


def synthetic_lei(rng: random.Random) -> str:
    """A checksum-valid LEI under the reserved-looking DEMO prefix."""
    body = "DEMO00" + "".join(rng.choice("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(12))
    digits = "".join(str(int(c, 36)) for c in body + "00")
    check = 98 - int(digits) % 97
    lei = f"{body}{check:02d}"
    if not lei_checksum_ok(lei):
        raise ValueError(f"generated LEI failed checksum: {lei}")
    return lei


def _mic_csv() -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPECTED_COLUMNS, quoting=csv.QUOTE_ALL)
    w.writeheader()
    for mic, op, cc, city, desc in VENUES:
        row = {c: "" for c in EXPECTED_COLUMNS}
        row.update(
            {
                "MIC": mic,
                "OPERATING MIC": op,
                "OPRT/SGMT": "OPRT" if mic == op else "SGMT",
                "MARKET NAME-INSTITUTION DESCRIPTION": f"{desc} (demo)",
                "ISO COUNTRY CODE (ISO 3166)": cc,
                "CITY": city,
                "STATUS": "ACTIVE",
                "LAST UPDATE DATE": "20260101",
                "COMMENTS": DEMO_MARKER,
            }
        )
        w.writerow(row)
    return buf.getvalue().encode()


class _Firm:
    def __init__(self, idx: int, rng: random.Random) -> None:
        pre = _PREFIX[idx % len(_PREFIX)]
        kind, form, cc = _SUFFIX[(idx * 7 + idx // len(_PREFIX)) % len(_SUFFIX)]
        self.name = f"{pre} {kind} {form}".upper()
        self.country = cc
        self.lei = synthetic_lei(rng)
        self.key = f"demo:{idx:03d}"
        self.sources: dict[str, list[tuple[str, str]]] = {}
        for src, venues in SOURCE_VENUES.items():
            if rng.random() < (0.55 if src != "euronext-members" else 0.45):
                k = max(1, rng.randint(1, len(venues)))
                self.sources[src] = sorted(rng.sample(venues, k))
        self.code = f"{rng.randint(1000, 99999):05d}"


class _NoGleif:
    """The demo never contacts GLEIF; synthetic LEIs have no golden-copy record."""

    def get_lei(self, lei: str) -> None:
        return None


class _DemoResolver:
    """Deterministic stand-in for GLEIF matching.

    Sources that publish an LEI resolve exactly. The rest mimic the real
    resolver's outcome mix: most match on legal name + country, a few stay
    fuzzy candidates (never merged automatically) or unresolved.
    """

    gleif = _NoGleif()

    def __init__(self, roster: list[_Firm], rng: random.Random) -> None:
        self.firms = {f.key: f for f in roster}
        self.outcome = {
            f.key: rng.choices(["name", "fuzzy", "none"], weights=[86, 6, 8])[0] for f in roster
        }

    def resolve(self, source_id: str, rec: ParticipantRecord) -> ResolutionResult:
        f = self.firms[rec.source_participant_key]
        if rec.source_lei:
            return ResolutionResult(
                status=IdentityStatus.EXACT_SOURCE_LEI,
                lei=rec.source_lei,
                method="source_lei",
                confidence=1.0,
                evidence="LEI published by the source next to the member",
                canonical_name=f.name,
                country=f.country,
            )
        outcome = self.outcome[f.key]
        if outcome == "name":
            return ResolutionResult(
                status=IdentityStatus.EXACT_NAME_COUNTRY,
                lei=f.lei,
                method="exact_name_country",
                confidence=0.97,
                candidate_count=1,
                candidates=[f.lei],
                evidence="normalized legal name + country match a single (synthetic) LEI record",
                canonical_name=f.name,
                country=f.country,
            )
        if outcome == "fuzzy":
            return ResolutionResult(
                status=IdentityStatus.FUZZY_CANDIDATE,
                lei=f.lei,
                method="fuzzy_name",
                confidence=0.71,
                candidate_count=2,
                candidates=[f.lei],
                evidence="similar name, country mismatch: kept as a review candidate",
            )
        return ResolutionResult(
            status=IdentityStatus.UNRESOLVED,
            method="no_candidate",
            evidence="no LEI record matched the normalized name",
        )


def _record(f: _Firm, src: str, code_override: str | None = None) -> ParticipantRecord:
    # a re-issued member code affects one segment, as it would in practice
    segs = [
        SegmentRecord(
            source_market_code=mic,
            mic=mic,
            market_family=fam,
            member_code=(code_override if code_override and i == 0 else None) or f.code,
        )
        for i, (mic, fam) in enumerate(f.sources[src])
    ]
    return ParticipantRecord(
        source_participant_key=f.key,
        raw_name=f.name,
        normalized_name=f.name,
        country=f.country,
        source_lei=f.lei if src in SOURCE_HAS_LEI else None,
        membership_type_raw="Member",
        membership_type_normalized="MEMBER",
        segments=segs,
    )


def build_demo(
    db_path: Path,
    out_dir: Path,
    *,
    seed: int = 1756,
    firms: int = 120,
    weeks: int = 12,
    start: datetime = datetime(2026, 7, 6, 6, 0, tzinfo=UTC),
) -> dict[str, Any]:
    """Build a synthetic dataset into ``db_path`` and publish into ``out_dir``."""
    if db_path.exists():
        db_path.unlink()
    rng = random.Random(seed)  # noqa: S311 - deterministic synthetic data, not security
    roster = [_Firm(i, rng) for i in range(firms)]
    # duck-typed: only .gleif and .resolve() are used by _resolve_and_persist
    resolver = cast(EntityResolver, _DemoResolver(roster, rng))
    store = Store(db_path)
    try:
        for s in load_catalog().values():
            store.upsert_source(s)

        mic_snap = f"iso-10383-mic:{start.strftime('%Y%m%dT%H%M%S')}"
        venues = parse_mic_csv(_mic_csv())
        store.insert_snapshot(
            {
                "snapshot_id": mic_snap,
                "source_id": "iso-10383-mic",
                "retrieved_at": start,
                "record_count": len(venues),
                "snapshot_status": SnapshotStatus.VALIDATED.value,
                "parser_version": "demo",
            }
        )
        store.replace_venues(venues, mic_snap, "2026-01-01")

        # Scripted churn so every change type has examples.
        joiners = {f.key: rng.randint(2, weeks - 1) for f in rng.sample(roster, firms // 10)}
        leavers = {f.key: rng.randint(2, weeks - 3) for f in rng.sample(roster, firms // 12)}
        code_changes = {f.key: rng.randint(2, weeks - 1) for f in rng.sample(roster, firms // 15)}
        quarantine_week = weeks // 2

        for w in range(weeks):
            for si, src in enumerate(SOURCE_VENUES):
                day = start + timedelta(weeks=w, minutes=si * 7)
                snap = f"{src}:{day.strftime('%Y%m%dT%H%M%S')}"
                present = [
                    f
                    for f in roster
                    if src in f.sources
                    and joiners.get(f.key, 0) <= w
                    and not (f.key in leavers and w >= leavers[f.key])
                ]
                # One quarantined capture: a truncated download is rejected by
                # the anomaly gate and must not create absence events.
                if src == "euronext-members" and w == quarantine_week:
                    kept = present[: max(1, len(present) // 3)]
                    store.insert_snapshot(
                        {
                            "snapshot_id": snap,
                            "source_id": src,
                            "retrieved_at": day,
                            "record_count": len(kept),
                            "snapshot_status": SnapshotStatus.QUARANTINED.value,
                            "parser_version": "demo",
                            "validation_report": json.dumps(
                                {
                                    "reasons": ["record_drop>15%"],
                                    "metrics": {"records": len(kept), "previous": len(present)},
                                }
                            ),
                        }
                    )
                    continue
                records = [
                    _record(
                        f,
                        src,
                        f"{int(f.code) + 1:05d}"
                        if f.key in code_changes and w >= code_changes[f.key]
                        else None,
                    )
                    for f in present
                ]
                store.insert_snapshot(
                    {
                        "snapshot_id": snap,
                        "source_id": src,
                        "retrieved_at": day,
                        "record_count": len(records),
                        "segment_count": sum(len(r.segments) for r in records),
                        "snapshot_status": SnapshotStatus.FETCHED.value,
                        "parser_version": "demo",
                        "raw_sha256": f"{rng.getrandbits(256):064x}",
                    }
                )
                store.con.execute("BEGIN TRANSACTION")  # one per snapshot, as in ingest
                unresolved = _resolve_and_persist(store, src, snap, records, resolver)
                store.con.execute(
                    "UPDATE snapshot SET membership_count=?, unresolved_identity_count=? "
                    "WHERE snapshot_id=?",
                    [len(records), unresolved, snap],
                )
                store.set_snapshot_status(snap, SnapshotStatus.VALIDATED)
                store.con.execute("COMMIT")
                print(f"  week {w + 1}/{weeks} {src}: {len(records)} members", flush=True)

        history = recompute_history(store)
        manifest = publish(store, out_dir)
    finally:
        store.close()
    manifest["dataset_mode"] = "demo"
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return {"db": str(db_path), "firms": firms, "weeks": weeks, "history": history}
