# ============================================================
# JARVIS SCALPING RESEARCH ENGINE
# V8
# ============================================================
#
# RESEARCH ONLY
#
# DATA:
#   Upstox Historical V3
#   agents.upstox_historical_loader
#
# TIMEFRAMES:
#   15m = CONTEXT
#   5m  = SETUP / TRIGGER
#
# SYMBOLS:
#   NIFTY
#   BANKNIFTY
#
# STRATEGIES:
#   VWAP_REVERSION
#   ORB_BREAKOUT
#   MOMENTUM_CONTINUATION
#   MEAN_REVERSION
#
# V8:
#   - 10,000 x 5m requested bars
#   - Symbol data downloaded once
#   - In-memory research cache
#   - Valid R/R parameter universe only
#   - Signal diagnostics
#   - Trade diagnostics
#   - Train / validation / OOS
#   - Walk-forward
#   - Parameter robustness
#   - Slippage
#   - Transaction cost
#   - Rupee P&L
#   - R-multiple
#   - NOT_TESTABLE state
#
# NO LIVE EXECUTION
# NO PAPER EXECUTION
#
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List
import json
import math

import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
]

STRATEGIES = [
    "VWAP_REVERSION",
    "ORB_BREAKOUT",
    "MOMENTUM_CONTINUATION",
    "MEAN_REVERSION",
]

TIMEFRAME = "5m"
CONTEXT_TIMEFRAME = "15m"

REQUESTED_BARS = 10000

STARTING_CAPITAL = 1_000_000.0

RISK_PER_TRADE_PERCENT = 0.50

TRAIN_FRACTION = 0.55
VALIDATION_FRACTION = 0.20
OOS_FRACTION = 0.25

MIN_TOTAL_BARS = 1000
MIN_TRAIN_BARS = 500
MIN_VALIDATION_BARS = 250
MIN_OOS_BARS = 250

MIN_OOS_TRADES = 30
MIN_WALK_FORWARD_TRADES = 10

MIN_PROFIT_FACTOR = 1.20
MIN_OOS_RETURN_PERCENT = 0.50
MIN_AVERAGE_R = 0.05
MAX_DRAWDOWN_PERCENT = 5.0

MIN_REWARD_RISK = 1.20

EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
VOLUME_PERIOD = 20

ORB_MINUTES = 15

STOP_ATR_VALUES = [
    0.8,
    1.0,
    1.2,
]

TARGET_ATR_VALUES = [
    1.2,
    1.5,
    1.8,
]

DISTANCE_VALUES = [
    0.8,
    1.0,
    1.2,
]

INSTRUMENT_CONFIG = {
    "NIFTY": {
        "lot_size": 1,
        "point_value": 1.0,
        "slippage_points": 1.0,
        "round_trip_cost_points": 2.0,
    },
    "BANKNIFTY": {
        "lot_size": 1,
        "point_value": 1.0,
        "slippage_points": 2.0,
        "round_trip_cost_points": 4.0,
    },
}

OUTPUT_DIR = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

LATEST_FILE = (
    OUTPUT_DIR
    / "scalping_research_latest_v8.json"
)


# ============================================================
# TRADE
# ============================================================

@dataclass
class Trade:

    entry_time: str
    exit_time: str

    symbol: str
    strategy: str
    direction: str

    entry_price: float
    exit_price: float

    stop_price: float
    target_price: float

    quantity: int
    lots: int

    risk_points: float
    gross_points: float

    gross_pnl: float
    slippage_cost: float
    transaction_cost: float
    net_pnl: float

    r_multiple: float

    exit_reason: str


# ============================================================
# HELPERS
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:

        result = float(
            value
        )

        if not math.isfinite(
            result
        ):

            return default

        return result

    except Exception:

        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:

        return int(
            float(
                value
            )
        )

    except Exception:

        return default


def pct(
    value: float,
    denominator: float,
) -> float:

    if denominator == 0:

        return 0.0

    return (
        value
        /
        denominator
        *
        100.0
    )


# ============================================================
# DATA
# ============================================================

def load_symbol_data(
    symbol: str,
) -> Dict[str, Any]:

    print()
    print(
        f"JARVIS DATA > "
        f"Downloading {symbol} history once..."
    )

    try:

        from agents.upstox_historical_loader import (
            get_symbol_5m,
        )

    except Exception as exc:

        return {
            "success":
                False,
            "status":
                "IMPORT_ERROR",
            "message":
                str(exc),
        }

    try:

        result = get_symbol_5m(
            symbol,
            bars=REQUESTED_BARS,
        )

    except Exception as exc:

        return {
            "success":
                False,
            "status":
                "LOADER_ERROR",
            "message":
                str(exc),
        }

    if not isinstance(
        result,
        dict,
    ):

        return {
            "success":
                False,
            "status":
                "INVALID_RESULT",
            "message":
                "Invalid loader response.",
        }

    frame = result.get(
        "data"
    )

    if not isinstance(
        frame,
        pd.DataFrame,
    ):

        return {
            "success":
                False,
            "status":
                "NO_DATAFRAME",
            "message":
                (
                    result.get(
                        "message"
                    )
                    or
                    "No historical dataframe."
                ),
        }

    return {
        "success":
            True,
        "status":
            result.get(
                "data_quality",
                "UNKNOWN",
            ),
        "data":
            frame,
        "bars":
            len(frame),
        "start":
            result.get(
                "start"
            ),
        "end":
            result.get(
                "end"
            ),
        "failures":
            result.get(
                "failures",
                [],
            ),
    }


def prepare_frame(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    data = frame.copy()

    required = {
        "Open",
        "High",
        "Low",
        "Close",
    }

    missing = (
        required
        -
        set(
            data.columns
        )
    )

    if missing:

        raise ValueError(
            "Missing columns: "
            +
            ", ".join(
                sorted(
                    missing
                )
            )
        )

    for column in [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]:

        if column in data.columns:

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            )

    if "Volume" not in data.columns:

        data["Volume"] = 0.0

    data = (
        data
        .dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )
        .sort_index()
    )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):

        raise ValueError(
            "Historical index must be DatetimeIndex."
        )

    return data


# ============================================================
# INDICATORS
# ============================================================

def ema(
    series: pd.Series,
    period: int,
) -> pd.Series:

    return (
        series
        .ewm(
            span=period,
            adjust=False,
        )
        .mean()
    )


def atr(
    frame: pd.DataFrame,
) -> pd.Series:

    previous = (
        frame["Close"]
        .shift(1)
    )

    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (
                frame["High"]
                -
                previous
            ).abs(),
            (
                frame["Low"]
                -
                previous
            ).abs(),
        ],
        axis=1,
    ).max(
        axis=1
    )

    return (
        true_range
        .rolling(
            ATR_PERIOD
        )
        .mean()
    )


