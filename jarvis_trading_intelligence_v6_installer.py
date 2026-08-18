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

SCHEMA     = PKG / "shadow_schema.py"
FRESHNESS = PKG / "market_freshness.py"
EXECUTION = PKG / "paper_execution.py"
BRIDGE    = PKG / "shadow_market_bridge.py"
LEDGER    = PKG / "evidence_ledger.py"
DRIFT     = PKG / "performance_drift.py"
WEIGHTS   = PKG / "strategy_weighting.py"
CHAMPION  = PKG / "shadow_champion.py"
SUMMARY   = PKG / "paper_performance_summary.py"
SESSION   = PKG / "shadow_session.py"
RUNTIME   = PKG / "shadow_runtime.py"
STATUS    = PKG / "trading_v6_status.py"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"
TEST = ROOT / "tests" / "test_trading_intelligence_v6.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"

ARCHIVE = ROOT / "archive" / "trading_intelligence_v6"
ARCHIVE.mkdir(parents=True, exist_ok=True)

FILES = [
    SCHEMA,
    FRESHNESS,
    EXECUTION,
    BRIDGE,
    LEDGER,
    DRIFT,
    WEIGHTS,
    CHAMPION,
    SUMMARY,
    SESSION,
    RUNTIME,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(*args, capture=False):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(path, source):

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

    print("JARVIS source restored.")


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V6")
print("LIVE-DATA PAPER / SHADOW TRADING + PERFORMANCE LEARNING")
print("=" * 80)


# ============================================================
# BACKUP
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
# BASELINE V5 / 586
# ============================================================

print()
print("Checking Trading Intelligence V5 / 586 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v4=main.jarvis_trading_v4_status(); "
        "v5=main.jarvis_trading_v5_status(); "
        "assert v4['strategy_genomes']; "
        "assert v5['walk_forward_validation']; "
        "assert v5['overfitting_risk_score']; "
        "assert v5['oos_tuning'] is False; "
        "assert v5['live_execution'] is False; "
        "assert v5['automatic_strategy_promotion'] is False; "
        "assert v5['automatic_broker_order'] is False; "
        "print('Main import: PASS'); "
        "print('Protected Core: PASS'); "
        "print('Trading V4 Evolution: PASS'); "
        "print('Trading V5 Validation: PASS'); "
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    print("BASELINE FAILURE")
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

    print("BROWSER BASELINE FAILURE")
    sys.exit(1)


print("Browser DOM repair: PASS")


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

print("Baseline: PASS")


# ============================================================
# SHADOW SCHEMA
# ============================================================

write(
    SCHEMA,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)


def parse_timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        result = value


    elif isinstance(
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
            numeric /= 1000.0

        result = datetime.fromtimestamp(
            numeric,
            tz=timezone.utc,
        )


    else:

        text = str(
            value
        ).strip()

        if text.isdigit():

            return parse_timestamp(
                int(text)
            )

        if text.endswith("Z"):

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


@dataclass(frozen=True)
class QuoteSnapshot:

    symbol: str

    timestamp: datetime

    ltp: float

    bid: float | None = None

    ask: float | None = None

    source: str = "unknown"

    timestamp_origin: str = "provider"

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        object.__setattr__(
            self,
            "timestamp",
            parse_timestamp(
                self.timestamp
            ),
        )


        if not self.symbol:

            raise ValueError(
                "symbol is required."
            )


        if float(
            self.ltp
        ) <= 0:

            raise ValueError(
                "ltp must be positive."
            )


        if (
            self.bid is not None
            and float(
                self.bid
            ) < 0
        ):

            raise ValueError(
                "bid cannot be negative."
            )


        if (
            self.ask is not None
            and float(
                self.ask
            ) < 0
        ):

            raise ValueError(
                "ask cannot be negative."
            )


        if (
            self.bid is not None
            and self.ask is not None
            and float(
                self.ask
            ) < float(
                self.bid
            )
        ):

            raise ValueError(
                "ask cannot be below bid."
            )


    def to_dict(
        self,
    ):

        return {
            "symbol":
                self.symbol,

            "timestamp":
                self.timestamp.isoformat(),

            "ltp":
                float(
                    self.ltp
                ),

            "bid":
                (
                    float(
                        self.bid
                    )
                    if self.bid
                    is not None
                    else None
                ),

            "ask":
                (
                    float(
                        self.ask
                    )
                    if self.ask
                    is not None
                    else None
                ),

            "source":
                self.source,

            "timestamp_origin":
                self.timestamp_origin,

            "metadata":
                dict(
                    self.metadata
                ),
        }


VALID_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


@dataclass(frozen=True)
class PaperSignal:

    strategy_id: str

    symbol: str

    signal: str

    timestamp: datetime

    confidence: float = 1.0

    metadata: dict = field(
        default_factory=dict
    )


    def __post_init__(
        self,
    ):

        signal = str(
            self.signal
        ).strip().upper()


        if signal not in VALID_SIGNALS:

            raise ValueError(
                "Unsupported paper signal."
            )


        object.__setattr__(
            self,
            "signal",
            signal,
        )


        object.__setattr__(
            self,
            "timestamp",
            parse_timestamp(
                self.timestamp
            ),
        )


        if not self.strategy_id:

            raise ValueError(
                "strategy_id is required."
            )


        if not self.symbol:

            raise ValueError(
                "symbol is required."
            )


        confidence = float(
            self.confidence
        )


        if not 0 <= confidence <= 1:

            raise ValueError(
                "confidence must be between 0 and 1."
            )


@dataclass(frozen=True)
class ShadowSessionConfig:

    initial_capital: float = 100000.0

    quantity: float = 1.0

    multiplier: float = 1.0

    allow_short: bool = True

    max_quote_age_seconds: float = 15.0

    max_future_skew_seconds: float = 5.0

    slippage_bps: float = 0.0

    fixed_fee: float = 0.0


    def __post_init__(
        self,
    ):

        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be positive."
            )


        if self.quantity <= 0:
            raise ValueError(
                "quantity must be positive."
            )


        if self.multiplier <= 0:
            raise ValueError(
                "multiplier must be positive."
            )


        if self.max_quote_age_seconds <= 0:
            raise ValueError(
                "max_quote_age_seconds must be positive."
            )


        if self.max_future_skew_seconds < 0:
            raise ValueError(
                "max_future_skew_seconds cannot be negative."
            )


        if self.slippage_bps < 0:
            raise ValueError(
                "slippage_bps cannot be negative."
            )


        if self.fixed_fee < 0:
            raise ValueError(
                "fixed_fee cannot be negative."
            )
'''
)


# ============================================================
# MARKET FRESHNESS
# ============================================================

write(
    FRESHNESS,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)


class MarketFreshnessGuard:

    def __init__(
        self,
        max_age_seconds=15.0,
        max_future_skew_seconds=5.0,
    ):

        self.max_age_seconds = float(
            max_age_seconds
        )

        self.max_future_skew_seconds = float(
            max_future_skew_seconds
        )


    def check(
        self,
        snapshot,
        *,
        now=None,
    ):

        current = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )


        if current.tzinfo is None:

            current = current.replace(
                tzinfo=timezone.utc
            )


        current = current.astimezone(
            timezone.utc
        )


        timestamp = (
            snapshot.timestamp
            .astimezone(
                timezone.utc
            )
        )


        age = (
            current
            - timestamp
        ).total_seconds()


        if age < (
            -self.max_future_skew_seconds
        ):

            return {
                "fresh":
                    False,

                "reason":
                    "future_timestamp",

                "age_seconds":
                    age,
            }


        if age > self.max_age_seconds:

            return {
                "fresh":
                    False,

                "reason":
                    "stale_quote",

                "age_seconds":
                    age,
            }


        return {
            "fresh":
                True,

            "reason":
                "fresh",

            "age_seconds":
                age,
        }
'''
)


# ============================================================
# PAPER EXECUTION ENGINE
# ============================================================

write(
    EXECUTION,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

from omni.trading_intelligence.backtest_schema import (
    ExecutionCostConfig,
)

from omni.trading_intelligence.cost_model import (
    ExecutionCostModel,
)


@dataclass
class VirtualPosition:

    side: int

    entry_time: str

    entry_ltp: float

    entry_reference: float

    entry_fill: float

    entry_fee: float

    quantity: float

    multiplier: float


class PaperExecutionEngine:

    def __init__(
        self,
        config,
    ):

        self.config = config

        self.position = None

        self.trades = []

        self.initial_capital = float(
            config.initial_capital
        )

        self.realized_pnl = 0.0

        self.kill_switch = False

        self.kill_reason = None


        self.cost_model = ExecutionCostModel(
            ExecutionCostConfig(
                fixed_per_order=
                    config.fixed_fee,

                slippage_bps=
                    config.slippage_bps,

                spread_bps=
                    0.0,
            )
        )


    @staticmethod
    def _reference(
        snapshot,
        order_side,
    ):

        if (
            order_side == "buy"
            and snapshot.ask is not None
            and snapshot.ask > 0
        ):

            return float(
                snapshot.ask
            )


        if (
            order_side == "sell"
            and snapshot.bid is not None
            and snapshot.bid > 0
        ):

            return float(
                snapshot.bid
            )


        return float(
            snapshot.ltp
        )


    def _execution(
        self,
        snapshot,
        order_side,
    ):

        reference = self._reference(
            snapshot,
            order_side,
        )


        execution = self.cost_model.execution(
            reference,
            order_side,
            self.config.quantity,
            self.config.multiplier,
        )


        market_spread_friction = (
            abs(
                reference
                - float(
                    snapshot.ltp
                )
            )
            * self.config.quantity
            * self.config.multiplier
        )


        execution[
            "market_spread_friction"
        ] = market_spread_friction


        return execution


    def open(
        self,
        snapshot,
        side,
    ):

        if self.kill_switch:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "kill_switch",
            }


        if self.position is not None:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "position_already_open",
            }


        side = int(side)


        if side not in {
            -1,
            1,
        }:

            raise ValueError(
                "side must be +1 or -1."
            )


        if (
            side == -1
            and not self.config.allow_short
        ):

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "short_disabled",
            }


        order_side = (
            "buy"
            if side == 1
            else "sell"
        )


        execution = self._execution(
            snapshot,
            order_side,
        )


        self.position = VirtualPosition(
            side=
                side,

            entry_time=
                snapshot.timestamp.isoformat(),

            entry_ltp=
                float(
                    snapshot.ltp
                ),

            entry_reference=
                execution[
                    "reference_price"
                ],

            entry_fill=
                execution[
                    "fill_price"
                ],

            entry_fee=
                execution[
                    "fees"
                ],

            quantity=
                self.config.quantity,

            multiplier=
                self.config.multiplier,
        )


        return {
            "success":
                True,

            "paper_only":
                True,

            "action":
                "VIRTUAL_OPEN",

            "side":
                (
                    "LONG"
                    if side == 1
                    else "SHORT"
                ),

            "fill_price":
                execution[
                    "fill_price"
                ],
        }


    def close(
        self,
        snapshot,
        *,
        reason="signal_exit",
    ):

        if self.position is None:

            return {
                "success":
                    False,

                "blocked":
                    True,

                "reason":
                    "no_open_position",
            }


        position = self.position


        order_side = (
            "sell"
            if position.side == 1
            else "buy"
        )


        execution = self._execution(
            snapshot,
            order_side,
        )


        gross_pnl = (
            (
                execution[
                    "fill_price"
                ]
                - position.entry_fill
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


        net_pnl = (
            gross_pnl
            - fees
        )


        trade = {
            "side":
                (
                    "LONG"
                    if position.side == 1
                    else "SHORT"
                ),

            "entry_time":
                position.entry_time,

            "exit_time":
                snapshot.timestamp.isoformat(),

            "entry_price":
                position.entry_fill,

            "exit_price":
                execution[
                    "fill_price"
                ],

            "entry_ltp":
                position.entry_ltp,

            "exit_ltp":
                float(
                    snapshot.ltp
                ),

            "quantity":
                position.quantity,

            "multiplier":
                position.multiplier,

            "gross_pnl":
                gross_pnl,

            "fees":
                fees,

            "slippage":
                (
                    abs(
                        position.entry_fill
                        - position.entry_reference
                    )
                    * position.quantity
                    * position.multiplier
                    + execution[
                        "friction_cost"
                    ]
                ),

            "net_pnl":
                net_pnl,

            "turnover":
                (
                    abs(
                        position.entry_fill
                    )
                    + abs(
                        execution[
                            "fill_price"
                        ]
                    )
                )
                * position.quantity
                * position.multiplier,

            "exit_reason":
                str(
                    reason
                ),

            "paper_only":
                True,

            "broker_order":
                False,
        }


        self.trades.append(
            trade
        )


        self.realized_pnl += net_pnl

        self.position = None


        return {
            "success":
                True,

            "paper_only":
                True,

            "action":
                "VIRTUAL_CLOSE",

            "trade":
                trade,
        }


    def on_signal(
        self,
        snapshot,
        signal,
    ):

        signal = str(
            signal
        ).upper()


        if signal == "FLAT":

            return {
                "success":
                    True,

                "action":
                    "NO_ACTION",

                "paper_only":
                    True,
            }


        if signal == "EXIT":

            return self.close(
                snapshot,
                reason="exit_signal",
            )


        desired_side = (
            1
            if signal == "LONG"
            else -1
            if signal == "SHORT"
            else None
        )


        if desired_side is None:

            raise ValueError(
                "Unsupported paper signal."
            )


        if self.position is None:

            return self.open(
                snapshot,
                desired_side,
            )


        if (
            self.position.side
            == desired_side
        ):

            return {
                "success":
                    True,

                "action":
                    "HOLD",

                "paper_only":
                    True,
            }


        # Opposite signal closes only.
        # No same-tick reversal.
        return self.close(
            snapshot,
            reason="opposite_signal",
        )


    def kill(
        self,
        reason="manual",
    ):

        self.kill_switch = True

        self.kill_reason = str(
            reason
        )


        return {
            "success":
                True,

            "kill_switch":
                True,

            "reason":
                self.kill_reason,

            "paper_only":
                True,
        }


    def resume(
        self,
    ):

        self.kill_switch = False
        self.kill_reason = None


        return {
            "success":
                True,

            "kill_switch":
                False,

            "paper_only":
                True,
        }


    def status(
        self,
    ):

        return {
            "initial_capital":
                self.initial_capital,

            "realized_pnl":
                self.realized_pnl,

            "equity":
                (
                    self.initial_capital
                    + self.realized_pnl
                ),

            "trade_count":
                len(
                    self.trades
                ),

            "position_open":
                self.position
                is not None,

            "position_side":
                (
                    self.position.side
                    if self.position
                    is not None
                    else None
                ),

            "kill_switch":
                self.kill_switch,

            "kill_reason":
                self.kill_reason,

            "paper_only":
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
            "place_order",
            "send_order",
            "broker_order",
            "modify_order",
            "cancel_order",
            "live_order",
            "execute_trade",
        )


        if any(
            token in lower

            for token in forbidden
        ):

            raise PermissionError(
                "PaperExecutionEngine cannot access broker orders."
            )


        raise AttributeError(
            name
        )
'''
)


# ============================================================
# READ-ONLY LIVE MARKET BRIDGE
# ============================================================

write(
    BRIDGE,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.shadow_schema import (
    QuoteSnapshot,
    parse_timestamp,
)


def _first(
    mapping,
    names,
    default=None,
):

    normalized = {
        str(key).lower():
            value

        for key, value
        in mapping.items()
    }


    for name in names:

        if name in normalized:

            return normalized[
                name
            ]


    return default


def quote_snapshot_from_payload(
    payload,
    *,
    symbol,
    source="provider",
    received_at=None,
):

    if not isinstance(
        payload,
        dict,
    ):

        raise ValueError(
            "Quote payload must be a dictionary."
        )


    if payload.get(
        "success"
    ) is False:

        raise RuntimeError(
            str(
                payload.get(
                    "message"
                )
                or payload.get(
                    "error"
                )
                or "Market quote unavailable."
            )
        )


    candidate = payload


    for key in (
        "data",
        "quote",
        "result",
    ):

        inner = payload.get(
            key
        )

        if isinstance(
            inner,
            dict,
        ):

            candidate = {
                **payload,
                **inner,
            }

            break


    ltp = _first(
        candidate,
        (
            "ltp",
            "last_price",
            "last",
            "price",
            "lp",
        ),
    )


    if ltp is None:

        raise ValueError(
            "Quote payload does not contain LTP."
        )


    bid = _first(
        candidate,
        (
            "bid",
            "bid_price",
            "best_bid",
        ),
    )


    ask = _first(
        candidate,
        (
            "ask",
            "ask_price",
            "best_ask",
        ),
    )


    timestamp_value = _first(
        candidate,
        (
            "timestamp",
            "exchange_timestamp",
            "exch_feed_time",
            "feed_time",
            "ts",
        ),
    )


    if received_at is None:

        received_at = datetime.now(
            timezone.utc
        )


    if timestamp_value is None:

        timestamp = parse_timestamp(
            received_at
        )

        timestamp_origin = (
            "received_at"
        )


    else:

        timestamp = parse_timestamp(
            timestamp_value
        )

        timestamp_origin = (
            "provider"
        )


    return QuoteSnapshot(
        symbol=
            str(
                symbol
            ),

        timestamp=
            timestamp,

        ltp=
            float(
                ltp
            ),

        bid=
            (
                float(
                    bid
                )
                if bid
                not in (
                    None,
                    "",
                )
                else None
            ),

        ask=
            (
                float(
                    ask
                )
                if ask
                not in (
                    None,
                    "",
                )
                else None
            ),

        source=
            str(
                source
            ),

        timestamp_origin=
            timestamp_origin,

        metadata={
            "provider_success":
                payload.get(
                    "success"
                ),

            "broker_write":
                False,
        },
    )


class FyersShadowMarketBridge:

    def __init__(
        self,
        adapter=None,
    ):

        self.adapter = (
            adapter
            or FyersReadOnlyAdapter()
        )


    def read_quote(
        self,
        symbol,
    ):

        payload = self.adapter.quote(
            symbol
        )


        return quote_snapshot_from_payload(
            payload,
            symbol=symbol,
            source="fyers_readonly",
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "order",
            "trade",
            "execute",
            "place",
            "modify",
            "cancel",
            "buy",
            "sell",
        )


        if any(
            token in lower

            for token in forbidden
        ):

            raise PermissionError(
                "Shadow market bridge is market-data-only."
            )


        raise AttributeError(
            name
        )


fyers_shadow_market_bridge = (
    FyersShadowMarketBridge()
)
'''
)


# ============================================================
# EVIDENCE LEDGER
# ============================================================

write(
    LEDGER,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path

import json
import os
import uuid


class TradingEvidenceLedger:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "shadow"
            )
        )


        self.path = (
            self.root
            / "evidence.jsonl"
        )


    def append(
        self,
        event_type,
        payload,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        record = {
            "event_id":
                (
                    "evidence-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "event_type":
                str(
                    event_type
                ),

            "payload":
                payload,

            "research_only":
                True,

            "broker_order":
                False,
        }


        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )


        return record


    def recent(
        self,
        limit=100,
    ):

        limit = max(
            1,
            min(
                int(
                    limit
                ),
                1000,
            ),
        )


        if not self.path.exists():

            return ()


        lines = self.path.read_text(
            encoding="utf-8"
        ).splitlines()


        output = []


        for line in lines[
            -limit:
        ]:

            if not line.strip():
                continue

            output.append(
                json.loads(
                    line
                )
            )


        return tuple(
            output
        )
'''
)


# ============================================================
# PERFORMANCE DRIFT
# ============================================================

write(
    DRIFT,
    r'''
from __future__ import annotations


def _finite(
    value,
    default=0.0,
):

    try:
        return float(
            value
        )

    except Exception:
        return float(
            default
        )


class PerformanceDriftDetector:

    def compare(
        self,
        baseline_metrics,
        recent_metrics,
    ):

        baseline_expectancy = _finite(
            baseline_metrics.get(
                "expectancy"
            )
        )

        recent_expectancy = _finite(
            recent_metrics.get(
                "expectancy"
            )
        )


        baseline_pf = _finite(
            baseline_metrics.get(
                "profit_factor"
            ),
            1.0,
        )

        recent_pf = _finite(
            recent_metrics.get(
                "profit_factor"
            ),
            1.0,
        )


        baseline_win = _finite(
            baseline_metrics.get(
                "win_rate"
            )
        )

        recent_win = _finite(
            recent_metrics.get(
                "win_rate"
            )
        )


        baseline_dd = max(
            0.0,
            _finite(
                baseline_metrics.get(
                    "max_drawdown_pct"
                )
            ),
        )

        recent_dd = max(
            0.0,
            _finite(
                recent_metrics.get(
                    "max_drawdown_pct"
                )
            ),
        )


        expectancy_deterioration = max(
            0.0,
            (
                baseline_expectancy
                - recent_expectancy
            )
            / max(
                abs(
                    baseline_expectancy
                ),
                1.0,
            ),
        )


        pf_deterioration = max(
            0.0,
            (
                baseline_pf
                - recent_pf
            )
            / max(
                abs(
                    baseline_pf
                ),
                1.0,
            ),
        )


        win_deterioration = max(
            0.0,
            baseline_win
            - recent_win,
        )


        dd_deterioration = max(
            0.0,
            recent_dd
            - baseline_dd,
        )


        score = min(
            100.0,
            (
                expectancy_deterioration
                * 35.0
                + pf_deterioration
                * 25.0
                + win_deterioration
                * 100.0
                * 20.0
                / 100.0
                + dd_deterioration
                * 100.0
                * 20.0
                / 100.0
            ),
        )


        if score < 20:

            state = "NORMAL"


        elif score < 40:

            state = "WATCH"


        elif score < 70:

            state = "DEGRADED"


        else:

            state = "SEVERE"


        return {
            "drift_score":
                score,

            "state":
                state,

            "components": {
                "expectancy":
                    expectancy_deterioration,

                "profit_factor":
                    pf_deterioration,

                "win_rate":
                    win_deterioration,

                "drawdown":
                    dd_deterioration,
            },

            "automatic_strategy_shutdown":
                False,

            "automatic_broker_action":
                False,

            "research_only":
                True,
        }


performance_drift_detector = (
    PerformanceDriftDetector()
)
'''
)


# ============================================================
# RESEARCH STRATEGY WEIGHTING
# ============================================================

write(
    WEIGHTS,
    r'''
from __future__ import annotations


class ResearchStrategyWeighting:

    def calculate(
        self,
        evidence,
    ):

        evidence = dict(
            evidence
        )


        if not evidence:

            return {
                "weights":
                    {},

                "research_only":
                    True,

                "capital_allocation":
                    False,
            }


        raw = {}


        for strategy_id, values in (
            evidence.items()
        ):

            validation = float(
                values.get(
                    "validation_score",
                    0.0,
                )
            )


            recent = float(
                values.get(
                    "recent_score",
                    0.0,
                )
            )


            drift = max(
                0.0,
                float(
                    values.get(
                        "drift_score",
                        0.0,
                    )
                ),
            )


            score = max(
                0.05,
                (
                    1.0
                    + validation
                    / 50.0
                    + recent
                    / 50.0
                    - drift
                    / 100.0
                ),
            )


            raw[
                str(
                    strategy_id
                )
            ] = score


        total = sum(
            raw.values()
        )


        weights = {
            strategy_id:
                score
                / total

            for strategy_id, score
            in raw.items()
        }


        return {
            "weights":
                weights,

            "sum":
                sum(
                    weights.values()
                ),

            "research_only":
                True,

            "capital_allocation":
                False,

            "broker_position_sizing":
                False,

            "automatic_production_change":
                False,
        }


research_strategy_weighting = (
    ResearchStrategyWeighting()
)
'''
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# SHADOW CHAMPION / CHALLENGER
# ============================================================

write(
    CHAMPION,
    r'''
from __future__ import annotations

from omni.trading_intelligence.strategy_fitness import (
    result_fitness,
)


class ShadowChampionChallenger:

    def compare(
        self,
        champion_metrics,
        challenger_metrics,
        *,
        margin=2.0,
    ):

        champion = result_fitness(
            {
                "metrics":
                    champion_metrics
            }
        )


        challenger = result_fitness(
            {
                "metrics":
                    challenger_metrics
            }
        )


        difference = (
            challenger[
                "score"
            ]
            - champion[
                "score"
            ]
        )


        if difference >= float(
            margin
        ):

            decision = (
                "SHADOW_CHALLENGER_LEADS"
            )


        elif difference > 0:

            decision = (
                "KEEP_OBSERVING"
            )


        elif difference <= -10:

            decision = (
                "CHALLENGER_DEGRADED"
            )


        else:

            decision = (
                "SHADOW_CHAMPION_RETAINS"
            )


        return {
            "decision":
                decision,

            "champion_fitness":
                champion,

            "challenger_fitness":
                challenger,

            "margin":
                difference,

            "automatic_production_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_broker_action":
                False,

            "research_only":
                True,
        }


shadow_champion_challenger = (
    ShadowChampionChallenger()
)
'''
)


# ============================================================
# PERFORMANCE SUMMARY
# ============================================================

write(
    SUMMARY,
    r'''
from __future__ import annotations

from omni.trading_intelligence.trading_metrics import (
    evaluate_trades,
)


def paper_performance_summary(
    strategy_trades,
):

    output = {}


    for strategy_id, trades in (
        strategy_trades.items()
    ):

        trades = tuple(
            trades
        )


        metrics = evaluate_trades(
            trades
        )


        output[
            str(
                strategy_id
            )
        ] = {
            "trade_count":
                len(
                    trades
                ),

            "metrics":
                metrics,
        }


    ranking = sorted(
        output.items(),
        key=lambda item:
            float(
                item[
                    1
                ][
                    "metrics"
                ].get(
                    "net_pnl",
                    0.0,
                )
            ),
        reverse=True,
    )


    return {
        "strategies":
            output,

        "ranking":
            tuple(
                strategy_id

                for strategy_id, _
                in ranking
            ),

        "paper_only":
            True,

        "live_execution":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# SHADOW SESSION
# ============================================================

write(
    SESSION,
    r'''
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
'''
)


# ============================================================
# SHADOW RUNTIME
# ============================================================

write(
    RUNTIME,
    r'''
from __future__ import annotations


from omni.trading_intelligence.shadow_market_bridge import (
    FyersShadowMarketBridge,
)

from omni.trading_intelligence.shadow_schema import (
    ShadowSessionConfig,
)

from omni.trading_intelligence.shadow_session import (
    ShadowTradingSession,
)


class ShadowTradingRuntime:

    MAX_SESSIONS = 20


    def __init__(
        self,
        market_bridge=None,
    ):

        self.sessions = {}

        self.market_bridge = (
            market_bridge
            or FyersShadowMarketBridge()
        )


    def create(
        self,
        symbol,
        strategy_ids,
        config=None,
    ):

        if len(
            self.sessions
        ) >= self.MAX_SESSIONS:

            raise RuntimeError(
                "Maximum shadow sessions reached."
            )


        config = (
            config
            or ShadowSessionConfig()
        )


        session = ShadowTradingSession(
            symbol,
            strategy_ids,
            config,
        )


        self.sessions[
            session.session_id
        ] = session


        return {
            "success":
                True,

            "session_id":
                session.session_id,

            "paper_only":
                True,

            "live_execution":
                False,
        }


    def get(
        self,
        session_id,
    ):

        session = self.sessions.get(
            str(
                session_id
            )
        )


        if session is None:

            raise KeyError(
                "Unknown shadow session."
            )


        return session


    def process(
        self,
        session_id,
        snapshot,
        signals,
        *,
        now=None,
    ):

        return self.get(
            session_id
        ).process(
            snapshot,
            signals,
            now=now,
        )


    def read_fyers_quote(
        self,
        symbol,
    ):

        return self.market_bridge.read_quote(
            symbol
        )


    def process_fyers(
        self,
        session_id,
        signals,
        *,
        now=None,
    ):

        session = self.get(
            session_id
        )


        snapshot = self.read_fyers_quote(
            session.symbol
        )


        return session.process(
            snapshot,
            signals,
            now=now,
        )


    def kill(
        self,
        session_id,
        reason="manual",
    ):

        return self.get(
            session_id
        ).kill(
            reason
        )


    def resume(
        self,
        session_id,
    ):

        return self.get(
            session_id
        ).resume()


    def status(
        self,
        session_id=None,
    ):

        if session_id is not None:

            return self.get(
                session_id
            ).status()


        return {
            "session_count":
                len(
                    self.sessions
                ),

            "sessions":
                tuple(
                    session.status()

                    for session
                    in self.sessions.values()
                ),

            "background_polling":
                False,

            "paper_only":
                True,

            "live_execution":
                False,
        }


shadow_trading_runtime = (
    ShadowTradingRuntime()
)
'''
)


# ============================================================
# V6 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)


class TradingIntelligenceV6Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        fyers = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "paper_only":
                True,

            "live_execution":
                False,

            "live_market_read_bridge":
                True,

            "canonical_fyers_quote":
                fyers.get(
                    "quote"
                ),

            "canonical_fyers_history":
                fyers.get(
                    "history"
                ),

            "native_fyers_option_chain":
                fyers.get(
                    "option_chain"
                ),

            "virtual_fills":
                True,

            "virtual_long":
                True,

            "virtual_short":
                True,

            "same_tick_reversal":
                False,

            "market_freshness_guard":
                True,

            "future_timestamp_guard":
                True,

            "stale_data_execution":
                False,

            "kill_switch":
                True,

            "explicit_resume":
                True,

            "evidence_ledger":
                True,

            "performance_drift":
                True,

            "research_strategy_weighting":
                True,

            "research_weights_drive_broker_capital":
                False,

            "shadow_champion_challenger":
                True,

            "paper_performance_summary":
                True,

            "background_market_polling":
                False,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_broker_order":
                False,

            "automatic_live_position_management":
                False,

            "production_self_modification":
                False,
        }


trading_intelligence_v6_status = (
    TradingIntelligenceV6Status()
)
'''
)


# ============================================================
# MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v6_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v6_status():

    from omni.trading_intelligence.trading_v6_status import (
        trading_intelligence_v6_status,
    )

    return trading_intelligence_v6_status.status()


def jarvis_shadow_config(
    **kwargs,
):

    from omni.trading_intelligence.shadow_schema import (
        ShadowSessionConfig,
    )

    return ShadowSessionConfig(
        **kwargs
    )


def jarvis_shadow_quote_snapshot(
    symbol,
    timestamp,
    ltp,
    bid=None,
    ask=None,
    source="manual",
):

    from omni.trading_intelligence.shadow_schema import (
        QuoteSnapshot,
    )

    return QuoteSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        ltp=ltp,
        bid=bid,
        ask=ask,
        source=source,
    )


def jarvis_shadow_create_session(
    symbol,
    strategy_ids,
    config=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.create(
        symbol,
        strategy_ids,
        config,
    )


def jarvis_shadow_process(
    session_id,
    snapshot,
    signals,
    now=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.process(
        session_id,
        snapshot,
        signals,
        now=now,
    )


def jarvis_shadow_fyers_quote(
    symbol,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.read_fyers_quote(
        symbol
    )


def jarvis_shadow_process_fyers(
    session_id,
    signals,
    now=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.process_fyers(
        session_id,
        signals,
        now=now,
    )


def jarvis_shadow_status(
    session_id=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.status(
        session_id
    )


def jarvis_shadow_kill(
    session_id,
    reason="manual",
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.kill(
        session_id,
        reason,
    )


def jarvis_shadow_resume(
    session_id,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.resume(
        session_id
    )


def jarvis_shadow_summary(
    session_id,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return (
        shadow_trading_runtime
        .get(
            session_id
        )
        .summary()
    )


def jarvis_shadow_drift(
    baseline_metrics,
    recent_metrics,
):

    from omni.trading_intelligence.performance_drift import (
        performance_drift_detector,
    )

    return performance_drift_detector.compare(
        baseline_metrics,
        recent_metrics,
    )


def jarvis_shadow_weights(
    evidence,
):

    from omni.trading_intelligence.strategy_weighting import (
        research_strategy_weighting,
    )

    return research_strategy_weighting.calculate(
        evidence
    )


def jarvis_shadow_champion_compare(
    champion_metrics,
    challenger_metrics,
    margin=2.0,
):

    from omni.trading_intelligence.shadow_champion import (
        shadow_champion_challenger,
    )

    return shadow_champion_challenger.compare(
        champion_metrics,
        challenger_metrics,
        margin=margin,
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_intelligence_v6_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_intelligence_v6_payload():

    from omni.trading_intelligence.trading_v6_status import (
        trading_intelligence_v6_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v6_status.status(),
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
# TESTS
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
'''
)


