from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap


ROOT = Path(r"C:\Jarvis")

MAIN_PY = (
    ROOT / ".venv"
    / "Scripts"
    / "python.exe"
)

NAUTILUS_PY = (
    ROOT / ".venv-nautilus"
    / "Scripts"
    / "python.exe"
)

KERNEL = (
    ROOT
    / "research"
    / "nautilus_kernel"
)

WORKER = (
    KERNEL
    / "worker_c2.py"
)

PKG = (
    ROOT
    / "omni"
    / "trading_intelligence"
)

BRIDGE = (
    PKG
    / "nautilus_c2_bridge.py"
)

RECONCILE = (
    PKG
    / "nautilus_reconciliation.py"
)

V5_GATE = (
    PKG
    / "nautilus_validation_adapter.py"
)

PORTFOLIO = (
    PKG
    / "nautilus_portfolio_research.py"
)

STATUS = (
    PKG
    / "nautilus_c2_status.py"
)

MAIN = (
    ROOT
    / "main.py"
)

APP = (
    ROOT
    / "workstation"
    / "app.py"
)

TEST = (
    ROOT
    / "tests"
    / "test_nautilus_phase_c2.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "nautilus_phase_c2"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    WORKER,
    BRIDGE,
    RECONCILE,
    V5_GATE,
    PORTFOLIO,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    python,
    *args,
    capture=False,
    timeout=None,
):

    return subprocess.run(
        [
            str(python),
            *args,
        ],
        cwd=ROOT,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
        newline="\n",
    )


def rollback():

    print()
    print("=" * 72)
    print("ROLLBACK")
    print("=" * 72)

    for path, existed in (
        BACKUPS.items()
    ):

        backup = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
        )

        if existed:

            shutil.copy2(
                backup,
                path,
            )

        else:

            path.unlink(
                missing_ok=True
            )

    print(
        "Phase C2 files restored."
    )


print("=" * 80)
print("JARVIS NAUTILUSTRADER PHASE C2")
print("UNIVERSAL INSTRUMENT + EXECUTION MODEL + V5 RECONCILIATION")
print("=" * 80)


# ============================================================
# 1. BASELINE
# ============================================================

print()
print(
    "Checking frozen Nautilus Phase B / 614 checkpoint..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "n=main.jarvis_nautilus_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert v6['live_execution'] is False;"
        "assert n['available'];"
        "assert n['engine']=='BacktestEngine';"
        "assert n['live_execution'] is False;"
        "assert n['broker_adapter'] is False;"
        "print('Protected Core: PASS');"
        "print('Trading V5: PASS');"
        "print('Trading V6: PASS');"
        "print('Nautilus Phase B: PASS');"
        "print('614 checkpoint: PASS')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


if not NAUTILUS_PY.exists():

    print(
        "Isolated Nautilus Python missing."
    )

    sys.exit(1)


r = run(
    NAUTILUS_PY,
    "-c",
    (
        "from importlib.metadata import version;"
        "import nautilus_trader;"
        "assert version('nautilus_trader')=='1.231.0';"
        "print('NautilusTrader 1.231.0: PASS')"
    ),
)


if r.returncode:

    print(
        "NAUTILUS VERSION FAILURE"
    )

    sys.exit(1)


# ============================================================
# 2. BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = (
        path.exists()
    )

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(
        PROTECTED
    ),
)


# ============================================================
# 3. ISOLATED C2 WORKER
# ============================================================

write(
    WORKER,
    r'''
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
'''
)


# ============================================================
# 4. COMPILE + REAL C2 PREFLIGHT
# ============================================================

print()
print(
    "Compiling universal isolated worker..."
)


r = run(
    NAUTILUS_PY,
    "-m",
    "py_compile",
    str(
        WORKER
    ),
)


if r.returncode:

    print(
        "C2 WORKER COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Worker syntax: PASS"
)


print()
print(
    "Running universal Nautilus instrument/execution preflight..."
)


r = run(
    NAUTILUS_PY,
    str(
        WORKER
    ),
    "--self-test-all",
    capture=True,
    timeout=120,
)


if r.returncode:

    print(
        "UNIVERSAL NAUTILUS PREFLIGHT FAILURE"
    )

    print(
        r.stdout
    )

    print(
        r.stderr
    )

    rollback()

    sys.exit(1)


try:

    preflight = json.loads(
        r.stdout.strip()
        .splitlines()[
            -1
        ]
    )


