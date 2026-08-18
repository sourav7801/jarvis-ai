from __future__ import annotations

from omni.trading_intelligence.account_simulator import (
    AccountSimulator,
)

from omni.trading_intelligence.execution_model import (
    ExecutionSimulator,
)

from omni.trading_intelligence.feature_engine import (
    feature_engine,
)

from omni.trading_intelligence.history_normalizer import (
    normalize_history_payload,
)

from omni.trading_intelligence.multi_timeframe import (
    multitimeframe_features,
)

from omni.trading_intelligence.signal_engine import (
    signal_engine,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.trading_dataset import (
    TradingDataset,
)

from omni.trading_intelligence.trading_metrics import (
    evaluate_trades,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)


class HistoricalBacktester:

    @staticmethod
    def _prepare_bars(
        bars,
    ):

        if isinstance(
            bars,
            TradingDataset,
        ):

            return bars.bars


        return (
            TradingDataset(
                bars
            )
            .bars
        )


    @staticmethod
    def _features(
        bars,
        config,
    ):

        result = (
            feature_engine
            .snapshot(
                bars
            )
        )


        if config.higher_timeframes:

            result.update(
                multitimeframe_features(
                    bars,
                    config.higher_timeframes,
                    base_timeframe_minutes=
                        config.base_timeframe_minutes,
                )
            )


        return result


    @staticmethod
    def _opposite_signal(
        side,
        signal,
    ):

        return (
            (
                side == 1
                and signal == "SHORT"
            )
            or (
                side == -1
                and signal == "LONG"
            )
        )


    def run(
        self,
        bars,
        strategy,
        config,
    ):

        bars = self._prepare_bars(
            bars
        )


        if isinstance(
            strategy,
            str,
        ):

            strategy = strategy_registry.get(
                strategy
            )


        if strategy is None:

            raise ValueError(
                "Unknown strategy."
            )


        minimum = max(
            int(
                config.warmup_bars
            ),
            21,
        )


        if len(
            bars
        ) <= (
            minimum
            + 1
        ):

            raise ValueError(
                "Not enough bars for configured warmup."
            )


        account = AccountSimulator(
            config.initial_capital
        )


        execution = ExecutionSimulator(
            config
        )


        trades = []

        position = None

        pending = None


        previous_features = (
            self._features(
                bars[
                    :minimum
                ],
                config,
            )
        )


        signals_evaluated = 0


        for index in range(
            minimum,
            len(
                bars
            ),
        ):

            bar = bars[
                index
            ]


            # ------------------------------------------------
            # Execute previous close's decision at this bar open.
            # ------------------------------------------------

            if pending is not None:

                action = pending[
                    "action"
                ]


                if (
                    action == "exit"
                    and position is not None
                ):

                    trade = (
                        execution
                        .close_position(
                            position,
                            float(
                                bar.open
                            ),
                            bar.timestamp,
                            index,
                            pending[
                                "reason"
                            ],
                        )
                    )


                    trades.append(
                        trade
                    )

                    account.record_trade(
                        trade
                    )

                    position = None


                elif (
                    action == "entry"
                    and position is None
                ):

                    side = int(
                        pending[
                            "side"
                        ]
                    )


                    permitted = (
                        (
                            side == 1
                            and config.allow_long
                        )
                        or (
                            side == -1
                            and config.allow_short
                        )
                    )


                    if permitted:

                        can_open = account.can_open(
                            config.quantity,
                            config.capital_requirement_per_unit,
                        )


                        if can_open:

                            position = (
                                execution
                                .open_position(
                                    side,
                                    float(
                                        bar.open
                                    ),
                                    bar.timestamp,
                                    index,
                                )
                            )


                        else:

                            account.reject_entry()


                pending = None


            # ------------------------------------------------
            # Intrabar protective exits.
            # ------------------------------------------------

            if position is not None:

                protective = (
                    execution
                    .protective_exit(
                        position,
                        bar,
                    )
                )


                if protective is not None:

                    price, reason = (
                        protective
                    )


                    trade = (
                        execution
                        .close_position(
                            position,
                            price,
                            bar.timestamp,
                            index,
                            reason,
                        )
                    )


                    trades.append(
                        trade
                    )

                    account.record_trade(
                        trade
                    )

                    position = None


                else:

                    execution.update_trailing(
                        position,
                        bar,
                    )


            # ------------------------------------------------
            # No future bar exists for next-open execution.
            # ------------------------------------------------

            if (
                index
                >= len(
                    bars
                )
                - 1
            ):

                break


            current_features = (
                self._features(
                    bars[
                        :index + 1
                    ],
                    config,
                )
            )


            signal = (
                signal_engine
                .evaluate(
                    strategy,
                    current_features,
                    previous_features,
                )
            )[
                "signal"
            ]


            signals_evaluated += 1


            # ------------------------------------------------
            # Schedule decisions for next bar open.
            # ------------------------------------------------

            if position is None:

                if (
                    signal == "LONG"
                    and config.allow_long
                ):

                    pending = {
                        "action":
                            "entry",

                        "side":
                            1,
                    }


                elif (
                    signal == "SHORT"
                    and config.allow_short
                ):

                    pending = {
                        "action":
                            "entry",

                        "side":
                            -1,
                    }


            else:

                held = (
                    index
                    - position.entry_index
                    + 1
                )


                time_exit = (
                    config.max_bars_in_trade
                    is not None
                    and held
                    >= config.max_bars_in_trade
                )


                opposite = (
                    config.exit_on_opposite_signal
                    and self._opposite_signal(
                        position.side,
                        signal,
                    )
                )


                explicit_exit = (
                    signal
                    == "EXIT"
                )


                if time_exit:

                    pending = {
                        "action":
                            "exit",

                        "reason":
                            "max_bars",
                    }


                elif explicit_exit:

                    pending = {
                        "action":
                            "exit",

                        "reason":
                            "strategy_exit",
                    }


                elif opposite:

                    pending = {
                        "action":
                            "exit",

                        "reason":
                            "opposite_signal",
                    }


            previous_features = (
                current_features
            )


        # ----------------------------------------------------
        # Final liquidation at final close.
        # ----------------------------------------------------

        if position is not None:

            last_index = (
                len(
                    bars
                )
                - 1
            )

            last_bar = bars[
                last_index
            ]


            trade = (
                execution
                .close_position(
                    position,
                    float(
                        last_bar.close
                    ),
                    last_bar.timestamp,
                    last_index,
                    "end_of_data",
                )
            )


            trades.append(
                trade
            )

            account.record_trade(
                trade
            )


        metrics = evaluate_trades(
            trades
        )


        account_status = (
            account.status()
        )


        metrics[
            "return_pct"
        ] = account_status[
            "return_pct"
        ]


        metrics[
            "account_max_drawdown"
        ] = account_status[
            "max_drawdown"
        ]


        equity_curve = (
            account.curve()
        )


        max_dd_pct = max(
            (
                point[
                    "drawdown_pct"
                ]

                for point
                in equity_curve
            ),
            default=0.0,
        )


        metrics[
            "max_drawdown_pct"
        ] = max_dd_pct


        return {
            "success":
                True,

            "strategy_id":
                strategy.strategy_id,

            "strategy_name":
                strategy.name,

            "strategy_family":
                strategy.family,

            "config":
                config.to_dict(),

            "bars":
                len(
                    bars
                ),

            "signals_evaluated":
                signals_evaluated,

            "trades":
                tuple(
                    trades
                ),

            "metrics":
                metrics,

            "account":
                account_status,

            "equity_curve":
                equity_curve,

            "research_only":
                True,

            "live_execution":
                False,

            "fill_model":
                "signal_close_to_next_bar_open",

            "intrabar_ambiguity_policy":
                config.ambiguous_bar_policy,
        }


    def run_fyers(
        self,
        symbol,
        strategy,
        config,
        *,
        market="NSE",
        timeframe="5m",
        bars=500,
    ):

        payload = (
            FyersReadOnlyAdapter()
            .history(
                symbol,
                market=market,
                timeframe=timeframe,
                bars=bars,
            )
        )


        normalized = (
            normalize_history_payload(
                payload,
                symbol=symbol,
            )
        )


        return self.run(
            normalized,
            strategy,
            config,
        )


historical_backtester = (
    HistoricalBacktester()
)