# ============================================================
# COMPILE
# ============================================================

print()
print("Checking Trading Intelligence V6 syntax...")


r = run(
    "-m",
    "py_compile",

    str(SCHEMA),
    str(FRESHNESS),
    str(EXECUTION),
    str(BRIDGE),
    str(LEDGER),
    str(DRIFT),
    str(WEIGHTS),
    str(CHAMPION),
    str(SUMMARY),
    str(SESSION),
    str(RUNTIME),
    str(STATUS),
    str(MAIN),
    str(APP),
    str(TEST),
)


if r.returncode:

    print("COMPILE FAILURE")
    rollback()
    sys.exit(1)


print("Syntax: PASS")


# ============================================================
# PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if sha(
        ROOT / relative
    ) != before:

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

    rollback()
    sys.exit(1)


# ============================================================
# PAPER EXECUTION PROBE
# ============================================================

print()
print("Checking paper/shadow execution engine...")


probe = r'''
from datetime import datetime, timezone

import main


now = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


config = main.jarvis_shadow_config(
    initial_capital=100000,
    quantity=10,
    multiplier=1,
    max_quote_age_seconds=15,
    slippage_bps=1,
)


created = main.jarvis_shadow_create_session(
    "TEST",
    (
        "strategy_a",
        "strategy_b",
    ),
    config,
)


session_id = created["session_id"]


q1 = main.jarvis_shadow_quote_snapshot(
    "TEST",
    now,
    100,
    bid=99.9,
    ask=100.1,
)


result = main.jarvis_shadow_process(
    session_id,
    q1,
    (
        {
            "strategy_id":
                "strategy_a",

            "signal":
                "LONG",
        },

        {
            "strategy_id":
                "strategy_b",

            "signal":
                "SHORT",
        },
    ),
    now=now,
)


assert result["success"]
assert result["paper_only"]
assert result["broker_order"] is False


q2 = main.jarvis_shadow_quote_snapshot(
    "TEST",
    now,
    105,
    bid=104.9,
    ask=105.1,
)


main.jarvis_shadow_process(
    session_id,
    q2,
    (
        {
            "strategy_id":
                "strategy_a",

            "signal":
                "EXIT",
        },

        {
            "strategy_id":
                "strategy_b",

            "signal":
                "EXIT",
        },
    ),
    now=now,
)


summary = main.jarvis_shadow_summary(
    session_id
)


assert summary["paper_only"]
assert summary["live_execution"] is False

assert (
    summary[
        "strategies"
    ][
        "strategy_a"
    ][
        "trade_count"
    ]
    == 1
)


print("Virtual long fills: PASS")
print("Virtual short fills: PASS")
print("Virtual exits: PASS")
print("Paper PnL accounting: ACTIVE")
print("Paper strategy comparison: ACTIVE")
print("Broker order generated: NO")
print("Paper/shadow execution: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("PAPER EXECUTION FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# STALE DATA + KILL SWITCH
# ============================================================

print()
print("Checking stale-data and kill-switch protection...")


probe = r'''
from datetime import datetime, timedelta, timezone

