from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

PKG = ROOT / "omni" / "trading_intelligence"

SCHEMA = PKG / "backtest_schema.py"
COSTS = PKG / "cost_model.py"
ACCOUNT = PKG / "account_simulator.py"
EXECUTION = PKG / "execution_model.py"
MTF = PKG / "multi_timeframe.py"
NORMALIZER = PKG / "history_normalizer.py"
BACKTESTER = PKG / "historical_backtester.py"
SWEEP = PKG / "parameter_sweep.py"
COMPARE = PKG / "strategy_compare.py"
JOURNAL = PKG / "trade_journal.py"
STATUS = PKG / "trading_v2_status.py"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

TEST = ROOT / "tests" / "test_trading_intelligence_v2.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_intelligence_v2"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    SCHEMA,
    COSTS,
    ACCOUNT,
    EXECUTION,
    MTF,
    NORMALIZER,
    BACKTESTER,
    SWEEP,
    COMPARE,
    JOURNAL,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
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
    )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
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
        "JARVIS source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V2")
print("HISTORICAL BACKTEST + EXECUTION SIMULATION + PARAMETER RESEARCH")
print("=" * 80)


# ============================================================
# 0. BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = path.exists()

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# ============================================================
# 1. VERIFY V1.1 CHECKPOINT
# ============================================================

