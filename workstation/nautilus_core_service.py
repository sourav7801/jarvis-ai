from __future__ import annotations

import json
import platform
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from typing import Any

HOST = "127.0.0.1"
PORT = 8792
MAX_EVENTS = 5000


class NautilusCoreState:
    def __init__(self) -> None:
        self.started_at = time.time()
        self._lock = threading.RLock()
        self._sequence = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._latencies_ms: deque[float] = deque(maxlen=2000)

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter_ns()
        with self._lock:
            self._sequence += 1
            event = {
                "sequence": self._sequence,
                "received_ns": time.time_ns(),
                "type": str(payload.get("type") or "MARKET_EVENT"),
                "symbol": str(payload.get("symbol") or "").upper(),
                "provider": str(payload.get("provider") or "JARVIS"),
                "payload": payload,
            }
            self._events.append(event)
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        self._latencies_ms.append(latency_ms)
        return {
            "success": True,
            "sequence": event["sequence"],
            "ingest_latency_ms": latency_ms,
            "paper_only": True,
            "live_execution": False,
        }

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            count = self._sequence
            events = len(self._events)
            latencies = list(self._latencies_ms)
        uptime = max(time.time() - self.started_at, 1e-9)
        return {
            "success": True,
            "uptime_seconds": uptime,
            "events_seen": count,
            "events_buffered": events,
            "events_per_second_since_start": count / uptime,
            "avg_local_ingest_latency_ms": (
                sum(latencies) / len(latencies) if latencies else 0.0
            ),
            "p99_local_ingest_latency_ms": (
                sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)]
                if latencies
                else 0.0
            ),
            "paper_only": True,
            "live_execution": False,
        }


STATE = NautilusCoreState()


def _module_available(name: str) -> bool:
    try:
        import_module(name)
        return True
    except Exception:
        return False


def nautilus_status() -> dict[str, Any]:
    try:
        import nautilus_trader
        from nautilus_trader.backtest import BacktestEngine
        from nautilus_trader.config import BacktestEngineConfig

        version = str(getattr(nautilus_trader, "__version__", "unknown"))
        engine = BacktestEngine(BacktestEngineConfig())
        engine.dispose()
        engine_ready = True
        error = None
    except Exception as exc:
        version = None
        engine_ready = False
        error = f"{type(exc).__name__}: {exc}"

    adapters = {
        "binance": _module_available("nautilus_trader.adapters.binance"),
        "deribit": _module_available("nautilus_trader.adapters.deribit"),
        "sandbox": _module_available("nautilus_trader.adapters.sandbox"),
    }

    return {
        "success": bool(engine_ready),
        "service": "JARVIS_NAUTILUS_QUANT_CORE",
        "host": HOST,
        "port": PORT,
        "nautilus_version": version,
        "python": platform.python_version(),
        "engine_ready": engine_ready,
        "adapters": adapters,
        "components": {
            "message_bus": True,
            "data_engine": True,
            "risk_engine": True,
            "execution_engine": True,
            "portfolio": True,
            "cache": True,
            "backtest_engine": True,
            "sandbox_execution": adapters["sandbox"],
        },
        "execution_mode": "PAPER_SANDBOX_ONLY",
        "live_execution": False,
        "error": error,
    }


def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(min(length, 1_000_000))
    payload = json.loads(raw.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisNautilusCore/5.0"

    def log_message(self, *_args: Any) -> None:
        return

    def _send(self, payload: dict[str, Any], code: int = 200) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/", "/health", "/status"}:
            self._send(nautilus_status())
            return
        if path == "/metrics":
            self._send(STATE.metrics())
            return
        if path == "/architecture":
            status = nautilus_status()
            status["target_architecture"] = {
                "jarvis_control_plane": "8797",
                "trading_terminal": "8787",
                "fyers_read_only_bridge": "8790",
                "nautilus_quant_core": "8792",
                "research_live_parity": True,
                "one_live_node_per_process": True,
            }
            self._send(status)
            return
        self._send({"success": False, "message": "Not found"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            payload = _json_body(self)
        except Exception as exc:
            self._send({"success": False, "message": str(exc)}, 400)
            return

        if path == "/event":
            self._send(STATE.ingest(payload))
            return
        if path == "/backtest-selftest":
            self._send(nautilus_status())
            return
        self._send({"success": False, "message": "Not found"}, 404)


def main() -> None:
    status = nautilus_status()
    if not status.get("engine_ready"):
        raise RuntimeError(f"Nautilus core unavailable: {status.get('error')}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 76)
    print("JARVIS NAUTILUS QUANT CORE V5")
    print("=" * 76)
    print(f"Core service: http://{HOST}:{PORT}")
    print(f"NautilusTrader: {status.get('nautilus_version')}")
    print("Execution: PAPER / SANDBOX ONLY")
    print("Live broker execution: LOCKED")
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
