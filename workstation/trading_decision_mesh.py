from __future__ import annotations

from datetime import datetime, timezone
import json
from threading import RLock
from typing import Any, Callable, Mapping
import urllib.error
import urllib.request


QUANT_BASE = "http://127.0.0.1:8787"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(provider: Callable[[], Any], *, name: str) -> dict[str, Any]:
    try:
        data = provider()
        return {
            "healthy": True,
            "name": name,
            "data": data if isinstance(data, dict) else {"value": data},
            "error": None,
        }
    except Exception as exc:
        return {
            "healthy": False,
            "name": name,
            "data": {},
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }


def _loopback_json(path: str, *, timeout: float = 3.0) -> dict[str, Any]:
    """Read one bounded JSON surface from the live Quant process.

    Completion Center and Quant are separate supervised processes. Importing
    scanner/controller singletons in the Completion process would create empty
    duplicate state, so V11 reads the authoritative 8787 runtime over loopback.
    """

    route = str(path or "").strip()
    if not route.startswith("/"):
        raise ValueError("loopback path must start with /")
    request = urllib.request.Request(
        QUANT_BASE + route,
        headers={"Accept": "application/json", "User-Agent": "JARVIS-V11-Decision-Mesh/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(0.5, float(timeout))) as response:
            raw = response.read(2_000_000)
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"Quant loopback unavailable for {route}: {exc}") from exc
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Quant loopback returned a non-object payload for {route}")
    return payload


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        token = str(value or "").strip()
        if token and token not in result:
            result.append(token)
    return result


class TradingDecisionMesh:
    """Read-only convergence of discovery, routing and paper execution evidence.

    Discovery and execution state are read from the authoritative Quant process
    on port 8787. The mesh never opens a broker order or bypasses the paper
    engine; it explains what each governed horizon saw, where a symbol was
    routed, which blockers remain and whether completed-bar execution qualified.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots = 0
        self._last_snapshot_at: str | None = None

    @staticmethod
    def _providers() -> dict[str, Callable[[], Any]]:
        def governance() -> Any:
            from omni.trading_intelligence.trading_governance_center import TRADING_GOVERNANCE_CENTER
            return TRADING_GOVERNANCE_CENTER.snapshot(days=31)

        return {
            "quant_health": lambda: _loopback_json("/api/health", timeout=2.0),
            "scanner": lambda: _loopback_json("/api/scanner/multi", timeout=4.0),
            "portfolio_controller": lambda: _loopback_json("/api/paper/portfolio-controller", timeout=4.0),
            "trading_governance": governance,
        }

    @staticmethod
    def _route_targets(symbol: str, routing: Mapping[str, Any]) -> list[str]:
        targets: list[str] = []
        mapping = (
            ("INTRADAY", "intraday_symbols"),
            ("SWING", "swing_symbols"),
            ("INVESTMENT", "investment_symbols"),
        )
        for label, key in mapping:
            values = {str(item).strip().upper() for item in list(routing.get(key) or [])}
            if symbol in values:
                targets.append(label)
        return targets

    @staticmethod
    def _engine_running(controller: Mapping[str, Any], mandate: str) -> bool | None:
        mandates = controller.get("mandates")
        if not isinstance(mandates, Mapping):
            return None
        status = mandates.get(mandate)
        if not isinstance(status, Mapping):
            return None
        return bool(status.get("running"))

    @staticmethod
    def _derived_10m_runtime(controller: Mapping[str, Any]) -> dict[str, Any]:
        mandates = controller.get("mandates")
        intraday = mandates.get("INTRADAY") if isinstance(mandates, Mapping) else None
        if not isinstance(intraday, Mapping):
            intraday = {}
        lanes = intraday.get("lanes") if isinstance(intraday.get("lanes"), Mapping) else {}
        lane = lanes.get("10M") if isinstance(lanes, Mapping) else None
        derived = intraday.get("derived_timeframes")
        contract = derived.get("10M") if isinstance(derived, Mapping) else None
        return {
            "success": True,
            "version": "11.0",
            "installed": isinstance(lane, Mapping),
            "running": bool(lane.get("running")) if isinstance(lane, Mapping) else False,
            "profile": lane.get("profile") if isinstance(lane, Mapping) else None,
            "timeframe": "10m",
            "source_timeframe": "5m",
            "completed_bars_only": True,
            "synthetic_missing_bars": False,
            "runtime_contract": dict(contract) if isinstance(contract, Mapping) else {},
            "source": "QUANT_LOOPBACK_8787",
            "paper_only": True,
            "live_execution": False,
        }

    @staticmethod
    def _routing_runtime(scanner: Mapping[str, Any]) -> dict[str, Any]:
        contract = str(scanner.get("routing_contract") or "").strip()
        return {
            "success": True,
            "version": "11.0",
            "installed": contract == "PORTFOLIO_HORIZON_CONTROLLER_ONLY",
            "routing_contract": contract or "LEGACY_OR_NOT_INITIALIZED",
            "governed_auto_routing": dict(scanner.get("governed_auto_routing") or {}),
            "governed_auto_routing_completed_at": scanner.get("governed_auto_routing_completed_at"),
            "source": "QUANT_LOOPBACK_8787",
            "paper_only": True,
            "live_execution": False,
        }

    @staticmethod
    def _decision_state(
        discovery: Mapping[str, Any] | None,
        decisions: list[dict[str, Any]],
        route_targets: list[str],
        controller: Mapping[str, Any],
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []
        if discovery is not None and not bool(discovery.get("auto_paper_eligible")):
            return "RESEARCH_ONLY", [str(discovery.get("eligibility_gate") or "NOT_AUTO_PAPER_ELIGIBLE")]

        confirmed_states = {"CONFIRMED_BREAKOUT", "CONFIRMED_BREAKDOWN"}
        discovery_state = str((discovery or {}).get("state") or "").upper()
        if discovery is not None and discovery_state and discovery_state not in confirmed_states:
            reasons.append("DISCOVERY_NOT_CONFIRMED")

        if decisions:
            qualified = [row for row in decisions if bool(row.get("qualified"))]
            if qualified:
                return "EXECUTION_QUALIFIED", reasons
            for row in decisions:
                reasons.extend(str(item) for item in list(row.get("blockers") or []) if str(item).strip())
            if not reasons:
                reasons.append("EXECUTION_GATES_NOT_SATISFIED")
            return "EVALUATED_BLOCKED", _unique(reasons)

        if route_targets:
            stopped = [
                mandate for mandate in route_targets
                if TradingDecisionMesh._engine_running(controller, mandate) is False
            ]
            if stopped:
                reasons.extend(f"{mandate}_ENGINE_STOPPED" for mandate in stopped)
                return "ROUTED_ENGINE_STOPPED", _unique(reasons)
            reasons.append("AWAITING_EXECUTION_SCAN")
            return "ROUTED_PENDING", _unique(reasons)

        if discovery is not None:
            reasons.append("NOT_ROUTED_TO_EXECUTION_HORIZON")
            return "DISCOVERED_ONLY", _unique(reasons)
        return "OBSERVED", ["NO_DISCOVERY_OR_EXECUTION_EVIDENCE"]

    def snapshot(self, *, limit: int = 80) -> dict[str, Any]:
        surfaces = {
            name: _safe(provider, name=name)
            for name, provider in self._providers().items()
        }
        scanner = dict(surfaces.get("scanner", {}).get("data") or {})
        controller = dict(surfaces.get("portfolio_controller", {}).get("data") or {})
        routing = dict(controller.get("candidate_routing") or {})
        scanner_candidates = [
            dict(row)
            for row in list(scanner.get("candidates") or [])
            if isinstance(row, dict)
        ]
        decisions = [
            dict(row)
            for row in list(controller.get("decision_board") or [])
            if isinstance(row, dict)
        ]

        discovery_by_symbol = {
            str(row.get("symbol") or "").strip().upper(): row
            for row in scanner_candidates
            if str(row.get("symbol") or "").strip()
        }
        decisions_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for row in decisions:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol:
                decisions_by_symbol.setdefault(symbol, []).append(row)

        symbols = _unique(list(discovery_by_symbol) + list(decisions_by_symbol))
        rows: list[dict[str, Any]] = []
        for symbol in symbols:
            discovery = discovery_by_symbol.get(symbol)
            execution_rows = decisions_by_symbol.get(symbol, [])
            targets = self._route_targets(symbol, routing)
            state, reasons = self._decision_state(discovery, execution_rows, targets, controller)
            best = max(
                execution_rows,
                key=lambda row: float(row.get("execution_score") or row.get("score") or 0.0),
                default={},
            )
            rows.append({
                "symbol": symbol,
                "state": state,
                "discovery_timeframe": ((discovery or {}).get("discovery_timeframe") or "1d") if discovery else None,
                "discovery_state": (discovery or {}).get("state"),
                "discovery_direction": (discovery or {}).get("direction"),
                "discovery_score": _float((discovery or {}).get("score")),
                "execution_score": _float(best.get("execution_score", best.get("score"))),
                "execution_side": best.get("candidate_side"),
                "execution_mandate": best.get("mandate"),
                "execution_lane": best.get("lane"),
                "execution_qualified": any(bool(row.get("qualified")) for row in execution_rows),
                "route_targets": targets,
                "route_engine_running": {
                    mandate: self._engine_running(controller, mandate)
                    for mandate in targets
                },
                "why_not_trade": reasons if state != "EXECUTION_QUALIFIED" else [],
                "all_execution_observations": execution_rows[:12],
                "auto_paper_eligible": (discovery or {}).get("auto_paper_eligible"),
                "runtime_source": "QUANT_LOOPBACK_8787",
                "paper_only": True,
                "live_execution": False,
            })

        state_priority = {
            "EXECUTION_QUALIFIED": 6,
            "EVALUATED_BLOCKED": 5,
            "ROUTED_PENDING": 4,
            "ROUTED_ENGINE_STOPPED": 3,
            "DISCOVERED_ONLY": 2,
            "RESEARCH_ONLY": 1,
            "OBSERVED": 0,
        }
        rows.sort(
            key=lambda row: (
                state_priority.get(str(row.get("state")), 0),
                float(row.get("execution_score") or 0.0),
                float(row.get("discovery_score") or 0.0),
            ),
            reverse=True,
        )
        bounded = rows[: max(1, min(int(limit), 200))]
        counts: dict[str, int] = {}
        for row in rows:
            state = str(row.get("state") or "UNKNOWN")
            counts[state] = counts.get(state, 0) + 1

        created_at = _now()
        with self._lock:
            self._snapshots += 1
            self._last_snapshot_at = created_at
            snapshots = self._snapshots

        derived_10m = self._derived_10m_runtime(controller)
        routing_runtime = self._routing_runtime(scanner)
        critical_surfaces = [surfaces.get("quant_health", {}), surfaces.get("scanner", {}), surfaces.get("portfolio_controller", {})]
        return {
            "success": True,
            "version": "11.0",
            "service": "JARVIS_TRADING_DECISION_MESH",
            "created_at": created_at,
            "snapshot_count": snapshots,
            "overall": "READY" if all(row.get("healthy") for row in critical_surfaces) else "DEGRADED",
            "runtime_source": "QUANT_LOOPBACK_8787",
            "score_contract": {
                "discovery_score": "Broad completed-bar ranking only; never entry authority.",
                "execution_score": "Horizon/lane-specific completed-bar score plus risk, freshness, session and safety gates.",
                "position_open": "A qualified execution row may still be rejected by downstream re-entry/adaptive/risk controls before a paper position opens.",
            },
            "funnel": {
                "scanner_candidates": len(scanner_candidates),
                "auto_paper_eligible": sum(1 for row in scanner_candidates if row.get("auto_paper_eligible")),
                "routed_intraday": len(list(routing.get("intraday_symbols") or [])),
                "routed_swing": len(list(routing.get("swing_symbols") or [])),
                "routed_investment": len(list(routing.get("investment_symbols") or [])),
                "execution_observations": len(decisions),
                "execution_qualified": sum(1 for row in decisions if row.get("qualified")),
                "states": counts,
            },
            "active_mandates": list(controller.get("active_mandates") or []),
            "rows": bounded,
            "surfaces": surfaces,
            "derived_10m": derived_10m,
            "routing_bridge": routing_runtime,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }

    def explain(self, symbol: str) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        snapshot = self.snapshot(limit=200)
        row = next((item for item in snapshot["rows"] if item.get("symbol") == normalized), None)
        if row is None:
            return {
                "success": True,
                "version": "11.0",
                "symbol": normalized,
                "state": "NO_RECENT_EVIDENCE",
                "why_not_trade": ["SYMBOL_NOT_PRESENT_IN_RECENT_DISCOVERY_OR_EXECUTION_ROWS"],
                "runtime_source": snapshot.get("runtime_source"),
                "paper_only": True,
                "live_execution": False,
            }
        return {
            "success": True,
            "version": "11.0",
            **row,
            "score_contract": snapshot["score_contract"],
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "version": "11.0",
                "service": "JARVIS_TRADING_DECISION_MESH",
                "snapshots": self._snapshots,
                "last_snapshot_at": self._last_snapshot_at,
                "runtime_source": "QUANT_LOOPBACK_8787",
                "read_only": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }


TRADING_DECISION_MESH = TradingDecisionMesh()

__all__ = ["TRADING_DECISION_MESH", "TradingDecisionMesh"]
