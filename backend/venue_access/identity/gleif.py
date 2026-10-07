"""GLEIF REST API client with a persistent JSON cache.

v0.1 deliberately uses the REST API + disk cache rather than the multi-GB
Golden Copy: the participant set is O(10^3) entities and API responses are
self-contained evidence. See docs/adr/003-entity-resolution.md.
"""

from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
import time

import httpx

BASE = "https://api.gleif.org/api/v1"
UA = {"User-Agent": "venue-access-eu/0.1 (+open-data; contact in README)"}


class GleifClient:
    def __init__(self, cache_dir: Path | None = None, delay: float = 0.05):
        self.cache_dir = cache_dir
        self.delay = delay
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(headers=UA, timeout=30.0)

    # -- cache -------------------------------------------------------------

    def _cache_path(self, key: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / f"{sha1(key.encode()).hexdigest()}.json"

    def _cached(self, key: str) -> dict | None:
        p = self._cache_path(key)
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def _store(self, key: str, data: dict) -> None:
        p = self._cache_path(key)
        if p:
            p.write_text(json.dumps(data), encoding="utf-8")

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict:
        key = path + "?" + json.dumps(params or {}, sort_keys=True)
        hit = self._cached(key)
        if hit is not None:
            return hit
        time.sleep(self.delay)
        resp = self._client.get(BASE + path, params=params)
        if resp.status_code == 404:
            data = {"data": []}
        else:
            resp.raise_for_status()
            data = resp.json()
        self._store(key, data)
        return data

    # -- domain ------------------------------------------------------------

    def get_lei(self, lei: str) -> dict | None:
        data = self._get(f"/lei-records/{lei}")
        rec = data.get("data")
        if isinstance(rec, dict):
            return rec
        if isinstance(rec, list):
            return rec[0] if rec else None
        return None

    def search_by_name(self, name: str, size: int = 10) -> list[dict]:
        data = self._get(
            "/lei-records",
            {"filter[entity.names]": name, "page[size]": str(size)},
        )
        return list(data.get("data") or [])

    def autocomplete(self, name: str, size: int = 10) -> list[dict]:
        data = self._get(
            "/autocompletions",
            {"field": "entity.legalName", "q": name, "page[size]": str(size)},
        )
        out = []
        for item in data.get("data") or []:
            lei = (item.get("relationships", {}).get("lei-records", {})
                   .get("data", {}).get("id"))
            if lei:
                rec = self.get_lei(lei)
                if rec:
                    out.append(rec)
        return out

    def direct_parent(self, lei: str) -> dict | None:
        data = self._get(f"/lei-records/{lei}/direct-parent")
        rec = data.get("data")
        return rec if isinstance(rec, dict) else (rec[0] if rec else None)

    def ultimate_parent(self, lei: str) -> dict | None:
        data = self._get(f"/lei-records/{lei}/ultimate-parent")
        rec = data.get("data")
        return rec if isinstance(rec, dict) else (rec[0] if rec else None)

    def direct_children(self, lei: str) -> list[dict]:
        data = self._get(f"/lei-records/{lei}/direct-children")
        return list(data.get("data") or [])

    def ultimate_children(self, lei: str) -> list[dict]:
        data = self._get(f"/lei-records/{lei}/ultimate-children")
        return list(data.get("data") or [])

    # -- extraction helpers ------------------------------------------------

    @staticmethod
    def legal_name(rec: dict) -> str:
        try:
            names = rec["attributes"]["entity"]["legalName"]
            if isinstance(names, dict):
                return names.get("name", "")
            return str(names)
        except (KeyError, TypeError):
            return ""

    @staticmethod
    def country(rec: dict) -> str | None:
        try:
            return rec["attributes"]["entity"]["legalAddress"]["country"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def city(rec: dict) -> str | None:
        try:
            return rec["attributes"]["entity"]["legalAddress"]["city"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def address_str(rec: dict) -> str:
        try:
            a = rec["attributes"]["entity"]["legalAddress"]
            return " ".join(
                str(p)
                for p in [
                    " ".join(a.get("addressLines") or []),
                    a.get("city"), a.get("postalCode"), a.get("country"),
                ]
                if p
            )
        except (KeyError, TypeError):
            return ""

    @staticmethod
    def entity_status(rec: dict) -> str | None:
        try:
            return rec["attributes"]["entity"]["status"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def registration_status(rec: dict) -> str | None:
        try:
            return rec["attributes"]["registration"]["registrationStatus"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def other_names(rec: dict) -> list[str]:
        out: list[str] = []
        try:
            ent = rec["attributes"]["entity"]
            for key in ("otherEntityNames", "transliteratedOtherEntityNames"):
                for n in ent.get(key) or []:
                    if isinstance(n, dict):
                        out.append(n.get("name", ""))
                    else:
                        out.append(str(n))
        except (KeyError, TypeError):
            pass
        return [n for n in out if n]


def now_utc() -> datetime:
    return datetime.now(UTC)
