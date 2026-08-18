
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FILES = [
    Path.home() / "Documents" / "JARVIS_Trading" / "scalping_research_latest_v8.json",
    Path.home() / "Documents" / "JARVIS_Trading" / "scalping_research_latest_v7.json",
    Path.home() / "Documents" / "JARVIS_Trading" / "scalping_research_latest_v6.json",
]


class ResearchGate:
    """
    Strict research gate.

    VALIDATED is accepted only when the stored research record explicitly says
    it is validated. This module never promotes UNVALIDATED to VALIDATED.
    """

    def load(self):
        for p in DEFAULT_FILES:
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    return {"success": True, "path": str(p), "data": data}
                except Exception:
                    continue
        return {"success": False, "records": []}

    @staticmethod
    def records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") or payload
        records = data.get("results", data.get("records", data.get("edges", [])))
        return records if isinstance(records, list) else []

    def validated(self):
        loaded = self.load()
        if not loaded.get("success"):
            return loaded
        recs = self.records(loaded)
        validated = [
            r for r in recs
            if bool(r.get("validated"))
            or str(r.get("status", "")).upper() == "VALIDATED"
        ]
        return {
            "success": True,
            "path": loaded["path"],
            "validated": validated,
            "validated_count": len(validated),
        }

    def authorize(self, symbol: str, strategy: str):
        result = self.validated()
        for r in result.get("validated", []):
            if (
                str(r.get("symbol", "")).upper() == symbol.upper()
                and str(r.get("strategy", "")).upper() == strategy.upper()
            ):
                return {
                    "eligible": True,
                    "reason": "Explicit VALIDATED research record found.",
                    "record": r,
                }
        return {
            "eligible": False,
            "reason": "No explicit VALIDATED research edge for this symbol/strategy.",
            "available_validated_count": result.get("validated_count", 0),
        }
