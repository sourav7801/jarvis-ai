from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from workstation.india_options_intelligence import (
    analyze_india_option_request,
    parse_india_option_request,
)


class IndiaOptionsIntelligenceTests(unittest.TestCase):
    def test_parse_nifty_call_tomorrow(self):
        request = parse_india_option_request(
            "analyze nifty 24500 call tomorrow expiry",
            today=date(2026, 8, 19),
        )
        self.assertIsNotNone(request)
        self.assertEqual(request.underlying, "NIFTY")
        self.assertEqual(request.strike, 24500)
        self.assertEqual(request.option_type, "CE")
        self.assertEqual(request.expiry_date, "2026-08-20")

    def test_parse_banknifty_put(self):
        request = parse_india_option_request(
            "paper buy bank nifty 57000 put next expiry",
            today=date(2026, 8, 19),
        )
        self.assertEqual(request.underlying, "BANKNIFTY")
        self.assertEqual(request.option_type, "PE")
        self.assertTrue(request.paper_requested)
        self.assertTrue(request.buy_requested)

    @patch("workstation.india_options_intelligence.fetch_option_chain")
    def test_ambiguous_call_put_never_creates_intent(self, fetch):
        fetch.side_effect = [
            {
                "s": "ok",
                "data": {
                    "expiryData": [
                        {"date": "20-08-2026", "expiry": "1787184000", "expiry_flag": "W"}
                    ],
                    "optionsChain": [],
                },
            },
            {
                "s": "ok",
                "data": {
                    "callOi": 1000,
                    "putOi": 900,
                    "optionsChain": [
                        {"option_type": "", "strike_price": -1, "ltp": 24500},
                        {"symbol": "NSE:NIFTYTESTCE", "option_type": "CE", "strike_price": 24500, "ltp": 120, "bid": 119, "ask": 121, "oi": 100, "oich": 5, "volume": 500, "greeks": {"iv": 12, "delta": .5, "gamma": .01, "theta": -5, "vega": 7}},
                        {"symbol": "NSE:NIFTYTESTPE", "option_type": "PE", "strike_price": 24500, "ltp": 110, "bid": 109, "ask": 111, "oi": 120, "oich": 8, "volume": 450, "greeks": {"iv": 13, "delta": -.5, "gamma": .01, "theta": -5, "vega": 7}},
                    ],
                },
            },
        ]
        result = analyze_india_option_request(
            "paper buy nifty 24500 option tomorrow expiry"
        )
        self.assertEqual(result["risk_gate"], "OPTION_TYPE_REQUIRED")
        self.assertIsNone(result["paper_intent"])
        self.assertFalse(result["live_execution"])

    @patch("workstation.india_options_intelligence.fetch_option_chain")
    def test_naked_short_option_is_blocked(self, fetch):
        fetch.side_effect = [
            {"s": "ok", "data": {"expiryData": [{"date": "20-08-2026", "expiry": "1787184000", "expiry_flag": "W"}]}},
            {"s": "ok", "data": {"callOi": 1000, "putOi": 900, "optionsChain": [
                {"option_type": "", "strike_price": -1, "ltp": 24500},
                {"symbol": "NSE:NIFTYTESTCE", "option_type": "CE", "strike_price": 24500, "ltp": 120, "bid": 119, "ask": 121, "oi": 100, "oich": 5, "volume": 500, "greeks": {"iv": 12}},
            ]}},
        ]
        result = analyze_india_option_request(
            "paper sell nifty 24500 call tomorrow expiry"
        )
        self.assertEqual(result["risk_gate"], "NAKED_SHORT_OPTION_BLOCKED")
        self.assertIsNone(result["paper_intent"])
        self.assertFalse(result["live_execution"])


if __name__ == "__main__":
    unittest.main()
