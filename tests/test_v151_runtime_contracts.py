from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from agents.fyers_data_adapter import _response_details
from omni.agent_registry import default_agent_specs
from omni.trading_intelligence.market_reasoning_v15 import AUTONOMOUS_MARKET_REASONING_V15
from omni.trading_intelligence.option_chain_provider import ReadOnlyOptionChainProvider
from omni.trading_intelligence.options_execution_intelligence_v151 import OPTIONS_EXECUTION_INTELLIGENCE_V151
from scripts import jarvis_runtime_supervisor_v151 as runtime_v151
from workstation.quant_terminal_v151_bridge import QuantTerminalV151Handler


ROOT = Path(__file__).resolve().parents[1]


class V151RuntimeContracts(unittest.TestCase):
    def test_quant_launcher_preserves_v15_and_installs_v151_before_workers(self):
        text = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        for marker in (
            'os.environ["JARVIS_AUTO_PAPER_START"] = "0"',
            "install_v14_execution_bridges",
            "install_v141_risk_geometry_bridges",
            "install_v15_reasoning_bridges",
            "install_v151_options_bridges",
            "install_v151_quant_http_bridge",
            "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "install_v14_execution_bridges",
            "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "install_v15_reasoning_bridges",
        ):
            self.assertIn(marker, text)
        self.assertLess(text.index("install_v151_options_bridges()"), text.index("runtime.start()"))

    def test_completion_launcher_preserves_v15_literal_and_targets_v151(self):
        text = (ROOT / "start_jarvis_completion_console.py").read_text(encoding="utf-8")
        for marker in ("completion_console_v13", "completion_console_v14", "completion_console_v141", "completion_console_v15", "completion_console_v151"):
            self.assertIn(marker, text)
        self.assertIn("# from workstation import completion_console_v15 as completion_console", text)
        self.assertIn("from workstation import completion_console_v151 as completion_console", text)

    def test_main_launcher_preserves_all_historical_supervisors_and_runs_v151(self):
        text = (ROOT / "JARVIS_WORKSTATION.bat").read_text(encoding="utf-8")
        for marker in (
            "scripts.jarvis_runtime_supervisor_v62",
            "-m scripts.jarvis_runtime_supervisor_v8",
            "-m scripts.jarvis_runtime_supervisor_v11",
            "-m scripts.jarvis_runtime_supervisor_v12",
            "-m scripts.jarvis_runtime_supervisor_v13",
            "-m scripts.jarvis_runtime_supervisor_v14",
            "-m scripts.jarvis_runtime_supervisor_v141",
            "-m scripts.jarvis_runtime_supervisor_v15",
            "-m scripts.jarvis_runtime_supervisor_v151",
            "/api/v15.1/paper-authority",
        ):
            self.assertIn(marker, text)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)

    def test_v151_service_identities(self):
        services = {service.name: service for service in runtime_v151.v151_services(ROOT)}
        self.assertTrue(services["master"].health_url.endswith("/api/v15.1/paper-authority"))
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE")
        self.assertTrue(services["quant"].health_url.endswith("/api/v15.1/status"))
        self.assertEqual(services["quant"].expected_service, "JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE")
        self.assertTrue(services["completion"].health_url.endswith("/api/v15.1/status"))
        self.assertEqual(services["completion"].expected_service, "JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_OS")

    def test_quant_v151_surface_is_get_only_and_read_only(self):
        source = inspect.getsource(QuantTerminalV151Handler.do_GET)
        for endpoint in ("/api/v15.1/options/status", "/api/v15.1/options/plan", "/api/v15.1/status"):
            self.assertIn(endpoint, source)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order(", "do_POST"):
            self.assertNotIn(forbidden, source)

    def test_option_chain_provider_stays_strictly_read_only(self):
        class Provider:
            def snapshot(self, symbol):
                return {"symbol": symbol}
        wrapped = ReadOnlyOptionChainProvider(Provider())
        self.assertEqual(wrapped.snapshot("NIFTY")["symbol"], "NIFTY")
        for name in ("place_order", "trade", "execute", "buy", "sell", "cancel_order", "modify_order"):
            with self.assertRaises(PermissionError):
                getattr(wrapped, name)

    def test_v151_ui_surfaces_are_loaded_after_v15(self):
        qhtml = (ROOT / "workstation" / "quant_terminal_v2_static" / "index.html").read_text(encoding="utf-8")
        qjs = (ROOT / "workstation" / "quant_terminal_v2_static" / "v151_options_execution_runtime.js").read_text(encoding="utf-8")
        v15js = (ROOT / "workstation" / "quant_terminal_v2_static" / "v15_market_reasoning_runtime.js").read_text(encoding="utf-8")
        chtml = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        cjs = (ROOT / "workstation" / "completion_console_static" / "v151_options_execution.js").read_text(encoding="utf-8")
        self.assertIn("v15_market_reasoning_runtime.js", qhtml)
        self.assertIn("v151_options_execution_runtime.js", qhtml)
        self.assertLess(qhtml.index("v15_market_reasoning_runtime.js"), qhtml.index("v151_options_execution_runtime.js"))
        self.assertIn("optionsExecutionV151Nav", chtml + cjs)
        self.assertIn("v151_options_execution.js", chtml)
        for marker in ("LONG PREMIUM", "LIVE BROKER"):
            self.assertIn(marker, qjs)
        for marker in ("HYPOTHESES SUPPRESSED", "DATA PROVIDER", "providerState"):
            self.assertIn(marker, v15js)

    def test_fyers_429_is_preserved_as_rate_limited_not_token_expired(self):
        details = _response_details({"s": "error", "code": 429, "message": "Bad request"})
        self.assertEqual(details["provider_code"], 429)
        self.assertEqual(details["provider_state"], "RATE_LIMITED")
        self.assertGreaterEqual(int(details["retry_after_seconds"]), 60)
        self.assertIn("does not imply an expired token", details["message"])
        source = (ROOT / "agents" / "fyers_data_adapter.py").read_text(encoding="utf-8")
        for marker in (
            "JARVIS_FYERS_DATA_GOVERNOR_V151",
            "cross_process_serialization",
            "_MIN_REQUEST_INTERVAL_SECONDS",
            "_RATE_LIMIT_COOLDOWN_SECONDS",
            "provider_cache_hit",
            "market_data_fabricated",
        ):
            self.assertIn(marker, source)

    def test_no_verified_market_evidence_suppresses_hypothesis_percentages(self):
        reasoning = AUTONOMOUS_MARKET_REASONING_V15.reason(
            {
                "symbol": "NIFTY",
                "profile": "5m_only",
                "candidate_side": "WAIT",
                "regime": "DATA UNAVAILABLE",
                "evidence": [
                    {
                        "timeframe": "5m",
                        "available": False,
                        "source": "FYERS",
                        "data_quality": "UNAVAILABLE",
                        "provider_state": "RATE_LIMITED",
                        "provider_code": 429,
                        "retry_after_seconds": 65,
                        "raw_bars": 0,
                        "complete_bars": 0,
                        "message": "FYERS data API rate limited (429).",
                    }
                ],
            },
            base_decision={"expected_value_r": 0.0},
        )
        self.assertFalse(reasoning["success"])
        self.assertEqual(reasoning["hypotheses"], [])
        self.assertIsNone(reasoning["dominant_hypothesis"])
        self.assertTrue(reasoning["hypotheses_suppressed_no_verified_evidence"])
        self.assertEqual(reasoning["provider_state"], "RATE_LIMITED")
        self.assertEqual(reasoning["provider_code"], 429)
        self.assertEqual(reasoning["market_belief"]["uncertainty"], 1.0)

    def test_permanent_agents_remain_29_with_critic(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)
        for plane in ("options_execution_intelligence_v151", "options_runtime_v151", "options_paper_execution_v151"):
            self.assertNotIn(plane, names)

    def test_v151_policy_is_long_premium_paper_only(self):
        status = OPTIONS_EXECUTION_INTELLIGENCE_V151.status()
        self.assertTrue(status["long_premium_only"])
        self.assertFalse(status["naked_option_selling"])
        self.assertTrue(status["requires_verified_option_chain"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])
        self.assertEqual(status["dealer_positioning"], "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY")

    def test_new_sources_expose_no_live_broker_surface(self):
        paths = (
            "omni/trading_intelligence/options_execution_intelligence_v151.py",
            "workstation/options_paper_execution_v151.py",
            "workstation/options_runtime_v151.py",
            "workstation/v151_runtime_bridges.py",
            "workstation/quant_terminal_v151_bridge.py",
            "workstation/completion_console_v151.py",
            "workstation/jarvis_os_v151_bridge.py",
            "scripts/jarvis_runtime_supervisor_v151.py",
            "start_jarvis_master_v151.py",
        )
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)
        self.assertIn("paper_only", text)
        self.assertIn("live_execution", text)
        self.assertIn("automatic_broker_order", text)


if __name__ == "__main__":
    unittest.main()
