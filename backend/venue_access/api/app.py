"""FastAPI read-only surface over the published DuckDB dataset."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from venue_access.queries import (
    changes_since,
    firm_checked_venues,
    firm_evidence,
    firm_memberships,
    find_participant,
    overlap,
    source_health,
    stats,
    venue_participants,
)
from venue_access.storage.export import SCHEMA_VERSION
from venue_access.storage.store import Store

DB_PATH = Path(__import__("os").environ.get(
    "VENUE_ACCESS_DB", "data/venue_access.duckdb"))

DISCLAIMER = (
    "venue-access-eu records public observations from trading-venue sources. "
    "A missing observation does not prove that a firm lacks direct or indirect "
    "access to a venue. The dataset does not attempt to identify private "
    "routing arrangements, DMA/DEA relationships, sponsored-access arrangements "
    "unless explicitly published by the venue, or contractual broker "
    "relationships."
)


@asynccontextmanager
def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.store = Store(DB_PATH) if DB_PATH.exists() else None
    yield


app = FastAPI(
    title="venue-access-eu",
    version="0.1.0",
    description="Public evidence of observed European trading-venue membership.",
    lifespan=lifespan,
    root_path="/api/v1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def store(request: Request) -> Store:
    s = request.app.state.store
    if s is None:
        raise HTTPException(503, "dataset not loaded")
    return s


@app.middleware("http")
async def add_semantics_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Dataset-Semantics"] = "observed-membership"
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# ---------------------------------------------------------------- meta

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready(request: Request) -> JSONResponse:
    s = request.app.state.store
    if s is None or not DB_PATH.exists():
        return JSONResponse({"ready": False, "reason": "no dataset"}, status_code=503)
    try:
        s.query("SELECT 1 FROM participant LIMIT 1")
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ready": False, "reason": str(exc)}, status_code=503)
    return JSONResponse({"ready": True})


@app.get("/meta")
def meta(request: Request) -> dict:
    s = store(request)
    return {
        "schema_version": SCHEMA_VERSION,
        "semantics": DISCLAIMER,
        "stats": stats(s),
        "sources": source_health(s),
    }


# ---------------------------------------------------------------- sources

@app.get("/sources")
def list_sources(request: Request) -> list[dict]:
    return source_health(store(request))


@app.get("/sources/{source_id}")
def get_source(request: Request, source_id: str) -> dict:
    s = store(request)
    rows = s.query("SELECT * FROM source WHERE source_id=?", [source_id])
    if not rows:
        raise HTTPException(404, "source not found")
    rows[0]["health"] = [r for r in source_health(s)
                         if r["source_id"] == source_id]
    rows[0]["snapshots"] = s.snapshots(source_id, limit=30)
    return rows[0]


@app.get("/snapshots")
def list_snapshots(request: Request, source: str | None = None,
                   limit: int = Query(50, le=200)) -> list[dict]:
    return store(request).snapshots(source, limit)


# ---------------------------------------------------------------- venues

@app.get("/venues")
def list_venues(request: Request, covered: bool = False,
                country: str | None = None) -> list[dict]:
    s = store(request)
    q = "SELECT * FROM venue"
    params: list[str] = []
    if country:
        q += " WHERE country=?"
        params.append(country.upper())
    q += " ORDER BY mic"
    return s.query(q, params)


@app.get("/venues/{mic}")
def get_venue(request: Request, mic: str) -> dict:
    s = store(request)
    rows = s.query("SELECT * FROM venue WHERE mic=?", [mic.upper()])
    if not rows:
        raise HTTPException(404, "venue not found")
    v = rows[0]
    v["segments"] = s.query("SELECT * FROM venue WHERE operating_mic=?", [mic.upper()])
    v["participants"] = venue_participants(s, mic)
    return v


# ---------------------------------------------------------------- participants

@app.get("/participants")
def list_participants(request: Request,
                      q: str | None = None,
                      country: str | None = None,
                      lei: str | None = None,
                      identity_status: str | None = None,
                      limit: int = Query(50, le=200),
                      offset: int = 0) -> list[dict]:
    s = store(request)
    if q:
        return find_participant(s, q)
    sql = "SELECT * FROM participant WHERE 1=1"
    params: list[str] = []
    if country:
        sql += " AND country=?"; params.append(country.upper())
    if lei:
        sql += " AND UPPER(lei)=UPPER(?)"; params.append(lei)
    if identity_status:
        sql += " AND identity_status=?"; params.append(identity_status)
    sql += " ORDER BY canonical_name LIMIT ? OFFSET ?"
    params += [str(limit), str(offset)]
    return s.query(sql, params)


@app.get("/participants/{participant_id}")
def get_participant(request: Request, participant_id: str) -> dict:
    s = store(request)
    rows = s.query("SELECT * FROM participant WHERE participant_id=?",
                   [participant_id])
    if not rows:
        raise HTTPException(404, "participant not found")
    p = rows[0]
    p["aliases"] = s.query(
        "SELECT * FROM participant_alias WHERE participant_id=?", [participant_id])
    return p


@app.get("/participants/{participant_id}/memberships")
def participant_memberships(request: Request, participant_id: str) -> dict:
    s = store(request)
    return {
        "observed": firm_memberships(s, participant_id),
        "checked": firm_checked_venues(s, participant_id),
        "note": DISCLAIMER,
    }


@app.get("/participants/{participant_id}/evidence")
def participant_evidence(request: Request, participant_id: str) -> list[dict]:
    return firm_evidence(store(request), participant_id)


@app.get("/participants/{participant_id}/relationships")
def participant_relationships(request: Request, participant_id: str) -> list[dict]:
    s = store(request)
    return s.query(
        """SELECT * FROM entity_relationship
           WHERE child_participant_id=? OR child_lei=(
                 SELECT lei FROM participant WHERE participant_id=?)""",
        [participant_id, participant_id],
    )


# ---------------------------------------------------------------- memberships / changes / search

@app.get("/memberships")
def list_memberships(request: Request,
                     mic: str | None = None,
                     member_code: str | None = None,
                     family: str | None = None,
                     limit: int = Query(100, le=500),
                     offset: int = 0) -> list[dict]:
    s = store(request)
    sql = """SELECT p.canonical_name, p.lei, p.country, s.mic, s.market_family,
                    s.member_code, o.membership_type_normalized, o.snapshot_id
             FROM membership_segment_observation s
             JOIN membership_observation o ON s.observation_id=o.observation_id
             JOIN participant p ON p.participant_id=o.participant_id
             WHERE 1=1"""
    params: list[str] = []
    if mic:
        sql += " AND s.mic=?"; params.append(mic.upper())
    if member_code:
        sql += " AND UPPER(s.member_code)=UPPER(?)"; params.append(member_code)
    if family:
        sql += " AND s.market_family=?"; params.append(family)
    sql += " ORDER BY p.canonical_name LIMIT ? OFFSET ?"
    params += [str(limit), str(offset)]
    return s.query(sql, params)


@app.get("/overlap")
def get_overlap(request: Request, a: str, b: str) -> dict:
    return overlap(store(request), a, b)


@app.get("/changes")
def get_changes(request: Request,
                since: str = "1970-01-01") -> list[dict]:
    return changes_since(store(request), since)


@app.get("/search")
def search(request: Request, q: str = Query(min_length=2)) -> dict:
    s = store(request)
    participants = find_participant(s, q)
    venues = s.query(
        """SELECT * FROM venue WHERE UPPER(mic)=UPPER(?)
           OR UPPER(market_name) LIKE '%' || UPPER(?) || '%' LIMIT 10""",
        [q, q],
    )
    codes = s.query(
        """SELECT DISTINCT member_code, mic FROM membership_segment_observation
           WHERE UPPER(member_code) LIKE UPPER(?) || '%' LIMIT 10""",
        [q],
    )
    return {"firms": participants, "venues": venues, "member_codes": codes}


@app.get("/stats")
def get_stats(request: Request) -> dict:
    return stats(store(request))
