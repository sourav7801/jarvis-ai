from __future__ import annotations

import threading
from typing import Any, Mapping


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
    """Starts independent, risk-bounded paper mandates for three horizons."""

    def __init__(self, *, engines: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.RLock()
        self.allocations = dict(DEFAULT_ALLOCATIONS)
        self.engines = dict(engines) if engines is not None else self._default_engines()

    @staticmethod
    def _default_engines() -> dict[str, Any]:
        from workstation.paper_autonomy_engine import PaperAutonomyEngine, paper_autonomy

        return {
            "INTRADAY": paper_autonomy,
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

    def status(self) -> dict[str, Any]:
        return self._payload({
            bucket: engine.status()
            for bucket, engine in self.engines.items()
        })

    def _payload(self, statuses: Mapping[str, Any]) -> dict[str, Any]:
        running = bool(statuses) and all(bool(status.get("running")) for status in statuses.values())
        return {
            "success": True,
            "running": running,
            "allocations": dict(self.allocations),
            "mandates": dict(statuses),
            "message": (
                "All-day paper portfolio is running across intraday, swing and investment mandates."
                if running
                else "All-day paper portfolio is stopped or partially available."
            ),
            "paper_only": True,
            "live_execution": False,
        }


paper_portfolio_controller = PaperPortfolioController()
