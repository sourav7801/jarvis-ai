import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.derivatives_history_analytics import (
    DerivativesHistoryAnalytics,
)

from omni.trading_intelligence.derivatives_history_store import (
    DerivativesHistoryStore,
)

from omni.trading_intelligence.derivatives_sync import (
    synchronize_derivatives,
)

from omni.trading_intelligence.fyers_chain_normalizer import (
    normalize_fyers_option_chain,
)

from omni.trading_intelligence.fyers_v7_bridge import (
    fyers_v7_readonly_bridge,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def fyers_result(
    *,
    spot=25000,
    call_oi=1000,
    put_oi=1200,
    call_iv=15,
    put_iv=17,
    expiry="1797550200",
):

    return {
        "success":
            True,

        "sdk_version":
            "3.1.16",

        "request": {
            "symbol":
                "NSE:NIFTY50-INDEX",

            "strikecount":
                5,

            "timestamp":
                expiry,

            "greeks":
                "1",
        },

        "response": {
            "s":
                "ok",

            "data": {
                "callOi":
                    call_oi,

                "putOi":
                    put_oi,

                "expiryData": [
                    {
                        "date":
                            "18-12-2026",

                        "expiry":
                            expiry,

                        "expiry_flag":
                            "M",
                    }
                ],

                "optionsChain": [
                    {
                        "option_type":
                            "",

                        "strike_price":
                            -1,

                        "ltp":
                            spot,
                    },

                    {
                        "symbol":
                            "NSE:NIFTY-CE",

                        "fyToken":
                            "1",

                        "option_type":
                            "CE",

                        "strike_price":
                            25000,

                        "ltp":
                            200,

                        "bid":
                            199,

                        "ask":
                            201,

                        "oi":
                            call_oi,

                        "oich":
                            100,

                        "prev_oi":
                            call_oi - 100,

                        "volume":
                            500,

                        "greeks": {
                            "delta":
                                0.5,

                            "gamma":
                                0.01,

                            "theta":
                                -10,

                            "vega":
                                12,

                            "iv":
                                call_iv,
                        },
                    },

                    {
                        "symbol":
                            "NSE:NIFTY-PE",

                        "fyToken":
                            "2",

                        "option_type":
                            "PE",

                        "strike_price":
                            25000,

                        "ltp":
                            210,

                        "bid":
                            209,

                        "ask":
                            211,

                        "oi":
                            put_oi,

                        "oich":
                            150,

                        "prev_oi":
                            put_oi - 150,

                        "volume":
                            600,

                        "greeks": {
                            "delta":
                                -0.5,

                            "gamma":
                                0.01,

                            "theta":
                                -11,

                            "vega":
                                13,

                            "iv":
                                put_iv,
                        },
                    },
                ],
            },
        },

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }


class TradingIntelligenceV7Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_sdk_status(
        self,
    ):

        status = (
            fyers_v7_readonly_bridge
            .status()
        )


        self.assertTrue(
            status[
                "available"
            ]
        )


        self.assertEqual(
            status[
                "sdk_version"
            ],
            "3.1.16",
        )


        self.assertEqual(
            status[
                "option_chain_method"
            ],
            "optionchain",
        )


        self.assertEqual(
            status[
                "depth_method"
            ],
            "depth",
        )


    def test_normalize(
        self,
    ):

        result = normalize_fyers_option_chain(
            fyers_result(),
            captured_at=NOW,
        )


        self.assertEqual(
            result[
                "spot"
            ],
            25000,
        )


        self.assertEqual(
            result[
                "atm_strike"
            ],
            25000,
        )


        self.assertEqual(
            len(
                result[
                    "legs"
                ]
            ),
            2,
        )


        self.assertAlmostEqual(
            result[
                "pcr_oi"
            ],
            1.2,
        )


        self.assertAlmostEqual(
            result[
                "atm_iv"
            ],
            16,
        )


        self.assertAlmostEqual(
            result[
                "atm_skew"
            ],
            2,
        )


    def test_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            snapshot = normalize_fyers_option_chain(
                fyers_result(),
                captured_at=NOW,
            )


            saved = store.save(
                snapshot
            )


            self.assertTrue(
                saved[
                    "success"
                ]
            )


            history = store.history(
                "NSE:NIFTY50-INDEX"
            )


            self.assertEqual(
                len(
                    history
                ),
                1,
            )


            legs = store.leg_history(
                "NSE:NIFTY50-INDEX",
                25000,
                "CE",
            )


            self.assertEqual(
                len(
                    legs
                ),
                1,
            )


    def test_iv_history_math(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            import omni.trading_intelligence.derivatives_history_analytics as module


            original = (
                module.derivatives_history_store
            )


            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            module.derivatives_history_store = store


            try:

                for index, iv in enumerate(
                    (
                        10,
                        15,
                        20,
                    )
                ):

                    snapshot = (
                        normalize_fyers_option_chain(
                            fyers_result(
                                call_iv=iv,
                                put_iv=iv + 2,
                                call_oi=
                                    1000
                                    + index * 50,
                                put_oi=
                                    1100
                                    + index * 100,
                            ),
                            captured_at=
                                NOW
                                + timedelta(
                                    minutes=index
                                ),
                        )
                    )


                    store.save(
                        snapshot
                    )


                analytics = (
                    module
                    .DerivativesHistoryAnalytics()
                    .analyze(
                        "NSE:NIFTY50-INDEX"
                    )
                )


                self.assertTrue(
                    analytics[
                        "available"
                    ]
                )


                self.assertIsNotNone(
                    analytics[
                        "atm_iv_rank"
                    ]
                )


                self.assertIsNotNone(
                    analytics[
                        "atm_iv_percentile"
                    ]
                )


                self.assertEqual(
                    analytics[
                        "delta_call_oi"
                    ],
                    50,
                )


                self.assertEqual(
                    analytics[
                        "delta_put_oi"
                    ],
                    100,
                )


            finally:

                module.derivatives_history_store = (
                    original
                )


    def test_sync_no_future_chain(
        self,
    ):

        underlying = [
            {
                "timestamp":
                    NOW
                    + timedelta(
                        minutes=index
                    ),

                "close":
                    100
                    + index,
            }

            for index
            in range(
                3
            )
        ]


        futures = [
            {
                "timestamp":
                    NOW
                    + timedelta(
                        minutes=index
                    ),

                "close":
                    101
                    + index,
            }

            for index
            in range(
                3
            )
        ]


        chains = [
            {
                "captured_at":
                    (
                        NOW
                        + timedelta(
                            seconds=30
                        )
                    ).isoformat(),

                "pcr_oi":
                    1.1,

                "atm_iv":
                    15,

                "atm_skew":
                    1,

                "call_oi":
                    100,

                "put_oi":
                    110,

                "atm_strike":
                    100,
            }
        ]


        result = synchronize_derivatives(
            underlying,
            futures,
            chains,
            max_chain_age_seconds=300,
        )


        self.assertTrue(
            result[
                "backward_asof_only"
            ]
        )


        self.assertFalse(
            result[
                "future_data_leakage"
            ]
        )


        # The first underlying timestamp precedes
        # chain capture and must not receive the chain.
        self.assertEqual(
            result[
                "row_count"
            ],
            2,
        )


    def test_regime(
        self,
    ):

        result = (
            main.jarvis_derivatives_regime(
                {
                    "atm_iv_rank":
                        80,

                    "pcr_oi":
                        1.3,

                    "delta_call_oi":
                        50,

                    "delta_put_oi":
                        100,

                    "futures_basis":
                        10,
                }
            )
        )


        self.assertEqual(
            result[
                "components"
            ][
                "volatility"
            ],
            "HIGH_IV",
        )


        self.assertFalse(
            result[
                "predictive_guarantee"
            ]
        )


    def test_ensemble(
        self,
    ):

        result = (
            main.jarvis_derivatives_ensemble(
                {
                    "a":
                        "LONG",

                    "b":
                        "LONG",

                    "c":
                        "SHORT",
                }
            )
        )


        self.assertEqual(
            result[
                "consensus"
            ],
            "LONG",
        )


        self.assertFalse(
            result[
                "execution_allowed"
            ]
        )


        self.assertFalse(
            result[
                "broker_order"
            ]
        )


    def test_campaign(
        self,
    ):

        result = (
            main.jarvis_derivatives_campaign(
                (
                    {
                        "candidate_id":
                            "a",

                        "v5_recommendation":
                            "PROMOTE",

                        "c3_campaign": {
                            "oos_pass_rate":
                                0.8,
                        },
                    },

                    {
                        "candidate_id":
                            "b",

                        "v5_recommendation":
                            "DEGRADE",
                    },
                )
            )
        )


        self.assertEqual(
            result[
                "candidate_count"
            ],
            2,
        )


        self.assertEqual(
            result[
                "best_candidate"
            ][
                "candidate_id"
            ],
            "a",
        )


        self.assertFalse(
            result[
                "automatic_strategy_promotion"
            ]
        )


    def test_campaign_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            main.jarvis_derivatives_campaign(
                tuple(
                    {
                        "candidate_id":
                            str(
                                index
                            )
                    }

                    for index in range(
                        51
                    )
                )
            )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            fyers_v7_readonly_bridge.place_order


    def test_v7_status(
        self,
    ):

        status = (
            main.jarvis_trading_v7_status()
        )


        self.assertTrue(
            status[
                "real_option_chain_read"
            ]
        )


        self.assertTrue(
            status[
                "historical_chain_store"
            ]
        )


        self.assertTrue(
            status[
                "underlying_futures_options_sync"
            ]
        )


        self.assertFalse(
            status[
                "future_data_leakage"
            ]
        )


        self.assertFalse(
            status[
                "background_option_chain_polling"
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


    def test_v5_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v5_status()
        )


        self.assertTrue(
            status[
                "walk_forward_validation"
            ]
        )


        self.assertFalse(
            status[
                "oos_tuning"
            ]
        )


    def test_c3_preserved(
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


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v7_status",
            "jarvis_fyers_option_chain",
            "jarvis_fyers_market_depth",
            "jarvis_derivatives_history",
            "jarvis_derivatives_leg_history",
            "jarvis_derivatives_history_analytics",
            "jarvis_sync_derivatives",
            "jarvis_derivatives_regime",
            "jarvis_derivatives_ensemble",
            "jarvis_derivatives_campaign",
        ):

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
