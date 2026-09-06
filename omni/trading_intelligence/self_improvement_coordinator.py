from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omni.trading_intelligence.trade_learning_engine import learning_engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "data" / "trading_intelligence" / "research_state.json"
DEFAULT_RESEARCH_INTERVAL_SECONDS = 900.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SelfImprovementCoordinator:
    """Governed background research loop for adaptive paper trading.

    The loop analyzes accumulated paper outcomes, identifies where research is
    warranted, runs candidate strategy research on verified historical data and
    stores challenger proposals. It never edits production strategy code and it
    never exposes live broker execution.
    """

    def __init__(self, interval_seconds: float = DEFAULT_RESEARCH_INTERVAL_SECONDS) -> None:
        self.interval_seconds = max(300.0, float(interval_seconds))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._cycles = 0
        self._errors = 0
        self._last_error: str | None = None
        self._last_run_at: str | None = None
        self._last_report: dict[str, Any] | None = self._load_state()

    @property
    def live_execution(self) -> bool:
        return False

    def _load_state(self) -> dict[str, Any] | None:
        try:
            if STATE_PATH.exists():
                value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                return value if isinstance(value, dict) else None
        except Exception:
            pass
        return None

    def _save_state(self, report: dict[str, Any]) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(STATE_PATH)

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return self.status()
            self._stop.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._loop,
                name="JarvisQuantSelfImprovement",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            self._running = False
        return self.status()

    def _research_targets(self) -> list[tuple[str, str]]:
        status = learning_engine.status()
        recent = list(status.get("recent_outcomes") or [])
        scores: dict[str, float] = {}
        for row in recent[-120:]:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol:
                continue
            pnl = float(row.get("pnl") or 0.0)
            mistakes = len(row.get("mistake_hypotheses") or [])
            scores[symbol] = scores.get(symbol, 0.0) + (2.0 if pnl < 0 else 0.25) + mistakes * 0.5
        if not scores:
            return [("BTC", "15m"), ("NIFTY", "15m")]
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [(symbol, "15m") for symbol, _score in ranked[:3]]

    def run_once(self) -> dict[str, Any]:
        from omni.trading_intelligence.strategy_research_lab import research_candidates
        from workstation.quant_terminal_v2 import candles_payload

        started = time.perf_counter()
        targets = self._research_targets()
        reports: list[dict[str, Any]] = []
        challengers: list[dict[str, Any]] = []
        for symbol, timeframe in targets:
            try:
                market = candles_payload(symbol, timeframe, 950)
                candles = list(market.get("candles") or []) if market.get("success") else []
                if len(candles) < 120:
                    reports.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "success": False,
                            "reason": "INSUFFICIENT_VERIFIED_HISTORY",
                        }
                    )
                    continue
                research = research_candidates(symbol, timeframe, candles)
                best = research.get("best_candidate") or {}
                reports.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "success": True,
                        "best_candidate": best,
                    }
                )
                if best.get("status") == "PAPER_CHALLENGER":
                    challengers.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "candidate": best.get("candidate"),
                            "quality_score": best.get("quality_score"),
                            "backtest": best.get("backtest"),
                            "walk_forward": best.get("walk_forward"),
                            "status": "PAPER_CHALLENGER",
                        }
                    )
            except Exception as exc:
                reports.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "success": False,
                        "reason": f"{type(exc).__name__}: {exc}"[:500],
                    }
                )

        report = {
            "generated_at": _now(),
            "elapsed_ms": (time.perf_counter() - started) * 1000.0,
            "targets": [{"symbol": symbol, "timeframe": timeframe} for symbol, timeframe in targets],
            "reports": reports,
            "challengers": challengers,
            "learning": {
                "family_weights": learning_engine.family_weights(),
                "mistakes": learning_engine.mistake_report().get("ranked_mistakes") or [],
            },
            "governance": {
                "automatic_production_code_rewrite": False,
                "automatic_live_promotion": False,
                "paper_challenger_only": True,
                "requires_walk_forward": True,
            },
            "research_only": True,
            "live_execution": False,
        }
        self._save_state(report)
        with self._lock:
            self._cycles += 1
            self._last_run_at = report["generated_at"]
            self._last_report = report
            self._last_error = None
        return report

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "running": self._running and not self._stop.is_set(),
                "cycles": self._cycles,
                "errors": self._errors,
                "last_error": self._last_error,
                "last_run_at": self._last_run_at,
                "interval_seconds": self.interval_seconds,
                "last_report": self._last_report,
                "research_only": True,
                "live_execution": False,
            }

    def _loop(self) -> None:
        # Delay the first heavy research cycle so startup stays responsive.
        if self._stop.wait(30.0):
            return
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception as exc:
                with self._lock:
                    self._errors += 1
                    self._last_error = f"{type(exc).__name__}: {exc}"[:500]
            if self._stop.wait(self.interval_seconds):
                break
        with self._lock:
            self._running = False


self_improvement_coordinator = SelfImprovementCoordinator()
