
from __future__ import annotations

from typing import List
import pandas as pd

from .indicators import prepare
from .models import Regime


def analyze(symbol: str, frame: pd.DataFrame) -> Regime:
    if frame is None or frame.empty or len(frame) < 30:
        return Regime(
            symbol=symbol,
            reasons=["Insufficient bars for analysis."],
        )

    df = prepare(frame)
    last = df.iloc[-1]

    close = float(last["Close"])
    ema20 = float(last["EMA20"])
    ema50 = float(last["EMA50"])
    vwap = float(last["VWAP"])
    rsi = float(last["RSI14"]) if pd.notna(last["RSI14"]) else 50.0
    atr = float(last["ATR14"]) if pd.notna(last["ATR14"]) else 0.0

    score = 50.0
    reasons: List[str] = []

    if close > vwap:
        score += 10
        reasons.append("Price above VWAP.")
    else:
        score -= 10
        reasons.append("Price below VWAP.")

    if ema20 > ema50:
        score += 10
        reasons.append("EMA20 above EMA50.")
    else:
        score -= 10
        reasons.append("EMA20 below EMA50.")

    if rsi >= 60:
        score += 10
        reasons.append("Momentum RSI >= 60.")
    elif rsi <= 40:
        score -= 10
        reasons.append("Momentum RSI <= 40.")

    vol_score = min(10.0, max(-10.0, (atr / max(close, 1e-9)) * 10000))
    score += 0 if abs(vol_score) < 1 else (5 if vol_score > 0 else -5)

    score = max(0, min(100, score))

    if score >= 65:
        direction = "BULLISH"
    elif score <= 35:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    if atr / max(close, 1e-9) > 0.004:
        regime = "HIGH_VOLATILITY"
    elif abs(close - vwap) / max(close, 1e-9) < 0.001:
        regime = "MEAN_REVERTING"
    else:
        regime = "TRENDING"

    return Regime(
        symbol=symbol,
        direction=direction,
        regime=regime,
        momentum_score=round(score, 2),
        volatility_score=round((atr / max(close, 1e-9)) * 100, 4),
        vwap_state="ABOVE" if close >= vwap else "BELOW",
        ema_state="BULLISH" if ema20 >= ema50 else "BEARISH",
        structure_state=direction,
        confidence=round(abs(score - 50) * 2, 2),
        reasons=reasons,
    )
