from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import jarvis_runtime_supervisor_v62 as v62


ROOT = Path(__file__).resolve().parents[1]


class RuntimeSupervisorV62Tests(unittest.TestCase):
    def test_required_quant_surface_includes_restored_routes(self):
        self.assertIn("/intelligence.html", v62.REQUIRED_QUANT_PATHS)
        self.assertIn("/lightweight-charts.standalone.production.js", v62.REQUIRED_QUANT_PATHS)
        self.assertIn("/adaptive_brain_runtime.js", v62.REQUIRED_QUANT_PATHS)

    def test_quant_surface_rejects_missing_intelligence_route(self):
        def fake_http(url: str, timeout: float = 1.5):
            if url.endswith("/api/health"):
                return 200, b'{"service":"JARVIS_QUANT_TERMINAL","version":"5.0"}'
            if url.endswith("/intelligence.html"):
                return 404, b"not found"
            return 200, b"ok"

        with patch.object(v62, "_http", side_effect=fake_http):
            status = v62.quant_surface_status()
        self.assertFalse(status["current"])
        self.assertEqual(status["routes"]["/intelligence.html"], 404)

    def test_quant_surface_accepts_complete_route_contract(self):
        def fake_http(url: str, timeout: float = 1.5):
            if url.endswith("/api/health"):
                return 200, b'{"service":"JARVIS_QUANT_TERMINAL","version":"6.2"}'
            return 200, b"ok"

        with patch.object(v62, "_http", side_effect=fake_http):
            status = v62.quant_surface_status()
        self.assertTrue(status["current"])

    def test_trusted_process_requires_jarvis_root(self):
        self.assertTrue(
            v62._trusted_jarvis_process(
                {
                    "ExecutablePath": r"C:\Jarvis\.venv\Scripts\python.exe",
                    "CommandLine": r'python C:\Jarvis\start_jarvis_quant_terminal.py',
                }
            )
        )
        self.assertFalse(
            v62._trusted_jarvis_process(
                {
                    "ExecutablePath": r"C:\OtherApp\python.exe",
                    "CommandLine": r"python server.py",
                }
            )
        )

    def test_launcher_uses_v62_supervisor(self):
        source = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        self.assertIn("jarvis_runtime_supervisor_v62.py", source)

    def test_wrapper_has_no_live_order_surface(self):
        source = (ROOT / "scripts" / "jarvis_runtime_supervisor_v62.py").read_text(encoding="utf-8")
        for forbidden in ("place_order(", "modify_order(", "cancel_order(", "submit_order("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
