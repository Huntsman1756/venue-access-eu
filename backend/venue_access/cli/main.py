"""venue-access CLI."""

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from venue_access.history.temporal import recompute_history
from venue_access.identity.gleif import GleifClient
from venue_access.identity.resolver import EntityResolver, load_overrides
from venue_access.ingest import (
    ADAPTERS,
    load_catalog,
    refresh_mic,
    refresh_source,
)
from venue_access.queries import (
    changes_since,
    covered_mics,
    find_participant,
    firm_checked_venues,
    firm_evidence,
    firm_memberships,
    latest_good_snapshot_ids,
    overlap,
    source_health,
    stats,
    venue_participants,
)
from venue_access.storage.export import publish
from venue_access.storage.store import Store

app = typer.Typer(
    help="Public evidence of observed European trading-venue membership.", no_args_is_help=True
)
console = Console()
err = Console(stderr=True)

DATA_ROOT = Path("data")
DB_PATH = DATA_ROOT / "venue_access.duckdb"
OVERRIDES_PATH = DATA_ROOT / "curation" / "entity_overrides.yml"

NOT_OBSERVED_NOTE = (
    "NOT_OBSERVED means that no matching public membership was found in a "
    "successfully processed source within its documented scope. It does not "
    "prove absence of indirect market access."
)


def _store() -> Store:
    return Store(DB_PATH)


def _resolver() -> EntityResolver:
    gleif = GleifClient(cache_dir=DATA_ROOT / "cache" / "gleif")
    return EntityResolver(gleif, load_overrides(OVERRIDES_PATH))


def _out_json(obj: object) -> None:
    console.print_json(json.dumps(obj, default=str))


# ---------------------------------------------------------------- refresh


