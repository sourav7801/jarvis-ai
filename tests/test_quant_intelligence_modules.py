import unittest
from unittest.mock import patch

from workstation.quant_intelligence_modules import intelligence_module_payload


class QuantIntelligenceModuleTests(unittest.TestCase):
    @patch("workstation.india_options_intelligence.option_chain_snapshot")
    def test_option_chain_uses_verified_provider_result(self, snapshot):
        snapshot.return_value = {
            "success": True,
            "provider": "FYERS_READ_ONLY",
            "chain": [{"strike": 25000, "option_type": "CE", "open_interest": 100}],
            "chain_analytics": {"pcr_oi": 1.1},
            "paper_only": True,
            "live_execution": False,
        }
        payload = intelligence_module_payload("option-chain", "NIFTY")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["module"], "option-chain")
        self.assertEqual(payload["provider"], "FYERS_READ_ONLY")
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])
        snapshot.assert_called_once_with("NIFTY", expiry=None)

    @patch("workstation.crypto_options_intelligence.option_chain_snapshot")
    def test_bitcoin_option_chain_uses_public_deribit_bulk_snapshot(self, snapshot):
        snapshot.return_value = {
            "success": True,
            "provider": "DERIBIT_PUBLIC",
            "symbol": "BTC",
            "expiry": "2026-09-04",
            "available_expiries": ["2026-09-04", "2026-09-11"],
            "chain": [{"symbol": "BTC-4SEP26-80000-C", "strike": 80000, "option_type": "CE"}],
            "chain_analytics": {"contract_count": 1},
            "paper_only": True,
            "live_execution": False,
        }

        payload = intelligence_module_payload(
            "option-chain", "BTC", expiry="2026-09-04"
        )

        snapshot.assert_called_once_with("BTC", expiry="2026-09-04")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider"], "DERIBIT_PUBLIC")
        self.assertEqual(payload["chain"][0]["strike"], 80000)

    @patch("workstation.india_options_intelligence.option_chain_snapshot")
    def test_mcx_option_chain_routes_to_verified_fyers_contract(self, snapshot):
        snapshot.return_value = {
            "success": True,
            "provider": "FYERS_READ_ONLY",
            "symbol": "CRUDEOIL",
            "provider_symbol": "MCX:CRUDEOILM26SEPFUT",
            "expiry": {"date": "17-09-2026"},
            "available_expiries": ["2026-09-17"],
            "chain": [{"strike": 7900, "option_type": "CE", "open_interest": 120}],
            "paper_only": True,
            "live_execution": False,
        }

        payload = intelligence_module_payload(
            "oi-iv", "CRUDEOIL", expiry="2026-09-17"
        )

        snapshot.assert_called_once_with("CRUDEOIL", expiry="2026-09-17")
        self.assertTrue(payload["success"])
        self.assertEqual(payload["provider_symbol"], "MCX:CRUDEOILM26SEPFUT")

    @patch("workstation.quant_terminal_v2.scan_payload")
    def test_structure_and_fvg_return_real_feature_evidence(self, scan):
        scan.return_value = {
            "success": True,
            "symbol": "NIFTY",
            "evidence": [{
                "timeframe": "5m",
                "features": {
                    "success": True,
                    "structure": {"bias": "BULLISH", "bos": True},
                    "liquidity": {"fair_value_gaps": [{"side": "BULLISH"}]},
                    "patterns": {"patterns": [{"name": "FLAG"}]},
                },
            }],
            "paper_only": True,
            "live_execution": False,
        }
        structure = intelligence_module_payload("structure", "NIFTY")
        fvg = intelligence_module_payload("fvg", "NIFTY")
        self.assertEqual(structure["timeframes"][0]["structure"]["bias"], "BULLISH")
        self.assertEqual(fvg["timeframes"][0]["fair_value_gaps"][0]["side"], "BULLISH")

    @patch("workstation.multi_market_scanner.MULTI_MARKET_SCANNER.status")
    def test_heatmap_filters_selected_universe_without_inventing_quotes(self, status):
        status.return_value = {
            "success": True,
            "results": [
                {"symbol": "HDFCBANK", "universes": ["BANKNIFTY"], "success": True,
                 "direction": "BEARISH", "score": 72, "percent_change": -1.2},
                {"symbol": "RELIANCE", "universes": ["NIFTY50"], "success": True,
                 "direction": "BULLISH", "score": 78, "percent_change": 0.8},
            ],
            "paper_only": True,
            "live_execution": False,
        }
        payload = intelligence_module_payload("heatmaps", "NIFTY", universe="BANKNIFTY")
        self.assertEqual([row["symbol"] for row in payload["rows"]], ["HDFCBANK"])
        self.assertEqual(payload["source"], "MULTI_MARKET_SCANNER_COMPLETED_BARS")

    def test_unknown_module_fails_closed(self):
        payload = intelligence_module_payload("magic", "NIFTY")
        self.assertFalse(payload["success"])
        self.assertTrue(payload["paper_only"])
        self.assertFalse(payload["live_execution"])


if __name__ == "__main__":
    unittest.main()
