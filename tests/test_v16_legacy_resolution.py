"""Real temporary ledgers; no market or broker execution in these tests."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import urllib.request
import urllib.error
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workstation import terminal_ledger_guard as guard, workspace_accounts as accounts
from workstation.paper_trading_desk import PaperTradingDesk
from workstation import v16_legacy_resolution as resolution


class LegacyResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "paper_portfolio.json"
        self.desk = PaperTradingDesk(self.root / "canonical.sqlite3")
        accounts.initialize(self.desk)
        self.paths = patch.multiple(guard, TERMINAL_DB=self.desk.db_path, LEGACY_ACCOUNT=self.path, LEGACY_SPREADS=self.root / "absent.sqlite3")
        self.paths.start(); self.addCleanup(self.paths.stop)
        self.record = dict(symbol="BTC", side="LONG", quantity=2., average_price=100., stop_loss=90., take_profit=130., opened_at="2026-08-17T23:34:17", current_price=105., realized_pnl=0., private_note="not-for-browser", metadata={"secret":"not-for-browser"})
        self.source = dict(version=2, positions=[self.record], account=dict(cash=800., realized_pnl=0., total_fees=0., starting_capital=1000.), trades=[])
        self.path.write_text(json.dumps(self.source), encoding="utf-8")
        now=datetime.now(timezone.utc).isoformat()
        self.quote=dict(success=True,symbol="BTC",provider="BINANCE_PUBLIC",ltp=110.,received_at=now,exchange_timestamp=now)
        self.spec=dict(symbol="BTC",provider_symbol="BTC",instrument_type="SPOT",asset_class="SPOT",contract_multiplier=1.,quantity_step=1.,tick_size=.01,verified=True,native_currency="INR",valuation_currency="INR")
        self.runtime=SimpleNamespace(desk=self.desk, mark_loader=lambda symbol: dict(self.quote))
        self.spec_patch=patch.object(resolution,"instrument_status",side_effect=lambda symbol:dict(status="VALID",spec=dict(self.spec),reason=None))
        self.spec_patch.start();self.addCleanup(self.spec_patch.stop)

    def body(self, action="MIGRATE", workspace="SWING"):
        row=resolution.legacy_resolution_details(self.runtime)["positions"][0]
        return dict(action=action,workspace=workspace,fingerprint=row["fingerprint"],revision=row["revision"])

    def run_action(self, body=None):
        return resolution.resolve_legacy_position(self.runtime,body or self.body())

    def rows(self):
        with self.desk._lock,self.desk._connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM paper_positions")]

    def test_diagnostics_sanitized_and_take_profit_preserved(self):
        before=self.path.read_bytes(); result=resolution.legacy_resolution_details(self.runtime)
        row=result["positions"][0]
        self.assertEqual(row["entry_price"],100.)
        self.assertEqual(row["target"],130.)
        self.assertNotIn("not-for-browser",json.dumps(result))
        self.assertEqual(before,self.path.read_bytes())

    def test_migration_preserves_economics_and_is_idempotent(self):
        body=self.body()
        with patch.object(self.desk,"open_position",side_effect=AssertionError("Migration is not an entry")):
            first=self.run_action(body); second=self.run_action(body)
        self.assertTrue(first["success"],first);self.assertTrue(second["idempotent"],second)
        row=self.rows()[0];self.assertEqual(len(self.rows()),1)
        for key,value in dict(entry=100.,quantity=2.,opened_at=self.record["opened_at"],side="LONG",stop=90.,target=130.).items():self.assertEqual(row[key],value)
        meta=json.loads(row["metadata_json"]);self.assertEqual(meta["portfolio_bucket"],"SWING")
        self.assertEqual(meta["legacy_fingerprint"],body["fingerprint"])
        self.assertEqual(meta["position_multiplier"],1.)
        self.assertEqual(guard.legacy_exposure(self.desk),[])
        data=json.loads(self.path.read_text());self.assertEqual(data["positions"],[]);self.assertEqual(len(data["resolved_positions"]),1)
        self.assertEqual(accounts.session(self.desk,"SWING")["state"],"PAUSED")
        with self.desk._lock,self.desk._connection() as conn:self.assertTrue(accounts.reconcile(self.desk,conn)["success"])

    def test_failure_before_commit_leaves_source_and_canonical_untouched(self):
        body=self.body();before=self.path.read_bytes()
        with patch.object(self.desk,"_event",side_effect=RuntimeError("transaction failed")):
            result=self.run_action(body)
        self.assertFalse(result["success"]);self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.rows(),[])

    def test_ack_failure_stays_blocked_and_retry_never_duplicates(self):
        body=self.body();before=self.path.read_bytes()
        with patch.object(resolution,"_write_source",side_effect=OSError("file locked")):
            result=self.run_action(body)
        self.assertFalse(result["success"]);self.assertEqual(result["reason"],"SOURCE_ACK_PENDING")
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(len(self.rows()),1)
        self.assertTrue(guard.legacy_exposure(self.desk))
        self.assertTrue(self.run_action(body)["success"]);self.assertEqual(len(self.rows()),1)

    def test_close_uses_verified_exit_and_updates_source_account(self):
        result=self.run_action(self.body("CLOSE"));self.assertTrue(result["success"],result)
        self.assertEqual(self.rows(),[])
        data=json.loads(self.path.read_text());self.assertEqual(data["positions"],[])
        audit=data["resolved_positions"][0]["resolution"]
        self.assertEqual(audit["close_price"],110.)
        self.assertEqual(audit["pnl"],20.)
        self.assertEqual(data["account"]["cash"],1020.)
        self.assertEqual(data["account"]["realized_pnl"],20.)
        self.assertEqual(guard.legacy_exposure(self.desk),[])

    def test_stale_identity_and_closed_market_cannot_fill(self):
        for change,reason in [({"exchange_timestamp":(datetime.now(timezone.utc)-timedelta(minutes=4)).isoformat()},"STALE_MARK"),({"symbol":"ETH"},"QUOTE_INSTRUMENT_MISMATCH")]:
            with self.subTest(reason=reason):
                previous=dict(self.quote);self.quote.update(change);before=self.path.read_bytes()
                self.assertEqual(self.run_action(self.body("CLOSE"))["reason"],reason)
                self.assertEqual(self.path.read_bytes(),before);self.quote=previous
        with patch.object(resolution,"verified_exit",return_value={"success":False,"reason":"MARKET_SESSION_CLOSED"}):
            self.assertEqual(self.run_action(self.body("CLOSE"))["reason"],"MARKET_SESSION_CLOSED")

    def test_expired_unresolved_and_unit_mismatch_fail_closed(self):
        for state in ("EXPIRED","UNRESOLVED","DELISTED"):
            with patch.object(resolution,"instrument_status",return_value={"status":state,"spec":{},"reason":state}):
                details=resolution.legacy_resolution_details(self.runtime)["positions"][0]
                self.assertFalse(details["can_migrate"]);self.assertFalse(details["can_close"])
                self.assertFalse(self.run_action(self.body("CLOSE"))["success"])
        self.spec.update(instrument_type="OPTION",contract_multiplier=100.)
        self.assertEqual(self.run_action()["reason"],"LEGACY_QUANTITY_UNIT_MISMATCH")

    def test_explicit_workspace_and_revision_required(self):
        body=self.body();body.pop("workspace")
        self.assertEqual(self.run_action(body)["reason"],"WORKSPACE_CHOICE_REQUIRED")
        body=self.body();body["revision"]="old"
        self.assertEqual(self.run_action(body)["reason"],"LEGACY_RECORD_CHANGED")

    def test_equivalent_canonical_exposure_is_not_imported_again(self):
        self.assertTrue(self.run_action()["success"])
        changed={**self.source,"positions":[{**self.record,"opened_at":"2026-08-18T23:34:17"}]}
        self.path.write_text(json.dumps(changed),encoding="utf-8")
        result=self.run_action();self.assertFalse(result["success"]);self.assertEqual(result["reason"],"CANONICAL_EXPOSURE_ALREADY_EXISTS")
        self.assertEqual(len(self.rows()),1)

    def test_all_outputs_keep_execution_locks(self):
        for result in [resolution.legacy_resolution_details(self.runtime),self.run_action()]:
            for key,expected in dict(paper_only=True,live_execution=False,automatic_broker_order=False,live_orders_locked=True,naked_option_selling=False).items():self.assertIs(result[key],expected)

    def test_closed_session_is_rechecked_by_real_quote_certificate(self):
        with patch('workstation.terminal_data.VENUE_SESSIONS.evaluate',return_value=SimpleNamespace(as_dict=lambda:dict(session_open=False))):
            before=self.path.read_bytes()
            self.assertEqual(self.run_action(self.body('CLOSE'))['reason'],'MARKET_SESSION_CLOSED')
            self.assertEqual(self.path.read_bytes(),before)

    def test_acknowledgement_crash_after_json_replace_is_retryable(self):
        body=self.body('CLOSE'); write=resolution._write_source
        def fail_after_replace(data):
            write(data)
            raise OSError('simulated process death after atomic replace')
        with patch.object(resolution,'_write_source',side_effect=fail_after_replace):
            self.assertEqual(self.run_action(body)['reason'],'SOURCE_ACK_PENDING')
        self.assertTrue(guard.legacy_exposure(self.desk))
        before=self.path.read_bytes()
        self.assertTrue(self.run_action(body)['success'])
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(guard.legacy_exposure(self.desk),[])

    def test_concurrent_calls_cannot_duplicate_canonical_exposure(self):
        body=self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.run_action(body),range(4)))
        self.assertTrue(any(r['success'] for r in results))
        self.assertEqual(len(self.rows()),1)
        self.assertTrue(self.run_action(body)['success'])
        self.assertEqual(guard.legacy_exposure(self.desk),[])

    def test_legacy_writer_cannot_resurrect_migrated_position(self):
        self.assertTrue(self.run_action()['success'])
        before=self.path.read_bytes()
        with guard.legacy_write_permission(self.path) as writable:
            self.assertFalse(writable)
        from workstation.paper_runtime import PaperTradingRuntime
        from agents.paper_broker import PaperBroker, Position
        old=PaperTradingRuntime.__new__(PaperTradingRuntime)
        old.state_file=self.path; old.broker=PaperBroker(); old.broker.positions={'BTC':Position(symbol='BTC',side='LONG',quantity=2,average_price=100)}
        old._autopilot=True; old._signals={}; old._activity=[]
        old.learning=SimpleNamespace(snapshot=lambda:{},load=lambda _:None)
        old._save()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(old.broker.positions,{})

    def test_http_requires_local_token_and_never_starts_session(self):
        from workstation.v16_terminal_http import build_handler, LEGACY_RESOLUTION_PATH
        self.runtime.token='test-local-token'
        self.runtime.reconcile=lambda **_:dict(success=not guard.legacy_exposure(self.desk))
        class Base(BaseHTTPRequestHandler):
            def _local(self):return self.headers.get('Origin','').startswith('http://127.0.0.1')
            def send_json(self,payload,status=200):
                raw=json.dumps(payload).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),build_handler(Base,self.runtime))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}{LEGACY_RESOLUTION_PATH}'
            raw=json.dumps(self.body()).encode()
            for headers in ({'Origin':'http://127.0.0.1'}, {'Origin':'https://example.com','X-Jarvis-Token':self.runtime.token}):
                with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(urllib.request.Request(url,raw,headers),timeout=5)
                self.assertEqual(caught.exception.code,403)
                caught.exception.close()
            self.assertEqual(self.rows(),[])
            headers={'Origin':'http://127.0.0.1','X-Jarvis-Token':self.runtime.token}
            with urllib.request.urlopen(urllib.request.Request(url,raw,headers),timeout=5) as response:
                data=json.load(response)
            self.assertTrue(data['success'],data)
            self.assertEqual(accounts.session(self.desk,'SWING')['state'],'PAUSED')
        finally:server.shutdown();thread.join();server.server_close()

    def test_canonical_option_buy_after_resolution_still_requires_start(self):
        from workstation import v16_option_paper, terminal_data
        self.assertTrue(self.run_action(self.body('CLOSE'))['success'])
        self.runtime.reconcile=lambda **_:dict(success=not guard.legacy_exposure(self.desk))
        symbol='NSE:NIFTY2691522400PE'
        self.quote.update(symbol=symbol,provider='FYERS_DATA',bid=99.5,ask=100.,ltp=100.)
        spec={**self.spec,'symbol':symbol,'provider_symbol':symbol,'instrument_type':'OPTION','asset_class':'OPTION','source':'FYERS_SYMBOL_MASTER'}
        body=dict(action='BUY',workspace='INTRADAY',symbol=symbol,option_type='PE',stop=90,target=120,lots=1,client_order_id='after-explicit-resolution')
        # Fix the exchange calendar in this fixture, not certificate validation.
        real_certificate=terminal_data.quote_certificate
        market_now=datetime.now(timezone.utc).replace(hour=5,minute=0,second=0,microsecond=0)
        self.quote.update(exchange_timestamp=market_now.isoformat(),received_at=market_now.isoformat())
        def certificate(symbol,payload,**kwargs):return real_certificate(symbol,payload,now=market_now,**kwargs)
        with patch.object(terminal_data,'quote_certificate',side_effect=certificate),patch.object(terminal_data.VENUE_SESSIONS,'evaluate',return_value=SimpleNamespace(as_dict=lambda:dict(session_open=True))),patch.object(v16_option_paper,'option_instrument_spec',return_value=spec):
            self.assertEqual(v16_option_paper.option_order(self.runtime,body)['reason'],'WORKSPACE_PAUSED')
            accounts.set_session(self.desk,'INTRADAY','START')
            opened=v16_option_paper.option_order(self.runtime,body)
            self.assertTrue(opened['success'],opened)
            self.assertEqual(len(self.rows()),1)

    def test_session_ui_uses_entry_session_not_overall_problem(self):
        js=(Path(__file__).resolve().parents[1]/"workstation/quant_terminal_v2_static/v16_option_execution.js").read_text(encoding="utf-8")
        section=js[js.index("function sessionState()"):js.index("function riskGate()")]
        self.assertNotIn("session?.state",section)
        self.assertIn("session?.entry_session",section)
        self.assertIn('state: "WAITING", detail: "STOP + TARGET REQUIRED"',js)

if __name__ == "__main__":unittest.main()
