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

from unittest.mock import (
    patch,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.cross_asset_regime_graph import (
    CrossAssetRegimeGraph,
)

from omni.trading_intelligence.derivatives_capture_plans import (
    CapturePlanStore,
    build_capture_plan,
)

from omni.trading_intelligence.derivatives_feature_dataset import (
    DerivativesFeatureDatasetBuilder,
)

from omni.trading_intelligence.derivatives_history_store import (
    DerivativesHistoryStore,
)

from omni.trading_intelligence.derivatives_session_collector import (
    CaptureStateStore,
    DerivativesSessionCollector,
)

from omni.trading_intelligence.research_portfolio_optimizer import (
    ResearchPortfolioOptimizer,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def snapshot(
    snapshot_id,
    symbol,
    minute,
    *,
    atm_iv,
    call_oi,
    put_oi,
    pcr=None,
    skew=0.0,
):

    if pcr is None:

        pcr = (
            put_oi
            / call_oi
        )


    return {
        "snapshot_id":
            snapshot_id,

        "symbol":
            symbol,

        "captured_at":
            (
                NOW
                + timedelta(
                    minutes=minute
                )
            ).isoformat(),

        "selected_expiry":
            "1787047800",

        "strikecount":
            5,

        "greeks_requested":
            True,

        "spot":
            24000
            + minute,

        "call_oi":
            call_oi,

        "put_oi":
            put_oi,

        "pcr_oi":
            pcr,

        "atm_strike":
            24000,

        "atm_call_iv":
            atm_iv,

        "atm_put_iv":
            atm_iv,

        "atm_iv":
            atm_iv,

        "atm_skew":
            skew,

        "expiry_data":
            (),

        "raw_response":
            {
                "s":
                    "ok"
            },

        "provider":
            "test",

        "sdk_version":
            "3.1.16",

        "legs":
            (),
    }


class TradingIntelligenceV8Tests(
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
            main.jarvis_trading_v8_status()
        )


        self.assertTrue(
            status[
                "governed_capture_plans"
            ]
        )


        self.assertTrue(
            status[
                "historical_feature_dataset"
            ]
        )


        self.assertTrue(
            status[
                "cross_asset_regime_graph"
            ]
        )


        self.assertFalse(
            status[
                "background_collection"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_plan_builder(
        self,
    ):

        plan = build_capture_plan(
            "nifty",
            "NSE:NIFTY50-INDEX",
            interval_minutes=5,
        )


        self.assertEqual(
            plan[
                "expiry_mode"
            ],
            "nearest",
        )


        self.assertTrue(
            plan[
                "read_only"
            ]
        )


    def test_explicit_expiry_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            build_capture_plan(
                "x",
                "NSE:NIFTY50-INDEX",
                expiry_mode="explicit",
                expiry_timestamps=(
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                ),
            )


    def test_plan_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            plan = build_capture_plan(
                "nifty",
                "NSE:NIFTY50-INDEX",
            )


            result = store.save(
                plan
            )


            self.assertTrue(
                result[
                    "success"
                ]
            )


            self.assertEqual(
                len(
                    store.list()
                ),
                1,
            )


    def test_collector_dry_run_no_network(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            plan_store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            state_store = CaptureStateStore(
                Path(
                    tmp
                )
                / "state.json"
            )


            plan = build_capture_plan(
                "test",
                "NSE:NIFTY50-INDEX",
                session_start="00:00",
                session_end="23:59",
                timezone="UTC",
            )


            plan_store.save(
                plan
            )


            calls = []


            def fetcher(
                *args,
                **kwargs,
            ):

                calls.append(
                    (
                        args,
                        kwargs,
                    )
                )

                raise AssertionError(
                    "Network fetcher must not run during dry-run."
                )


            collector = DerivativesSessionCollector(
                plan_store=plan_store,
                state_store=state_store,
                fetcher=fetcher,
            )


            result = collector.collect_due(
                now=NOW,
                dry_run=True,
            )


            self.assertEqual(
                len(
                    calls
                ),
                0,
            )


            self.assertEqual(
                result[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "DRY_RUN_DUE",
            )


    def test_collector_fake_capture_and_interval(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            plan_store = CapturePlanStore(
                Path(
                    tmp
                )
                / "plans.json"
            )


            state_store = CaptureStateStore(
                Path(
                    tmp
                )
                / "state.json"
            )


            plan = build_capture_plan(
                "test",
                "NSE:NIFTY50-INDEX",
                interval_minutes=5,
                session_start="00:00",
                session_end="23:59",
                timezone="UTC",
            )


            plan_store.save(
                plan
            )


            calls = []


            def fetcher(
                symbol,
                **kwargs,
            ):

                calls.append(
                    (
                        symbol,
                        kwargs,
                    )
                )


                return {
                    "success":
                        True,

                    "snapshot": {
                        "snapshot_id":
                            "fake-1",
                    },

                    "live_execution":
                        False,
                }


            collector = DerivativesSessionCollector(
                plan_store=plan_store,
                state_store=state_store,
                fetcher=fetcher,
            )


            first = collector.collect_due(
                now=NOW,
            )


            self.assertEqual(
                first[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "CAPTURED",
            )


            second = collector.collect_due(
                now=
                    NOW
                    + timedelta(
                        minutes=2
                    ),
            )


            self.assertEqual(
                second[
                    "results"
                ][
                    0
                ][
                    "status"
                ],
                "NOT_DUE",
            )


            self.assertEqual(
                len(
                    calls
                ),
                1,
            )


    def test_feature_dataset_no_lookahead(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            store.save(
                snapshot(
                    "a",
                    "A",
                    0,
                    atm_iv=10,
                    call_oi=100,
                    put_oi=100,
                )
            )


            store.save(
                snapshot(
                    "b",
                    "A",
                    1,
                    atm_iv=20,
                    call_oi=110,
                    put_oi=130,
                )
            )


            builder = DerivativesFeatureDatasetBuilder(
                store=store
            )


            result = builder.build(
                "A"
            )


            rows = result[
                "rows"
            ]


            self.assertEqual(
                len(
                    rows
                ),
                2,
            )


            self.assertIsNone(
                rows[
                    0
                ][
                    "delta_call_oi"
                ]
            )


            self.assertEqual(
                rows[
                    1
                ][
                    "delta_call_oi"
                ],
                10,
            )


            self.assertEqual(
                rows[
                    1
                ][
                    "delta_put_oi"
                ],
                30,
            )


            self.assertFalse(
                result[
                    "future_data_leakage"
                ]
            )


    def test_regime_dataset_builder(
        self,
    ):

        builder = DerivativesFeatureDatasetBuilder()


        features = (
            {
                "captured_at":
                    NOW.isoformat(),

                "regime": {
                    "regime":
                        "R1",
                },
            },

            {
                "captured_at":
                    (
                        NOW
                        + timedelta(
                            minutes=2
                        )
                    ).isoformat(),

                "regime": {
                    "regime":
                        "R2",
                },
            },
        )


        bars = [
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
                4
            )
        ]


        result = builder.regime_datasets(
            bars,
            features,
        )


        self.assertIn(
            "R1",
            result,
        )


        self.assertIn(
            "R2",
            result,
        )


    def test_cross_asset_graph(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            for index in range(
                4
            ):

                store.save(
                    snapshot(
                        "a"
                        + str(
                            index
                        ),
                        "A",
                        index,
                        atm_iv=
                            10
                            + index,
                        call_oi=
                            100
                            + index,
                        put_oi=
                            100
                            + index,
                    )
                )


                store.save(
                    snapshot(
                        "b"
                        + str(
                            index
                        ),
                        "B",
                        index,
                        atm_iv=
                            20
                            + index * 2,
                        call_oi=
                            100
                            + index,
                        put_oi=
                            100
                            + index,
                    )
                )


            builder = DerivativesFeatureDatasetBuilder(
                store=store
            )


            graph = CrossAssetRegimeGraph(
                dataset_builder=builder
            ).build(
                (
                    "A",
                    "B",
                ),
                min_overlap=3,
                edge_threshold=0.5,
            )


            self.assertEqual(
                len(
                    graph[
                        "edges"
                    ]
                ),
                1,
            )


            self.assertTrue(
                graph[
                    "edges"
                ][
                    0
                ][
                    "material_edge"
                ]
            )


    def test_research_optimizer(
        self,
    ):

        optimizer = ResearchPortfolioOptimizer()


        result = optimizer.optimize(
            (
                {
                    "candidate_id":
                        "a",

                    "symbol":
                        "A",

                    "validation_state":
                        "PORTFOLIO_RESEARCH_ELIGIBLE",

                    "quality_score":
                        50,
                },

                {
                    "candidate_id":
                        "b",

                    "symbol":
                        "B",

                    "validation_state":
                        "KEEP_TESTING",

                    "quality_score":
                        40,
                },
            )
        )


        self.assertAlmostEqual(
            sum(
                result[
                    "research_weights"
                ].values()
            ),
            1.0,
        )


        self.assertFalse(
            result[
                "research_weights_drive_broker_capital"
            ]
        )


        self.assertFalse(
            result[
                "automatic_capital_allocation"
            ]
        )


    def test_v4_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "candidate":
                "ok"
        }


        with patch.object(
            main,
            "jarvis_evolve_strategy",
            return_value=fake,
        ) as mocked:

            result = (
                main.jarvis_v4_evolve_derivatives(
                    "strategy",
                    {
                        "R":
                            ()
                    },
                    {
                        "capital":
                            100000
                    },
                    candidate_count=4,
                    random_seed=7,
                )
            )


            mocked.assert_called_once()


            self.assertEqual(
                result[
                    "v4_result"
                ],
                fake,
            )


            self.assertFalse(
                result[
                    "automatic_strategy_promotion"
                ]
            )


    def test_v5_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "recommendation": {
                "recommendation":
                    "KEEP_TESTING"
            }
        }


        with patch.object(
            main,
            "jarvis_trading_validate_candidate",
            return_value=fake,
        ) as mocked:

            result = (
                main.jarvis_v5_validate_derivatives(
                    {
                        "id":
                            "c"
                    },
                    (),
                    {},
                    regime_datasets={
                        "R":
                            ()
                    },
                )
            )


            mocked.assert_called_once()


            self.assertTrue(
                result[
                    "v5_authoritative"
                ]
            )


            self.assertFalse(
                result[
                    "automatic_strategy_promotion"
                ]
            )


    def test_nautilus_adapter_exact_passthrough(
        self,
    ):

        fake = {
            "success":
                True,

            "live_execution":
                False,
        }


        with patch.object(
            main,
            "jarvis_nautilus_portfolio_backtest",
            return_value=fake,
        ) as mocked:

            result = (
                main
                .jarvis_nautilus_validate_derivatives_portfolio(
                    {
                        "strategies":
                            ()
                    }
                )
            )


            mocked.assert_called_once()


            self.assertEqual(
                result[
                    "mode"
                ],
                "backtest",
            )


            self.assertFalse(
                result[
                    "live_execution"
                ]
            )


    def test_v7_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v7_status()
        )


        self.assertTrue(
            status[
                "historical_chain_store"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
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

        names = (
            "jarvis_trading_v8_status",
            "jarvis_derivatives_capture_plan",
            "jarvis_save_derivatives_capture_plan",
            "jarvis_list_derivatives_capture_plans",
            "jarvis_run_derivatives_collector",
            "jarvis_build_derivatives_feature_dataset",
            "jarvis_build_synchronized_derivatives_dataset",
            "jarvis_build_derivatives_regime_datasets",
            "jarvis_v4_evolve_derivatives",
            "jarvis_v5_validate_derivatives",
            "jarvis_v5_walk_forward_derivatives",
            "jarvis_nautilus_validate_derivatives_portfolio",
            "jarvis_cross_asset_regime_graph",
            "jarvis_research_portfolio_optimize",
        )


        for name in names:

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
