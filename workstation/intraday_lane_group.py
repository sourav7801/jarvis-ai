from __future__ import annotations

from collections import Counter
import threading
from typing import Any, Iterable, Mapping


LANE_SHARES = {
    "MTF": 0.20,
    "5M": 0.40,
    "15M": 0.40,
}

FAST_BASE_UNIVERSE = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "GOLD",
    "BTC",
    "ETH",
)


class IntradayLaneGroup:
    """One governed intraday mandate with independent 5m and 15m execution lanes.

    V8 required 5m/15m agreement inside the adaptive MTF engine. That remains
    available as a conservative lane, but it no longer has exclusive authority
    over intraday paper entries. A confirmed 5m or 15m breakout can be evaluated
    by its own single-timeframe profile and still passes the normal stop, target,
    R:R, freshness, session, adaptive-policy and portfolio-risk checks.

    Only the MTF lane manages marks so all positions continue to share one paper
    portfolio/risk surface without three competing mark loops.
    """

    def __init__(self, *, engines: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.RLock()
        self.engines = dict(engines) if engines is not None else self._default_engines()
        self.portfolio_bucket = "INTRADAY"
        self.allocation_fraction = 0.50
        self.allowed_sides = ("LONG", "SHORT")

    @staticmethod
    def _default_engines() -> dict[str, Any]:
        from workstation.paper_autonomy_engine import PaperAutonomyEngine, paper_autonomy

        return {
            "MTF": paper_autonomy,
            "5M": PaperAutonomyEngine(
                universe=FAST_BASE_UNIVERSE,
                profile="5m_only",
                portfolio_bucket="INTRADAY_5M",
                allocation_fraction=0.20,
                manage_marks=False,
            ),
            "15M": PaperAutonomyEngine(
                universe=FAST_BASE_UNIVERSE,
                profile="15m_only",
                portfolio_bucket="INTRADAY_15M",
                allocation_fraction=0.20,
                manage_marks=False,
            ),
        }

    @property
    def live_execution(self) -> bool:
        return False

    def configure_mandate(
        self,
        bucket: str,
        allocation_fraction: float,
        allowed_sides: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        normalized_bucket = str(bucket or "INTRADAY").strip().upper() or "INTRADAY"
        bounded_fraction = float(allocation_fraction)
        if not 0.0 < bounded_fraction <= 1.0:
            raise ValueError("allocation_fraction must be greater than zero and at most one")
        normalized_sides = tuple(
            side
            for side in (str(item).strip().upper() for item in (allowed_sides or self.allowed_sides))
            if side in {"LONG", "SHORT"}
        )
        if not normalized_sides:
            raise ValueError("allowed_sides must include LONG or SHORT")
        with self._lock:
            self.portfolio_bucket = normalized_bucket
            self.allocation_fraction = bounded_fraction
            self.allowed_sides = normalized_sides
            engines = dict(self.engines)
        for lane, engine in engines.items():
            share = LANE_SHARES[lane]
            engine.configure_mandate(
                f"{normalized_bucket}_{lane}",
                bounded_fraction * share,
                normalized_sides,
            )
        return self.status()

    def start(self, *, profile: str | None = None, scan_now: bool = False) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        profiles = {
            "MTF": str(profile or "adaptive_intraday"),
            "5M": "5m_only",
            "15M": "15m_only",
        }
        for lane, engine in engines.items():
            engine.start(profile=profiles[lane], scan_now=scan_now)
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        for engine in engines.values():
            engine.stop()
        return self.status()

    def add_symbols(self, symbols: Iterable[str], *, cap: int = 16) -> dict[str, Any]:
        """Enroll discovery candidates only into the fast single-TF lanes.

        The MTF lane retains the compact canonical universe. This prevents the
        broad daily discovery scanner from doubling the expensive 5m/15m MTF
        workload while the independent lanes evaluate the newly discovered names.
        """

        with self._lock:
            engines = dict(self.engines)
        for lane in ("5M", "15M"):
            engine = engines.get(lane)
            if engine is not None:
                engine.add_symbols(symbols, cap=cap)
        return self.status()

    def trigger_candidate_scan(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        results = {}
        for lane in ("5M", "15M"):
            engine = engines.get(lane)
            if engine is not None:
                results[lane] = engine.trigger_scan()
        return {
            "success": True,
            "triggered_lanes": list(results),
            "lane_results": results,
            "paper_only": True,
            "live_execution": False,
        }

    def trigger_scan(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        results = {lane: engine.trigger_scan() for lane, engine in engines.items()}
        return {
            "success": True,
            "triggered_lanes": list(results),
            "lane_results": results,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
            allocation_fraction = self.allocation_fraction
            allowed_sides = list(self.allowed_sides)
            portfolio_bucket = self.portfolio_bucket
        lanes = {lane: engine.status() for lane, engine in engines.items()}
        running = bool(lanes) and all(bool(status.get("running")) for status in lanes.values())
        rejection_counts = Counter()
        rows: list[dict[str, Any]] = []
        universes: list[str] = []
        scan_funnel = Counter()
        for lane, status in lanes.items():
            rejection_counts.update(status.get("last_rejection_counts") or {})
            scan_funnel.update(status.get("last_scan_funnel") or {})
            for symbol in status.get("universe") or []:
                if symbol not in universes:
                    universes.append(symbol)
            for row in status.get("last_rows_summary") or []:
                if isinstance(row, dict):
                    rows.append({**row, "lane": lane})
        return {
            "success": True,
            "running": running,
            "profile": "intraday_lanes_v81",
            "profile_description": (
                "V8.1 intraday execution: conservative 5m/15m MTF consensus plus "
                "independent confirmed-breakout 5m and 15m paper lanes."
            ),
            "timeframes": ["5m", "15m"],
            "min_score": min(
                (float(status.get("min_score") or 100.0) for status in lanes.values()),
                default=67.0,
            ),
            "min_risk_reward": min(
                (float(status.get("min_risk_reward") or 99.0) for status in lanes.values()),
                default=1.8,
            ),
            "portfolio_bucket": portfolio_bucket,
            "allocation_fraction": allocation_fraction,
            "allowed_sides": allowed_sides,
            "lane_allocation_shares": dict(LANE_SHARES),
            "universe": universes,
            "scan_cycles": sum(int(status.get("scan_cycles") or 0) for status in lanes.values()),
            "positions_opened": sum(int(status.get("positions_opened") or 0) for status in lanes.values()),
            "positions_closed": sum(int(status.get("positions_closed") or 0) for status in lanes.values()),
            "errors": sum(int(status.get("errors") or 0) for status in lanes.values()),
            "last_scan_funnel": dict(scan_funnel),
            "last_rejection_counts": dict(rejection_counts),
            "last_rows_summary": rows[-72:],
            "lanes": lanes,
            "paper_only": True,
            "live_execution": False,
        }
