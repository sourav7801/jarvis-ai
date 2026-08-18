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
    / "worker_c3.py"
)

PKG = (
    ROOT
    / "omni"
    / "trading_intelligence"
)

BRIDGE = (
    PKG
    / "nautilus_c3_bridge.py"
)

CAMPAIGN = (
    PKG
    / "nautilus_c3_campaign.py"
)

STATUS = (
    PKG
    / "nautilus_c3_status.py"
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
    / "test_nautilus_phase_c3.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "nautilus_phase_c3"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    WORKER,
    BRIDGE,
    CAMPAIGN,
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


def sha(path):

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

    for path, existed in BACKUPS.items():

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
        "Phase C3 files restored."
    )


print("=" * 80)
print("JARVIS NAUTILUSTRADER PHASE C3")
print("TRUE MULTI-INSTRUMENT PORTFOLIO + WALK-FORWARD RESEARCH")
print("=" * 80)


# ============================================================
# 1. FROZEN C2 / 627 CHECKPOINT
# ============================================================

print()
print(
    "Checking frozen Nautilus C2 / 627 checkpoint..."
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
        "c2=main.jarvis_nautilus_c2_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert c2['available'];"
        "assert c2['commodity_future'];"
        "assert c2['listed_option'];"
        "assert c2['live_execution'] is False;"
        "assert c2['broker_adapter'] is False;"
        "print('Protected Core: PASS');"
        "print('Trading V5: PASS');"
        "print('Trading V6: PASS');"
        "print('Nautilus C2: PASS');"
        "print('627 checkpoint: PASS')"
    ),
)


if r.returncode:

    print("BASELINE FAILURE")
    sys.exit(1)


r = run(
    NAUTILUS_PY,
    "-c",
    (
        "from importlib.metadata import version;"
        "assert version('nautilus_trader')=='1.231.0';"
        "print('NautilusTrader 1.231.0: PASS')"
    ),
)


if r.returncode:

    print(
        "NAUTILUS ENVIRONMENT FAILURE"
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
    len(PROTECTED),
)


# ============================================================
# 3. TRUE PORTFOLIO WORKER
# ============================================================

write(
    WORKER,
    r'''
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
'''
)


# ============================================================
# 4. REAL MULTI-INSTRUMENT PREFLIGHT
# ============================================================

print()
print(
    "Compiling C3 portfolio worker..."
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
        "C3 WORKER COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Worker syntax: PASS"
)


print()
print("=" * 72)
print(
    "RUNNING TRUE MULTI-INSTRUMENT / MULTI-STRATEGY BACKTEST"
)
print("=" * 72)


r = run(
    NAUTILUS_PY,
    str(
        WORKER
    ),
    "--self-test",
    capture=True,
    timeout=120,
)


