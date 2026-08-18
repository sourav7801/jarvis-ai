
from __future__ import annotations

import pandas as pd


def detect_orb(df: pd.DataFrame, minutes: int = 15) -> dict:
    if df is None or df.empty or not hasattr(df.index, "time"):
        return {
            "status": "UNAVAILABLE",
            "high": None,
            "low": None,
            "breakout": None,
            "reasons": ["Opening-range data unavailable."],
        }

    # Assumes intraday bars indexed in local exchange time.
    session = df.between_time("09:15", "09:30")
    if session.empty:
        return {
            "status": "UNAVAILABLE",
            "high": None,
            "low": None,
            "breakout": None,
            "reasons": ["Opening-range bars not present in dataset."],
        }

    orb_high = float(session["High"].max())
    orb_low = float(session["Low"].min())
    last = float(df["Close"].iloc[-1])

    if last > orb_high:
        breakout = "BULLISH"
        status = "CONFIRMED"
    elif last < orb_low:
        breakout = "BEARISH"
        status = "CONFIRMED"
    else:
        breakout = "NONE"
        status = "INSIDE"

    return {
        "status": status,
        "high": orb_high,
        "low": orb_low,
        "breakout": breakout,
        "reasons": [
            f"ORB high={orb_high:.2f}.",
            f"ORB low={orb_low:.2f}.",
        ],
    }


def detect_fvg(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 4:
        return {"found": False, "type": None, "upper": None, "lower": None, "reasons": []}

    a = df.iloc[-3]
    b = df.iloc[-2]
    c = df.iloc[-1]

    # 3-candle imbalance proxy.
    bullish = float(c["Low"]) > float(a["High"])
    bearish = float(c["High"]) < float(a["Low"])

    if bullish:
        return {
            "found": True,
            "type": "BULLISH",
            "upper": float(c["Low"]),
            "lower": float(a["High"]),
            "reasons": ["Recent bullish imbalance detected."],
        }
    if bearish:
        return {
            "found": True,
            "type": "BEARISH",
            "upper": float(a["Low"]),
            "lower": float(c["High"]),
            "reasons": ["Recent bearish imbalance detected."],
        }

    return {"found": False, "type": None, "upper": None, "lower": None, "reasons": []}


def detect_liquidity(df: pd.DataFrame, lookback: int = 20) -> dict:
    if df is None or len(df) < lookback + 2:
        return {
            "sweep": False,
            "type": None,
            "level": None,
            "reasons": ["Insufficient data for liquidity sweep check."],
        }

    prior = df.iloc[-lookback-1:-1]
    last = df.iloc[-1]
    prior_high = float(prior["High"].max())
    prior_low = float(prior["Low"].min())
    last_high = float(last["High"])
    last_low = float(last["Low"])
    last_close = float(last["Close"])

    if last_high > prior_high and last_close < prior_high:
        return {
            "sweep": True,
            "type": "HIGH_SWEEP",
            "level": prior_high,
            "reasons": ["Price swept a prior high and closed back below it."],
        }

    if last_low < prior_low and last_close > prior_low:
        return {
            "sweep": True,
            "type": "LOW_SWEEP",
            "level": prior_low,
            "reasons": ["Price swept a prior low and closed back above it."],
        }

    return {
        "sweep": False,
        "type": None,
        "level": None,
        "reasons": ["No recent liquidity sweep detected."],
    }


def volume_anomaly(df: pd.DataFrame, window: int = 20) -> dict:
    if df is None or "Volume" not in df.columns or len(df) < window + 1:
        return {"status": "UNAVAILABLE", "ratio": 0.0, "reasons": []}

    vol = df["Volume"].astype(float)
    baseline = float(vol.iloc[-window-1:-1].mean())
    latest = float(vol.iloc[-1])

    if baseline <= 0:
        return {
            "status": "NO_VOLUME_FEED",
            "ratio": 0.0,
            "reasons": ["Volume feed is zero/unavailable for this instrument."],
        }

    ratio = latest / baseline
    status = "HIGH" if ratio >= 1.8 else "ELEVATED" if ratio >= 1.3 else "NORMAL"

    return {
        "status": status,
        "ratio": round(ratio, 2),
        "reasons": [f"Latest volume is {ratio:.2f}x baseline."],
    }
