from __future__ import annotations

import argparse
import json
import sys

from decimal import (
    Decimal,
)

from importlib.metadata import (
    version,
)

from pathlib import (
    Path,
)


import pandas as pd


from nautilus_trader.backtest.config import (
    BacktestEngineConfig,
)

from nautilus_trader.backtest.engine import (
    BacktestEngine,
)

from nautilus_trader.config import (
    LoggingConfig,
    StrategyConfig,
)

from nautilus_trader.model.currencies import (
    USD,
)

from nautilus_trader.model.data import (
    Bar,
    BarType,
)

from nautilus_trader.model.enums import (
    AccountType,
    OmsType,
    OrderSide,
)

from nautilus_trader.model.identifiers import (
    InstrumentId,
    TraderId,
)

from nautilus_trader.model.objects import (
    Money,
)

from nautilus_trader.persistence.wranglers import (
    BarDataWrangler,
)

from nautilus_trader.test_kit.providers import (
    TestInstrumentProvider,
)

from nautilus_trader.trading.strategy import (
    Strategy,
)


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


class JarvisReplayConfig(
    StrategyConfig,
    frozen=True,
):

    instrument_id: InstrumentId

    bar_type: BarType

    trade_size: Decimal


class JarvisReplayStrategy(
    Strategy,
):

    def __init__(
        self,
        config,
        signals,
    ):

        super().__init__(
            config
        )

        self._signals = tuple(
            signals
        )

        self._bar_index = 0


    def on_start(
        self,
    ):

        self.subscribe_bars(
            self.config.bar_type
        )


    def _instrument(
        self,
    ):

        instrument = (
            self.cache.instrument(
                self.config.instrument_id
            )
        )


        if instrument is None:

            raise RuntimeError(
                "Instrument missing from Nautilus cache."
            )


        return instrument


    def _buy(
        self,
    ):

        instrument = (
            self._instrument()
        )


        order = (
            self.order_factory.market(
                self.config.instrument_id,
                OrderSide.BUY,
                instrument.make_qty(
                    self.config.trade_size
                ),
            )
        )


        self.submit_order(
            order
        )


    def _sell(
        self,
    ):

        instrument = (
            self._instrument()
        )


        order = (
            self.order_factory.market(
                self.config.instrument_id,
                OrderSide.SELL,
                instrument.make_qty(
                    self.config.trade_size
                ),
            )
        )


        self.submit_order(
            order
        )


    def on_bar(
        self,
        bar: Bar,
    ):

        index = self._bar_index

        self._bar_index += 1


        if index >= len(
            self._signals
        ):

            return


        signal = self._signals[
            index
        ]


        if signal == "FLAT":

            return


        instrument_id = (
            self.config.instrument_id
        )


        if signal == "EXIT":

            if not self.portfolio.is_flat(
                instrument_id
            ):

                self.close_all_positions(
                    instrument_id
                )

            return


        if signal == "LONG":

            if self.portfolio.is_flat(
                instrument_id
            ):

                self._buy()

            elif self.portfolio.is_net_short(
                instrument_id
            ):

                # Deliberately close only.
                # No same-bar reversal.
                self.close_all_positions(
                    instrument_id
                )

            return


        if signal == "SHORT":

            if self.portfolio.is_flat(
                instrument_id
            ):

                self._sell()

            elif self.portfolio.is_net_long(
                instrument_id
            ):

                self.close_all_positions(
                    instrument_id
                )

            return


def frame_records(
    frame,
):

    if frame is None:

        return []


    try:

        frame = frame.reset_index()

    except Exception:

        pass


    try:

        return json.loads(
            frame.to_json(
                orient="records",
                date_format="iso",
            )
        )

    except Exception:

        return [
            {
                "repr":
                    str(
                        frame
                    )
            }
        ]


