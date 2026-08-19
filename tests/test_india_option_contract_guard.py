from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.india_option_contract_guard import validate_india_option_paper_payload


class IndiaOptionContractGuardTests(unittest.TestCase):
    @patch("workstation.india_option_contract_guard.lot_size", return_value=75)
    def test_validated_one_lot_intent_adds_units(self, _lot):
        payload = {
            "paper_intent": {
                "symbol": "NSE:NIFTYTESTCE",
                "entry_reference": 100.0,
                "quantity_lots": 1,
            },
            "paper_only": True,
            "live_execution": False,
        }
        result = validate_india_option_paper_payload(
            payload,
            equity=100000,
            max_premium_fraction=0.20,
        )
        self.assertEqual(result["risk_gate"], "PAPER_OPTION_INTENT_VALIDATED")
        self.assertEqual(result["paper_intent"]["quantity_units"], 75)
        self.assertEqual(result["paper_intent"]["estimated_premium"], 7500.0)
        self.assertFalse(result["live_execution"])

    @patch("workstation.india_option_contract_guard.lot_size", return_value=None)
    def test_unverified_lot_size_blocks_intent(self, _lot):
        payload = {
            "paper_intent": {
                "symbol": "NSE:NIFTYTESTCE",
                "entry_reference": 100.0,
                "quantity_lots": 1,
            },
            "paper_only": True,
            "live_execution": False,
        }
        result = validate_india_option_paper_payload(payload)
        self.assertIsNone(result["paper_intent"])
        self.assertEqual(result["risk_gate"], "LOT_SIZE_UNVERIFIED")

    @patch("workstation.india_option_contract_guard.lot_size", return_value=75)
    def test_premium_budget_blocks_oversized_one_lot(self, _lot):
        payload = {
            "paper_intent": {
                "symbol": "NSE:NIFTYTESTCE",
                "entry_reference": 400.0,
                "quantity_lots": 1,
            },
            "paper_only": True,
            "live_execution": False,
        }
        result = validate_india_option_paper_payload(
            payload,
            equity=100000,
            max_premium_fraction=0.20,
        )
        self.assertIsNone(result["paper_intent"])
        self.assertEqual(result["risk_gate"], "PREMIUM_BUDGET_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
