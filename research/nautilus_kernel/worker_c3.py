from __future__ import annotations

import argparse
import json
import math
import sys

from collections import (
    defaultdict,
)

from decimal import (
    Decimal,
)

from pathlib import (
    Path,
)


import pandas as pd


HERE = Path(__file__).resolve().parent

if str(HERE) not in sys.path:

    sys.path.insert(
        0,
        str(HERE),
    )


from worker_c2 import (
    ReplayConfig,
    ReplayStrategy,
    build_execution_models,
    describe_instrument,
    frame_records,
    instrument_currency,
    make_instrument,
    normalize_payload,
    numeric_money,
)


from nautilus_trader.backtest.config import (
    BacktestEngineConfig,
)

from nautilus_trader.backtest.engine import (
    BacktestEngine,
)

from nautilus_trader.config import (
    LoggingConfig,
)

from nautilus_trader.model.data import (
    BarType,
)

from nautilus_trader.model.enums import (
    AccountType,
    OmsType,
)

from nautilus_trader.model.identifiers import (
    TraderId,
)

from nautilus_trader.model.objects import (
    Money,
)

from nautilus_trader.persistence.wranglers import (
    BarDataWrangler,
)


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


MAX_STRATEGIES = 20

MAX_TOTAL_BARS = 500000


def quantity_multiplier(
    instrument,
):

    try:

        value = instrument.multiplier

    except Exception:

        return 1.0


    if value is None:

        return 1.0


    number = numeric_money(
        value
    )


    return (
        float(number)

        if number is not None

        else 1.0
    )


def validate_slots(
    payload,
):

    strategies = list(
        payload.get(
            "strategies",
            ()
        )
    )


    if not strategies:

        raise ValueError(
            "At least one portfolio strategy is required."
        )


    if len(
        strategies
    ) > MAX_STRATEGIES:

        raise ValueError(
            "Too many portfolio strategies."
        )


    slot_ids = []


    for index, slot in enumerate(
        strategies
    ):

        slot_id = str(
            slot.get(
                "slot_id",
                "slot_"
                + str(
                    index
                ),
            )
        )


        if not slot_id:

            raise ValueError(
                "slot_id cannot be empty."
            )


        slot_ids.append(
            slot_id
        )


    if len(
        set(
            slot_ids
        )
    ) != len(
        slot_ids
    ):

        raise ValueError(
            "Duplicate slot_id."
        )


    return strategies


def instrument_row_matches(
    row,
    instrument_id,
):

    target = str(
        instrument_id
    )


    for value in row.values():

        if str(
            value
        ) == target:

            return True


    return False


def realized_pnl(
    rows,
):

    values = []


    for row in rows:

        if not isinstance(
            row,
            dict,
        ):

            continue


        for key, value in row.items():

            normalized = (
                str(
                    key
                )
                .lower()
                .replace(
                    " ",
                    "_",
                )
            )


            if normalized in {
                "realized_pnl",
                "realizedpnl",
            }:

                number = numeric_money(
                    value
                )


                if number is not None:

                    values.append(
                        float(
                            number
                        )
                    )


    if not values:

        return None


    return sum(
        values
    )


def finite_or_none(
    value,
):

    if value is None:

        return None


    value = float(
        value
    )


    if not math.isfinite(
        value
    ):

        return None


    return value


