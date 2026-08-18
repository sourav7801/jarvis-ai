import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    CanonicalFyersProvider,
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.market_data_gateway import (
    MarketDataGateway,
)


class FakeProvider:

    def get_quote(
        self,
        symbol,
    ):

        return {
            "success":
                True,

            "symbol":
                symbol,

            "ltp":
                100.0,
        }


    def get_intraday_data(
        self,
        symbol,
        market="NSE",
        timeframe="5m",
        bars=10,
    ):

        return {
            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "bars":
                bars,
        }


    def place_order(
        self,
        payload,
    ):

        raise AssertionError(
            "Must never execute."
        )


class FyersBridgeTests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_canonical_provider_discovered(
        self,
    ):

        adapter = (
            FyersReadOnlyAdapter()
        )


        self.assertTrue(
            adapter
            .canonical_available()
        )


    def test_canonical_capabilities(
        self,
    ):

        capabilities = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        self.assertEqual(
            capabilities[
                "quote"
            ],
            "get_quote",
        )


        self.assertEqual(
            capabilities[
                "history"
            ],
            "get_intraday_data",
        )


    def test_no_fake_option_chain(
        self,
    ):

        capabilities = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        self.assertIsNone(
            capabilities[
                "option_chain"
            ]
        )


        self.assertIsNone(
            capabilities[
                "market_depth"
            ]
        )


    def test_explicit_provider_quote(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        result = adapter.quote(
            "NIFTY"
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


    def test_explicit_provider_history(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        result = adapter.history(
            "NIFTY",
            market="NSE",
            timeframe="5m",
            bars=50,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertEqual(
            result[
                "bars"
            ],
            50,
        )


    def test_order_attribute_blocked(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        with self.assertRaises(
            PermissionError
        ):

            adapter.place_order


    def test_gateway_bridge(
        self,
    ):

        gateway = (
            MarketDataGateway()
        )


        adapter = gateway.ensure_fyers(
            FakeProvider()
        )


        self.assertEqual(
            adapter.capabilities()[
                "quote"
            ],
            "get_quote",
        )


    def test_public_bridge_status(
        self,
    ):

        status = (
            main.jarvis_fyers_bridge_status()
        )


        self.assertTrue(
            status[
                "canonical_provider_available"
            ]
        )


        self.assertEqual(
            status[
                "quote_function"
            ],
            "get_quote",
        )


        self.assertEqual(
            status[
                "history_function"
            ],
            "get_intraday_data",
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_trading_status_bridge(
        self,
    ):

        status = (
            main.jarvis_trading_v1_status()
        )


        capabilities = status[
            "fyers_discovered_capabilities"
        ]


        self.assertEqual(
            capabilities[
                "quote"
            ],
            "get_quote",
        )


        self.assertEqual(
            capabilities[
                "history"
            ],
            "get_intraday_data",
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


if __name__ == "__main__":

    unittest.main()
