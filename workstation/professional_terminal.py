"""A single local terminal surface over the existing Quant engine and ledger."""
from __future__ import annotations

from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
from zoneinfo import ZoneInfo

from workstation import workspace_accounts as accounts
from workstation.terminal_data import BoundedPool, MARKET_CACHE, validate_candles, quote_certificate
from omni.loopback_http import ExclusiveThreadingHTTPServer

STATIC = Path(__file__).with_name("professional_terminal_static")


class TerminalHTTPServer(ExclusiveThreadingHTTPServer):
    """Bound connection workers; analysis itself runs in separate small pools."""
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        self._requests = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._requests.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nRetry-After: 2\r\nContent-Length: 0\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        request.settimeout(10)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._requests.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._requests.release()


def engines_for(controller, name):
    engine = controller.engines[name]
    return list(engine.engines.values()) if hasattr(engine, "engines") else [engine]


class TerminalRuntime:
    def __init__(self, desk, controller, *, mark_loader=None):
        self.desk, self.controller = desk, controller
        # The configured universe is authoritative. Broad discovery remains
        # available on demand, without silently adding instruments or workers.
        controller._owns_runtime_router = False
        controller.professional_sessions = True
        if mark_loader is None:
            from workstation.paper_trading_desk import live_mark_snapshot
            mark_loader = live_mark_snapshot
        self.mark_loader = mark_loader
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._controls = ThreadPoolExecutor(3, thread_name_prefix="JarvisSession")
        self._data = BoundedPool(2, 8)
        self._research = BoundedPool(2, 6)
        self._desired = {name: False for name in accounts.WORKSPACES}
        self._control_jobs = {}
        self._jobs = OrderedDict()
        self._marks = {}
        self._mark_jobs = {}
        self._control_errors = {}
        self._reconciled_at = 0.
        self._last_monitor = None
        self._error = None
        self._monitor_ms = 0.
        self._alert_cursor = 0
        accounts.initialize(desk)
        accounts.reset_sessions(desk)
        self.reconcile(integrity=True)
        for name in accounts.WORKSPACES:
            state = accounts.session(desk, name)
            self.controller.allocations[name] = state["allocation"]
            for engine in engines_for(controller, name):
                engine.manage_marks = False
                engine.scan_interval_seconds = max(engine.scan_interval_seconds, 30 if name == "INTRADAY" else 120 if name == "SWING" else 600)
                engine.universe = tuple(state["settings"]["symbols"])

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._monitor_loop, name="JarvisPositionMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        for name in accounts.WORKSPACES:
            self.control(name, "pause")
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._controls.shutdown(wait=False, cancel_futures=True)
        self._data._pool.shutdown(wait=False, cancel_futures=True)
        self._research._pool.shutdown(wait=False, cancel_futures=True)

    def control(self, name, action):
        if name not in accounts.WORKSPACES or action not in {"start", "pause"}:
            raise ValueError("Choose a workspace and start or pause")
        with self._lock:
            self._desired[name] = action == "start"
            if action == "pause":
                # Invalidate in-flight decisions before signalling workers.
                accounts.set_session(self.desk, name, False)
                for engine in engines_for(self.controller, name):
                    engine._stop.set()
                return {"success": True, "state": "PAUSED", "positions_remain_monitored": True}
            if not self.reconcile()["success"]:
                self._desired[name] = False
                return {"success": False, "state": "PROBLEM", "reason": "LEDGER_RECONCILIATION_REQUIRED", "message": "Resolve the records listed in Diagnostics before starting a paper session."}
            self._control_errors.pop(name, None)
            future = self._control_jobs.get(name)
            if future and not future.done():
                return {"success": True, "state": "STARTING"}
            if accounts.session(self.desk, name)["state"] == "RUNNING":
                return {"success": True, "state": "RUNNING"}
            self._control_jobs[name] = self._controls.submit(self._start_workspace, name)
            return {"success": True, "state": "STARTING"}

    def _start_workspace(self, name):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            with self._lock:
                if not self._desired[name] or self._stop.is_set():
                    return
            workers = engines_for(self.controller, name)
            settling = any(e._stop.is_set() and any(t and t.is_alive() for t in (e._scan_thread, e._trigger_thread)) for e in workers)
            if not settling:
                break
            self._stop.wait(.1)
        else:
            self._control_errors[name] = "Previous scan has not stopped; entries remain paused."
            self._desired[name] = False
            return
        with self._lock:
            if not self._desired[name]:
                return
            state = accounts.session(self.desk, name)
            for engine in workers:
                engine.universe = tuple(state["settings"]["symbols"])
            accounts.set_session(self.desk, name, True)
            try:
                self.controller.start_bucket(name, scan_now=False)
            except Exception as exc:
                accounts.set_session(self.desk, name, False)
                self._control_errors[name] = "Session start failed: " + type(exc).__name__
                self._desired[name] = False

    def reconcile(self, *, integrity=False):
        from workstation.terminal_ledger_guard import legacy_exposure
        with self.desk._lock, self.desk._connection() as conn:
            result = accounts.reconcile(self.desk, conn, integrity=integrity)
        result["legacy_exposure"] = legacy_exposure(self.desk)
        if result["legacy_exposure"]:
            result["success"] = False
            result["issues"].append("LEGACY_EXPOSURE_REQUIRES_RECONCILIATION")
        self._reconciliation = result
        self._reconciled_at = time.monotonic()
        return result

    def monitor_once(self):
        started = time.perf_counter()
        if started - self._reconciled_at > 30:
            self.reconcile()
        # Roll daily equity baselines before fetching new quotes, including
        # the first mark after an offline gap or overnight restart.
        with self.desk._lock, self.desk._connection() as conn:
            accounts.account_snapshot(self.desk, conn)
        snapshot = self.desk.snapshot()
        positions = snapshot.get("positions") or []
        symbols = list(dict.fromkeys(p["symbol"] for p in positions))
        with self.desk._lock, self.desk._connection() as conn:
            alert_symbols = list(dict.fromkeys(r["symbol"] for r in conn.execute("SELECT symbol,body_json FROM terminal_notes WHERE kind='alert'") if not json.loads(r["body_json"]).get("triggered_at")))
        # Position marks have priority; rotate at most two additional alert
        # instruments per cycle so research cannot exhaust the monitor queue.
        if alert_symbols:
            for i in range(min(2, len(alert_symbols))):
                symbol = alert_symbols[(self._alert_cursor + i) % len(alert_symbols)]
                if symbol not in symbols:
                    symbols.append(symbol)
            self._alert_cursor = (self._alert_cursor + 2) % len(alert_symbols)
        marks, certificates = {}, {}
        pending = []
        for symbol, future in list(self._mark_jobs.items()):
            if symbol not in symbols and (future.done() or future.cancel()):
                self._mark_jobs.pop(symbol, None)
        for symbol in symbols:
            try:
                future = self._mark_jobs.get(symbol)
                if future is None:
                    future = self._mark_jobs[symbol] = self._data.submit(self.mark_loader, symbol)
                pending.append((symbol, future))
            except RuntimeError:
                certificates[symbol] = {"reason": "MARK_QUEUE_FULL", "eligible_for_exit": False}
        deadline = time.monotonic() + 2
        for symbol, future in pending:
            try:
                certificate = dict(future.result(timeout=max(0., deadline-time.monotonic())))
                if certificate.get("eligible_for_exit"):
                    certificate = quote_certificate(symbol, certificate)
            except Exception as exc:
                certificate = {"reason": "MARK_UNAVAILABLE:" + type(exc).__name__, "eligible_for_exit": False}
            if future.done():
                self._mark_jobs.pop(symbol, None)
            certificates[symbol] = certificate
            if certificate.get("eligible_for_exit") and certificate.get("mark"):
                marks[symbol] = certificate["mark"]
        # Existing policies, partials, stops and target exits share this ledger.
        exits = self.desk.manage_positions(marks)
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        for p in positions:
            if accounts.workspace(p.get("portfolio_bucket")) != "INTRADAY" or p["symbol"] not in marks:
                continue
            certificate = certificates[p["symbol"]]
            venue = (certificate.get("session") or {}).get("venue")
            # Cash/FO day positions exit at 15:10 IST, before closing auctions.
            # On an outage they stay
            # unresolved until a valid tradable quote returns, including next day.
            overdue = str(p.get("opened_at") or "")[:10] < now.date().isoformat()
            if venue in {"NSE", "BSE"} and (overdue or (now.hour, now.minute) >= (15, 10)):
                exits.append(self.desk.close_position(position_id=p["id"], exit_price=marks[p["symbol"]], reason="INTRADAY_SESSION_EXIT"))
        with self._lock:
            self._marks = certificates
            self._last_monitor = datetime.now(timezone.utc).isoformat()
            self._monitor_ms = (time.perf_counter() - started) * 1000
        self._evaluate_alerts(marks)
        return {"marks": marks, "certificates": certificates, "exits": exits}

    def _evaluate_alerts(self, marks):
        with self.desk._lock, self.desk._connection() as conn:
            for row in conn.execute("SELECT * FROM terminal_notes WHERE kind='alert'").fetchall():
                body = json.loads(row["body_json"])
                price = marks.get(row["symbol"])
                if body.get("triggered_at") or price is None:
                    continue
                crossed = price >= body["level"] if body["condition"] == "above" else price <= body["level"]
                if crossed:
                    body["triggered_at"] = datetime.now(timezone.utc).isoformat()
                    body["trigger_price"] = price
                    conn.execute("UPDATE terminal_notes SET body_json=? WHERE id=?", (json.dumps(body), row["id"]))

    def _monitor_loop(self):
        while not self._stop.is_set():
            try:
                self.monitor_once()
                self._error = None
            except Exception as exc:
                self._error = "Position monitor: " + type(exc).__name__
            self._stop.wait(1.)

    def _engine_state(self, name):
        rows, rejections, cycles, active = [], Counter(), 0, False
        for engine in engines_for(self.controller, name):
            with engine._lock:
                rows.extend({**r, "profile": engine.profile} for r in engine._last_rows_summary)
                rejections.update(engine._last_rejection_counts)
                cycles += engine._scan_cycles
                active |= bool(engine._scan_guard.locked())
        return {"rows": rows[-100:], "rejections": dict(rejections), "cycles": cycles, "scanning": active}

    def snapshot(self, name="INTRADAY"):
        from workstation.quant_terminal_v2 import LIVE_BRIDGE_STARTUP
        if name not in accounts.WORKSPACES:
            raise ValueError("Unknown workspace")
        with self.desk._lock, self.desk._connection() as conn:
            all_accounts = accounts.account_snapshot(self.desk, conn)
            a = all_accounts[name]
            history = []
            for row in conn.execute("SELECT * FROM paper_positions WHERE status='CLOSED' AND CASE WHEN json_extract(metadata_json,'$.portfolio_bucket') IN ('SWING','INVESTMENT') THEN json_extract(metadata_json,'$.portfolio_bucket') ELSE 'INTRADAY' END = ? ORDER BY id DESC LIMIT 100", (name,)):
                meta = self.desk._metadata(row)
                if accounts.workspace(meta.get("portfolio_bucket")) == name:
                    history.append({**dict(row), "metadata": meta})
                    if len(history) >= 100:
                        break
            orders = [{**dict(r), "payload": json.loads(r["payload_json"])} for r in conn.execute("SELECT * FROM terminal_orders WHERE workspace=? ORDER BY id DESC LIMIT 100", (name,))]
            notes = [{**dict(r), "body": json.loads(r["body_json"])} for r in conn.execute("SELECT * FROM terminal_notes WHERE workspace=? ORDER BY id DESC LIMIT 100", (name,))]
        state = self._engine_state(name)
        with self._lock:
            marks = dict(self._marks)
            error = self._control_errors.get(name) or self._error
            if not self._reconciliation["success"]:
                error = "Ledger reconciliation required; see Diagnostics. Existing valid positions remain monitored."
            starting = self._desired[name] and a["session"] != "RUNNING"
        blocked_marks = [p["symbol"] for p in a["positions"] if not marks.get(p["symbol"], {}).get("eligible_for_exit")]
        data_failures = [reason for reason in state["rejections"] if any(key in reason for key in ("STALE", "DATA_UNAVAILABLE", "NO_DATA", "429", "RATE_LIMIT", "MARK_UNAVAILABLE", "TIMESTAMP", "MISMATCH", "UNVERIFIED"))]
        status = "STARTING" if starting else "DATA_PROBLEM" if blocked_marks or (a["session"] == "RUNNING" and data_failures) else "MANAGING_POSITION" if a["positions"] else "SCANNING" if a["session"] == "RUNNING" and state["scanning"] else "WAITING_FOR_TRIGGER" if a["session"] == "RUNNING" else "PAUSED"
        if error:
            status = "PROBLEM"
        wins = sum(float(r["realized_pnl"]) > 0 for r in history)
        return {"success": True, "service": "JARVIS_PROFESSIONAL_PAPER_TERMINAL", "version": "terminal-1.0",
                "workspace": name, "account": a, "accounts": {k: {x: v for x, v in a.items() if x not in {"positions", "settings"}} for k, a in all_accounts.items()},
                "state": status, "entry_session": a["session"], "status_reason": error or ("Fresh quotes unavailable for: " + ", ".join(blocked_marks) if blocked_marks else ", ".join(data_failures) if data_failures and a["session"] == "RUNNING" else "Waiting for verified strategy triggers" if a["session"] == "RUNNING" else "Entry scanning is paused; existing positions remain monitored"),
                "scan": state, "history": history, "orders": orders, "notes": notes,
                "performance": {"realized_pnl": a["realized_pnl"], "unrealized_pnl": a["unrealized_pnl"], "daily_pnl": a["daily_pnl"], "displayed_closed_trades": len(history), "wins": wins},
                "marks": marks, "monitor": {"last_cycle": self._last_monitor, "elapsed_ms": self._monitor_ms, "error": error},
                "cache": MARKET_CACHE.status(), "data_bridge": dict(LIVE_BRIDGE_STARTUP), "reconciliation": self._reconciliation, "csrf_token": self.token,
                "generated_at": datetime.now(timezone.utc).isoformat(), "paper_only": True, "live_execution": False}

    def job(self, key, loader, ttl=10):
        with self._lock:
            item = self._jobs.get(key)
            if item and not item[1].done():
                return {"success": True, "pending": True}
            if item and item[0] is None:
                item = self._jobs[key] = (time.monotonic(), item[1])
            if item and time.monotonic() - item[0] < ttl:
                try:
                    return {"success": True, "pending": False, "result": item[1].result()}
                except Exception as exc:
                    return {"success": False, "pending": False, "message": type(exc).__name__ + ": " + str(exc)[:200]}
            try:
                future = self._research.submit(loader)
            except RuntimeError:
                return {"success": False, "pending": False, "message": "Analysis is busy; retry shortly"}
            self._jobs[key] = (None, future)
            while len(self._jobs) > 64:
                self._jobs.popitem(last=False)
            return {"success": True, "pending": True}

    def chart(self, symbol, timeframe):
        def load():
            from workstation import quant_terminal_v2 as quant
            if ":" in symbol and symbol.endswith(("CE", "PE")):
                from workstation.option_chart_data import option_candles
                payload = option_candles("FYERS", symbol, timeframe, 400)
            else:
                payload = quant.candles_payload(symbol, timeframe, 400)
            payload = dict(payload)
            error = validate_candles(payload.get("candles") or [], 300)
            if error:
                return {"success": False, "message": error, "candles": []}
            payload["quote"] = self.mark_loader(symbol)
            return payload
        return self.job(("chart", symbol, timeframe), load, ttl=10)

    def quote(self, symbol):
        return self.job(("quote", symbol), lambda: self.mark_loader(symbol), ttl=1)

    def module(self, name, symbol, module):
        from workstation.quant_intelligence_modules import SUPPORTED_MODULES, intelligence_module_payload
        if module not in SUPPORTED_MODULES or name not in accounts.WORKSPACES:
            raise ValueError("Unknown analysis module")
        if module in {"portfolio-risk", "trade-journal"}:
            state = self.snapshot(name)
            payload = {"workspace": name, "paper_only": True, "live_execution": False}
            payload.update({"account": state["account"], "rejections": state["scan"]["rejections"]} if module == "portfolio-risk" else {"trades": state["history"], "performance": state["performance"]})
            return {"success": True, "pending": False, "result": payload}
        return self.job((name, symbol, module), lambda: intelligence_module_payload(module, symbol, profile=name.lower()), ttl=30)

    def save_note(self, name, body):
        if name not in accounts.WORKSPACES or body.get("kind") not in {"thesis", "alert"}:
            raise ValueError("Invalid note")
        symbol = str(body.get("symbol") or "").strip().upper()
        detail = body.get("body")
        if not symbol or not isinstance(detail, dict) or len(json.dumps(detail)) > 16000:
            raise ValueError("Provide an instrument and a note")
        if body["kind"] == "alert":
            if detail.get("condition") not in {"above", "below"} or accounts.number(detail.get("level")) <= 0:
                raise ValueError("An alert needs an above/below condition and positive level")
            detail["level"] = float(detail["level"])
        with self.desk._lock, self.desk._connection() as conn:
            if body.get("id"):
                updated = conn.execute("UPDATE terminal_notes SET symbol=?,body_json=?,updated_at=? WHERE id=? AND workspace=? AND kind=?", (symbol, json.dumps(detail), datetime.now(timezone.utc).isoformat(), int(body["id"]), name, body["kind"]))
                if updated.rowcount != 1:
                    raise ValueError("Note does not belong to this workspace")
            else:
                conn.execute("INSERT INTO terminal_notes(workspace,kind,symbol,body_json,updated_at) VALUES(?,?,?,?,?)", (name, body["kind"], symbol, json.dumps(detail), datetime.now(timezone.utc).isoformat()))
        return {"success": True}


