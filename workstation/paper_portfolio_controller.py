from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Iterable, Mapping


DEFAULT_ALLOCATIONS = {
    "INTRADAY": 0.50,
    "SWING": 0.30,
    "INVESTMENT": 0.20,
}

PROFILE_BY_BUCKET = {
    "INTRADAY": "intraday",
    "SWING": "swing",
    "INVESTMENT": "investment",
}

CONTROL_PROFILE_TOKENS = {
    "intraday_only": ("START", "INTRADAY"),
    "swing_only": ("START", "SWING"),
    "investment_only": ("START", "INVESTMENT"),
    "stop_intraday": ("STOP", "INTRADAY"),
    "stop_swing": ("STOP", "SWING"),
    "stop_investment": ("STOP", "INVESTMENT"),
}


class PaperPortfolioController:
    """Own independent, risk-bounded paper mandates for three horizons.

    V12 preserves the separate INTRADAY / SWING / INVESTMENT controls while
    replacing static score authority inside the default engines with adaptive
    expected-value paper intelligence. Discovery score remains routing-only.
    """

    def __init__(self, *, engines: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.RLock()
        self.allocations = dict(DEFAULT_ALLOCATIONS)
        self._owns_runtime_router = engines is None
        self.engines = dict(engines) if engines is not None else self._default_engines()
        self._last_candidate_routing: dict[str, Any] = {
            "routed_at": None,
            "source": "MULTI_MARKET_DISCOVERY",
            "discovery_candidates": 0,
            "intraday_symbols": [],
            "swing_symbols": [],
            "investment_symbols": [],
            "discovery_scores": {},
            "paper_only": True,
            "live_execution": False,
        }

    @staticmethod
    def _default_engines() -> dict[str, Any]:
        from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
        from workstation.intraday_lane_group import IntradayLaneGroup

        return {
            "INTRADAY": IntradayLaneGroup(),
            "SWING": AdaptivePaperAutonomyEngine(
                profile="swing",
                portfolio_bucket="SWING",
                allocation_fraction=DEFAULT_ALLOCATIONS["SWING"],
                manage_marks=False,
            ),
            "INVESTMENT": AdaptivePaperAutonomyEngine(
                profile="investment",
                portfolio_bucket="INVESTMENT",
                allocation_fraction=DEFAULT_ALLOCATIONS["INVESTMENT"],
                allowed_sides=("LONG",),
                manage_marks=False,
            ),
        }

    def configure(self, allocations: Mapping[str, float]) -> dict[str, Any]:
        normalized = {str(key).upper(): float(value) for key, value in allocations.items()}
        if set(normalized) != set(DEFAULT_ALLOCATIONS):
            raise ValueError("allocations must contain INTRADAY, SWING and INVESTMENT")
        if any(value <= 0.0 or value > 1.0 for value in normalized.values()):
            raise ValueError("each allocation must be greater than zero and at most one")
        if abs(sum(normalized.values()) - 1.0) > 1e-9:
            raise ValueError("portfolio allocations must total exactly one")
        with self._lock:
            self.allocations = normalized
        return self.status()

    def _start_candidate_router(self) -> None:
        if not self._owns_runtime_router:
            return
        try:
            from workstation.candidate_horizon_router import candidate_horizon_router

            candidate_horizon_router.start()
        except Exception:
            pass

    def start_bucket(self, bucket: str, *, scan_now: bool = True) -> dict[str, Any]:
        normalized = str(bucket or "").strip().upper()
        if normalized not in PROFILE_BY_BUCKET:
            raise ValueError("bucket must be INTRADAY, SWING or INVESTMENT")
        with self._lock:
            engine = self.engines.get(normalized)
            allocation = self.allocations[normalized]
        if engine is None:
            raise RuntimeError(f"{normalized} paper engine is unavailable")
        sides = ("LONG",) if normalized == "INVESTMENT" else ("LONG", "SHORT")
        engine.configure_mandate(normalized, allocation, sides)
        profile = (
            "adaptive_intraday"
            if normalized == "INTRADAY"
            else PROFILE_BY_BUCKET[normalized]
        )
        engine.start(profile=profile, scan_now=scan_now)
        self._start_candidate_router()
        return self.status()

    def stop_bucket(self, bucket: str) -> dict[str, Any]:
        normalized = str(bucket or "").strip().upper()
        if normalized not in PROFILE_BY_BUCKET:
            raise ValueError("bucket must be INTRADAY, SWING or INVESTMENT")
        with self._lock:
            engine = self.engines.get(normalized)
        if engine is None:
            raise RuntimeError(f"{normalized} paper engine is unavailable")
        engine.stop()
        return self.status()

    def start(self, *, intraday_profile: str = "adaptive_intraday") -> dict[str, Any]:
        token = str(intraday_profile or "adaptive_intraday").strip().lower()
        control = CONTROL_PROFILE_TOKENS.get(token)
        if control is not None:
            action, bucket = control
            return self.start_bucket(bucket) if action == "START" else self.stop_bucket(bucket)

        statuses: dict[str, Any] = {}
        with self._lock:
            allocations = dict(self.allocations)
            engines = dict(self.engines)
        for bucket, profile in PROFILE_BY_BUCKET.items():
            engine = engines.get(bucket)
            if engine is None:
                continue
            sides = ("LONG",) if bucket == "INVESTMENT" else ("LONG", "SHORT")
            engine.configure_mandate(bucket, allocations[bucket], sides)
            selected_profile = intraday_profile if bucket == "INTRADAY" else profile
            statuses[bucket] = engine.start(profile=selected_profile, scan_now=True)
        self._start_candidate_router()
        return self._payload(statuses)

    def stop(self) -> dict[str, Any]:
        statuses = {
            bucket: engine.stop()
            for bucket, engine in self.engines.items()
        }
        return self._payload(statuses)

    @staticmethod
    def _unique_symbols(rows: Iterable[dict[str, Any]], limit: int) -> list[str]:
        symbols: list[str] = []
        for row in rows:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol and symbol not in symbols:
                symbols.append(symbol)
            if len(symbols) >= max(1, int(limit)):
                break
        return symbols

    def enroll_discovery_candidates(
        self,
        candidates: Iterable[dict[str, Any]],
        *,
        max_intraday: int = 8,
        max_swing: int = 10,
        max_investment: int = 6,
    ) -> dict[str, Any]:
        """Route discovery candidates; horizon engines own execution intelligence.

        V12 deliberately removes the old investment discovery score >=65 gate.
        Discovery ranking decides only which names deserve evaluation.  The
        adaptive horizon engine independently estimates expected value and risk.
        """

        rows = [
            dict(row)
            for row in candidates
            if isinstance(row, dict)
            and row.get("candidate") is True
            and row.get("auto_paper_eligible") is True
        ]
        rows.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)

        intraday_symbols = self._unique_symbols(rows, max_intraday)
        swing_symbols = self._unique_symbols(rows, max_swing)
        investment_rows = [
            row
            for row in rows
            if str(row.get("direction") or "").upper() == "BULLISH"
        ]
        investment_symbols = self._unique_symbols(investment_rows, max_investment)

        with self._lock:
            engines = dict(self.engines)

        routing_plan = {
            "INTRADAY": intraday_symbols,
            "SWING": swing_symbols,
            "INVESTMENT": investment_symbols,
        }
        for bucket, symbols in routing_plan.items():
            engine = engines.get(bucket)
            if engine is None or not symbols or not hasattr(engine, "add_symbols"):
                continue
            engine.add_symbols(symbols, cap=24 if bucket != "INTRADAY" else 16)
            try:
                running = bool(engine.status().get("running"))
            except Exception:
                running = False
            if not running:
                continue
            trigger = (
                getattr(engine, "trigger_candidate_scan", None)
                or getattr(engine, "trigger_scan", None)
            )
            if callable(trigger):
                trigger()

        discovery_scores = {
            str(row.get("symbol") or "").strip().upper(): float(row.get("score") or 0.0)
            for row in rows[: max(max_intraday, max_swing, max_investment)]
            if str(row.get("symbol") or "").strip()
        }
        routing = {
            "routed_at": datetime.now(timezone.utc).isoformat(),
            "source": "MULTI_MARKET_DISCOVERY",
            "discovery_candidates": len(rows),
            "intraday_symbols": intraday_symbols,
            "swing_symbols": swing_symbols,
            "investment_symbols": investment_symbols,
            "discovery_scores": discovery_scores,
            "contract": "DISCOVERY_SCORE_IS_NOT_EXECUTION_SCORE",
            "adaptive_execution": True,
            "static_discovery_score_gate": False,
            "paper_only": True,
            "live_execution": False,
        }
        with self._lock:
            self._last_candidate_routing = routing
        return dict(routing)

    @staticmethod
    def _rows_for_status(status: Mapping[str, Any]) -> list[dict[str, Any]]:
        rows = [
            dict(row)
            for row in list(status.get("last_rows_summary") or [])
            if isinstance(row, dict)
        ]
        if rows:
            return rows
        lanes = status.get("lanes")
        if not isinstance(lanes, Mapping):
            return []
        combined: list[dict[str, Any]] = []
        for lane, lane_status in lanes.items():
            if not isinstance(lane_status, Mapping):
                continue
            for row in list(lane_status.get("last_rows_summary") or []):
                if isinstance(row, dict):
                    combined.append({**dict(row), "lane": str(lane)})
        return combined

    def _decision_board(self, statuses: Mapping[str, Any]) -> list[dict[str, Any]]:
        with self._lock:
            routing = dict(self._last_candidate_routing)
        discovery_scores = dict(routing.get("discovery_scores") or {})
        board: list[dict[str, Any]] = []
        for bucket, status in statuses.items():
            if not isinstance(status, Mapping):
                continue
            for row in self._rows_for_status(status):
                symbol = str(row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                adaptive_action = str(row.get("adaptive_action") or "").upper() or None
                adaptive_executable = bool(row.get("adaptive_executable")) if adaptive_action else None
                hard = [str(item) for item in list(row.get("hard_blockers") or row.get("blockers") or [])]
                soft = [str(item) for item in list(row.get("soft_evidence") or [])]
                execution_score = row.get("execution_score", row.get("score", row.get("legacy_score")))
                legacy_qualified = bool(row.get("qualified", row.get("legacy_qualified", False)))
                decision = (
                    adaptive_action
                    if adaptive_action
                    else "QUALIFIED" if legacy_qualified else "BLOCKED"
                )
                board.append(
                    {
                        "symbol": symbol,
                        "mandate": str(bucket),
                        "lane": row.get("lane"),
                        "discovery_score": discovery_scores.get(symbol),
                        "execution_score": execution_score,
                        "legacy_qualified": legacy_qualified,
                        "qualified": adaptive_executable if adaptive_action else legacy_qualified,
                        "candidate_side": row.get("adaptive_side", row.get("candidate_side")),
                        "adaptive_action": adaptive_action,
                        "adaptive_probability_win": row.get("adaptive_probability_win"),
                        "adaptive_expected_value_r": row.get("adaptive_expected_value_r"),
                        "adaptive_confidence": row.get("adaptive_confidence"),
                        "adaptive_risk_multiplier": row.get("adaptive_risk_multiplier"),
                        "session_open": row.get("session_open"),
                        "blockers": hard,
                        "hard_blockers": hard,
                        "soft_evidence": soft,
                        "primary_blocker": hard[0] if hard else None,
                        "message": row.get("message"),
                        "decision": decision,
                        "paper_only": True,
                        "live_execution": False,
                    }
                )
        board.sort(
            key=lambda row: (
                bool(row.get("qualified")),
                float(row.get("adaptive_expected_value_r") or -999.0),
                float(row.get("adaptive_confidence") or 0.0),
                float(row.get("execution_score") or 0.0),
                float(row.get("discovery_score") or 0.0),
            ),
            reverse=True,
        )
        return board[:80]

    def status(self) -> dict[str, Any]:
        return self._payload({
            bucket: engine.status()
            for bucket, engine in self.engines.items()
        })

    def _payload(self, statuses: Mapping[str, Any]) -> dict[str, Any]:
        active = {
            bucket: bool(status.get("running"))
            for bucket, status in statuses.items()
        }
        running = any(active.values())
        all_running = bool(active) and all(active.values())
        with self._lock:
            routing = dict(self._last_candidate_routing)
        return {
            "success": True,
            "running": running,
            "all_running": all_running,
            "active_mandates": [bucket for bucket, is_running in active.items() if is_running],
            "allocations": dict(self.allocations),
            "mandates": dict(statuses),
            "candidate_routing": routing,
            "decision_board": self._decision_board(statuses),
            "score_contract": {
                "discovery_score": "Broad completed-bar candidate ranking only; never entry authority.",
                "execution_score": "Continuous evidence feature only; no fixed 67/68/70 execution boundary in V12.",
                "adaptive_authority": "Expected value + uncertainty + outcome learning + hard data/risk/safety blockers.",
            },
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "message": (
                "Paper mandates active: " + ", ".join(bucket for bucket, is_running in active.items() if is_running)
                if running
                else "Intraday, swing and investment paper mandates are stopped."
            ),
            "paper_only": True,
            "live_execution": False,
        }


paper_portfolio_controller = PaperPortfolioController()