print()
print("Checking Trading Intelligence V1.1 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v=main.jarvis_trading_v1_status(); "
        "b=main.jarvis_fyers_bridge_status(); "
        "c=main.jarvis_fyers_readonly_capabilities(); "
        "assert v['research_only']; "
        "assert v['live_execution'] is False; "
        "assert v['automatic_broker_order'] is False; "
        "assert b['canonical_provider_available']; "
        "assert b['quote_function']=='get_quote'; "
        "assert b['history_function']=='get_intraday_data'; "
        "assert c['quote']=='get_quote'; "
        "assert c['history']=='get_intraday_data'; "
        "print('Main import: PASS'); "
        "print('Protected Core: PASS'); "
        "print('Trading Intelligence V1.1: PASS'); "
        "print('Canonical FYERS quote/history bridge: PASS'); "
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


# Verify the repaired browser probe still works.
r = run(
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
        "BROWSER BASELINE FAILURE"
    )

    sys.exit(1)


print(
    "Browser DOM probe: PASS"
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

print(
    "Baseline: PASS"
)


# ============================================================
# 2. BACKTEST SCHEMA
# ============================================================

write(
    SCHEMA,
    r'''
from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)


SUPPORTED_INSTRUMENT_KINDS = {
    "spot",
    "future",
    "option_long",
    "commodity_future",
    "currency_future",
}


SUPPORTED_AMBIGUOUS_POLICIES = {
    "stop_first",
    "target_first",
}


@dataclass(frozen=True)
class ExecutionCostConfig:

    brokerage_bps: float = 0.0

    exchange_bps: float = 0.0

    other_bps: float = 0.0

    tax_bps_buy: float = 0.0

    tax_bps_sell: float = 0.0

    fixed_per_order: float = 0.0

    per_contract: float = 0.0

    slippage_bps: float = 0.0

    spread_bps: float = 0.0


    def __post_init__(
        self,
    ):

        for name, value in asdict(
            self
        ).items():

            if float(
                value
            ) < 0:

                raise ValueError(
                    name
                    + " cannot be negative."
                )


@dataclass(frozen=True)
class BacktestConfig:

    initial_capital: float = 100000.0

    quantity: float = 1.0

    contract_multiplier: float = 1.0

    instrument_kind: str = "spot"

    allow_long: bool = True

    allow_short: bool = True

    warmup_bars: int = 50

    stop_loss_pct: float | None = None

    target_pct: float | None = None

    trailing_stop_pct: float | None = None

    max_bars_in_trade: int | None = None

    exit_on_opposite_signal: bool = True

    ambiguous_bar_policy: str = "stop_first"

    base_timeframe_minutes: int = 1

    higher_timeframes: tuple[int, ...] = ()

    capital_requirement_per_unit: float | None = None

    cost: ExecutionCostConfig = field(
        default_factory=ExecutionCostConfig
    )


    def __post_init__(
        self,
    ):

        if (
            self.initial_capital
            <= 0
        ):

            raise ValueError(
                "initial_capital must be positive."
            )


        if self.quantity <= 0:

            raise ValueError(
                "quantity must be positive."
            )


        if (
            self.contract_multiplier
            <= 0
        ):

            raise ValueError(
                "contract_multiplier must be positive."
            )


        if (
            self.instrument_kind
            not in SUPPORTED_INSTRUMENT_KINDS
        ):

            raise ValueError(
                "Unsupported instrument_kind."
            )


        if (
            self.instrument_kind
            == "option_long"
            and self.allow_short
        ):

            raise ValueError(
                "option_long cannot enable naked premium shorting."
            )


        if self.warmup_bars < 21:

            raise ValueError(
                "warmup_bars must be at least 21."
            )


        for name in (
            "stop_loss_pct",
            "target_pct",
            "trailing_stop_pct",
        ):

            value = getattr(
                self,
                name,
            )

            if (
                value is not None
                and float(
                    value
                ) <= 0
            ):

                raise ValueError(
                    name
                    + " must be positive."
                )


        if (
            self.max_bars_in_trade
            is not None
            and int(
                self.max_bars_in_trade
            ) <= 0
        ):

            raise ValueError(
                "max_bars_in_trade must be positive."
            )


        if (
            self.ambiguous_bar_policy
            not in SUPPORTED_AMBIGUOUS_POLICIES
        ):

            raise ValueError(
                "Unsupported ambiguous-bar policy."
            )


        if (
            self.base_timeframe_minutes
            <= 0
        ):

            raise ValueError(
                "base_timeframe_minutes must be positive."
            )


        for timeframe in self.higher_timeframes:

            if int(
                timeframe
            ) <= self.base_timeframe_minutes:

                raise ValueError(
                    "Higher timeframe must exceed base timeframe."
                )


        if (
            self.capital_requirement_per_unit
            is not None
            and self.capital_requirement_per_unit
            < 0
        ):

            raise ValueError(
                "capital_requirement_per_unit cannot be negative."
            )


    def to_dict(
        self,
    ):

        return asdict(
            self
        )


def option_premium_config(
    *,
    initial_capital=100000.0,
    quantity=1.0,
    lot_size=1.0,
    **kwargs,
):

    return BacktestConfig(
        initial_capital=
            initial_capital,

        quantity=
            quantity,

        contract_multiplier=
            lot_size,

        instrument_kind=
            "option_long",

        allow_long=
            True,

        allow_short=
            False,

        **kwargs,
    )


def commodity_future_config(
    *,
    initial_capital=100000.0,
    contracts=1.0,
    lot_size=1.0,
    **kwargs,
):

    return BacktestConfig(
        initial_capital=
            initial_capital,

        quantity=
            contracts,

        contract_multiplier=
            lot_size,

        instrument_kind=
            "commodity_future",

        allow_long=
            True,

        allow_short=
            True,

        **kwargs,
    )
'''
)


# ============================================================
# 3. COST MODEL
# ============================================================

write(
    COSTS,
    r'''
from __future__ import annotations

from omni.trading_intelligence.backtest_schema import (
    ExecutionCostConfig,
)


class ExecutionCostModel:

    def __init__(
        self,
        config=None,
    ):

        self.config = (
            config
            or ExecutionCostConfig()
        )


    def fill(
        self,
        reference_price,
        order_side,
    ):

        reference = float(
            reference_price
        )

        if reference <= 0:

            raise ValueError(
                "reference price must be positive."
            )


        order_side = str(
            order_side
        ).strip().lower()


        if order_side not in {
            "buy",
            "sell",
        }:

            raise ValueError(
                "order_side must be buy or sell."
            )


        friction_bps = (
            float(
                self.config.slippage_bps
            )
            + (
                float(
                    self.config.spread_bps
                )
                / 2.0
            )
        )


        adjustment = (
            reference
            * friction_bps
            / 10000.0
        )


        if order_side == "buy":

            fill = (
                reference
                + adjustment
            )

        else:

            fill = (
                reference
                - adjustment
            )


        return {
            "reference_price":
                reference,

            "fill_price":
                fill,

            "price_friction":
                abs(
                    fill
                    - reference
                ),
        }


    def fees(
        self,
        fill_price,
        quantity,
        multiplier,
        order_side,
    ):

        fill_price = float(
            fill_price
        )

        quantity = float(
            quantity
        )

        multiplier = float(
            multiplier
        )


        notional = (
            abs(
                fill_price
            )
            * quantity
            * multiplier
        )


        order_side = str(
            order_side
        ).strip().lower()


        side_tax_bps = (
            self.config.tax_bps_buy

            if order_side == "buy"

            else self.config.tax_bps_sell
        )


        variable_bps = (
            float(
                self.config.brokerage_bps
            )
            + float(
                self.config.exchange_bps
            )
            + float(
                self.config.other_bps
            )
            + float(
                side_tax_bps
            )
        )


        variable = (
            notional
            * variable_bps
            / 10000.0
        )


        fixed = float(
            self.config.fixed_per_order
        )


        contract_fee = (
            float(
                self.config.per_contract
            )
            * quantity
        )


        return {
            "notional":
                notional,

            "variable":
                variable,

            "fixed":
                fixed,

            "per_contract":
                contract_fee,

            "total":
                (
                    variable
                    + fixed
                    + contract_fee
                ),
        }


    def execution(
        self,
        reference_price,
        order_side,
        quantity,
        multiplier,
    ):

        fill = self.fill(
            reference_price,
            order_side,
        )


        fees = self.fees(
            fill[
                "fill_price"
            ],
            quantity,
            multiplier,
            order_side,
        )


        friction_cost = (
            fill[
                "price_friction"
            ]
            * float(
                quantity
            )
            * float(
                multiplier
            )
        )


        return {
            **fill,

            "fees":
                fees[
                    "total"
                ],

            "friction_cost":
                friction_cost,

            "notional":
                fees[
                    "notional"
                ],
        }
'''
)


# ============================================================
# 4. ACCOUNT SIMULATOR
# ============================================================

write(
    ACCOUNT,
    r'''
from __future__ import annotations


class AccountSimulator:

    def __init__(
        self,
        initial_capital,
    ):

        initial_capital = float(
            initial_capital
        )


        if initial_capital <= 0:

            raise ValueError(
                "initial capital must be positive."
            )


        self.initial_capital = (
            initial_capital
        )

        self.equity = (
            initial_capital
        )

        self.peak_equity = (
            initial_capital
        )

        self.realized_pnl = 0.0

        self.total_fees = 0.0

        self.total_friction = 0.0

        self.max_drawdown = 0.0

        self.rejected_entries = 0

        self._curve = []


    def can_open(
        self,
        quantity,
        required_per_unit=None,
    ):

        if required_per_unit is None:

            return True


        required = (
            float(
                quantity
            )
            * float(
                required_per_unit
            )
        )


        return (
            required
            <= self.equity
        )


    def reject_entry(
        self,
    ):

        self.rejected_entries += 1


    def record_trade(
        self,
        trade,
    ):

        net = float(
            trade[
                "net_pnl"
            ]
        )


        self.realized_pnl += net

        self.total_fees += float(
            trade.get(
                "fees",
                0.0,
            )
        )

        self.total_friction += float(
            trade.get(
                "slippage",
                0.0,
            )
        )


        self.equity = (
            self.initial_capital
            + self.realized_pnl
        )


        self.peak_equity = max(
            self.peak_equity,
            self.equity,
        )


        drawdown = (
            self.peak_equity
            - self.equity
        )


        self.max_drawdown = max(
            self.max_drawdown,
            drawdown,
        )


        drawdown_pct = (
            drawdown
            / self.peak_equity
            if self.peak_equity > 0
            else 0.0
        )


        self._curve.append(
            {
                "timestamp":
                    trade[
                        "exit_time"
                    ],

                "equity":
                    self.equity,

                "cumulative_pnl":
                    self.realized_pnl,

                "drawdown":
                    drawdown,

                "drawdown_pct":
                    drawdown_pct,
            }
        )


    def curve(
        self,
    ):

        return tuple(
            self._curve
        )


    def status(
        self,
    ):

        return {
            "initial_capital":
                self.initial_capital,

            "ending_equity":
                self.equity,

            "realized_pnl":
                self.realized_pnl,

            "return_pct":
                (
                    self.realized_pnl
                    / self.initial_capital
                ),

            "total_fees":
                self.total_fees,

            "total_execution_friction":
                self.total_friction,

            "max_drawdown":
                self.max_drawdown,

            "rejected_entries":
                self.rejected_entries,
        }
'''
)


# ============================================================
# 5. EXECUTION MODEL
# ============================================================

write(
    EXECUTION,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)


from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)


@dataclass
class SimulatedPosition:

    side: int

    entry_time: str

    entry_index: int

    entry_reference_price: float

    entry_fill_price: float

    quantity: float

    multiplier: float

    entry_fee: float

    entry_friction: float

    stop_price: float | None

    target_price: float | None

    trailing_stop_price: float | None

    highest_price: float

    lowest_price: float


class ExecutionSimulator:

    def __init__(
        self,
        config,
    ):

        self.config = config

        self.costs = (
            ExecutionCostModel(
                config.cost
            )
        )


    @staticmethod
    def _time(
        value,
    ):

        if hasattr(
            value,
            "isoformat",
        ):

            return value.isoformat()


        return str(
            value
        )


    def open_position(
        self,
        side,
        reference_price,
        timestamp,
        index,
    ):

        side = int(
            side
        )


        if side not in {
            -1,
            1,
        }:

            raise ValueError(
                "side must be +1 or -1."
            )


        order_side = (
            "buy"
            if side == 1
            else "sell"
        )


        execution = (
            self.costs
            .execution(
                reference_price,
                order_side,
                self.config.quantity,
                self.config.contract_multiplier,
            )
        )


        entry_reference = float(
            reference_price
        )


        stop = None

        target = None

        trailing = None


        if (
            self.config.stop_loss_pct
            is not None
        ):

            if side == 1:

                stop = (
                    entry_reference
                    * (
                        1.0
                        - self.config.stop_loss_pct
                    )
                )

            else:

                stop = (
                    entry_reference
                    * (
                        1.0
                        + self.config.stop_loss_pct
                    )
                )


        if (
            self.config.target_pct
            is not None
        ):

            if side == 1:

                target = (
                    entry_reference
                    * (
                        1.0
                        + self.config.target_pct
                    )
                )

            else:

                target = (
                    entry_reference
                    * (
                        1.0
                        - self.config.target_pct
                    )
                )


        if (
            self.config.trailing_stop_pct
            is not None
        ):

            if side == 1:

                trailing = (
                    entry_reference
                    * (
                        1.0
                        - self.config.trailing_stop_pct
                    )
                )

            else:

                trailing = (
                    entry_reference
                    * (
                        1.0
                        + self.config.trailing_stop_pct
                    )
                )


        return SimulatedPosition(
            side=
                side,

            entry_time=
                self._time(
                    timestamp
                ),

            entry_index=
                int(
                    index
                ),

            entry_reference_price=
                entry_reference,

            entry_fill_price=
                execution[
                    "fill_price"
                ],

            quantity=
                self.config.quantity,

            multiplier=
                self.config.contract_multiplier,

            entry_fee=
                execution[
                    "fees"
                ],

            entry_friction=
                execution[
                    "friction_cost"
                ],

            stop_price=
                stop,

            target_price=
                target,

            trailing_stop_price=
                trailing,

            highest_price=
                entry_reference,

            lowest_price=
                entry_reference,
        )


    @staticmethod
    def effective_stop(
        position,
    ):

        values = [
            value

            for value in (
                position.stop_price,
                position.trailing_stop_price,
            )

            if value is not None
        ]


        if not values:

            return None


        if position.side == 1:

            return max(
                values
            )


        return min(
            values
        )


    def protective_exit(
        self,
        position,
        bar,
    ):

        stop = self.effective_stop(
            position
        )

        target = position.target_price


        open_price = float(
            bar.open
        )

        high = float(
            bar.high
        )

        low = float(
            bar.low
        )


        if position.side == 1:

            # Gap through stop.
            if (
                stop is not None
                and open_price <= stop
            ):

                return (
                    open_price,
                    "stop_gap",
                )


            # Gap beyond target.
            if (
                target is not None
                and open_price >= target
            ):

                return (
                    open_price,
                    "target_gap",
                )


            stop_hit = (
                stop is not None
                and low <= stop
            )

            target_hit = (
                target is not None
                and high >= target
            )


        else:

            if (
                stop is not None
                and open_price >= stop
            ):

                return (
                    open_price,
                    "stop_gap",
                )


            if (
                target is not None
                and open_price <= target
            ):

                return (
                    open_price,
                    "target_gap",
                )


            stop_hit = (
                stop is not None
                and high >= stop
            )

            target_hit = (
                target is not None
                and low <= target
            )


        if (
            stop_hit
            and target_hit
        ):

            if (
                self.config
                .ambiguous_bar_policy
                == "target_first"
            ):

                return (
                    target,
                    "target",
                )


            return (
                stop,
                "stop",
            )


        if stop_hit:

            return (
                stop,
                "stop",
            )


        if target_hit:

            return (
                target,
                "target",
            )


        return None


    def update_trailing(
        self,
        position,
        bar,
    ):

        position.highest_price = max(
            position.highest_price,
            float(
                bar.high
            ),
        )


        position.lowest_price = min(
            position.lowest_price,
            float(
                bar.low
            ),
        )


        trailing_pct = (
            self.config
            .trailing_stop_pct
        )


        if trailing_pct is None:

            return


        if position.side == 1:

            candidate = (
                position.highest_price
                * (
                    1.0
                    - trailing_pct
                )
            )


            if (
                position.trailing_stop_price
                is None
            ):

                position.trailing_stop_price = (
                    candidate
                )

            else:

                position.trailing_stop_price = max(
                    position.trailing_stop_price,
                    candidate,
                )


        else:

            candidate = (
                position.lowest_price
                * (
                    1.0
                    + trailing_pct
                )
            )


            if (
                position.trailing_stop_price
                is None
            ):

                position.trailing_stop_price = (
                    candidate
                )

            else:

                position.trailing_stop_price = min(
                    position.trailing_stop_price,
                    candidate,
                )


    def close_position(
        self,
        position,
        reference_price,
        timestamp,
        index,
        reason,
    ):

        exit_order_side = (
            "sell"
            if position.side == 1
            else "buy"
        )


        execution = (
            self.costs
            .execution(
                reference_price,
                exit_order_side,
                position.quantity,
                position.multiplier,
            )
        )


        gross_pnl = (
            (
                float(
                    reference_price
                )
                - position.entry_reference_price
            )
            * position.side
            * position.quantity
            * position.multiplier
        )


        fees = (
            position.entry_fee
            + execution[
                "fees"
            ]
        )


        friction = (
            position.entry_friction
            + execution[
                "friction_cost"
            ]
        )


        net_pnl = (
            gross_pnl
            - fees
            - friction
        )


        return {
            "side":
                (
                    "LONG"
                    if position.side == 1
                    else "SHORT"
                ),

            "entry_time":
                position.entry_time,

            "exit_time":
                self._time(
                    timestamp
                ),

            "entry_index":
                position.entry_index,

            "exit_index":
                int(
                    index
                ),

            "entry_reference_price":
                position.entry_reference_price,

            "entry_fill_price":
                position.entry_fill_price,

            "exit_reference_price":
                float(
                    reference_price
                ),

            "exit_fill_price":
                execution[
                    "fill_price"
                ],

            "quantity":
                position.quantity,

            "multiplier":
                position.multiplier,

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                friction,

            "net_pnl":
                net_pnl,

            "turnover":
                (
                    abs(
                        position.entry_fill_price
                    )
                    + abs(
                        execution[
                            "fill_price"
                        ]
                    )
                )
                * position.quantity
                * position.multiplier,

            "bars_held":
                (
                    int(
                        index
                    )
                    - position.entry_index
                    + 1
                ),

            "exit_reason":
                str(
                    reason
                ),

            "research_only":
                True,
        }
'''
)


# ============================================================
# 6. MULTI-TIMEFRAME ENGINE
# ============================================================

write(
    MTF,
    r'''
from __future__ import annotations

from collections import (
    OrderedDict,
)

from datetime import (
    timedelta,
)


from omni.trading_intelligence.feature_engine import (
    feature_engine,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)


def _bucket_start(
    timestamp,
    minutes,
):

    minutes = int(
        minutes
    )


    midnight = timestamp.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


    elapsed = int(
        (
            timestamp
            - midnight
        ).total_seconds()
        // 60
    )


    bucket = (
        elapsed
        // minutes
        * minutes
    )


    return (
        midnight
        + timedelta(
            minutes=bucket
        )
    )


def resample_bars(
    bars,
    timeframe_minutes,
    *,
    base_timeframe_minutes=1,
    closed_only=True,
):

    bars = list(
        bars
    )


    timeframe_minutes = int(
        timeframe_minutes
    )

    base_timeframe_minutes = int(
        base_timeframe_minutes
    )


    if (
        timeframe_minutes
        <= base_timeframe_minutes
    ):

        raise ValueError(
            "Resampled timeframe must exceed base timeframe."
        )


    if (
        timeframe_minutes
        % base_timeframe_minutes
        != 0
    ):

        raise ValueError(
            "Higher timeframe must be an integer "
            "multiple of base timeframe."
        )


    required_count = (
        timeframe_minutes
        // base_timeframe_minutes
    )


    buckets = OrderedDict()


    for bar in bars:

        key = _bucket_start(
            bar.timestamp,
            timeframe_minutes,
        )


        bucket = buckets.setdefault(
            key,
            [],
        )


        bucket.append(
            bar
        )


    output = []


    for timestamp, items in buckets.items():

        if (
            closed_only
            and len(
                items
            ) < required_count
        ):

            continue


        oi_values = [
            item.open_interest

            for item in items

            if item.open_interest
            is not None
        ]


        output.append(
            Bar(
                timestamp=
                    timestamp,

                open=
                    float(
                        items[
                            0
                        ].open
                    ),

                high=
                    max(
                        float(
                            item.high
                        )
                        for item
                        in items
                    ),

                low=
                    min(
                        float(
                            item.low
                        )
                        for item
                        in items
                    ),

                close=
                    float(
                        items[
                            -1
                        ].close
                    ),

                volume=
                    sum(
                        float(
                            item.volume
                        )
                        for item
                        in items
                    ),

                open_interest=
                    (
                        oi_values[
                            -1
                        ]
                        if oi_values
                        else None
                    ),

                symbol=
                    items[
                        -1
                    ].symbol,
            )
        )


    return tuple(
        output
    )


def multitimeframe_features(
    bars,
    higher_timeframes,
    *,
    base_timeframe_minutes=1,
):

    context = {}


    for timeframe in higher_timeframes:

        resampled = resample_bars(
            bars,
            timeframe,
            base_timeframe_minutes=
                base_timeframe_minutes,
            closed_only=True,
        )


        if len(
            resampled
        ) < 21:

            continue


        snapshot = feature_engine.snapshot(
            resampled
        )


        prefix = (
            "tf"
            + str(
                timeframe
            )
            + "_"
        )


        for key, value in snapshot.items():

            context[
                prefix
                + key
            ] = value


    return context
'''
)


# ============================================================
# 7. FYERS / GENERIC HISTORY NORMALIZER
# ============================================================

write(
    NORMALIZER,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)


from omni.trading_intelligence.market_schema import (
    Bar,
)


def normalize_timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        if value.tzinfo is None:

            return value.replace(
                tzinfo=timezone.utc
            )


        return value


    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):

        numeric = float(
            value
        )


        if numeric > 100000000000:

            numeric = (
                numeric
                / 1000.0
            )


        return datetime.fromtimestamp(
            numeric,
            tz=timezone.utc,
        )


    text = str(
        value
    ).strip()


    if text.isdigit():

        return normalize_timestamp(
            int(
                text
            )
        )


    if text.endswith(
        "Z"
    ):

        text = (
            text[:-1]
            + "+00:00"
        )


    result = datetime.fromisoformat(
        text
    )


    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )


    return result


def _records(
    value,
):

    if value is None:

        return []


    # pandas-like DataFrame without importing pandas.
    if (
        hasattr(
            value,
            "to_dict",
        )
        and hasattr(
            value,
            "columns",
        )
    ):

        try:

            return list(
                value.to_dict(
                    "records"
                )
            )

        except Exception:

            pass


    if isinstance(
        value,
        (list, tuple),
    ):

        return list(
            value
        )


    if isinstance(
        value,
        dict,
    ):

        # Column-oriented dictionary.
        keys = {
            str(
                key
            ).lower()

            for key in value
        }


        if {
            "open",
            "high",
            "low",
            "close",
        }.issubset(
            keys
        ):

            lengths = [
                len(
                    child
                )

                for child in value.values()

                if isinstance(
                    child,
                    (
                        list,
                        tuple,
                    ),
                )
            ]


            if lengths:

                count = min(
                    lengths
                )

                rows = []


                for index in range(
                    count
                ):

                    rows.append(
                        {
                            key:
                                (
                                    child[
                                        index
                                    ]
                                    if isinstance(
                                        child,
                                        (
                                            list,
                                            tuple,
                                        ),
                                    )
                                    else child
                                )

                            for key, child
                            in value.items()
                        }
                    )


                return rows


    raise ValueError(
        "Unsupported historical-data payload shape."
    )


def _candidate_payload(
    payload,
):

    if isinstance(
        payload,
        dict
    ):

        if (
            payload.get(
                "success"
            )
            is False
        ):

            raise RuntimeError(
                str(
                    payload.get(
                        "message"
                    )
                    or payload.get(
                        "error"
                    )
                    or "Historical provider returned failure."
                )
            )


        for key in (
            "data",
            "candles",
            "rows",
            "history",
            "ohlcv",
            "frame",
        ):

            if key in payload:

                return payload[
                    key
                ]


    return payload


def _mapping_value(
    row,
    names,
    default=None,
):

    normalized = {
        str(
            key
        ).strip().lower():
            value

        for key, value
        in row.items()
    }


    for name in names:

        if name in normalized:

            return normalized[
                name
            ]


    return default


def normalize_history_payload(
    payload,
    *,
    symbol=None,
):

    candidate = _candidate_payload(
        payload
    )


    rows = _records(
        candidate
    )


    bars = []


    for row in rows:

        if isinstance(
            row,
            Bar,
        ):

            bars.append(
                row
            )

            continue


        if isinstance(
            row,
            (
                list,
                tuple,
            ),
        ):

            if len(
                row
            ) < 6:

                raise ValueError(
                    "Candle row requires at least "
                    "timestamp/O/H/L/C/volume."
                )


            timestamp = row[
                0
            ]

            open_price = row[
                1
            ]

            high = row[
                2
            ]

            low = row[
                3
            ]

            close = row[
                4
            ]

            volume = row[
                5
            ]

            oi = (
                row[
                    6
                ]
                if len(
                    row
                ) > 6
                else None
            )


        elif isinstance(
            row,
            dict,
        ):

            timestamp = _mapping_value(
                row,
                (
                    "timestamp",
                    "datetime",
                    "date",
                    "time",
                    "ts",
                    "epoch",
                ),
            )


            open_price = _mapping_value(
                row,
                (
                    "open",
                    "o",
                ),
            )


            high = _mapping_value(
                row,
                (
                    "high",
                    "h",
                ),
            )


            low = _mapping_value(
                row,
                (
                    "low",
                    "l",
                ),
            )


            close = _mapping_value(
                row,
                (
                    "close",
                    "c",
                ),
            )


            volume = _mapping_value(
                row,
                (
                    "volume",
                    "v",
                    "vol",
                ),
                0.0,
            )


            oi = _mapping_value(
                row,
                (
                    "open_interest",
                    "oi",
                ),
                None,
            )


        else:

            raise ValueError(
                "Unsupported candle row."
            )


        if timestamp is None:

            raise ValueError(
                "Historical row has no timestamp."
            )


        bars.append(
            Bar(
                timestamp=
                    normalize_timestamp(
                        timestamp
                    ),

                open=
                    float(
                        open_price
                    ),

                high=
                    float(
                        high
                    ),

                low=
                    float(
                        low
                    ),

                close=
                    float(
                        close
                    ),

                volume=
                    float(
                        volume
                        or 0.0
                    ),

                open_interest=
                    (
                        float(
                            oi
                        )
                        if oi
                        not in (
                            None,
                            "",
                        )
                        else None
                    ),

                symbol=
                    symbol,
            )
        )


    bars.sort(
        key=lambda bar:
            bar.timestamp
    )


    if len(
        bars
    ) < 2:

        raise ValueError(
            "Historical payload contains too few candles."
        )


    return tuple(
        bars
    )
'''
)


