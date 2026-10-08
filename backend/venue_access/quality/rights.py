"""Publication-rights gate: honest tracking of what each source's terms
permit. A RESTRICTED or UNCLEAR source never blocks internal processing,
but publish() tags the manifest so a public release cannot accidentally
claim rights it does not have."""

from pathlib import Path
from typing import Any

import yaml

RIGHTS_PATH = Path("data/curation/publication_rights.yml")

RIGHTS_ORDER = ("VERIFIED", "UNCLEAR", "RESTRICTED")


def load_rights(path: Path | None = None) -> dict[str, Any]:
    p = path or RIGHTS_PATH
    if not p.exists():
        return {"reviewed_at": None, "sources": {}}
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data


def publication_gate(rights: dict[str, Any]) -> dict[str, Any]:
    """Aggregate per-source statuses into a publish verdict."""
    sources: dict[str, Any] = rights.get("sources", {})
    worst = "VERIFIED" if sources else "UNCLEAR"
    for r in sources.values():
        s = r.get("status", "UNCLEAR")
        if RIGHTS_ORDER.index(s) > RIGHTS_ORDER.index(worst):
            worst = s
    return {
        "publication_status": {
            "VERIFIED": "PUBLIC_DATASET_OK",
            "UNCLEAR": "CODE_PUBLISHABLE_DATASET_REVIEW",
            "RESTRICTED": "CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY",
        }[worst],
        "worst_source_status": worst,
        "sources": {sid: r.get("status", "UNCLEAR") for sid, r in sources.items()},
        "reviewed_at": rights.get("reviewed_at"),
    }
