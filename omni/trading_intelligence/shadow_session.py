from __future__ import annotations

import uuid


from omni.trading_intelligence.evidence_ledger import (
    TradingEvidenceLedger,
)

from omni.trading_intelligence.market_freshness import (
    MarketFreshnessGuard,
)

from omni.trading_intelligence.paper_execution import (
    PaperExecutionEngine,
)

from omni.trading_intelligence.paper_performance_summary import (
    paper_performance_summary,
)

from omni.trading_intelligence.shadow_schema import (
    PaperSignal,
)


class ShadowTradingSession:

    def __init__(
        self,
        symbol,
        strategy_ids,
        config,
        *,
        ledger=None,
    ):

        self.session_id = (
            "shadow-"
            + uuid.uuid4()
            .hex[:16]
        )


        self.symbol = str(
            symbol
        )


        self.config = config


        self.strategy_ids = tuple(
            dict.fromkeys(
                str(
                    item
                )

                for item
                in strategy_ids
            )
        )


        if not self.strategy_ids:

            raise ValueError(
                "At least one strategy is required."
            )


        self.freshness = MarketFreshnessGuard(
            config.max_quote_age_seconds,
            config.max_future_skew_seconds,
        )


        self.engines = {
            strategy_id:
                PaperExecutionEngine(
                    config
                )

            for strategy_id
            in self.strategy_ids
        }


        self.ledger = (
            ledger
            or TradingEvidenceLedger()
        )


        self.kill_switch = False

        self.kill_reason = None

        self.last_snapshot = None


    def kill(
        self,
        reason="manual",
    ):

        self.kill_switch = True

        self.kill_reason = str(
            reason
        )


        for engine in self.engines.values():

            engine.kill(
                self.kill_reason
            )


        self.ledger.append(
            "kill_switch",
            {
                "session_id":
                    self.session_id,

                "reason":
                    self.kill_reason,
            },
        )


        return {
            "success":
                True,

            "kill_switch":
                True,

            "reason":
                self.kill_reason,

            "broker_action":
                False,
        }


    def resume(
        self,
    ):

        self.kill_switch = False
        self.kill_reason = None


        for engine in self.engines.values():

            engine.resume()


        self.ledger.append(
            "session_resume",
            {
                "session_id":
                    self.session_id,
            },
        )


        return {
            "success":
                True,

            "kill_switch":
                False,

            "paper_only":
                True,
        }


    def process(
        self,
        snapshot,
        signals,
        *,
        now=None,
    ):

        if snapshot.symbol != self.symbol:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "symbol_mismatch",
            }


        if self.kill_switch:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "kill_switch",
            }


        freshness = self.freshness.check(
            snapshot,
            now=now,
        )


        if not freshness[
            "fresh"
        ]:

            self.ledger.append(
                "stale_market_data",
                {
                    "session_id":
                        self.session_id,

                    "symbol":
                        snapshot.symbol,

                    "freshness":
                        freshness,
                },
            )


            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    freshness[
                        "reason"
                    ],

                "freshness":
                    freshness,

                "virtual_execution":
                    False,
            }


        self.last_snapshot = snapshot


        signal_map = {}


        for item in signals:

            if isinstance(
                item,
                PaperSignal,
            ):

                signal = item


            else:

                signal = PaperSignal(
                    strategy_id=
                        item[
                            "strategy_id"
                        ],

                    symbol=
                        item.get(
                            "symbol",
                            self.symbol,
                        ),

                    signal=
                        item[
                            "signal"
                        ],

                    timestamp=
                        item.get(
                            "timestamp",
                            snapshot.timestamp,
                        ),

                    confidence=
                        item.get(
                            "confidence",
                            1.0,
                        ),

                    metadata=
                        item.get(
                            "metadata",
                            {},
                        ),
                )


            if signal.symbol != self.symbol:

                raise ValueError(
                    "Signal symbol mismatch."
                )


            signal_map[
                signal.strategy_id
            ] = signal


        results = {}


        for strategy_id in self.strategy_ids:

            signal = signal_map.get(
                strategy_id
            )


            if signal is None:

                continue


            engine = self.engines[
                strategy_id
            ]


            result = engine.on_signal(
                snapshot,
                signal.signal,
            )


            results[
                strategy_id
            ] = result


            self.ledger.append(
                "paper_signal",
                {
                    "session_id":
                        self.session_id,

                    "strategy_id":
                        strategy_id,

                    "symbol":
                        self.symbol,

                    "signal":
                        signal.signal,

                    "result":
                        result,
                },
            )


        return {
            "success":
                True,

            "session_id":
                self.session_id,

            "symbol":
                self.symbol,

            "freshness":
                freshness,

            "results":
                results,

            "paper_only":
                True,

            "broker_order":
                False,
        }


    def summary(
        self,
    ):

        return paper_performance_summary(
            {
                strategy_id:
                    tuple(
                        engine.trades
                    )

                for strategy_id, engine
                in self.engines.items()
            }
        )


    def status(
        self,
    ):

        return {
            "session_id":
                self.session_id,

            "symbol":
                self.symbol,

            "strategies":
                self.strategy_ids,

            "kill_switch":
                self.kill_switch,

            "kill_reason":
                self.kill_reason,

            "last_snapshot":
                (
                    self.last_snapshot.to_dict()

                    if self.last_snapshot
                    is not None

                    else None
                ),

            "engines": {
                strategy_id:
                    engine.status()

                for strategy_id, engine
                in self.engines.items()
            },

            "paper_only":
                True,

            "live_execution":
                False,
        }