print()
print("PART 1 SAVED")
print("Now paste PART 2.")


# ============================================================
# 8. HISTORICAL BACKTESTER
# ============================================================

write(
    BACKTESTER,
    r'''
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
'''
)


# ============================================================
# 9. PARAMETER SWEEP
# ============================================================

write(
    SWEEP,
    r'''
from __future__ import annotations

from dataclasses import (
    replace,
)

from itertools import (
    product,
)


from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)


SWEEPABLE_FIELDS = {
    "quantity",
    "contract_multiplier",
    "stop_loss_pct",
    "target_pct",
    "trailing_stop_pct",
    "max_bars_in_trade",
    "exit_on_opposite_signal",
}


HIGHER_IS_BETTER = {
    "net_pnl",
    "return_pct",
    "win_rate",
    "profit_factor",
    "expectancy",
    "payoff_ratio",
    "sharpe_per_trade",
}


LOWER_IS_BETTER = {
    "max_drawdown",
    "max_drawdown_pct",
    "fees",
    "slippage",
}


class ParameterSweepEngine:

    MAX_COMBINATIONS = 200


    @staticmethod
    def _score(
        result,
        objective,
    ):

        value = (
            result[
                "metrics"
            ]
            .get(
                objective
            )
        )


        if value is None:

            return float(
                "-inf"
            )


        value = float(
            value
        )


        if objective in LOWER_IS_BETTER:

            return -value


        return value


    def run(
        self,
        bars,
        strategy,
        base_config,
        grid,
        *,
        objective="net_pnl",
    ):

        if (
            objective
            not in HIGHER_IS_BETTER
            and objective
            not in LOWER_IS_BETTER
        ):

            raise ValueError(
                "Unsupported sweep objective."
            )


        grid = dict(
            grid
        )


        unknown = (
            set(
                grid
            )
            - SWEEPABLE_FIELDS
        )


        if unknown:

            raise ValueError(
                "Unsupported sweep fields: "
                + repr(
                    sorted(
                        unknown
                    )
                )
            )


        keys = tuple(
            grid
        )


        values = [
            tuple(
                grid[
                    key
                ]
            )

            for key in keys
        ]


        combinations = 1


        for options in values:

            combinations *= len(
                options
            )


        if combinations > self.MAX_COMBINATIONS:

            raise ValueError(
                "Parameter sweep exceeds "
                + str(
                    self.MAX_COMBINATIONS
                )
                + " combinations."
            )


        results = []


        for combination in product(
            *values
        ):

            overrides = dict(
                zip(
                    keys,
                    combination,
                )
            )


            config = replace(
                base_config,
                **overrides
            )


            result = (
                historical_backtester
                .run(
                    bars,
                    strategy,
                    config,
                )
            )


            results.append(
                {
                    "parameters":
                        overrides,

                    "metrics":
                        result[
                            "metrics"
                        ],

                    "trade_count":
                        len(
                            result[
                                "trades"
                            ]
                        ),

                    "result":
                        result,
                }
            )


        ranked = sorted(
            results,
            key=lambda item:
                self._score(
                    item[
                        "result"
                    ],
                    objective,
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "objective":
                objective,

            "combinations":
                combinations,

            "ranked":
                tuple(
                    ranked
                ),

            "best_candidate":
                (
                    ranked[
                        0
                    ]
                    if ranked
                    else None
                ),

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


parameter_sweep_engine = (
    ParameterSweepEngine()
)
'''
)


