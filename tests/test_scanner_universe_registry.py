from __future__ import annotations

import json
from pathlib import Path
import unittest

from workstation.scanner_universe_registry import (
    BANKNIFTY_CONSTITUENTS_URL,
    ScannerUniverseRegistry,
    scanner_universe_registry,
)


class ScannerUniverseRegistryTests(unittest.TestCase):
    def test_offline_catalog_covers_requested_market_families(self):
        registry = scanner_universe_registry(["NSE:DMART", {"symbol": "PIDILITIND", "label": "Pidilite"}])

        self.assertFalse(registry["live_execution"])
        self.assertEqual(registry["guardrails"]["broker_order_api"], "NOT_PRESENT")
        self.assertEqual(
            set(registry["universes"]),
            {
                "INDIA_INDICES", "NIFTY50", "BANKNIFTY", "SENSEX30",
                "INDIA_CONFIGURED", "GLOBAL_MAJOR", "CRYPTO_MAJOR", "MCX_MAJOR",
            },
        )
        self.assertEqual(registry["universes"]["NIFTY50"]["count"], 50)
        self.assertEqual(registry["universes"]["BANKNIFTY"]["count"], 12)
        self.assertEqual(registry["universes"]["SENSEX30"]["count"], 30)
        configured = registry["universes"]["INDIA_CONFIGURED"]["instruments"]
        self.assertEqual({row["symbol"] for row in configured}, {"DMART", "PIDILITIND"})

    def test_every_instrument_has_normalized_provenance_session_and_gate(self):
        registry = scanner_universe_registry(["BSE:500325"])
        for universe in registry["universes"].values():
            for instrument in universe["instruments"]:
                self.assertTrue(instrument["asset_class"])
                self.assertTrue(instrument["provenance"])
                self.assertTrue(instrument["data_quality"])
                self.assertTrue(instrument["eligibility_gate"])
                self.assertTrue(instrument["session"]["timezone"])
                self.assertIsInstance(instrument["auto_paper_eligible"], bool)

    def test_global_delayed_feed_fails_closed_for_automatic_paper(self):
        global_snapshot = ScannerUniverseRegistry.global_equities()
        self.assertTrue(global_snapshot.instruments)
        for instrument in global_snapshot.instruments:
            self.assertFalse(instrument.auto_paper_eligible)
            self.assertEqual(instrument.data_quality, "UNOFFICIAL_DELAYED")
            self.assertIn("BLOCKED", instrument.eligibility_gate)

    def test_crypto_is_24x7_but_synthetic_paper_only(self):
        crypto = ScannerUniverseRegistry.crypto()
        btc = next(row for row in crypto.instruments if row.symbol == "BTC")
        self.assertTrue(btc.session.continuous)
        self.assertEqual(len(btc.session.trading_days), 7)
        self.assertTrue(btc.auto_paper_eligible)
        self.assertIn("SYNTHETIC_PAPER_ONLY", btc.eligibility_gate)

    def test_banknifty_official_loader_and_malformed_fallback(self):
        rows = ["Company Name,Industry,Symbol,Series,ISIN Code"]
        rows.extend(f"Bank {number},Financial Services,BANK{number},EQ,INE{number}" for number in range(12))
        official_text = "\n".join(rows)
        seen = []

        def loader(url):
            seen.append(url)
            return official_text

        official = ScannerUniverseRegistry().banknifty(loader)
        self.assertEqual(seen, [BANKNIFTY_CONSTITUENTS_URL])
        self.assertTrue(official.official_runtime)
        self.assertEqual(len(official.instruments), 12)
        self.assertEqual(official.instruments[0].provider_symbol, "NSE:BANK0-EQ")

        fallback = ScannerUniverseRegistry().banknifty(lambda _url: "bad,data")
        self.assertFalse(fallback.official_runtime)
        self.assertEqual(fallback.source_mode, "OFFICIAL_SNAPSHOT_FALLBACK")
        self.assertEqual(len(fallback.instruments), 12)

    def test_sensex_official_json_requires_exactly_30_tradable_symbols(self):
        payload = {
            "Table": [
                {"symbol": f"BSE{number}", "companyname": f"Company {number}"}
                for number in range(30)
            ]
        }
        official = ScannerUniverseRegistry().sensex30(lambda _url: json.dumps(payload))
        self.assertTrue(official.official_runtime)
        self.assertEqual(len(official.instruments), 30)
        self.assertEqual(official.instruments[0].exchange, "BSE")

        numeric_only = {"Table": [{"scrip_cd": str(number)} for number in range(30)]}
        fallback = ScannerUniverseRegistry().sensex30(lambda _url: json.dumps(numeric_only))
        self.assertEqual(fallback.source_mode, "OFFICIAL_SNAPSHOT_FALLBACK")

    def test_module_contains_no_live_order_capability(self):
        source = (Path(__file__).parents[1] / "workstation" / "scanner_universe_registry.py").read_text(encoding="utf-8")
        self.assertNotIn("place_order", source.lower())
        self.assertNotIn("submit_order", source.lower())
        self.assertNotIn("access_token", source.lower())


if __name__ == "__main__":
    unittest.main()