def correlation_analysis(
    slot_rows,
):

    series = {}


    for slot_id, rows in (
        slot_rows.items()
    ):

        if len(
            rows
        ) < 3:

            continue


        index = pd.to_datetime(
            [
                row[
                    "timestamp"
                ]

                for row in rows
            ],
            utc=True,
        )


        close = pd.Series(
            [
                float(
                    row[
                        "close"
                    ]
                )

                for row in rows
            ],
            index=index,
            dtype=float,
        )


        series[
            slot_id
        ] = close.pct_change()


    if not series:

        return {
            "matrix":
                {},

            "max_absolute_pair":
                None,

            "research_only":
                True,
        }


    frame = pd.concat(
        series,
        axis=1,
    )


    matrix_frame = frame.corr(
        min_periods=2
    )


    matrix = {}


    max_pair = None

    max_abs = -1.0


    for left in matrix_frame.columns:

        matrix[
            str(
                left
            )
        ] = {}


        for right in matrix_frame.columns:

            value = finite_or_none(
                matrix_frame.loc[
                    left,
                    right,
                ]
            )


            matrix[
                str(
                    left
                )
            ][
                str(
                    right
                )
            ] = value


            if (
                left != right
                and value is not None
                and abs(
                    value
                ) > max_abs
            ):

                max_abs = abs(
                    value
                )


                max_pair = {
                    "left":
                        str(
                            left
                        ),

                    "right":
                        str(
                            right
                        ),

                    "correlation":
                        value,
                }


    return {
        "matrix":
            matrix,

        "max_absolute_pair":
            max_pair,

        "research_only":
            True,
    }


def concentration_analysis(
    prepared,
    *,
    warning_threshold=0.50,
):

    notionals = {}


    for item in prepared:

        last_close = float(
            item[
                "bars_input"
            ][
                -1
            ][
                "close"
            ]
        )


        quantity = float(
            item[
                "quantity"
            ]
        )


        multiplier = (
            quantity_multiplier(
                item[
                    "instrument"
                ]
            )
        )


        notional = abs(
            last_close
            * quantity
            * multiplier
        )


        notionals[
            item[
                "slot_id"
            ]
        ] = notional


    total = sum(
        notionals.values()
    )


    shares = {
        slot_id:
            (
                value
                / total

                if total > 0

                else 0.0
            )

        for slot_id, value
        in notionals.items()
    }


    hhi = sum(
        share
        * share

        for share in shares.values()
    )


    max_slot = (
        max(
            shares,
            key=shares.get,
        )

        if shares

        else None
    )


    max_share = (
        shares[
            max_slot
        ]

        if max_slot
        is not None

        else 0.0
    )


    return {
        "input_notional_proxy":
            notionals,

        "shares":
            shares,

        "total_input_notional_proxy":
            total,

        "hhi":
            hhi,

        "largest_slot":
            max_slot,

        "largest_share":
            max_share,

        "warning_threshold":
            float(
                warning_threshold
            ),

        "concentration_warning":
            (
                max_share
                > float(
                    warning_threshold
                )
            ),

        "actual_dynamic_exposure":
            False,

        "research_only":
            True,
    }


def signal_proxy_series(
    bars_input,
    signals,
    *,
    quantity,
    multiplier,
    allow_short,
):

    position = 0

    previous_close = None

    series = []


    for row, signal in zip(
        bars_input,
        signals,
    ):

        close = float(
            row[
                "close"
            ]
        )


        pnl = 0.0


        if previous_close is not None:

            pnl = (
                (
                    close
                    - previous_close
                )
                * position
                * float(
                    quantity
                )
                * float(
                    multiplier
                )
            )


        series.append(
            (
                row[
                    "timestamp"
                ],
                pnl,
            )
        )


        if signal == "EXIT":

            position = 0


        elif signal == "LONG":

            if position == 0:

                position = 1


            elif position == -1:

                # Close only.
                position = 0


        elif (
            signal == "SHORT"
            and allow_short
        ):

            if position == 0:

                position = -1


            elif position == 1:

                position = 0


        previous_close = close


    return tuple(
        series
    )


