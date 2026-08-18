
from __future__ import annotations

import pandas as pd


def detect_structure(df: pd.DataFrame, lookback: int = 20) -> dict:
    if df is None or len(df) < max(lookback, 10):
        return {
            "state": "UNKNOWN",
            "bos": False,
            "choch": False,
            "swing_high": None,
            "swing_low": None,
            "reasons": ["Insufficient bars for structure analysis."],
        }

    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    swing_high = float(high.tail(lookback).max())
    swing_low = float(low.tail(lookback).min())
    last = float(close.iloc[-1])

    prev_window = df.iloc[-lookback-1:-1] if len(df) > lookback else df.iloc[:-1]
    prev_high = float(prev_window["High"].max())
    prev_low = float(prev_window["Low"].min())

    bos_up = last > prev_high
    bos_down = last < prev_low

    # Conservative CHOCH proxy: a break in the opposite direction after
    # a short directional run.
    recent = close.tail(8)
    slope_up = recent.iloc[-1] > recent.iloc[0]
    slope_down = recent.iloc[-1] < recent.iloc[0]
    choch_down = slope_up and bos_down
    choch_up = slope_down and bos_up

    if bos_up:
        state = "BULLISH_BOS"
    elif bos_down:
        state = "BEARISH_BOS"
    elif choch_up:
        state = "BULLISH_CHOCH"
    elif choch_down:
        state = "BEARISH_CHOCH"
    elif last > close.rolling(10).mean().iloc[-1]:
        state = "HIGHER_STRUCTURE"
    elif last < close.rolling(10).mean().iloc[-1]:
        state = "LOWER_STRUCTURE"
    else:
        state = "RANGE"

    return {
        "state": state,
        "bos": bool(bos_up or bos_down),
        "choch": bool(choch_up or choch_down),
        "swing_high": swing_high,
        "swing_low": swing_low,
        "reasons": [
            f"Swing high={swing_high:.2f}.",
            f"Swing low={swing_low:.2f}.",
            f"Structure={state}.",
        ],
    }
