from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable

from workstation.paper_trading_desk import live_mark_loader, paper_desk


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
        min_risk_reward: float = 1.5,
        scan_interval_seconds: float = 15.0,
        mark_interval_seconds: float = 0.75,
        max_workers: int = 4,
    ) -> None:
        self.universe = tuple(str(item).upper() for item in universe)
        self.timeframes = tuple(str(item) for item in timeframes)
        self.min_score = float(min_score)
        self.min_risk_reward = float(min_risk_reward)
        self.scan_interval_seconds = max(5.0, float(scan_interval_seconds))
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
        self._last_error: str | None = None
        self._last_candidates: list[dict[str, Any]] = []

    @property
    def live_execution(self) -> bool:
        return False

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return self.status()
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
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            self._running = False
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "running": self._running and not self._stop.is_set(),
                "universe": list(self.universe),
                "timeframes": list(self.timeframes),
                "min_score": self.min_score,
                "min_risk_reward": self.min_risk_reward,
                "scan_interval_seconds": self.scan_interval_seconds,
                "mark_interval_seconds": self.mark_interval_seconds,
                "scan_cycles": self._scan_cycles,
                "mark_cycles": self._mark_cycles,
                "positions_opened": self._positions_opened,
                "positions_closed": self._positions_closed,
                "errors": self._errors,
                "last_scan_at": self._last_scan_at,
                "last_mark_at": self._last_mark_at,
                "last_error": self._last_error,
                "last_candidates": list(self._last_candidates[-20:]),
                "paper_only": True,
                "live_execution": False,
            }

    def _decision(self, symbol: str, timeframe: str) -> dict[str, Any]:
        from workstation.quant_firm_runtime import decision_payload

        result = decision_payload(symbol, timeframe)
        return dict(result) if isinstance(result, dict) else {}

    def _scan_symbol(self, symbol: str) -> list[dict[str, Any]]:
        rows = []
        for timeframe in self.timeframes:
            try:
                result = self._decision(symbol, timeframe)
            except Exception as exc:
                rows.append(
                    {
                        "success": False,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "message": f"{type(exc).__name__}: {exc}"[:300],
                    }
                )
                continue
            rows.append(result)
        return rows

    @staticmethod
    def _rank_key(row: dict[str, Any]) -> tuple[float, float]:
        return (
            float(row.get("score") or 0.0),
            float(row.get("risk_reward") or 0.0),
        )

    def scan_once(self) -> dict[str, Any]:
        started = time.perf_counter()
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._scan_symbol, symbol): symbol for symbol in self.universe}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    rows.extend(future.result())
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
            and str(row.get("side") or "").upper() in {"LONG", "SHORT"}
            and float(row.get("score") or 0.0) >= self.min_score
            and float(row.get("risk_reward") or 0.0) >= self.min_risk_reward
            and row.get("entry") is not None
            and row.get("stop") is not None
            and row.get("target") is not None
        ]
        candidates.sort(key=self._rank_key, reverse=True)

        snapshot = paper_desk.snapshot()
        already_open = {str(item.get("symbol") or "").upper() for item in snapshot.get("positions") or []}
        opened = []

        for row in candidates:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol or symbol in already_open:
                continue
            result = paper_desk.open_position(
                symbol=symbol,
                side=str(row.get("side")),
                entry=float(row["entry"]),
                stop=float(row["stop"]),
                target=float(row["target"]),
                quantity=None,
                timeframe=str(row.get("timeframe") or ""),
                strategy="QUANT_V4_REGIME_ENSEMBLE",
                score=float(row.get("score") or 0.0),
                source="AUTONOMOUS_PAPER",
                asset_type="CRYPTO" if symbol in {"BTC", "ETH", "SOL"} else "MARKET",
                external_id=(
                    "auto:"
                    + symbol
                    + ":"
                    + str(row.get("timeframe") or "")
                    + ":"
                    + datetime.now(timezone.utc).strftime("%Y%m%d")
                ),
                metadata={
                    "regime": row.get("regime"),
                    "risk_reward": row.get("risk_reward"),
                    "votes": row.get("votes") or [],
                },
            )
            if result.get("success") and result.get("reason") == "PAPER_POSITION_OPENED":
                opened.append(result)
                already_open.add(symbol)

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
                }
                for row in candidates[:20]
            ]

        return {
            "success": True,
            "elapsed_ms": elapsed_ms,
            "rows": len(rows),
            "candidate_count": len(candidates),
            "opened": opened,
            "paper_only": True,
            "live_execution": False,
        }

    def mark_once(self) -> dict[str, Any]:
        snapshot = paper_desk.snapshot()
        symbols = [str(item.get("symbol") or "").upper() for item in snapshot.get("positions") or []]
        marks: dict[str, float] = {}
        for symbol in symbols:
            mark = live_mark_loader(symbol)
            if mark is not None:
                marks[symbol] = mark
        closed = paper_desk.evaluate_stops_targets(marks)
        with self._lock:
            self._mark_cycles += 1
            self._positions_closed += sum(1 for item in closed if item.get("success"))
            self._last_mark_at = datetime.now(timezone.utc).isoformat()
        return {
            "success": True,
            "marks": marks,
            "closed": closed,
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