def drawdown_attribution(
    prepared,
    initial_capital,
):

    slot_maps = {}

    all_times = set()


    for item in prepared:

        multiplier = (
            quantity_multiplier(
                item[
                    "instrument"
                ]
            )
        )


        proxy = signal_proxy_series(
            item[
                "bars_input"
            ],

            item[
                "signals"
            ],

            quantity=
                item[
                    "quantity"
                ],

            multiplier=
                multiplier,

            allow_short=
                (
                    item[
                        "kind"
                    ]
                    != "option"
                ),
        )


        mapping = {
            timestamp:
                pnl

            for timestamp, pnl
            in proxy
        }


        slot_maps[
            item[
                "slot_id"
            ]
        ] = mapping


        all_times.update(
            mapping
        )


    timestamps = sorted(
        all_times,
        key=pd.Timestamp,
    )


    equity = float(
        initial_capital
    )


    peak = equity

    peak_index = 0

    max_drawdown = 0.0

    max_drawdown_pct = 0.0

    trough_index = 0

    current_peak_index = 0

    portfolio_pnl = []

    per_slot_total = {
        slot_id:
            0.0

        for slot_id
        in slot_maps
    }


    for index, timestamp in enumerate(
        timestamps
    ):

        pnl = 0.0


        for slot_id, mapping in (
            slot_maps.items()
        ):

            value = float(
                mapping.get(
                    timestamp,
                    0.0,
                )
            )


            pnl += value

            per_slot_total[
                slot_id
            ] += value


        portfolio_pnl.append(
            pnl
        )


        equity += pnl


        if equity > peak:

            peak = equity

            current_peak_index = index


        drawdown = (
            peak
            - equity
        )


        drawdown_pct = (
            drawdown
            / peak

            if peak > 0

            else 0.0
        )


        if drawdown > max_drawdown:

            max_drawdown = (
                drawdown
            )

            max_drawdown_pct = (
                drawdown_pct
            )

            peak_index = (
                current_peak_index
            )

            trough_index = index


    contribution = {
        slot_id:
            0.0

        for slot_id
        in slot_maps
    }


    if timestamps:

        start = max(
            0,
            peak_index + 1,
        )


        end = min(
            len(
                timestamps
            ),
            trough_index + 1,
        )


        for timestamp in timestamps[
            start:end
        ]:

            for slot_id, mapping in (
                slot_maps.items()
            ):

                contribution[
                    slot_id
                ] += float(
                    mapping.get(
                        timestamp,
                        0.0,
                    )
                )


    return {
        "proxy":
            True,

        "engine_accounting":
            False,

        "method":
            "signal_path_mark_to_market_proxy",

        "max_drawdown":
            max_drawdown,

        "max_drawdown_pct":
            max_drawdown_pct,

        "peak_timestamp":
            (
                timestamps[
                    peak_index
                ]

                if timestamps

                else None
            ),

        "trough_timestamp":
            (
                timestamps[
                    trough_index
                ]

                if timestamps

                else None
            ),

        "drawdown_window_contribution":
            contribution,

        "slot_total_proxy_pnl":
            per_slot_total,

        "portfolio_total_proxy_pnl":
            sum(
                per_slot_total.values()
            ),

        "research_only":
            True,
    }


