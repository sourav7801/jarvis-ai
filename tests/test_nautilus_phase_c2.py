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

from omni.trading_intelligence.nautilus_c2_bridge import (
    nautilus_c2_bridge,
)


def bars(
    base,
    step,
    spread,
    count=80,
):

    start = datetime(
        2026,
        1,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


    output = []


    for index in range(
        count
    ):

        price = (
            float(
                base
            )
            + index
            * float(
                step
            )
        )


        output.append(
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


    return output


def normal_signals(
    count=80,
):

    result = [
        "FLAT"
        for _ in range(
            count
        )
    ]


    result[
        20
    ] = "LONG"


    result[
        40
    ] = "EXIT"


    result[
        50
    ] = "SHORT"


    result[
        70
    ] = "EXIT"


    return result


def option_signals(
    count=80,
):

    result = [
        "FLAT"
        for _ in range(
            count
        )
    ]


    result[
        20
    ] = "LONG"


    result[
        50
    ] = "EXIT"


    return result


class NautilusPhaseC2Tests(
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
            main.jarvis_nautilus_c2_status()
        )


        self.assertTrue(
            status[
                "available"
            ]
        )


        self.assertEqual(
            status[
                "version"
            ],
            "1.231.0",
        )


        self.assertTrue(
            status[
                "commodity_future"
            ]
        )


        self.assertTrue(
            status[
                "listed_option"
            ]
        )


        self.assertFalse(
            status[
                "single_leg_option_short"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_equity(
        self,
    ):

        result = (
            main.jarvis_nautilus_universal_backtest(
                bars(
                    100,
                    0.1,
                    0.5,
                ),

                normal_signals(),

                {
                    "kind":
                        "equity",

                    "symbol":
                        "AAPL",

                    "venue":
                        "XNAS",
                },

                quantity=10,
                timeout=60,
            )
        )


        self.assertEqual(
            result[
                "instrument"
            ][
                "research_kind"
            ],
            "equity",
        )


        self.assertGreaterEqual(
            result[
                "fill_count"
            ],
            2,
        )


    def test_future(
        self,
    ):

        result = (
            main.jarvis_nautilus_universal_backtest(
                bars(
                    5000,
                    1,
                    3,
                ),

                normal_signals(),

                {
                    "kind":
                        "future",

                    "symbol":
                        "ESZ6",

                    "venue":
                        "SIM",

                    "underlying":
                        "ES",

                    "asset_class":
                        "INDEX",

                    "price_increment":
                        "0.25",

                    "multiplier":
                        "50",

                    "expiration":
                        "2026-12-18T21:00:00Z",
                },

                quantity=1,
                timeout=60,
            )
        )


        self.assertEqual(
            result[
                "instrument"
            ][
                "type"
            ],
            "FuturesContract",
        )


    def test_commodity_future(
        self,
    ):

        result = (
            main.jarvis_nautilus_universal_backtest(
                bars(
                    75,
                    0.05,
                    0.30,
                ),

                normal_signals(),

                {
                    "kind":
                        "commodity_future",

                    "symbol":
                        "CLZ6",

                    "venue":
                        "SIM",

                    "underlying":
                        "CL",

                    "price_increment":
                        "0.01",

                    "multiplier":
                        "1000",

                    "expiration":
                        "2026-11-20T19:30:00Z",
                },

                quantity=1,
                timeout=60,
            )
        )


        self.assertEqual(
            result[
                "instrument"
            ][
                "research_kind"
            ],
            "commodity_future",
        )


        self.assertEqual(
            result[
                "instrument"
            ][
                "type"
            ],
            "FuturesContract",
        )


    def test_option_long(
        self,
    ):

        result = (
            main.jarvis_nautilus_universal_backtest(
                bars(
                    10,
                    0.04,
                    0.20,
                ),

                option_signals(),

                {
                    "kind":
                        "option",

                    "symbol":
                        "AAPL261218C00150000",

                    "venue":
                        "SIM",

                    "underlying":
                        "AAPL",

                    "asset_class":
                        "EQUITY",

                    "option_kind":
                        "CALL",

                    "strike":
                        "150",

                    "multiplier":
                        "100",

                    "expiration":
                        "2026-12-18T21:00:00Z",
                },

                quantity=1,
                timeout=60,
            )
        )


        self.assertEqual(
            result[
                "instrument"
            ][
                "type"
            ],
            "OptionContract",
        )


    def test_option_short_blocked(
        self,
    ):

        signals = option_signals()

        signals[
            30
        ] = "SHORT"


        with self.assertRaises(
            PermissionError
        ):

            nautilus_c2_bridge.backtest(
                bars(
                    10,
                    0.04,
                    0.2,
                ),

                signals,

                instrument={
                    "kind":
                        "option",

                    "symbol":
                        "TESTC100",

                    "venue":
                        "SIM",

                    "underlying":
                        "TEST",

                    "strike":
                        "100",
                },
            )


    def test_execution_profile(
        self,
    ):

        result = (
            main.jarvis_nautilus_universal_backtest(
                bars(
                    1.10,
                    0.0001,
                    0.0003,
                ),

                normal_signals(),

                {
                    "kind":
                        "fx",

                    "symbol":
                        "EUR/USD",
                },

                execution={
                    "name":
                        "one_tick",
                },

                quantity=1000,
                timeout=60,
            )
        )


        self.assertEqual(
            result[
                "execution"
            ][
                "prob_slippage"
            ],
            1.0,
        )


    def test_reconciliation(
        self,
    ):

        result = (
            main.jarvis_reconcile_backtests(
                {
                    "trades": (
                        {
                            "net_pnl":
                                10,
                        },
                    ),

                    "metrics": {
                        "net_pnl":
                            10,
                    },
                },

                {
                    "engine":
                        "BacktestEngine",

                    "fill_count":
                        2,

                    "position_report_rows":
                        1,

                    "realized_pnl_numeric":
                        9,
                },
            )
        )


        self.assertFalse(
            result[
                "timing_semantics"
            ][
                "direct_equivalence_expected"
            ]
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_v5_gate(
        self,
    ):

        result = (
            main.jarvis_nautilus_v5_gate(
                {
                    "recommendation": {
                        "recommendation":
                            "PROMOTE"
                    }
                },

                {
                    "success":
                        True,

                    "fill_count":
                        4,

                    "paper_only":
                        True,

                    "live_execution":
                        False,

                    "broker_adapter":
                        False,
                },
            )
        )


        self.assertEqual(
            result[
                "state"
            ],
            "EXTENDED_RESEARCH_ELIGIBLE",
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_portfolio_research(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_research(
                (
                    {
                        "research_only":
                            True,

                        "live_execution":
                            False,

                        "broker_adapter":
                            False,

                        "instrument": {
                            "research_kind":
                                "equity",

                            "instrument_id":
                                "A.X",
                        },

                        "fill_count":
                            2,

                        "position_report_rows":
                            1,

                        "realized_pnl_numeric":
                            10,
                    },

                    {
                        "research_only":
                            True,

                        "live_execution":
                            False,

                        "broker_adapter":
                            False,

                        "instrument": {
                            "research_kind":
                                "commodity_future",

                            "instrument_id":
                                "CL.SIM",
                        },

                        "fill_count":
                            4,

                        "position_report_rows":
                            2,

                        "realized_pnl_numeric":
                            -2,
                    },
                )
            )
        )


        self.assertEqual(
            result[
                "result_count"
            ],
            2,
        )


        self.assertEqual(
            result[
                "total_fills"
            ],
            6,
        )


        self.assertFalse(
            result[
                "capital_allocation"
            ]
        )


        self.assertFalse(
            result[
                "portfolio_live_execution"
            ]
        )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            nautilus_c2_bridge.place_order


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