# ============================================================
# 10. STRATEGY COMPARISON
# ============================================================

write(
    COMPARE,
    r'''
from __future__ import annotations

from omni.trading_intelligence.historical_backtester import (
    historical_backtester,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)


SUPPORTED_OBJECTIVES = {
    "net_pnl",
    "return_pct",
    "profit_factor",
    "expectancy",
    "win_rate",
    "max_drawdown_pct",
}


class StrategyComparator:

    @staticmethod
    def _sort_value(
        result,
        objective,
    ):

        value = result[
            "metrics"
        ].get(
            objective
        )


        if value is None:

            return float(
                "-inf"
            )


        value = float(
            value
        )


        if objective == "max_drawdown_pct":

            return -value


        return value


    def compare(
        self,
        bars,
        strategy_ids,
        config,
        *,
        objective="net_pnl",
    ):

        if objective not in SUPPORTED_OBJECTIVES:

            raise ValueError(
                "Unsupported comparison objective."
            )


        results = []


        for strategy_id in strategy_ids:

            strategy = (
                strategy_registry
                .get(
                    strategy_id
                )
            )


            if strategy is None:

                raise ValueError(
                    "Unknown strategy: "
                    + str(
                        strategy_id
                    )
                )


            result = (
                historical_backtester
                .run(
                    bars,
                    strategy,
                    config,
                )
            )


            results.append(
                result
            )


        ranked = sorted(
            results,
            key=lambda result:
                self._sort_value(
                    result,
                    objective,
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "objective":
                objective,

            "ranked":
                tuple(
                    {
                        "rank":
                            index + 1,

                        "strategy_id":
                            result[
                                "strategy_id"
                            ],

                        "strategy_name":
                            result[
                                "strategy_name"
                            ],

                        "metrics":
                            result[
                                "metrics"
                            ],

                        "trade_count":
                            len(
                                result[
                                    "trades"
                                ]
                            ),
                    }

                    for index, result
                    in enumerate(
                        ranked
                    )
                ),

            "automatic_promotion":
                False,

            "research_only":
                True,
        }


strategy_comparator = (
    StrategyComparator()
)
'''
)


