from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.v17_crypto_paper_lane import (
    CRYPTO_PAPER_UNIVERSE,
    crypto_paper_lane,
)


class _Runtime:
    def control(self, workspace, action):
        return {"success": True, "state": "RUNNING" if action == "start" else "PAUSED", "workspace": workspace}


class _CryptoLane:
    def start(self):
        return {
            "success": True,
            "running": True,
            "state": "RUNNING",
            "universe": ["BTC", "ETH", "SOL"],
            "paper_only": True,
            "live_execution": False,
            "deribit_options_execution": False,
        }

    def stop_new_entries(self):
        return {"success": True, "running": False, "state": "PAUSED", "paper_only": True, "live_execution": False}

    def status(self):
        return self.start()


class V17CryptoUnderlyingPaperTests(unittest.TestCase):
    def test_lane_is_crypto_underlying_only_and_canonical_paper(self):
        self.assertEqual(CRYPTO_PAPER_UNIVERSE, ("BTC", "ETH", "SOL"))
        self.assertEqual(tuple(crypto_paper_lane.engine.universe), CRYPTO_PAPER_UNIVERSE)
        self.assertFalse(crypto_paper_lane.engine.manage_marks)
        status = crypto_paper_lane.status()
        self.assertTrue(status["canonical_paper_desk"])
        self.assertFalse(status["separate_crypto_ledger"])
        self.assertTrue(status["deribit_options_research_only"])
        self.assertFalse(status["deribit_options_execution"])
        self.assertTrue(status["paper_only"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])

    def test_one_touch_start_includes_crypto_underlying_lane(self):
        from workstation import v17_terminal_http as http

        preferences = {
            "start_workspaces": ["INTRADAY", "SWING", "INVESTMENT"],
            "options_capital_fraction": 0.50,
            "one_touch_autopilot": True,
            "chart_first_options": True,
            "learning_enabled": True,
        }
        with patch.object(http, "load_preferences", return_value=preferences), patch.object(
            http, "crypto_paper_lane", _CryptoLane()
        ):
            result = http._autopilot_control(_Runtime(), {"action": "start"})
        self.assertTrue(result["success"])
        self.assertIn("CRYPTO_UNDERLYING", result["results"])
        self.assertEqual(result["states"]["CRYPTO_UNDERLYING"], "RUNNING")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["automatic_broker_order"])

    def test_one_touch_stop_pauses_crypto_new_entries(self):
        from workstation import v17_terminal_http as http

        preferences = {
            "start_workspaces": ["INTRADAY", "SWING", "INVESTMENT"],
            "options_capital_fraction": 0.50,
            "one_touch_autopilot": True,
            "chart_first_options": True,
            "learning_enabled": True,
        }
        with patch.object(http, "load_preferences", return_value=preferences), patch.object(
            http, "crypto_paper_lane", _CryptoLane()
        ):
            result = http._autopilot_control(_Runtime(), {"action": "stop"})
        self.assertTrue(result["success"])
        self.assertEqual(result["states"]["CRYPTO_UNDERLYING"], "PAUSED")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
