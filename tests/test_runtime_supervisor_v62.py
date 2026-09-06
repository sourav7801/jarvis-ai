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

    def test_launcher_preserves_v62_preflight_through_supported_wrapper_chain(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        direct = "-m scripts.jarvis_runtime_supervisor_v62" in launcher
        via_v7 = "-m scripts.jarvis_runtime_supervisor_v7" in launcher
        via_v8 = "-m scripts.jarvis_runtime_supervisor_v8" in launcher
        self.assertTrue(direct or via_v7 or via_v8)
        self.assertNotIn("scripts\\jarvis_runtime_supervisor_v62.py", launcher)

        if via_v7:
            wrapper = (ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py").read_text(encoding="utf-8")
            self.assertIn("reclaim_obsolete_quant_listener", wrapper)
            self.assertIn("scripts.jarvis_runtime_supervisor_v62", wrapper)

        if via_v8:
            v8_wrapper = (ROOT / "scripts" / "jarvis_runtime_supervisor_v8.py").read_text(encoding="utf-8")
            v7_wrapper = (ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py").read_text(encoding="utf-8")
            self.assertIn("reclaim_obsolete_quant_listener", v8_wrapper)
            self.assertIn("v7_services", v8_wrapper)
            self.assertIn("scripts.jarvis_runtime_supervisor_v7", v8_wrapper)
            self.assertIn("scripts.jarvis_runtime_supervisor_v62", v7_wrapper)

    def test_wrapper_chain_has_no_live_order_surface(self):
        paths = [
            ROOT / "scripts" / "jarvis_runtime_supervisor_v62.py",
            ROOT / "scripts" / "jarvis_runtime_supervisor_v7.py",
            ROOT / "scripts" / "jarvis_runtime_supervisor_v8.py",
        ]
        for path in paths:
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            for forbidden in ("place_order(", "modify_order(", "cancel_order(", "submit_order("):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
