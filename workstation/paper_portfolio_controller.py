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


class PaperPortfolioController:
    """Starts independent, risk-bounded paper mandates for three horizons.

    V8.1 keeps the externally stable three-bucket contract while replacing the
    default intraday engine with a lane group that owns MTF, 5m-only and 15m-only
    paper execution. Daily discovery candidates are also routed into the swing
    and long-only investment watchlists instead of being enrolled only into the
    intraday singleton.
    """

    def __init__(self, *, engines: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.RLock()
        self.allocations = dict(DEFAULT_ALLOCATIONS)
        self.engines = dict(engines) if engines is not None else self._default_engines()
        self._last_candidate_routing: dict[str, Any] = {
            "routed_at": None,
            "source": "MULTI_MARKET_DISCOVERY",
            "discovery_candidates": 0,
            "intraday_symbols": [],
            "swing_symbols": [],
            "investment_symbols": [],
            "paper_only": True,
            "live_execution": False,
        }

    @staticmethod
    def _default_engines() -> dict[str, Any]:
        from workstation.intraday_lane_group import IntradayLaneGroup
        from workstation.paper_autonomy_engine import PaperAutonomyEngine

        return {
            "INTRADAY": IntradayLaneGroup(),
            "SWING": PaperAutonomyEngine(
                profile="swing",
                portfolio_bucket="SWING",
                allocation_fraction=DEFAULT_ALLOCATIONS["SWING"],
                manage_marks=False,
            ),
            "INVESTMENT": PaperAutonomyEngine(
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

    def start(self, *, intraday_profile: str = "adaptive_intraday") -> dict[str, Any]:
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
        """Route discovery candidates into the appropriate paper horizons.

        The discovery score is intentionally *not* treated as an execution score.
        It only determines which names deserve horizon-specific evaluation. Each
        target engine recomputes its own completed-bar execution decision and can
        still reject the setup for score, R:R, freshness, pattern, session or risk.
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
            and str(row.get("state") or "").upper() == "CONFIRMED_BREAKOUT"
            and float(row.get("score") or 0.0) >= 65.0
        ]
        investment_symbols = self._unique_symbols(investment_rows, max_investment)

        with self._lock:
            engines = dict(self.engines)

        intraday = engines.get("INTRADAY")
        if intraday is not None and intraday_symbols and hasattr(intraday, "add_symbols"):
            intraday.add_symbols(intraday_symbols, cap=16)
            trigger = getattr(intraday, "trigger_candidate_scan", None) or getattr(intraday, "trigger_scan", None)
            if callable(trigger):
                trigger()

        swing = engines.get("SWING")
        if swing is not None and swing_symbols and hasattr(swing, "add_symbols"):
            swing.add_symbols(swing_symbols, cap=24)
            trigger = getattr(swing, "trigger_scan", None)
            if callable(trigger):
                trigger()

        investment = engines.get("INVESTMENT")
        if investment is not None and investment_symbols and hasattr(investment, "add_symbols"):
            investment.add_symbols(investment_symbols, cap=24)
            trigger = getattr(investment, "trigger_scan", None)
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
            "paper_only": True,
            "live_execution": False,
        }
        with self._lock:
            self._last_candidate_routing = routing
        return dict(routing)

    def status(self) -> dict[str, Any]:
        return self._payload({
            bucket: engine.status()
            for bucket, engine in self.engines.items()
        })

    def _payload(self, statuses: Mapping[str, Any]) -> dict[str, Any]:
        running = bool(statuses) and all(bool(status.get("running")) for status in statuses.values())
        with self._lock:
            routing = dict(self._last_candidate_routing)
        return {
            "success": True,
            "running": running,
            "allocations": dict(self.allocations),
            "mandates": dict(statuses),
            "candidate_routing": routing,
            "message": (
                "All-day paper portfolio is running across intraday execution lanes, swing and investment mandates."
                if running
                else "All-day paper portfolio is stopped or partially available."
            ),
            "paper_only": True,
            "live_execution": False,
        }


paper_portfolio_controller = PaperPortfolioController()
