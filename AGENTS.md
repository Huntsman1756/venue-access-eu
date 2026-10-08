# AGENTS.md — venue-access-eu

Evidence-backed observations of European trading-venue membership.
Backend: Python 3.12 pipeline + FastAPI over DuckDB (`backend/`).
Frontend: Next.js 16 client-fetching UI (`frontend/`, read `frontend/AGENTS.md`
before touching Next APIs). Public demo: `venues.h1756.es` (see `deploy/`).

## Commands (run from repo root; Windows paths handled by the Makefile)

| Task | Command |
|---|---|
| Setup | `make setup` |
| Backend tests (offline) | `make test` — or one file: `cd backend && .venv/Scripts/python -m pytest tests/test_api.py -q` |
| Lint / format / types | `make lint` · `make typecheck` (mypy strict) |
| Frontend checks | `cd frontend && pnpm exec tsc --noEmit && pnpm lint && pnpm build` |
| Synthetic dataset | `make demo` → `backend/demo/venue_access.duckdb` |
| Run on demo data | `make dev-demo` (API :8000 + web :3000) |
| Real refresh (network) | `make refresh` — hits venue sites; never in CI per-PR |
| Images | `docker build --target api .` / `--target web .` |

Definition of done for a change: ruff + ruff format + mypy clean, affected
pytest files green, `tsc`/`lint` clean if frontend touched. Run the slow
temporal/invariant tests when touching `history/`, `identity/`, `ingest.py`
or `storage/`.

## Invariants — do not break

1. **Observations, not memberships** (ADR 002). `first_seen_at` is an
   observation date. Never invent valid_from/valid_to.
2. **Absence** needs two consecutive good snapshots (ADR 005). Quarantined
   snapshots never create absence events. NOT_OBSERVED ≠ "no access".
3. **History is anchored on `source_participant_id`** (ADR 008). Identity
   resolution changes emit `IDENTITY_RESOLUTION_CHANGED` only; they must
   never create or end membership intervals. `test_invariants.py` guards it.
4. **No fuzzy auto-merge** (ADR 003). FUZZY_CANDIDATE stays unresolved.
5. **Determinism**: history is rebuilt from observations; timestamps that
   order decisions come from snapshot `retrieved_at`, not wall clock (a
   wall-clock stamp caused a date-dependent test failure on 2026-10-08).
6. **Publication rights** (ADR 007): the real dataset is
   `CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY`. Never commit raw snapshots,
   derived data, `*.duckdb`, or upload them as CI artifacts. Public
   instances serve `venue_access/demo.py` output only, until
   `backend/data/curation/publication_rights.yml` says otherwise.
7. **Test fixtures are synthetic** (`SYNTHETIC`/`SYNTEST` markers enforced).

## Performance notes (DuckDB)

- Wrap bulk writes in one transaction: autocommit costs a durable commit per
  statement (~250 ms each on a busy Windows disk vs ~6 ms in a transaction).
- `storage/store.py` short-circuits DuckDB's per-query pandas import probe
  when pandas is absent; keep pandas out of runtime deps or remove that shim.
- Use `to_arrow_table()` (not the deprecated `fetch_arrow_table()`).

## Repo conventions

- Mixed line endings in history: preserve each file's existing EOL. On
  Windows Git Bash, `sed -i` silently converts CRLF→LF; prefer the editor
  tools or Python with `newline=""`.
- Code and docs in English. Decisions with lasting impact get an ADR in
  `docs/adr/` and a `CHANGELOG.md` entry.
- Workspace rules (scratch in `F:\Temp\…`, worktrees under
  `F:\AgentState\worktrees\venue-access-eu\…`) come from `F:\_Proyectos\AGENTS.md`.

## Deployment boundaries

`deploy/release.sh` builds, ships and starts the stack on the shared VPS.
Running `ship`/`up`/`rollback` touches production: only with explicit
approval from the owner in the current session. Server operations follow
`F:\_Proyectos\h1756.es` (private ops repo).

## Agent tooling

Pi + Gentle Shell + Ponytail are installed project-locally (`.pi/`, template
`Huntsman1756/gentle-shell-_ponytail_Pi_NAN`). Activate with
`. .\.pi\bin\activate.ps1` then `pi --stack-check`. Runtime trees under
`.pi/stack-runtime/` are gitignored; `.pi/settings.json` and
`.pi/extensions/` are versioned.
