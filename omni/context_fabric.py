"""Read-only context fabric for JARVIS V8 executive reasoning.

The fabric gathers bounded local state from existing JARVIS subsystems without
creating broker orders, mutating portfolio policy, or changing memory records.
It is designed to give planners one coherent view instead of making every agent
reconstruct context independently.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from config import HYBRID_MEMORY_DB, MISSION_STATE_FILE
from omni.conversation_turns import conversation_turns


ROOT = Path(__file__).resolve().parents[1]


def _safe(name: str, function: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"success": True, "name": name, "data": function()}
    except Exception as exc:
        return {
            "success": False,
            "name": name,
            "error": f"{type(exc).__name__}: {exc}"[:400],
        }


def _memory_summary() -> dict[str, Any]:
    path = Path(HYBRID_MEMORY_DB)
    result: dict[str, Any] = {
        "exists": path.exists(),
        "records": 0,
        "kinds": {},
        "read_only": True,
    }
    if not path.exists():
        return result
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
    try:
        row = connection.execute("SELECT COUNT(*) FROM memories").fetchone()
        result["records"] = int(row[0]) if row else 0
        rows = connection.execute(
            "SELECT kind, COUNT(*) FROM memories GROUP BY kind ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall()
        result["kinds"] = {str(kind): int(count) for kind, count in rows}
    finally:
        connection.close()
    return result


def _mission_summary() -> dict[str, Any]:
    path = Path(MISSION_STATE_FILE)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("Mission state is not an object.")
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return {"mission_count": 0, "latest": None, "read_only": True}
    latest = dict(state.get("latest_mission") or {})
    return {
        "mission_count": len(state.get("missions") or []),
        "latest": {
            "id": latest.get("id"),
            "title": latest.get("title"),
            "status": latest.get("status"),
            "selected_agents": latest.get("selected_agents") or [],
        } if latest else None,
        "read_only": True,
    }


def _paper_summary() -> dict[str, Any]:
    from workstation.paper_trading_desk import paper_desk

    state = paper_desk.snapshot()
    return {
        "open_count": int(state.get("open_count") or 0),
        "total_pnl": float(state.get("total_pnl") or 0.0),
        "equity": float(state.get("equity") or 0.0),
        "risk_at_stops": float(state.get("risk_at_stops") or 0.0),
        "risk_locks": list(state.get("risk_locks") or []),
        "paper_only": True,
        "live_execution": False,
    }


def snapshot(query: str = "", *, include_market_context: bool | None = None) -> dict[str, Any]:
    """Return bounded current context for executive planning.

    Heavy trading context is included only when the request appears market
    related, unless explicitly requested by the caller.
    """

    from omni.workspace_command_center import snapshot as workspace_snapshot
    from omni.mission_queue import MISSION_QUEUE

    text = " ".join(str(query or "").lower().split())
    market_related = any(
        token in text
        for token in (
            "trade", "trading", "market", "nifty", "banknifty", "sensex", "btc",
            "bitcoin", "eth", "crude", "gold", "portfolio", "paper", "option",
        )
    )
    if include_market_context is not None:
        market_related = bool(include_market_context)

    recent = conversation_turns.history(limit=3, useful_only=True)
    payload: dict[str, Any] = {
        "success": True,
        "version": "8.0",
        "query": str(query or "")[:1000],
        "conversation": {
            "latest": conversation_turns.latest(prefer_anchor=True),
            "recent": list(recent),
            "volatile_working_memory": True,
        },
        "workspaces": workspace_snapshot(),
        "missions": _mission_summary(),
        "mission_queue": MISSION_QUEUE.snapshot(limit=20),
        "memory": _safe("memory", _memory_summary),
        "paper": _safe("paper", _paper_summary) if market_related else {
            "success": True,
            "name": "paper",
            "data": {"included": False, "reason": "NON_MARKET_REQUEST"},
        },
        "policy": {
            "local_first": True,
            "context_mutation": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "external_actions": "APPROVAL_GATED",
        },
    }
    return payload


__all__ = ["snapshot"]
