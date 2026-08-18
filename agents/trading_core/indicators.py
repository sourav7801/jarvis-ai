
from __future__ import annotations

import numpy as np
import pandas as pd


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in df.columns:
            df[col] = 0.0
    df = df.sort_index()

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA200"] = close.ewm(span=200, adjust=False).mean()

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR14"] = tr.rolling(14, min_periods=3).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=3).mean()
    loss = -delta.clip(upper=0).rolling(14, min_periods=3).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))

    typical = (high + low + close) / 3
    vol = df["Volume"].astype(float)
    if vol.fillna(0).sum() > 0:
        df["VWAP"] = (typical * vol).cumsum() / vol.replace(0, np.nan).cumsum()
    else:
        # Index feeds commonly have zero volume; keep a session-like proxy
        # from typical price so the analysis layer has a deterministic value.
        df["VWAP"] = typical.expanding(min_periods=1).mean()

    return df
