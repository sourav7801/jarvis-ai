from __future__ import annotations

import threading
import time
from typing import Any


class CandidateHorizonRouter:
    """Bridge completed discovery cycles into the three governed paper horizons.

    The broad scanner owns discovery only. This watcher notices a new completed
    scanner cycle and asks the PaperPortfolioController to enroll eligible names
    into INTRADAY, SWING and INVESTMENT watchlists. No broker execution surface
    is imported here; each target engine independently recomputes execution gates.
    """

    def __init__(self, *, poll_seconds: float = 2.0) -> None:
        self.poll_seconds = max(0.5, float(poll_seconds))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_seen_completion: str | None = None
        self._route_cycles = 0
        self._last_error: str | None = None
        self._last_result: dict[str, Any] = {}

    @property
    def live_execution(self) -> bool:
        return False

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                self._running = True
                return self.status()
            self._stop.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._run,
                name="JarvisCandidateHorizonRouter",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=3.0)
        with self._lock:
            self._running = bool(thread and thread.is_alive())
        return self.status()

    def route_now(self) -> dict[str, Any]:
        from workstation.multi_market_scanner import multi_market_scanner
        from workstation.paper_portfolio_controller import paper_portfolio_controller

        scanner = multi_market_scanner.status()
        completed = str(scanner.get("completed_at") or "").strip()
        candidates = list(scanner.get("candidates") or [])
        if not completed:
            return {
                "success": True,
                "routed": False,
                "reason": "NO_COMPLETED_DISCOVERY_CYCLE",
                "paper_only": True,
                "live_execution": False,
            }
        result = paper_portfolio_controller.enroll_discovery_candidates(candidates)
        with self._lock:
            self._last_seen_completion = completed
            self._route_cycles += 1
            self._last_result = dict(result)
            self._last_error = None
        return {
            "success": True,
            "routed": True,
            "scanner_completed_at": completed,
            "routing": result,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "running": self._running and not self._stop.is_set(),
                "last_seen_completion": self._last_seen_completion,
                "route_cycles": self._route_cycles,
                "last_error": self._last_error,
                "last_result": dict(self._last_result),
                "paper_only": True,
                "live_execution": False,
            }

    def _run(self) -> None:
        try:
            while not self._stop.wait(self.poll_seconds):
                try:
                    from workstation.multi_market_scanner import multi_market_scanner

                    scanner = multi_market_scanner.status()
                    completed = str(scanner.get("completed_at") or "").strip()
                    with self._lock:
                        seen = self._last_seen_completion
                    if not completed or completed == seen:
                        continue
                    self.route_now()
                except Exception as exc:
                    with self._lock:
                        self._last_error = f"{type(exc).__name__}: {exc}"[:500]
                    time.sleep(min(self.poll_seconds, 2.0))
        finally:
            with self._lock:
                self._running = False


candidate_horizon_router = CandidateHorizonRouter()