@app.command()
def refresh(
    source: str | None = typer.Argument(None, help="xetra|euronext|bme|lse|mic|all (default all)"),
    no_resolve: bool = typer.Option(False, "--no-resolve", help="skip GLEIF identity resolution"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Fetch, parse, gate and persist source snapshots."""
    store = _store()
    for s in load_catalog().values():
        store.upsert_source(s)
    name = (source or "all").lower()
    mapping = {
        "xetra": "xetra-participants",
        "euronext": "euronext-members",
        "bme": "bme-equity-members",
        "lse": "lse-member-directory",
        "mic": "iso-10383-mic",
    }
    targets = list(mapping.values()) if name == "all" else [mapping.get(name, name) or name]
    resolver = None if no_resolve else _resolver()
    results = []
    for t in targets:
        if t == "iso-10383-mic":
            results.append(refresh_mic(store, DATA_ROOT))
        elif t in ADAPTERS:
            results.append(refresh_source(store, ADAPTERS[t](), DATA_ROOT, resolver=resolver))
        else:
            err.print(f"unknown source: {t}")
            sys.exit(2)
    if json_out:
        _out_json(results)
    else:
        for r in results:
            status = r.get("status")
            color = {"VALIDATED": "green", "QUARANTINED": "red", "FAILED": "red"}.get(
                status or "", "yellow"
            )
            console.print(
                f"[{color}]{status:<12}[/{color}] {r.get('source')}  "
                f"{r.get('records', r.get('venues', ''))} records "
                f"{r.get('error', '')}"
            )
            for reason in r.get("reasons") or r.get("warnings") or []:
                console.print(f"    - {reason}")
    store.close()


@app.command()
def validate() -> None:
    """Run referential-integrity checks over the database."""
    store = _store()
    issues = []
    checks = {
        "segments_without_observation": """SELECT COUNT(*) c FROM membership_segment_observation s
               LEFT JOIN membership_observation o ON s.observation_id=o.observation_id
               WHERE o.observation_id IS NULL""",
        "observations_without_snapshot": """SELECT COUNT(*) c FROM membership_observation o
               LEFT JOIN snapshot s ON o.snapshot_id=s.snapshot_id
               WHERE s.snapshot_id IS NULL""",
        "observations_without_participant": """SELECT COUNT(*) c FROM membership_observation o
               LEFT JOIN participant p ON o.participant_id=p.participant_id
               WHERE p.participant_id IS NULL""",
        "invalid_lei_checksum": """SELECT COUNT(*) c FROM participant WHERE lei IS NOT NULL""",
        "mic_not_in_venue": """SELECT COUNT(*) c FROM (
                 SELECT DISTINCT mic FROM membership_segment_observation
                 WHERE mic IS NOT NULL) m
               LEFT JOIN venue v ON m.mic=v.mic WHERE v.mic IS NULL""",
    }
    for name, sql in checks.items():
        n = store.query(sql)[0]["c"]
        if name == "invalid_lei_checksum":
            from venue_access.domain.ids import lei_checksum_ok

            leis = [
                r["lei"] for r in store.query("SELECT lei FROM participant WHERE lei IS NOT NULL")
            ]
            n = sum(1 for x in leis if not lei_checksum_ok(x))
        status = "ok" if n == 0 else "FAIL"
        issues.append({"check": name, "violations": n, "status": status})
        console.print(
            f"[{'green' if n == 0 else 'red'}]{status:>4}[/{'green' if n == 0 else 'red'}] "
            f"{name}: {n}"
        )
    if any(i["status"] == "FAIL" for i in issues):
        sys.exit(1)


# ---------------------------------------------------------------- queries


@app.command()
def sources() -> None:
    """List registered sources and health."""
    store = _store()
    rows = source_health(store)
    t = Table("source", "scope", "latest", "latest good", "records", "status")
    for r in rows:
        t.add_row(
            r["source_id"],
            r["coverage_scope"],
            str(r["latest_attempt_at"] or "-")[:16],
            str(r["latest_good_at"] or "-")[:16],
            str(r["record_count"] or "-"),
            str(r["latest_status"] or "-"),
        )
    console.print(t)


@app.command()
def snapshots(source: str | None = typer.Argument(None)) -> None:
    """List snapshots (optionally per source)."""
    store = _store()
    rows = store.snapshots(source)
    t = Table("snapshot", "status", "records", "segments", "retrieved")
    for r in rows:
        t.add_row(
            r["snapshot_id"],
            r["snapshot_status"],
            str(r["record_count"] or 0),
            str(r["segment_count"] or 0),
            str(r["retrieved_at"])[:19],
        )
    console.print(t)


@app.command()
def firm(
    name: str = typer.Argument(..., help="firm name, LEI or member code"),
    lei: str | None = typer.Option(None, "--lei"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show observed venue memberships for a firm."""
    store = _store()
    matches = find_participant(store, lei or name)
    if not matches:
        err.print(f"no participant found for {name!r}")
        raise typer.Exit(2)
    p = matches[0]
    if len(matches) > 1 and not lei:
        console.print("[yellow]multiple matches; showing first. Use --lei to disambiguate:[/]")
        for m in matches[:8]:
            console.print(f"  {m['participant_id']:<42} {m['canonical_name']}")
    memberships = firm_memberships(store, p["participant_id"])
    checked = firm_checked_venues(store, p["participant_id"])
    if json_out:
        _out_json({"participant": p, "memberships": memberships, "checked": checked})
        return
    console.print(f"\n[bold]{p['canonical_name']}[/bold]")
    console.print(
        f"LEI: {p['lei'] or '-'}   Identity: {p['identity_status']}"
        f" ({p.get('identity_method') or '-'})"
    )
    t = Table("Venue", "Family", "Member code", "Type", "Evidence")
    for m in memberships:
        t.add_row(
            m["mic"] or "-",
            m["market_family"] or "-",
            m["member_code"] or "-",
            m["membership_type_raw"] or "-",
            str(m["retrieved_at"])[:10],
        )
    console.print("\n[bold]OBSERVED MEMBERSHIPS[/bold]")
    console.print(t)
    console.print("\n[bold]OTHER CHECKED VENUES[/bold]")
    seen = set()
    for c in checked:
        key = (c["mic"], c["market_family"])
        if key in seen or c["status"] == "OBSERVED":
            continue
        seen.add(key)
        color = "yellow" if c["status"] == "UNKNOWN" else "white"
        console.print(
            f"[{color}]{c['mic']:<6} {c['market_family']:<13} "
            f"{c['status']}  ({c['source_id']})[/{color}]"
        )
    console.print(f"\n[dim]{NOT_OBSERVED_NOTE}[/dim]")


@app.command()
def venue(mic: str) -> None:
    """List participants observed on a venue MIC."""
    store = _store()
    v = store.query("SELECT * FROM venue WHERE mic=?", [mic.upper()])
    if v:
        console.print(
            f"[bold]{v[0]['market_name']}[/bold] ({v[0]['mic']}, "
            f"{v[0]['country']}, {v[0]['mic_type']}, {v[0]['mic_status']})"
        )
    rows = venue_participants(store, mic)
    t = Table("Firm", "LEI", "Family", "Member code", "Identity")
    for r in rows:
        t.add_row(
            r["canonical_name"],
            r["lei"] or "-",
            r["market_family"] or "-",
            r["member_code"] or "-",
            r["identity_status"],
        )
    console.print(t)
    console.print(f"{len(rows)} participants")


@app.command("overlap")
def overlap_cmd(a: str, b: str) -> None:
    """Firms observed on both MIC A and MIC B."""
    store = _store()
    res = overlap(store, a, b)
    console.print(
        f"[bold]{a.upper()}[/bold]: {res['counts']['a']}   "
        f"[bold]{b.upper()}[/bold]: {res['counts']['b']}   "
        f"[bold]both[/bold]: {res['counts']['both']}"
    )
    t = Table("Firm", "LEI", f"{a.upper()} code", f"{b.upper()} code")
    for r in res["both"]:
        t.add_row(
            r["canonical_name"],
            r["lei"] or "-",
            r.get("member_code_a") or "-",
            r.get("member_code_b") or "-",
        )
    console.print(t)


@app.command()
def country(code: str) -> None:
    """Participants from an ISO country."""
    store = _store()
    rows = store.query(
        "SELECT * FROM participant WHERE country=? ORDER BY canonical_name", [code.upper()]
    )
    t = Table("Firm", "LEI", "Identity")
    for r in rows:
        t.add_row(r["canonical_name"], r["lei"] or "-", r["identity_status"])
    console.print(t)
    console.print(f"{len(rows)} participants")


@app.command()
def changes(since: str = typer.Option("1970-01-01", "--since")) -> None:
    """Observed membership changes since a date."""
    store = _store()
    rows = changes_since(store, since)
    t = Table("date", "firm", "key", "change", "old", "new")
    for r in rows:
        t.add_row(
            str(r["observed_at"]),
            r["canonical_name"],
            r["membership_key"],
            r["change_type"],
            str(r["old_value"] or "-")[:30],
            str(r["new_value"] or "-")[:30],
        )
    console.print(t)
    console.print(f"{len(rows)} changes")


@app.command()
def resolve(source: str | None = typer.Argument(None)) -> None:
    """(Re)run GLEIF entity resolution over persisted aliases."""
    from venue_access.identity.apply import apply_resolution

    store = _store()
    mapping = {
        "xetra": "xetra-participants",
        "euronext": "euronext-members",
        "bme": "bme-equity-members",
        "lse": "lse-member-directory",
    }
    counters = apply_resolution(store, _resolver(), mapping.get(source or "", source))
    console.print_json(json.dumps(counters))
    store.close()


@app.command()
def relationships() -> None:
    """Populate GLEIF Level-2 entity relationships for resolved LEIs."""
    from venue_access.identity.apply import populate_relationships

    store = _store()
    gleif = GleifClient(cache_dir=DATA_ROOT / "cache" / "gleif")
    console.print_json(json.dumps(populate_relationships(store, gleif)))
    store.close()


@app.command()
def unresolved() -> None:
    """Participants needing identity review."""
    store = _store()
    rows = store.query(
        """SELECT i.source_id, i.source_participant_key, a.raw_name,
                  i.status, i.confidence, i.candidates_json, i.evidence
           FROM identity_resolution i
           JOIN participant_alias a USING (source_id, source_participant_key)
           WHERE i.status IN ('UNRESOLVED','CONFLICT','FUZZY_CANDIDATE')
           ORDER BY i.status, i.source_id"""
    )
    t = Table("source", "raw name", "status", "conf", "candidates")
    for r in rows:
        cands = ", ".join(json.loads(r["candidates_json"] or "[]")[:3])
        t.add_row(
            r["source_id"], r["raw_name"][:40], r["status"], f"{r['confidence']:.2f}", cands[:40]
        )
    console.print(t)
    console.print(f"{len(rows)} unresolved/candidates")


@app.command()
def identity(participant_id: str) -> None:
    """Evidence for a participant's identity resolution."""
    store = _store()
    for r in firm_evidence(store, participant_id):
        console.print_json(json.dumps(r, default=str))


# ---------------------------------------------------------------- publish


@app.command(name="publish")
def publish_cmd(
    out: Path = typer.Option(DATA_ROOT / "published", "--out"),
) -> None:
    """Recompute history, export Parquet/CSV/DuckDB + manifest + report."""
    store = _store()
    hist = recompute_history(store)
    console.print(f"history: {hist}")
    manifest = publish(store, out, DATA_ROOT / "published" / "venue_access.duckdb")
    console.print_json(json.dumps(manifest["quality"], default=str))
    console.print(f"published -> {out}")


app.command(name="export")(publish_cmd)


@app.command()
def status() -> None:
    """Dataset overview."""
    store = _store()
    console.print_json(
        json.dumps(
            {
                "stats": stats(store),
                "sources": source_health(store),
                "latest_snapshots": latest_good_snapshot_ids(store),
                "covered_mics": {k: sorted(v) for k, v in covered_mics(store).items()},
            },
            default=str,
        )
    )


def main() -> None:  # console entrypoint
    app()


if __name__ == "__main__":
    main()
