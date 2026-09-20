"""V17.3 cross-market PAPER control plane.

This module persists no broker credentials and exposes no broker-order methods.
It reconciles the operator's explicit PAPER armed intent with the canonical
workspace scanners plus the BTC/ETH/SOL and session-aware MCX PAPER lanes.

A restart must not silently forget an explicit START JARVIS intent, but a
disarmed terminal must never arm itself.  All live-order authority remains
locked.
"""
from __future__ import annotations

from datetime import datetime, timezone
import threading
import time
from typing import Any

from workstation.v17_autopilot_preferences import load_preferences
from workstation.v17_crypto_paper_lane import crypto_paper_lane

_RECONCILE_INTERVAL_SECONDS = 5.0


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_running(payload: dict[str, Any] | None) -> bool:
    value = dict(payload or {})
    session = value.get("session") if isinstance(value.get("session"), dict) else {}
    state = str(
        value.get("state")
        or session.get("entry_session")
        or session.get("state")
        or ""
    ).upper()
    return bool(value.get("running")) or state in {"RUNNING", "ACTIVE", "SCANNING"}


def _runtime_workspace_status(runtime: Any, name: str) -> dict[str, Any]:
    """Read canonical workspace intent without requiring a public status method."""
    status_fn = getattr(runtime, "status", None)
    if callable(status_fn):
        try:
            payload = status_fn(name)
            if isinstance(payload, dict):
                return dict(payload)
        except Exception:
            pass

    desired_map = getattr(runtime, "_desired", None)
    desired = bool(desired_map.get(name)) if isinstance(desired_map, dict) else False
    session: dict[str, Any] = {}
    desk = getattr(runtime, "desk", None)
    if desk is not None:
        try:
            from workstation import workspace_accounts

            session = dict(workspace_accounts.session(desk, name) or {})
        except Exception:
            session = {}

    session_state = str(
        session.get("entry_session")
        or session.get("state")
        or ""
    ).upper()
    running = session_state == "RUNNING"
    state = session_state or ("STARTING" if desired else "PAUSED")
    return {
        "success": True,
        "running": running,
        "desired_running": desired,
        "state": state,
        "session": session,
    }


