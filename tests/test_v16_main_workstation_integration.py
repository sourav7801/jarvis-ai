from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from scripts import jarvis_runtime_supervisor_v16
from workstation import jarvis_os_v16_bridge
from workstation import v16_terminal_http


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "workstation" / "jarvis_os_v3_assets"
QUANT_ASSETS = ROOT / "workstation" / "quant_terminal_v2_static"


class V16MainWorkstationIntegrationTests(unittest.TestCase):
    def test_chart_library_is_served_by_actual_master_handler(self):
        import threading
        import urllib.request
        server = jarvis_os_v16_bridge.create_server('127.0.0.1', 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_address[1]}/v16/lightweight-charts.js'
            with urllib.request.urlopen(url, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b'Lightweight Charts', response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_supervisor_composes_v16_master_and_internal_professional_trading(self):
        services = {service.name: service for service in jarvis_runtime_supervisor_v16.v16_services(ROOT)}
        self.assertIn("master", services)
        self.assertIn("quant", services)
        self.assertEqual(services["master"].port, 8797)
        self.assertEqual(services["master"].expected_service, "JARVIS_MASTER_V16_UNIFIED_WORKSTATION_BRIDGE")
        self.assertTrue(services["master"].argv[-1].endswith("start_jarvis_master_v16.py"))
        self.assertEqual(services["quant"].port, 8787)
        self.assertEqual(services["quant"].expected_service, "JARVIS_PROFESSIONAL_PAPER_TERMINAL")
        self.assertTrue(services["quant"].argv[-1].endswith("start_jarvis_professional_terminal_v16.py"))
        env = dict(services["quant"].environment)
        self.assertEqual(env.get("JARVIS_AUTO_PAPER_START"), "0")
        self.assertEqual(env.get("JARVIS_V12_AUTO_PAPER_START"), "0")
        self.assertEqual(env.get("JARVIS_NO_BROWSER"), "1")

    def test_master_uses_protected_core_bootstrap(self):
        launcher = (ROOT / "start_jarvis_master_v16.py").read_text(encoding="utf-8")
        self.assertIn("from start_jarvis_v3 import main as protected_master_main", launcher)
        self.assertIn("jarvis_os_v8.create_server = create_v16_bridge_server", launcher)
        self.assertIn('os.environ["JARVIS_AUTO_PAPER_START"] = "0"', launcher)
        self.assertIn("Live broker execution: LOCKED", launcher)

    def test_master_bridge_exposes_same_origin_read_only_trading_gateway(self):
        routes = dict(jarvis_os_v16_bridge._TRADING_GET_ROUTES)
        self.assertEqual(routes["/api/v16/trading/health"], "/api/terminal/health")
        self.assertEqual(routes["/api/v16/trading/workspace-state"], "/api/v16/trading/workspace-state")
        self.assertEqual(routes["/api/v16/trading/chart"], "/api/terminal/chart")
        source = inspect.getsource(jarvis_os_v16_bridge.V16BridgeHandler)
        self.assertIn("v16_main_trading_runtime.js", source)
        self.assertIn("v16_main_trading.css", source)
        self.assertIn("TRADING_SERVICE_UNAVAILABLE", source)

    def test_main_chart_runtime_supports_exact_one_through_eight(self):
        source = (ASSETS / "v16_main_trading_runtime.js").read_text(encoding="utf-8")
        self.assertIn("count >= 1 && count <= 8", source)
        self.assertIn("for (let count = 1; count <= 8; count++)", source)
        self.assertIn("chartSlots = chartSlots.slice(0, count)", source)
        self.assertIn("v16LayoutColumns", source)
        self.assertIn("v16ChartSymbol", source)
        self.assertIn("v16ChartTimeframe", source)
        self.assertIn("index * 140", source)
        self.assertNotIn("http://127.0.0.1:8787", source)

    def test_rich_quant_surface_keeps_exact_layouts_and_v16_workspace_runtime(self):
        html = (QUANT_ASSETS / "index.html").read_text(encoding="utf-8")
        workspace = (QUANT_ASSETS / "v16_workspace.js").read_text(encoding="utf-8")
        option_runtime = (QUANT_ASSETS / "option_chart_runtime.js").read_text(encoding="utf-8")
        for count in range(1, 9):
            self.assertIn(f'data-layout="{count}"', html)
        for mode in ("INTRADAY", "SWING", "INVESTMENT", "OPTIONS"):
            self.assertIn(f'data-workspace="{mode}"', html)
        self.assertIn('<script src="/v16_workspace.js"></script>', html)
        self.assertIn("/api/v16/trading/workspace-state", workspace)
        self.assertIn("/api/terminal/session", workspace)
        self.assertIn("option-chain", workspace)
        self.assertIn("LIVE BROKER EXECUTION LOCKED", workspace)
        self.assertIn("NAKED OPTION SELLING BLOCKED", workspace)
        self.assertIn("layout = chartCount(Number(result.layout))", option_runtime)

    def test_rich_quant_surface_exposes_canonical_long_option_paper_controls(self):
        html = (QUANT_ASSETS / "index.html").read_text(encoding="utf-8")
        execution = (QUANT_ASSETS / "v16_option_execution.js").read_text(encoding="utf-8")
        backend = (ROOT / "workstation" / "v16_option_paper.py").read_text(encoding="utf-8")
        http = inspect.getsource(v16_terminal_http)
        self.assertIn('<script src="/v16_option_execution.js"></script>', html)
        self.assertIn("BUY CALL · PAPER", execution)
        self.assertIn("BUY PUT · PAPER", execution)
        self.assertIn("CLOSE LONG POSITION", execution)
        self.assertIn("MANUAL_RISK_LEVELS_REQUIRED", backend)
        self.assertIn("NAKED_SHORT_OPTION_BLOCKED", backend)
        self.assertIn("FYERS_DAILY_SYMBOL_MASTER_EXACT_MATCH", backend)
        self.assertIn("/api/v16/trading/option-order", http)
        self.assertIn("/api/v16/trading/reconciliation", http)
        self.assertIn("live_orders_locked", backend)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, execution + backend + http)

    def test_v16_http_boundary_absorbs_aborted_browser_connections(self):
        source = inspect.getsource(v16_terminal_http)
        self.assertIn("ConnectionAbortedError", source)
        self.assertIn("BrokenPipeError", source)
        self.assertIn("live_orders_locked", source)
        self.assertIn("automatic_broker_order", source)

    def test_new_workstation_surface_does_not_add_live_order_calls(self):
        paths = [
            ROOT / "start_jarvis_master_v16.py",
            ROOT / "start_jarvis_v16_workstation.py",
            ROOT / "scripts" / "jarvis_runtime_supervisor_v16.py",
            ROOT / "workstation" / "jarvis_os_v16_bridge.py",
            ROOT / "workstation" / "v16_terminal_http.py",
            ROOT / "workstation" / "v16_option_paper.py",
            ASSETS / "v16_main_trading_runtime.js",
            QUANT_ASSETS / "v16_workspace.js",
            QUANT_ASSETS / "v16_option_execution.js",
        ]
        source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
