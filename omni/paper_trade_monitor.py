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
    errors: int = 0
    last_action: str = "WAIT"
    last_message: str = "Waiting for first analysis."
    last_price: float | None = None
    paper_trade: dict | None = None


class PaperTradeMonitor:
    """Background monitor that only records simulated paper positions.

    This module deliberately imports no broker order surface. It consumes the
    existing TradingAgent analysis, requires the existing risk engine to approve
    an entry, records a PAPER position, and can close that paper position on an
    opposite approved analytical signal. Live execution is always false.
    """

    MIN_INTERVAL_SECONDS = 15.0
    MAX_SESSIONS = 8
    MAX_CONSECUTIVE_ERRORS = 10

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

        return max(
            PaperTradeMonitor.MIN_INTERVAL_SECONDS,
            float(seconds),
        )

    def start(self, symbol: str, timeframe: str = "15m", request: str = "") -> dict:
        symbol = str(symbol or "").strip().upper()
        timeframe = str(timeframe or "15m").strip().lower()

        if not symbol:
            raise ValueError("symbol is required")

        with self._lock:
            for session in self._sessions.values():
                if (
                    session.active
                    and session.symbol == symbol
                    and session.timeframe == timeframe
                ):
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

    @staticmethod
    def _approved(risk) -> bool:
        return risk is not None and bool(
            getattr(risk, "approved", False)
        )

    @staticmethod
    def _entry_payload(symbol, timeframe, action, signal, risk, price):
        return {
            "mode": "PAPER",
            "status": "OPEN",
            "symbol": symbol,
            "timeframe": timeframe,
            "side": action,
            "entry": signal.get("entry") or price,
            "stop_loss": signal.get("stop_loss"),
            "target": signal.get("target"),
            "risk_reason": getattr(risk, "reason", None),
            "created_at": time.time(),
            "closed_at": None,
            "exit": None,
            "exit_reason": None,
            "live_execution": False,
        }

    @staticmethod
    def _opposite(side: str, action: str) -> bool:
        return (
            (side == "BUY" and action == "SELL")
            or (side == "SELL" and action == "BUY")
        )

    def _run(self, session_id: str) -> None:
        from agents.trading_agent import trading_agent

        consecutive_errors = 0

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

                if not isinstance(result, dict) or not result.get("success", False):
                    detail = (
                        result.get("message", "analysis unavailable")
                        if isinstance(result, dict)
                        else "analysis unavailable"
                    )
                    raise RuntimeError(str(detail))

                signal = result.get("signal", {})
                action = str(signal.get("action") or "WAIT").upper()
                risk = result.get("risk")
                price = result.get("price")
                approved = self._approved(risk)

                consecutive_errors = 0
                message = f"{symbol} {timeframe}: {action}"

                with self._lock:
                    current = self._sessions.get(session_id)
                    if current is None or not current.active:
                        return

                    current.checks += 1
                    current.errors = 0
                    current.last_action = action

                    try:
                        current.last_price = (
                            float(price)
                            if price is not None
                            else current.last_price
                        )
                    except (TypeError, ValueError):
                        pass

                    trade = current.paper_trade

                    if (
                        trade is None
                        and action in {"BUY", "SELL"}
                        and approved
                    ):
                        current.paper_trade = self._entry_payload(
                            symbol,
                            timeframe,
                            action,
                            signal,
                            risk,
                            price,
                        )
                        message = (
                            f"Paper {action} position opened for {symbol}. "
                            "Live execution remains locked."
                        )

                    elif (
                        trade is not None
                        and trade.get("status") == "OPEN"
                        and self._opposite(
                            str(trade.get("side") or "").upper(),
                            action,
                        )
                        and approved
                    ):
                        trade["status"] = "CLOSED"
                        trade["closed_at"] = time.time()
                        trade["exit"] = price
                        trade["exit_reason"] = (
                            "Opposite approved analytical signal."
                        )
                        trade["live_execution"] = False
                        current.active = False
                        message = (
                            f"Paper position closed for {symbol} on an opposite "
                            "approved signal. Live execution remained locked."
                        )

                    current.last_message = message

                    if not current.active:
                        return

            except Exception as exc:
                consecutive_errors += 1

                with self._lock:
                    current = self._sessions.get(session_id)
                    if current is None:
                        return

                    current.checks += 1
                    current.errors = consecutive_errors
                    current.last_action = "ERROR"
                    current.last_message = (
                        f"{type(exc).__name__}: {exc}"
                    )

                    if consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                        current.active = False
                        current.last_message = (
                            "Paper monitor stopped after repeated analysis errors: "
                            + current.last_message
                        )
                        return

            time.sleep(interval)

    def stop(
        self,
        session_id: str | None = None,
        symbol: str | None = None,
    ) -> dict:
        stopped = []
        normalized_symbol = (
            str(symbol).strip().upper()
            if symbol
            else None
        )

        with self._lock:
            for sid, session in self._sessions.items():
                if not session.active:
                    continue

                if session_id and sid != session_id:
                    continue

                if (
                    normalized_symbol
                    and session.symbol != normalized_symbol
                ):
                    continue

                session.active = False
                session.last_message = "Paper monitor stopped manually."
                stopped.append(sid)

        return {
            "success": True,
            "stopped": tuple(stopped),
            "paper_only": True,
            "live_execution": False,
        }

    def status(
        self,
        session_id: str | None = None,
    ) -> dict:
        with self._lock:
            if session_id:
                session = self._sessions.get(str(session_id))
                sessions = [session] if session is not None else []
            else:
                sessions = list(self._sessions.values())

            payload = tuple(
                {
                    "session_id": s.session_id,
                    "symbol": s.symbol,
                    "timeframe": s.timeframe,
                    "interval_seconds": s.interval_seconds,
                    "active": s.active,
                    "checks": s.checks,
                    "errors": s.errors,
                    "last_action": s.last_action,
                    "last_message": s.last_message,
                    "last_price": s.last_price,
                    "paper_trade": (
                        dict(s.paper_trade)
                        if s.paper_trade
                        else None
                    ),
                }
                for s in sessions
                if s is not None
            )

        return {
            "success": True,
            "session_count": len(payload),
            "active_count": sum(1 for item in payload if item["active"]),
            "sessions": payload,
            "background_monitoring": True,
            "paper_only": True,
            "live_execution": False,
        }


paper_trade_monitor = PaperTradeMonitor()
