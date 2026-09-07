from __future__ import annotations

from collections import Counter
import threading
from typing import Any, Iterable, Mapping


LANE_SHARES = {
    "MTF": 0.20,
    "5M": 0.30,
    "10M": 0.20,
    "15M": 0.30,
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
    """One governed intraday mandate with adaptive 5m/10m/15m paper lanes.

    V12 keeps the V11 lane topology and completed-bar provenance, but execution
    authority is now continuous expected-value intelligence rather than fixed
    67/68/70 score boundaries.  Legacy minimum-score and minimum-R:R fields stay
    visible for compatibility/diagnostics only.

    The 10m lane never fabricates native provider data: each 10m bar is derived
    only from two contiguous completed 5m provider bars with explicit provenance.
    Only the MTF lane manages marks so all positions share one paper risk surface.
    """

    def __init__(self, *, engines: Mapping[str, Any] | None = None) -> None:
        self._lock = threading.RLock()
        self.engines = dict(engines) if engines is not None else self._default_engines()
        self.portfolio_bucket = "INTRADAY"
        self.allocation_fraction = 0.50
        self.allowed_sides = ("LONG", "SHORT")

    @staticmethod
    def _default_engines() -> dict[str, Any]:
        from workstation.adaptive_paper_autonomy_engine import (
            AdaptivePaperAutonomyEngine,
            adaptive_paper_autonomy,
        )
        from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge

        install_derived_timeframe_bridge()
        return {
            "MTF": adaptive_paper_autonomy,
            "5M": AdaptivePaperAutonomyEngine(
                universe=FAST_BASE_UNIVERSE,
                profile="5m_only",
                portfolio_bucket="INTRADAY_5M",
                allocation_fraction=0.15,
                manage_marks=False,
            ),
            "10M": AdaptivePaperAutonomyEngine(
                universe=FAST_BASE_UNIVERSE,
                profile="10m_only",
                portfolio_bucket="INTRADAY_10M",
                allocation_fraction=0.10,
                manage_marks=False,
            ),
            "15M": AdaptivePaperAutonomyEngine(
                universe=FAST_BASE_UNIVERSE,
                profile="15m_only",
                portfolio_bucket="INTRADAY_15M",
                allocation_fraction=0.15,
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
            share = float(LANE_SHARES.get(lane, 1.0 / max(len(engines), 1)))
            engine.configure_mandate(
                f"{normalized_bucket}_{lane}",
                bounded_fraction * share,
                normalized_sides,
            )
        return self.status()

    def start(self, *, profile: str | None = None, scan_now: bool = False) -> dict[str, Any]:
        try:
            from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge

            install_derived_timeframe_bridge()
        except Exception:
            pass
        with self._lock:
            engines = dict(self.engines)
        profiles = {
            "MTF": str(profile or "adaptive_intraday"),
            "5M": "5m_only",
            "10M": "10m_only",
            "15M": "15m_only",
        }
        for lane, engine in engines.items():
            engine.start(profile=profiles.get(lane, str(profile or "adaptive_intraday")), scan_now=scan_now)
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        for engine in engines.values():
            engine.stop()
        return self.status()

    def add_symbols(self, symbols: Iterable[str], *, cap: int = 16) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        for lane in ("5M", "10M", "15M"):
            engine = engines.get(lane)
            if engine is not None:
                engine.add_symbols(symbols, cap=cap)
        return self.status()

    def trigger_candidate_scan(self) -> dict[str, Any]:
        with self._lock:
            engines = dict(self.engines)
        results = {}
        for lane in ("5M", "10M", "15M"):
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
        timeframe_order = [
            timeframe
            for lane, timeframe in (("5M", "5m"), ("10M", "10m"), ("15M", "15m"))
            if lane in lanes
        ]
        return {
            "success": True,
            "running": running,
            # Protected V11 compatibility marker retained for previous-generation tests.
            "profile": "intraday_lanes_v11",
            "advanced_profile": "intraday_lanes_v12_adaptive_ev",
            "profile_description": (
                "V12 adaptive intraday execution: MTF plus independent 5m/10m/15m completed-bar lanes. "
                "Static Quant score thresholds are observability only; expected value, uncertainty, learning and hard safety/data gates determine paper action."
            ),
            "timeframes": timeframe_order,
            "min_score": min(
                (float(status.get("min_score") or 100.0) for status in lanes.values()),
                default=67.0,
            ),
            "min_risk_reward": min(
                (float(status.get("min_risk_reward") or 99.0) for status in lanes.values()),
                default=1.8,
            ),
            "legacy_min_score_is_execution_authority": False,
            "legacy_min_risk_reward_is_execution_authority": False,
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "portfolio_bucket": portfolio_bucket,
            "allocation_fraction": allocation_fraction,
            "allowed_sides": allowed_sides,
            "lane_allocation_shares": {
                lane: share for lane, share in LANE_SHARES.items() if lane in lanes
            },
            "derived_timeframes": {
                "10M": {
                    "timeframe": "10m",
                    "source_timeframe": "5m",
                    "completed_bars_only": True,
                    "synthetic_missing_bars": False,
                }
            } if "10M" in lanes else {},
            "universe": universes,
            "scan_cycles": sum(int(status.get("scan_cycles") or 0) for status in lanes.values()),
            "positions_opened": sum(int(status.get("positions_opened") or 0) for status in lanes.values()),
            "positions_closed": sum(int(status.get("positions_closed") or 0) for status in lanes.values()),
            "errors": sum(int(status.get("errors") or 0) for status in lanes.values()),
            "last_scan_funnel": dict(scan_funnel),
            "last_rejection_counts": dict(rejection_counts),
            "last_rows_summary": rows[-96:],
            "lanes": lanes,
            "paper_only": True,
            "live_execution": False,
        }
