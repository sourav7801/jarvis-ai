"""Read-only context fabric for JARVIS executive reasoning.

V10 composes bounded conversation, mission, memory, World Model, Cognitive Bus,
Critic, Evidence Ledger, engineering, diagnostics and paper-governance context.
It never creates broker orders, mutates portfolio policy, edits production code,
or grants approval.
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
        return {"success": False, "name": name, "error": f"{type(exc).__name__}: {exc}"[:400]}


def _memory_summary() -> dict[str, Any]:
    path = Path(HYBRID_MEMORY_DB)
    result: dict[str, Any] = {"exists": path.exists(), "records": 0, "kinds": {}, "read_only": True}
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
            "id": latest.get("id"), "title": latest.get("title"),
            "status": latest.get("status"), "selected_agents": latest.get("selected_agents") or [],
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


def _world_context() -> dict[str, Any]:
    from omni.cognitive_bridges import install_cognitive_bridges
    from omni.world_model import WORLD_MODEL
    bridge = install_cognitive_bridges()
    refresh = WORLD_MODEL.refresh_local()
    world = WORLD_MODEL.snapshot(limit=40)
    return {"bridge": bridge, "refresh": refresh, "world": world}


def _cognitive_context() -> dict[str, Any]:
    from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS
    return COGNITIVE_EVENT_BUS.snapshot(limit=30)


def _critic_context() -> dict[str, Any]:
    from omni.critic_verifier import CRITIC_VERIFIER
    return CRITIC_VERIFIER.status()


def _evidence_context() -> dict[str, Any]:
    from omni.evidence_ledger import EVIDENCE_LEDGER
    return EVIDENCE_LEDGER.snapshot(limit=25)


def _engineering_context() -> dict[str, Any]:
    from omni.engineering_governance import ENGINEERING_GOVERNANCE
    return {"status": ENGINEERING_GOVERNANCE.status(), "repository": ENGINEERING_GOVERNANCE.inspect()}


def _system_context() -> dict[str, Any]:
    from omni.system_diagnostics import SYSTEM_DIAGNOSTICS
    return SYSTEM_DIAGNOSTICS.status()


def _trading_governance_context() -> dict[str, Any]:
    from omni.trading_intelligence.trading_governance_center import TRADING_GOVERNANCE_CENTER
    return TRADING_GOVERNANCE_CENTER.status()


def snapshot(query: str = "", *, include_market_context: bool | None = None) -> dict[str, Any]:
    """Return bounded current context for executive planning.

    The historical `version=8.0` field is intentionally preserved for V8/V9
    compatibility tests. V10 capabilities are exposed through
    `advanced_version=10.0`.
    """
    from omni.workspace_command_center import snapshot as workspace_snapshot
    from omni.mission_queue import MISSION_QUEUE

    text = " ".join(str(query or "").lower().split())
    market_related = any(token in text for token in (
        "trade", "trading", "market", "nifty", "banknifty", "sensex", "btc",
        "bitcoin", "eth", "crude", "gold", "portfolio", "paper", "option",
    ))
    engineering_related = any(token in text for token in (
        "code", "coding", "repo", "repository", "branch", "test", "debug", "fix",
        "python", "javascript", "engineering", "compile", "regression",
    ))
    system_related = any(token in text for token in (
        "system", "service", "runtime", "health", "port", "process", "outage",
        "diagnostic", "restart", "supervisor", "memory pressure", "disk",
    ))
    if include_market_context is not None:
        market_related = bool(include_market_context)

    recent = conversation_turns.history(limit=3, useful_only=True)
    payload: dict[str, Any] = {
        "success": True,
        "version": "8.0",
        "advanced_version": "10.0",
        "world_model_version": "9.3",
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
        "world_model": _safe("world_model", _world_context),
        "cognitive_events": _safe("cognitive_events", _cognitive_context),
        "critic": _safe("critic", _critic_context),
        "evidence_ledger": _safe("evidence_ledger", _evidence_context),
        "engineering": _safe("engineering", _engineering_context) if engineering_related else {
            "success": True, "name": "engineering", "data": {"included": False, "reason": "NON_ENGINEERING_REQUEST"}
        },
        "system_diagnostics": _safe("system_diagnostics", _system_context) if system_related else {
            "success": True, "name": "system_diagnostics", "data": {"included": False, "reason": "NON_SYSTEM_REQUEST"}
        },
        "paper": _safe("paper", _paper_summary) if market_related else {
            "success": True, "name": "paper", "data": {"included": False, "reason": "NON_MARKET_REQUEST"}
        },
        "trading_governance": _safe("trading_governance", _trading_governance_context) if market_related else {
            "success": True, "name": "trading_governance", "data": {"included": False, "reason": "NON_MARKET_REQUEST"}
        },
        "policy": {
            "local_first": True,
            "context_mutation": False,
            "state_provenance": True,
            "freshness_explicit": True,
            "cognitive_bus": True,
            "critic_verifier": True,
            "evidence_ledger": True,
            "governed_engineering": True,
            "safe_recovery_proposals": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        },
    }
    return payload


__all__ = ["snapshot"]