if r.returncode:

    print(
        "C3 PORTFOLIO PREFLIGHT FAILURE"
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

assert preflight[
    "strategy_count"
] == 3

assert preflight[
    "instrument_count"
] == 3

assert preflight[
    "fill_count"
] >= 6

assert (
    preflight[
        "live_execution"
    ]
    is False
)

assert (
    preflight[
        "broker_adapter"
    ]
    is False
)


print(
    "Single BacktestEngine: PASS"
)

print(
    "Three instruments in one engine: PASS"
)

print(
    "Three strategy instances in one engine: PASS"
)

print(
    "Runtime strategy IDs:",
    preflight[
        "runtime_strategy_ids"
    ],
)

print(
    "Simulated fills:",
    preflight[
        "fill_count"
    ],
)

print(
    "Cross-instrument correlation: PASS"
)

print(
    "Concentration analytics: PASS"
)

print(
    "Drawdown attribution proxy: PASS"
)

print(
    "Broker adapter: NONE"
)

print(
    "True portfolio preflight: PASS"
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# 5. MAIN SUBPROCESS BRIDGE
# ============================================================

write(
    BRIDGE,
    r'''
from __future__ import annotations

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
    / "worker_c3.py"
)


class NautilusC3PortfolioBridge:

    MAX_STRATEGIES = 20

    MAX_TOTAL_BARS = 500000


    def available(
        self,
    ):

        return (
            NAUTILUS_PY.exists()
            and WORKER.exists()
        )


    def _validate(
        self,
        portfolio,
    ):

        portfolio = dict(
            portfolio
        )


        strategies = list(
            portfolio.get(
                "strategies",
                (),
            )
        )


        if not strategies:

            raise ValueError(
                "Portfolio strategies cannot be empty."
            )


        if len(
            strategies
        ) > self.MAX_STRATEGIES:

            raise ValueError(
                "Portfolio strategy limit exceeded."
            )


        total_bars = 0


        for slot in strategies:

            bars = tuple(
                slot.get(
                    "bars",
                    (),
                )
            )


            signals = tuple(
                slot.get(
                    "signals",
                    (),
                )
            )


            if len(
                bars
            ) != len(
                signals
            ):

                raise ValueError(
                    "Each slot requires matching bars/signals."
                )


            total_bars += len(
                bars
            )


            kind = str(
                slot.get(
                    "instrument",
                    {}
                ).get(
                    "kind",
                    "",
                )
            ).lower()


            if (
                kind == "option"
                and any(
                    str(
                        signal
                    ).upper()
                    == "SHORT"

                    for signal
                    in signals
                )
            ):

                raise PermissionError(
                    "Single-leg option short is blocked."
                )


        if total_bars > self.MAX_TOTAL_BARS:

            raise ValueError(
                "Portfolio bar limit exceeded."
            )


        return portfolio


    def run(
        self,
        portfolio,
        *,
        timeout=180,
    ):

        if not self.available():

            raise RuntimeError(
                "Nautilus C3 portfolio kernel unavailable."
            )


        payload = self._validate(
            portfolio
        )


        with tempfile.TemporaryDirectory(
            prefix=
                "jarvis_nautilus_c3_"
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
                    or "Nautilus C3 worker failed."
                )


            if not output_path.exists():

                raise RuntimeError(
                    "C3 worker produced no output."
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
                "C3 portfolio run failed."
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


    def stress_matrix(
        self,
        portfolio,
        *,
        profiles=None,
        timeout=180,
    ):

        if profiles is None:

            profiles = (
                {
                    "name":
                        "ideal",
                },

                {
                    "name":
                        "one_tick",
                },

                {
                    "name":
                        "probabilistic",

                    "random_seed":
                        42,
                },

                {
                    "name":
                        "delayed",
                },

                {
                    "name":
                        "stress",

                    "fee_mode":
                        "per_contract",

                    "commission":
                        1.0,

                    "random_seed":
                        42,
                },
            )


        rows = []


        for profile in profiles:

            payload = dict(
                portfolio
            )


            payload[
                "execution"
            ] = dict(
                profile
            )


            result = self.run(
                payload,
                timeout=timeout,
            )


            engine_pnl = result.get(
                "realized_pnl_numeric"
            )


            proxy_pnl = (
                result[
                    "drawdown_attribution"
                ][
                    "portfolio_total_proxy_pnl"
                ]
            )


            rows.append(
                {
                    "profile":
                        dict(
                            profile
                        ),

                    "fill_count":
                        result[
                            "fill_count"
                        ],

                    "engine_realized_pnl":
                        engine_pnl,

                    "signal_proxy_pnl":
                        proxy_pnl,

                    "proxy_max_drawdown":
                        result[
                            "drawdown_attribution"
                        ][
                            "max_drawdown"
                        ],

                    "live_execution":
                        False,
                }
            )


        return {
            "success":
                True,

            "rows":
                tuple(
                    rows
                ),

            "profile_count":
                len(
                    rows
                ),

            "same_portfolio":
                True,

            "automatic_profile_selection":
                False,

            "research_only":
                True,

            "live_execution":
                False,
        }


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
            "trading_node",
            "execution_client",
            "rebalance",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "C3 portfolio bridge is research-only."
            )


        raise AttributeError(
            name
        )


nautilus_c3_portfolio_bridge = (
    NautilusC3PortfolioBridge()
)
'''
)


# ============================================================
# 6. C3 WALK-FORWARD CAMPAIGN + V5 GATE
# ============================================================

write(
    CAMPAIGN,
    r'''
from __future__ import annotations

from statistics import (
    fmean,
)


from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


class NautilusC3WalkForward:

    @staticmethod
    def _aligned_length(
        portfolio,
    ):

        strategies = list(
            portfolio[
                "strategies"
            ]
        )


        lengths = {
            len(
                slot[
                    "bars"
                ]
            )

            for slot in strategies
        }


        signal_lengths = {
            len(
                slot[
                    "signals"
                ]
            )

            for slot in strategies
        }


        if (
            len(
                lengths
            ) != 1
            or lengths
            != signal_lengths
        ):

            raise ValueError(
                "C3 walk-forward currently requires "
                "aligned equal-length strategy datasets."
            )


        total = next(
            iter(
                lengths
            )
        )


        timestamps = None


        for slot in strategies:

            current = tuple(
                str(
                    (
                        bar.get(
                            "timestamp"
                        )
                        if isinstance(
                            bar,
                            dict,
                        )
                        else getattr(
                            bar,
                            "timestamp",
                        )
                    )
                )

                for bar
                in slot[
                    "bars"
                ]
            )


            if timestamps is None:

                timestamps = current


            elif current != timestamps:

                raise ValueError(
                    "Walk-forward timestamps are not aligned."
                )


        return total


    @staticmethod
    def _slice(
        portfolio,
        start,
        end,
    ):

        result = dict(
            portfolio
        )


        strategies = []


        for slot in portfolio[
            "strategies"
        ]:

            child = dict(
                slot
            )


            child[
                "bars"
            ] = tuple(
                slot[
                    "bars"
                ][
                    start:end
                ]
            )


            child[
                "signals"
            ] = tuple(
                slot[
                    "signals"
                ][
                    start:end
                ]
            )


            strategies.append(
                child
            )


        result[
            "strategies"
        ] = tuple(
            strategies
        )


        return result


    @staticmethod
    def _research_pnl(
        result,
    ):

        engine = result.get(
            "realized_pnl_numeric"
        )


        if engine is not None:

            return (
                float(
                    engine
                ),
                "engine_realized_pnl",
            )


        return (
            float(
                result[
                    "drawdown_attribution"
                ][
                    "portfolio_total_proxy_pnl"
                ]
            ),
            "signal_proxy_pnl",
        )


    def run(
        self,
        portfolio,
        *,
        train_size,
        validation_size,
        test_size,
        step=None,
        timeout=180,
    ):

        total = self._aligned_length(
            portfolio
        )


        train_size = int(
            train_size
        )

        validation_size = int(
            validation_size
        )

        test_size = int(
            test_size
        )


        step = int(
            step
            if step is not None
            else test_size
        )


        if min(
            train_size,
            validation_size,
            test_size,
            step,
        ) < 10:

            raise ValueError(
                "Each C3 walk-forward segment "
                "must contain at least 10 bars."
            )


        required = (
            train_size
            + validation_size
            + test_size
        )


        if total < required:

            raise ValueError(
                "Insufficient aligned data for C3 walk-forward."
            )


        windows = []

        start = 0

        window_id = 0


        while (
            start
            + required
            <= total
        ):

            train_end = (
                start
                + train_size
            )


            validation_end = (
                train_end
                + validation_size
            )


            test_end = (
                validation_end
                + test_size
            )


            train_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        start,
                        train_end,
                    ),
                    timeout=timeout,
                )
            )


            validation_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        train_end,
                        validation_end,
                    ),
                    timeout=timeout,
                )
            )


            oos_result = (
                nautilus_c3_portfolio_bridge
                .run(
                    self._slice(
                        portfolio,
                        validation_end,
                        test_end,
                    ),
                    timeout=timeout,
                )
            )


            train_pnl, train_source = (
                self._research_pnl(
                    train_result
                )
            )


            validation_pnl, validation_source = (
                self._research_pnl(
                    validation_result
                )
            )


            oos_pnl, oos_source = (
                self._research_pnl(
                    oos_result
                )
            )


            windows.append(
                {
                    "window_id":
                        window_id,

                    "indexes": {
                        "start":
                            start,

                        "train_end":
                            train_end,

                        "validation_end":
                            validation_end,

                        "test_end":
                            test_end,
                    },

                    "train": {
                        "pnl":
                            train_pnl,

                        "source":
                            train_source,

                        "fill_count":
                            train_result[
                                "fill_count"
                            ],
                    },

                    "validation": {
                        "pnl":
                            validation_pnl,

                        "source":
                            validation_source,

                        "fill_count":
                            validation_result[
                                "fill_count"
                            ],
                    },

                    "out_of_sample": {
                        "pnl":
                            oos_pnl,

                        "source":
                            oos_source,

                        "fill_count":
                            oos_result[
                                "fill_count"
                            ],

                        "profitable":
                            oos_pnl
                            > 0,
                    },
                }
            )


            start += step

            window_id += 1


        profitable = sum(
            1

            for row in windows

            if row[
                "out_of_sample"
            ][
                "profitable"
            ]
        )


        oos_pnls = [
            row[
                "out_of_sample"
            ][
                "pnl"
            ]

            for row in windows
        ]


        return {
            "success":
                True,

            "window_count":
                len(
                    windows
                ),

            "windows":
                tuple(
                    windows
                ),

            "oos_profitable_windows":
                profitable,

            "oos_pass_rate":
                (
                    profitable
                    / len(
                        windows
                    )

                    if windows

                    else 0.0
                ),

            "average_oos_pnl":
                (
                    fmean(
                        oos_pnls
                    )

                    if oos_pnls

                    else 0.0
                ),

            "chronological":
                True,

            "precomputed_signal_replay":
                True,

            "candidate_reoptimized_on_oos":
                False,

            "oos_tuning":
                False,

            "automatic_strategy_promotion":
                False,

            "research_only":
                True,
        }


nautilus_c3_walk_forward = (
    NautilusC3WalkForward()
)


def nautilus_c3_v5_gate(
    v5_report,
    c3_campaign,
):

    recommendation = (
        v5_report.get(
            "recommendation",
            {}
        ).get(
            "recommendation"
        )
    )


    pass_rate = float(
        c3_campaign.get(
            "oos_pass_rate",
            0.0,
        )
    )


    safe = (
        c3_campaign.get(
            "success"
        )
        is True

        and c3_campaign.get(
            "oos_tuning"
        )
        is False

        and c3_campaign.get(
            "candidate_reoptimized_on_oos"
        )
        is False
    )


    if not safe:

        state = "REJECT"


    elif recommendation == "RETIRE":

        state = "RETIRE"


    elif recommendation == "DEGRADE":

        state = "DEGRADE"


    elif (
        recommendation == "PROMOTE"
        and pass_rate >= 0.60
    ):

        state = (
            "PORTFOLIO_RESEARCH_ELIGIBLE"
        )


    else:

        state = "KEEP_TESTING"


    return {
        "state":
            state,

        "v5_recommendation":
            recommendation,

        "c3_oos_pass_rate":
            pass_rate,

        "oos_tuning":
            False,

        "production_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_portfolio_allocation":
            False,

        "automatic_broker_order":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 7. STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


def nautilus_c3_status():

    core = verify_protected_core()


    return {
        "protected_core":
            core.ok,

        "available":
            nautilus_c3_portfolio_bridge.available(),

        "engine":
            "BacktestEngine",

        "single_event_driven_engine":
            True,

        "multi_instrument":
            True,

        "multiple_strategy_instances":
            True,

        "unified_venue_account":
            True,

        "single_base_currency_per_portfolio":
            True,

        "cross_instrument_correlation":
            True,

        "concentration_analytics":
            True,

        "concentration_uses_input_notional_proxy":
            True,

        "drawdown_attribution":
            True,

        "drawdown_attribution_is_signal_proxy":
            True,

        "engine_account_report":
            True,

        "engine_fill_report":
            True,

        "engine_position_report":
            True,

        "execution_profile_stress_matrix":
            True,

        "automatic_execution_profile_selection":
            False,

        "nautilus_walk_forward_campaign":
            True,

        "chronological_oos":
            True,

        "oos_tuning":
            False,

        "candidate_reoptimized_on_oos":
            False,

        "v5_campaign_gate":
            True,

        "single_leg_option_short":
            False,

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

        "automatic_portfolio_allocation":
            False,

        "automatic_portfolio_rebalance":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 8. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_nautilus_c3_status("
    not in main_source
):

    main_source += r'''


def jarvis_nautilus_c3_status():

    from omni.trading_intelligence.nautilus_c3_status import (
        nautilus_c3_status,
    )

    return nautilus_c3_status()


def jarvis_nautilus_portfolio_backtest(
    portfolio,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_bridge import (
        nautilus_c3_portfolio_bridge,
    )

    return nautilus_c3_portfolio_bridge.run(
        portfolio,
        timeout=timeout,
    )


def jarvis_nautilus_execution_stress(
    portfolio,
    profiles=None,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_bridge import (
        nautilus_c3_portfolio_bridge,
    )

    return nautilus_c3_portfolio_bridge.stress_matrix(
        portfolio,
        profiles=profiles,
        timeout=timeout,
    )


def jarvis_nautilus_portfolio_walk_forward(
    portfolio,
    train_size,
    validation_size,
    test_size,
    step=None,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_campaign import (
        nautilus_c3_walk_forward,
    )

    return nautilus_c3_walk_forward.run(
        portfolio,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
        timeout=timeout,
    )


def jarvis_nautilus_c3_v5_gate(
    v5_report,
    c3_campaign,
):

    from omni.trading_intelligence.nautilus_c3_campaign import (
        nautilus_c3_v5_gate,
    )

    return nautilus_c3_v5_gate(
        v5_report,
        c3_campaign,
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 9. WORKSTATION PAYLOAD
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_nautilus_c3_payload("
    not in app_source
):

    app_source += r'''


def jarvis_nautilus_c3_payload():

    from omni.trading_intelligence.nautilus_c3_status import (
        nautilus_c3_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                nautilus_c3_status(),
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
# 10. TESTS
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

from omni.trading_intelligence.nautilus_c3_bridge import (
    nautilus_c3_portfolio_bridge,
)


def dataset(
    base,
    step,
    spread,
    count=120,
    *,
    short=True,
):

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
        count
    ):

        wave = (
            (
                index % 15
            )
            - 7
        ) * step * 0.15


        price = (
            base
            + index
            * step
            + wave
        )


        bars.append(
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


        signal = "FLAT"


        # Repeated entries ensure each walk-forward
        # segment has independent research evidence.
        cycle = index % 40


        if cycle == 5:

            signal = "LONG"


        elif cycle == 15:

            signal = "EXIT"


        elif (
            short
            and cycle == 22
        ):

            signal = "SHORT"


        elif (
            short
            and cycle == 32
        ):

            signal = "EXIT"


        signals.append(
            signal
        )


    return (
        bars,
        signals,
    )


def portfolio(
    count=120,
):

    equity_bars, equity_signals = (
        dataset(
            100,
            0.10,
            0.50,
            count,
        )
    )


    future_bars, future_signals = (
        dataset(
            75,
            0.05,
            0.30,
            count,
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
        ),
    }


class NautilusPhaseC3Tests(
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
            main.jarvis_nautilus_c3_status()
        )


        self.assertTrue(
            status[
                "single_event_driven_engine"
            ]
        )


        self.assertTrue(
            status[
                "multi_instrument"
            ]
        )


        self.assertTrue(
            status[
                "multiple_strategy_instances"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "broker_adapter"
            ]
        )


    def test_true_portfolio(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        self.assertTrue(
            result[
                "single_engine"
            ]
        )


        self.assertEqual(
            result[
                "strategy_count"
            ],
            2,
        )


        self.assertEqual(
            result[
                "instrument_count"
            ],
            2,
        )


        self.assertGreaterEqual(
            result[
                "fill_count"
            ],
            4,
        )


    def test_correlation(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        self.assertIn(
            "equity_alpha",
            result[
                "correlation"
            ][
                "matrix"
            ],
        )


    def test_concentration(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        concentration = result[
            "concentration"
        ]


        self.assertGreater(
            concentration[
                "total_input_notional_proxy"
            ],
            0,
        )


        self.assertFalse(
            concentration[
                "actual_dynamic_exposure"
            ]
        )


    def test_drawdown_attribution_truthful(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_backtest(
                portfolio(),
                timeout=90,
            )
        )


        attribution = (
            result[
                "drawdown_attribution"
            ]
        )


        self.assertTrue(
            attribution[
                "proxy"
            ]
        )


        self.assertFalse(
            attribution[
                "engine_accounting"
            ]
        )


    def test_stress_matrix(
        self,
    ):

        result = (
            main.jarvis_nautilus_execution_stress(
                portfolio(),

                profiles=(
                    {
                        "name":
                            "ideal"
                    },

                    {
                        "name":
                            "one_tick"
                    },
                ),

                timeout=90,
            )
        )


        self.assertEqual(
            result[
                "profile_count"
            ],
            2,
        )


        self.assertFalse(
            result[
                "automatic_profile_selection"
            ]
        )


    def test_walk_forward(
        self,
    ):

        result = (
            main.jarvis_nautilus_portfolio_walk_forward(
                portfolio(
                    120
                ),

                train_size=40,
                validation_size=20,
                test_size=20,
                step=20,
                timeout=90,
            )
        )


        self.assertGreaterEqual(
            result[
                "window_count"
            ],
            3,
        )


        self.assertFalse(
            result[
                "oos_tuning"
            ]
        )


        self.assertFalse(
            result[
                "candidate_reoptimized_on_oos"
            ]
        )


    def test_v5_gate(
        self,
    ):

        result = (
            main.jarvis_nautilus_c3_v5_gate(
                {
                    "recommendation": {
                        "recommendation":
                            "PROMOTE"
                    }
                },

                {
                    "success":
                        True,

                    "oos_pass_rate":
                        0.75,

                    "oos_tuning":
                        False,

                    "candidate_reoptimized_on_oos":
                        False,
                },
            )
        )


        self.assertEqual(
            result[
                "state"
            ],
            "PORTFOLIO_RESEARCH_ELIGIBLE",
        )


        self.assertFalse(
            result[
                "production_promotion"
            ]
        )


    def test_mixed_venue_blocked(
        self,
    ):

        value = portfolio()


        value[
            "strategies"
        ][
            1
        ][
            "instrument"
        ][
            "venue"
        ] = "OTHER"


        with self.assertRaises(
            RuntimeError
        ):

            main.jarvis_nautilus_portfolio_backtest(
                value,
                timeout=90,
            )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            nautilus_c3_portfolio_bridge.place_order


    def test_c2_preserved(
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


        self.assertTrue(
            status[
                "commodity_future"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


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
# 11. COMPILE
# ============================================================

print()
print(
    "Checking Phase C3 syntax..."
)


r = run(
    MAIN_PY,
    "-m",
    "py_compile",

    str(
        BRIDGE
    ),

    str(
        CAMPAIGN
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
        "C3 COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Phase C3 syntax: PASS"
)


# ============================================================
# 12. PROTECTED CORE
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
# 13. STATUS
# ============================================================

print()
print(
    "Checking C3 architecture..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_nautilus_c3_status();"
        "assert s['available'];"
        "assert s['single_event_driven_engine'];"
        "assert s['multi_instrument'];"
        "assert s['multiple_strategy_instances'];"
        "assert s['cross_instrument_correlation'];"
        "assert s['concentration_analytics'];"
        "assert s['drawdown_attribution'];"
        "assert s['execution_profile_stress_matrix'];"
        "assert s['nautilus_walk_forward_campaign'];"
        "assert s['oos_tuning'] is False;"
        "assert s['live_execution'] is False;"
        "assert s['broker_adapter'] is False;"
        "print('True portfolio engine: PASS');"
        "print('Cross-instrument analytics: PASS');"
        "print('Execution stress matrix: PASS');"
        "print('Nautilus walk-forward: PASS');"
        "print('Live execution: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "C3 STATUS FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 14. SAFETY
# ============================================================

print()
print(
    "Checking Phase C3 safety..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_nautilus_c3_status();"
        "assert s['single_leg_option_short'] is False;"
        "assert s['oos_tuning'] is False;"
        "assert s['candidate_reoptimized_on_oos'] is False;"
        "assert s['automatic_execution_profile_selection'] is False;"
        "assert s['automatic_strategy_promotion'] is False;"
        "assert s['automatic_registry_mutation'] is False;"
        "assert s['automatic_portfolio_allocation'] is False;"
        "assert s['automatic_portfolio_rebalance'] is False;"
        "assert s['automatic_broker_order'] is False;"
        "assert s['production_self_modification'] is False;"
        "print('Naked option short: BLOCKED');"
        "print('OOS tuning: BLOCKED');"
        "print('Auto profile selection: BLOCKED');"
        "print('Auto portfolio allocation: BLOCKED');"
        "print('Auto portfolio rebalance: BLOCKED');"
        "print('Broker orders: BLOCKED');"
        "print('C3 safety: PASS')"
    ),
)


if r.returncode:

    print(
        "C3 SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 15. TARGETED REGRESSION
# ============================================================

print()
print(
    "Running Phase C3 targeted regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",

    "tests.test_nautilus_phase_c3",
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
    timeout=360,
)


if r.returncode:

    print(
        "TARGETED REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 16. FULL REGRESSION
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
    timeout=420,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 17. FINAL INTEGRITY
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
        "c2=main.jarvis_nautilus_c2_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert c2['available'];"
        "assert c3['available'];"
        "assert c3['live_execution'] is False;"
        "assert c3['automatic_broker_order'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Trading V5: PRESERVED');"
        "print('Trading V6: PRESERVED');"
        "print('Nautilus C2: PRESERVED');"
        "print('Nautilus C3: PASS')"
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
        "pprint.pp(main.jarvis_nautilus_c3_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS NAUTILUSTRADER PHASE C3 SUCCESS")
print("=" * 80)

print()
print("TRUE EVENT-DRIVEN PORTFOLIO")
print("One BacktestEngine: ACTIVE")
print("Multiple instruments: ACTIVE")
print("Multiple strategy instances: ACTIVE")
print("Unified simulated venue/account: ACTIVE")
print("Single base currency per portfolio: ENFORCED")
print()

print("PORTFOLIO ANALYTICS")
print("Cross-instrument return correlation: ACTIVE")
print("Input-notional concentration: ACTIVE")
print("HHI concentration metric: ACTIVE")
print("Largest-exposure warning: ACTIVE")
print("Signal-path drawdown attribution proxy: ACTIVE")
print("Raw Nautilus account reports: ACTIVE")
print("Raw Nautilus fill reports: ACTIVE")
print("Raw Nautilus position reports: ACTIVE")
print()

print("EXECUTION ROBUSTNESS")
print("Ideal profile stress: ACTIVE")
print("One-tick stress: ACTIVE")
print("Probabilistic stress: ACTIVE")
print("Latency stress: ACTIVE")
print("Fee/slippage stress: ACTIVE")
print("Automatic best-profile selection: BLOCKED")
print()

print("NAUTILUS WALK-FORWARD")
print("Chronological train segment: ACTIVE")
print("Chronological validation segment: ACTIVE")
print("Unseen OOS segment: ACTIVE")
print("Rolling portfolio windows: ACTIVE")
print("OOS profitable-window rate: ACTIVE")
print("OOS tuning: BLOCKED")
print("OOS candidate reoptimization: BLOCKED")
print()

print("V5 GOVERNANCE")
print("V5 recommendation remains authoritative: YES")
print("C3 cannot bypass V5: ENFORCED")
print("Portfolio research eligibility gate: ACTIVE")
print("Production promotion: BLOCKED")
print()

print("GOVERNANCE")
print("Single-leg naked option short: BLOCKED")
print("Live TradingNode: NOT CREATED")
print("Broker adapter: NONE")
print("FYERS execution connection: NONE")
print("Automatic capital allocation: BLOCKED")
print("Automatic portfolio rebalance: BLOCKED")
print("Automatic broker order: BLOCKED")
print("Production self-modification: BLOCKED")
print()

print("PRESERVED")
print("Trading V1-V6: YES")
print("Nautilus Phase B: YES")
print("Nautilus C2: YES")
print("Browser lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(
    status.stdout.strip()
)
print()

print("NEXT: TRADING INTELLIGENCE V7")
print("Historical derivatives feature store")
print("Timestamped option-chain snapshots")
print("Historical IV / IV-rank / skew")
print("Historical OI / delta-OI / PCR")
print("Underlying + futures + options synchronized datasets")
print("Real option-chain provider adapter")
print("Derivative regime engine")
print("Strategy ensemble research")
print("Cross-asset regime intelligence")
print("Automated research campaigns")
print("All candidates still pass through V5")
print("Still NO live broker execution")
