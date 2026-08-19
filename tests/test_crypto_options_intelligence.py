from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from workstation.crypto_options_intelligence import option_command_payload, parse_option_request


class CryptoOptionsIntelligenceTests(unittest.TestCase):
    def test_exact_runtime_phrase_is_parsed(self):
        request = parse_option_request(
            "can i buy bitcoin 69000 option tomorrow expiry",
            today=date(2026, 8, 19),
        )
        self.assertIsNotNone(request)
        self.assertEqual(request.underlying, "BTC")
        self.assertEqual(request.strike, 69000.0)
        self.assertEqual(request.expiry_date, "2026-08-20")
        self.assertIsNone(request.option_type)
        self.assertTrue(request.buy_requested)

    def test_call_and_put_are_explicit(self):
        call = parse_option_request("buy BTC 69000 call tomorrow", today=date(2026, 8, 19))
        put = parse_option_request("buy BTC 69000 put tomorrow", today=date(2026, 8, 19))
        self.assertEqual(call.option_type, "call")
        self.assertEqual(put.option_type, "put")

    @patch("workstation.crypto_options_intelligence._ticker")
    @patch("workstation.crypto_options_intelligence._instruments")
    def test_ambiguous_call_put_does_not_execute(self, instruments, ticker):
        instruments.return_value = [
            {
                "instrument_name": "BTC-20AUG26-69000-C",
                "expiration_timestamp": 1787193600000,
                "strike": 69000,
                "option_type": "call",
                "contract_size": 1,
                "min_trade_amount": 0.1,
            },
            {
                "instrument_name": "BTC-20AUG26-69000-P",
                "expiration_timestamp": 1787193600000,
                "strike": 69000,
                "option_type": "put",
                "contract_size": 1,
                "min_trade_amount": 0.1,
            },
        ]
        ticker.return_value = {
            "mark_price": 0.01,
            "underlying_price": 68800,
            "mark_iv": 55,
            "best_bid_price": 0.009,
            "best_ask_price": 0.011,
            "open_interest": 10,
            "greeks": {},
            "state": "open",
        }
        result = option_command_payload(
            "can i buy bitcoin 69000 option tomorrow expiry",
            today=date(2026, 8, 19),
        )
        self.assertIsNone(result["paper_intent"])
        self.assertIn("call versus put is ambiguous", result["speech"].lower())
        self.assertFalse(result["live_execution"])

    @patch("workstation.crypto_options_intelligence._journal")
    @patch("workstation.crypto_options_intelligence._ticker")
    @patch("workstation.crypto_options_intelligence._instruments")
    def test_explicit_call_creates_paper_intent_only(self, instruments, ticker, journal):
        instruments.return_value = [
            {
                "instrument_name": "BTC-20AUG26-69000-C",
                "expiration_timestamp": 1787193600000,
                "strike": 69000,
                "option_type": "call",
                "contract_size": 1,
                "min_trade_amount": 0.1,
            }
        ]
        ticker.return_value = {
            "mark_price": 0.002,
            "underlying_price": 68800,
            "mark_iv": 55,
            "best_bid_price": 0.0019,
            "best_ask_price": 0.0021,
            "open_interest": 10,
            "greeks": {"delta": 0.5},
            "state": "open",
        }
        result = option_command_payload(
            "buy bitcoin 69000 call tomorrow",
            today=date(2026, 8, 19),
        )
        self.assertIsNotNone(result["paper_intent"])
        self.assertEqual(result["paper_intent"]["status"], "PAPER_OPTION_INTENT")
        self.assertFalse(result["paper_intent"]["live_execution"])
        journal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