def prepare_portfolio(
    payload,
):

    strategies = validate_slots(
        payload
    )


    portfolio_venue = str(
        payload.get(
            "portfolio_venue",
            "SIM",
        )
    )


    prepared = []

    currencies = set()

    instrument_ids = set()

    total_bars = 0


    for index, slot in enumerate(
        strategies
    ):

        slot_id = str(
            slot.get(
                "slot_id",
                "slot_"
                + str(
                    index
                ),
            )
        )


        instrument_spec = dict(
            slot[
                "instrument"
            ]
        )


        requested_venue = str(
            instrument_spec.get(
                "venue",
                portfolio_venue,
            )
        )


        if requested_venue != portfolio_venue:

            raise ValueError(
                "Unified C3 portfolio requires one venue. "
                "Expected "
                + portfolio_venue
                + ", got "
                + requested_venue
                + "."
            )


        instrument_spec[
            "venue"
        ] = portfolio_venue


        bars_input, signals = (
            normalize_payload(
                {
                    "bars":
                        slot[
                            "bars"
                        ],

                    "signals":
                        slot[
                            "signals"
                        ],
                }
            )
        )


        total_bars += len(
            bars_input
        )


        if total_bars > MAX_TOTAL_BARS:

            raise ValueError(
                "Portfolio exceeds total bar limit."
            )


        kind, instrument = (
            make_instrument(
                instrument_spec
            )
        )


        if (
            kind == "option"
            and "SHORT" in signals
        ):

            raise PermissionError(
                "Single-leg option short simulation is blocked."
            )


        instrument_id = str(
            instrument.id
        )


        if instrument_id in instrument_ids:

            raise ValueError(
                "C3 requires unique instruments per strategy slot "
                "for clean attribution."
            )


        instrument_ids.add(
            instrument_id
        )


        currency = str(
            instrument_currency(
                instrument
            )
        )


        currencies.add(
            currency
        )


        quantity = Decimal(
            str(
                slot.get(
                    "quantity",
                    1,
                )
            )
        )


        if quantity <= 0:

            raise ValueError(
                "quantity must be positive."
            )


        bar_type = (
            BarType.from_str(
                instrument_id
                + "-1-MINUTE-LAST-EXTERNAL"
            )
        )


        frame = pd.DataFrame(
            {
                "open":
                    [
                        row[
                            "open"
                        ]

                        for row
                        in bars_input
                    ],

                "high":
                    [
                        row[
                            "high"
                        ]

                        for row
                        in bars_input
                    ],

                "low":
                    [
                        row[
                            "low"
                        ]

                        for row
                        in bars_input
                    ],

                "close":
                    [
                        row[
                            "close"
                        ]

                        for row
                        in bars_input
                    ],
            },
            index=pd.to_datetime(
                [
                    row[
                        "timestamp"
                    ]

                    for row
                    in bars_input
                ],
                utc=True,
            ),
        )


        nautilus_bars = (
            BarDataWrangler(
                bar_type,
                instrument,
            )
            .process(
                frame
            )
        )


        prepared.append(
            {
                "slot_id":
                    slot_id,

                "kind":
                    kind,

                "instrument":
                    instrument,

                "bars_input":
                    bars_input,

                "signals":
                    signals,

                "quantity":
                    quantity,

                "bar_type":
                    bar_type,

                "nautilus_bars":
                    nautilus_bars,
            }
        )


    if len(
        currencies
    ) != 1:

        raise ValueError(
            "Unified C3 portfolio currently requires "
            "one settlement/base currency."
        )


    return (
        prepared,
        portfolio_venue,
        currencies.pop(),
    )


