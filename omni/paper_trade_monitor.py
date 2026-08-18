from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class PaperMonitorSession:
    session_id: str
    symbol: str
    timeframe: str
    interval_seconds: float
    active: bool = True
    created_at: float = field(default_factory=time.time)
    checks: int = 0
    last_action: str = "WAIT"
    last_message: str = "Waiting for first analysis."
    paper_trade: dict | None = None


class PaperTradeMonitor:
    """Background monitor that only records paper candidates."""

    MIN_INTERVAL_SECONDS = 15.0
    MAX_SESSIONS = 8

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: dict[str, PaperMonitorSession] = {}

    @staticmethod
    def interval_from_request(text: str, default: float = 60.0) -> float:
        value = str(text or "").lower()
        match = re.search(
            r"\bevery\s+(\d+)\s*(second|seconds|sec|secs|minute|minutes|min|mins)\b",
            value,
        )
        if not match:
            return default
        amount = max(1, int(match.group(1)))
        unit = match.group(2)
        seconds = amount * (60 if unit.startswith(("minute", "min")) else 1)
        return max(PaperTradeMonitor.MIN_INTERVAL_SECONDS, float(seconds))

    def start(self, symbol: str, timeframe: str = "15m", request: str = "") -> dict:
        symbol = str(symbol or "").strip().upper()
        timeframe = str(timeframe or "15m").strip().lower()
        if not symbol:
            raise ValueError("symbol is required")

        with self._lock:
            for session in self._sessions.values():
                if session.active and session.symbol == symbol and session.timeframe == timeframe:
                    return {
                        "success": True,
                        "session_id": session.session_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "paper_only": True,
                        "live_execution": False,
                        "already_running": True,
                    }

            if len([s for s in self._sessions.values() if s.active]) >= self.MAX_SESSIONS:
                raise RuntimeError("Maximum active paper monitors reached.")

            session = PaperMonitorSession(
                session_id="paper-monitor-" + uuid.uuid4().hex[:10],
                symbol=symbol,
                timeframe=timeframe,
                interval_seconds=self.interval_from_request(request),
            )
            self._sessions[session.session_id] = session

        threading.Thread(
            target=self._run,
            args=(session.session_id,),
            daemon=True,
            name=f"JarvisPaperMonitor-{symbol}",
        ).start()

        return {
            "success": True,
            "session_id": session.session_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "interval_seconds": session.interval_seconds,
            "paper_only": True,
            "live_execution": False,
            "background_monitoring": True,
        }

    def _run(self, session_id: str) -> None:
        from agents.trading_agent import trading_agent

        while True:
            with self._lock:
                session = self._sessions.get(session_id)
                if session is None or not session.active:
                    return
                symbol = session.symbol
                timeframe = session.timeframe
                interval = session.interval_seconds

            try:
                result = trading_agent.analyze(
                    symbol=symbol,
                    market="india",
                    timeframe=timeframe,
                )
                signal = result.get("signal", {}) if isinstance(result, dict) else {}
                action = str(signal.get("action") or "WAIT").upper()
                risk = result.get("risk") if isinstance(result, dict) else None

                paper_trade = None
                message = f"{symbol} {timeframe}: {action}"

                if (
                    action in {"BUY", "SELL"}
                    and risk is not None
                    and bool(getattr(risk, "approved", False))
                ):
                    paper_trade = {
                        "mode": "PAPER",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "side": action,
                        "entry": signal.get("entry"),
                        "stop_loss": signal.get("stop_loss"),
                        "target": signal.get("target"),
                        "risk_reason": getattr(risk, "reason", None),
                        "created_at": time.time(),
                        "live_execution": False,
                    }
                    message = f"Paper {action} candidate recorded for {symbol}."

                with self._lock:
                    current = self._sessions.get(session_id)
                    if current is None:
                        return
                    current.checks += 1
                    current.last_action = action
                    current.last_message = message
                    if paper_trade is not None:
                        current.paper_trade = paper_trade
                        current.active = False
                        return

            except Exception as exc:
                with self._lock:
                    current = self._sessions.get(session_id)
                    if current is None:
                        return
                    current.checks += 1
                    current.last_action = "ERROR"
                    current.last_message = f"{type(exc).__name__}: {exc}"

            time.sleep(interval)

    def stop(self, session_id: str | None = None, symbol: str | None = None) -> dict:
        stopped = []
        with self._lock:
            for sid, session in self._sessions.items():
                if not session.active:
                    continue
                if session_id and sid != session_id:
                    continue
                if symbol and session.symbol != str(symbol).upper():
                    continue
                session.active = False
                stopped.append(sid)

        return {
            "success": True,
            "stopped": tuple(stopped),
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict:
        with self._lock:
            sessions = tuple(
                {
                    "session_id": s.session_id,
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "interval_seconds": s.interval_seconds,
                    "active": s.active,
                    "checks": s.checks,
                    "last_action": s.last_action,
                    "last_message": s.last_message,
                    "paper_trade": dict(s.paper_trade) if s.paper_trade else None,
                }
                for s in self._sessions.values()
            )

        return {
            "success": True,
            "sessions": sessions,
            "background_monitoring": True,
            "paper_only": True,
            "live_execution": False,
        }


paper_trade_monitor = PaperTradeMonitor()
