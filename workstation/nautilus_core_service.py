from __future__ import annotations

import importlib.util
import json
import platform
import threading
import time
import traceback
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PORT = 8792
MAX_EVENTS = 5000
LOG_PATH = Path(r"C:\Jarvis\data\logs\nautilus_core_v52.log")


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
_STATUS_LOCK = threading.RLock()
_STARTUP_STATUS: dict[str, Any] = {
    "success": False,
    "service": "JARVIS_NAUTILUS_QUANT_CORE",
    "host": HOST,
    "port": PORT,
    "phase": "STARTING",
    "engine_ready": False,
    "paper_only": True,
    "live_execution": False,
    "error": None,
}


def _log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _backtest_engine_types():
    """Resolve NautilusTrader's low-level BacktestEngine API defensively.

    NautilusTrader has moved/re-exported BacktestEngineConfig across release
    lines.  The pinned Windows wheel is probed against known stable locations
    instead of assuming one convenience re-export.
    """

    from nautilus_trader.backtest.engine import BacktestEngine

    config_error: Exception | None = None
    for module_name in (
        "nautilus_trader.backtest.engine",
        "nautilus_trader.backtest.config",
        "nautilus_trader.config",
    ):
        try:
            module = __import__(module_name, fromlist=["BacktestEngineConfig"])
            config_type = getattr(module, "BacktestEngineConfig")
            return BacktestEngine, config_type, module_name
        except Exception as exc:
            config_error = exc

    raise ImportError(
        "BacktestEngineConfig was not available from known NautilusTrader API paths"
    ) from config_error


def _probe_nautilus() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        import nautilus_trader

        version = str(getattr(nautilus_trader, "__version__", "unknown"))
        BacktestEngine, BacktestEngineConfig, config_module = _backtest_engine_types()
        engine = BacktestEngine(config=BacktestEngineConfig())
        try:
            pass
        finally:
            engine.dispose()

        engine_ready = True
        error = None
        trace = None
        engine_module = "nautilus_trader.backtest.engine"
    except Exception as exc:
        version = None
        engine_ready = False
        error = f"{type(exc).__name__}: {exc}"
        trace = traceback.format_exc(limit=20)
        config_module = None
        engine_module = None

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
        "phase": "READY" if engine_ready else "DEGRADED",
        "nautilus_version": version,
        "python": platform.python_version(),
        "engine_ready": engine_ready,
        "engine_module": engine_module,
        "config_module": config_module,
        "probe_seconds": time.perf_counter() - started,
        "adapters": adapters,
        "components": {
            "message_bus": engine_ready,
            "data_engine": engine_ready,
            "risk_engine": engine_ready,
            "execution_engine": engine_ready,
            "portfolio": engine_ready,
            "cache": engine_ready,
            "backtest_engine": engine_ready,
            "sandbox_execution": adapters["sandbox"],
        },
        "execution_mode": "PAPER_SANDBOX_ONLY",
        "paper_only": True,
        "live_execution": False,
        "error": error,
        "traceback": trace,
        "log_path": str(LOG_PATH),
    }


def _set_status(payload: dict[str, Any]) -> None:
    global _STARTUP_STATUS
    with _STATUS_LOCK:
        _STARTUP_STATUS = dict(payload)


def nautilus_status() -> dict[str, Any]:
    with _STATUS_LOCK:
        return dict(_STARTUP_STATUS)


def _probe_worker() -> None:
    _set_status(
        {
            **nautilus_status(),
            "phase": "PROBING",
            "engine_ready": False,
            "success": False,
        }
    )
    _log("Nautilus capability probe started")
    result = _probe_nautilus()
    _set_status(result)
    if result.get("engine_ready"):
        _log(
            "Nautilus capability probe READY "
            f"version={result.get('nautilus_version')} "
            f"config={result.get('config_module')} "
            f"seconds={result.get('probe_seconds'):.3f}"
        )
    else:
        _log(f"Nautilus capability probe DEGRADED: {result.get('error')}")
        if result.get("traceback"):
            _log(str(result.get("traceback")))


def _json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(min(length, 1_000_000))
    payload = json.loads(raw.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisNautilusCore/5.2"

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
        if path in {"/", "/health"}:
            status = nautilus_status()
            self._send(
                {
                    "success": True,
                    "service": "JARVIS_NAUTILUS_QUANT_CORE",
                    "phase": status.get("phase"),
                    "engine_ready": bool(status.get("engine_ready")),
                    "paper_only": True,
                    "live_execution": False,
                }
            )
            return
        if path == "/status":
            status = nautilus_status()
            self._send(status, 200 if status.get("engine_ready") else 503)
            return
        if path == "/metrics":
            payload = STATE.metrics()
            payload["core"] = nautilus_status()
            self._send(payload)
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
            self._send(status, 200 if status.get("engine_ready") else 503)
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
        if path in {"/backtest-selftest", "/probe"}:
            result = _probe_nautilus()
            _set_status(result)
            self._send(result, 200 if result.get("engine_ready") else 503)
            return
        self._send({"success": False, "message": "Not found"}, 404)


def main() -> None:
    _log("Starting JARVIS Nautilus Quant Core V5.2")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    worker = threading.Thread(target=_probe_worker, name="nautilus-probe", daemon=True)
    worker.start()

    print("=" * 76, flush=True)
    print("JARVIS NAUTILUS QUANT CORE V5.2", flush=True)
    print("=" * 76, flush=True)
    print(f"Core service: http://{HOST}:{PORT}", flush=True)
    print(f"Diagnostics: {LOG_PATH}", flush=True)
    print("Execution: PAPER / SANDBOX ONLY", flush=True)
    print("Live broker execution: LOCKED", flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