def run_portfolio(
    payload,
):

    prepared, portfolio_venue, currency_code = (
        prepare_portfolio(
            payload
        )
    )


    initial_capital = float(
        payload.get(
            "initial_capital",
            100000.0,
        )
    )


    if initial_capital <= 0:

        raise ValueError(
            "initial_capital must be positive."
        )


    currency = (
        instrument_currency(
            prepared[
                0
            ][
                "instrument"
            ]
        )
    )


    execution = (
        build_execution_models(
            payload.get(
                "execution",
                {
                    "name":
                        "ideal"
                },
            ),
            currency,
        )
    )


    engine = BacktestEngine(
        config=
            BacktestEngineConfig(
                trader_id=
                    TraderId(
                        "JARVIS-C3-001"
                    ),

                logging=
                    LoggingConfig(
                        log_level=
                            "ERROR"
                    ),
            )
    )


    strategies_runtime = []


    try:

        engine.add_venue(
            venue=
                prepared[
                    0
                ][
                    "instrument"
                ]
                .id
                .venue,

            oms_type=
                OmsType.NETTING,

            account_type=
                AccountType.MARGIN,

            starting_balances=[
                Money(
                    initial_capital,
                    currency,
                )
            ],

            base_currency=
                currency,

            default_leverage=
                Decimal(
                    str(
                        payload.get(
                            "leverage",
                            1,
                        )
                    )
                ),

            fill_model=
                execution[
                    "fill_model"
                ],

            fee_model=
                execution[
                    "fee_model"
                ],

            latency_model=
                execution[
                    "latency_model"
                ],

            bar_execution=
                True,

            trade_execution=
                True,

            use_reduce_only=
                True,
        )


        # Register all instruments first.
        for item in prepared:

            engine.add_instrument(
                item[
                    "instrument"
                ]
            )


        # Defer sorting until all instruments are loaded.
        for item in prepared:

            engine.add_data(
                item[
                    "nautilus_bars"
                ],
                sort=False,
            )


        engine.sort_data()


        # Multiple strategy instances share this one BacktestEngine.
        # Nautilus registration assigns unique numeric tags.
        for item in prepared:

            strategy = ReplayStrategy(
                ReplayConfig(
                    instrument_id=
                        item[
                            "instrument"
                        ].id,

                    bar_type=
                        item[
                            "bar_type"
                        ],

                    trade_size=
                        item[
                            "quantity"
                        ],

                    allow_short=
                        (
                            item[
                                "kind"
                            ]
                            != "option"
                        ),
                ),
                item[
                    "signals"
                ],
            )


            engine.add_strategy(
                strategy
            )


            strategies_runtime.append(
                strategy
            )


        engine.run()


        fills = frame_records(
            engine.trader
            .generate_order_fills_report()
        )


        positions = frame_records(
            engine.trader
            .generate_positions_report()
        )


        accounts = frame_records(
            engine.trader
            .generate_account_report(
                prepared[
                    0
                ][
                    "instrument"
                ]
                .id
                .venue
            )
        )


        per_instrument = {}


        for item in prepared:

            instrument_id = str(
                item[
                    "instrument"
                ].id
            )


            instrument_fills = [
                row

                for row in fills

                if instrument_row_matches(
                    row,
                    instrument_id,
                )
            ]


            instrument_positions = [
                row

                for row in positions

                if instrument_row_matches(
                    row,
                    instrument_id,
                )
            ]


            per_instrument[
                item[
                    "slot_id"
                ]
            ] = {
                "instrument":
                    describe_instrument(
                        item[
                            "kind"
                        ],
                        item[
                            "instrument"
                        ],
                    ),

                "fill_count":
                    len(
                        instrument_fills
                    ),

                "position_report_rows":
                    len(
                        instrument_positions
                    ),

                "realized_pnl_numeric":
                    realized_pnl(
                        instrument_positions
                    ),
            }


        slot_rows = {
            item[
                "slot_id"
            ]:
                item[
                    "bars_input"
                ]

            for item in prepared
        }


        correlation = (
            correlation_analysis(
                slot_rows
            )
        )


        concentration = (
            concentration_analysis(
                prepared,
                warning_threshold=
                    float(
                        payload.get(
                            "concentration_warning_threshold",
                            0.50,
                        )
                    ),
            )
        )


        attribution = (
            drawdown_attribution(
                prepared,
                initial_capital,
            )
        )


        runtime_ids = []


        for strategy in strategies_runtime:

            try:

                runtime_ids.append(
                    str(
                        strategy.id
                    )
                )

            except Exception:

                runtime_ids.append(
                    type(
                        strategy
                    ).__name__
                )


        return {
            "success":
                True,

            "engine":
                "BacktestEngine",

            "single_engine":
                True,

            "portfolio_venue":
                portfolio_venue,

            "base_currency":
                currency_code,

            "strategy_count":
                len(
                    prepared
                ),

            "instrument_count":
                len(
                    prepared
                ),

            "runtime_strategy_ids":
                tuple(
                    runtime_ids
                ),

            "execution": {
                "name":
                    execution[
                        "name"
                    ],

                "fill_model":
                    execution[
                        "fill_model_type"
                    ],

                "fee_model":
                    execution[
                        "fee_model_type"
                    ],

                "latency_model":
                    execution[
                        "latency_model_type"
                    ],

                "prob_slippage":
                    execution[
                        "prob_slippage"
                    ],

                "base_latency_nanos":
                    execution[
                        "base_latency_nanos"
                    ],
            },

            "fill_count":
                len(
                    fills
                ),

            "position_report_rows":
                len(
                    positions
                ),

            "realized_pnl_numeric":
                realized_pnl(
                    positions
                ),

            "per_instrument":
                per_instrument,

            "correlation":
                correlation,

            "concentration":
                concentration,

            "drawdown_attribution":
                attribution,

            "account_report":
                accounts,

            "fills":
                fills,

            "positions":
                positions,

            "timing_semantics": {
                "engine":
                    "nautilus_event_driven",

                "same_bar_exact_v2_equivalence":
                    False,
            },

            "paper_only":
                True,

            "research_only":
                True,

            "live_execution":
                False,

            "trading_node":
                False,

            "broker_adapter":
                False,

            "network_request":
                False,
        }


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


    def dataset(
        base,
        step,
        spread,
        *,
        option=False,
    ):

        bars = []

        signals = []


        for index in range(
            100
        ):

            price = (
                base
                + index
                * step
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


            if index == 20:

                signal = "LONG"


            elif index == 45:

                signal = "EXIT"


            elif (
                not option
                and index == 60
            ):

                signal = "SHORT"


            elif (
                not option
                and index == 85
            ):

                signal = "EXIT"


            signals.append(
                signal
            )


        return (
            bars,
            signals,
        )


    equity_bars, equity_signals = (
        dataset(
            100,
            0.10,
            0.50,
        )
    )


    future_bars, future_signals = (
        dataset(
            75,
            0.05,
            0.30,
        )
    )


    option_bars, option_signals = (
        dataset(
            10,
            0.04,
            0.20,
            option=True,
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

            {
                "slot_id":
                    "option_alpha",

                "instrument": {
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

                    "currency":
                        "USD",

                    "option_kind":
                        "CALL",

                    "strike":
                        "150",

                    "multiplier":
                        "100",

                    "expiration":
                        "2026-12-18T21:00:00Z",
                },

                "bars":
                    option_bars,

                "signals":
                    option_signals,

                "quantity":
                    1,
            },
        ),
    }


def main():

    parser = argparse.ArgumentParser()


    parser.add_argument(
        "--self-test",
        action="store_true",
    )


    parser.add_argument(
        "--input",
    )


    parser.add_argument(
        "--output",
    )


    args = parser.parse_args()


    if args.self_test:

        result = run_portfolio(
            self_test_payload()
        )


        if result[
            "strategy_count"
        ] != 3:

            raise RuntimeError(
                "Multi-strategy registration failed."
            )


        if result[
            "instrument_count"
        ] != 3:

            raise RuntimeError(
                "Multi-instrument registration failed."
            )


        if result[
            "fill_count"
        ] < 6:

            raise RuntimeError(
                "Portfolio generated too few simulated fills."
            )


        if not result[
            "correlation"
        ][
            "matrix"
        ]:

            raise RuntimeError(
                "Correlation analysis failed."
            )


        print(
            json.dumps(
                {
                    "success":
                        True,

                    "strategy_count":
                        result[
                            "strategy_count"
                        ],

                    "instrument_count":
                        result[
                            "instrument_count"
                        ],

                    "runtime_strategy_ids":
                        result[
                            "runtime_strategy_ids"
                        ],

                    "fill_count":
                        result[
                            "fill_count"
                        ],

                    "correlation":
                        result[
                            "correlation"
                        ],

                    "concentration":
                        result[
                            "concentration"
                        ],

                    "drawdown_attribution":
                        result[
                            "drawdown_attribution"
                        ],

                    "live_execution":
                        result[
                            "live_execution"
                        ],

                    "broker_adapter":
                        result[
                            "broker_adapter"
                        ],
                },
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


    result = run_portfolio(
        payload
    )


    Path(
        args.output
    ).write_text(
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