def result_summary(
    result,
):

    output = {
        "type":
            type(
                result
            ).__name__,

        "repr":
            str(
                result
            ),
    }


    for name in (
        "run_config_id",
        "instance_id",
        "total_events",
        "total_orders",
        "total_positions",
        "elapsed_time",
    ):

        try:

            value = getattr(
                result,
                name
            )

        except Exception:

            continue


        if callable(
            value
        ):

            continue


        output[
            name
        ] = value


    return output


def normalize_payload(
    payload,
):

    bars = list(
        payload.get(
            "bars",
            ()
        )
    )


    signals = list(
        payload.get(
            "signals",
            ()
        )
    )


    if len(
        bars
    ) < 10:

        raise ValueError(
            "At least 10 bars are required."
        )


    if len(
        bars
    ) != len(
        signals
    ):

        raise ValueError(
            "bars and signals must have equal length."
        )


    normalized = []


    for bar, signal in zip(
        bars,
        signals,
    ):

        signal = str(
            signal
        ).strip().upper()


        if signal not in ALLOWED_SIGNALS:

            raise ValueError(
                "Unsupported signal: "
                + signal
            )


        normalized.append(
            (
                {
                    "timestamp":
                        str(
                            bar[
                                "timestamp"
                            ]
                        ),

                    "open":
                        float(
                            bar[
                                "open"
                            ]
                        ),

                    "high":
                        float(
                            bar[
                                "high"
                            ]
                        ),

                    "low":
                        float(
                            bar[
                                "low"
                            ]
                        ),

                    "close":
                        float(
                            bar[
                                "close"
                            ]
                        ),
                },
                signal,
            )
        )


    normalized.sort(
        key=lambda item:
            pd.Timestamp(
                item[
                    0
                ][
                    "timestamp"
                ]
            )
    )


    return (
        [
            item[
                0
            ]

            for item
            in normalized
        ],
        [
            item[
                1
            ]

            for item
            in normalized
        ],
    )


def run_backtest(
    payload,
):

    bars_input, signals = (
        normalize_payload(
            payload
        )
    )


    initial_capital = float(
        payload.get(
            "initial_capital",
            100000.0,
        )
    )


    quantity = Decimal(
        str(
            payload.get(
                "quantity",
                1000,
            )
        )
    )


    if initial_capital <= 0:

        raise ValueError(
            "initial_capital must be positive."
        )


    if quantity <= 0:

        raise ValueError(
            "quantity must be positive."
        )


    instrument = (
        TestInstrumentProvider
        .default_fx_ccy(
            "EUR/USD"
        )
    )


    venue = (
        instrument.id.venue
    )


    bar_type = BarType.from_str(
        str(
            instrument.id
        )
        + "-1-MINUTE-LAST-EXTERNAL"
    )


    index = pd.to_datetime(
        [
            item[
                "timestamp"
            ]

            for item
            in bars_input
        ],
        utc=True,
    )


    dataframe = pd.DataFrame(
        {
            "open":
                [
                    item[
                        "open"
                    ]

                    for item
                    in bars_input
                ],

            "high":
                [
                    item[
                        "high"
                    ]

                    for item
                    in bars_input
                ],

            "low":
                [
                    item[
                        "low"
                    ]

                    for item
                    in bars_input
                ],

            "close":
                [
                    item[
                        "close"
                    ]

                    for item
                    in bars_input
                ],
        },
        index=index,
    )


    nautilus_bars = (
        BarDataWrangler(
            bar_type,
            instrument,
        )
        .process(
            dataframe
        )
    )


    engine = BacktestEngine(
        config=
            BacktestEngineConfig(
                trader_id=
                    TraderId(
                        "JARVIS-BACKTESTER-001"
                    ),

                logging=
                    LoggingConfig(
                        log_level=
                            "ERROR"
                    ),
            )
    )


    try:

        engine.add_venue(
            venue=
                venue,

            oms_type=
                OmsType.NETTING,

            account_type=
                AccountType.MARGIN,

            starting_balances=[
                Money(
                    initial_capital,
                    USD,
                )
            ],

            base_currency=
                USD,

            default_leverage=
                Decimal(
                    "1"
                ),

            bar_execution=
                True,

            trade_execution=
                True,
        )


        engine.add_instrument(
            instrument
        )


        engine.add_data(
            nautilus_bars
        )


        strategy = (
            JarvisReplayStrategy(
                JarvisReplayConfig(
                    instrument_id=
                        instrument.id,

                    bar_type=
                        bar_type,

                    trade_size=
                        quantity,
                ),
                signals,
            )
        )


        engine.add_strategy(
            strategy
        )


        engine.run()


        account = frame_records(
            engine.trader
            .generate_account_report(
                venue
            )
        )


        fills = frame_records(
            engine.trader
            .generate_order_fills_report()
        )


        positions = frame_records(
            engine.trader
            .generate_positions_report()
        )


        result = (
            engine.get_result()
        )


        output = {
            "success":
                True,

            "kernel":
                "nautilustrader",

            "nautilus_version":
                version(
                    "nautilus_trader"
                ),

            "engine":
                "BacktestEngine",

            "instrument_id":
                str(
                    instrument.id
                ),

            "venue":
                str(
                    venue
                ),

            "bar_type":
                str(
                    bar_type
                ),

            "bars":
                len(
                    nautilus_bars
                ),

            "signals":
                len(
                    signals
                ),

            "fill_count":
                len(
                    fills
                ),

            "position_report_rows":
                len(
                    positions
                ),

            "account_report":
                account,

            "fills":
                fills,

            "positions":
                positions,

            "engine_result":
                result_summary(
                    result
                ),

            "paper_only":
                True,

            "research_only":
                True,

            "live_execution":
                False,

            "broker_adapter":
                False,

            "trading_node":
                False,

            "network_request":
                False,
        }


        return output


    finally:

        try:
            engine.dispose()

        except Exception:
            pass