def build_handler(base, runtime):
    class TerminalHandler(base):
        def _local(self):
            host = self.headers.get("Host", "").split(":")[0]
            return host in {"127.0.0.1", "localhost"}

        def do_GET(self):
            if not self._local():
                return self.send_json({"success": False, "message": "Local terminal only"}, 403)
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            name = str(params.get("workspace", ["INTRADAY"])[0]).upper()
            symbol = str(params.get("symbol", ["NIFTY"])[0])
            try:
                if parsed.path == "/":
                    return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
                if parsed.path in {"/terminal.js", "/terminal.css"}:
                    return self.send_file(STATIC / parsed.path[1:], "application/javascript; charset=utf-8" if parsed.path.endswith(".js") else "text/css; charset=utf-8")
                if parsed.path == "/legacy":
                    from workstation.quant_terminal_v2 import STATIC as legacy
                    return self.send_file(legacy / "index.html", "text/html; charset=utf-8")
                if parsed.path == "/api/terminal/state":
                    return self.send_json(runtime.snapshot(name))
                if parsed.path == "/api/terminal/chart":
                    return self.send_json(runtime.chart(symbol, str(params.get("timeframe", ["5m"])[0])))
                if parsed.path == "/api/terminal/quote":
                    return self.send_json(runtime.quote(symbol))
                if parsed.path == "/api/terminal/module":
                    return self.send_json(runtime.module(name, symbol, str(params.get("module", ["patterns"])[0])))
                if parsed.path == "/api/terminal/health":
                    return self.send_json({"success": True, "service": "JARVIS_PROFESSIONAL_PAPER_TERMINAL", "paper_only": True, "live_execution": False})
            except (ValueError, KeyError) as exc:
                return self.send_json({"success": False, "message": str(exc)}, 400)
            return super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if not parsed.path.startswith("/api/terminal/"):
                return super().do_POST()
            if not self._local() or not secrets.compare_digest(self.headers.get("X-Jarvis-Token", ""), runtime.token):
                return self.send_json({"success": False, "message": "Refresh this local terminal before changing the session"}, 403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32768:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(length))
                name = str(body.get("workspace") or "INTRADAY").upper()
                if parsed.path == "/api/terminal/session":
                    return self.send_json(runtime.control(name, body.get("action")))
                if parsed.path == "/api/terminal/settings":
                    result = accounts.configure(runtime.desk, name, body.get("settings"), body.get("allocations"))
                    for key in accounts.WORKSPACES:
                        runtime.controller.allocations[key] = accounts.session(runtime.desk, key)["allocation"]
                    return self.send_json({"success": True, "settings": result})
                if parsed.path == "/api/terminal/note":
                    return self.send_json(runtime.save_note(name, body))
                raise ValueError("Unknown terminal action")
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_json({"success": False, "message": str(exc)}, 400)
    return TerminalHandler
