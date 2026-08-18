from __future__ import annotations

import argparse
import json
import re

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

from nautilus_trader.backtest.models.fee import (
    FixedFeeModel,
    MakerTakerFeeModel,
    PerContractFeeModel,
)

from nautilus_trader.backtest.models.fill import (
    FillModel,
)

from nautilus_trader.backtest.models.latency import (
    LatencyModel,
)

from nautilus_trader.config import (
    LoggingConfig,
    StrategyConfig,
)

from nautilus_trader.model.currencies import (
    Currency,
)

from nautilus_trader.model.data import (
    Bar,
    BarType,
)

from nautilus_trader.model.enums import (
    AccountType,
    AssetClass,
    OmsType,
    OptionKind,
    OrderSide,
)

from nautilus_trader.model.identifiers import (
    InstrumentId,
    Symbol,
    TraderId,
    Venue,
)

from nautilus_trader.model.instruments import (
    FuturesContract,
    OptionContract,
)

from nautilus_trader.model.objects import (
    Money,
    Price,
    Quantity,
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


SUPPORTED_KINDS = {
    "fx",
    "equity",
    "future",
    "commodity_future",
    "option",
}


SUPPORTED_PROFILES = {
    "ideal",
    "one_tick",
    "probabilistic",
    "delayed",
    "stress",
}


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


def timestamp_ns(
    value,
):

    timestamp = pd.Timestamp(
        value
    )


    if timestamp.tzinfo is None:

        timestamp = timestamp.tz_localize(
            "UTC"
        )

    else:

        timestamp = timestamp.tz_convert(
            "UTC"
        )


    return int(
        timestamp.value
    )


def currency_from_code(
    code,
):

    currency = Currency.from_str(
        str(
            code
        ),
        strict=True,
    )


    if currency is None:

        raise ValueError(
            "Unknown currency: "
            + str(
                code
            )
        )


    return currency


def asset_class_from_name(
    value,
):

    name = str(
        value
    ).strip().upper()


    if not hasattr(
        AssetClass,
        name,
    ):

        raise ValueError(
            "Unsupported AssetClass: "
            + name
        )


    return getattr(
        AssetClass,
        name,
    )


def option_kind_from_name(
    value,
):

    name = str(
        value
    ).strip().upper()


    if name in {
        "CE",
        "CALL",
        "C",
    }:

        name = "CALL"


    elif name in {
        "PE",
        "PUT",
        "P",
    }:

        name = "PUT"


    if not hasattr(
        OptionKind,
        name,
    ):

        raise ValueError(
            "Unsupported OptionKind: "
            + name
        )


    return getattr(
        OptionKind,
        name,
    )


def make_future(
    spec,
    *,
    force_commodity=False,
):

    symbol = str(
        spec.get(
            "symbol",
            "ESZ6",
        )
    )


    venue_name = str(
        spec.get(
            "venue",
            "SIM",
        )
    )


    underlying = str(
        spec.get(
            "underlying",
            symbol,
        )
    )


    currency = currency_from_code(
        spec.get(
            "currency",
            "USD",
        )
    )


    asset_name = (
        "COMMODITY"

        if force_commodity

        else spec.get(
            "asset_class",
            "INDEX",
        )
    )


    asset_class = (
        asset_class_from_name(
            asset_name
        )
    )


    activation_ns = timestamp_ns(
        spec.get(
            "activation",
            "2020-01-01T00:00:00Z",
        )
    )


    expiration_ns = timestamp_ns(
        spec.get(
            "expiration",
            "2035-12-31T23:59:59Z",
        )
    )


    if expiration_ns <= activation_ns:

        raise ValueError(
            "Futures expiration must be after activation."
        )


    instrument_id = (
        InstrumentId.from_str(
            str(
                spec.get(
                    "instrument_id",
                    symbol
                    + "."
                    + venue_name,
                )
            )
        )
    )


    kwargs = {
        "instrument_id":
            instrument_id,

        "raw_symbol":
            Symbol(
                str(
                    spec.get(
                        "raw_symbol",
                        symbol,
                    )
                )
            ),

        "asset_class":
            asset_class,

        "currency":
            currency,

        "price_precision":
            int(
                spec.get(
                    "price_precision",
                    2,
                )
            ),

        "price_increment":
            Price.from_str(
                str(
                    spec.get(
                        "price_increment",
                        "0.01",
                    )
                )
            ),

        "multiplier":
            Quantity.from_str(
                str(
                    spec.get(
                        "multiplier",
                        "1",
                    )
                )
            ),

        "lot_size":
            Quantity.from_str(
                str(
                    spec.get(
                        "lot_size",
                        "1",
                    )
                )
            ),

        "underlying":
            underlying,

        "activation_ns":
            activation_ns,

        "expiration_ns":
            expiration_ns,

        "ts_event":
            0,

        "ts_init":
            0,

        "margin_init":
            Decimal(
                str(
                    spec.get(
                        "margin_init",
                        "0",
                    )
                )
            ),

        "margin_maint":
            Decimal(
                str(
                    spec.get(
                        "margin_maint",
                        "0",
                    )
                )
            ),

        "maker_fee":
            Decimal(
                str(
                    spec.get(
                        "maker_fee",
                        "0",
                    )
                )
            ),

        "taker_fee":
            Decimal(
                str(
                    spec.get(
                        "taker_fee",
                        "0",
                    )
                )
            ),
    }


    exchange = spec.get(
        "exchange"
    )


    if exchange is not None:

        kwargs[
            "exchange"
        ] = str(
            exchange
        )


    return FuturesContract(
        **kwargs
    )


def make_option(
    spec,
):

    symbol = str(
        spec.get(
            "symbol",
            "TESTC100",
        )
    )


    venue_name = str(
        spec.get(
            "venue",
            "SIM",
        )
    )


    underlying = str(
        spec.get(
            "underlying",
            "TEST",
        )
    )


    currency = currency_from_code(
        spec.get(
            "currency",
            "USD",
        )
    )


    activation_ns = timestamp_ns(
        spec.get(
            "activation",
            "2020-01-01T00:00:00Z",
        )
    )


    expiration_ns = timestamp_ns(
        spec.get(
            "expiration",
            "2035-12-31T23:59:59Z",
        )
    )


    if expiration_ns <= activation_ns:

        raise ValueError(
            "Option expiration must be after activation."
        )


    if "strike" not in spec:

        raise ValueError(
            "Option strike is required."
        )


    kwargs = {
        "instrument_id":
            InstrumentId.from_str(
                str(
                    spec.get(
                        "instrument_id",
                        symbol
                        + "."
                        + venue_name,
                    )
                )
            ),

        "raw_symbol":
            Symbol(
                str(
                    spec.get(
                        "raw_symbol",
                        symbol,
                    )
                )
            ),

        "asset_class":
            asset_class_from_name(
                spec.get(
                    "asset_class",
                    "EQUITY",
                )
            ),

        "currency":
            currency,

        "price_precision":
            int(
                spec.get(
                    "price_precision",
                    2,
                )
            ),

        "price_increment":
            Price.from_str(
                str(
                    spec.get(
                        "price_increment",
                        "0.01",
                    )
                )
            ),

        "multiplier":
            Quantity.from_str(
                str(
                    spec.get(
                        "multiplier",
                        "1",
                    )
                )
            ),

        "lot_size":
            Quantity.from_str(
                str(
                    spec.get(
                        "lot_size",
                        "1",
                    )
                )
            ),

        "underlying":
            underlying,

        "option_kind":
            option_kind_from_name(
                spec.get(
                    "option_kind",
                    "CALL",
                )
            ),

        "strike_price":
            Price.from_str(
                str(
                    spec[
                        "strike"
                    ]
                )
            ),

        "activation_ns":
            activation_ns,

        "expiration_ns":
            expiration_ns,

        "ts_event":
            0,

        "ts_init":
            0,

        "margin_init":
            Decimal(
                str(
                    spec.get(
                        "margin_init",
                        "0",
                    )
                )
            ),

        "margin_maint":
            Decimal(
                str(
                    spec.get(
                        "margin_maint",
                        "0",
                    )
                )
            ),

        "maker_fee":
            Decimal(
                str(
                    spec.get(
                        "maker_fee",
                        "0",
                    )
                )
            ),

        "taker_fee":
            Decimal(
                str(
                    spec.get(
                        "taker_fee",
                        "0",
                    )
                )
            ),
    }


    exchange = spec.get(
        "exchange"
    )


    if exchange is not None:

        kwargs[
            "exchange"
        ] = str(
            exchange
        )


    return OptionContract(
        **kwargs
    )


def make_instrument(
    spec,
):

    spec = dict(
        spec
    )


    kind = str(
        spec.get(
            "kind",
            "fx",
        )
    ).strip().lower()


    if kind not in SUPPORTED_KINDS:

        raise ValueError(
            "Unsupported instrument kind: "
            + kind
        )


    if kind == "fx":

        symbol = str(
            spec.get(
                "symbol",
                "EUR/USD",
            )
        )


        venue_value = spec.get(
            "venue"
        )


        venue = (
            Venue(
                str(
                    venue_value
                )
            )

            if venue_value
            is not None

            else None
        )


        instrument = (
            TestInstrumentProvider
            .default_fx_ccy(
                symbol,
                venue=venue,
            )
        )


    elif kind == "equity":

        instrument = (
            TestInstrumentProvider
            .equity(
                symbol=
                    str(
                        spec.get(
                            "symbol",
                            "AAPL",
                        )
                    ),

                venue=
                    str(
                        spec.get(
                            "venue",
                            "XNAS",
                        )
                    ),
            )
        )


    elif kind == "future":

        instrument = make_future(
            spec,
            force_commodity=False,
        )


    elif kind == "commodity_future":

        instrument = make_future(
            spec,
            force_commodity=True,
        )


    else:

        instrument = make_option(
            spec
        )


    return (
        kind,
        instrument,
    )


def instrument_currency(
    instrument,
):

    for name in (
        "settlement_currency",
        "quote_currency",
        "currency",
    ):

        try:

            value = getattr(
                instrument,
                name
            )


        except Exception:

            continue


        if value is not None:

            return value


    raise RuntimeError(
        "Unable to determine instrument currency."
    )


def enum_name(
    value,
):

    name = getattr(
        value,
        "name",
        None,
    )


    if name:

        return str(
            name
        )


    return str(
        value
    )


def describe_instrument(
    kind,
    instrument,
):

    output = {
        "research_kind":
            kind,

        "type":
            type(
                instrument
            ).__name__,

        "instrument_id":
            str(
                instrument.id
            ),

        "venue":
            str(
                instrument.id.venue
            ),

        "currency":
            str(
                instrument_currency(
                    instrument
                )
            ),
    }


    for name in (
        "asset_class",
        "instrument_class",
        "underlying",
        "multiplier",
        "lot_size",
        "strike_price",
        "option_kind",
        "expiration_ns",
    ):

        try:

            value = getattr(
                instrument,
                name
            )


        except Exception:

            continue


        if value is not None:

            output[
                name
            ] = enum_name(
                value
            )


    return output


def build_execution_models(
    profile,
    currency,
):

    profile = dict(
        profile
        or {}
    )


    name = str(
        profile.get(
            "name",
            "ideal",
        )
    ).strip().lower()


    if name not in SUPPORTED_PROFILES:

        raise ValueError(
            "Unsupported execution profile: "
            + name
        )


    seed = int(
        profile.get(
            "random_seed",
            42,
        )
    )


    if name == "ideal":

        prob_limit = 1.0
        prob_slippage = 0.0

        default_latency = 0


    elif name == "one_tick":

        prob_limit = 1.0
        prob_slippage = 1.0

        default_latency = 0


    elif name == "probabilistic":

        prob_limit = float(
            profile.get(
                "prob_fill_on_limit",
                0.70,
            )
        )

        prob_slippage = float(
            profile.get(
                "prob_slippage",
                0.25,
            )
        )

        default_latency = 0


    elif name == "delayed":

        prob_limit = 1.0
        prob_slippage = 0.0

        default_latency = int(
            profile.get(
                "base_latency_nanos",
                250_000_000,
            )
        )


    else:

        prob_limit = float(
            profile.get(
                "prob_fill_on_limit",
                0.60,
            )
        )

        prob_slippage = float(
            profile.get(
                "prob_slippage",
                1.0,
            )
        )

        default_latency = int(
            profile.get(
                "base_latency_nanos",
                500_000_000,
            )
        )


    if not 0 <= prob_limit <= 1:

        raise ValueError(
            "prob_fill_on_limit must be between 0 and 1."
        )


    if not 0 <= prob_slippage <= 1:

        raise ValueError(
            "prob_slippage must be between 0 and 1."
        )


    fill_model = FillModel(
        prob_fill_on_limit=
            prob_limit,

        prob_slippage=
            prob_slippage,

        random_seed=
            seed,
    )


    base_latency = int(
        profile.get(
            "base_latency_nanos",
            default_latency,
        )
    )


    latency_model = LatencyModel(
        base_latency_nanos=
            base_latency,

        insert_latency_nanos=
            int(
                profile.get(
                    "insert_latency_nanos",
                    0,
                )
            ),

        update_latency_nanos=
            int(
                profile.get(
                    "update_latency_nanos",
                    0,
                )
            ),

        cancel_latency_nanos=
            int(
                profile.get(
                    "cancel_latency_nanos",
                    0,
                )
            ),
    )


    fee_mode = str(
        profile.get(
            "fee_mode",
            "maker_taker",
        )
    ).strip().lower()


    commission = float(
        profile.get(
            "commission",
            0.0,
        )
    )


    if commission < 0:

        raise ValueError(
            "commission cannot be negative."
        )


    if (
        fee_mode == "fixed"
        and commission > 0
    ):

        fee_model = FixedFeeModel(
            Money(
                commission,
                currency,
            ),

            charge_commission_once=
                bool(
                    profile.get(
                        "charge_commission_once",
                        False,
                    )
                ),
        )


    elif (
        fee_mode == "per_contract"
        and commission >= 0
    ):

        fee_model = (
            PerContractFeeModel(
                Money(
                    commission,
                    currency,
                )
            )
        )


    elif fee_mode == "maker_taker":

        fee_model = (
            MakerTakerFeeModel()
        )


    else:

        raise ValueError(
            "Unsupported fee_mode or invalid commission."
        )


    return {
        "name":
            name,

        "fill_model":
            fill_model,

        "fee_model":
            fee_model,

        "latency_model":
            latency_model,

        "prob_fill_on_limit":
            prob_limit,

        "prob_slippage":
            prob_slippage,

        "base_latency_nanos":
            base_latency,

        "fee_mode":
            fee_mode,

        "commission":
            commission,

        "fill_model_type":
            type(
                fill_model
            ).__name__,

        "fee_model_type":
            type(
                fee_model
            ).__name__,

        "latency_model_type":
            type(
                latency_model
            ).__name__,
    }


class ReplayConfig(
    StrategyConfig,
    frozen=True,
):

    instrument_id: InstrumentId

    bar_type: BarType

    trade_size: Decimal

    allow_short: bool = True


class ReplayStrategy(
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


    def instrument(
        self,
    ):

        instrument = (
            self.cache.instrument(
                self.config.instrument_id
            )
        )


        if instrument is None:

            raise RuntimeError(
                "Instrument missing from cache."
            )


        return instrument


    def buy(
        self,
    ):

        instrument = (
            self.instrument()
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


    def sell(
        self,
    ):

        if not self.config.allow_short:

            return


        instrument = (
            self.instrument()
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

                self.buy()


            elif self.portfolio.is_net_short(
                instrument_id
            ):

                self.close_all_positions(
                    instrument_id
                )

            return


        if signal == "SHORT":

            if not self.config.allow_short:

                return


            if self.portfolio.is_flat(
                instrument_id
            ):

                self.sell()


            elif self.portfolio.is_net_long(
                instrument_id
            ):

                self.close_all_positions(
                    instrument_id
                )


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


def numeric_money(
    value,
):

    if value is None:

        return None


    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        return float(
            value
        )


    match = re.search(
        r"[-+]?\d+(?:\.\d+)?",
        str(
            value
        ).replace(
            ",",
            "",
        ),
    )


    if not match:

        return None


    return float(
        match.group(
            0
        )
    )


def realized_pnl_from_positions(
    positions,
):

    values = []


    for row in positions:

        if not isinstance(
            row,
            dict,
        ):

            continue


        for key, value in (
            row.items()
        ):

            normalized = str(
                key
            ).lower()


            if normalized in {
                "realized_pnl",
                "realizedpnl",
            }:

                number = numeric_money(
                    value
                )


                if number is not None:

                    values.append(
                        number
                    )


    if not values:

        return None


    return sum(
        values
    )


def normalize_payload(
    payload,
):

    bars = list(
        payload.get(
            "bars",
            ()
        )
    )


    signals = [
        str(
            signal
        ).strip().upper()

        for signal
        in payload.get(
            "signals",
            ()
        )
    ]


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
            "bars/signals length mismatch."
        )


    invalid = {
        signal

        for signal in signals

        if signal
        not in ALLOWED_SIGNALS
    }


    if invalid:

        raise ValueError(
            "Unsupported signals: "
            + repr(
                sorted(
                    invalid
                )
            )
        )


    rows = []


    for bar, signal in zip(
        bars,
        signals,
    ):

        rows.append(
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


    rows.sort(
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
            in rows
        ],

        [
            item[
                1
            ]

            for item
            in rows
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


    instrument_spec = dict(
        payload.get(
            "instrument",
            {
                "kind":
                    "fx",

                "symbol":
                    "EUR/USD",
            },
        )
    )


    kind, instrument = (
        make_instrument(
            instrument_spec
        )
    )


    # Single-leg option shorts remain blocked.
    if (
        kind == "option"
        and "SHORT" in signals
    ):

        raise PermissionError(
            "Single-leg option short simulation is blocked. "
            "Use defined-risk spread research."
        )


    initial_capital = float(
        payload.get(
            "initial_capital",
            100000.0,
        )
    )


    trade_size = Decimal(
        str(
            payload.get(
                "quantity",
                1,
            )
        )
    )


    if initial_capital <= 0:

        raise ValueError(
            "initial_capital must be positive."
        )


    if trade_size <= 0:

        raise ValueError(
            "quantity must be positive."
        )


    currency = instrument_currency(
        instrument
    )


    execution = build_execution_models(
        payload.get(
            "execution",
            {
                "name":
                    "ideal"
            },
        ),
        currency,
    )


    bar_type = BarType.from_str(
        str(
            instrument.id
        )
        + "-1-MINUTE-LAST-EXTERNAL"
    )


    index = pd.to_datetime(
        [
            row[
                "timestamp"
            ]

            for row
            in bars_input
        ],
        utc=True,
    )


    dataframe = pd.DataFrame(
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
                        "JARVIS-C2-001"
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
                instrument.id.venue,

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
                            "1",
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


        engine.add_instrument(
            instrument
        )


        engine.add_data(
            nautilus_bars
        )


        strategy = ReplayStrategy(
            ReplayConfig(
                instrument_id=
                    instrument.id,

                bar_type=
                    bar_type,

                trade_size=
                    trade_size,

                allow_short=
                    (
                        kind
                        != "option"
                    ),
            ),
            signals,
        )


        engine.add_strategy(
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
                instrument.id.venue
            )
        )


        realized_pnl = (
            realized_pnl_from_positions(
                positions
            )
        )


        return {
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

            "instrument":
                describe_instrument(
                    kind,
                    instrument,
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

                "prob_fill_on_limit":
                    execution[
                        "prob_fill_on_limit"
                    ],

                "prob_slippage":
                    execution[
                        "prob_slippage"
                    ],

                "base_latency_nanos":
                    execution[
                        "base_latency_nanos"
                    ],

                "fee_mode":
                    execution[
                        "fee_mode"
                    ],

                "commission":
                    execution[
                        "commission"
                    ],
            },

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

            "realized_pnl_numeric":
                realized_pnl,

            "fills":
                fills,

            "positions":
                positions,

            "account_report":
                accounts,

            "timing_semantics": {
                "nautilus":
                    "event_driven_bar_execution",

                "jarvis_v2":
                    "signal_close_to_next_bar_open",

                "direct_equivalence_expected":
                    False,
            },

            "single_leg_option_short":
                False,

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


def self_test_dataset(
    kind,
):

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


    if kind == "fx":

        base = 1.10
        step = 0.0001
        spread = 0.0003

        instrument = {
            "kind":
                "fx",

            "symbol":
                "EUR/USD",
        }

        quantity = 1000


    elif kind == "equity":

        base = 100.0
        step = 0.10
        spread = 0.50

        instrument = {
            "kind":
                "equity",

            "symbol":
                "AAPL",

            "venue":
                "XNAS",
        }

        quantity = 10


    elif kind == "future":

        base = 5000.0
        step = 1.0
        spread = 3.0

        instrument = {
            "kind":
                "future",

            "symbol":
                "ESZ6",

            "venue":
                "SIM",

            "exchange":
                "XCME",

            "underlying":
                "ES",

            "asset_class":
                "INDEX",

            "price_precision":
                2,

            "price_increment":
                "0.25",

            "multiplier":
                "50",

            "lot_size":
                "1",

            "expiration":
                "2026-12-18T21:00:00Z",
        }

        quantity = 1


    elif kind == "commodity_future":

        base = 75.0
        step = 0.05
        spread = 0.30

        instrument = {
            "kind":
                "commodity_future",

            "symbol":
                "CLZ6",

            "venue":
                "SIM",

            "exchange":
                "XNYM",

            "underlying":
                "CL",

            "currency":
                "USD",

            "price_precision":
                2,

            "price_increment":
                "0.01",

            "multiplier":
                "1000",

            "lot_size":
                "1",

            "expiration":
                "2026-11-20T19:30:00Z",
        }

        quantity = 1


    elif kind == "option":

        base = 10.0
        step = 0.04
        spread = 0.20

        instrument = {
            "kind":
                "option",

            "symbol":
                "AAPL261218C00150000",

            "venue":
                "SIM",

            "exchange":
                "OPRA",

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

            "price_precision":
                2,

            "price_increment":
                "0.01",

            "multiplier":
                "100",

            "lot_size":
                "1",

            "expiration":
                "2026-12-18T21:00:00Z",
        }

        quantity = 1


    else:

        raise ValueError(
            kind
        )


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
            kind != "option"
            and index == 60
        ):

            signal = "SHORT"


        elif (
            kind != "option"
            and index == 85
        ):

            signal = "EXIT"


        signals.append(
            signal
        )


    return {
        "bars":
            bars,

        "signals":
            signals,

        "instrument":
            instrument,

        "quantity":
            quantity,

        "initial_capital":
            100000,

        "execution": {
            "name":
                "ideal"
        },
    }


def capabilities():

    return {
        "available":
            True,

        "nautilus_version":
            version(
                "nautilus_trader"
            ),

        "engine":
            "BacktestEngine",

        "supported_instruments":
            tuple(
                sorted(
                    SUPPORTED_KINDS
                )
            ),

        "execution_profiles":
            tuple(
                sorted(
                    SUPPORTED_PROFILES
                )
            ),

        "fill_model":
            "FillModel",

        "fee_models": (
            "MakerTakerFeeModel",
            "FixedFeeModel",
            "PerContractFeeModel",
        ),

        "latency_model":
            "LatencyModel",

        "commodity_future":
            True,

        "listed_option":
            True,

        "single_leg_option_short":
            False,

        "paper_only":
            True,

        "live_execution":
            False,

        "trading_node":
            False,

        "broker_adapter":
            False,
    }


def main():

    parser = argparse.ArgumentParser()


    parser.add_argument(
        "--capabilities-json",
        action="store_true",
    )


    parser.add_argument(
        "--self-test-all",
        action="store_true",
    )


    parser.add_argument(
        "--input",
    )


    parser.add_argument(
        "--output",
    )


    args = parser.parse_args()


    if args.capabilities_json:

        print(
            json.dumps(
                capabilities(),
                default=str,
            )
        )

        return


    if args.self_test_all:

        results = {}


        for kind in (
            "fx",
            "equity",
            "future",
            "commodity_future",
            "option",
        ):

            result = run_backtest(
                self_test_dataset(
                    kind
                )
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
                    kind
                    + " produced too few fills."
                )


            results[
                kind
            ] = {
                "instrument":
                    result[
                        "instrument"
                    ],

                "fill_count":
                    result[
                        "fill_count"
                    ],

                "execution":
                    result[
                        "execution"
                    ],
            }


        # Explicit model construction tests.
        currency = currency_from_code(
            "USD"
        )


        profiles = {}


        for name in (
            "ideal",
            "one_tick",
            "probabilistic",
            "delayed",
            "stress",
        ):

            profile = {
                "name":
                    name,
            }


            if name == "stress":

                profile.update(
                    {
                        "fee_mode":
                            "per_contract",

                        "commission":
                            1.0,
                    }
                )


            built = (
                build_execution_models(
                    profile,
                    currency,
                )
            )


            profiles[
                name
            ] = {
                "fill_model":
                    built[
                        "fill_model_type"
                    ],

                "fee_model":
                    built[
                        "fee_model_type"
                    ],

                "latency_model":
                    built[
                        "latency_model_type"
                    ],

                "prob_slippage":
                    built[
                        "prob_slippage"
                    ],
            }


        print(
            json.dumps(
                {
                    "success":
                        True,

                    "instruments":
                        results,

                    "profiles":
                        profiles,

                    "capabilities":
                        capabilities(),
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


    result = run_backtest(
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
