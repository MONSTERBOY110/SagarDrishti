"""Provenance records (TRD M1, feeding the agent's citation guarantee).

CONTRIBUTING.md: numbers enter an answer only via tool results, carrying dataset +
timestamp + float WMO id. That guarantee has to start at ingestion -- by the
time a value is a pixel or a spoken sentence it is far too late to work out
where it came from. So every derived store gets a provenance.json written
beside it, and the API echoes it on every response.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROVENANCE_FILE = "provenance.json"


def write_provenance(
    store: Path,
    *,
    source_id: str,
    title: str,
    citation: str,
    variables: list[str],
    source_url: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write provenance.json into (or beside) a derived store."""
    store = Path(store)
    target = store / PROVENANCE_FILE if store.is_dir() else store.with_suffix(".provenance.json")

    record: dict[str, Any] = {
        "source_id": source_id,
        "title": title,
        "citation": citation,
        "variables": variables,
        "source_url": source_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "produced_by": "SagarDrishti tools/preprocess.py",
        "host": platform.node(),
    }
    if extra:
        record.update(extra)

    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return target


def read_provenance(store: Path) -> dict[str, Any]:
    """Read a store's provenance, or {} if it has none.

    A store without provenance is usable but must never be cited, so callers
    check for an empty dict rather than getting a plausible-looking default.
    """
    store = Path(store)
    candidates = [store / PROVENANCE_FILE, store.with_suffix(".provenance.json")]
    for c in candidates:
        if c.is_file():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
    return {}
