import threading
import time
import unittest

from workstation.terminal_data import scan_rows


class V17ScanSchedulerTests(unittest.TestCase):
    def test_completed_peer_is_yielded_before_slow_first_submission(self):
        cancelled = threading.Event()

        def analyze(symbol):
            if symbol == "SLOW":
                time.sleep(0.20)
            else:
                time.sleep(0.02)
            return {"success": True, "symbol": symbol}

        started = time.monotonic()
        rows = list(
            scan_rows(
                analyze,
                ("SLOW", "FAST", "THIRD"),
                cancelled,
                timeout_seconds=2.0,
                max_in_flight=2,
            )
        )
        elapsed = time.monotonic() - started

        symbols = [row.get("symbol") for row in rows]
        self.assertEqual(symbols[0], "FAST")
        self.assertCountEqual(symbols, ["SLOW", "FAST", "THIRD"])
        self.assertLess(elapsed, 0.6)

    def test_scheduler_keeps_timeout_fail_closed(self):
        text = __import__("pathlib").Path("workstation/terminal_data.py").read_text(encoding="utf-8")
        self.assertIn('"message": "ANALYSIS_TIMEOUT"', text)
        self.assertIn("SCAN_ROW_MAX_IN_FLIGHT = 2", text)
        self.assertIn("SCAN_ROW_TIMEOUT_SECONDS = 75.0", text)


if __name__ == "__main__":
    unittest.main()
