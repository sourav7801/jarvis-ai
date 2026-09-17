from pathlib import Path
import unittest

from workstation.v17_autonomous_options import option_execution_capability
from workstation.v17_crypto_paper_lane import crypto_paper_lane
from workstation.v17_mcx_paper_lane import (
    ADAPTIVE_AUTHORITY,
    MCX_PAPER_UNIVERSE,
    mcx_paper_lane,
)


class V17CrossMarketPaperTests(unittest.TestCase):
    def test_verified_indian_option_underlyings_remain_enabled(self):
        for symbol in ("NIFTY", "BANKNIFTY", "SENSEX"):
            capability = option_execution_capability(symbol)
            self.assertTrue(capability["auto_paper"], symbol)
            self.assertTrue(capability["paper_only"], symbol)
            self.assertFalse(capability["live_execution"], symbol)
        mcx_options = option_execution_capability("MCX_OPTIONS")
        self.assertFalse(mcx_options["auto_paper"])
        self.assertIn("MCX", mcx_options["reason"])

    def test_mcx_lane_uses_canonical_adaptive_paper_authority(self):
        self.assertEqual(MCX_PAPER_UNIVERSE, ("CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"))
        status = mcx_paper_lane.status()
        self.assertEqual(status["service"], "JARVIS_V17_CANONICAL_MCX_UNDERLYING_PAPER")
        self.assertEqual(status["qualification_authority"], ADAPTIVE_AUTHORITY)
        self.assertTrue(status["adaptive_policy_version"])
        self.assertTrue(status["canonical_paper_desk"])
        self.assertFalse(status["separate_mcx_ledger"])
        self.assertFalse(status["mcx_options_execution"])
        self.assertTrue(status["paper_only"])
        self.assertFalse(status["live_execution"])
        self.assertFalse(status["automatic_broker_order"])

    def test_one_touch_crypto_status_carries_mcx_lane_without_second_http_control_plane(self):
        status = crypto_paper_lane.status()
        self.assertTrue(status["mcx_lane_attached"])
        mcx = status["mcx_underlying_paper"]
        self.assertEqual(mcx["service"], "JARVIS_V17_CANONICAL_MCX_UNDERLYING_PAPER")
        self.assertTrue(mcx["canonical_paper_desk"])
        self.assertFalse(mcx["live_execution"])

    def test_cross_market_browser_monitor_declares_all_three_surfaces(self):
        text = Path("workstation/quant_terminal_v2_static/v17_crypto_paper_runtime.js").read_text(encoding="utf-8")
        self.assertIn("INDIAN INDEX OPTIONS", text)
        self.assertIn("MCX UNDERLYING/FUTURES PAPER", text)
        self.assertIn("CRYPTO UNDERLYING PAPER", text)
        self.assertIn("/api/v16/trading/workspace-state?workspace=INTRADAY", text)
        self.assertIn("mcx_underlying_paper", text)
        self.assertIn("MCX options disabled", text)


if __name__ == "__main__":
    unittest.main()
