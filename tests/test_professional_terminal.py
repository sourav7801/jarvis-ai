"""Deterministic execution/failure tests. Quotes here are test fixtures only."""
from concurrent.futures import ThreadPoolExecutor
import ast
import multiprocessing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request

from workstation.paper_trading_desk import PaperTradingDesk
from workstation import workspace_accounts as accounts
from workstation.terminal_data import quote_certificate, validate_candles, SingleFlightCache, BoundedPool
from workstation.professional_terminal import TerminalRuntime, TerminalHTTPServer, build_handler


def quote(symbol="BTC", price=100, **changes):
    now = datetime.now(timezone.utc).isoformat()
    return {"success": True, "symbol": symbol, "source": "BINANCE_PUBLIC", "mark": price,
            "received_at": now, "exchange_timestamp": now, **changes}


def stub_engine():
    return SimpleNamespace(manage_marks=True, scan_interval_seconds=30, universe=(), _stop=threading.Event(),
                           _scan_thread=None, _trigger_thread=None, _mark_thread=None, _lock=threading.RLock(),
                           _scan_guard=threading.Lock(), _last_rows_summary=[], _last_rejection_counts={},
                           _scan_cycles=0, profile="intraday")


def process_order(path, order, barrier, results):
    desk=PaperTradingDesk(path,max_open_positions=1)
    barrier.wait(timeout=5)
    results.put(desk.open_position(**order))


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "desk.sqlite3"
        self.desk = PaperTradingDesk(self.path)
        accounts.initialize(self.desk)
        for name in accounts.WORKSPACES:
            accounts.set_session(self.desk, name, True)

    def order(self, symbol="BTC", name="INTRADAY", **changes):
        return dict(symbol=symbol,side="LONG",entry=100.,stop=98.,target=106.,
                    risk_multiplier=1.,portfolio_bucket=name,external_id="test:"+name+":"+symbol,
                    instrument_spec={"symbol":symbol,"provider_symbol":symbol,"asset_class":"SPOT","instrument_type":"SPOT",
                                     "quantity_step":1.,"contract_multiplier":1.,"tick_size":.05,"verified":True},
                    metadata={"entry_certificate":quote(symbol),"session_generation":accounts.session(self.desk,name)["generation"]},**changes)

    def balances(self):
        with self.desk._lock,self.desk._connection() as conn:
            return accounts.account_snapshot(self.desk,conn)

    def opened(self, **changes):
        order=self.order(); order.update(changes)
        result=self.desk.open_position(**order)
        self.assertTrue(result["success"],result)
        return result

    def test_funded_cost_aware_variable_sizing(self):
        first=self.opened(risk_multiplier=.10)
        second=self.opened(symbol="ETH", external_id="test:ETH", instrument_spec={**self.order()["instrument_spec"],"symbol":"ETH"},
                           metadata={"entry_certificate":quote("ETH"),"session_generation":accounts.session(self.desk,"INTRADAY")["generation"]})
        self.assertGreater(second["sizing"]["quantity"],first["sizing"]["quantity"])
        self.assertLessEqual(second["sizing"]["capital_at_risk"],second["sizing"]["risk_budget"])
        self.assertEqual(second["sizing"]["risk_weight"],.25)
        self.assertGreater(second["sizing"]["capital_allocated"],second["sizing"]["capital_at_risk"])
        a=self.balances()["INTRADAY"]
        self.assertLess(a["available_capital"],50000-a["positions"][0]["capital_allocated"])

    def test_untrusted_calibration_cannot_increase_risk(self):
        order=self.order()
        order["metadata"]["confidence_calibration"]={"held_out":True,"sample_count":100000,"brier_score":0}
        self.assertEqual(self.opened(**order)["sizing"]["risk_weight"],.25)

    def test_workspaces_do_not_share_cash_or_pnl(self):
        self.opened()
        self.desk.manage_positions({"BTC":99.})
        a=self.balances()
        self.assertLess(a["INTRADAY"]["available_capital"],50000)
        self.assertEqual(a["SWING"]["available_capital"],30000)
        self.assertEqual(a["INVESTMENT"]["available_capital"],20000)
        self.assertLess(a["INTRADAY"]["daily_pnl"],0)
        self.assertEqual(a["SWING"]["daily_pnl"],0)

    def test_saved_mark_survives_snapshot_and_restart(self):
        self.opened()
        self.desk.manage_positions({"BTC":99.})
        self.assertEqual(self.desk.snapshot()["positions"][0]["mark"],99.)
        restarted=PaperTradingDesk(self.path)
        self.assertEqual(restarted.snapshot()["positions"][0]["mark"],99.)

    def test_pause_invalidates_inflight_decision(self):
        order=self.order()
        accounts.set_session(self.desk,"INTRADAY",False)
        self.assertEqual(self.desk.open_position(**order)["reason"],"WORKSPACE_PAUSED")
        accounts.set_session(self.desk,"INTRADAY",True)
        self.assertEqual(self.desk.open_position(**order)["reason"],"SESSION_TICKET_EXPIRED")

    def test_restart_idempotency_including_closed_position(self):
        order=self.order(); opened=self.desk.open_position(**order)
        self.desk.close_position(position_id=opened["position_id"],exit_price=102,reason="TEST")
        restarted=PaperTradingDesk(self.path); accounts.reset_sessions(restarted)
        self.assertEqual(restarted.open_position(**order)["reason"],"ALREADY_RECORDED")
        self.assertEqual(restarted.snapshot()["open_count"],0)
        with restarted._connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM terminal_orders WHERE status='FILLED' AND kind='ENTRY'").fetchone()[0],1)

    def test_concurrent_desk_instances_cannot_exceed_position_limit(self):
        # Independent RLocks sharing a SQLite file, as in multiple agents/processes.
        self.desk.max_open_positions=1
        other=PaperTradingDesk(self.path,max_open_positions=1)
        barrier=threading.Barrier(2)
        def submit(desk,symbol):
            order=self.order(symbol=symbol)
            barrier.wait(timeout=2)
            return desk.open_position(**order)
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(submit,self.desk,"BTC"),pool.submit(submit,other,"ETH")]
            results=[f.result(timeout=6) for f in futures]
        self.assertEqual(sum(r["success"] for r in results),1,results)
        self.assertEqual(self.desk.snapshot()["open_count"],1)

    def test_duplicate_lanes_cannot_open_same_workspace_instrument(self):
        order=self.order(); order["portfolio_bucket"]="INTRADAY_5M"
        self.assertTrue(self.desk.open_position(**order)["success"])
        order["external_id"]="different-lane"; order["portfolio_bucket"]="INTRADAY_15M"
        self.assertEqual(self.desk.open_position(**order)["reason"],"WORKSPACE_SYMBOL_ALREADY_OPEN")

    def test_outage_blocks_entry_without_fake_fill(self):
        order=self.order();order["metadata"]["entry_certificate"]=quote(exchange_timestamp=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat())
        self.assertEqual(self.desk.open_position(**order)["reason"],"STALE_MARK")
        self.assertEqual(self.desk.snapshot()["open_count"],0)

    def test_mapping_mismatch_rejected(self):
        order=self.order();order["metadata"]["entry_certificate"]=quote("ETH")
        self.assertEqual(self.desk.open_position(**order)["reason"],"QUOTE_INSTRUMENT_MISMATCH")

    def test_old_decision_cannot_fill_at_historical_price(self):
        order=self.order();order["metadata"]["entry_certificate"]=quote("BTC",110)
        self.assertEqual(self.desk.open_position(**order)["reason"],"LIVE_ENTRY_DRIFT_TOO_LARGE")

    def test_strategy_decision_through_sizing_execution_exit_and_journal(self):
        from tests.test_v12_adaptive_market_intelligence import _row
        from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
        from workstation.paper_market_data import PAPER_MARKET_DATA
        engine=AdaptivePaperAutonomyEngine(universe=("BTC",),profile="adaptive_intraday",portfolio_bucket="INTRADAY",allocation_fraction=.5,manage_marks=False)
        row=_row(score=75,alignment=100,rr=3)
        row.update(entry=100,stop=98,target=106,timeframe="5m")
        row["evidence"][0]["last_candle_time"]="2026-09-09T05:00:00+00:00"
        with patch("workstation.adaptive_paper_autonomy_engine.paper_desk",self.desk), \
             patch.object(engine,"_scan_symbol",return_value=row), \
             patch("workstation.paper_trading_desk.live_mark_snapshot",side_effect=lambda s:quote_certificate(s,quote(s))), \
             patch.object(PAPER_MARKET_DATA,"instrument_spec",return_value=self.order()["instrument_spec"]), \
             patch.object(PAPER_MARKET_DATA,"quote",return_value={"success":True,"native_ltp":100,"valuation_ltp":100}):
            result=engine.scan_once()
        self.assertEqual(len(result["opened"]),1,result)
        position=self.balances()["INTRADAY"]["positions"][0]
        self.assertTrue(position["metadata"]["workspace_sizing"])
        self.assertEqual(position["metadata"]["entry_certificate"]["source"],"BINANCE_PUBLIC")
        self.desk.manage_positions({"BTC":97.})
        runtime=self.runtime(lambda s:{})
        state=runtime.snapshot()
        self.assertEqual(len(state["history"]),1)
        self.assertEqual(state["orders"][0]["position_id"],state["history"][0]["id"])
        self.assertEqual(state["history"][0]["metadata"]["exit_reason"],"STOP_HIT")

    def test_insufficient_daily_headroom_blocks_order(self):
        self.opened()
        self.desk.close_position(symbol="BTC",exit_price=1.,reason="GAP")
        order=self.order("ETH")
        self.assertEqual(self.desk.open_position(**order)["reason"],"WORKSPACE_DAILY_LOSS_LIMIT")

    def test_daily_profit_and_capital_reallocation_preserve_pnl(self):
        self.opened()
        self.desk.close_position(symbol="BTC",exit_price=103.,reason="TEST")
        before=self.balances()["INTRADAY"]["daily_pnl"]
        self.assertGreater(before,0)
        accounts.reset_sessions(self.desk)
        accounts.configure(self.desk,"INTRADAY",allocations={"INTRADAY":.4,"SWING":.4,"INVESTMENT":.2})
        self.assertAlmostEqual(self.balances()["INTRADAY"]["daily_pnl"],before)

    def test_insufficient_funds_for_lot_is_rejected(self):
        order=self.order();order["instrument_spec"]["contract_multiplier"]=100000
        self.assertEqual(self.desk.open_position(**order)["reason"],"INSUFFICIENT_CAPITAL_OR_RISK_FOR_ONE_LOT")

    def test_margin_and_derivative_specs_required(self):
        order=self.order();order["instrument_spec"]["instrument_type"]="FUTURE"
        self.assertEqual(self.desk.open_position(**order)["reason"],"VERIFIED_MARGIN_REQUIRED")
        order["instrument_spec"]["verified"]=False
        self.assertEqual(self.desk.open_position(**order)["reason"],"VERIFIED_INSTRUMENT_SPEC_REQUIRED")

    def test_short_geometry_and_long_only_mandates(self):
        order=self.order();order.update(side="SHORT",stop=102,target=96)
        result=self.desk.open_position(**order)
        self.assertTrue(result["success"],result)
        self.desk.manage_positions({"BTC":104.})
        self.assertEqual(self.desk.snapshot()["open_count"],0)
        self.assertLess(self.balances()["INTRADAY"]["realized_pnl"],0)
        order=self.order(name="SWING");order.update(side="SHORT",stop=102,target=96)
        self.assertEqual(self.desk.open_position(**order)["reason"],"SHORT_NOT_SUPPORTED_FOR_THIS_MANDATE")

    def test_nonfinite_allocations_and_settings_rejected(self):
        accounts.reset_sessions(self.desk)
        for v in [float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError): accounts.configure(self.desk,"INTRADAY",allocations=dict.fromkeys(accounts.WORKSPACES,v))
            with self.assertRaises(ValueError): accounts.configure(self.desk,"INTRADAY",settings={"risk_per_trade":v})

    def runtime(self, loader):
        controller=SimpleNamespace(engines={name:stub_engine() for name in accounts.WORKSPACES},allocations={},start_bucket=lambda *args,**kw:None)
        runtime=TerminalRuntime(self.desk,controller,mark_loader=loader)
        self.addCleanup(runtime.stop)
        return runtime

    def test_swing_position_monitored_while_all_entries_paused(self):
        self.opened(**self.order(name="SWING"))
        runtime=self.runtime(lambda symbol:quote_certificate(symbol,quote(symbol,97)))
        runtime.monitor_once()
        self.assertEqual(self.desk.snapshot()["open_count"],0)
        state=runtime.snapshot("SWING")
        self.assertEqual(len(state["history"]),1)
        self.assertEqual(len(runtime.snapshot("INTRADAY")["history"]),0)
        self.assertEqual(state["entry_session"],"PAUSED")

    def test_disconnect_freezes_then_recovers_at_actual_gap_mark(self):
        self.opened()
        runtime=self.runtime(lambda symbol:{"eligible_for_exit":False,"reason":"DISCONNECTED"})
        runtime.monitor_once()
        self.assertEqual(runtime.snapshot()["state"],"DATA_PROBLEM")
        self.assertEqual(self.desk.snapshot()["open_count"],1)
        runtime.mark_loader=lambda symbol:quote_certificate(symbol,quote(symbol,90))
        runtime.monitor_once()
        trade=runtime.snapshot()["history"][0]
        self.assertLessEqual(trade["exit_price"],90)  # Includes configured adverse friction.
        self.assertEqual(trade["metadata"]["exit_reason"],"STOP_HIT")

    def test_alerts_without_positions_and_thesis_ownership(self):
        runtime=self.runtime(lambda symbol:quote_certificate(symbol,quote(symbol,101)))
        runtime.save_note("SWING",{"symbol":"BTC","kind":"alert","body":{"condition":"above","level":100}})
        runtime.monitor_once()
        notes=runtime.snapshot("SWING")["notes"]
        self.assertTrue(notes[0]["body"]["triggered_at"])
        self.assertEqual(runtime.snapshot("INTRADAY")["notes"],[])
        with self.assertRaises(ValueError): runtime.save_note("INVESTMENT",{"id":notes[0]["id"],"symbol":"BTC","kind":"alert","body":{"condition":"below","level":90}})

    def test_slow_analysis_result_delivered_after_ttl(self):
        runtime=self.runtime(lambda symbol:{})
        gate=threading.Event()
        def load(): gate.wait(timeout=1); return {"answer":42}
        self.assertTrue(runtime.job("x",load,ttl=.001)["pending"])
        gate.set()
        runtime._jobs["x"][1].result(timeout=1)
        self.assertEqual(runtime.job("x",load,ttl=.001)["result"]["answer"],42)

    def test_http_start_pause_settings_and_host_csrf(self):
        from workstation.quant_terminal_v2 import Handler
        runtime=self.runtime(lambda symbol:{})
        with TerminalHTTPServer(("127.0.0.1",0),build_handler(Handler,runtime)) as server:
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base="http://127.0.0.1:"+str(server.server_port)
            try:
                state=json.load(urllib.request.urlopen(base+"/api/terminal/state?workspace=SWING"))
                self.assertEqual(state["account"]["available_capital"],30000)
                request=urllib.request.Request(base+"/api/terminal/session",data=json.dumps({"workspace":"SWING","action":"pause"}).encode(),headers={"X-Jarvis-Token":state["csrf_token"],"Content-Type":"application/json"})
                self.assertEqual(json.load(urllib.request.urlopen(request))["state"],"PAUSED")
                request.remove_header("X-jarvis-token")
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403)
                with self.assertRaises(OSError): TerminalHTTPServer(("127.0.0.1",server.server_port),Handler)
            finally: server.shutdown();worker.join(timeout=2)

    def test_two_processes_serialize_the_same_capital(self):
        ctx=multiprocessing.get_context("spawn"); barrier=ctx.Barrier(2); results=ctx.Queue()
        processes=[ctx.Process(target=process_order,args=(self.path,self.order(symbol),barrier,results)) for symbol in ("BTC","ETH")]
        try:
            for p in processes: p.start()
            outcomes=[results.get(timeout=10) for _ in processes]
            for p in processes: p.join(timeout=5); self.assertEqual(p.exitcode,0)
            self.assertEqual(sum(r["success"] for r in outcomes),1,outcomes)
            self.assertEqual(self.desk.snapshot()["open_count"],1)
        finally:
            for p in processes:
                if p.is_alive(): p.terminate();p.join(timeout=2)
            results.close()

    def test_partial_fill_and_fired_rung_roll_back_together(self):
        order=self.order(); order["metadata"]["exit_policy"]={"scale_out":[{"at_r":1,"fraction":.5}]}
        self.opened(**order); before=self.desk.snapshot()["positions"][0]
        original=self.desk._event
        def fail(conn, position, kind, payload):
            original(conn,position,kind,payload)
            if kind=="SCALE_OUT": raise RuntimeError("injected crash before commit")
        with patch.object(self.desk,"_event",side_effect=fail):
            with self.assertRaises(RuntimeError): self.desk.manage_positions({"BTC":103})
        after=self.balances()["INTRADAY"]["positions"][0]
        self.assertEqual(after["quantity"],before["quantity"])
        self.assertFalse(after["metadata"].get("scale_out_fired"))
        restarted=PaperTradingDesk(self.path); restarted.manage_positions({"BTC":103}); qty=restarted.snapshot()["positions"][0]["quantity"]
        restarted.manage_positions({"BTC":103})
        self.assertEqual(restarted.snapshot()["positions"][0]["quantity"],qty)
        self.assertLess(qty,before["quantity"])
        with restarted._connection() as conn:
            self.assertTrue(accounts.reconcile(restarted,conn)["success"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM terminal_orders WHERE kind='SCALE_OUT'").fetchone()[0],1)

    def test_new_day_uses_prior_persisted_equity(self):
        self.opened(**self.order(name="SWING")); self.desk.manage_positions({"BTC":99})
        old=self.balances()["SWING"]["equity"]
        with self.desk._connection() as conn:
            conn.execute("DELETE FROM terminal_daily")
            conn.execute("UPDATE terminal_workspaces SET last_equity_day='2000-01-01'")
        current=self.balances()["SWING"]
        self.assertAlmostEqual(current["equity"],old)
        self.assertAlmostEqual(current["daily_pnl"],0)
        self.desk.manage_positions({"BTC":98.5})
        self.assertLess(self.balances()["SWING"]["daily_pnl"],0)

    def test_restart_does_not_mint_fresh_starting_capital(self):
        other=PaperTradingDesk(self.path,starting_equity=10_000_000)
        accounts.initialize(other)
        with other._connection() as conn:
            balances=accounts.account_snapshot(other,conn)
        self.assertEqual(sum(a["starting_capital"] for a in balances.values()),100000)

    def test_reconciliation_blocks_an_orphaned_order(self):
        self.opened(); runtime=self.runtime(lambda s:{})
        with self.desk._connection() as conn:
            conn.execute("UPDATE terminal_orders SET position_id=999 WHERE kind='ENTRY'")
        self.assertFalse(runtime.control("INTRADAY","start")["success"])
        self.assertFalse(runtime.snapshot()["reconciliation"]["success"])
        self.assertEqual(self.desk.snapshot()["open_count"],1)

    def test_slow_mark_is_single_flight_and_state_stays_responsive(self):
        self.opened(); gate=threading.Event(); calls=[]
        def loader(s): calls.append(s); gate.wait(timeout=6); return quote_certificate(s,quote(s))
        runtime=self.runtime(loader)
        try:
            runtime.monitor_once()
            pending=runtime._mark_jobs["BTC"]
            start=time.perf_counter();runtime.control("INTRADAY","pause");runtime.snapshot()
            self.assertLess(time.perf_counter()-start,.5)
            gate.set();pending.result(timeout=2);runtime.monitor_once()
            self.assertEqual(calls,["BTC"])
        finally: gate.set()

    def test_workspace_risk_module_contains_only_its_positions(self):
        self.opened(); runtime=self.runtime(lambda s:{})
        swing=runtime.module("SWING","BTC","portfolio-risk")["result"]
        self.assertEqual(swing["account"]["positions"],[])
        self.assertEqual(swing["account"]["available_capital"],30000)

    def test_session_start_error_survives_successful_monitor(self):
        runtime=self.runtime(lambda s:{})
        runtime.controller.start_bucket=lambda *a,**k:(_ for _ in ()).throw(RuntimeError("injected failure"))
        runtime.control("INTRADAY","start");runtime._control_jobs["INTRADAY"].result(timeout=2)
        runtime.monitor_once()
        state=runtime.snapshot()
        self.assertEqual(state["state"],"PROBLEM")
        self.assertEqual(state["entry_session"],"PAUSED")
        self.assertIn("Session start failed",state["status_reason"])


class MarketQualityTests(unittest.TestCase):
    def test_required_quote_timestamps_and_quality(self):
        now=datetime.now(timezone.utc)
        cases=[({"exchange_timestamp":None},"MARK_EXCHANGE_TIMESTAMP_MISSING"),
               ({"received_at":None},"MARK_RECEIVED_TIMESTAMP_MISSING"),
               ({"exchange_timestamp":(now+timedelta(seconds=10)).isoformat()},"FUTURE_MARK_TIMESTAMP"),
               ({"delayed":True},"DATA_NOT_LIVE"),({"simulated":True},"DATA_NOT_LIVE"),
               ({"mark":float('nan')},"INVALID_MARK"),({"bid":102,"ask":101},"INVALID_BID_ASK"),
               ({"source":"YAHOO"},"UNVERIFIED_PROVIDER")]
        for change,reason in cases:
            with self.subTest(reason=reason):
                certificate=quote_certificate("BTC",quote(**change))
                self.assertFalse(certificate["eligible_for_entry"])
                self.assertEqual(certificate["reason"],reason)

    def test_indian_session_closed(self):
        at=datetime(2026,9,9,16,tzinfo=timezone.utc)
        certificate=quote_certificate("NIFTY",quote("NIFTY",source="FYERS",received_at=at.isoformat(),exchange_timestamp=at.isoformat()),now=at)
        self.assertEqual(certificate["reason"],"MARKET_SESSION_CLOSED")

    def test_candles_ohlc_order_and_future(self):
        row={"time":datetime.now(timezone.utc).timestamp()-300,"open":100,"high":103,"low":98,"close":102}
        self.assertIsNone(validate_candles([row],300))
        self.assertEqual(validate_candles([row,row],300),"OUT_OF_ORDER_OR_DUPLICATE_CANDLES")
        self.assertEqual(validate_candles([{**row,"high":99}],300),"INVALID_CANDLE_OHLC")
        self.assertEqual(validate_candles([{**row,"time":row["time"]+600}],300),"FUTURE_CANDLE")

    def test_shared_reads_deduplicate_concurrent_agents(self):
        cache=SingleFlightCache(capacity=2); barrier=threading.Barrier(8); calls=[]
        def loader(): calls.append(1); time.sleep(.02); return {"price":100}
        def read(): barrier.wait(timeout=1); return cache.get("same-bar",loader,ttl=10)
        with ThreadPoolExecutor(8) as pool: results=list(pool.map(lambda _:read(),range(8)))
        self.assertEqual(len(calls),1);self.assertEqual(len(results),8)
        results[0]["price"]=0
        self.assertEqual(cache.get("same-bar",loader)["price"],100)
        for i in range(4): cache.get(i,loader)
        self.assertEqual(cache.status()["entries"],2)

    def test_bounded_worker_queue(self):
        pool=BoundedPool(workers=1,capacity=1);gate=threading.Event()
        future=pool.submit(lambda:gate.wait(timeout=1))
        try:
            with self.assertRaises(RuntimeError): pool.submit(lambda:None)
        finally: gate.set();future.result(timeout=1);pool._pool.shutdown()


if __name__ == '__main__': unittest.main()
