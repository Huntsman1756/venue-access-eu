VENV := backend/.venv
PY := $(VENV)/Scripts/python
ifeq ($(OS),Windows_NT)
else
PY := $(VENV)/bin/python
endif

.PHONY: setup refresh test lint typecheck dev api frontend publish

setup:
	cd backend && uv venv --python 3.12 .venv && uv pip install -e ".[dev]" --python .venv/Scripts/python.exe
	cd frontend && pnpm install

refresh:
	$(PY) -m venue_access.cli.main refresh all
	$(PY) -m venue_access.cli.main resolve
	$(PY) -m venue_access.cli.main relationships
	$(PY) -m venue_access.cli.main publish

test:
	cd backend && $(PY) -m pytest tests/ -q

lint:
	cd backend && $(VENV)/Scripts/ruff check venue_access tests
	cd backend && $(VENV)/Scripts/ruff format --check venue_access tests

typecheck:
	cd backend && $(PY) -m mypy venue_access

dev: api frontend

api:
	cd backend && $(PY) -m uvicorn venue_access.api.app:app --reload --port 8000

frontend:
	cd frontend && pnpm dev

publish:
	$(PY) -m venue_access.cli.main publish
