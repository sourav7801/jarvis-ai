from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Mapping


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

    The mesh deliberately separates broad discovery ranking from execution
    qualification. It never opens a broker order or bypasses the paper engine;
    it only explains what each governed horizon saw, where a symbol was routed,
    which blockers remain and whether a completed-bar execution setup qualified.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots = 0
        self._last_snapshot_at: str | None = None

    @staticmethod
    def _providers() -> dict[str, Callable[[], Any]]:
        def scanner() -> Any:
            from workstation.multi_market_scanner import multi_market_scanner
            return multi_market_scanner.status()

        def controller() -> Any:
            from workstation.paper_portfolio_controller import paper_portfolio_controller
            return paper_portfolio_controller.status()

        def router() -> Any:
            from workstation.candidate_horizon_router import candidate_horizon_router
            return candidate_horizon_router.status()

        def derived() -> Any:
            from workstation.derived_timeframe_bridge import status
            return status()

        def routing_bridge() -> Any:
            from workstation.discovery_routing_bridge import status
            return status()

        def governance() -> Any:
            from omni.trading_intelligence.trading_governance_center import TRADING_GOVERNANCE_CENTER
            return TRADING_GOVERNANCE_CENTER.snapshot(days=31)

        return {
            "scanner": scanner,
            "portfolio_controller": controller,
            "candidate_router": router,
            "derived_timeframe": derived,
            "discovery_routing_bridge": routing_bridge,
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
        try:
            from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge
            from workstation.discovery_routing_bridge import install_discovery_routing_bridge

            install_derived_timeframe_bridge()
            install_discovery_routing_bridge()
        except Exception:
            # Snapshot remains fault-isolated and reports subsystem health below.
            pass

        surfaces = {
            name: _safe(provider, name=name)
            for name, provider in self._providers().items()
        }
        scanner = dict(surfaces["scanner"].get("data") or {})
        controller = dict(surfaces["portfolio_controller"].get("data") or {})
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
                "discovery_timeframe": (discovery or {}).get("discovery_timeframe") or "1d" if discovery else None,
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

        return {
            "success": True,
            "version": "11.0",
            "service": "JARVIS_TRADING_DECISION_MESH",
            "created_at": created_at,
            "snapshot_count": snapshots,
            "overall": "READY" if all(row.get("healthy") for row in surfaces.values()) else "DEGRADED",
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
            "derived_10m": dict(surfaces["derived_timeframe"].get("data") or {}),
            "routing_bridge": dict(surfaces["discovery_routing_bridge"].get("data") or {}),
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
                "read_only": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            }


TRADING_DECISION_MESH = TradingDecisionMesh()

__all__ = ["TRADING_DECISION_MESH", "TradingDecisionMesh"]
