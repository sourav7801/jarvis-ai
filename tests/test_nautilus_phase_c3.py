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

from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


def dataset(
    base,
    step,
    spread,
    count=120,
    *,
    short=True,
):

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
        count
    ):

        wave = (
            (
                index % 15
            )
            - 7
        ) * step * 0.15


        price = (
            base
            + index
            * step
            + wave
        )


        bars.append(
            {
                "timestamp":
                    (
                        start
                        + timedelta(
                            minutes=index
                        )
                    ),

                "open":
                    price,

                "high":
                    price
                    + spread,

                "low":
                    max(
                        0.000001,
                        price
                        - spread,
                    ),

                "close":
                    price
                    + step
                    / 2,
            }
        )


        signal = "FLAT"


        # Repeated entries ensure each walk-forward
        # segment has independent research evidence.
        cycle = index % 40


        if cycle == 5:

            signal = "LONG"


        elif cycle == 15:

            signal = "EXIT"


        elif (
            short
            and cycle == 22
        ):

            signal = "SHORT"


        elif (
            short
            and cycle == 32
        ):

            signal = "EXIT"


        signals.append(
            signal
        )


    return (
        bars,
        signals,
    )


def portfolio(
    count=120,
):

    equity_bars, equity_signals = (
        dataset(
            100,
            0.10,
            0.50,
            count,
        )
    )


    future_bars, future_signals = (
        dataset(
            75,
            0.05,
            0.30,
            count,
        )
    )


    return {
        "portfolio_venue":
            "SIM",

        "initial_capital":
            250000,

        "execution": {
            "name":
                "ideal"
        },

        "strategies": (
            {
                "slot_id":
                    "equity_alpha",

                "instrument": {
                    "kind":
                        "equity",

                    "symbol":
                        "AAPL",

                    "venue":
                        "SIM",
                },

                "bars":
                    equity_bars,

                "signals":
                    equity_signals,

                "quantity":
                    10,
            },

            {
                "slot_id":
                    "commodity_alpha",

                "instrument": {
                    "kind":
                        "commodity_future",

                    "symbol":
                        "CLZ6",

                    "venue":
                        "SIM",

                    "underlying":
                        "CL",

                    "currency":
                        "USD",

                    "price_increment":
                        "0.01",

                    "multiplier":
                        "1000",

                    "expiration":
                        "2026-11-20T19:30:00Z",
                },

                "bars":
                    future_bars,

                "signals":
                    future_signals,

                "quantity":
                    1,
            },
        ),
    }


class NautilusPhaseC3Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_status(
        self,
    ):

        status = (
            main.jarvis_nautilus_c3_status()
        )


        self.assertTrue(
            status[
                "single_event_driven_engine"
            ]
        )


        self.assertTrue(
            status[
                "multi_instrument"
            ]
        )


        self.assertTrue(
            status[
                "multiple_strategy_instances"
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


    def test_true_portfolio(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        self.assertTrue(
            result[
                "single_engine"
            ]
        )


        self.assertEqual(
            result[
                "strategy_count"
            ],
            2,
        )


        self.assertEqual(
            result[
                "instrument_count"
            ],
            2,
        )


        self.assertGreaterEqual(
            result[
                "fill_count"
            ],
            4,
        )


    def test_correlation(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        self.assertIn(
            "equity_alpha",
            result[
                "correlation"
            ][
                "matrix"
            ],
        )


    def test_concentration(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        concentration = result[
            "concentration"
        ]


        self.assertGreater(
            concentration[
                "total_input_notional_proxy"
            ],
            0,
        )


        self.assertFalse(
            concentration[
                "actual_dynamic_exposure"
            ]
        )


    def test_drawdown_attribution_truthful(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        attribution = (
            result[
                "drawdown_attribution"
            ]
        )


        self.assertTrue(
            attribution[
                "proxy"
            ]
        )


        self.assertFalse(
            attribution[
                "engine_accounting"
            ]
        )


    def test_stress_matrix(
        self,
    ):

        result = (
            main.jarvis_nautilus_execution_stress(
                portfolio(),

                profiles=(
                    {
                        "name":
                            "ideal"
                    },

                    {
                        "name":
                            "one_tick"
                    },
                ),

                timeout=90,
            )
        )


        self.assertEqual(
            result[
                "profile_count"
            ],
            2,
        )


        self.assertFalse(
            result[
                "automatic_profile_selection"
            ]
        )


    def test_walk_forward(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_walk_forward(
                portfolio(
                    120
                ),

                train_size=40,
                validation_size=20,
                test_size=20,
                step=20,
                timeout=90,
            )
        )


        self.assertGreaterEqual(
            result[
                "window_count"
            ],
            3,
        )


        self.assertFalse(
            result[
                "oos_tuning"
            ]
        )


        self.assertFalse(
            result[
                "candidate_reoptimized_on_oos"
            ]
        )


    def test_v5_gate(
        self,
    ):

        result = (
            main.jarvis_nautilus_c3_v5_gate(
                {
                    "recommendation": {
                        "recommendation":
                            "PROMOTE"
                    }
                },

                {
                    "success":
                        True,

                    "oos_pass_rate":
                        0.75,

                    "oos_tuning":
                        False,

                    "candidate_reoptimized_on_oos":
                        False,
                },
            )
        )


        self.assertEqual(
            result[
                "state"
            ],
            "PORTFOLIO_RESEARCH_ELIGIBLE",
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_mixed_venue_blocked(
        self,
    ):

        value = portfolio()


        value[
            "strategies"
        ][
            1
        ][
            "instrument"
        ][
            "venue"
        ] = "OTHER"


        with self.assertRaises(
            RuntimeError
        ):

            main.jarvis_nautilus_portfolio_backtest(
                value,
                timeout=90,
            )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            nautilus_c3_portfolio_bridge.place_order


    def test_c2_preserved(
        self,
    ):

        status = (
            main.jarvis_nautilus_c2_status()
        )


        self.assertTrue(
            status[
                "available"
            ]
        )


        self.assertTrue(
            status[
                "commodity_future"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


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


if __name__ == "__main__":

    unittest.main()
