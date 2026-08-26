from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.options_chain_analytics import analyze_chain, normalize_contracts
from workstation.india_options_intelligence import analyze_india_option_request


class OptionsChainAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"symbol": "C95", "strike_price": 95, "option_type": "CE", "bid": 7, "ask": 7.2, "oi": 100, "oich": 5, "volume": 30, "greeks": {"iv": 20, "delta": 0.70, "gamma": 0.02}},
            {"symbol": "P95", "strike_price": 95, "option_type": "PE", "bid": 1.8, "ask": 2, "oi": 200, "oich": 8, "volume": 40, "greeks": {"iv": 23, "delta": -0.25, "gamma": 0.02}},
            {"symbol": "C100", "strike_price": 100, "option_type": "CE", "bid": 4.9, "ask": 5.1, "oi": 500, "oich": 20, "volume": 100, "greeks": {"iv": 19, "delta": 0.50, "gamma": 0.04}},
            {"symbol": "P100", "strike_price": 100, "option_type": "PE", "bid": 4.8, "ask": 5, "oi": 700, "oich": 25, "volume": 120, "greeks": {"iv": 22, "delta": -0.50, "gamma": 0.04}},
            {"symbol": "C105", "strike_price": 105, "option_type": "CE", "bid": 1.9, "ask": 2.1, "oi": 800, "oich": 30, "volume": 90, "greeks": {"iv": 18, "delta": 0.25, "gamma": 0.02}},
            {"symbol": "P105", "strike_price": 105, "option_type": "PE", "bid": 7, "ask": 7.3, "oi": 300, "oich": 9, "volume": 35, "greeks": {"iv": 24, "delta": -0.70, "gamma": 0.02}},
        ]

    def test_normalization_preserves_provider_values_and_missing_values(self):
        rows = normalize_contracts(self.rows, underlying="NIFTY", provider="TEST", expiry="2026-08-27")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0].provider, "TEST")
        self.assertEqual(rows[0].expiry, "2026-08-27")
        self.assertIsNone(rows[0].theta)
        self.assertAlmostEqual(rows[0].spread, 0.2)

    def test_chain_analytics_are_descriptive_and_paper_only(self):
        rows = normalize_contracts(self.rows, underlying="NIFTY", provider="TEST", expiry="2026-08-27")
        result = analyze_chain(rows, spot=100, received_at="2026-08-26T10:00:00Z")
        self.assertAlmostEqual(result["pcr_oi"], 1200 / 1400)
        self.assertEqual(result["call_oi_wall"]["strike"], 105)
        self.assertEqual(result["put_oi_wall"]["strike"], 100)
        self.assertIsNotNone(result["max_pain"])
        self.assertTrue(result["max_pain"]["descriptive_only"])
        self.assertAlmostEqual(result["expected_move"]["amount"], 9.9)
        self.assertEqual(result["skew_25_delta"]["put_minus_call_iv"], 5)
        self.assertTrue(result["gamma_concentration"])
        self.assertTrue(result["descriptive_not_predictive"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])

    def test_missing_chain_fields_are_not_fabricated(self):
        rows = normalize_contracts(
            [{"symbol": "C100", "strike": 100, "option_type": "call", "ltp": 5}],
            underlying="BTC",
            provider="TEST",
        )
        result = analyze_chain(rows, spot=100)
        self.assertIsNone(result["pcr_oi"])
        self.assertIsNone(result["max_pain"])
        self.assertIsNone(result["expected_move"])
        self.assertIsNone(result["skew_25_delta"])
        self.assertEqual(result["gamma_concentration"], [])

    def test_invalid_non_contract_rows_are_excluded(self):
        rows = normalize_contracts(
            [{"strike": 100, "option_type": ""}, {"strike": None, "option_type": "CE"}],
            underlying="NIFTY",
            provider="TEST",
        )
        result = analyze_chain(rows, spot=100)
        self.assertFalse(result["success"])
        self.assertEqual(result["contract_count"], 0)

    @patch("workstation.india_options_intelligence.fetch_option_chain")
    def test_india_adapter_exposes_normalized_chain_and_analytics(self, fetch):
        fetch.side_effect = [
            {"data": {"expiryData": [{"expiry": 123, "date": "27-08-2026"}]}},
            {
                "data": {
                    "optionsChain": [
                        {"option_type": "", "ltp": 100},
                        *self.rows,
                    ],
                    "callOi": 1400,
                    "putOi": 1200,
                }
            },
        ]
        result = analyze_india_option_request("analyze NIFTY 100 call option")
        self.assertEqual(len(result["chain"]), 6)
        self.assertTrue(result["chain_analytics"]["success"])
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
