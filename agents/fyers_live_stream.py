"""Read-only FYERS data WebSocket for JARVIS live snapshots.

The wrapper owns reconnects so the workstation has one observable lifecycle and
the FYERS SDK never runs a competing opaque reconnect loop. It is intentionally
DATA ONLY: no order socket or broker-order surface is exposed here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import random
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


def _iso_timestamp(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


class FyersLiveStream:
    """Owns a resilient market-data socket only; order sockets are absent."""

    STATES = {
        "DISCONNECTED",
        "CONNECTING",
        "CONNECTED",
        "RECONNECTING",
        "STALE",
        "FAILED",
    }

    def __init__(
        self,
        *,
        stale_after_seconds: float = 45.0,
        max_reconnect_attempts: int = 8,
        reconnect_base_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
        reconnect_jitter_seconds: float = 0.5,
        connect_grace_seconds: float = 8.0,
    ) -> None:
        self._lock = threading.RLock()
        self._socket: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._symbols: list[str] = []
        self._latest: dict[str, dict[str, Any]] = {}
        self._running = False
        self._connected = False
        self._state = "DISCONNECTED"
        self._last_error = ""
        self._last_message_at: Optional[float] = None
        self._last_connected_at: Optional[float] = None
        self._last_disconnected_at: Optional[float] = None
        self._next_retry_at: Optional[float] = None
        self._consecutive_failures = 0
        self._generation = 0
        self._transport_fault_generation: Optional[int] = None

        self._stale_after_seconds = max(1.0, float(stale_after_seconds))
        self._max_reconnect_attempts = max(1, int(max_reconnect_attempts))
        self._reconnect_base_seconds = max(0.1, float(reconnect_base_seconds))
        self._reconnect_max_seconds = max(
            self._reconnect_base_seconds, float(reconnect_max_seconds)
        )
        self._reconnect_jitter_seconds = max(0.0, float(reconnect_jitter_seconds))
        self._connect_grace_seconds = max(1.0, float(connect_grace_seconds))

        self._socket_factory: Optional[SocketFactory] = None
        self._lite_mode = False

    def _set_state(self, state: str) -> None:
        if state not in self.STATES:
            raise ValueError(f"Unsupported FYERS stream state: {state}")
        with self._lock:
            self._state = state

    def _on_message(self, message: Any, *, generation: Optional[int] = None) -> None:
        if not isinstance(message, dict):
            return
        symbol = str(message.get("symbol", "")).strip().upper()
        if not symbol:
            return
        now = time.time()
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
            "received_at": _iso_timestamp(now),
            "raw": dict(message),
        }
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self._latest[symbol] = normalized
            self._last_message_at = now
            if self._connected:
                self._state = "CONNECTED"

    def _on_error(self, error: Any, *, generation: Optional[int] = None) -> None:
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self._last_error = str(error)
            # FYERS can emit on_error("Connection to remote host was lost")
            # without a matching on_close callback. Treat any websocket error
            # as a transport fault so the owner loop cannot remain falsely
            # CONNECTED forever on a dead socket.
            current_generation = self._generation if generation is None else generation
            self._transport_fault_generation = current_generation
            self._connected = False
            self._last_disconnected_at = time.time()
            if self._running and not self._stop_event.is_set():
                self._state = "RECONNECTING"

    def _on_close(
        self,
        _message: Any = None,
        *,
        generation: Optional[int] = None,
    ) -> None:
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self._connected = False
            self._last_disconnected_at = time.time()
            if self._running and not self._stop_event.is_set():
                self._state = "RECONNECTING"
            elif self._state != "FAILED":
                self._state = "DISCONNECTED"

    def _on_connect(self, *, generation: Optional[int] = None) -> None:
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self._connected = True
            self._state = "CONNECTED"
            self._last_connected_at = time.time()
            self._consecutive_failures = 0
            self._next_retry_at = None
            self._last_error = ""
            socket = self._socket
            symbols = list(self._symbols)
        if socket is not None:
            socket.subscribe(symbols=symbols, data_type="SymbolUpdate")

    def _retry_delay(self, consecutive_failures: int) -> float:
        exponent = max(0, int(consecutive_failures) - 1)
        bounded = min(
            self._reconnect_max_seconds,
            self._reconnect_base_seconds * (2**exponent),
        )
        if self._reconnect_jitter_seconds <= 0:
            return bounded
        return min(
            self._reconnect_max_seconds + self._reconnect_jitter_seconds,
            bounded + random.uniform(0.0, self._reconnect_jitter_seconds),
        )

    def _make_socket(self, generation: int) -> Any:
        factory = self._socket_factory or _official_socket_factory()

        def on_connect() -> None:
            self._on_connect(generation=generation)

        def on_close(message: Any = None) -> None:
            self._on_close(message, generation=generation)

        def on_error(error: Any) -> None:
            self._on_error(error, generation=generation)

        def on_message(message: Any) -> None:
            self._on_message(message, generation=generation)

        socket = factory(
            access_token=websocket_access_token(),
            log_path="",
            litemode=bool(self._lite_mode),
            write_to_file=False,
            # JARVIS owns bounded reconnects. A second SDK reconnect loop
            # would create competing lifecycles and unobservable worker leaks.
            reconnect=False,
            on_connect=on_connect,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )
        if hasattr(socket, "background_flag"):
            socket.background_flag = True
        return socket

    @staticmethod
    def _close_socket_bounded(socket: Any, symbols: list[str]) -> None:
        if socket is None:
            return

        def close_socket() -> None:
            try:
                socket.unsubscribe(symbols=symbols, data_type="SymbolUpdate")
            except Exception:
                pass
            try:
                socket.close_connection()
            except Exception:
                pass

        closer = threading.Thread(
            target=close_socket,
            name="jarvis-fyers-socket-close",
            daemon=True,
        )
        closer.start()
        closer.join(timeout=3)

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

        # Resolve the official SDK before the worker starts so a missing
        # dependency fails immediately and visibly.
        factory = socket_factory or _official_socket_factory()

        with self._lock:
            if self._running:
                return self.status()

            self._symbols = provider_symbols
            self._last_error = ""
            self._last_message_at = None
            self._last_connected_at = None
            self._last_disconnected_at = None
            self._next_retry_at = None
            self._consecutive_failures = 0
            self._transport_fault_generation = None
            self._socket_factory = factory
            self._lite_mode = bool(lite_mode)
            self._stop_event.clear()
            self._running = True
            self._connected = False
            self._state = "CONNECTING"
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-fyers-data-socket",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    self._generation += 1
                    generation = self._generation
                    self._connected = False
                    self._transport_fault_generation = None
                    self._state = "RECONNECTING" if generation > 1 else "CONNECTING"
                    self._next_retry_at = None

                socket = None
                connected_this_generation = False
                try:
                    socket = self._make_socket(generation)
                    with self._lock:
                        if generation != self._generation:
                            break
                        self._socket = socket
                    socket.connect()

                    deadline = time.monotonic() + self._connect_grace_seconds
                    while not self._stop_event.wait(0.25):
                        with self._lock:
                            transport_fault = self._transport_fault_generation == generation
                        if transport_fault:
                            break
                        connected_probe = getattr(socket, "is_connected", None)
                        if callable(connected_probe):
                            try:
                                probe_value = bool(connected_probe())
                            except Exception as exc:
                                raise RuntimeError(
                                    f"FYERS connection probe failed: {exc}"
                                ) from exc
                            with self._lock:
                                if generation != self._generation:
                                    break
                                if probe_value and not self._connected:
                                    self._connected = True
                                    self._state = "CONNECTED"
                                    self._last_connected_at = time.time()
                                    self._consecutive_failures = 0
                                current_connected = self._connected
                        else:
                            with self._lock:
                                current_connected = self._connected

                        if current_connected:
                            connected_this_generation = True
                            deadline = float("inf")
                        elif connected_this_generation:
                            break
                        elif time.monotonic() >= deadline:
                            raise RuntimeError(
                                "FYERS data socket did not become connected within the grace period."
                            )

                    if self._stop_event.is_set():
                        break
                    if connected_this_generation:
                        self._on_close(generation=generation)
                except Exception as exc:
                    self._on_error(exc, generation=generation)
                finally:
                    with self._lock:
                        symbols = list(self._symbols)
                    self._close_socket_bounded(socket, symbols)
                    with self._lock:
                        if self._socket is socket:
                            self._socket = None
                        if generation == self._generation:
                            self._connected = False

                if self._stop_event.is_set():
                    break

                with self._lock:
                    if connected_this_generation:
                        # A successful session that later dropped starts a new
                        # reconnect window; only consecutive failed handshakes
                        # count against the retry budget.
                        self._consecutive_failures = 1
                    else:
                        self._consecutive_failures += 1
                    failures = self._consecutive_failures

                if failures >= self._max_reconnect_attempts:
                    with self._lock:
                        self._state = "FAILED"
                        self._running = False
                        self._next_retry_at = None
                    return

                delay = self._retry_delay(failures)
                with self._lock:
                    self._state = "RECONNECTING"
                    self._next_retry_at = time.time() + delay
                if self._stop_event.wait(delay):
                    break
        finally:
            with self._lock:
                self._connected = False
                self._socket = None
                self._next_retry_at = None
                if self._state != "FAILED":
                    self._state = "DISCONNECTED"
                self._running = False

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._generation += 1
            socket = self._socket
            symbols = list(self._symbols)
            thread = self._thread
        self._close_socket_bounded(socket, symbols)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=4)
        with self._lock:
            self._running = False
            self._connected = False
            self._state = "DISCONNECTED"
            self._socket = None
            self._thread = None
            self._next_retry_at = None
            self._transport_fault_generation = None
            self._last_disconnected_at = time.time()

    def subscribe(self, symbols: Iterable[str]) -> dict[str, Any]:
        provider_symbols = list(dict.fromkeys(normalize_symbol(item) for item in symbols))
        with self._lock:
            additions = [item for item in provider_symbols if item not in self._symbols]
            self._symbols.extend(additions)
            socket = self._socket
            connected = self._connected
        if additions and socket is not None and connected:
            socket.subscribe(symbols=additions, data_type="SymbolUpdate")
        return {**self.status(), "subscribed": additions}

    def snapshot(self, symbol: str) -> Optional[dict[str, Any]]:
        try:
            provider_symbol = normalize_symbol(symbol)
        except ValueError:
            provider_symbol = str(symbol or "").strip().upper()
        with self._lock:
            value = self._latest.get(provider_symbol)
            return dict(value) if value else None

    def status(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            state = self._state
            freshness_reference = self._last_message_at or self._last_connected_at
            age_seconds = (
                max(0.0, now - freshness_reference)
                if freshness_reference is not None
                else None
            )
            if (
                self._connected
                and freshness_reference is not None
                and age_seconds is not None
                and age_seconds > self._stale_after_seconds
            ):
                state = "STALE"
            elif self._connected:
                state = "CONNECTED"

            retry_in_seconds = (
                max(0.0, self._next_retry_at - now)
                if self._next_retry_at is not None
                else None
            )

            return {
                "provider": "FYERS",
                "transport": "DATA_WEBSOCKET",
                "state": state,
                "running": self._running,
                "connected": self._connected,
                "symbols": list(self._symbols),
                "snapshots": len(self._latest),
                "fresh": state == "CONNECTED",
                "stale_after_seconds": self._stale_after_seconds,
                "message_age_seconds": round(age_seconds, 3)
                if age_seconds is not None
                else None,
                "last_message_at": _iso_timestamp(self._last_message_at),
                "last_connected_at": _iso_timestamp(self._last_connected_at),
                "last_disconnected_at": _iso_timestamp(self._last_disconnected_at),
                "reconnect_attempt": self._consecutive_failures,
                "max_reconnect_attempts": self._max_reconnect_attempts,
                "next_retry_at": _iso_timestamp(self._next_retry_at),
                "transport_fault_generation": self._transport_fault_generation,
                "retry_in_seconds": round(retry_in_seconds, 3)
                if retry_in_seconds is not None
                else None,
                "error": self._last_error or None,
                "data_only": True,
                "read_only": True,
                "order_socket_enabled": False,
                "live_order_execution": False,
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