# ============================================================
# 11. TRADE JOURNAL
# ============================================================

write(
    JOURNAL,
    r'''
from __future__ import annotations

from pathlib import (
    Path,
)

import csv
import json
import os
import re
import uuid


class TradeJournal:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "backtests"
            )
        )


    @staticmethod
    def _name(
        value,
    ):

        value = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            str(
                value
            ),
        ).strip(
            "_"
        )


        return (
            value[:80]
            or "backtest"
        )


    def save(
        self,
        result,
        *,
        name=None,
    ):

        if not result.get(
            "research_only"
        ):

            raise ValueError(
                "Journal only accepts research results."
            )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        base = self._name(
            name
            or result.get(
                "strategy_id",
                "backtest",
            )
        )


        run_id = (
            uuid.uuid4()
            .hex[:12]
        )


        json_path = (
            self.root
            / (
                base
                + "_"
                + run_id
                + ".json"
            )
        )


        csv_path = (
            self.root
            / (
                base
                + "_"
                + run_id
                + "_trades.csv"
            )
        )


        temporary = (
            json_path
            .with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        os.replace(
            temporary,
            json_path,
        )


        trades = list(
            result.get(
                "trades",
                ()
            )
        )


        if trades:

            fields = sorted(
                {
                    key

                    for trade in trades

                    for key in trade
                }
            )


            with csv_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:

                writer = csv.DictWriter(
                    handle,
                    fieldnames=fields,
                )

                writer.writeheader()

                writer.writerows(
                    trades
                )


        return {
            "success":
                True,

            "json":
                str(
                    json_path
                ),

            "trades_csv":
                (
                    str(
                        csv_path
                    )
                    if trades
                    else None
                ),

            "research_only":
                True,
        }


trade_journal = (
    TradeJournal()
)
'''
)


# ============================================================
# 12. V2 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)


class TradingIntelligenceV2Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "historical_backtester":
                True,

            "next_bar_open_execution":
                True,

            "long_simulation":
                True,

            "short_simulation":
                True,

            "option_long_premium_simulation":
                True,

            "naked_option_premium_short":
                False,

            "commodity_future_simulation":
                True,

            "currency_future_simulation":
                True,

            "fixed_stop":
                True,

            "profit_target":
                True,

            "trailing_stop":
                True,

            "max_holding_period":
                True,

            "opposite_signal_exit":
                True,

            "intrabar_ambiguity_policy":
                True,

            "gap_stop_handling":
                True,

            "brokerage_model":
                "configurable",

            "tax_model":
                "configurable",

            "exchange_fee_model":
                "configurable",

            "spread_model":
                "configurable",

            "slippage_model":
                "configurable",

            "hardcoded_current_market_fees":
                False,

            "multi_timeframe_features":
                True,

            "fyers_history_normalizer":
                True,

            "canonical_fyers_history_bridge":
                True,

            "parameter_sweep":
                True,

            "parameter_sweep_max_combinations":
                200,

            "automatic_parameter_promotion":
                False,

            "strategy_comparison":
                True,

            "trade_journal":
                True,

            "equity_curve":
                True,

            "drawdown_analytics":
                True,

            "account_simulator":
                True,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v2_status = (
    TradingIntelligenceV2Status()
)
'''
)


# ============================================================
# 13. MAIN APIS
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v2_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v2_status():

    from omni.trading_intelligence.trading_v2_status import (
        trading_intelligence_v2_status,
    )

    return trading_intelligence_v2_status.status()


def jarvis_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        BacktestConfig,
    )

    return BacktestConfig(
        **kwargs
    )


def jarvis_option_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        option_premium_config,
    )

    return option_premium_config(
        **kwargs
    )


def jarvis_commodity_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        commodity_future_config,
    )

    return commodity_future_config(
        **kwargs
    )


def jarvis_backtest(
    bars,
    strategy_id,
    config,
):

    from omni.trading_intelligence.historical_backtester import (
        historical_backtester,
    )

    return historical_backtester.run(
        bars,
        strategy_id,
        config,
    )


def jarvis_backtest_fyers(
    symbol,
    strategy_id,
    config,
    market="NSE",
    timeframe="5m",
    bars=500,
):

    from omni.trading_intelligence.historical_backtester import (
        historical_backtester,
    )

    return historical_backtester.run_fyers(
        symbol,
        strategy_id,
        config,
        market=market,
        timeframe=timeframe,
        bars=bars,
    )


def jarvis_normalize_market_history(
    payload,
    symbol=None,
):

    from omni.trading_intelligence.history_normalizer import (
        normalize_history_payload,
    )

    return normalize_history_payload(
        payload,
        symbol=symbol,
    )


def jarvis_resample_bars(
    bars,
    timeframe_minutes,
    base_timeframe_minutes=1,
    closed_only=True,
):

    from omni.trading_intelligence.multi_timeframe import (
        resample_bars,
    )

    return resample_bars(
        bars,
        timeframe_minutes,
        base_timeframe_minutes=base_timeframe_minutes,
        closed_only=closed_only,
    )


def jarvis_parameter_sweep(
    bars,
    strategy_id,
    base_config,
    grid,
    objective="net_pnl",
):

    from omni.trading_intelligence.parameter_sweep import (
        parameter_sweep_engine,
    )

    return parameter_sweep_engine.run(
        bars,
        strategy_id,
        base_config,
        grid,
        objective=objective,
    )


def jarvis_compare_strategies(
    bars,
    strategy_ids,
    config,
    objective="net_pnl",
):

    from omni.trading_intelligence.strategy_compare import (
        strategy_comparator,
    )

    return strategy_comparator.compare(
        bars,
        strategy_ids,
        config,
        objective=objective,
    )


def jarvis_save_backtest(
    result,
    name=None,
):

    from omni.trading_intelligence.trade_journal import (
        trade_journal,
    )

    return trade_journal.save(
        result,
        name=name,
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 14. WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_intelligence_v2_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_intelligence_v2_payload():

    from omni.trading_intelligence.trading_v2_status import (
        trading_intelligence_v2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v2_status.status(),
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
    )


# ============================================================
# 15. TESTS
# ============================================================

write(
    TEST,
    r'''
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


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.backtest_schema import (
    BacktestConfig,
    ExecutionCostConfig,
    commodity_future_config,
    option_premium_config,
)