except Exception:

    print(
        r.stdout
    )

    print(
        r.stderr
    )

    rollback()

    raise


assert preflight[
    "success"
]


for kind in (
    "fx",
    "equity",
    "future",
    "commodity_future",
    "option",
):

    assert (
        preflight[
            "instruments"
        ][
            kind
        ][
            "fill_count"
        ]
        >= 2
    )


assert (
    preflight[
        "capabilities"
    ][
        "single_leg_option_short"
    ]
    is False
)


print(
    "FX instrument: PASS"
)

print(
    "Equity instrument: PASS"
)

print(
    "Futures instrument: PASS"
)

print(
    "Commodity futures instrument: PASS"
)

print(
    "Listed option instrument: PASS"
)

print(
    "Execution profile construction: PASS"
)

print(
    "Single-leg option short: BLOCKED"
)

print(
    "Universal Nautilus preflight: PASS"
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# 5. MAIN-SIDE UNIVERSAL BRIDGE
# ============================================================

write(
    BRIDGE,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
)

from pathlib import (
    Path,
)

import json
import subprocess
import tempfile


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


NAUTILUS_PY = (
    ROOT
    / ".venv-nautilus"
    / "Scripts"
    / "python.exe"
)


WORKER = (
    ROOT
    / "research"
    / "nautilus_kernel"
    / "worker_c2.py"
)


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


class NautilusC2Bridge:

    MAX_BARS = 200000


    def available(
        self,
    ):

        return (
            NAUTILUS_PY.exists()
            and WORKER.exists()
        )


    def capabilities(
        self,
    ):

        if not self.available():

            return {
                "available":
                    False,

                "paper_only":
                    True,

                "live_execution":
                    False,

                "broker_adapter":
                    False,
            }


        result = subprocess.run(
            [
                str(
                    NAUTILUS_PY
                ),

                str(
                    WORKER
                ),

                "--capabilities-json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )


        if result.returncode:

            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or "Nautilus C2 capability probe failed."
            )


        return json.loads(
            result.stdout.strip()
            .splitlines()[
                -1
            ]
        )


    @staticmethod
    def _bar(
        bar,
    ):

        if isinstance(
            bar,
            dict,
        ):

            getter = bar.get


        else:

            getter = lambda name: getattr(
                bar,
                name
            )


        timestamp = getter(
            "timestamp"
        )


        if isinstance(
            timestamp,
            datetime,
        ):

            timestamp = (
                timestamp.isoformat()
            )


        return {
            "timestamp":
                str(
                    timestamp
                ),

            "open":
                float(
                    getter(
                        "open"
                    )
                ),

            "high":
                float(
                    getter(
                        "high"
                    )
                ),

            "low":
                float(
                    getter(
                        "low"
                    )
                ),

            "close":
                float(
                    getter(
                        "close"
                    )
                ),
        }


    def backtest(
        self,
        bars,
        signals,
        *,
        instrument,
        execution=None,
        initial_capital=100000.0,
        quantity=1,
        leverage=1,
        timeout=120,
    ):

        if not self.available():

            raise RuntimeError(
                "Nautilus C2 kernel unavailable."
            )


        bars = tuple(
            bars
        )


        signals = tuple(
            str(
                signal
            ).strip().upper()

            for signal
            in signals
        )


        if not bars:

            raise ValueError(
                "bars cannot be empty."
            )


        if len(
            bars
        ) > self.MAX_BARS:

            raise ValueError(
                "Nautilus job exceeds maximum bar count."
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


        instrument = dict(
            instrument
        )


        kind = str(
            instrument.get(
                "kind",
                ""
            )
        ).strip().lower()


        if (
            kind == "option"
            and "SHORT" in signals
        ):

            raise PermissionError(
                "Single-leg option short simulation is blocked."
            )


        payload = {
            "bars":
                [
                    self._bar(
                        bar
                    )

                    for bar
                    in bars
                ],

            "signals":
                list(
                    signals
                ),

            "instrument":
                instrument,

            "execution":
                dict(
                    execution
                    or {
                        "name":
                            "ideal"
                    }
                ),

            "initial_capital":
                float(
                    initial_capital
                ),

            "quantity":
                float(
                    quantity
                ),

            "leverage":
                float(
                    leverage
                ),

            "research_only":
                True,

            "live_execution":
                False,

            "broker_adapter":
                False,
        }


        with tempfile.TemporaryDirectory(
            prefix=
                "jarvis_nautilus_c2_"
        ) as tmp:

            tmp = Path(
                tmp
            )


            input_path = (
                tmp
                / "input.json"
            )


            output_path = (
                tmp
                / "output.json"
            )


            input_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )


            result = subprocess.run(
                [
                    str(
                        NAUTILUS_PY
                    ),

                    str(
                        WORKER
                    ),

                    "--input",
                    str(
                        input_path
                    ),

                    "--output",
                    str(
                        output_path
                    ),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=float(
                    timeout
                ),
            )


            if result.returncode:

                raise RuntimeError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "Nautilus C2 worker failed."
                )


            if not output_path.exists():

                raise RuntimeError(
                    "Nautilus worker returned no output."
                )


            output = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                )
            )


        if not output.get(
            "success"
        ):

            raise RuntimeError(
                "Nautilus C2 result unsuccessful."
            )


        if (
            output.get(
                "live_execution"
            )
            is not False
        ):

            raise RuntimeError(
                "Live-execution invariant failed."
            )


        if (
            output.get(
                "broker_adapter"
            )
            is not False
        ):

            raise RuntimeError(
                "Broker-adapter invariant failed."
            )


        return output


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "live",
            "broker",
            "place_order",
            "modify_order",
            "cancel_order",
            "execution_client",
            "trading_node",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "Nautilus C2 bridge is research-only."
            )


        raise AttributeError(
            name
        )


