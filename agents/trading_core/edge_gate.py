
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_EDGE_DB = Path.home() / "Documents" / "JARVIS_Trading" / "research_edge_database_v2.json"


def load_edge_database(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or DEFAULT_EDGE_DB)
    if not target.exists():
        return {"success": False, "path": str(target), "records": []}

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"success": False, "path": str(target), "records": [], "error": str(exc)}

    records = payload.get("edges", payload.get("records", []))
    if not isinstance(records, list):
        records = []

    return {"success": True, "path": str(target), "records": records}


def find_edge(
    symbol: str,
    strategy: str,
    database: dict[str, Any],
) -> dict[str, Any]:
    symbol = symbol.upper()
    strategy = strategy.upper()

    matches = []
    for record in database.get("records", []):
        if not isinstance(record, dict):
            continue
        r_symbol = str(record.get("symbol", "")).upper()
        r_strategy = str(record.get("strategy", "")).upper()
        if r_symbol == symbol and r_strategy == strategy:
            matches.append(record)

    if not matches:
        return {
            "found": False,
            "eligible": False,
            "reason": "No validated research edge found for this symbol/strategy.",
        }

    # A research record is eligible only when explicitly validated.
    validated = [
        r for r in matches
        if bool(r.get("validated", r.get("status") == "VALIDATED"))
    ]

    if not validated:
        return {
            "found": True,
            "eligible": False,
            "reason": "Research records exist, but none are VALIDATED.",
            "records": matches,
        }

    return {
        "found": True,
        "eligible": True,
        "reason": "Validated research edge found.",
        "records": validated,
    }
