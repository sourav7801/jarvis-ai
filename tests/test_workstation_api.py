import http.client
import json
import threading
import unittest
from unittest.mock import patch

from workstation import app


class WorkstationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.JarvisHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        encoded = None if body is None else json.dumps(body)
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=encoded, headers=request_headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, json.loads(payload) if payload else None

    def test_health_is_available_without_token(self):
        status, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["live_trading_enabled"])

    def test_dashboard_assets_are_not_cached(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", "/app.js")
        response = connection.getresponse()
        response.read()
        connection.close()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Cache-Control"), "no-store")

    def test_server_rejects_a_second_listener_on_the_same_port(self):
        with self.assertRaises(OSError):
            duplicate = app.JarvisHTTPServer(("127.0.0.1", self.port), app.Handler)
            duplicate.server_close()

    def test_state_requires_token(self):
        status, _payload = self.request("GET", "/api/state")
        self.assertEqual(status, 401)

    def test_authorized_capability_manifest(self):
        status, payload = self.request(
            "GET",
            "/api/capabilities",
            headers={"X-Jarvis-Token": app.API_TOKEN},
        )
        self.assertEqual(status, 200)
        self.assertGreater(len(payload["tools"]), 0)

    def test_control_plane_is_authenticated_and_delegated(self):
        expected = {
            "status": "READY",
            "summary": {"agents_ready": 22, "agents_total": 22},
        }
        with patch.object(app, "control_plane_snapshot", return_value=expected):
            status, payload = self.request(
                "GET",
                "/api/control-plane",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_command_endpoint_is_bounded_and_authenticated(self):
        expected = {"speech": "ok", "source": "test"}
        with patch.object(app, "execute_command", return_value=expected):
            status, payload = self.request(
                "POST",
                "/api/command",
                {"text": "hello"},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_command_endpoint_passes_conversation_context(self):
        expected = {"speech": "chart reply", "context": "charts"}
        with patch.object(app, "execute_command", return_value=expected) as command:
            status, payload = self.request(
                "POST",
                "/api/agent",
                {"text": "open NIFTY", "context": "charts"},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        command.assert_called_once_with("open NIFTY", "charts")

    def test_voice_confidence_is_forwarded_to_speech_guardrails(self):
        expected = {"speech": "please repeat", "action": "clarify_speech"}
        with patch.object(app, "execute_command", return_value=expected) as command:
            status, payload = self.request(
                "POST",
                "/api/agent",
                {"text": "unclear speech", "context": "master", "speech_confidence": 0.18},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        command.assert_called_once_with(
            "unclear speech", "master", speech_confidence=0.18
        )

    def test_quant_chat_uses_selected_symbol_and_broker_intelligence(self):
        intelligence = {
            "success": True,
            "symbol": "NIFTY",
            "setup": "PAPER_WATCH_SHORT",
            "confidence": 84,
            "regime": "SHORT",
            "support": 24249.95,
            "resistance": 24405.20,
        }
        with patch.object(app.PAPER_MARKET_DATA, "analyze", return_value=intelligence) as analyze:
            status, payload = self.request(
                "POST",
                "/api/agent",
                {
                    "text": "find the trade",
                    "context": "quant",
                    "active_symbol": "NIFTY",
                },
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["action"], "open_quant")
        self.assertEqual(payload["source"], "trading_intelligence")
        self.assertEqual(payload["symbol"], "NIFTY")
        self.assertIn("PAPER WATCH SHORT", payload["speech"])
        analyze.assert_called_once_with("NIFTY")

    def test_master_routes_crude_oil_analysis_to_multi_asset_intelligence(self):
        intelligence = {
            "success": True,
            "symbol": "CRUDEOIL",
            "setup": "PAPER_WATCH_LONG",
            "confidence": 84,
            "regime": "LONG",
            "support": 7860.0,
            "resistance": 7980.0,
            "strategy": "TREND_FOLLOWING",
            "risk_reward": 2.2,
            "chart_patterns": ["RANGE_EXPANSION"],
        }
        with patch.object(app.PAPER_MARKET_DATA, "analyze", return_value=intelligence) as analyze:
            result = app.execute_command(
                "Can you analyse the crude oil chart and check?", "master"
            )
        self.assertEqual(result["action"], "open_quant")
        self.assertEqual(result["symbol"], "CRUDEOIL")
        self.assertIn("CRUDEOIL broker analysis is ready", result["speech"])
        analyze.assert_called_once_with("CRUDEOIL")

    def test_master_can_arm_protected_paper_monitoring_from_compound_request(self):
        intelligence = {
            "success": True,
            "symbol": "CRUDEOIL",
            "setup": "PAPER_WATCH_LONG",
            "decision_gate": "QUALIFIED",
            "confidence": 84,
            "regime": "LONG",
            "strategy": "TREND_FOLLOWING",
            "risk_reward": 2.2,
            "chart_patterns": ["RANGE_EXPANSION"],
        }
        paper = {
            "paper_only": True,
            "live_orders": False,
            "positions": [
                {
                    "symbol": "CRUDEOIL",
                    "side": "LONG",
                    "stop_loss": 7860.0,
                    "take_profit": 8040.0,
                }
            ],
            "guardrails": {"max_open_positions": 6},
        }
        with (
            patch.object(app.PAPER_MARKET_DATA, "analyze", return_value=intelligence),
            patch.object(app.PAPER_RUNTIME, "set_autopilot") as arm,
            patch.object(app.PAPER_RUNTIME, "scan_once", return_value=paper) as scan,
        ):
            result = app.execute_command(
                "Analyse crude oil and whenever you find a trade ping me and execute trade",
                "master",
            )
        self.assertEqual(result["action"], "open_quant")
        self.assertTrue(result["notification_requested"])
        self.assertFalse(result["paper"]["live_orders"])
        self.assertIn("already open", result["speech"])
        self.assertIn("Live broker execution remains locked", result["speech"])
        arm.assert_called_once_with(True)
        scan.assert_called_once_with()

    def test_profile_followup_uses_previous_web_result_and_never_opens_quant(self):
        previous = {
            "query": "Risav Goswami SJMSOM LinkedIn",
            "mode": "WEB_SEARCH",
            "sources": [
                {
                    "title": "Risav Goswami | SJMSOM IIT-Bombay",
                    "url": "https://in.linkedin.com/in/risav-goswami",
                    "excerpt": "Accenture Strategy and Consulting; SJMSOM MBA 2024-26.",
                    "provider": "FIRECRAWL_FREE",
                }
            ],
        }
        assessment = {
            "success": True,
            "action": "open_web",
            "mode": "SOURCE_ASSESSMENT",
            "query": "Analyze this 1st profile will this person be suitable to handle my company",
            "answer": "Role-specific evidence is required before any hiring decision.",
            "message": "Assessment complete.",
            "sources": previous["sources"],
            "providers": ["DIRECT_WEBSITE"],
        }
        with (
            patch.object(app.WEB_INTELLIGENCE_AGENT, "snapshot", return_value={"latest": previous}),
            patch.object(app.WEB_INTELLIGENCE_AGENT, "assess_source", return_value=assessment) as assess,
            patch.object(app.PAPER_MARKET_DATA, "analyze") as quant,
        ):
            result = app.execute_command(
                "Analyze this 1st profile will this person be suitable to handle my company",
                "master",
            )
        self.assertEqual(result["action"], "open_web")
        self.assertEqual(result["mode"], "SOURCE_ASSESSMENT")
        self.assertNotEqual(result["action"], "open_quant")
        self.assertIn("Role-specific evidence", result["speech"])
        assess.assert_called_once_with(
            previous["sources"][0],
            "Analyze this 1st profile will this person be suitable to handle my company",
            selection_index=1,
            origin_query="Risav Goswami SJMSOM LinkedIn",
        )
        quant.assert_not_called()

    def test_profile_followup_can_recover_last_search_after_restart(self):
        recovered = {
            "query": "Risav Goswami SJMSOM LinkedIn",
            "mode": "WEB_SEARCH",
            "sources": [{"title": "Risav", "url": "https://example.com/risav"}],
        }
        stale_snapshot = {
            "latest": {
                "query": "analyze this profile for my company",
                "mode": "WEB_SEARCH",
                "sources": [{"title": "Wrong generic result", "url": "https://example.com/wrong"}],
            },
            "recent_results": [],
            "history": [
                {
                    "query": "analyze this profile for my company",
                    "mode": "WEB_SEARCH",
                    "success": True,
                },
                {
                    "query": "Risav Goswami SJMSOM LinkedIn",
                    "mode": "WEB_SEARCH",
                    "success": True,
                },
            ],
        }
        with (
            patch.object(app.WEB_INTELLIGENCE_AGENT, "snapshot", return_value=stale_snapshot),
            patch.object(app, "_sources_from_web_conversation", return_value=None),
            patch.object(app.WEB_INTELLIGENCE_AGENT, "research", return_value=recovered) as research,
        ):
            result = app._latest_web_search_result()
        self.assertEqual(result, recovered)
        research.assert_called_once_with(
            "search the web for Risav Goswami SJMSOM LinkedIn"
        )

    def test_ambiguous_romanized_speech_is_not_confidently_mistranslated(self):
        with patch.object(app.jarvis_main, "process_command") as chat:
            result = app.execute_command(
                "Aakhri Tak vaisa idhar koi wo nahi Ki.", "master"
            )
        self.assertEqual(result["action"], "clarify_speech")
        self.assertIn("will not invent a translation", result["speech"])
        chat.assert_not_called()

    def test_active_commodity_chart_uses_resolved_fyers_contract(self):
        contract = {
            "provider_symbol": "MCX:CRUDEOIL26AUGFUT",
            "description": "CRUDEOIL 19 Aug 26 FUT",
        }
        with (
            patch.object(app.PAPER_MARKET_DATA, "provider_symbol", return_value=contract),
            patch.object(app.v7, "set_chart") as set_chart,
        ):
            result = app.execute_command("open crude oil chart", "master")
        self.assertEqual(result["action"], "set_chart")
        self.assertEqual(result["chart"]["symbol"], "MCX:CRUDEOIL26AUGFUT")
        set_chart.assert_called_once()

    def test_invalid_limit_returns_bad_request(self):
        status, _payload = self.request(
            "GET",
            "/api/events?limit=nope",
            headers={"X-Jarvis-Token": app.API_TOKEN},
        )
        self.assertEqual(status, 400)

    def test_market_state_is_authenticated_and_data_only(self):
        expected = {
            "stream": {
                "provider": "FYERS",
                "running": True,
                "connected": True,
                "data_only": True,
                "live_orders": False,
            },
            "symbols": {"NIFTY": {"ltp": 24500.0}},
            "live_trading_enabled": False,
        }
        with patch.object(
            app.MARKET_RUNTIME,
            "public_state",
            return_value=expected,
        ):
            status, payload = self.request(
                "GET",
                "/api/market",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_market_restart_is_authenticated_and_delegated(self):
        expected = {
            "provider": "FYERS",
            "configured": True,
            "running": True,
            "data_only": True,
            "live_orders": False,
        }
        with patch.object(app.MARKET_RUNTIME, "restart", return_value=expected) as restart:
            status, payload = self.request(
                "POST",
                "/api/market/restart",
                {},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        restart.assert_called_once_with()

    def test_paper_state_is_authenticated_and_never_live(self):
        expected = {
            "paper_only": True,
            "live_orders": False,
            "autopilot": False,
            "positions": [],
        }
        with patch.object(app.PAPER_RUNTIME, "public_state", return_value=expected):
            status, payload = self.request(
                "GET",
                "/api/paper",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        self.assertFalse(payload["live_orders"])

    def test_paper_autopilot_requires_explicit_control(self):
        expected = {"paper_only": True, "live_orders": False, "autopilot": True}
        with patch.object(app.PAPER_RUNTIME, "set_autopilot", return_value=expected) as control:
            status, payload = self.request(
                "POST",
                "/api/paper/control",
                {"enabled": True},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        control.assert_called_once_with(True)

    def test_paper_order_is_delegated_only_to_synthetic_runtime(self):
        expected = {"ok": True, "paper_only": True, "state": {"live_orders": False}}
        with patch.object(app.PAPER_RUNTIME, "place_guarded_order", return_value=expected) as order:
            status, payload = self.request(
                "POST",
                "/api/paper/order",
                {"symbol": "NIFTY", "side": "BUY", "quantity": 2},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        order.assert_called_once_with("NIFTY", "BUY", 2.0)

    def test_paper_chat_parses_fractional_crypto_quantity(self):
        expected = {
            "ok": True,
            "result": {"execution_price": 7_500_000.0},
            "state": {"paper_only": True, "live_orders": False},
        }
        with patch.object(app.PAPER_RUNTIME, "place_guarded_order", return_value=expected) as order:
            payload = app.paper_command_payload("paper buy 0.01 BTC")
        self.assertEqual(payload["action"], "open_paper")
        order.assert_called_once_with("BTC", "BUY", 0.01)

    def test_paper_chat_does_not_replace_option_with_underlying(self):
        before = {
            "paper_only": True,
            "live_orders": False,
            "positions": [],
        }
        with (
            patch.object(app.PAPER_RUNTIME, "public_state", return_value=before),
            patch.object(
                app.PAPER_MARKET_DATA,
                "resolve_option_contract",
                side_effect=RuntimeError("No exact expiry contract."),
            ),
            patch.object(app.PAPER_RUNTIME, "place_guarded_order") as underlying_order,
            patch.object(app.PAPER_RUNTIME, "place_option_order") as option_order,
        ):
            payload = app.paper_command_payload(
                "paper buy crude oil mcx 10 qty 7900 ce option today expiry"
            )
        self.assertEqual(payload["action"], "open_paper")
        self.assertIn("did not substitute the underlying", payload["speech"])
        underlying_order.assert_not_called()
        option_order.assert_not_called()

    def test_paper_context_executes_exact_verified_option_contract(self):
        contract = {
            "provider_symbol": "MCX:CRUDEOIL26SEP7900CE",
            "description": "CRUDEOIL 17 Sep 26 7900 CE",
            "underlying": "CRUDEOIL",
            "strike": 7900.0,
            "option_type": "CE",
        }
        fill = {
            "ok": True,
            "paper_only": True,
            "result": {
                "execution_price": 560.0,
                "stop_loss": 280.0,
                "take_profit": 1120.0,
            },
            "state": {"paper_only": True, "live_orders": False},
        }
        with (
            patch.object(app.PAPER_MARKET_DATA, "resolve_option_contract", return_value=contract) as resolve,
            patch.object(app.PAPER_RUNTIME, "place_option_order", return_value=fill) as order,
        ):
            payload = app.paper_command_payload(
                "buy crude oil 7900 call of september expiry"
            )
        self.assertEqual(payload["action"], "open_paper")
        self.assertEqual(payload["option_contract"], contract)
        self.assertIn("Exact-contract synthetic option fill", payload["speech"])
        self.assertIn("no FYERS broker order was sent", payload["speech"])
        resolve.assert_called_once_with(
            "CRUDEOIL", 7900.0, "CE", "buy crude oil 7900 call of september expiry"
        )
        order.assert_called_once_with(contract, "BUY", 1.0)

    def test_option_strike_is_not_misread_as_quantity(self):
        parsed = app._paper_option_request(
            "buy crude oil 7900 call of september expiry"
        )
        self.assertEqual(parsed["strike"], 7900.0)
        self.assertEqual(parsed["quantity"], 1.0)

    def test_paper_quantity_recognizes_explicit_qty(self):
        self.assertEqual(
            app._paper_quantity("paper buy crude oil mcx qty 10"),
            10.0,
        )

    def test_paper_chat_recognizes_commodity_symbols(self):
        self.assertEqual(app._paper_symbol("paper buy gold"), "GOLD")
        self.assertEqual(app._paper_symbol("scan natural gas"), "NATURALGAS")

    def test_paper_analysis_command_returns_trade_or_wait_decision(self):
        intelligence = {
            "success": True,
            "symbol": "BTC",
            "setup": "NO_QUALIFIED_SETUP",
            "decision_gate": "WAIT",
            "confidence": 68,
            "risk_reward": 2.2,
            "strategy": "TREND_FOLLOWING",
            "chart_patterns": ["INSIDE_BAR"],
            "regime": "MIXED",
            "support": 63_000,
            "resistance": 65_000,
        }
        paper = {"paper_only": True, "live_orders": False, "autopilot": True}
        with (
            patch.object(app.PAPER_MARKET_DATA, "analyze", return_value=intelligence) as analyze,
            patch.object(app.PAPER_RUNTIME, "public_state", return_value=paper),
            patch.object(app.PAPER_RUNTIME, "scan_once") as scan,
            patch.object(app.PAPER_RUNTIME, "place_guarded_order") as order,
        ):
            payload = app.paper_command_payload(
                "analyze the bitcoin chart and tell me whether i need to take a trade or wait"
            )
        analyze.assert_called_once_with("BTC")
        scan.assert_not_called()
        order.assert_not_called()
        self.assertIn("WAIT — NO QUALIFIED SETUP", payload["speech"])
        self.assertEqual(payload["trading_intelligence"], intelligence)
        self.assertFalse(payload["paper"]["live_orders"])

    def test_paper_chat_routes_to_separate_context(self):
        expected = {
            "paper_only": True,
            "live_orders": False,
            "autopilot": False,
            "market_connected": True,
            "account": {"equity": 1_000_000.0, "open_positions": 0},
        }
        with patch.object(app.PAPER_RUNTIME, "public_state", return_value=expected):
            result = app.execute_command("show my paper portfolio", "paper")
        self.assertEqual(result["action"], "open_paper")
        self.assertEqual(result["context"], "paper")
        self.assertFalse(result["paper"]["live_orders"])

    def test_candle_endpoint_is_authenticated_and_bounded(self):
        expected = {
            "success": True,
            "source": "FYERS",
            "symbol": "NIFTY",
            "timeframe": "5m",
            "bars": 1,
            "candles": [{"timestamp": "2026-08-14T15:25:00+05:30", "close": 24366.0}],
        }
        with patch.object(app, "candle_payload", return_value=expected) as loader:
            status, payload = self.request(
                "GET",
                "/api/candles?symbol=NIFTY&timeframe=5m&bars=120",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        loader.assert_called_once_with("NIFTY", "5m", 120)

    def test_invalid_candle_bar_count_is_rejected(self):
        status, payload = self.request(
            "GET",
            "/api/candles?bars=not-a-number",
            headers={"X-Jarvis-Token": app.API_TOKEN},
        )
        self.assertEqual(status, 400)
        self.assertIn("invalid", payload["error"].lower())

    def test_news_endpoint_uses_query_and_limit(self):
        expected = {
            "success": True,
            "source": "GDELT_DOC_2",
            "query": "crude oil",
            "count": 0,
            "articles": [],
        }
        with patch.object(app, "search_market_news", return_value=expected) as search:
            status, payload = self.request(
                "GET",
                "/api/news?q=crude%20oil&limit=10",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        search.assert_called_once_with("crude oil", limit=10)

    def test_news_endpoint_passes_explicit_freshness_window(self):
        expected = {"success": True, "articles": [], "timespan": "1d"}
        with patch.object(app, "search_market_news", return_value=expected) as search:
            status, payload = self.request(
                "GET",
                "/api/news?q=crude%20oil&limit=10&timespan=1d",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        search.assert_called_once_with("crude oil", limit=10, timespan="1d")

    def test_news_briefing_endpoint_adds_reply_to_requested_chat(self):
        expected = {
            "success": True,
            "action": "news_briefing",
            "speech": "Here is the briefing.",
            "articles": [],
        }
        with patch.object(app, "build_news_briefing", return_value=expected) as briefing:
            status, payload = self.request(
                "POST",
                "/api/news/briefing",
                {"index": 1, "limit": 1, "chat_context": "news"},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload["speech"], "Here is the briefing.")
        self.assertEqual(payload["context"], "news")
        self.assertGreater(len(payload["messages"]), 0)
        briefing.assert_called_once_with(index=1, limit=1)

    def test_company_snapshot_is_authenticated(self):
        expected = {"agent_count": 16, "latest_plan": None}
        with patch.object(app.COMPANY_OS, "snapshot", return_value=expected):
            status, payload = self.request(
                "GET",
                "/api/company",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_company_plan_endpoint_is_bounded_and_delegated(self):
        expected = {"ok": True, "plan": {"id": "plan-1"}}
        with patch.object(app, "company_plan_payload", return_value=expected) as planner:
            status, payload = self.request(
                "POST",
                "/api/company/plan",
                {"idea": "A governed AI operations company."},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        planner.assert_called_once()

    def test_mission_snapshot_is_authenticated(self):
        expected = {"mission_count": 1, "latest_mission": {"id": "mission-1"}}
        with patch.object(app.MISSION_CONTROL, "snapshot", return_value=expected):
            status, payload = self.request(
                "GET",
                "/api/missions",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_mission_create_endpoint_is_bounded_and_delegated(self):
        expected = {"ok": True, "mission": {"id": "mission-1"}}
        with patch.object(app, "mission_create_payload", return_value=expected) as creator:
            status, payload = self.request(
                "POST",
                "/api/missions/create",
                {"objective": "Build a complete secure product mission."},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        creator.assert_called_once()

    def test_web_snapshot_is_authenticated(self):
        expected = {"latest": {"query": "safe AI"}, "broad_search_configured": False}
        with patch.object(app.WEB_INTELLIGENCE_AGENT, "snapshot", return_value=expected):
            status, payload = self.request(
                "GET", "/api/web", headers={"X-Jarvis-Token": app.API_TOKEN}
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)

    def test_web_research_endpoint_is_delegated(self):
        expected = {"ok": True, "result": {"query": "safe AI"}}
        with patch.object(app, "web_research_payload", return_value=expected) as researcher:
            status, payload = self.request(
                "POST",
                "/api/web/research",
                {"query": "search the web for safe AI"},
                {"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        researcher.assert_called_once()

    def test_greeting_in_web_context_stays_conversational(self):
        with (
            patch.object(app.jarvis_main, "process_command", return_value={"message": "Hello."}) as chat,
            patch.object(app.jarvis_main.AGENT_REGISTRY, "execute") as specialist,
            patch.object(app, "audit_event"),
        ):
            result = app.execute_command("hi", "web")
        self.assertEqual(result["speech"], "Hello.")
        self.assertEqual(result["source"], "orchestrator")
        chat.assert_called_once_with("hi")
        specialist.assert_not_called()

    def test_trading_intelligence_endpoint_is_read_only(self):
        expected = {"success": True, "symbol": "BANKNIFTY", "mode": "RESEARCH_AND_PAPER_ONLY"}
        with patch.object(app.PAPER_MARKET_DATA, "analyze", return_value=expected) as analyzer:
            status, payload = self.request(
                "GET",
                "/api/trading/intelligence?symbol=BANKNIFTY",
                headers={"X-Jarvis-Token": app.API_TOKEN},
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, expected)
        analyzer.assert_called_once_with("BANKNIFTY")


if __name__ == "__main__":
    unittest.main()