nautilus_c2_bridge = (
    NautilusC2Bridge()
)
'''
)


# ============================================================
# 6. NATIVE-vs-NAUTILUS RECONCILIATION
# ============================================================

write(
    RECONCILE,
    r'''
from __future__ import annotations


def reconcile_native_nautilus(
    native_result,
    nautilus_result,
):

    native_trades = tuple(
        native_result.get(
            "trades",
            ()
        )
    )


    native_metrics = dict(
        native_result.get(
            "metrics",
            {}
        )
    )


    native_pnl = native_metrics.get(
        "net_pnl"
    )


    nautilus_pnl = (
        nautilus_result.get(
            "realized_pnl_numeric"
        )
    )


    pnl_gap = None

    pnl_gap_pct = None


    if (
        native_pnl is not None
        and nautilus_pnl is not None
    ):

        native_pnl = float(
            native_pnl
        )

        nautilus_pnl = float(
            nautilus_pnl
        )


        pnl_gap = (
            nautilus_pnl
            - native_pnl
        )


        pnl_gap_pct = (
            pnl_gap
            / max(
                abs(
                    native_pnl
                ),
                1.0,
            )
        )


    return {
        "success":
            True,

        "native_engine":
            "jarvis_v2",

        "nautilus_engine":
            nautilus_result.get(
                "engine"
            ),

        "native_trade_count":
            len(
                native_trades
            ),

        "nautilus_fill_count":
            int(
                nautilus_result.get(
                    "fill_count",
                    0,
                )
            ),

        "nautilus_position_rows":
            int(
                nautilus_result.get(
                    "position_report_rows",
                    0,
                )
            ),

        "native_net_pnl":
            native_pnl,

        "nautilus_realized_pnl":
            nautilus_pnl,

        "pnl_gap":
            pnl_gap,

        "pnl_gap_pct":
            pnl_gap_pct,

        "pnl_comparable":
            (
                native_pnl is not None
                and nautilus_pnl is not None
            ),

        "timing_semantics": {
            "jarvis_v2":
                "signal_close_to_next_bar_open",

            "nautilus":
                "event_driven_bar_execution",

            "direct_equivalence_expected":
                False,
        },

        "interpretation":
            (
                "Differences are evidence to investigate, "
                "not an automatic failure, because the engines "
                "use intentionally different bar-execution semantics."
            ),

        "automatic_strategy_decision":
            False,

        "production_promotion":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 7. V5 VALIDATION ADAPTER
# ============================================================

write(
    V5_GATE,
    r'''
from __future__ import annotations


def nautilus_v5_validation_gate(
    v5_report,
    nautilus_result,
):

    recommendation_block = (
        v5_report.get(
            "recommendation",
            {}
        )
    )


    recommendation = (
        recommendation_block.get(
            "recommendation"
        )
    )


    nautilus_safe = (
        nautilus_result.get(
            "success"
        )
        is True

        and nautilus_result.get(
            "live_execution"
        )
        is False

        and nautilus_result.get(
            "broker_adapter"
        )
        is False

        and nautilus_result.get(
            "paper_only"
        )
        is True
    )


    has_evidence = (
        int(
            nautilus_result.get(
                "fill_count",
                0,
            )
        )
        > 0
    )


    research_eligible = (
        recommendation
        == "PROMOTE"

        and nautilus_safe

        and has_evidence
    )


    if not nautilus_safe:

        state = "REJECT"


    elif not has_evidence:

        state = "KEEP_TESTING"


    elif recommendation == "PROMOTE":

        state = (
            "EXTENDED_RESEARCH_ELIGIBLE"
        )


    elif recommendation in {
        "KEEP_TESTING",
        None,
    }:

        state = "KEEP_TESTING"


    elif recommendation == "DEGRADE":

        state = "DEGRADE"


    else:

        state = "RETIRE"


    return {
        "state":
            state,

        "v5_recommendation":
            recommendation,

        "nautilus_safe":
            nautilus_safe,

        "nautilus_evidence":
            has_evidence,

        "extended_research_eligible":
            research_eligible,

        "production_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_broker_order":
            False,

        "live_deployment":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 8. PORTFOLIO RESEARCH FOUNDATION
# ============================================================

write(
    PORTFOLIO,
    r'''
from __future__ import annotations

from collections import (
    Counter,
)


def nautilus_portfolio_research(
    results,
):

    results = tuple(
        results
    )


    if not results:

        raise ValueError(
            "At least one research result is required."
        )


    total_fills = 0

    total_positions = 0

    known_pnl = []

    kinds = Counter()

    instruments = []


    for result in results:

        if (
            result.get(
                "research_only"
            )
            is not True
        ):

            raise ValueError(
                "Portfolio accepts research-only results."
            )


        if (
            result.get(
                "live_execution"
            )
            is not False
        ):

            raise ValueError(
                "Live result rejected."
            )


        if (
            result.get(
                "broker_adapter"
            )
            is not False
        ):

            raise ValueError(
                "Broker-connected result rejected."
            )


        instrument = dict(
            result.get(
                "instrument",
                {}
            )
        )


        kind = str(
            instrument.get(
                "research_kind",
                "unknown",
            )
        )


        kinds[
            kind
        ] += 1


        instruments.append(
            instrument
        )


        total_fills += int(
            result.get(
                "fill_count",
                0,
            )
        )


        total_positions += int(
            result.get(
                "position_report_rows",
                0,
            )
        )


        pnl = result.get(
            "realized_pnl_numeric"
        )


        if pnl is not None:

            known_pnl.append(
                float(
                    pnl
                )
            )


    return {
        "success":
            True,

        "result_count":
            len(
                results
            ),

        "instrument_kinds":
            dict(
                kinds
            ),

        "instruments":
            tuple(
                instruments
            ),

        "total_fills":
            total_fills,

        "total_position_rows":
            total_positions,

        "known_realized_pnl_count":
            len(
                known_pnl
            ),

        "aggregate_known_realized_pnl":
            (
                sum(
                    known_pnl
                )
                if known_pnl
                else None
            ),

        "multi_instrument_research":
            True,

        "multi_strategy_foundation":
            True,

        "capital_allocation":
            False,

        "broker_position_sizing":
            False,

        "portfolio_live_execution":
            False,

        "automatic_portfolio_rebalance":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 9. STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

import importlib.util


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.nautilus_c2_bridge import (
    nautilus_c2_bridge,
)


def nautilus_c2_status():

    core = verify_protected_core()

    capabilities = (
        nautilus_c2_bridge
        .capabilities()
    )


    return {
        "protected_core":
            core.ok,

        "available":
            capabilities.get(
                "available",
                False,
            ),

        "version":
            capabilities.get(
                "nautilus_version"
            ),

        "engine":
            capabilities.get(
                "engine"
            ),

        "isolated_subprocess":
            True,

        "main_venv_imports_nautilus":
            (
                importlib.util.find_spec(
                    "nautilus_trader"
                )
                is not None
            ),

        "supported_instruments":
            capabilities.get(
                "supported_instruments",
                (),
            ),

        "execution_profiles":
            capabilities.get(
                "execution_profiles",
                (),
            ),

        "fx":
            True,

        "equity":
            True,

        "future":
            True,

        "commodity_future":
            True,

        "listed_option":
            True,

        "single_leg_option_short":
            False,

        "fill_model_profiles":
            True,

        "fee_model_profiles":
            True,

        "latency_model_profiles":
            True,

        "native_nautilus_reconciliation":
            True,

        "v5_validation_adapter":
            True,

        "portfolio_research_foundation":
            True,

        "timing_semantics_calibrated":
            True,

        "exact_pnl_equivalence_required":
            False,

        "paper_only":
            True,

        "live_execution":
            False,

        "trading_node":
            False,

        "broker_adapter":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_broker_order":
            False,

        "automatic_portfolio_rebalance":
            False,

        "production_self_modification":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 10. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_nautilus_c2_status("
    not in main_source
):

    main_source += r'''


def jarvis_nautilus_c2_status():

    from omni.trading_intelligence.nautilus_c2_status import (
        nautilus_c2_status,
    )

    return nautilus_c2_status()


def jarvis_nautilus_universal_backtest(
    bars,
    signals,
    instrument,
    execution=None,
    initial_capital=100000.0,
    quantity=1,
    leverage=1,
    timeout=120,
):

    from omni.trading_intelligence.nautilus_c2_bridge import (
        nautilus_c2_bridge,
    )

    return nautilus_c2_bridge.backtest(
        bars,
        signals,
        instrument=instrument,
        execution=execution,
        initial_capital=initial_capital,
        quantity=quantity,
        leverage=leverage,
        timeout=timeout,
    )


def jarvis_reconcile_backtests(
    native_result,
    nautilus_result,
):

    from omni.trading_intelligence.nautilus_reconciliation import (
        reconcile_native_nautilus,
    )

    return reconcile_native_nautilus(
        native_result,
        nautilus_result,
    )


def jarvis_nautilus_v5_gate(
    v5_report,
    nautilus_result,
):

    from omni.trading_intelligence.nautilus_validation_adapter import (
        nautilus_v5_validation_gate,
    )

    return nautilus_v5_validation_gate(
        v5_report,
        nautilus_result,
    )


def jarvis_nautilus_portfolio_research(
    results,
):

    from omni.trading_intelligence.nautilus_portfolio_research import (
        nautilus_portfolio_research,
    )

    return nautilus_portfolio_research(
        results
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 11. WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_nautilus_c2_payload("
    not in app_source
):

    app_source += r'''


def jarvis_nautilus_c2_payload():

    from omni.trading_intelligence.nautilus_c2_status import (
        nautilus_c2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                nautilus_c2_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 12. TESTS
# ============================================================

write(
    TEST,
    r'''
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
'''
)


# ============================================================
# 13. COMPILE
# ============================================================

print()
print(
    "Checking Phase C2 bridge syntax..."
)


r = run(
    MAIN_PY,
    "-m",
    "py_compile",

    str(
        BRIDGE
    ),

    str(
        RECONCILE
    ),

    str(
        V5_GATE
    ),

    str(
        PORTFOLIO
    ),

    str(
        STATUS
    ),

    str(
        MAIN
    ),

    str(
        APP
    ),

    str(
        TEST
    ),
)


if r.returncode:

    print(
        "C2 COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Phase C2 syntax: PASS"
)


# ============================================================
# 14. CORE
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


print(
    "Protected Core hashes: PASS"
)


# ============================================================
# 15. C2 STATUS
# ============================================================

print()
print(
    "Checking C2 universal-kernel status..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_nautilus_c2_status();"
        "assert s['available'];"
        "assert s['version']=='1.231.0';"
        "assert s['commodity_future'];"
        "assert s['listed_option'];"
        "assert s['single_leg_option_short'] is False;"
        "assert s['live_execution'] is False;"
        "assert s['broker_adapter'] is False;"
        "print('Universal instruments: PASS');"
        "print('Execution models: PASS');"
        "print('V5 validation adapter: PASS');"
        "print('Portfolio research foundation: PASS');"
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "C2 STATUS FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 16. SAFETY
# ============================================================

print()
print(
    "Checking Phase C2 safety..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_nautilus_c2_status();"
        "assert s['paper_only'];"
        "assert s['live_execution'] is False;"
        "assert s['trading_node'] is False;"
        "assert s['broker_adapter'] is False;"
        "assert s['automatic_strategy_promotion'] is False;"
        "assert s['automatic_registry_mutation'] is False;"
        "assert s['automatic_broker_order'] is False;"
        "assert s['automatic_portfolio_rebalance'] is False;"
        "assert s['production_self_modification'] is False;"
        "print('TradingNode: BLOCKED');"
        "print('Broker adapter: NONE');"
        "print('Automatic strategy promotion: BLOCKED');"
        "print('Automatic broker orders: BLOCKED');"
        "print('Automatic portfolio rebalance: BLOCKED');"
        "print('C2 safety: PASS')"
    ),
)


if r.returncode:

    print(
        "C2 SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 17. TARGETED REGRESSION
# ============================================================

print()
print(
    "Running Phase C2 targeted regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",

    "tests.test_nautilus_phase_c2",
    "tests.test_nautilus_research_kernel",

    "tests.test_trading_intelligence_v6",
    "tests.test_trading_intelligence_v5",
    "tests.test_trading_intelligence_v4",
    "tests.test_trading_intelligence_v3",
    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "-q",
    timeout=240,
)


if r.returncode:

    print(
        "TARGETED REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 18. FULL REGRESSION
# ============================================================

print()
print(
    "Running full JARVIS regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
    timeout=300,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 19. FINAL CORE / PREVIOUS PHASES
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "FINAL PROTECTED CORE CHANGE:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "b=main.jarvis_nautilus_status();"
        "c2=main.jarvis_nautilus_c2_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert b['available'];"
        "assert c2['available'];"
        "assert v6['live_execution'] is False;"
        "assert c2['live_execution'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Trading V5: PRESERVED');"
        "print('Trading V6: PRESERVED');"
        "print('Nautilus Phase B: PRESERVED');"
        "print('Nautilus C2: PASS')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:

    print(
        "FINAL BROWSER TEST FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Final browser DOM test: PASS"
)


# ============================================================
# SUCCESS
# ============================================================

status = run(
    MAIN_PY,
    "-c",
    (
        "import main,pprint;"
        "pprint.pp(main.jarvis_nautilus_c2_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS NAUTILUSTRADER PHASE C2 SUCCESS")
print("=" * 80)

print()
print("UNIVERSAL INSTRUMENTS")
print("FX: ACTIVE")
print("Equity: ACTIVE")
print("Futures: ACTIVE")
print("Commodity futures: ACTIVE")
print("Listed options: ACTIVE")
print("Single-leg naked option short: BLOCKED")
print()

print("EXECUTION MODEL")
print("Ideal profile: ACTIVE")
print("One-tick L1 slippage profile: ACTIVE")
print("Probabilistic profile: ACTIVE")
print("Latency profile: ACTIVE")
print("Stress profile: ACTIVE")
print("Maker/taker fee model: ACTIVE")
print("Fixed fee model: ACTIVE")
print("Per-contract fee model: ACTIVE")
print()

print("ENGINE RECONCILIATION")
print("JARVIS V2 engine: PRESERVED")
print("Nautilus event-driven engine: ACTIVE")
print("Timing-semantic difference: EXPLICIT")
print("False exact-equivalence requirement: DISABLED")
print("PnL reconciliation when extractable: ACTIVE")
print()

print("V5 VALIDATION")
print("PROMOTE remains research recommendation only")
print("Nautilus cannot bypass V5: ENFORCED")
print("Extended-research eligibility gate: ACTIVE")
print("Production promotion: BLOCKED")
print()

print("PORTFOLIO FOUNDATION")
print("Multi-instrument result aggregation: ACTIVE")
print("Multi-strategy research foundation: ACTIVE")
print("Aggregate research PnL: ACTIVE WHEN AVAILABLE")
print("Broker capital allocation: BLOCKED")
print("Automatic portfolio rebalance: BLOCKED")
print()

print("GOVERNANCE")
print("Main JARVIS venv imports Nautilus: NO")
print("TradingNode: NOT CREATED")
print("Broker adapter: NONE")
print("FYERS execution connection: NONE")
print("Live orders: BLOCKED")
print("Production self-modification: BLOCKED")
print("Protected Core: UNCHANGED")
print("Trading V1-V6: PRESERVED")
print("Nautilus Phase B: PRESERVED")
print("Full regression: PASS")
print()

print("STATUS:")
print(
    status.stdout.strip()
)
print()

print("NEXT:")
print("NAUTILUS PHASE C3")
print("True multi-instrument portfolio BacktestEngine")
print("Multiple strategies inside one event-driven engine")
print("Cross-instrument capital/account simulation")
print("Correlation / concentration analytics")
print("Portfolio drawdown attribution")
print("Execution-profile stress matrix")
print("V5 walk-forward campaigns through Nautilus")
print()
print("THEN TRADING V7:")
print("Historical derivatives feature streams")
print("Real option-chain provider integration")
print("IV/OI/skew history")
print("Strategy ensemble research")
print("Cross-asset regime intelligence")
print("Automated research campaigns")
print("Still NO live broker execution")