class V17CrossMarketControlPlane:
    """Reconciles durable PAPER intent with session-aware execution lanes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_reconcile_monotonic = 0.0
        self._last_requested_armed: bool | None = None
        self._last_reconcile_at: str | None = None
        self._last_action = "NOT_RECONCILED"
        self._last_error: str | None = None
        self._resume_count = 0
        self._reconcile_count = 0
        self._results: dict[str, Any] = {}

    def reconcile(
        self,
        runtime: Any,
        *,
        preferences: dict[str, Any] | None = None,
        force: bool = False,
        crypto_lane: Any | None = None,
    ) -> dict[str, Any]:
        prefs = dict(preferences or load_preferences())
        armed = bool(prefs.get("armed", False))
        now = time.monotonic()

        with self._lock:
            same_intent = self._last_requested_armed is armed
            if (
                not force
                and same_intent
                and self._last_reconcile_monotonic
                and now - self._last_reconcile_monotonic < _RECONCILE_INTERVAL_SECONDS
            ):
                return self.status(preferences=prefs)
            self._last_reconcile_monotonic = now
            self._last_requested_armed = armed

        results: dict[str, Any] = {}
        errors: list[str] = []
        changed = False
        lane = crypto_lane or crypto_paper_lane

        targets = (
            list(prefs.get("start_workspaces") or [])
            if armed
            else ["INTRADAY", "SWING", "INVESTMENT"]
        )
        for workspace in targets:
            name = str(workspace).upper()
            current = _runtime_workspace_status(runtime, name)
            running = _workspace_running(current)
            desired_running = bool(current.get("desired_running", running))
            active_or_requested = running or desired_running
            desired_action = None
            if armed and not active_or_requested:
                desired_action = "start"
            elif not armed and active_or_requested:
                desired_action = "pause"

            if desired_action:
                try:
                    current = dict(runtime.control(name, desired_action))
                    changed = True
                except Exception as exc:
                    errors.append(f"{name}:{type(exc).__name__}")
                    current = {
                        **current,
                        "success": False,
                        "state": "PROBLEM",
                        "message": f"{type(exc).__name__}: {exc}"[:300],
                    }

            current_running = _workspace_running(current)
            current_desired = bool(current.get("desired_running", current_running))
            results[name] = {
                "desired": "RUNNING" if armed else "PAUSED",
                "running": current_running,
                "start_requested": current_desired,
                "state": current.get("state")
                or (current.get("session") or {}).get("entry_session")
                or ("RUNNING" if current_running else "STARTING" if current_desired else "PAUSED"),
                "success": current.get("success") is not False,
            }

        try:
            crypto = dict(lane.status())
            crypto_running = bool(crypto.get("running"))
            if armed and not crypto_running:
                crypto = dict(lane.start())
                changed = True
                with self._lock:
                    self._resume_count += 1
            elif not armed and crypto_running:
                crypto = dict(lane.stop_new_entries())
                changed = True

            mcx = crypto.get("mcx_underlying_paper")
            if not isinstance(mcx, dict):
                try:
                    mcx = dict(lane.status().get("mcx_underlying_paper") or {})
                except Exception:
                    mcx = {}

            results["CRYPTO_UNDERLYING"] = {
                "desired": "RUNNING" if armed else "PAUSED",
                "running": bool(crypto.get("running")),
                "state": crypto.get("state") or ("RUNNING" if crypto.get("running") else "PAUSED"),
                "scan_cycles": crypto.get("scan_cycles"),
                "qualification_authority": crypto.get("qualification_authority"),
                "decision_authority": crypto.get("decision_authority"),
                "adaptive_policy_version": crypto.get("adaptive_policy_version"),
                "success": crypto.get("success") is not False,
            }
            results["MCX_FUTURES_PAPER"] = {
                "desired": "SESSION_AWARE" if armed else "PAUSED",
                "running": bool(mcx.get("running")),
                "state": mcx.get("state") or "UNKNOWN",
                "session_open": mcx.get("session_open"),
                "scan_cycles": mcx.get("scan_cycles"),
                "success": mcx.get("success") is not False,
            }
        except Exception as exc:
            errors.append(f"CRYPTO_MCX:{type(exc).__name__}")
            results["CRYPTO_UNDERLYING"] = {
                "desired": "RUNNING" if armed else "PAUSED",
                "running": False,
                "state": "PROBLEM",
                "success": False,
            }

        with self._lock:
            self._reconcile_count += 1
            self._last_reconcile_at = _iso_now()
            self._last_error = ", ".join(errors) if errors else None
            if errors:
                self._last_action = "RECONCILE_WITH_ERRORS"
            elif changed:
                self._last_action = "AUTO_RESUME" if armed else "AUTO_PAUSE"
            else:
                self._last_action = "IN_SYNC"
            self._results = results
            return self.status(preferences=prefs)

    def status(self, *, preferences: dict[str, Any] | None = None) -> dict[str, Any]:
        prefs = dict(preferences or load_preferences())
        with self._lock:
            return {
                "service": "JARVIS_V17_CROSS_MARKET_CONTROL_PLANE",
                "version": "17.3",
                "armed": bool(prefs.get("armed", False)),
                "desired_state": "ARMED" if prefs.get("armed") else "DISARMED",
                "last_reconcile_at": self._last_reconcile_at,
                "last_action": self._last_action,
                "last_error": self._last_error,
                "resume_count": self._resume_count,
                "reconcile_count": self._reconcile_count,
                "lanes": dict(self._results),
                "paper_only": True,
                "live_execution": False,
                "live_orders_locked": True,
            }


cross_market_control_plane = V17CrossMarketControlPlane()


__all__ = [
    "V17CrossMarketControlPlane",
    "cross_market_control_plane",
]
