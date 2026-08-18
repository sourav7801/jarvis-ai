"""Read-only FYERS data WebSocket for JARVIS live snapshots."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable, Iterable, Optional

from agents.fyers_auth_manager import websocket_access_token
from agents.fyers_data_adapter import normalize_symbol


SocketFactory = Callable[..., Any]


def _official_socket_factory() -> SocketFactory:
    try:
        from fyers_apiv3.FyersWebsocket import data_ws
    except ImportError as exc:
        raise RuntimeError(
            "FYERS SDK is not installed. Run: python -m pip install fyers-apiv3"
        ) from exc
    return data_ws.FyersDataSocket


class FyersLiveStream:
    """Owns a market-data socket only; order sockets are intentionally absent."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._socket: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._symbols: list[str] = []
        self._latest: dict[str, dict[str, Any]] = {}
        self._running = False
        self._connected = False
        self._last_error = ""

    def _on_message(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        symbol = str(message.get("symbol", "")).strip().upper()
        if not symbol:
            return
        normalized = {
            "success": True,
            "source": "FYERS",
            "provider_symbol": symbol,
            "ltp": message.get("ltp"),
            "open": message.get("open_price"),
            "high": message.get("high_price"),
            "low": message.get("low_price"),
            "previous_close": message.get("prev_close_price"),
            "volume": message.get("vol_traded_today"),
            "bid": message.get("bid_price"),
            "ask": message.get("ask_price"),
            "change": message.get("ch"),
            "change_percent": message.get("chp"),
            "exchange_timestamp": message.get(
                "exch_feed_time", message.get("last_traded_time")
            ),
            "received_at": datetime.now(timezone.utc).isoformat(),
            "raw": dict(message),
        }
        with self._lock:
            self._latest[symbol] = normalized

    def _on_error(self, error: Any) -> None:
        with self._lock:
            self._last_error = str(error)

    def _on_close(self, _message: Any = None) -> None:
        with self._lock:
            self._connected = False

    def _on_connect(self) -> None:
        with self._lock:
            self._connected = True
            socket = self._socket
            symbols = list(self._symbols)
        if socket is not None:
            socket.subscribe(symbols=symbols, data_type="SymbolUpdate")

    def start(
        self,
        symbols: Iterable[str] = ("NIFTY", "BANKNIFTY", "SENSEX"),
        *,
        lite_mode: bool = False,
        socket_factory: Optional[SocketFactory] = None,
    ) -> dict[str, Any]:
        provider_symbols = list(dict.fromkeys(normalize_symbol(item) for item in symbols))
        if not provider_symbols:
            raise ValueError("At least one FYERS symbol is required.")
        with self._lock:
            if self._running:
                return self.status()

            factory = socket_factory or _official_socket_factory()
            self._symbols = provider_symbols
            self._last_error = ""
            self._stop_event.clear()
            self._socket = factory(
                access_token=websocket_access_token(),
                log_path="",
                litemode=bool(lite_mode),
                write_to_file=False,
                # The SDK's internal reconnect path can orphan non-daemon
                # message workers when a session is rejected. JARVIS owns the
                # lifecycle and fails closed; a fresh authenticated start is
                # safer than an opaque SDK reconnect loop.
                reconnect=False,
                on_connect=self._on_connect,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message,
            )
            # FYERS SDK workers otherwise default to non-daemon threads and
            # can keep the workstation process alive after Ctrl+C.  This flag
            # is read by the SDK before it creates its WebSocket worker; all
            # child message/ping threads then inherit the daemon lifecycle.
            if hasattr(self._socket, "background_flag"):
                self._socket.background_flag = True
            self._running = True
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-fyers-data-socket",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def _run(self) -> None:
        try:
            with self._lock:
                socket = self._socket
            socket.connect()
            # FYERS connect() launches its own WebSocket worker and returns
            # after a short handshake.  Keep our lifecycle thread alive so the
            # workstation remains the explicit owner until stop() is called.
            while not self._stop_event.wait(0.5):
                connected = getattr(socket, "is_connected", None)
                if callable(connected):
                    with self._lock:
                        self._connected = bool(connected())
        except Exception as exc:
            self._on_error(exc)
        finally:
            with self._lock:
                self._connected = False
                self._running = False

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            socket = self._socket
            symbols = list(self._symbols)
            thread = self._thread
        if socket is not None:
            def close_socket() -> None:
                try:
                    socket.unsubscribe(symbols=symbols, data_type="SymbolUpdate")
                except Exception:
                    pass
                try:
                    socket.close_connection()
                except Exception:
                    pass

            # Some SDK versions wait indefinitely while joining their own
            # network worker. Never let a broker-data shutdown block JARVIS.
            closer = threading.Thread(
                target=close_socket,
                name="jarvis-fyers-socket-close",
                daemon=True,
            )
            closer.start()
            closer.join(timeout=3)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3)
        with self._lock:
            self._running = False
            self._connected = False
            self._socket = None
            self._thread = None

    def snapshot(self, symbol: str) -> Optional[dict[str, Any]]:
        try:
            provider_symbol = normalize_symbol(symbol)
        except ValueError:
            provider_symbol = str(symbol or "").strip().upper()
        with self._lock:
            value = self._latest.get(provider_symbol)
            return dict(value) if value else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "provider": "FYERS",
                "running": self._running,
                "connected": self._connected,
                "symbols": list(self._symbols),
                "snapshots": len(self._latest),
                "error": self._last_error or None,
                "data_only": True,
            }


fyers_live_stream = FyersLiveStream()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Start the JARVIS FYERS data stream")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["NIFTY", "BANKNIFTY", "SENSEX"],
    )
    parser.add_argument("--lite", action="store_true", help="Receive LTP-only updates")
    args = parser.parse_args(argv)
    try:
        fyers_live_stream.start(args.symbols, lite_mode=args.lite)
        print("FYERS data stream started. Press Ctrl+C to stop.")
        while fyers_live_stream.status()["running"]:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"FYERS stream error: {exc}")
        return 1
    finally:
        fyers_live_stream.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