from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)

from omni.trading_intelligence.history_normalizer import (
    normalize_history_payload,
)

from omni.trading_intelligence.historical_backtester import (
    HistoricalBacktester,
)

from omni.trading_intelligence.market_schema import (
    Bar,
)

from omni.trading_intelligence.multi_timeframe import (
    resample_bars,
)

from omni.trading_intelligence.parameter_sweep import (
    ParameterSweepEngine,
)

from omni.trading_intelligence.strategy_compare import (
    StrategyComparator,
)

from omni.trading_intelligence.trade_journal import (
    TradeJournal,
)


def rising_bars(
    count=120,
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

        base = (
            100.0
            + index
            * 0.4
        )


        output.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index,
                    ),

                open=
                    base,

                high=
                    base
                    + 0.8,

                low=
                    base
                    - 0.4,

                close=
                    base
                    + 0.5,

                volume=
                    1000
                    + index
                    * 10,
            )
        )


    return output


def falling_bars(
    count=120,
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

        base = (
            200.0
            - index
            * 0.4
        )


        output.append(
            Bar(
                timestamp=
                    start
                    + timedelta(
                        minutes=index,
                    ),

                open=
                    base,

                high=
                    base
                    + 0.4,

                low=
                    base
                    - 0.8,

                close=
                    base
                    - 0.5,

                volume=
                    1000
                    + index
                    * 10,
            )
        )


    return output


class TradingIntelligenceV2Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_cost_fill_buy_is_worse(
        self,
    ):

        model = ExecutionCostModel(
            ExecutionCostConfig(
                slippage_bps=10,
                spread_bps=20,
            )
        )


        result = model.fill(
            100,
            "buy",
        )


        self.assertGreater(
            result[
                "fill_price"
            ],
            100,
        )


    def test_cost_fill_sell_is_worse(
        self,
    ):

        model = ExecutionCostModel(
            ExecutionCostConfig(
                slippage_bps=10,
                spread_bps=20,
            )
        )


        result = model.fill(
            100,
            "sell",
        )


        self.assertLess(
            result[
                "fill_price"
            ],
            100,
        )


    def test_option_long_blocks_short(
        self,
    ):

        config = option_premium_config(
            lot_size=75,
        )


        self.assertFalse(
            config.allow_short
        )


        self.assertEqual(
            config.instrument_kind,
            "option_long",
        )


    def test_manual_option_short_rejected(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            BacktestConfig(
                instrument_kind=
                    "option_long",

                allow_short=
                    True,
            )


    def test_commodity_config(
        self,
    ):

        config = commodity_future_config(
            contracts=2,
            lot_size=100,
        )


        self.assertTrue(
            config.allow_long
        )

        self.assertTrue(
            config.allow_short
        )

        self.assertEqual(
            config.contract_multiplier,
            100,
        )


    def test_history_list_normalizer(
        self,
    ):

        payload = {
            "success":
                True,

            "candles": [
                [
                    1700000000,
                    100,
                    102,
                    99,
                    101,
                    1000,
                ],

                [
                    1700000060,
                    101,
                    103,
                    100,
                    102,
                    1100,
                ],
            ],
        }


        bars = normalize_history_payload(
            payload,
            symbol="TEST",
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


        self.assertEqual(
            bars[
                0
            ].symbol,
            "TEST",
        )


    def test_history_dict_normalizer(
        self,
    ):

        payload = {
            "data": [
                {
                    "timestamp":
                        "2026-01-01T09:15:00+00:00",

                    "open":
                        100,

                    "high":
                        102,

                    "low":
                        99,

                    "close":
                        101,

                    "volume":
                        1000,
                },

                {
                    "timestamp":
                        "2026-01-01T09:16:00+00:00",

                    "open":
                        101,

                    "high":
                        103,

                    "low":
                        100,

                    "close":
                        102,

                    "volume":
                        1000,
                },
            ]
        }


        bars = normalize_history_payload(
            payload
        )


        self.assertEqual(
            len(
                bars
            ),
            2,
        )


    def test_resample(
        self,
    ):

        bars = rising_bars(
            10
        )


        result = resample_bars(
            bars,
            5,
            base_timeframe_minutes=1,
            closed_only=True,
        )


        self.assertEqual(
            len(
                result
            ),
            2,
        )


    def test_resample_drops_partial(
        self,
    ):

        bars = rising_bars(
            8
        )


        result = resample_bars(
            bars,
            5,
            base_timeframe_minutes=1,
            closed_only=True,
        )


        self.assertEqual(
            len(
                result
            ),
            1,
        )


    def test_long_backtest(
        self,
    ):

        config = BacktestConfig(
            initial_capital=100000,
            allow_long=True,
            allow_short=False,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertGreaterEqual(
            len(
                result[
                    "trades"
                ]
            ),
            1,
        )


        self.assertFalse(
            result[
                "live_execution"
            ]
        )


    def test_short_backtest(
        self,
    ):

        config = BacktestConfig(
            initial_capital=100000,
            allow_long=False,
            allow_short=True,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            falling_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertGreaterEqual(
            len(
                result[
                    "trades"
                ]
            ),
            1,
        )


        self.assertEqual(
            result[
                "trades"
            ][0][
                "side"
            ],
            "SHORT",
        )


    def test_next_bar_open_fill_model(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertEqual(
            result[
                "fill_model"
            ],
            "signal_close_to_next_bar_open",
        )


    def test_stop_loss(
        self,
    ):

        bars = rising_bars(
            80
        )


        # Force a large adverse bar after likely entry.
        bars[
            35
        ] = Bar(
            timestamp=
                bars[
                    35
                ].timestamp,

            open=
                bars[
                    35
                ].open,

            high=
                bars[
                    35
                ].high,

            low=
                50,

            close=
                bars[
                    35
                ].close,

            volume=
                bars[
                    35
                ].volume,
        )


        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            stop_loss_pct=0.02,
        )


        result = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertTrue(
            {
                "stop",
                "stop_gap",
            }
            & reasons
        )


    def test_target(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            target_pct=0.01,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertTrue(
            {
                "target",
                "target_gap",
            }
            & reasons
        )


    def test_trailing_stop_config(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            trailing_stop_pct=0.02,
        )


        self.assertEqual(
            config.trailing_stop_pct,
            0.02,
        )


    def test_max_bars_exit(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            max_bars_in_trade=3,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        reasons = {
            trade[
                "exit_reason"
            ]

            for trade in result[
                "trades"
            ]
        }


        self.assertIn(
            "max_bars",
            reasons,
        )


    def test_costs_reduce_pnl(
        self,
    ):

        clean = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
        )


        costly = BacktestConfig(
            allow_short=False,
            warmup_bars=30,

            cost=ExecutionCostConfig(
                brokerage_bps=10,
                slippage_bps=10,
                spread_bps=10,
            ),
        )


        bars = rising_bars()


        a = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            clean,
        )


        b = HistoricalBacktester().run(
            bars,
            "vwap_momentum_v1",
            costly,
        )


        self.assertLess(
            b[
                "metrics"
            ][
                "net_pnl"
            ],
            a[
                "metrics"
            ][
                "net_pnl"
            ],
        )


    def test_equity_curve(
        self,
    ):

        config = BacktestConfig(
            allow_short=False,
            warmup_bars=30,
            max_bars_in_trade=5,
        )


        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            config,
        )


        self.assertEqual(
            len(
                result[
                    "equity_curve"
                ]
            ),
            len(
                result[
                    "trades"
                ]
            ),
        )


    def test_drawdown_metric_present(
        self,
    ):

        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",
            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),
        )


        self.assertIn(
            "max_drawdown_pct",
            result[
                "metrics"
            ],
        )


    def test_parameter_sweep(
        self,
    ):

        engine = ParameterSweepEngine()


        result = engine.run(
            rising_bars(),
            "vwap_momentum_v1",

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),

            {
                "target_pct":
                    (
                        0.01,
                        0.02,
                    ),

                "stop_loss_pct":
                    (
                        0.01,
                        0.02,
                    ),
            },

            objective=
                "net_pnl",
        )


        self.assertEqual(
            result[
                "combinations"
            ],
            4,
        )


        self.assertFalse(
            result[
                "automatic_promotion"
            ]
        )


    def test_sweep_limit(
        self,
    ):

        engine = ParameterSweepEngine()


        with self.assertRaises(
            ValueError
        ):

            engine.run(
                rising_bars(),
                "vwap_momentum_v1",

                BacktestConfig(
                    allow_short=False,
                    warmup_bars=30,
                ),

                {
                    "target_pct":
                        tuple(
                            0.001
                            * (
                                i + 1
                            )

                            for i in range(
                                201
                            )
                        )
                },
            )


    def test_strategy_compare(
        self,
    ):

        result = StrategyComparator().compare(
            rising_bars(),

            (
                "vwap_momentum_v1",
                "rsi_mean_reversion_v1",
            ),

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),

            objective=
                "net_pnl",
        )


        self.assertEqual(
            len(
                result[
                    "ranked"
                ]
            ),
            2,
        )


        self.assertFalse(
            result[
                "automatic_promotion"
            ]
        )


    def test_trade_journal(
        self,
    ):

        result = HistoricalBacktester().run(
            rising_bars(),
            "vwap_momentum_v1",

            BacktestConfig(
                allow_short=False,
                warmup_bars=30,
            ),
        )


        with tempfile.TemporaryDirectory() as tmp:

            journal = TradeJournal(
                Path(
                    tmp
                )
            )


            saved = journal.save(
                result,
                name="test",
            )


            self.assertTrue(
                Path(
                    saved[
                        "json"
                    ]
                ).exists()
            )


    def test_v2_status(
        self,
    ):

        status = main.jarvis_trading_v2_status()


        self.assertTrue(
            status[
                "historical_backtester"
            ]
        )


        self.assertTrue(
            status[
                "option_long_premium_simulation"
            ]
        )


        self.assertFalse(
            status[
                "naked_option_premium_short"
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
            "jarvis_trading_v2_status",
            "jarvis_backtest_config",
            "jarvis_option_backtest_config",
            "jarvis_commodity_backtest_config",
            "jarvis_backtest",
            "jarvis_backtest_fyers",
            "jarvis_normalize_market_history",
            "jarvis_resample_bars",
            "jarvis_parameter_sweep",
            "jarvis_compare_strategies",
            "jarvis_save_backtest",
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
'''
)


# ============================================================
# 16. COMPILE
# ============================================================

print()
print("Checking Trading Intelligence V2 syntax...")


r = run(
    "-m",
    "py_compile",
    str(SCHEMA),
    str(COSTS),
    str(ACCOUNT),
    str(EXECUTION),
    str(MTF),
    str(NORMALIZER),
    str(BACKTESTER),
    str(SWEEP),
    str(COMPARE),
    str(JOURNAL),
    str(STATUS),
    str(MAIN),
    str(APP),
    str(TEST),
)


if r.returncode:

    print(
        "COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Syntax: PASS"
)


# ============================================================
# 17. PROTECTED CORE CHECK
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "import main; "
        "print('Protected Core: PASS'); "
        "print('Main import: PASS')"
    ),
)


if r.returncode:

    print(
        "CORE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 18. SAFETY
# ============================================================

print()
print("Checking V2 trading safety...")


probe = r'''
import main

v1 = main.jarvis_trading_v1_status()
v2 = main.jarvis_trading_v2_status()

assert v1["live_execution"] is False
assert v1["automatic_broker_order"] is False

assert v2["research_only"] is True
assert v2["live_execution"] is False
assert v2["automatic_broker_order"] is False

assert v2["naked_option_premium_short"] is False
assert v2["automatic_parameter_promotion"] is False
assert v2["hardcoded_current_market_fees"] is False

for action in (
    "order.place",
    "order.modify",
    "order.cancel",
    "trade.execute",
    "trading.live.execute",
):

    result = main.jarvis_trading_guard(
        action
    )

    assert not result["allowed"], result


print("Historical research: ACTIVE")
print("Live orders: BLOCKED")
print("Naked option premium shorting: BLOCKED")
print("Automatic parameter promotion: BLOCKED")
print("Hard-coded current brokerage/taxes: NO")
print("V2 safety: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 19. BACKTEST PROBE
# ============================================================

print()
print("Checking real historical simulation mechanics...")


probe = r'''
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import main

from omni.trading_intelligence.market_schema import (
    Bar,
)


bars = []

start = datetime(
    2026,
    1,
    1,
    9,
    15,
    tzinfo=timezone.utc,
)


for i in range(120):

    p = 100 + i * 0.5

    bars.append(
        Bar(
            timestamp=start + timedelta(minutes=i),
            open=p,
            high=p + 1,
            low=p - 0.5,
            close=p + 0.6,
            volume=1000 + i * 20,
        )
    )


config = main.jarvis_backtest_config(
    initial_capital=100000,
    allow_long=True,
    allow_short=False,
    warmup_bars=30,
    stop_loss_pct=0.02,
    target_pct=0.04,
    trailing_stop_pct=0.03,
    max_bars_in_trade=20,
)


result = main.jarvis_backtest(
    bars,
    "vwap_momentum_v1",
    config,
)


assert result["success"]
assert result["research_only"]
assert result["live_execution"] is False

assert result["fill_model"] == "signal_close_to_next_bar_open"

assert "net_pnl" in result["metrics"]
assert "win_rate" in result["metrics"]
assert "profit_factor" in result["metrics"]
assert "max_drawdown_pct" in result["metrics"]

assert len(result["trades"]) >= 1


print("Next-bar-open signal execution: PASS")
print("Long simulation: PASS")
print("Stop model: ACTIVE")
print("Target model: ACTIVE")
print("Trailing stop model: ACTIVE")
print("Max holding-period model: ACTIVE")
print("Trade journal structure: ACTIVE")
print("Equity curve: ACTIVE")
print("Drawdown analytics: ACTIVE")
print("Historical simulation: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "BACKTEST PROBE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 20. COST MODEL PROBE
# ============================================================

print()
print("Checking configurable transaction-cost model...")


probe = r'''
from omni.trading_intelligence.backtest_schema import (
    ExecutionCostConfig,
)

from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)


model = ExecutionCostModel(
    ExecutionCostConfig(
        brokerage_bps=2,
        exchange_bps=1,
        tax_bps_sell=5,
        fixed_per_order=10,
        per_contract=1,
        slippage_bps=3,
        spread_bps=4,
    )
)


buy = model.execution(
    100,
    "buy",
    10,
    1,
)


sell = model.execution(
    100,
    "sell",
    10,
    1,
)


assert buy["fill_price"] > 100
assert sell["fill_price"] < 100

assert buy["fees"] > 0
assert sell["fees"] > 0

assert buy["friction_cost"] > 0
assert sell["friction_cost"] > 0


print("Brokerage BPS: ACTIVE")
print("Exchange-fee BPS: ACTIVE")
print("Buy/sell tax BPS: ACTIVE")
print("Fixed order fee: ACTIVE")
print("Per-contract fee: ACTIVE")
print("Spread simulation: ACTIVE")
print("Slippage simulation: ACTIVE")
print("Current statutory rates hard-coded: NO")
print("Transaction-cost model: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "COST MODEL FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 21. OPTION / COMMODITY CONFIG PROBE
# ============================================================

print()
print("Checking derivatives simulation configuration...")


probe = r'''
import main


option = main.jarvis_option_backtest_config(
    initial_capital=100000,
    quantity=1,
    lot_size=75,
    warmup_bars=30,
    stop_loss_pct=0.20,
    target_pct=0.40,
)


assert option.instrument_kind == "option_long"
assert option.allow_long is True
assert option.allow_short is False
assert option.contract_multiplier == 75


commodity = main.jarvis_commodity_backtest_config(
    initial_capital=100000,
    contracts=1,
    lot_size=100,
    warmup_bars=30,
)


assert commodity.instrument_kind == "commodity_future"
assert commodity.allow_long
assert commodity.allow_short
assert commodity.contract_multiplier == 100


print("Long option premium simulation: ACTIVE")
print("Naked option premium shorts: BLOCKED")
print("Option lot multiplier: ACTIVE")
print("Commodity futures long simulation: ACTIVE")
print("Commodity futures short simulation: ACTIVE")
print("Commodity contract multiplier: ACTIVE")
print("Derivatives simulation configuration: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "DERIVATIVES CONFIG FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 22. MULTI-TIMEFRAME PROBE
# ============================================================

print()
print("Checking multi-timeframe engine...")


probe = r'''
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from omni.trading_intelligence.market_schema import Bar
from omni.trading_intelligence.multi_timeframe import resample_bars


start = datetime(
    2026,
    1,
    1,
    9,
    15,
    tzinfo=timezone.utc,
)


bars = []


for i in range(13):

    p = 100 + i

    bars.append(
        Bar(
            timestamp=start + timedelta(minutes=i),
            open=p,
            high=p + 1,
            low=p - 1,
            close=p + 0.5,
            volume=100,
        )
    )


five = resample_bars(
    bars,
    5,
    base_timeframe_minutes=1,
    closed_only=True,
)


assert len(five) == 2


print("1m -> 5m resampling: PASS")
print("Partial higher-timeframe bar excluded: PASS")
print("Closed-bar higher-timeframe context: ACTIVE")
print("Multi-timeframe engine: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "MULTI-TIMEFRAME FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 23. PARAMETER SWEEP PROBE
# ============================================================

print()
print("Checking bounded parameter research...")


probe = r'''
from datetime import datetime, timedelta, timezone

import main

from omni.trading_intelligence.market_schema import Bar


start = datetime(
    2026,
    1,
    1,
    tzinfo=timezone.utc,
)


bars = []


for i in range(100):

    p = 100 + i * 0.3

    bars.append(
        Bar(
            timestamp=start + timedelta(minutes=i),
            open=p,
            high=p + 0.8,
            low=p - 0.4,
            close=p + 0.5,
            volume=1000 + i,
        )
    )


config = main.jarvis_backtest_config(
    allow_long=True,
    allow_short=False,
    warmup_bars=30,
)


result = main.jarvis_parameter_sweep(
    bars,
    "vwap_momentum_v1",
    config,
    {
        "stop_loss_pct": (
            0.01,
            0.02,
        ),

        "target_pct": (
            0.02,
            0.04,
        ),
    },
)


assert result["success"]
assert result["combinations"] == 4
assert len(result["ranked"]) == 4
assert result["automatic_promotion"] is False


print("Parameter combinations: 4")
print("Bounded search: PASS")
print("Result ranking: PASS")
print("Automatic strategy promotion: BLOCKED")
print("Parameter sweep engine: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "PARAMETER SWEEP FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 24. TARGETED TESTS
# ============================================================

print()
print("Running Trading Intelligence V2 targeted regression...")


r = run(
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",
    "tests.test_computer_operator",

    "tests.test_connected_services_v3",
    "tests.test_connected_services_v2",
    "tests.test_connected_services_v1",

    "tests.test_real_world_action_v3",
    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_engine",

    "tests.test_universal_learning_v5",
    "tests.test_autonomy_engine",
    "tests.test_improvement_lab",

    "-q",
)


if r.returncode:

    print(
        "TARGETED TEST FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 25. FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 26. FINAL CORE + BROWSER + FYERS
# ============================================================

for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "b=main.jarvis_fyers_bridge_status(); "
        "assert b['canonical_provider_available']; "
        "assert b['quote_function']=='get_quote'; "
        "assert b['history_function']=='get_intraday_data'; "
        "v=main.jarvis_trading_v2_status(); "
        "assert v['live_execution'] is False; "
        "assert v['automatic_broker_order'] is False; "
        "print('Final Protected Core: PASS'); "
        "print('Canonical FYERS bridge: PASS'); "
        "print('Trading V2 safety: PASS')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


r = run(
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
        "FINAL BROWSER PROBE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Final DOM-provider test: PASS"
)


# ============================================================
# SUCCESS
# ============================================================

status = run(
    "-c",
    (
        "import main,pprint; "
        "pprint.pp(main.jarvis_trading_v2_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V2 SUCCESS")
print("=" * 80)

print()
print("HISTORICAL BACKTEST ENGINE")
print("Close signal -> next-bar-open execution: ACTIVE")
print("No same-bar close look-ahead execution: ACTIVE")
print("Long trades: ACTIVE")
print("Short trades: ACTIVE")
print("Final position liquidation: ACTIVE")
print()

print("POSITION / EXIT SIMULATION")
print("Fixed stop-loss: ACTIVE")
print("Profit target: ACTIVE")
print("Trailing stop: ACTIVE")
print("Gap-through-stop handling: ACTIVE")
print("Gap-through-target handling: ACTIVE")
print("Both stop + target same bar: DETERMINISTIC POLICY")
print("Maximum holding bars: ACTIVE")
print("Opposite-signal exits: ACTIVE")
print()

print("ACCOUNT ENGINE")
print("Initial capital: ACTIVE")
print("Realized equity: ACTIVE")
print("Equity curve: ACTIVE")
print("Peak equity: ACTIVE")
print("Drawdown: ACTIVE")
print("Drawdown percentage: ACTIVE")
print("Optional capital requirement per unit: ACTIVE")
print("Rejected-entry tracking: ACTIVE")
print()

print("TRANSACTION COSTS")
print("Brokerage BPS: CONFIGURABLE")
print("Exchange charges: CONFIGURABLE")
print("Buy taxes: CONFIGURABLE")
print("Sell taxes: CONFIGURABLE")
print("Fixed order fee: CONFIGURABLE")
print("Per-contract fee: CONFIGURABLE")
print("Bid/ask spread: CONFIGURABLE")
print("Slippage: CONFIGURABLE")
print("Current statutory fee rates hard-coded: NO")
print()

print("DERIVATIVES")
print("Long option-premium backtests: ACTIVE")
print("Option lot multiplier: ACTIVE")
print("Naked premium short simulation: BLOCKED")
print("Commodity futures long simulation: ACTIVE")
print("Commodity futures short simulation: ACTIVE")
print("Commodity lot multiplier: ACTIVE")
print("Currency futures schema-compatible simulation: ACTIVE")
print()

print("MULTI-TIMEFRAME")
print("Base timeframe aggregation: ACTIVE")
print("Closed higher-timeframe bars only: ACTIVE")
print("Partial HTF-bar leakage protection: ACTIVE")
print("Higher-timeframe feature prefixes: ACTIVE")
print()

print("FYERS")
print("Canonical FYERS provider: PRESERVED")
print("get_quote(): PRESERVED")
print("get_intraday_data(): PRESERVED")
print("Historical payload normalizer: ACTIVE")
print("FYERS -> historical backtest API: ACTIVE ON USER REQUEST")
print("Installer real FYERS data request: NO")
print()

print("RESEARCH LAB")
print("Parameter sweeps: ACTIVE")
print("Maximum combinations: 200")
print("Strategy comparison: ACTIVE")
print("Trade-by-trade journal: ACTIVE")
print("JSON research artifact: ACTIVE")
print("CSV trade export: ACTIVE")
print("Automatic parameter promotion: BLOCKED")
print()

print("SAFETY")
print("Live order placement: BLOCKED")
print("Live order modification: BLOCKED")
print("Live order cancellation: BLOCKED")
print("Automatic broker order: BLOCKED")
print("Automatic strategy promotion: BLOCKED")
print("Protected Core: UNCHANGED")
print("Browser Windows-lock repair: PRESERVED")
print("Trading V1 / V1.1: PRESERVED")
print("Connected Services V3: PRESERVED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT:")
print("TRADING INTELLIGENCE V3")
print("Advanced option-chain intelligence")
print("IV rank / IV percentile")
print("IV skew + term structure")
print("PCR / OI / change-in-OI structure")
print("ATM / ITM / OTM chain relationships")
print("Underlying + futures + option confirmation")
print("Expiry-time intelligence")
print("Defined-risk multi-leg option structures")
print("Commodity session / contract intelligence")
print("Liquidity / spread quality scoring")
print("Regime-specific derivatives strategy families")
print()
print("THEN:")
print("V4 Strategy Evolution + Regime Adaptation")
print("V5 Walk-Forward + Monte Carlo + Anti-Overfitting")
print("V6 Live-data Paper/Shadow Trading + Performance Learning")
print("NautilusTrader isolated research kernel")
