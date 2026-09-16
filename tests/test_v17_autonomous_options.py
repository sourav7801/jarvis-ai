import unittest

from workstation.v17_autonomous_options import (
    OPTION_EXECUTION_CAPABILITIES,
    SAFETY,
    option_execution_capability,
)


class V17AutonomousOptionsTests(unittest.TestCase):
    def test_verified_india_index_options_are_auto_paper_capable(self):
        for underlying in ("NIFTY", "BANKNIFTY", "SENSEX"):
            with self.subTest(underlying=underlying):
                capability = option_execution_capability(underlying)
                self.assertTrue(capability["auto_paper"])
                self.assertTrue(capability["paper_only"])
                self.assertFalse(capability["live_execution"])
                self.assertFalse(capability["automatic_broker_order"])
                self.assertTrue(capability["live_orders_locked"])

    def test_unverified_option_venues_fail_closed(self):
        for underlying in ("MCX_OPTIONS", "CRYPTO_OPTIONS", "UNKNOWN"):
            with self.subTest(underlying=underlying):
                capability = option_execution_capability(underlying)
                self.assertFalse(capability["auto_paper"])
                self.assertFalse(capability["live_execution"])
                self.assertFalse(capability["automatic_broker_order"])
                self.assertTrue(capability["live_orders_locked"])
                self.assertTrue(capability.get("reason"))

    def test_no_forced_trade_quota(self):
        self.assertFalse(SAFETY["forced_trade_quota"])
        self.assertTrue(
            all("auto_paper" in capability for capability in OPTION_EXECUTION_CAPABILITIES.values())
        )


if __name__ == "__main__":
    unittest.main()
