import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.evidence_ledger import (
    TradingEvidenceLedger,
)

from omni.trading_intelligence.market_freshness import (
    MarketFreshnessGuard,
)

from omni.trading_intelligence.paper_execution import (
    PaperExecutionEngine,
)

from omni.trading_intelligence.performance_drift import (
    PerformanceDriftDetector,
)

from omni.trading_intelligence.shadow_champion import (
    ShadowChampionChallenger,
)

from omni.trading_intelligence.shadow_market_bridge import (
    FyersShadowMarketBridge,
    quote_snapshot_from_payload,
)

from omni.trading_intelligence.shadow_runtime import (
    ShadowTradingRuntime,
)

from omni.trading_intelligence.shadow_schema import (
    QuoteSnapshot,
    ShadowSessionConfig,
)

from omni.trading_intelligence.strategy_weighting import (
    ResearchStrategyWeighting,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def quote(
    price=100,
    seconds=0,
):

    return QuoteSnapshot(
        symbol="TEST",
        timestamp=
            NOW
            + timedelta(
                seconds=seconds
            ),
        ltp=price,
        bid=price - 0.1,
        ask=price + 0.1,
        source="test",
    )


class FakeAdapter:

    def quote(
        self,
        symbol,
    ):

        return {
            "success":
                True,

            "symbol":
                symbol,

            "ltp":
                101.0,

            "bid":
                100.9,

            "ask":
                101.1,

            "timestamp":
                NOW.isoformat(),
        }


    def place_order(
        self,
        payload,
    ):

        raise AssertionError(
            "Broker order must never run."
        )


class TradingIntelligenceV6Tests(
    unittest.TestCase
):

    def test_core(self):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_fresh_quote(self):

        result = MarketFreshnessGuard(
            15,
            5,
        ).check(
            quote(),
            now=NOW,
        )


        self.assertTrue(
            result[
                "fresh"
            ]
        )


    def test_stale_quote(self):

        stale = QuoteSnapshot(
            symbol="TEST",
            timestamp=
                NOW
                - timedelta(
                    seconds=30
                ),
            ltp=100,
        )


        result = MarketFreshnessGuard(
            15,
            5,
        ).check(
            stale,
            now=NOW,
        )


        self.assertFalse(
            result[
                "fresh"
            ]
        )


        self.assertEqual(
            result[
                "reason"
            ],
            "stale_quote",
        )


    def test_future_quote_blocked(self):

        future = quote(
            seconds=30
        )


        result = MarketFreshnessGuard(
            15,
            5,
        ).check(
            future,
            now=NOW,
        )


        self.assertFalse(
            result[
                "fresh"
            ]
        )


    def test_virtual_long_trade(self):

        engine = PaperExecutionEngine(
            ShadowSessionConfig(
                fixed_fee=1,
            )
        )


        opened = engine.on_signal(
            quote(100),
            "LONG",
        )


        closed = engine.on_signal(
            quote(105),
            "EXIT",
        )


        self.assertTrue(
            opened[
                "success"
            ]
        )


        self.assertTrue(
            closed[
                "success"
            ]
        )


        self.assertEqual(
            len(
                engine.trades
            ),
            1,
        )


        self.assertTrue(
            engine.trades[
                0
            ][
                "paper_only"
            ]
        )


        self.assertFalse(
            engine.trades[
                0
            ][
                "broker_order"
            ]
        )


    def test_virtual_short_trade(self):

        engine = PaperExecutionEngine(
            ShadowSessionConfig(
                allow_short=True,
            )
        )


        engine.on_signal(
            quote(100),
            "SHORT",
        )


        engine.on_signal(
            quote(95),
            "EXIT",
        )


        self.assertEqual(
            engine.trades[
                0
            ][
                "side"
            ],
            "SHORT",
        )


    def test_same_tick_reversal_not_done(self):

        engine = PaperExecutionEngine(
            ShadowSessionConfig()
        )


        engine.on_signal(
            quote(100),
            "LONG",
        )


        result = engine.on_signal(
            quote(99),
            "SHORT",
        )


        self.assertEqual(
            result[
                "action"
            ],
            "VIRTUAL_CLOSE",
        )


        self.assertIsNone(
            engine.position
        )


    def test_kill_switch(self):

        engine = PaperExecutionEngine(
            ShadowSessionConfig()
        )


        engine.kill(
            "test"
        )


        result = engine.open(
            quote(),
            1,
        )


        self.assertTrue(
            result[
                "blocked"
            ]
        )


        self.assertEqual(
            result[
                "reason"
            ],
            "kill_switch",
        )


    def test_order_surface_blocked(self):

        engine = PaperExecutionEngine(
            ShadowSessionConfig()
        )


        with self.assertRaises(
            PermissionError
        ):

            engine.place_order


    def test_quote_payload(self):

        snapshot = quote_snapshot_from_payload(
            {
                "success":
                    True,

                "ltp":
                    100,

                "bid":
                    99.9,

                "ask":
                    100.1,

                "timestamp":
                    NOW.isoformat(),
            },

            symbol="TEST",
        )


        self.assertEqual(
            snapshot.ltp,
            100,
        )


        self.assertEqual(
            snapshot.timestamp_origin,
            "provider",
        )


    def test_received_timestamp_truthful(self):

        snapshot = quote_snapshot_from_payload(
            {
                "success":
                    True,

                "ltp":
                    100,
            },

            symbol="TEST",
            received_at=NOW,
        )


        self.assertEqual(
            snapshot.timestamp_origin,
            "received_at",
        )


    def test_fake_fyers_bridge(self):

        bridge = FyersShadowMarketBridge(
            FakeAdapter()
        )


        snapshot = bridge.read_quote(
            "TEST"
        )


        self.assertEqual(
            snapshot.ltp,
            101,
        )


        with self.assertRaises(
            PermissionError
        ):

            bridge.place_order


    def test_shadow_session_stale_block(self):

        runtime = ShadowTradingRuntime(
            market_bridge=
                FyersShadowMarketBridge(
                    FakeAdapter()
                )
        )


        created = runtime.create(
            "TEST",
            (
                "alpha",
            ),
            ShadowSessionConfig(
                max_quote_age_seconds=10,
            ),
        )


        stale = QuoteSnapshot(
            symbol="TEST",
            timestamp=
                NOW
                - timedelta(
                    seconds=60
                ),
            ltp=100,
        )


        result = runtime.process(
            created[
                "session_id"
            ],
            stale,
            (
                {
                    "strategy_id":
                        "alpha",

                    "signal":
                        "LONG",
                },
            ),
            now=NOW,
        )


        self.assertTrue(
            result[
                "blocked"
            ]
        )


    def test_shadow_runtime_trade(self):

        runtime = ShadowTradingRuntime(
            market_bridge=
                FyersShadowMarketBridge(
                    FakeAdapter()
                )
        )


        created = runtime.create(
            "TEST",
            (
                "alpha",
            ),
        )


        session_id = created[
            "session_id"
        ]


        runtime.process(
            session_id,
            quote(100),
            (
                {
                    "strategy_id":
                        "alpha",

                    "signal":
                        "LONG",
                },
            ),
            now=NOW,
        )


        runtime.process(
            session_id,
            quote(105),
            (
                {
                    "strategy_id":
                        "alpha",

                    "signal":
                        "EXIT",
                },
            ),
            now=NOW,
        )


        summary = (
            runtime.get(
                session_id
            )
            .summary()
        )


        self.assertEqual(
            summary[
                "strategies"
            ][
                "alpha"
            ][
                "trade_count"
            ],
            1,
        )


    def test_evidence_ledger(self):

        with tempfile.TemporaryDirectory() as tmp:

            ledger = TradingEvidenceLedger(
                Path(
                    tmp
                )
            )


            ledger.append(
                "test",
                {
                    "value":
                        1
                },
            )


            recent = ledger.recent()


            self.assertEqual(
                len(
                    recent
                ),
                1,
            )


            self.assertFalse(
                recent[
                    0
                ][
                    "broker_order"
                ]
            )


    def test_drift(self):

        result = (
            PerformanceDriftDetector()
            .compare(
                {
                    "expectancy":
                        100,

                    "profit_factor":
                        2,

                    "win_rate":
                        0.60,

                    "max_drawdown_pct":
                        0.05,
                },

                {
                    "expectancy":
                        -20,

                    "profit_factor":
                        0.8,

                    "win_rate":
                        0.35,

                    "max_drawdown_pct":
                        0.20,
                },
            )
        )


        self.assertGreater(
            result[
                "drift_score"
            ],
            0,
        )


        self.assertFalse(
            result[
                "automatic_broker_action"
            ]
        )


    def test_weights_sum_one(self):

        result = (
            ResearchStrategyWeighting()
            .calculate(
                {
                    "a": {
                        "validation_score":
                            20,

                        "recent_score":
                            10,

                        "drift_score":
                            5,
                    },

                    "b": {
                        "validation_score":
                            5,

                        "recent_score":
                            -10,

                        "drift_score":
                            50,
                    },
                }
            )
        )


        self.assertAlmostEqual(
            result[
                "sum"
            ],
            1.0,
        )


        self.assertFalse(
            result[
                "capital_allocation"
            ]
        )


    def test_shadow_champion(self):

        result = (
            ShadowChampionChallenger()
            .compare(
                {
                    "trades":
                        10,

                    "return_pct":
                        0.05,

                    "expectancy":
                        10,

                    "avg_loss":
                        10,

                    "profit_factor":
                        1.5,

                    "win_rate":
                        0.50,

                    "max_drawdown_pct":
                        0.10,
                },

                {
                    "trades":
                        10,

                    "return_pct":
                        0.10,

                    "expectancy":
                        20,

                    "avg_loss":
                        10,

                    "profit_factor":
                        2.0,

                    "win_rate":
                        0.60,

                    "max_drawdown_pct":
                        0.05,
                },
            )
        )


        self.assertFalse(
            result[
                "automatic_production_promotion"
            ]
        )


    def test_status(self):

        status = main.jarvis_trading_v6_status()


        self.assertTrue(
            status[
                "paper_only"
            ]
        )


        self.assertTrue(
            status[
                "market_freshness_guard"
            ]
        )


        self.assertTrue(
            status[
                "performance_drift"
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


        self.assertFalse(
            status[
                "research_weights_drive_broker_capital"
            ]
        )


    def test_v5_preserved(self):

        status = main.jarvis_trading_v5_status()


        self.assertTrue(
            status[
                "walk_forward_validation"
            ]
        )


        self.assertFalse(
            status[
                "automatic_strategy_promotion"
            ]
        )


    def test_public_apis(self):

        for name in (
            "jarvis_trading_v6_status",
            "jarvis_shadow_config",
            "jarvis_shadow_quote_snapshot",
            "jarvis_shadow_create_session",
            "jarvis_shadow_process",
            "jarvis_shadow_fyers_quote",
            "jarvis_shadow_process_fyers",
            "jarvis_shadow_status",
            "jarvis_shadow_kill",
            "jarvis_shadow_resume",
            "jarvis_shadow_summary",
            "jarvis_shadow_drift",
            "jarvis_shadow_weights",
            "jarvis_shadow_champion_compare",
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