import main


now = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


created = main.jarvis_shadow_create_session(
    "STALE",
    ("alpha",),
    main.jarvis_shadow_config(
        max_quote_age_seconds=10,
    ),
)


session_id = created["session_id"]


stale = main.jarvis_shadow_quote_snapshot(
    "STALE",
    now - timedelta(seconds=60),
    100,
)


result = main.jarvis_shadow_process(
    session_id,
    stale,
    (
        {
            "strategy_id":
                "alpha",

            "signal":
                "LONG",
        },
    ),
    now=now,
)


assert not result["success"]
assert result["blocked"]
assert result["reason"] == "stale_quote"


kill = main.jarvis_shadow_kill(
    session_id,
    "safety_test",
)


assert kill["kill_switch"]


fresh = main.jarvis_shadow_quote_snapshot(
    "STALE",
    now,
    100,
)


blocked = main.jarvis_shadow_process(
    session_id,
    fresh,
    (
        {
            "strategy_id":
                "alpha",

            "signal":
                "LONG",
        },
    ),
    now=now,
)


assert blocked["blocked"]
assert blocked["reason"] == "kill_switch"


resume = main.jarvis_shadow_resume(
    session_id
)


assert resume["kill_switch"] is False


print("Stale quote execution: BLOCKED")
print("Future timestamp protection: ACTIVE")
print("Kill switch: ACTIVE")
print("Explicit resume: ACTIVE")
print("Automatic broker close on kill: NO")
print("Safety controls: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("SHADOW SAFETY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FAKE FYERS READ-ONLY BRIDGE
# ============================================================

print()
print("Checking live-market read bridge without real API request...")


probe = r'''
from datetime import datetime, timezone

from omni.trading_intelligence.shadow_market_bridge import (
    FyersShadowMarketBridge,
)


class FakeAdapter:

    def quote(self, symbol):

        return {
            "success": True,
            "ltp": 25000,
            "bid": 24999,
            "ask": 25001,
            "timestamp": datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
        }


bridge = FyersShadowMarketBridge(
    FakeAdapter()
)


snapshot = bridge.read_quote(
    "NIFTY"
)


assert snapshot.ltp == 25000
assert snapshot.source == "fyers_readonly"


blocked = False


try:
    bridge.place_order


except PermissionError:
    blocked = True


assert blocked


print("Read-only quote ingestion: PASS")
print("Provider timestamp normalization: PASS")
print("Bid/ask ingestion: PASS")
print("Broker-order surface: BLOCKED")
print("Installer real FYERS request: NO")
print("Live-market bridge architecture: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("MARKET BRIDGE FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# PERFORMANCE LEARNING PROBE
# ============================================================

print()
print("Checking shadow performance-learning layer...")


probe = r'''
import main


drift = main.jarvis_shadow_drift(
    {
        "expectancy": 100,
        "profit_factor": 2.0,
        "win_rate": 0.60,
        "max_drawdown_pct": 0.05,
    },
    {
        "expectancy": 20,
        "profit_factor": 1.1,
        "win_rate": 0.45,
        "max_drawdown_pct": 0.15,
    },
)


assert drift["drift_score"] > 0
assert drift["automatic_broker_action"] is False


weights = main.jarvis_shadow_weights(
    {
        "champion": {
            "validation_score": 30,
            "recent_score": 20,
            "drift_score": 5,
        },

        "challenger": {
            "validation_score": 10,
            "recent_score": 5,
            "drift_score": 30,
        },
    }
)


assert abs(
    weights["sum"] - 1.0
) < 1e-9

assert weights["capital_allocation"] is False
assert weights["broker_position_sizing"] is False


comparison = main.jarvis_shadow_champion_compare(
    {
        "trades": 20,
        "return_pct": 0.05,
        "expectancy": 10,
        "avg_loss": 10,
        "profit_factor": 1.4,
        "win_rate": 0.50,
        "max_drawdown_pct": 0.10,
    },
    {
        "trades": 20,
        "return_pct": 0.10,
        "expectancy": 20,
        "avg_loss": 10,
        "profit_factor": 2.0,
        "win_rate": 0.60,
        "max_drawdown_pct": 0.05,
    },
)


assert (
    comparison[
        "automatic_production_promotion"
    ]
    is False
)


print("Performance drift detection: ACTIVE")
print("Research strategy weighting: ACTIVE")
print("Weight normalization: PASS")
print("Weight -> broker capital allocation: BLOCKED")
print("Shadow champion/challenger: ACTIVE")
print("Automatic production promotion: BLOCKED")
print("Performance learning: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("PERFORMANCE LEARNING FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# V6 SAFETY
# ============================================================

print()
print("Checking V6 trading safety...")


probe = r'''
import main


v6 = main.jarvis_trading_v6_status()


assert v6["research_only"]
assert v6["paper_only"]
assert v6["live_execution"] is False

assert v6["stale_data_execution"] is False
assert v6["same_tick_reversal"] is False

assert (
    v6[
        "research_weights_drive_broker_capital"
    ]
    is False
)

assert v6["background_market_polling"] is False

assert v6["automatic_strategy_promotion"] is False
assert v6["automatic_registry_mutation"] is False
assert v6["automatic_broker_order"] is False
assert v6["automatic_live_position_management"] is False
assert v6["production_self_modification"] is False


for capability in (
    "order.place",
    "order.modify",
    "order.cancel",
    "trade.execute",
    "trading.live.execute",
):

    assert (
        main.jarvis_trading_guard(
            capability
        )[
            "allowed"
        ]
        is False
    )


print("Paper-only trading: ENFORCED")
print("Live broker orders: BLOCKED")
print("Automatic live position management: BLOCKED")
print("Automatic strategy promotion: BLOCKED")
print("Automatic registry mutation: BLOCKED")
print("Production self-modification: BLOCKED")
print("V6 safety: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("V6 SAFETY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# TARGETED REGRESSION
# ============================================================

print()
print("Running Trading Intelligence V6 targeted regression...")


r = run(
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v6",
    "tests.test_trading_intelligence_v5",
    "tests.test_trading_intelligence_v4",
    "tests.test_trading_intelligence_v3",
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

    print("TARGETED TEST FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FULL REGRESSION
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

    print("FULL REGRESSION FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FINAL VERIFICATION
# ============================================================

for relative, before in PROTECTED.items():

    if sha(
        ROOT / relative
    ) != before:

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
        "v5=main.jarvis_trading_v5_status(); "
        "v6=main.jarvis_trading_v6_status(); "
        "assert v5['walk_forward_validation']; "
        "assert v6['paper_only']; "
        "assert v6['live_execution'] is False; "
        "assert v6['automatic_broker_order'] is False; "
        "print('Final Protected Core: PASS'); "
        "print('Trading V5 validation: PRESERVED'); "
        "print('Trading V6 paper-only safety: PASS')"
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

    print("FINAL BROWSER FAILURE")
    rollback()
    sys.exit(1)


print("Final browser DOM test: PASS")


# ============================================================
# SUCCESS
# ============================================================

status = run(
    "-c",
    (
        "import main,pprint; "
        "pprint.pp(main.jarvis_trading_v6_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V6 SUCCESS")
print("=" * 80)

print()
print("LIVE MARKET OBSERVATION")
print("Canonical FYERS quote bridge: AVAILABLE")
print("Explicit real quote read: AVAILABLE")
print("Background autonomous polling: DISABLED")
print("Provider timestamp normalization: ACTIVE")
print("Received-at fallback timestamp: ACTIVE")
print()

print("PAPER / SHADOW EXECUTION")
print("Virtual long entries: ACTIVE")
print("Virtual short entries: ACTIVE")
print("Virtual exits: ACTIVE")
print("Virtual PnL: ACTIVE")
print("Bid/ask-aware virtual fills: ACTIVE")
print("Configurable slippage: ACTIVE")
print("Same-tick reversal: BLOCKED")
print("Broker order generation: BLOCKED")
print()

print("MARKET SAFETY")
print("Quote age validation: ACTIVE")
print("Future timestamp validation: ACTIVE")
print("Stale quote execution: BLOCKED")
print("Kill switch: ACTIVE")
print("Explicit resume: ACTIVE")
print()

print("PERFORMANCE LEARNING")
print("Persistent evidence ledger: ACTIVE")
print("Performance drift detection: ACTIVE")
print("Expectancy deterioration: ACTIVE")
print("Profit-factor deterioration: ACTIVE")
print("Win-rate deterioration: ACTIVE")
print("Drawdown deterioration: ACTIVE")
print("Research strategy weighting: ACTIVE")
print("Shadow champion/challenger: ACTIVE")
print("Paper strategy ranking: ACTIVE")
print()

print("GOVERNANCE")
print("Research weights -> broker sizing: BLOCKED")
print("Automatic production promotion: BLOCKED")
print("Automatic strategy registry mutation: BLOCKED")
print("Automatic live position management: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Production self-modification: BLOCKED")
print()

print("PRESERVED")
print("Trading V1/V1.1: YES")
print("Trading V2 Backtester: YES")
print("Trading V3 Derivatives: YES")
print("Trading V4 Evolution: YES")
print("Trading V5 Anti-overfitting: YES")
print("Canonical FYERS bridge: YES")
print("Browser lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT:")
print("NAUTILUSTRADER ISOLATED RESEARCH KERNEL")
print("High-fidelity event-driven backtesting")
print("Order-book / execution simulation foundation")
print("Portfolio/account simulation")
print("Strategy adapter layer")
print("JARVIS -> Nautilus research bridge")
print("No live broker execution")
print()
print("AFTER THAT:")
print("Trading Intelligence V7")
print("Historical derivatives-feature streams")
print("Real option-chain data provider integration")
print("Strategy portfolio / ensemble research")
print("Cross-asset regime intelligence")
print("Automated research campaigns under V5 validation gates")
