"""Lifecycle-owned, read-only market data for the canonical workstation."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Callable, Iterable, Optional

from config import (
    FYERS_LIVE_DATA_ENABLED,
    FYERS_LIVE_LITE_MODE,
    FYERS_LIVE_SYMBOLS,
    MARKET_DATA_PROVIDER,
)


StreamLoader = Callable[[], Any]
ConfiguredCheck = Callable[[], bool]
QuoteLoader = Callable[[str], dict[str, Any]]


def _load_fyers_stream() -> Any:
    from agents.fyers_live_stream import fyers_live_stream

    return fyers_live_stream


def _fyers_is_configured() -> bool:
    from agents.fyers_auth_manager import is_configured

    return is_configured()


def _load_quote(symbol: str) -> dict[str, Any]:
    from agents.fyers_data_adapter import get_quote

    return get_quote(symbol)


def _safe_error(error: BaseException | str) -> str:
    value = f"{type(error).__name__}: {error}" if isinstance(error, BaseException) else str(error)
    return value.replace("\r", " ").replace("\n", " ")[:300]


class MarketRuntime:
    """Starts one FYERS data socket inside the workstation process.

    It owns only read-only market data.  The class has no broker execution
    methods and explicitly reports the project-wide live-order boundary.
    """

    def __init__(
        self,
        *,
        enabled: bool = FYERS_LIVE_DATA_ENABLED,
        provider: str = MARKET_DATA_PROVIDER,
        symbols: Iterable[str] = FYERS_LIVE_SYMBOLS,
        lite_mode: bool = FYERS_LIVE_LITE_MODE,
        stream_loader: StreamLoader = _load_fyers_stream,
        configured_check: ConfiguredCheck = _fyers_is_configured,
        quote_loader: Optional[QuoteLoader] = _load_quote,
    ) -> None:
        self.enabled = bool(enabled)
        self.provider = str(provider or "AUTO").strip().upper()
        self.symbols = tuple(dict.fromkeys(str(item).strip().upper() for item in symbols if str(item).strip()))
        self.lite_mode = bool(lite_mode)
        self._stream_loader = stream_loader
        self._configured_check = configured_check
        self._quote_loader = quote_loader
        self._lock = threading.RLock()
        self._stream: Any = None
        self._configured = False
        self._started = False
        self._error: Optional[str] = None
        self._seeded: dict[str, dict[str, Any]] = {}

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._started:
                return self.status()
            self._started = True
            self._error = None

        if not self.enabled:
            return self.status()
        if self.provider not in {"", "AUTO", "FYERS", "FYERS_ONLY"}:
            return self.status()
        if not self.symbols:
            with self._lock:
                self._error = "No FYERS live symbols are configured."
            return self.status()

        try:
            configured = bool(self._configured_check())
        except Exception as exc:
            configured = False
            with self._lock:
                self._error = _safe_error(exc)
        with self._lock:
            self._configured = configured
        if not configured:
            with self._lock:
                self._error = self._error or (
                    "FYERS token is not configured. Run the FYERS login command."
                )
            return self.status()

        try:
            stream = self._stream_loader()
            with self._lock:
                self._stream = stream
            stream.start(self.symbols, lite_mode=self.lite_mode)
        except Exception as exc:
            with self._lock:
                self._error = _safe_error(exc)
            return self.status()

        # Seed the dashboard with a REST quote so it remains informative while
        # the market is closed and before the first WebSocket tick arrives.
        if self._quote_loader is not None:
            for symbol in self.symbols:
                try:
                    quote = self._quote_loader(symbol)
                    if quote.get("success"):
                        self._seeded[symbol] = {
                            **quote,
                            "snapshot_kind": "QUOTE_SEED",
                            "received_at": datetime.now(timezone.utc).isoformat(),
                        }
                except Exception:
                    # The socket remains useful even when optional seeding fails.
                    continue
        return self.status()

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
        if stream is not None:
            try:
                stream.stop()
            except Exception as exc:
                with self._lock:
                    self._error = _safe_error(exc)

    def restart(self) -> dict[str, Any]:
        """Reconnect read-only market data after a token refresh."""

        self.stop()
        with self._lock:
            self._stream = None
            self._configured = False
            self._started = False
            self._error = None
            self._seeded = {}
        return self.start()


    def health_status(self) -> dict[str, Any]:
        """
        Return a bounded, non-blocking health snapshot.

        Unlike status(), this method never calls stream.status().
        It is intended for HTTP liveness/health endpoints where a
        provider or websocket must never delay the response.
        """
        with self._lock:
            stream_present = self._stream is not None

            return {
                "provider": "FYERS",
                "enabled": self.enabled,
                "configured": self._configured,
                "started": self._started,
                "running": bool(self._started and stream_present),
                "connected": False,
                "symbols": list(self.symbols),
                "snapshots": len(self._seeded),
                "error": self._error,
                "data_only": True,
                "live_orders": False,
            }

    def status(self) -> dict[str, Any]:
        with self._lock:
            stream = self._stream
            base = {
                "provider": "FYERS",
                "enabled": self.enabled,
                "configured": self._configured,
                "started": self._started,
                "running": False,
                "connected": False,
                "symbols": list(self.symbols),
                "snapshots": len(self._seeded),
                "error": self._error,
                "data_only": True,
                "live_orders": False,
            }
        if stream is None:
            return base
        try:
            stream_status = stream.status()
            return {
                **base,
                **stream_status,
                "enabled": self.enabled,
                "configured": self._configured,
                "started": self._started,
                "error": stream_status.get("error") or self._error,
                "data_only": True,
                "live_orders": False,
            }
        except Exception as exc:
            return {**base, "error": _safe_error(exc)}

    def snapshot(self, symbol: str) -> Optional[dict[str, Any]]:
        alias = str(symbol or "").strip().upper()
        with self._lock:
            stream = self._stream
        result = None
        if stream is not None:
            try:
                result = stream.snapshot(alias)
            except Exception:
                result = None
        if not result:
            with self._lock:
                result = self._seeded.get(alias)
        if not result:
            return None
        safe = {key: value for key, value in dict(result).items() if key != "raw"}
        safe["symbol"] = alias
        return safe

    def public_state(self) -> dict[str, Any]:
        return {
            "stream": self.status(),
            "symbols": {
                symbol: self.snapshot(symbol)
                for symbol in self.symbols
            },
            "live_trading_enabled": False,
        }


MARKET_RUNTIME = MarketRuntime()
