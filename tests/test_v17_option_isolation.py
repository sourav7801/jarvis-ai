from concurrent.futures import Future
import unittest

from workstation.v17_option_data_lanes import _SingleLane


class V17OptionIsolationTests(unittest.TestCase):
    def test_different_requests_are_rejected_while_lane_is_busy(self):
        lane = _SingleLane("TestV17OptionLane", workers=1, cache_ttl=5)
        try:
            blocker = Future()
            lane.futures[("A",)] = blocker
            result = lane.request(("B",), lambda: {"ok": True})
            self.assertFalse(result["success"])
            self.assertFalse(result["pending"])
            self.assertEqual(result["reason"], "OPTIONS_DATA_LANE_BUSY")
        finally:
            lane.pool.shutdown(wait=False, cancel_futures=True)

    def test_completed_job_is_handed_to_cache_instead_of_restarted(self):
        lane = _SingleLane("TestV17OptionCache", workers=1, cache_ttl=5)
        try:
            future = Future()
            future.set_result({"success": True, "chain": [{"symbol": "NIFTY"}]})
            lane.futures[("NIFTY",)] = future
            first = lane.request(("NIFTY",), lambda: {"success": False})
            self.assertTrue(first["success"])
            self.assertFalse(first["pending"])
            self.assertFalse(first["cache_hit"])

            second = lane.request(("NIFTY",), lambda: {"success": False})
            self.assertTrue(second["success"])
            self.assertFalse(second["pending"])
            self.assertTrue(second["cache_hit"])
        finally:
            lane.pool.shutdown(wait=False, cancel_futures=True)

    def test_v17_http_contains_isolated_option_routes(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        text = (root / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
        self.assertIn('if parsed.path == "/api/terminal/module" and self._local():', text)
        self.assertIn('module in {"option-chain", "oi-iv"}', text)
        self.assertIn('if parsed.path == "/api/option-candles" and self._local():', text)
        self.assertIn("V17_ISOLATED_OPTION_CHAIN", text)
        self.assertIn("V17_ISOLATED_OPTION_CHART", text)

    def test_status_path_is_read_only(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        text = (root / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
        self.assertIn("control_plane = cross_market_control_plane.status(", text)
        self.assertNotIn("control_plane = cross_market_control_plane.reconcile(", text)


if __name__ == "__main__":
    unittest.main()
