# venue-access-eu

**Public evidence of observed European trading-venue membership.**

`venue-access-eu` answers: *"does this firm publicly appear as a member of
this European trading venue — and what is the evidence?"*

```bash
venue-access firm "Example Bank"
```

```text
Illustrative output (synthetic data — see the rights gate below)

EXAMPLE BANK S.A.
LEI: SYNTEST000000000AA97   Identity: EXACT_SOURCE_LEI

OBSERVED MEMBERSHIPS
Venue  Family       Member code    Type                  Evidence
XETR   Cash         TESTM1         Trading Participant   <snapshot date>
XAMS   Cash         00000001       Trading Member (T)    <snapshot date>
...

OTHER CHECKED VENUES
XLON   Cash          NOT_OBSERVED
XMAD   Equity        OBSERVED
```

## What "observed" means — and what it does not

This dataset records **observations** of membership captured from official
venue sources at a point in time. It is *not* a complete database of every
way a firm can access a European market.

- **OBSERVED** — positive evidence in a captured, successfully processed
  official source.
- **NOT_OBSERVED** — no matching membership was found in a successfully
  processed source whose documented scope covers the question. It does
  **not** prove absence of direct or indirect access.
- **UNKNOWN** — the source was partial/failed/quarantined, identity could
  not be resolved, or the scope does not permit inference.

Membership ≠ access ≠ routing ≠ clearing ≠ settlement ≠ DMA/DEA ≠
sponsored access ≠ broker relationship. Only observed membership is
modelled.

## Coverage (v0.1)

| Source | Venues | Identity |
|---|---|---|
| Xetra trading participants | XETR | source LEI |
| Euronext members | XAMS XBRU XDUB XLIS XMIL XOSL XPAR (cash+derivatives) | GLEIF resolution |
| BME equity members | XMAD XBAR XBIL XVAL MABX XLAT | GLEIF resolution |
| LSE member firm directory | XLON | source LEI |
| ISO 10383 | venue reference dimension | — |
| GLEIF | legal-entity identity + Level-2 relationships | — |

Roadmap (explicitly out of v0.1): Cboe, Aquis, Athens, Nasdaq Nordic/Baltic,
SIX, Warsaw, Eurex, CCP membership, LSE information-sheet event stream.

## Quick start

```bash
git clone https://github.com/Huntsman1756/venue-access-eu && cd venue-access-eu
make setup          # uv venv + backend deps, pnpm install
make refresh        # fetch → parse → gate → resolve → publish
make test           # backend test suite
make dev            # API :8000 + frontend :3000
```

CLI: `venue-access firm|venue|overlap|country|changes|sources|snapshots|
unresolved|identity|refresh|validate|publish|status` — `--json` where useful.

API (read-only, `/api/v1`): `/meta /sources /snapshots /venues /venues/{mic}
/participants /participants/{id}/memberships|evidence|relationships
/memberships /overlap /changes /search /stats /health /ready`.

## Architecture

Raw immutable snapshots (SHA-256, retrieved_at) → deterministic parsers →
anomaly gate (>15% record/segment drop, zero rows, schema change →
QUARANTINED) → normalization → deterministic GLEIF entity resolution →
DuckDB observations → derived intervals/change events → locally generated
Parquet + DuckDB artifacts + FastAPI + Next.js.

Snapshots are never overwritten. `first_seen_at` is an observation date,
never a membership start date. A disappearance needs two consecutive good
snapshots to be confirmed.

## Development

```bash
cd backend
pytest tests/            # unit+contract+temporal+invariants (fixtures, offline)
pytest -m live           # hits real sources (scheduled, not per-PR)
ruff check venue_access  # lint
mypy venue_access        # strict types
```

Docs: [sources](docs/sources.md) · [methodology](docs/methodology.md) ·
[architecture](docs/architecture.md) · [data dictionary](docs/data-dictionary.md)
· [ADRs](docs/adr/) · [prior art](docs/prior-art.md)

## License

Code: MIT (see LICENSE).

The aggregated membership dataset is **not redistributed publicly** while
source-specific redistribution and public-display rights remain under review
(`CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY` in `data/curation/
publication_rights.yml`). Raw snapshots and derived data files are never
committed; test fixtures are synthetic. Users may generate data locally
subject to the applicable source terms (see docs/licenses.md, ADR 007).
