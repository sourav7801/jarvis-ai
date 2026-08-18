import json
import unittest
from datetime import datetime, timezone

import pandas as pd

from workstation.paper_market_data import UnifiedPaperMarketData


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.payload if limit < 0 else self.payload[:limit]


class FakeRuntime:
    def snapshot(self, symbol):
        return {"symbol": symbol, "ltp": 100.0}

    def status(self):
        return {"connected": True, "configured": True, "error": None}


class UnifiedPaperMarketDataTests(unittest.TestCase):
    now = staticmethod(lambda: datetime(2026, 8, 17, 5, 0, tzinfo=timezone.utc))

    def test_front_month_contract_comes_from_daily_symbol_master(self):
        master = (
            "1,GOLDM 15 Aug 26 FUT,11,1,1,,,2026-08-15,1786690800,MCX:GOLDM26AUGFUT,11,20,1,GOLDM\n"
            "2,GOLDM 25 Sep 26 FUT,11,1,1,,0900-2330,2026-08-15,1790359200,MCX:GOLDM26SEPFUT,11,20,2,GOLDM\n"
        ).encode()
        data = UnifiedPaperMarketData(
            market_runtime=FakeRuntime(),
            urlopen=lambda *_args, **_kwargs: Response(master),
            now=self.now,
        )
        contract = data._resolve_front_month("GOLDM")
        self.assertEqual(contract["provider_symbol"], "MCX:GOLDM26SEPFUT")
        self.assertIn("Sep", contract["description"])

    def test_friendly_commodity_resolves_to_active_provider_symbol(self):
        master = (
            "1,CRUDEOILM 19 Aug 26 FUT,11,1,1,,0900-2330,2026-08-15,1787083200,MCX:CRUDEOILM26AUGFUT,11,20,1,CRUDEOILM\n"
        ).encode()
        data = UnifiedPaperMarketData(
            market_runtime=FakeRuntime(),
            urlopen=lambda *_args, **_kwargs: Response(master),
            now=self.now,
        )
        contract = data.provider_symbol("CRUDEOIL")
        self.assertEqual(contract["provider_symbol"], "MCX:CRUDEOILM26AUGFUT")
        self.assertEqual(contract["asset_class"], "COMMODITY")

    def test_exact_mcx_option_contract_and_premium_are_verified(self):
        master = (
            "1,CRUDEOIL 17 Sep 26 7900 CE,31,1,0.1,,0900-2330,2026-08-15,1789668000,MCX:CRUDEOIL26SEP7900CE,11,20,1,CRUDEOIL\n"
            "2,CRUDEOIL 17 Sep 26 7900 PE,31,1,0.1,,0900-2330,2026-08-15,1789668000,MCX:CRUDEOIL26SEP7900PE,11,20,2,CRUDEOIL\n"
        ).encode()
        data = UnifiedPaperMarketData(
            market_runtime=FakeRuntime(),
            urlopen=lambda *_args, **_kwargs: Response(master),
            fyers_quote_loader=lambda symbol: {
                "success": symbol == "MCX:CRUDEOIL26SEP7900CE",
                "ltp": 560.0,
                "source": "FYERS",
            },
            now=self.now,
        )
        contract = data.resolve_option_contract(
            "CRUDEOIL", 7900, "CE", "September expiry"
        )
        self.assertEqual(contract["provider_symbol"], "MCX:CRUDEOIL26SEP7900CE")
        self.assertEqual(contract["option_type"], "CE")
        quote = data.quote(contract["provider_symbol"], use_cache=False)
        self.assertTrue(quote["success"])
        self.assertEqual(quote["valuation_ltp"], 560.0)
        self.assertEqual(quote["asset_class"], "OPTION")

    def test_crypto_quote_is_public_and_valued_in_inr(self):
        currency_master = (
            "1,USDINR 27 Aug 26 FUT,16,1,0.0025,,0900-1700,2026-08-15,1787814000,NSE:USDINR26AUGFUT,10,12,1,USDINR\n"
        ).encode()
        ticker = json.dumps(
            {
                "lastPrice": "64000",
                "priceChange": "1000",
                "priceChangePercent": "1.5",
                "highPrice": "65000",
                "lowPrice": "62000",
                "volume": "100",
                "closeTime": 1,
            }
        ).encode()

        def opener(request, **_kwargs):
            return Response(currency_master if "NSE_CD.csv" in request.full_url else ticker)

        data = UnifiedPaperMarketData(
            market_runtime=FakeRuntime(),
            urlopen=opener,
            fyers_quote_loader=lambda _symbol: {"success": True, "ltp": 90.0},
            now=self.now,
        )
        quote = data.quote("BTC", use_cache=False)
        self.assertTrue(quote["success"])
        self.assertEqual(quote["native_ltp"], 64000.0)
        self.assertEqual(quote["valuation_ltp"], 5_760_000.0)
        self.assertEqual(quote["asset_class"], "CRYPTO")
        self.assertEqual(quote["source"], "BINANCE_PUBLIC")

    def test_crypto_history_normalizes_public_klines(self):
        rows = []
        for index in range(80):
            rows.append([1_780_000_000_000 + index * 300_000, "100", "102", "99", "101", "10"])
        data = UnifiedPaperMarketData(
            market_runtime=FakeRuntime(),
            urlopen=lambda *_args, **_kwargs: Response(json.dumps(rows).encode()),
            now=self.now,
        )
        result = data.history("ETH", timeframe="5m", bars=80)
        self.assertTrue(result["success"])
        self.assertEqual(result["data_quality"], "PUBLIC_SPOT_OHLCV")
        self.assertEqual(len(result["data"]), 80)
        self.assertIsInstance(result["data"], pd.DataFrame)

    def test_market_sessions_are_asset_specific(self):
        data = UnifiedPaperMarketData(market_runtime=FakeRuntime(), now=self.now)
        self.assertTrue(data.session_open("NIFTY"))
        self.assertTrue(data.session_open("GOLD"))
        self.assertTrue(data.session_open("BTC"))
        self.assertFalse(hasattr(data, "place_order"))


if __name__ == "__main__":
    unittest.main()
