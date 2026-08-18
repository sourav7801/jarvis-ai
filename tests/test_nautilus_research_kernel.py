import importlib.util
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.nautilus_bridge import (
    nautilus_research_bridge,
)


def dataset():

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    bars = []

    signals = []


    for index in range(
        120
    ):

        price = (
            1.1000
            + index
            * 0.00005
        )


        bars.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index
                    ),

                open=
                    price,

                high=
                    price
                    + 0.0004,

                low=
                    price
                    - 0.0004,

                close=
                    price
                    + 0.0001,

                volume=
                    1000,
            )
        )


        signal = "FLAT"


        if index == 25:
            signal = "LONG"

        elif index == 55:
            signal = "EXIT"

        elif index == 70:
            signal = "SHORT"

        elif index == 100:
            signal = "EXIT"


        signals.append(
            signal
        )


    return (
        bars,
        signals,
    )


class NautilusResearchKernelTests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_main_venv_isolated(
        self,
    ):

        self.assertIsNone(
            importlib.util.find_spec(
                "nautilus_trader"
            )
        )


    def test_status(
        self,
    ):

        status = (
            main.jarvis_nautilus_status()
        )


        self.assertTrue(
            status[
                "available"
            ]
        )


        self.assertEqual(
            status[
                "engine"
            ],
            "BacktestEngine",
        )


        self.assertTrue(
            status[
                "isolated_subprocess"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "broker_adapter"
            ]
        )


        self.assertFalse(
            status[
                "trading_node"
            ]
        )


    def test_real_kernel_backtest(
        self,
    ):

        bars, signals = dataset()


        result = (
            main.jarvis_nautilus_backtest(
                bars,
                signals,
                initial_capital=100000,
                quantity=1000,
                timeout=60,
            )
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertEqual(
            result[
                "engine"
            ],
            "BacktestEngine",
        )


        self.assertGreaterEqual(
            result[
                "fill_count"
            ],
            2,
        )


        self.assertTrue(
            result[
                "paper_only"
            ]
        )


        self.assertFalse(
            result[
                "live_execution"
            ]
        )


        self.assertFalse(
            result[
                "broker_adapter"
            ]
        )


    def test_invalid_signal_blocked(
        self,
    ):

        bars, signals = dataset()

        signals[
            10
        ] = "PLACE_LIVE_ORDER"


        with self.assertRaises(
            ValueError
        ):

            nautilus_research_bridge.backtest(
                bars,
                signals,
            )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            nautilus_research_bridge.place_order


    def test_v6_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v6_status()
        )


        self.assertTrue(
            status[
                "paper_only"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


if __name__ == "__main__":

    unittest.main()
