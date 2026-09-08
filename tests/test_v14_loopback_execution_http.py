from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
import urllib.request

from workstation.quant_terminal_v14_bridge import QuantTerminalV14Handler


ROOT = Path(__file__).resolve().parents[1]


class V14LoopbackExecutionHttpTests(unittest.TestCase):
    def test_actual_loopback_handler_serves_v14_asset_and_authority(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), QuantTerminalV14Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/v14_execution_runtime.js", timeout=3.0) as response:
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertGreater(len(body), 100)
            with urllib.request.urlopen(base + "/api/v14/execution-authority", timeout=3.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["version"], "14.0")
            self.assertEqual(payload["service"], "JARVIS_QUANT_V14_EXECUTION_AUTHORITY")
            self.assertEqual(
                payload["policy"]["decision_authority"],
                "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
            )
            self.assertFalse(payload["policy"]["arbitrary_confidence_execution_gate"])
            self.assertEqual(payload["policy"]["positive_ev_boundary_r"], 0.0)
            self.assertFalse(payload["live_execution"])
            self.assertFalse(payload["automatic_broker_order"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3.0)


if __name__ == "__main__":
    unittest.main()
