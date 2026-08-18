import unittest

from datetime import (
    datetime,
    timezone,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.commodity_intelligence import (
    CommodityContract,
    commodity_contract_state,
)

from omni.trading_intelligence.defined_risk_spreads import (
    build_vertical_spread,
    vertical_payoff,
)

from omni.trading_intelligence.derivatives_confirmation import (
    derivatives_confirmation,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    derivatives_signal,
    derivatives_strategy_catalog,
)

from omni.trading_intelligence.expiry_intelligence import (
    expiry_state,
)

from omni.trading_intelligence.iv_analytics import (
    iv_percentile,
    iv_rank,
    iv_term_structure,
)

from omni.trading_intelligence.option_chain_intelligence import (
    option_chain_intelligence,
)

from omni.trading_intelligence.option_chain_provider import (
    OptionChainProviderRegistry,
)

from omni.trading_intelligence.option_chain_schema import (
    normalize_option_chain,
)


def chain_rows():

    rows = []


    for strike, call_oi, put_oi, civ, piv in (
        (
            24800,
            50000,
            150000,
            16.0,
            18.0,
        ),

        (
            24900,
            80000,
            130000,
            15.5,
            17.0,
        ),

        (
            25000,
            120000,
            120000,
            15.0,
            16.0,
        ),

        (
            25100,
            160000,
            90000,
            15.5,
            16.5,
        ),

        (
            25200,
            200000,
            60000,
            17.0,
            17.5,
        ),
    ):

        rows.append(
            {
                "symbol":
                    f"NIFTY{strike}CE",

                "strike":
                    strike,

                "option_type":
                    "CE",

                "expiry":
                    "2026-08-27",

                "ltp":
                    200,

                "bid":
                    199,

                "ask":
                    201,

                "volume":
                    call_oi / 10,

                "oi":
                    call_oi,

                "change_in_oi":
                    call_oi / 20,

                "iv":
                    civ,
            }
        )


        rows.append(
            {
                "symbol":
                    f"NIFTY{strike}PE",

                "strike":
                    strike,

                "option_type":
                    "PE",

                "expiry":
                    "2026-08-27",

                "ltp":
                    195,

                "bid":
                    194,

                "ask":
                    196,

                "volume":
                    put_oi / 10,

                "oi":
                    put_oi,

                "change_in_oi":
                    put_oi / 20,

                "iv":
                    piv,
            }
        )


    return rows


def snapshot():

    return normalize_option_chain(
        chain_rows(),
        underlying="NIFTY",
        spot=25020,
        timestamp="2026-08-18T10:00:00+05:30",
    )


class TradingIntelligenceV3Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_chain_normalization(
        self,
    ):

        value = snapshot()


        self.assertEqual(
            len(
                value.contracts
            ),
            10,
        )


        self.assertEqual(
            len(
                value.strikes
            ),
            5,
        )


    def test_atm_chain(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertEqual(
            analysis[
                "atm_strike"
            ],
            25000,
        )


    def test_pcr(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertGreater(
            analysis[
                "pcr_oi"
            ],
            0,
        )


        self.assertGreater(
            analysis[
                "pcr_volume"
            ],
            0,
        )


    def test_oi_walls(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertEqual(
            analysis[
                "call_oi_wall"
            ][
                "strike"
            ],
            25200,
        )


        self.assertEqual(
            analysis[
                "put_oi_wall"
            ][
                "strike"
            ],
            24800,
        )


    def test_max_pain_research(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertIn(
            analysis[
                "max_pain_research"
            ][
                "strike"
            ],
            snapshot().strikes,
        )


        self.assertFalse(
            analysis[
                "max_pain_research"
            ][
                "predictive_claim"
            ]
        )


    def test_liquidity(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertGreater(
            analysis[
                "chain_liquidity_score"
            ],
            0,
        )


    def test_iv_rank(
        self,
    ):

        result = iv_rank(
            20,
            (
                10,
                15,
                20,
                25,
                30,
            ),
        )


        self.assertEqual(
            result,
            50.0,
        )


    def test_iv_percentile(
        self,
    ):

        result = iv_percentile(
            20,
            (
                10,
                15,
                20,
                25,
                30,
            ),
        )


        self.assertEqual(
            result,
            60.0,
        )


    def test_term_structure(
        self,
    ):

        result = iv_term_structure(
            (
                {
                    "expiry":
                        "A",

                    "days_to_expiry":
                        2,

                    "atm_iv":
                        20,
                },

                {
                    "expiry":
                        "B",

                    "days_to_expiry":
                        10,

                    "atm_iv":
                        18,
                },
            )
        )


        self.assertEqual(
            len(
                result[
                    "slopes"
                ]
            ),
            1,
        )


    def test_expiry_intelligence(
        self,
    ):

        result = expiry_state(
            "2026-08-18",
            now=datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=timezone.utc,
            ),
            timezone_name="UTC",
            expiry_time="15:30",
        )


        self.assertEqual(
            result[
                "phase"
            ],
            "EXPIRY_DAY",
        )


    def test_bull_call_defined_risk(
        self,
    ):

        spread = build_vertical_spread(
            "bull_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
            multiplier=1,
        )


        self.assertTrue(
            spread[
                "defined_risk"
            ]
        )


        self.assertFalse(
            spread[
                "naked_short"
            ]
        )


        self.assertEqual(
            spread[
                "max_loss"
            ],
            4,
        )


        self.assertEqual(
            spread[
                "max_profit"
            ],
            6,
        )


    def test_bear_call_defined_risk(
        self,
    ):

        spread = build_vertical_spread(
            "bear_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
        )


        self.assertEqual(
            spread[
                "max_profit"
            ],
            4,
        )


        self.assertEqual(
            spread[
                "max_loss"
            ],
            6,
        )


    def test_vertical_payoff(
        self,
    ):

        spread = build_vertical_spread(
            "bull_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
        )


        self.assertEqual(
            vertical_payoff(
                spread,
                90,
            ),
            -4,
        )


        self.assertEqual(
            vertical_payoff(
                spread,
                120,
            ),
            6,
        )


    def test_commodity_session(
        self,
    ):

        contract = CommodityContract(
            symbol="CRUDE",
            exchange="MCX",
            underlying="CRUDEOIL",
            expiry="2026-09-18",
            lot_size=100,
            tick_size=1,
            session_start="09:00",
            session_end="23:30",
            timezone="UTC",
        )


        state = commodity_contract_state(
            contract,
            now=datetime(
                2026,
                8,
                18,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            spot=6000,
            future=6050,
            bid=6049,
            ask=6051,
            volume=1000,
            open_interest=5000,
        )


        self.assertTrue(
            state[
                "session_open"
            ]
        )


        self.assertGreater(
            state[
                "liquidity_score"
            ],
            0,
        )


    def test_confirmation(
        self,
    ):

        chain = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        result = derivatives_confirmation(
            chain,
            underlying_return=0.01,
            futures_return=0.012,
            futures_basis_pct=0.002,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertGreaterEqual(
            result[
                "confirmation_score"
            ],
            -1,
        )


        self.assertLessEqual(
            result[
                "confirmation_score"
            ],
            1,
        )


    def test_derivatives_strategy_catalog(
        self,
    ):

        catalog = (
            derivatives_strategy_catalog()
        )


        ids = {
            item[
                "strategy_id"
            ]

            for item
            in catalog
        }


        self.assertIn(
            "derivatives_confirmation_v1",
            ids,
        )


        self.assertIn(
            "commodity_liquid_trend_v1",
            ids,
        )


    def test_derivatives_signal(
        self,
    ):

        result = derivatives_signal(
            "derivatives_confirmation_v1",
            {
                "confirmation_score":
                    0.8,

                "liquidity_score":
                    75,
            },
        )


        self.assertEqual(
            result[
                "signal"
            ],
            "LONG",
        )


        self.assertFalse(
            result[
                "execution_allowed"
            ]
        )


    def test_provider_registry_empty_by_default(
        self,
    ):

        registry = (
            OptionChainProviderRegistry()
        )


        status = registry.status()


        self.assertEqual(
            status[
                "count"
            ],
            0,
        )


        self.assertTrue(
            status[
                "read_only"
            ]
        )


    def test_status_truthful_fyers(
        self,
    ):

        status = (
            main.jarvis_trading_v3_status()
        )


        self.assertIsNone(
            status[
                "native_fyers_option_chain"
            ]
        )


        self.assertIsNone(
            status[
                "native_fyers_market_depth"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "naked_option_selling"
            ]
        )


    def test_v2_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v2_status()
        )


        self.assertTrue(
            status[
                "historical_backtester"
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
            "jarvis_trading_v3_status",
            "jarvis_option_chain_snapshot",
            "jarvis_option_chain_analyze",
            "jarvis_iv_rank",
            "jarvis_iv_percentile",
            "jarvis_iv_term_structure",
            "jarvis_expiry_state",
            "jarvis_build_vertical_spread",
            "jarvis_vertical_payoff",
            "jarvis_derivatives_confirmation",
            "jarvis_commodity_contract_state",
            "jarvis_derivatives_strategy_catalog",
            "jarvis_derivatives_signal",
            "jarvis_option_chain_provider_status",
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
