from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import re
import threading
import time
from typing import Any

from workstation.advanced_pattern_engine import analyze_chart_patterns
from workstation.equity_universe import nifty50_constituents


_SCAN_RE = re.compile(
    r"\b(?:scan|check|find|rank|analy[sz]e)\b.*\b(?:nifty\s*50|nifty50)\b.*\b(?:stocks?|companies|breakouts?|breakdowns?|setups?|swing|universe)\b|"
    r"\b(?:breakouts?|breakdowns?|setups?)\b.*\b(?:nifty\s*50|nifty50)\b",
    flags=re.IGNORECASE,
)


def is_nifty50_scan_request(text: str) -> bool:
    return bool(_SCAN_RE.search(str(text or "")))


class Nifty50BreakoutScanner:
    """Rate-bounded background scanner for the official NSE NIFTY 50 list."""

    def __init__(self, *, max_workers: int = 3, cache_seconds: float = 300.0) -> None:
        self.max_workers = max(1, min(int(max_workers), 4))
        self.cache_seconds = max(30.0, float(cache_seconds))
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._started_at: str | None = None
        self._completed_at: str | None = None
        self._last_completed_mono = 0.0
        self._source = ""
        self._scanned = 0
        self._total = 50
        self._results: list[dict[str, Any]] = []
        self._errors: list[dict[str, str]] = []
        self._auto_enroll = False

    def status(self) -> dict[str, Any]:
        with self._lock:
            candidates = [row for row in self._results if row.get("candidate")]
            return {
                "success": True,
                "running": self._running,
                "universe": "NIFTY50",
                "timeframe": "1d",
                "profile": "swing_breakout_prefilter",
                "source": self._source,
                "started_at": self._started_at,
                "completed_at": self._completed_at,
                "scanned": self._scanned,
                "total": self._total,
                "candidate_count": len(candidates),
                "candidates": candidates[:15],
                "results": list(self._results[:50]),
                "errors": list(self._errors[:10]),
                "auto_enroll": self._auto_enroll,
                "paper_only": True,
                "live_execution": False,
            }

    def start(self, *, force: bool = False, auto_enroll: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._running:
                if auto_enroll:
                    self._auto_enroll = True
                return self.status()
            if (
                not force
                and self._last_completed_mono
                and time.monotonic() - self._last_completed_mono < self.cache_seconds
            ):
                if auto_enroll:
                    self._enroll_candidates_locked()
                return self.status()
            self._running = True
            self._auto_enroll = bool(auto_enroll)
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._completed_at = None
            self._scanned = 0
            self._results = []
            self._errors = []
            self._thread = threading.Thread(
                target=self._run,
                name="JarvisNifty50BreakoutScanner",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    @staticmethod
    def _risk_levels(candles: list[dict[str, Any]], pattern: dict[str, Any]) -> dict[str, float | None]:
        close = float(candles[-1]["close"])
        atr = float(pattern.get("atr_proxy") or 0.0)
        direction = str(pattern.get("direction") or "NEUTRAL")
        if atr <= 0 or direction not in {"BULLISH", "BEARISH"}:
            return {"entry": None, "stop": None, "target": None, "risk_reward": None}
        if direction == "BULLISH":
            level = float(pattern.get("breakout_level") or close)
            entry = max(close, level + 0.05 * atr)
            stop = entry - 1.5 * atr
            target = entry + 3.0 * atr
        else:
            level = float(pattern.get("breakdown_level") or close)
            entry = min(close, level - 0.05 * atr)
            stop = entry + 1.5 * atr
            target = entry - 3.0 * atr
        return {"entry": entry, "stop": stop, "target": target, "risk_reward": 2.0}

    @staticmethod
    def _scan_one(instrument: Any) -> dict[str, Any]:
        from omni.trading_intelligence.quant_firm_engine import decide
        from workstation.quant_terminal_v2 import candles_payload

        payload = candles_payload(instrument.symbol, "1d", 180)
        candles = list(payload.get("candles") or [])
        if not payload.get("success") or len(candles) < 60:
            return {
                "symbol": instrument.symbol,
                "label": instrument.label,
                "industry": instrument.industry,
                "success": False,
                "candidate": False,
                "message": payload.get("message") or "Daily candles unavailable.",
            }
        pattern = analyze_chart_patterns(candles)
        decision = decide(instrument.symbol, "1d", candles).to_dict()
        pattern_direction = str(pattern.get("direction") or "NEUTRAL")
        decision_side = str(decision.get("side") or "WAIT")
        decision_direction = "BULLISH" if decision_side == "LONG" else "BEARISH" if decision_side == "SHORT" else "NEUTRAL"
        score = 0.65 * float(pattern.get("score") or 0.0) + 0.35 * float(decision.get("score") or 0.0)
        if decision_direction not in {"NEUTRAL", pattern_direction}:
            score -= 18.0
        state = str(pattern.get("state") or "NO_EDGE")
        candidate = state in {
            "CONFIRMED_BREAKOUT", "UNCONFIRMED_BREAKOUT", "BREAKOUT_WATCH",
            "CONFIRMED_BREAKDOWN", "UNCONFIRMED_BREAKDOWN", "BREAKDOWN_WATCH",
        } and score >= 55.0
        levels = Nifty50BreakoutScanner._risk_levels(candles, pattern)
        return {
            "success": True,
            "symbol": instrument.symbol,
            "label": instrument.label,
            "industry": instrument.industry,
            "provider_symbol": instrument.provider_symbol,
            "state": state,
            "direction": pattern_direction,
            "signal": "BUY" if pattern_direction == "BULLISH" else "SELL" if pattern_direction == "BEARISH" else "WAIT",
            "score": round(max(0.0, min(score, 100.0)), 2),
            "candidate": candidate,
            "close": float(candles[-1]["close"]),
            "breakout_level": pattern.get("breakout_level"),
            "breakdown_level": pattern.get("breakdown_level"),
            "distance_to_breakout_percent": pattern.get("distance_to_breakout_percent"),
            "distance_to_breakdown_percent": pattern.get("distance_to_breakdown_percent"),
            "volume_ratio": pattern.get("volume_ratio"),
            "structure": pattern.get("structure"),
            "patterns": pattern.get("patterns") or [],
            "quant_side": decision_side,
            "quant_score": decision.get("score"),
            **levels,
            "message": pattern.get("message"),
            "paper_only": True,
            "live_execution": False,
        }

    def _enroll_candidates_locked(self) -> None:
        symbols = [row["symbol"] for row in self._results if row.get("candidate")][:8]
        if not symbols:
            return
        from workstation.paper_autonomy_engine import paper_autonomy

        paper_autonomy.add_symbols(symbols)

    def _run(self) -> None:
        try:
            instruments, source = nifty50_constituents(force_refresh=True)
            with self._lock:
                self._source = source
                self._total = len(instruments)
            rows: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(self._scan_one, item): item for item in instruments}
                for future in as_completed(futures):
                    item = futures[future]
                    try:
                        row = future.result()
                    except Exception as exc:
                        row = {
                            "success": False,
                            "symbol": item.symbol,
                            "label": item.label,
                            "candidate": False,
                            "message": f"{type(exc).__name__}: {exc}"[:300],
                        }
                    rows.append(row)
                    with self._lock:
                        self._scanned += 1
                        if not row.get("success"):
                            self._errors.append({"symbol": item.symbol, "message": str(row.get("message") or "")[:240]})
            rows.sort(key=lambda row: (bool(row.get("candidate")), float(row.get("score") or 0.0)), reverse=True)
            with self._lock:
                self._results = rows
                self._last_completed_mono = time.monotonic()
                self._completed_at = datetime.now(timezone.utc).isoformat()
                if self._auto_enroll:
                    self._enroll_candidates_locked()
        finally:
            with self._lock:
                self._running = False


nifty50_scanner = Nifty50BreakoutScanner()


def nifty50_scan_command_payload(text: str) -> dict[str, Any] | None:
    if not is_nifty50_scan_request(text):
        return None
    status = nifty50_scanner.start(force=True, auto_enroll=False)
    return {
        **status,
        "action": "nifty50_breakout_scan",
        "speech": (
            "The official NIFTY 50 swing-breakout scan has started in the background. "
            "It checks look-ahead-safe 20-day levels, volume, structure, candlestick patterns, "
            "and the Quant ensemble, then ranks conditional entry, stop and target references. "
            "No broker order will be sent."
        ),
    }