def rsi(
    series: pd.Series,
) -> pd.Series:

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = (
        gain
        .rolling(
            RSI_PERIOD
        )
        .mean()
    )

    avg_loss = (
        loss
        .rolling(
            RSI_PERIOD
        )
        .mean()
    )

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan,
        )
    )

    result = (
        100.0
        -
        (
            100.0
            /
            (
                1.0 + rs
            )
        )
    )

    return result.fillna(
        50.0
    )


def vwap(
    frame: pd.DataFrame,
) -> pd.Series:

    typical = (
        frame["High"]
        +
        frame["Low"]
        +
        frame["Close"]
    ) / 3.0

    volume = (
        frame["Volume"]
        .replace(
            0,
            np.nan,
        )
    )

    if volume.notna().sum() == 0:

        return (
            typical
            .expanding()
            .mean()
        )

    return (
        (
            typical
            *
            volume
        ).cumsum()
        /
        volume.cumsum()
    ).fillna(
        typical
        .expanding()
        .mean()
    )


def add_indicators(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    data = frame.copy()

    data["EMA20"] = ema(
        data["Close"],
        EMA_FAST,
    )

    data["EMA50"] = ema(
        data["Close"],
        EMA_SLOW,
    )

    data["ATR"] = atr(
        data
    )

    data["RSI"] = rsi(
        data["Close"]
    )

    data["VWAP"] = vwap(
        data
    )

    data["VolumeMA20"] = (
        data["Volume"]
        .rolling(
            VOLUME_PERIOD
        )
        .mean()
    )

    return data


# ============================================================
# 15M CONTEXT
# ============================================================

def add_context(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    context = (
        frame[
            [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
        ]
        .resample(
            "15min",
            label="left",
            closed="left",
        )
        .agg(
            {
                "Open":
                    "first",
                "High":
                    "max",
                "Low":
                    "min",
                "Close":
                    "last",
                "Volume":
                    "sum",
            }
        )
        .dropna()
    )

    context["EMA20"] = ema(
        context["Close"],
        EMA_FAST,
    )

    context["EMA50"] = ema(
        context["Close"],
        EMA_SLOW,
    )

    context["RSI"] = rsi(
        context["Close"]
    )

    context["ATR"] = atr(
        context
    )

    context["Direction"] = np.where(
        (
            context["EMA20"]
            >
            context["EMA50"]
        )
        &
        (
            context["Close"]
            >
            context["EMA20"]
        ),
        "BULLISH",
        np.where(
            (
                context["EMA20"]
                <
                context["EMA50"]
            )
            &
            (
                context["Close"]
                <
                context["EMA20"]
            ),
            "BEARISH",
            "NEUTRAL",
        ),
    )

    context = context[
        [
            "EMA20",
            "EMA50",
            "RSI",
            "ATR",
            "Direction",
        ]
    ].rename(
        columns={
            "EMA20":
                "CTX_EMA20",
            "EMA50":
                "CTX_EMA50",
            "RSI":
                "CTX_RSI",
            "ATR":
                "CTX_ATR",
            "Direction":
                "CTX_DIRECTION",
        }
    )

    return pd.merge_asof(
        frame.sort_index(),
        context.sort_index(),
        left_index=True,
        right_index=True,
        direction="backward",
    )


# ============================================================
# ORB
# ============================================================

def add_orb(
    frame: pd.DataFrame,
) -> pd.DataFrame:

    data = frame.copy()

    if data.index.tz is not None:

        local = (
            data.index
            .tz_convert(
                "Asia/Kolkata"
            )
        )

    else:

        local = data.index

    minutes_from_open = (
        local.hour
        *
        60
        +
        local.minute
        -
        555
    )

    opening = (
        (minutes_from_open >= 0)
        &
        (
            minutes_from_open
            <
            ORB_MINUTES
        )
    )

    dates = pd.Series(
        local.date,
        index=data.index,
    )

    data["SessionDate"] = dates

    data["ORBHigh"] = (
        data["High"]
        .where(
            opening
        )
        .groupby(
            dates
        )
        .transform(
            "max"
        )
    )

    data["ORBLow"] = (
        data["Low"]
        .where(
            opening
        )
        .groupby(
            dates
        )
        .transform(
            "min"
        )
    )

    return data


# ============================================================
# SIGNAL DIAGNOSTICS
# ============================================================

def blank_signal_diagnostics() -> Dict[str, int]:

    return {
        "bars_scanned":
            0,
        "raw_candidates":
            0,
        "signals":
            0,
        "context_rejections":
            0,
        "momentum_rejections":
            0,
        "volume_rejections":
            0,
        "distance_rejections":
            0,
        "orb_rejections":
            0,
    }


def diagnose_signal(
    frame: pd.DataFrame,
    index: int,
    strategy: str,
    distance: float,
    diagnostics: Dict[str, int],
) -> str | None:

    diagnostics[
        "bars_scanned"
    ] += 1

    row = frame.iloc[
        index
    ]

    previous = frame.iloc[
        index - 1
    ]

    close = safe_float(
        row["Close"]
    )

    ema20 = safe_float(
        row["EMA20"]
    )

    ema50 = safe_float(
        row["EMA50"]
    )

    atr_value = safe_float(
        row["ATR"]
    )

    rsi_value = safe_float(
        row["RSI"],
        50.0,
    )

    context = str(
        row.get(
            "CTX_DIRECTION",
            "NEUTRAL",
        )
    )

    volume = safe_float(
        row.get(
            "Volume"
        )
    )

    volume_ma = safe_float(
        row.get(
            "VolumeMA20"
        )
    )

    volume_ok = (
        volume_ma <= 0
        or
        volume >= volume_ma
    )

    # --------------------------------------------------------
    # VWAP REVERSION
    # --------------------------------------------------------

    if strategy == "VWAP_REVERSION":

        vwap_value = safe_float(
            row["VWAP"]
        )

        if atr_value <= 0:

            diagnostics[
                "distance_rejections"
            ] += 1

            return None

        deviation = (
            abs(
                close
                -
                vwap_value
            )
            /
            atr_value
        )

        bullish = (
            close < vwap_value
            and
            rsi_value <= 35.0
            and
            context != "BEARISH"
        )

        bearish = (
            close > vwap_value
            and
            rsi_value >= 65.0
            and
            context != "BULLISH"
        )

        if not (
            bullish
            or
            bearish
        ):

            return None

        diagnostics[
            "raw_candidates"
        ] += 1

        if (
            deviation
            <
            distance
        ):

            diagnostics[
                "distance_rejections"
            ] += 1

            return None

        diagnostics[
            "signals"
        ] += 1

        return (
            "LONG"
            if bullish
            else
            "SHORT"
        )

    # --------------------------------------------------------
    # ORB
    # --------------------------------------------------------

    if strategy == "ORB_BREAKOUT":

        orb_high = safe_float(
            row.get(
                "ORBHigh"
            )
        )

        orb_low = safe_float(
            row.get(
                "ORBLow"
            )
        )

        previous_close = safe_float(
            previous["Close"]
        )

        if (
            orb_high <= 0
            or
            orb_low <= 0
        ):

            diagnostics[
                "orb_rejections"
            ] += 1

            return None

        bullish = (
            previous_close
            <=
            orb_high
            and
            close
            >
            orb_high
        )

        bearish = (
            previous_close
            >=
            orb_low
            and
            close
            <
            orb_low
        )

        if not (
            bullish
            or
            bearish
        ):

            diagnostics[
                "orb_rejections"
            ] += 1

            return None

        diagnostics[
            "raw_candidates"
        ] += 1

        if not volume_ok:

            diagnostics[
                "volume_rejections"
            ] += 1

            return None

        diagnostics[
            "signals"
        ] += 1

        return (
            "LONG"
            if bullish
            else
            "SHORT"
        )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if strategy == "MOMENTUM_CONTINUATION":

        bullish = (
            context == "BULLISH"
            and
            close > ema20
            and
            ema20 > ema50
        )

        bearish = (
            context == "BEARISH"
            and
            close < ema20
            and
            ema20 < ema50
        )

        if not (
            bullish
            or
            bearish
        ):

            diagnostics[
                "context_rejections"
            ] += 1

            return None

        diagnostics[
            "raw_candidates"
        ] += 1

        if (
            bullish
            and
            rsi_value
            <
            58.0
        ):

            diagnostics[
                "momentum_rejections"
            ] += 1

            return None

        if (
            bearish
            and
            rsi_value
            >
            42.0
        ):

            diagnostics[
                "momentum_rejections"
            ] += 1

            return None

        if not volume_ok:

            diagnostics[
                "volume_rejections"
            ] += 1

            return None

        diagnostics[
            "signals"
        ] += 1

        return (
            "LONG"
            if bullish
            else
            "SHORT"
        )

    # --------------------------------------------------------
    # MEAN REVERSION
    # --------------------------------------------------------

    if strategy == "MEAN_REVERSION":

        if atr_value <= 0:

            diagnostics[
                "distance_rejections"
            ] += 1

            return None

        deviation = (
            close
            -
            ema20
        )

        threshold = (
            atr_value
            *
            distance
        )

        bullish = (
            deviation
            <=
            -threshold
            and
            rsi_value
            <=
            35.0
        )

        bearish = (
            deviation
            >=
            threshold
            and
            rsi_value
            >=
            65.0
        )

        if not (
            bullish
            or
            bearish
        ):

            diagnostics[
                "distance_rejections"
            ] += 1

            return None

        diagnostics[
            "raw_candidates"
        ] += 1

        diagnostics[
            "signals"
        ] += 1

        return (
            "LONG"
            if bullish
            else
            "SHORT"
        )

    return None


# ============================================================
# TRADE DIAGNOSTICS
# ============================================================

def blank_trade_diagnostics() -> Dict[str, int]:

    return {
        "signal_count":
            0,
        "invalid_price":
            0,
        "invalid_atr":
            0,
        "invalid_stop_distance":
            0,
        "invalid_target_distance":
            0,
        "rr_rejection":
            0,
        "position_size_zero":
            0,
        "position_size_valid":
            0,
        "trade_created":
            0,
    }


# ============================================================
# POSITION SIZE
# ============================================================

def position_size(
    symbol: str,
    risk_points: float,
) -> Dict[str, Any]:

    config = INSTRUMENT_CONFIG[
        symbol
    ]

    lot_size = max(
        1,
        safe_int(
            config.get(
                "lot_size",
                1,
            ),
            1,
        ),
    )

    point_value = safe_float(
        config.get(
            "point_value",
            1.0,
        ),
        1.0,
    )

    maximum_risk = (
        STARTING_CAPITAL
        *
        RISK_PER_TRADE_PERCENT
        /
        100.0
    )

    risk_per_unit = (
        abs(
            risk_points
        )
        *
        point_value
    )

    if risk_per_unit <= 0:

        return {
            "quantity":
                0,
            "lots":
                0,
            "planned_risk":
                0.0,
        }

    quantity = int(
        maximum_risk
        /
        risk_per_unit
    )

    lots = (
        quantity
        //
        lot_size
    )

    quantity = (
        lots
        *
        lot_size
    )

    return {
        "quantity":
            int(
                quantity
            ),
        "lots":
            int(
                lots
            ),
        "planned_risk":
            float(
                quantity
                *
                risk_per_unit
            ),
    }


# ============================================================
# TRADE SIMULATION
# ============================================================

def simulate_trade(
    frame: pd.DataFrame,
    entry_index: int,
    direction: str,
    strategy: str,
    symbol: str,
    stop_atr: float,
    target_atr: float,
    diagnostics: Dict[str, int],
) -> Trade | None:

    diagnostics[
        "signal_count"
    ] += 1

    row = frame.iloc[
        entry_index
    ]

    entry_price = safe_float(
        row["Close"]
    )

    atr_value = safe_float(
        row["ATR"]
    )

    if entry_price <= 0:

        diagnostics[
            "invalid_price"
        ] += 1

        return None

    if atr_value <= 0:

        diagnostics[
            "invalid_atr"
        ] += 1

        return None

    stop_distance = (
        atr_value
        *
        stop_atr
    )

    target_distance = (
        atr_value
        *
        target_atr
    )

    if stop_distance <= 0:

        diagnostics[
            "invalid_stop_distance"
        ] += 1

        return None

    if target_distance <= 0:

        diagnostics[
            "invalid_target_distance"
        ] += 1

        return None

    reward_risk = (
        target_distance
        /
        stop_distance
    )

    if (
        reward_risk
        <
        MIN_REWARD_RISK
    ):

        diagnostics[
            "rr_rejection"
        ] += 1

        return None

    if direction == "LONG":

        stop_price = (
            entry_price
            -
            stop_distance
        )

        target_price = (
            entry_price
            +
            target_distance
        )

    else:

        stop_price = (
            entry_price
            +
            stop_distance
        )

        target_price = (
            entry_price
            -
            target_distance
        )

    sizing = position_size(
        symbol,
        stop_distance,
    )

    quantity = int(
        sizing[
            "quantity"
        ]
    )

    lots = int(
        sizing[
            "lots"
        ]
    )

    if (
        quantity <= 0
        or
        lots <= 0
    ):

        diagnostics[
            "position_size_zero"
        ] += 1

        return None

    diagnostics[
        "position_size_valid"
    ] += 1

    exit_index = (
        len(frame) - 1
    )

    exit_price = safe_float(
        frame.iloc[
            -1
        ]["Close"]
    )

    exit_reason = (
        "END_OF_DATA"
    )

    for i in range(
        entry_index + 1,
        len(frame),
    ):

        candle = frame.iloc[
            i
        ]

        high = safe_float(
            candle["High"]
        )

        low = safe_float(
            candle["Low"]
        )

        if direction == "LONG":

            stop_hit = (
                low
                <=
                stop_price
            )

            target_hit = (
                high
                >=
                target_price
            )

        else:

            stop_hit = (
                high
                >=
                stop_price
            )

            target_hit = (
                low
                <=
                target_price
            )

        if (
            stop_hit
            and
            target_hit
        ):

            exit_index = i
            exit_price = stop_price
            exit_reason = (
                "STOP_AND_TARGET_SAME_BAR"
            )

            break

        if stop_hit:

            exit_index = i
            exit_price = stop_price
            exit_reason = (
                "STOP"
            )

            break

        if target_hit:

            exit_index = i
            exit_price = target_price
            exit_reason = (
                "TARGET"
            )

            break

    if direction == "LONG":

        gross_points = (
            exit_price
            -
            entry_price
        )

    else:

        gross_points = (
            entry_price
            -
            exit_price
        )

    config = INSTRUMENT_CONFIG[
        symbol
    ]

    point_value = safe_float(
        config.get(
            "point_value",
            1.0,
        ),
        1.0,
    )

    slippage_points = (
        safe_float(
            config.get(
                "slippage_points",
                1.0,
            ),
            1.0,
        )
        *
        2.0
    )

    transaction_points = safe_float(
        config.get(
            "round_trip_cost_points",
            2.0,
        ),
        2.0,
    )

    gross_pnl = (
        gross_points
        *
        point_value
        *
        quantity
    )

    slippage_cost = (
        slippage_points
        *
        point_value
        *
        quantity
    )

    transaction_cost = (
        transaction_points
        *
        point_value
        *
        quantity
    )

    net_pnl = (
        gross_pnl
        -
        slippage_cost
        -
        transaction_cost
    )

    risk_pnl = (
        stop_distance
        *
        point_value
        *
        quantity
    )

    if risk_pnl <= 0:

        diagnostics[
            "invalid_stop_distance"
        ] += 1

        return None

    diagnostics[
        "trade_created"
    ] += 1

    return Trade(
        entry_time=str(
            frame.index[
                entry_index
            ]
        ),
        exit_time=str(
            frame.index[
                exit_index
            ]
        ),
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        entry_price=float(
            entry_price
        ),
        exit_price=float(
            exit_price
        ),
        stop_price=float(
            stop_price
        ),
        target_price=float(
            target_price
        ),
        quantity=quantity,
        lots=lots,
        risk_points=float(
            stop_distance
        ),
        gross_points=float(
            gross_points
        ),
        gross_pnl=float(
            gross_pnl
        ),
        slippage_cost=float(
            slippage_cost
        ),
        transaction_cost=float(
            transaction_cost
        ),
        net_pnl=float(
            net_pnl
        ),
        r_multiple=float(
            net_pnl
            /
            risk_pnl
        ),
        exit_reason=exit_reason,
    )


# ============================================================
# BACKTEST
# ============================================================

def run_backtest(
    frame: pd.DataFrame,
    symbol: str,
    strategy: str,
    start: int,
    end: int,
    stop_atr: float,
    target_atr: float,
    distance: float,
) -> Dict[str, Any]:

    signal_diagnostics = (
        blank_signal_diagnostics()
    )

    trade_diagnostics = (
        blank_trade_diagnostics()
    )

    trades: List[
        Trade
    ] = []

    index = max(
        start,
        2,
    )

    while index < end:

        side = diagnose_signal(
            frame,
            index,
            strategy,
            distance,
            signal_diagnostics,
        )

        if side is None:

            index += 1

            continue

        trade = simulate_trade(
            frame,
            index,
            side,
            strategy,
            symbol,
            stop_atr,
            target_atr,
            trade_diagnostics,
        )

        if trade is None:

            index += 1

            continue

        trades.append(
            trade
        )

        try:

            exit_index = (
                frame.index.get_loc(
                    pd.Timestamp(
                        trade.exit_time
                    )
                )
            )

            index = max(
                index + 1,
                int(
                    exit_index
                ) + 1,
            )

        except Exception:

            index += 1

    return {
        "trades":
            trades,
        "signal_diagnostics":
            signal_diagnostics,
        "trade_diagnostics":
            trade_diagnostics,
    }


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    trades: List[Trade],
) -> Dict[str, Any]:

    if not trades:

        return {
            "trades":
                0,
            "net_pnl":
                0.0,
            "gross_points":
                0.0,
            "return_percent":
                0.0,
            "profit_factor":
                0.0,
            "win_rate":
                0.0,
            "average_r":
                0.0,
            "total_r":
                0.0,
            "max_drawdown":
                0.0,
            "max_drawdown_percent":
                0.0,
            "costs":
                0.0,
        }

    pnls = np.array(
        [
            trade.net_pnl
            for trade
            in trades
        ],
        dtype=float,
    )

    rs = np.array(
        [
            trade.r_multiple
            for trade
            in trades
        ],
        dtype=float,
    )

    positive = pnls[
        pnls > 0
    ]

    negative = pnls[
        pnls < 0
    ]

    gross_profit = float(
        positive.sum()
    )

    gross_loss = abs(
        float(
            negative.sum()
        )
    )

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            /
            gross_loss
        )

    elif gross_profit > 0:

        profit_factor = float(
            "inf"
        )

    else:

        profit_factor = 0.0

    equity = (
        STARTING_CAPITAL
        +
        np.cumsum(
            pnls
        )
    )

    peaks = (
        np.maximum.accumulate(
            equity
        )
    )

    drawdown = (
        peaks
        -
        equity
    )

    max_drawdown = float(
        drawdown.max()
    )

    costs = sum(
        (
            trade.slippage_cost
            +
            trade.transaction_cost
        )
        for trade
        in trades
    )

    return {
        "trades":
            len(
                trades
            ),
        "net_pnl":
            float(
                pnls.sum()
            ),
        "gross_points":
            float(
                sum(
                    trade.gross_points
                    for trade
                    in trades
                )
            ),
        "return_percent":
            pct(
                float(
                    pnls.sum()
                ),
                STARTING_CAPITAL,
            ),
        "profit_factor":
            float(
                profit_factor
            ),
        "win_rate":
            float(
                (
                    pnls > 0
                ).mean()
                *
                100.0
            ),
        "average_r":
            float(
                rs.mean()
            ),
        "total_r":
            float(
                rs.sum()
            ),
        "max_drawdown":
            max_drawdown,
        "max_drawdown_percent":
            pct(
                max_drawdown,
                STARTING_CAPITAL,
            ),
        "costs":
            float(
                costs
            ),
    }


# ============================================================
# PARAMETER GRID
# ============================================================

def parameter_grid(
    strategy: str,
) -> List[Dict[str, float]]:

    result = []

    for stop_atr in (
        STOP_ATR_VALUES
    ):

        for target_atr in (
            TARGET_ATR_VALUES
        ):

            reward_risk = (
                target_atr
                /
                stop_atr
            )

            if (
                reward_risk
                <
                MIN_REWARD_RISK
            ):

                continue

            if strategy in {
                "VWAP_REVERSION",
                "MEAN_REVERSION",
            }:

                for distance in (
                    DISTANCE_VALUES
                ):

                    result.append(
                        {
                            "stop_atr":
                                stop_atr,
                            "target_atr":
                                target_atr,
                            "distance":
                                distance,
                            "reward_risk":
                                reward_risk,
                        }
                    )

            else:

                result.append(
                    {
                        "stop_atr":
                            stop_atr,
                        "target_atr":
                            target_atr,
                        "distance":
                            1.0,
                        "reward_risk":
                            reward_risk,
                    }
                )

    return result


# ============================================================
# ROBUSTNESS
# ============================================================

def run_robustness(
    frame: pd.DataFrame,
    symbol: str,
    strategy: str,
    start: int,
    end: int,
) -> Dict[str, Any]:

    rows = []

    for params in parameter_grid(
        strategy
    ):

        test = run_backtest(
            frame,
            symbol,
            strategy,
            start,
            end,
            params["stop_atr"],
            params["target_atr"],
            params["distance"],
        )

        metrics = calculate_metrics(
            test["trades"]
        )

        rows.append(
            {
                **params,
                "trades":
                    metrics[
                        "trades"
                    ],
                "profit_factor":
                    metrics[
                        "profit_factor"
                    ],
                "return_percent":
                    metrics[
                        "return_percent"
                    ],
                "average_r":
                    metrics[
                        "average_r"
                    ],
            }
        )

    usable = [
        row
        for row
        in rows
        if row["trades"] >= 3
    ]

    if not usable:

        return {
            "robust":
                False,
            "parameter_sets":
                len(
                    rows
                ),
            "usable_parameter_sets":
                0,
            "positive_parameter_sets":
                0,
            "positive_ratio":
                0.0,
            "results":
                rows,
        }

    positive = [
        row
        for row
        in usable
        if (
            row["profit_factor"]
            >=
            MIN_PROFIT_FACTOR
        )
        and
        (
            row["return_percent"]
            >
            0
        )
    ]

    ratio = (
        len(
            positive
        )
        /
        len(
            usable
        )
    )

    return {
        "robust":
            bool(
                ratio >= 0.50
            ),
        "parameter_sets":
            len(
                rows
            ),
        "usable_parameter_sets":
            len(
                usable
            ),
        "positive_parameter_sets":
            len(
                positive
            ),
        "positive_ratio":
            float(
                ratio
            ),
        "median_profit_factor":
            float(
                np.median(
                    [
                        row[
                            "profit_factor"
                        ]
                        for row
                        in usable
                    ]
                )
            ),
        "median_return_percent":
            float(
                np.median(
                    [
                        row[
                            "return_percent"
                        ]
                        for row
                        in usable
                    ]
                )
            ),
        "results":
            rows,
    }


# ============================================================
# WALK FORWARD
# ============================================================

def run_walk_forward(
    frame: pd.DataFrame,
    symbol: str,
    strategy: str,
    params: Dict[str, float],
) -> Dict[str, Any]:

    total = len(
        frame
    )

    windows = [
        (
            0.00,
            0.50,
        ),
        (
            0.15,
            0.65,
        ),
        (
            0.30,
            0.80,
        ),
        (
            0.45,
            1.00,
        ),
    ]

    rows = []

    for (
        start_fraction,
        end_fraction,
    ) in windows:

        start = int(
            total
            *
            start_fraction
        )

        end = int(
            total
            *
            end_fraction
        )

        if (
            end
            -
            start
            <
            MIN_VALIDATION_BARS
        ):

            continue

        test = run_backtest(
            frame,
            symbol,
            strategy,
            start,
            end,
            params[
                "stop_atr"
            ],
            params[
                "target_atr"
            ],
            params[
                "distance"
            ],
        )

        metrics = calculate_metrics(
            test[
                "trades"
            ]
        )

        rows.append(
            {
                "start_fraction":
                    start_fraction,
                "end_fraction":
                    end_fraction,
                "metrics":
                    metrics,
            }
        )

    passing = [
        row
        for row
        in rows
        if (
            row[
                "metrics"
            ][
                "trades"
            ]
            >=
            MIN_WALK_FORWARD_TRADES
        )
        and
        (
            row[
                "metrics"
            ][
                "profit_factor"
            ]
            >=
            MIN_PROFIT_FACTOR
        )
        and
        (
            row[
                "metrics"
            ][
                "net_pnl"
            ]
            >
            0
        )
    ]

    return {
        "total_windows":
            len(
                rows
            ),
        "passing_windows":
            len(
                passing
            ),
        "pass":
            bool(
                len(
                    passing
                )
                >=
                2
            ),
        "windows":
            rows,
    }


# ============================================================
# VALIDATION
# ============================================================

def validation_gate(
    quality: Dict[str, Any],
    oos: Dict[str, Any],
    walk_forward: Dict[str, Any],
    robustness: Dict[str, Any],
) -> Dict[str, Any]:

    failures = []

    if not quality.get(
        "sufficient"
    ):

        failures.append(
            "Insufficient historical sample."
        )

    if (
        oos[
            "trades"
        ]
        ==
        0
    ):

        return {
            "validated":
                False,
            "status":
                "NOT_TESTABLE",
            "failures":
                [
                    "No OOS trades: NOT_TESTABLE."
                ],
        }

    if (
        oos[
            "trades"
        ]
        <
        MIN_OOS_TRADES
    ):

        failures.append(
            "Insufficient OOS trades."
        )

    if (
        oos[
            "profit_factor"
        ]
        <
        MIN_PROFIT_FACTOR
    ):

        failures.append(
            "OOS profit factor below threshold."
        )

    if (
        oos[
            "return_percent"
        ]
        <=
        MIN_OOS_RETURN_PERCENT
    ):

        failures.append(
            "OOS return below threshold."
        )

    if (
        oos[
            "average_r"
        ]
        <=
        MIN_AVERAGE_R
    ):

        failures.append(
            "OOS average R below threshold."
        )

    if (
        oos[
            "max_drawdown_percent"
        ]
        >
        MAX_DRAWDOWN_PERCENT
    ):

        failures.append(
            "OOS drawdown exceeds threshold."
        )

    if not walk_forward.get(
        "pass"
    ):

        failures.append(
            "Walk-forward validation failed."
        )

    if not robustness.get(
        "robust"
    ):

        failures.append(
            "Parameter robustness failed."
        )

    return {
        "validated":
            len(
                failures
            )
            ==
            0,
        "status":
            (
                "VALIDATED"
                if not failures
                else
                "UNVALIDATED"
            ),
        "failures":
            failures,
    }


# ============================================================
# SCORE
# ============================================================

def research_score(
    oos: Dict[str, Any],
    walk_forward: Dict[str, Any],
    robustness: Dict[str, Any],
) -> float:

    if (
        oos[
            "trades"
        ]
        ==
        0
    ):

        return 0.0

    score = 0.0

    if (
        oos[
            "trades"
        ]
        >=
        MIN_OOS_TRADES
    ):

        score += 20.0

    elif (
        oos[
            "trades"
        ]
        >=
        10
    ):

        score += 5.0

    if (
        oos[
            "profit_factor"
        ]
        >=
        2.0
    ):

        score += 20.0

    elif (
        oos[
            "profit_factor"
        ]
        >=
        1.5
    ):

        score += 15.0

    elif (
        oos[
            "profit_factor"
        ]
        >=
        MIN_PROFIT_FACTOR
    ):

        score += 10.0

    if (
        oos[
            "return_percent"
        ]
        >=
        5.0
    ):

        score += 20.0

    elif (
        oos[
            "return_percent"
        ]
        >=
        2.0
    ):

        score += 15.0

    elif (
        oos[
            "return_percent"
        ]
        >
        0
    ):

        score += 5.0

    if (
        oos[
            "average_r"
        ]
        >=
        0.50
    ):

        score += 15.0

    elif (
        oos[
            "average_r"
        ]
        >=
        0.25
    ):

        score += 10.0

    elif (
        oos[
            "average_r"
        ]
        >
        0
    ):

        score += 5.0

    if (
        oos[
            "max_drawdown_percent"
        ]
        <=
        MAX_DRAWDOWN_PERCENT
    ):

        score += 10.0

    if walk_forward.get(
        "pass"
    ):

        score += 10.0

    if robustness.get(
        "robust"
    ):

        score += 5.0

    return round(
        min(
            score,
            100.0,
        ),
        2,
    )


# ============================================================
# CELL
# ============================================================

def run_cell(
    symbol: str,
    strategy: str,
    frame: pd.DataFrame,
    quality: Dict[str, Any],
) -> Dict[str, Any]:

    usable = len(
        frame
    )

    if usable < 1000:

        return {
            "success":
                True,
            "research_family":
                "SCALPING",
            "symbol":
                symbol,
            "strategy":
                strategy,
            "status":
                "INSUFFICIENT_USABLE_BARS",
            "validated":
                False,
            "research_score":
                0.0,
            "validation_failures":
                [
                    "Insufficient usable bars."
                ],
        }

    train_end = int(
        usable
        *
        TRAIN_FRACTION
    )

    validation_end = int(
        usable
        *
        (
            TRAIN_FRACTION
            +
            VALIDATION_FRACTION
        )
    )

    train_bars = (
        train_end
    )

    validation_bars = (
        validation_end
        -
        train_end
    )

    oos_bars = (
        usable
        -
        validation_end
    )

    if (
        train_bars
        <
        MIN_TRAIN_BARS
        or
        validation_bars
        <
        MIN_VALIDATION_BARS
        or
        oos_bars
        <
        MIN_OOS_BARS
    ):

        return {
            "success":
                True,
            "research_family":
                "SCALPING",
            "symbol":
                symbol,
            "strategy":
                strategy,
            "status":
                "INSUFFICIENT_SPLIT_SIZE",
            "validated":
                False,
            "research_score":
                0.0,
            "validation_failures":
                [
                    "Train/validation/OOS split too small."
                ],
        }

    params_list = (
        parameter_grid(
            strategy
        )
    )

    if not params_list:

        return {
            "success":
                True,
            "research_family":
                "SCALPING",
            "symbol":
                symbol,
            "strategy":
                strategy,
            "status":
                "NOT_TESTABLE",
            "validated":
                False,
            "research_score":
                0.0,
            "validation_failures":
                [
                    "No valid parameter combinations."
                ],
        }

    candidates = []

    for params in params_list:

        test = run_backtest(
            frame,
            symbol,
            strategy,
            0,
            train_end,
            params[
                "stop_atr"
            ],
            params[
                "target_atr"
            ],
            params[
                "distance"
            ],
        )

        metrics = calculate_metrics(
            test[
                "trades"
            ]
        )

        candidates.append(
            {
                "params":
                    params,
                "metrics":
                    metrics,
            }
        )

    with_trades = [
        item
        for item in candidates
        if (
            item[
                "metrics"
            ][
                "trades"
            ]
            >
            0
        )
    ]

    ranking_pool = (
        with_trades
        if with_trades
        else
        candidates
    )

    ranking_pool.sort(
        key=lambda item: (
            item[
                "metrics"
            ][
                "total_r"
            ],
            item[
                "metrics"
            ][
                "profit_factor"
            ],
            item[
                "metrics"
            ][
                "trades"
            ],
        ),
        reverse=True,
    )

    best = ranking_pool[
        0
    ]

    params = best[
        "params"
    ]

    train_metrics = best[
        "metrics"
    ]

    validation_test = (
        run_backtest(
            frame,
            symbol,
            strategy,
            train_end,
            validation_end,
            params[
                "stop_atr"
            ],
            params[
                "target_atr"
            ],
            params[
                "distance"
            ],
        )
    )

    validation_metrics = (
        calculate_metrics(
            validation_test[
                "trades"
            ]
        )
    )

    oos_test = (
        run_backtest(
            frame,
            symbol,
            strategy,
            validation_end,
            usable,
            params[
                "stop_atr"
            ],
            params[
                "target_atr"
            ],
            params[
                "distance"
            ],
        )
    )

    oos_metrics = (
        calculate_metrics(
            oos_test[
                "trades"
            ]
        )
    )

    walk_forward = (
        run_walk_forward(
            frame,
            symbol,
            strategy,
            params,
        )
    )

    robustness = (
        run_robustness(
            frame,
            symbol,
            strategy,
            train_end,
            validation_end,
        )
    )

    gate = (
        validation_gate(
            quality,
            oos_metrics,
            walk_forward,
            robustness,
        )
    )

    score = (
        research_score(
            oos_metrics,
            walk_forward,
            robustness,
        )
    )

    return {
        "success":
            True,
        "research_family":
            "SCALPING",
        "status":
            gate[
                "status"
            ],
        "symbol":
            symbol,
        "strategy":
            strategy,
        "timeframe":
            TIMEFRAME,
        "context_timeframe":
            CONTEXT_TIMEFRAME,
        "selected_parameters":
            params,
        "parameter_universe":
            {
                "total":
                    len(
                        params_list
                    ),
                "minimum_reward_risk":
                    MIN_REWARD_RISK,
            },
        "data_quality":
            quality,
        "usable_bars":
            usable,
        "train_bars":
            train_bars,
        "validation_bars":
            validation_bars,
        "oos_bars":
            oos_bars,
        "train":
            train_metrics,
        "validation":
            validation_metrics,
        "oos":
            oos_metrics,
        "oos_signal_diagnostics":
            oos_test[
                "signal_diagnostics"
            ],
        "oos_trade_diagnostics":
            oos_test[
                "trade_diagnostics"
            ],
        "walk_forward":
            walk_forward,
        "robustness":
            robustness,
        "research_score":
            score,
        "validated":
            gate[
                "validated"
            ],
        "validation_failures":
            gate[
                "failures"
            ],
        "oos_trades":
            [
                asdict(
                    trade
                )
                for trade
                in oos_test[
                    "trades"
                ]
            ],
    }


# ============================================================
# PREPARE SYMBOL
# ============================================================

def prepare_symbol(
    symbol: str,
) -> Dict[str, Any]:

    loaded = (
        load_symbol_data(
            symbol
        )
    )

    if not loaded.get(
        "success"
    ):

        return {
            "success":
                False,
            "symbol":
                symbol,
            "status":
                loaded.get(
                    "status",
                    "DATA_ERROR",
                ),
            "error":
                loaded.get(
                    "message",
                    "Unknown data error.",
                ),
        }

    try:

        frame = (
            prepare_frame(
                loaded[
                    "data"
                ]
            )
        )

    except Exception as exc:

        return {
            "success":
                False,
            "symbol":
                symbol,
            "status":
                "PREP_ERROR",
            "error":
                str(exc),
        }

    if frame.index.tz is not None:

        local_index = (
            frame.index
            .tz_convert(
                "Asia/Kolkata"
            )
        )

    else:

        local_index = (
            frame.index
        )

    quality = {
        "bars":
            len(
                frame
            ),
        "trading_days":
            len(
                set(
                    local_index.date
                )
            ),
        "start":
            str(
                local_index[0]
            ),
        "end":
            str(
                local_index[-1]
            ),
        "sufficient":
            (
                len(
                    frame
                )
                >=
                MIN_TOTAL_BARS
            ),
        "loader_failures":
            loaded.get(
                "failures",
                [],
            ),
    }

    if not quality[
        "sufficient"
    ]:

        return {
            "success":
                False,
            "symbol":
                symbol,
            "status":
                "INSUFFICIENT_HISTORY",
            "quality":
                quality,
            "error":
                (
                    f"Only {len(frame)} bars; "
                    f"minimum={MIN_TOTAL_BARS}."
                ),
        }

    print(
        f"JARVIS DATA > "
        f"{symbol} "
        f"bars={len(frame)} | "
        f"days={quality['trading_days']} | "
        f"{quality['start']} -> "
        f"{quality['end']}"
    )

    try:

        frame = add_indicators(
            frame
        )

        frame = add_context(
            frame
        )

        frame = add_orb(
            frame
        )

    except Exception as exc:

        return {
            "success":
                False,
            "symbol":
                symbol,
            "status":
                "INDICATOR_ERROR",
            "error":
                str(exc),
        }

    frame = (
        frame
        .dropna(
            subset=[
                "EMA20",
                "EMA50",
                "ATR",
                "RSI",
                "CTX_EMA20",
                "CTX_EMA50",
                "CTX_ATR",
            ]
        )
        .copy()
    )

    quality[
        "usable_bars"
    ] = len(
        frame
    )

    return {
        "success":
            True,
        "symbol":
            symbol,
        "frame":
            frame,
        "quality":
            quality,
    }


# ============================================================
# MATRIX
# ============================================================

def run_matrix() -> Dict[str, Any]:

    symbol_cache: Dict[
        str,
        Dict[str, Any]
    ] = {}

    results = []

    print()
    print(
        "=" * 60
    )

    print(
        "JARVIS V8 > LOADING SYMBOL DATA"
    )

    print(
        "=" * 60
    )

    for symbol in SYMBOLS:

        symbol_cache[
            symbol
        ] = prepare_symbol(
            symbol
        )

    total_cells = (
        len(
            SYMBOLS
        )
        *
        len(
            STRATEGIES
        )
    )

    cell_number = 0

    for symbol in SYMBOLS:

        prepared = (
            symbol_cache[
                symbol
            ]
        )

        for strategy in STRATEGIES:

            cell_number += 1

            print()
            print(
                "-" * 60
            )

            print(
                f"JARVIS SCALPING V8 "
                f"{cell_number}/{total_cells}"
            )

            print(
                f"Symbol={symbol} | "
                f"Strategy={strategy}"
            )

            if not prepared.get(
                "success"
            ):

                result = {
                    "success":
                        False,
                    "research_family":
                        "SCALPING",
                    "symbol":
                        symbol,
                    "strategy":
                        strategy,
                    "status":
                        prepared.get(
                            "status",
                            "DATA_ERROR",
                        ),
                    "validated":
                        False,
                    "research_score":
                        0.0,
                    "error":
                        prepared.get(
                            "error",
                            "Unknown error.",
                        ),
                }

            else:

                result = (
                    run_cell(
                        symbol,
                        strategy,
                        prepared[
                            "frame"
                        ],
                        prepared[
                            "quality"
                        ],
                    )
                )

            oos = result.get(
                "oos",
                {}
            )

            signal_diag = result.get(
                "oos_signal_diagnostics",
                {}
            )

            trade_diag = result.get(
                "oos_trade_diagnostics",
                {}
            )

            params = result.get(
                "selected_parameters",
                {}
            )

            print(
                f"  Status="
                f"{result.get('status')}"
            )

            if params:

                print(
                    f"  Selected: "
                    f"SL="
                    f"{safe_float(params.get('stop_atr')):.2f} ATR | "
                    f"TP="
                    f"{safe_float(params.get('target_atr')):.2f} ATR | "
                    f"R/R="
                    f"{safe_float(params.get('reward_risk')):.2f}"
                )

            print(
                f"  OOS Signals="
                f"{signal_diag.get('signals', 0)} | "
                f"Raw candidates="
                f"{signal_diag.get('raw_candidates', 0)} | "
                f"OOS trades="
                f"{oos.get('trades', 0)}"
            )

            print(
                "  Signal rejects: "
                f"context="
                f"{signal_diag.get('context_rejections', 0)} | "
                f"momentum="
                f"{signal_diag.get('momentum_rejections', 0)} | "
                f"volume="
                f"{signal_diag.get('volume_rejections', 0)} | "
                f"distance="
                f"{signal_diag.get('distance_rejections', 0)} | "
                f"ORB="
                f"{signal_diag.get('orb_rejections', 0)}"
            )

            print(
                "  Trade rejects: "
                f"invalid_price="
                f"{trade_diag.get('invalid_price', 0)} | "
                f"invalid_ATR="
                f"{trade_diag.get('invalid_atr', 0)} | "
                f"RR="
                f"{trade_diag.get('rr_rejection', 0)} | "
                f"size_zero="
                f"{trade_diag.get('position_size_zero', 0)} | "
                f"created="
                f"{trade_diag.get('trade_created', 0)}"
            )

            print(
                f"  OOS P&L="
                f"Rs {safe_float(oos.get('net_pnl')):.2f} | "
                f"Return="
                f"{safe_float(oos.get('return_percent')):.3f}% | "
                f"PF="
                f"{safe_float(oos.get('profit_factor')):.2f} | "
                f"AvgR="
                f"{safe_float(oos.get('average_r')):.3f}"
            )

            print(
                f"  Score="
                f"{safe_float(result.get('research_score')):.2f} | "
                f"Validated="
                f"{result.get('validated', False)}"
            )

            for failure in result.get(
                "validation_failures",
                [],
            ):

                print(
                    f"  WARNING: "
                    f"{failure}"
                )

            results.append(
                result
            )

    validated = [
        result
        for result in results
        if result.get(
            "validated"
        )
    ]

    def rank_key(
        item: Dict[str, Any]
    ):

        status_rank = {
            "VALIDATED":
                3,
            "UNVALIDATED":
                2,
            "NOT_TESTABLE":
                1,
        }.get(
            item.get(
                "status",
                ""
            ),
            0,
        )

        return (
            status_rank,
            safe_float(
                item.get(
                    "research_score",
                    0.0,
                )
            ),
        )

    ranked = sorted(
        results,
        key=rank_key,
        reverse=True,
    )

    report = {
        "engine":
            "JARVIS_SCALPING_RESEARCH_ENGINE",
        "version":
            "V8",
        "generated_at":
            pd.Timestamp.now(
                tz="Asia/Kolkata"
            ).isoformat(),
        "mode":
            "HISTORICAL_RESEARCH_ONLY",
        "symbols":
            SYMBOLS,
        "strategies":
            STRATEGIES,
        "timeframe":
            TIMEFRAME,
        "context_timeframe":
            CONTEXT_TIMEFRAME,
        "requested_bars":
            REQUESTED_BARS,
        "minimum_reward_risk":
            MIN_REWARD_RISK,
        "data_downloads":
            len(
                SYMBOLS
            ),
        "research_cells":
            len(
                results
            ),
        "validated_count":
            len(
                validated
            ),
        "validated":
            validated,
        "top_results":
            ranked,
        "configuration":
            {
                "train_fraction":
                    TRAIN_FRACTION,
                "validation_fraction":
                    VALIDATION_FRACTION,
                "oos_fraction":
                    OOS_FRACTION,
                "min_total_bars":
                    MIN_TOTAL_BARS,
                "min_oos_trades":
                    MIN_OOS_TRADES,
                "min_profit_factor":
                    MIN_PROFIT_FACTOR,
                "min_oos_return_percent":
                    MIN_OOS_RETURN_PERCENT,
                "min_average_r":
                    MIN_AVERAGE_R,
                "max_drawdown_percent":
                    MAX_DRAWDOWN_PERCENT,
            },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    LATEST_FILE.write_text(
        json.dumps(
            report,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return report


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print(
        "=" * 60
    )

    print(
        "JARVIS SCALPING RESEARCH ENGINE V8"
    )

    print(
        "=" * 60
    )

    print(
        "15m = CONTEXT"
    )

    print(
        "5m = SETUP / TRIGGER"
    )

    print(
        "Historical research only"
    )

    print(
        "NO LIVE ORDER"
    )

    print(
        "NO PAPER ORDER"
    )

    print(
        f"Requested bars: "
        f"{REQUESTED_BARS}"
    )

    print(
        f"Minimum R/R: "
        f"{MIN_REWARD_RISK:.2f}"
    )

    print(
        "Historical source: "
        "UPSTOX_HISTORICAL_V3_CHUNKED"
    )

    print(
        "Data cache: ENABLED"
    )

    print(
        "Early-stop historical loader: ENABLED"
    )

    print(
        "Signal diagnostics: ENABLED"
    )

    print(
        "Trade diagnostics: ENABLED"
    )

    print(
        "Walk-forward: ENABLED"
    )

    print(
        "Robustness: ENABLED"
    )

    report = run_matrix()

    print()
    print(
        "=" * 60
    )

    print(
        "JARVIS SCALPING RESEARCH RESULTS V8"
    )

    print(
        "=" * 60
    )

    print(
        f"Data downloads: "
        f"{report['data_downloads']}"
    )

    print(
        f"Research cells: "
        f"{report['research_cells']}"
    )

    print(
        f"Validated: "
        f"{report['validated_count']}"
    )

    print()

    for number, item in enumerate(
        report[
            "top_results"
        ],
        start=1,
    ):

        oos = item.get(
            "oos",
            {}
        )

        print(
            f"{number}. "
            f"{item.get('strategy')} | "
            f"{item.get('symbol')} | "
            f"Status="
            f"{item.get('status')} | "
            f"Score="
            f"{safe_float(item.get('research_score')):.2f} | "
            f"OOS Rs="
            f"{safe_float(oos.get('net_pnl')):.2f} | "
            f"PF="
            f"{safe_float(oos.get('profit_factor')):.2f} | "
            f"Trades="
            f"{oos.get('trades', 0)}"
        )

    print()
    print(
        "Research file:"
    )

    print(
        LATEST_FILE
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This is historical research only."
    )

    print(
        "No paper or live order is generated."
    )

    print(
        "NOT_TESTABLE means there are zero "
        "OOS trades."
    )

    print(
        "UNVALIDATED means trades exist but "
        "all validation gates are not passed."
    )

    print(
        "VALIDATED requires all validation gates."
    )

    print()
    print(
        "Scalping Research Engine V8 "
        "loaded successfully."
    )


if __name__ == "__main__":

    main()# ============================================================
# JARVIS SCALPING RESEARCH ENGINE
# V8
# ============================================================
#
# RESEARCH ONLY
#
# DATA:
#   Upstox Historical V3
#   agents.upstox_historical_loader
#
# TIMEFRAMES:
#   15m = CONTEXT
#   5m  = SETUP / TRIGGER
#
# SYMBOLS:
#   NIFTY
#   BANKNIFTY
#
# STRATEGIES:
#   VWAP_REVERSION
#   ORB_BREAKOUT
#   MOMENTUM_CONTINUATION
#   MEAN_REVERSION
#
# V8:
#   - 10,000 x 5m requested bars
#   - Symbol data downloaded once
#   - In-memory research cache
#   - Valid R/R parameter universe only
#   - Signal diagnostics
#   - Trade diagnostics
#   - Train / validation / OOS
#   - Walk-forward
#   - Parameter robustness
#   - Slippage
#   - Transaction cost
#   - Rupee P&L
#   - R-multiple
#   - NOT_TESTABLE state
#
# NO LIVE EXECUTION
# NO PAPER EXECUTION
#
# ============================================================


