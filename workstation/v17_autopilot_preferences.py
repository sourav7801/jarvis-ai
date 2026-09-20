"""Durable local preferences for the JARVIS V17 PAPER autopilot.

The file contains no broker credentials and grants no live-order authority.  It
only stores workstation behavior such as the requested autonomous-options
capital fraction and chart-first UI preference.
"""
from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREFERENCES_PATH = Path(
    os.getenv(
        "JARVIS_V17_PREFERENCES_PATH",
        str(PROJECT_ROOT / "data" / "runtime" / "v17_autopilot_preferences.json"),
    )
)
_LOCK = threading.RLock()

DEFAULTS: dict[str, Any] = {
    "one_touch_autopilot": True,
    "armed": False,
    "chart_first_options": True,
    "options_capital_fraction": 0.50,
    "start_workspaces": ["INTRADAY", "SWING", "INVESTMENT"],
    "daily_rebalance": False,
    "cross_workspace_top_up": False,
    "learning_enabled": True,
    "production_code_rewrite": False,
}


def _fraction(value: Any, default: float = 0.50) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    # Keep at least 5% so a spoken typo cannot silently create a zero-sized
    # mandate; 100% remains available when the user explicitly asks for it.
    return max(0.05, min(result, 1.0))


def load_preferences() -> dict[str, Any]:
    with _LOCK:
        payload: dict[str, Any] = {}
        try:
            if PREFERENCES_PATH.exists():
                raw = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    payload = raw
        except Exception:
            payload = {}
        result = {**DEFAULTS, **payload}
        result["options_capital_fraction"] = _fraction(
            result.get("options_capital_fraction")
        )
        workspaces = result.get("start_workspaces")
        if not isinstance(workspaces, list):
            workspaces = list(DEFAULTS["start_workspaces"])
        allowed = {"INTRADAY", "SWING", "INVESTMENT"}
        result["start_workspaces"] = [
            item for item in (str(v).upper() for v in workspaces) if item in allowed
        ] or list(DEFAULTS["start_workspaces"])
        # These are invariant safety semantics, not user-overridable switches.
        result["daily_rebalance"] = False
        result["cross_workspace_top_up"] = False
        result["production_code_rewrite"] = False
        result["armed"] = bool(result.get("armed", False))
        return result


def save_preferences(updates: dict[str, Any] | None = None) -> dict[str, Any]:
    updates = dict(updates or {})
    allowed = {
        "one_touch_autopilot",
        "chart_first_options",
        "options_capital_fraction",
        "start_workspaces",
        "learning_enabled",
        "armed",
    }
    unknown = set(updates) - allowed
    if unknown:
        raise ValueError("Unknown V17 preference: " + ", ".join(sorted(unknown)))

    with _LOCK:
        current = load_preferences()
        if "options_capital_fraction" in updates:
            current["options_capital_fraction"] = _fraction(
                updates["options_capital_fraction"]
            )
        for key in ("one_touch_autopilot", "chart_first_options", "learning_enabled", "armed"):
            if key in updates:
                current[key] = bool(updates[key])
        if "start_workspaces" in updates:
            workspaces = updates["start_workspaces"]
            if not isinstance(workspaces, list):
                raise ValueError("start_workspaces must be a list")
            allowed_workspaces = {"INTRADAY", "SWING", "INVESTMENT"}
            normalized = [
                item
                for item in (str(v).upper() for v in workspaces)
                if item in allowed_workspaces
            ]
            if not normalized:
                raise ValueError("At least one PAPER workspace must remain enabled")
            current["start_workspaces"] = list(dict.fromkeys(normalized))

        current["daily_rebalance"] = False
        current["cross_workspace_top_up"] = False
        current["production_code_rewrite"] = False
        PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = PREFERENCES_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(PREFERENCES_PATH)
        return current


__all__ = ["DEFAULTS", "PREFERENCES_PATH", "load_preferences", "save_preferences"]
