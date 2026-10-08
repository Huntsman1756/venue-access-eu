ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python.exe
RUFF := backend/.venv/Scripts/ruff.exe
else
PY := backend/.venv/bin/python
RUFF := backend/.venv/bin/ruff
endif

.PHONY: setup refresh resolve test test-live lint typecheck api web dev publish demo api-demo dev-demo

setup:
	cd backend && uv venv --python 3.12 .venv
	cd backend && uv pip install -e ".[dev]" --python ../backend/.venv/Scripts/python.exe 2>/dev/null || cd backend && uv pip install -e ".[dev]"
	cd frontend && pnpm install

refresh:
	cd backend && ../$(PY) -m venue_access.cli.main refresh all
	cd backend && ../$(PY) -m venue_access.cli.main resolve
	cd backend && ../$(PY) -m venue_access.cli.main relationships
	cd backend && ../$(PY) -m venue_access.cli.main publish

test:
	cd backend && ../$(PY) -m pytest tests/ -q

test-live:
	cd backend && ../$(PY) -m pytest tests/ -m live -q

lint:
	cd backend && ../$(RUFF) check venue_access tests
	cd backend && ../$(RUFF) format --check venue_access tests

typecheck:
	cd backend && ../$(PY) -m mypy venue_access

api:
	cd backend && ../$(PY) -m uvicorn venue_access.api.app:app --reload --port 8000

web:
	cd frontend && pnpm dev

dev: api web

publish:
	cd backend && ../$(PY) -m venue_access.cli.main publish

# Synthetic dataset (what the public instance serves): no network, ~1-3 min.
demo:
	cd backend && ../$(PY) -m venue_access.cli.main demo

api-demo:
	cd backend && VENUE_ACCESS_DB=demo/venue_access.duckdb VENUE_ACCESS_MODE=demo ../$(PY) -m uvicorn venue_access.api.app:app --reload --port 8000

dev-demo: api-demo web
