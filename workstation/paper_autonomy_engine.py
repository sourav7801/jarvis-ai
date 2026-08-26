from __future__ import annotations

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable

from workstation.paper_trading_desk import live_mark_loader, live_mark_snapshot, paper_desk


DEFAULT_UNIVERSE = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "NATURALGAS",
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
)
DEFAULT_TIMEFRAMES = ("5m", "15m", "1h")


class PaperAutonomyEngine:
    """Autonomous research/paper execution coordinator.

    New-entry research is intentionally slower than mark-to-market risk checks:
    strategy decisions are based on completed market bars, while open positions
    are marked frequently from read-only live snapshots.  No broker order API is
    imported or exposed.
    """

    def __init__(
        self,
        *,
        universe: Iterable[str] = DEFAULT_UNIVERSE,
        timeframes: Iterable[str] = DEFAULT_TIMEFRAMES,
        min_score: float = 68.0,
        min_risk_reward: float = 1.8,
        scan_interval_seconds: float = 15.0,
        mark_interval_seconds: float = 0.75,
        max_workers: int = 4,
        profile: str | None = None,
    ) -> None:
        from workstation.trading_timeframe_profiles import resolve_trading_profile

        inferred_profile = profile
        requested_timeframes = tuple(str(item) for item in timeframes)
        if inferred_profile is None and len(requested_timeframes) == 1:
            inferred_profile = f"{requested_timeframes[0]}_only"
        profile_spec = resolve_trading_profile(inferred_profile or "intraday")
        self.universe = tuple(str(item).upper() for item in universe)
        self.profile = profile_spec.name
        self.profile_description = profile_spec.description
        self.timeframes = profile_spec.timeframes
        self.profile_risk_multiplier = profile_spec.risk_multiplier
        self.min_score = max(float(min_score), profile_spec.minimum_score)
        self.min_risk_reward = max(float(min_risk_reward), profile_spec.minimum_risk_reward)
        self.scan_interval_seconds = max(1.0, float(scan_interval_seconds))
        self.mark_interval_seconds = max(0.25, float(mark_interval_seconds))
        self.max_workers = max(1, min(int(max_workers), 8))
        self._lock = threading.RLock()
        self._running = False
        self._stop = threading.Event()
        self._scan_thread: threading.Thread | None = None
        self._mark_thread: threading.Thread | None = None
        self._scan_cycles = 0
        self._mark_cycles = 0
        self._positions_opened = 0
        self._positions_closed = 0
        self._errors = 0
        self._last_scan_at: str | None = None
        self._last_mark_at: str | None = None
        self._last_mark_rejection_counts: dict[str, int] = {}
        self._last_mark_certificates: list[dict[str, Any]] = []
        self._last_error: str | None = None
        self._last_candidates: list[dict[str, Any]] = []
        self._last_rejection_counts: dict[str, int] = {}
        self._last_rows_summary: list[dict[str, Any]] = []
        self._scan_guard = threading.Lock()
        self._trigger_thread: threading.Thread | None = None

    @property
    def live_execution(self) -> bool:
        return False

    def configure_profile(self, profile: str) -> dict[str, Any]:
        from workstation.trading_timeframe_profiles import resolve_trading_profile

        spec = resolve_trading_profile(profile)
        with self._lock:
            self.profile = spec.name
            self.profile_description = spec.description
            self.timeframes = spec.timeframes
            self.profile_risk_multiplier = spec.risk_multiplier
            self.min_score = spec.minimum_score
            self.min_risk_reward = spec.minimum_risk_reward
            self.scan_interval_seconds = max(1.0, spec.scan_interval_seconds)
        return self.status()

    def start(self, *, profile: str | None = None, scan_now: bool = False) -> dict[str, Any]:
        if profile:
            self.configure_profile(profile)
        with self._lock:
            if self._running:
                if self._stop.is_set():
                    return {**self.status(), "reason": "PREVIOUS_WORKERS_STOPPING"}
                status = self.status()
                if scan_now:
                    self.trigger_scan()
                return status
            if any(
                thread is not None and thread.is_alive()
                for thread in (self._scan_thread, self._mark_thread)
            ):
                return {**self.status(), "reason": "PREVIOUS_WORKERS_STOPPING"}
            self._running = True
            self._stop.clear()
            self._scan_thread = threading.Thread(
                target=self._scan_loop,
                name="JarvisAutoPaperScan",
                daemon=True,
            )
            self._mark_thread = threading.Thread(
                target=self._mark_loop,
                name="JarvisAutoPaperRisk",
                daemon=True,
            )
            self._scan_thread.start()
            self._mark_thread.start()
        try:
            from workstation.bounded_decision_review import decision_review_coordinator

            decision_review_coordinator.start()
        except Exception:
            pass
        if scan_now:
            self.trigger_scan()
        return self.status()

    def trigger_scan(self) -> dict[str, Any]:
        with self._lock:
            if self._trigger_thread and self._trigger_thread.is_alive():
                return {**self.status(), "scan_triggered": False, "reason": "SCAN_ALREADY_RUNNING"}
            self._trigger_thread = threading.Thread(
                target=self.scan_once,
                name="JarvisAutoPaperImmediateScan",
                daemon=True,
            )
            self._trigger_thread.start()
        return {**self.status(), "scan_triggered": True}

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        threads = (self._scan_thread, self._mark_thread, self._trigger_thread)
        for thread in threads:
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=3.0)
        with self._lock:
            self._running = any(
                thread is not None and thread.is_alive()
                for thread in (self._scan_thread, self._mark_thread)
            )
        return self.status()

    def add_symbols(self, symbols: Iterable[str], *, cap: int = 18) -> dict[str, Any]:
        """Enroll a bounded paper watchlist without restarting the service."""

        from workstation.quant_terminal_v2 import normalize_symbol

        with self._lock:
            combined = list(self.universe)
            for raw in symbols:
                try:
                    symbol = normalize_symbol(str(raw))
                except Exception:
                    continue
                if symbol not in combined:
                    combined.append(symbol)
            self.universe = tuple(combined[: max(len(DEFAULT_UNIVERSE), min(int(cap), 24))])
        return self.status()

    def reset_universe(self) -> dict[str, Any]:
        with self._lock:
            self.universe = tuple(DEFAULT_UNIVERSE)
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "running": self._running and not self._stop.is_set(),
                "universe": list(self.universe),
                "profile": self.profile,
                "profile_description": self.profile_description,
                "timeframes": list(self.timeframes),
                "min_score": self.min_score,
                "min_risk_reward": self.min_risk_reward,
                "profile_risk_multiplier": self.profile_risk_multiplier,
                "scan_interval_seconds": self.scan_interval_seconds,
                "mark_interval_seconds": self.mark_interval_seconds,
                "scan_cycles": self._scan_cycles,
                "mark_cycles": self._mark_cycles,
                "positions_opened": self._positions_opened,
                "positions_closed": self._positions_closed,
                "errors": self._errors,
                "last_scan_at": self._last_scan_at,
                "last_mark_at": self._last_mark_at,
                "last_mark_rejection_counts": dict(self._last_mark_rejection_counts),
                "last_mark_certificates": list(self._last_mark_certificates),
                "last_error": self._last_error,
                "last_candidates": list(self._last_candidates[-20:]),
                "last_rejection_counts": dict(self._last_rejection_counts),
                "last_rows_summary": list(self._last_rows_summary[-24:]),
                "paper_only": True,
                "live_execution": False,
            }

    def _decision(self, symbol: str, timeframe: str) -> dict[str, Any]:
        # Retained as a raw diagnostic hook.  Automatic entries never use an
        # isolated timeframe decision; `_scan_symbol` consumes the governed
        # symbol-level consensus below.
        from workstation.quant_firm_runtime import decision_payload

        result = decision_payload(symbol, timeframe)
        return dict(result) if isinstance(result, dict) else {}

    def _scan_symbol(self, symbol: str) -> dict[str, Any]:
        from workstation.quant_terminal_v2 import scan_payload

        try:
            result = scan_payload(symbol, profile=self.profile)
            return dict(result) if isinstance(result, dict) else {}
        except Exception as exc:
            return {
                "success": False,
                "symbol": symbol,
                "side": "WAIT",
                "qualified": False,
                "message": f"{type(exc).__name__}: {exc}"[:300],
                "paper_only": True,
                "live_execution": False,
            }

    @staticmethod
    def _rank_key(row: dict[str, Any]) -> tuple[float, float]:
        return (
            float(row.get("score") or 0.0),
            float(row.get("risk_reward") or 0.0),
        )

    def scan_once(self) -> dict[str, Any]:
        if not self._scan_guard.acquire(blocking=False):
            return {
                "success": True,
                "reason": "SCAN_ALREADY_RUNNING",
                "paper_only": True,
                "live_execution": False,
            }
        try:
            return self._scan_once_unlocked()
        finally:
            self._scan_guard.release()

    def _scan_once_unlocked(self) -> dict[str, Any]:
        started = time.perf_counter()
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._scan_symbol, symbol): symbol for symbol in self.universe}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    rows.append(
                        {
                            "success": False,
                            "symbol": symbol,
                            "message": f"{type(exc).__name__}: {exc}"[:300],
                        }
                    )

        candidates = [
            row
            for row in rows
            if row.get("success")
            and row.get("qualified") is True
            and str(row.get("side") or "").upper() in {"LONG", "SHORT"}
            and float(row.get("score") or 0.0) >= self.min_score
            and float(row.get("risk_reward") or 0.0) >= self.min_risk_reward
            and row.get("entry") is not None
            and row.get("stop") is not None
            and row.get("target") is not None
        ]
        candidates.sort(key=self._rank_key, reverse=True)

        rejection_counts = Counter()
        for row in rows:
            blockers = list(row.get("blockers") or [])
            if not row.get("success") and not blockers:
                blockers = ["DATA_UNAVAILABLE"]
            if not blockers and not row.get("qualified"):
                blockers = ["NO_QUALIFIED_SETUP"]
            rejection_counts.update(str(item) for item in blockers)

        snapshot = paper_desk.snapshot()
        already_open = {str(item.get("symbol") or "").upper() for item in snapshot.get("positions") or []}
        opened = []

        for row in candidates:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol or symbol in already_open:
                continue
            strategy = "QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4"
            try:
                from workstation.bounded_decision_review import decision_review_coordinator

                policy = decision_review_coordinator.policy_for(strategy, self.profile)
            except Exception:
                policy = {"allowed": True, "risk_multiplier": 1.0}
            if not policy.get("allowed", True):
                rejection_counts["ADAPTIVE_COHORT_QUARANTINED"] += 1
                continue
            if float(row.get("score") or 0.0) < self.min_score + float(policy.get("minimum_score_delta") or 0.0):
                rejection_counts["ADAPTIVE_SCORE_GATE"] += 1
                continue
            if float(row.get("risk_reward") or 0.0) < self.min_risk_reward + float(policy.get("minimum_risk_reward_delta") or 0.0):
                rejection_counts["ADAPTIVE_RISK_REWARD_GATE"] += 1
                continue
            try:
                from workstation.paper_trade_action_router import _live_entry

                live_entry, live_blocker = _live_entry(row)
            except Exception:
                live_entry, live_blocker = None, "LIVE_ENTRY_VALIDATION_FAILED"
            if live_entry is None:
                rejection_counts[str(live_blocker or "LIVE_ENTRY_VALIDATION_FAILED")] += 1
                continue
            valuation_multiplier = 1.0
            try:
                from workstation.paper_market_data import PAPER_MARKET_DATA

                instrument_spec = PAPER_MARKET_DATA.instrument_spec(symbol)
            except Exception:
                rejection_counts["INSTRUMENT_SPEC_UNAVAILABLE"] += 1
                continue
            if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
                try:
                    valuation_quote = PAPER_MARKET_DATA.quote(symbol)
                    native_ltp = float(valuation_quote.get("native_ltp") or 0.0)
                    valuation_ltp = float(valuation_quote.get("valuation_ltp") or 0.0)
                    if not valuation_quote.get("success") or native_ltp <= 0 or valuation_ltp <= 0:
                        raise ValueError("crypto valuation reference unavailable")
                    valuation_multiplier = valuation_ltp / native_ltp
                except Exception:
                    rejection_counts["VALUATION_FX_UNAVAILABLE"] += 1
                    continue
            evidence = list(row.get("evidence") or [])
            signal_bar = next(
                (
                    str(item.get("last_candle_time"))
                    for item in evidence
                    if item.get("last_candle_time") is not None
                ),
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M"),
            )
            result = paper_desk.open_position(
                symbol=symbol,
                side=str(row.get("side")),
                entry=float(live_entry),
                stop=float(row["stop"]),
                target=float(row["target"]),
                quantity=None,
                timeframe=str(row.get("timeframe") or ""),
                strategy=strategy,
                score=float(row.get("score") or 0.0),
                source="AUTONOMOUS_PAPER",
                asset_type=(
                    "CRYPTO"
                    if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}
                    else "COMMODITY"
                    if symbol in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
                    else "EQUITY"
                    if symbol not in DEFAULT_UNIVERSE
                    else "MARKET"
                ),
                external_id=(
                    "auto:"
                    + symbol
                    + ":"
                    + str(row.get("timeframe") or "")
                    + ":"
                    + self.profile
                    + ":"
                    + signal_bar
                ),
                metadata={
                    "regime": row.get("regime"),
                    "alignment": row.get("alignment"),
                    "risk_reward": row.get("risk_reward"),
                    "votes": row.get("votes") or [],
                    "decisions": row.get("decisions") or [],
                    "decision_version": row.get("decision_version"),
                    "risk_model": row.get("risk_model"),
                    "evidence_graph": row.get("evidence_graph") or [],
                    "contradictions": row.get("contradictions") or [],
                    "reasons_not_to_trade": row.get("reasons_not_to_trade") or [],
                    "profile": self.profile,
                    "profile_risk_multiplier": self.profile_risk_multiplier,
                    "adaptive_policy": policy,
                    "initial_risk": abs(float(live_entry) - float(row["stop"])),
                    "exit_policy": {
                        "breakeven_at_r": 1.0 if self.profile == "swing" else 0.75,
                        "trailing_at_r": 1.5 if self.profile == "swing" else 1.0,
                        "trailing_distance_r": 0.75 if self.profile == "swing" else 0.50,
                        "trailing_target_r": 1.5 if self.profile == "swing" else 1.0,
                        "scale_out": [
                            {"at_r": 1.0, "fraction": 0.34},
                            {"at_r": 2.0, "fraction": 0.50},
                        ],
                        "max_hold_minutes": 10080 if self.profile == "swing" else 390,
                    },
                },
                risk_multiplier=(
                    self.profile_risk_multiplier
                    * float(policy.get("risk_multiplier") or 1.0)
                ),
                valuation_multiplier=valuation_multiplier,
                instrument_spec=instrument_spec,
            )
            if result.get("success") and result.get("reason") == "PAPER_POSITION_OPENED":
                opened.append(result)
                already_open.add(symbol)
            else:
                rejection_counts[str(result.get("reason") or "PAPER_DESK_ENTRY_REJECTED")] += 1

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        with self._lock:
            self._scan_cycles += 1
            self._positions_opened += len(opened)
            self._last_scan_at = datetime.now(timezone.utc).isoformat()
            self._last_candidates = [
                {
                    "symbol": row.get("symbol"),
                    "timeframe": row.get("timeframe"),
                    "side": row.get("side"),
                    "score": row.get("score"),
                    "regime": row.get("regime"),
                    "risk_reward": row.get("risk_reward"),
                    "alignment": row.get("alignment"),
                    "decision_version": row.get("decision_version"),
                }
                for row in candidates[:20]
            ]
            self._last_rejection_counts = dict(rejection_counts)
            self._last_rows_summary = [
                {
                    "symbol": row.get("symbol"),
                    "side": row.get("side"),
                    "candidate_side": row.get("candidate_side"),
                    "score": row.get("score"),
                    "qualified": row.get("qualified"),
                    "blockers": list(row.get("blockers") or []),
                    "message": row.get("message"),
                }
                for row in rows
            ]

        return {
            "success": True,
            "elapsed_ms": elapsed_ms,
            "rows": len(rows),
            "candidate_count": len(candidates),
            "opened": opened,
            "profile": self.profile,
            "timeframes": list(self.timeframes),
            "rejection_counts": dict(rejection_counts),
            "paper_only": True,
            "live_execution": False,
        }

    def mark_once(self) -> dict[str, Any]:
        snapshot = paper_desk.snapshot()
        symbols = [str(item.get("symbol") or "").upper() for item in snapshot.get("positions") or []]
        marks: dict[str, float] = {}
        certificates: list[dict[str, Any]] = []
        if symbols:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(symbols))) as pool:
                futures = {pool.submit(live_mark_snapshot, symbol): symbol for symbol in symbols}
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        certificate = dict(future.result())
                    except Exception as exc:
                        certificate = {
                            "success": False,
                            "symbol": symbol,
                            "eligible_for_exit": False,
                            "reason": f"MARK_UNAVAILABLE:{type(exc).__name__}",
                        }
                    certificates.append(certificate)
                    if certificate.get("eligible_for_exit") and certificate.get("mark") is not None:
                        marks[symbol] = float(certificate["mark"])
        closed = paper_desk.manage_positions(marks)
        rejected = Counter(
            str(item.get("reason") or "MARK_REJECTED")
            for item in certificates
            if not item.get("eligible_for_exit")
        )
        with self._lock:
            self._mark_cycles += 1
            self._positions_closed += sum(1 for item in closed if item.get("success"))
            self._last_mark_at = datetime.now(timezone.utc).isoformat()
            self._last_mark_rejection_counts = dict(rejected)
            self._last_mark_certificates = certificates[-24:]
        return {
            "success": True,
            "marks": marks,
            "closed": closed,
            "certificates": certificates,
            "rejection_counts": dict(rejected),
            "paper_only": True,
            "live_execution": False,
        }

    def _scan_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception as exc:
                with self._lock:
                    self._errors += 1
                    self._last_error = f"{type(exc).__name__}: {exc}"[:500]
            if self._stop.wait(self.scan_interval_seconds):
                break
        with self._lock:
            self._running = False

    def _mark_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.mark_once()
            except Exception as exc:
                with self._lock:
                    self._errors += 1
                    self._last_error = f"{type(exc).__name__}: {exc}"[:500]
            if self._stop.wait(self.mark_interval_seconds):
                break


paper_autonomy = PaperAutonomyEngine()