def self_test_payload():

    from datetime import (
        datetime,
        timedelta,
        timezone,
    )


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
        140
    ):

        base = (
            1.1000
            + index
            * 0.00005
        )


        bars.append(
            {
                "timestamp":
                    (
                        start
                        + timedelta(
                            minutes=index
                        )
                    ).isoformat(),

                "open":
                    base,

                "high":
                    base
                    + 0.0004,

                "low":
                    base
                    - 0.0004,

                "close":
                    base
                    + 0.0001,
            }
        )


        signal = "FLAT"


        if index == 30:
            signal = "LONG"

        elif index == 60:
            signal = "EXIT"

        elif index == 75:
            signal = "SHORT"

        elif index == 110:
            signal = "EXIT"


        signals.append(
            signal
        )


    return {
        "bars":
            bars,

        "signals":
            signals,

        "initial_capital":
            100000,

        "quantity":
            1000,
    }


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--version-json",
        action="store_true",
    )

    parser.add_argument(
        "--input",
    )

    parser.add_argument(
        "--output",
    )


    args = parser.parse_args()


    if args.version_json:

        print(
            json.dumps(
                {
                    "available":
                        True,

                    "nautilus_version":
                        version(
                            "nautilus_trader"
                        ),

                    "engine":
                        "BacktestEngine",

                    "paper_only":
                        True,

                    "live_execution":
                        False,

                    "broker_adapter":
                        False,
                }
            )
        )

        return


    if args.self_test:

        result = run_backtest(
            self_test_payload()
        )


        if not result[
            "success"
        ]:

            raise RuntimeError(
                result
            )


        if result[
            "fill_count"
        ] < 2:

            raise RuntimeError(
                "Nautilus self-test produced "
                "too few fills: "
                + str(
                    result[
                        "fill_count"
                    ]
                )
            )


        print(
            json.dumps(
                result,
                default=str,
            )
        )

        return


    if not args.input:

        raise ValueError(
            "--input is required."
        )


    if not args.output:

        raise ValueError(
            "--output is required."
        )


    payload = json.loads(
        Path(
            args.input
        ).read_text(
            encoding="utf-8"
        )
    )


    result = run_backtest(
        payload
    )


    output_path = Path(
        args.output
    )


    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":

    main()
