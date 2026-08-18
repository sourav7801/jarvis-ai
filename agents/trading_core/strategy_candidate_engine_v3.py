
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math
import pandas as pd


MIN_RR = 1.20


@dataclass
class StrategyCandidate:
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop: float
    target: float
    rr: float
    score: float
    setup_quality: str
    reasons: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atr(frame: pd.DataFrame, period: int = 14) -> float:
    if frame is None or len(frame) < period + 1:
        return 0.0
    h = frame["High"].astype(float)
    l = frame["Low"].astype(float)
    c = frame["Close"].astype(float)
    pc = c.shift(1)
    tr = pd.concat(
        [
            h - l,
            (h - pc).abs(),
            (l - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)
    v = float(tr.rolling(period).mean().iloc[-1])
    return v if math.isfinite(v) else 0.0


def _vwap(frame: pd.DataFrame) -> float:
    if frame is None or frame.empty:
        return 0.0
    vol = frame["Volume"].astype(float)
    if float(vol.sum()) <= 0:
        return float(frame["Close"].mean())
    tp = (frame["High"] + frame["Low"] + frame["Close"]) / 3.0
    return float((tp * vol).sum() / vol.sum())


def _ema(frame: pd.DataFrame, period: int) -> pd.Series:
    return frame["Close"].astype(float).ewm(span=period, adjust=False).mean()


def _rsi(frame: pd.DataFrame, period: int = 14) -> float:
    delta = frame["Close"].astype(float).diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.rolling(period).mean()
    avg_down = down.rolling(period).mean()
    rs = avg_up / avg_down.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    value = rsi.iloc[-1]
    return float(value) if pd.notna(value) else 50.0


def _swing(frame: pd.DataFrame, lookback: int = 8) -> tuple[float, float]:
    x = frame.tail(lookback)
    return float(x["High"].max()), float(x["Low"].min())


def _structure(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or len(frame) < 12:
        return {}
    x = frame.tail(12)
    prior = x.iloc[:-2]
    last = x.iloc[-1]
    ph = float(prior["High"].max())
    pl = float(prior["Low"].min())
    return {
        "prior_high": ph,
        "prior_low": pl,
        "bos_bullish": float(last["Close"]) > ph,
        "bos_bearish": float(last["Close"]) < pl,
        "sweep_low_reclaim": (
            float(last["Low"]) < pl and float(last["Close"]) > pl
        ),
        "sweep_high_reject": (
            float(last["High"]) > ph and float(last["Close"]) < ph
        ),
    }


def _make_candidate(
    symbol: str,
    strategy: str,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    score: float,
    reasons: list[str],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    risk = abs(entry - stop)
    reward = (
        target - entry
        if direction == "BULLISH"
        else entry - target
    )
    rr = reward / risk if risk > 0 else 0.0
    diagnostics["entry"] = entry
    diagnostics["stop"] = stop
    diagnostics["target"] = target
    diagnostics["rr"] = rr

    if risk <= 0 or reward <= 0 or rr < MIN_RR:
        diagnostics.setdefault("rejections", []).append(
            f"R/R {rr:.2f} below minimum {MIN_RR:.2f} or invalid reward/risk."
        )
        return {
            "candidate": None,
            "diagnostics": diagnostics,
            "reason": "Risk/reward gate failed.",
        }

    quality = (
        "A"
        if score >= 80
        else "B"
        if score >= 65
        else "C"
    )

    candidate = StrategyCandidate(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        rr=round(rr, 2),
        score=round(score, 2),
        setup_quality=quality,
        reasons=reasons,
        diagnostics=diagnostics,
    )

    return {
        "candidate": candidate.to_dict(),
        "diagnostics": diagnostics,
        "reason": "Strategy-specific candidate created.",
    }


def generate_strategy_candidates(
    symbol: str,
    frame_15m: pd.DataFrame,
    frame_5m: pd.DataFrame,
    direction_15m: str | None,
    direction_5m: str | None,
    momentum_5m: float | None,
) -> list[dict[str, Any]]:
    """
    Strategy matrix:
      - VWAP_REVERSION
      - ORB_BREAKOUT
      - MOMENTUM_CONTINUATION
      - MEAN_REVERSION
      - LIQUIDITY_SWEEP_RECLAIM

    This creates candidates only. It never authorizes execution.
    """
    if frame_5m is None or frame_5m.empty:
        return []

    close = float(frame_5m["Close"].iloc[-1])
    vwap = _vwap(frame_5m)
    ema20 = float(_ema(frame_5m, 20).iloc[-1])
    ema50 = float(_ema(frame_5m, 50).iloc[-1])
    rsi = _rsi(frame_5m)
    atr = _atr(frame_5m)
    swing_high, swing_low = _swing(frame_5m)
    st = _structure(frame_5m)

    if atr <= 0 or close <= 0:
        return []

    out = []

    aligned = (
        direction_15m == direction_5m
        and direction_5m in {"BULLISH", "BEARISH"}
    )

    # --------------------------------------------------------
    # MOMENTUM_CONTINUATION
    # --------------------------------------------------------
    momentum_ok = (
        (direction_5m == "BULLISH" and (momentum_5m or 50) >= 60)
        or
        (direction_5m == "BEARISH" and (momentum_5m or 50) <= 40)
    )
    bos_ok = (
        (direction_5m == "BULLISH" and st.get("bos_bullish"))
        or
        (direction_5m == "BEARISH" and st.get("bos_bearish"))
    )

    if aligned and momentum_ok and bos_ok:
        if direction_5m == "BULLISH":
            entry = close
            stop = min(swing_low, entry - atr)
            target = entry + 1.8 * (entry - stop)
        else:
            entry = close
            stop = max(swing_high, entry + atr)
            target = entry - 1.8 * (stop - entry)

        score = 60 + (10 if momentum_ok else 0) + (10 if bos_ok else 0) + (10 if abs(close-vwap) > 0 else 0)
        out.append(_make_candidate(
            symbol,
            "MOMENTUM_CONTINUATION",
            direction_5m,
            entry,
            stop,
            target,
            min(score, 100),
            [
                "15m/5m aligned.",
                "Momentum confirms direction.",
                "Break of structure confirmed.",
            ],
            {
                "vwap": vwap,
                "ema20": ema20,
                "ema50": ema50,
                "rsi": rsi,
                "atr": atr,
                "structure": st,
            },
        ))

    # --------------------------------------------------------
    # VWAP_REVERSION
    # --------------------------------------------------------
    stretched = abs(close - vwap) >= 0.60 * atr
    reversal = (
        (close > vwap and rsi >= 65)
        or
        (close < vwap and rsi <= 35)
    )

    if stretched and reversal:
        if close > vwap:
            direction = "BEARISH"
            entry = close
            stop = max(swing_high, entry + 0.9 * atr)
            target = min(vwap, entry - 1.5 * (stop - entry))
        else:
            direction = "BULLISH"
            entry = close
            stop = min(swing_low, entry - 0.9 * atr)
            target = max(vwap, entry + 1.5 * (entry - stop))

        out.append(_make_candidate(
            symbol,
            "VWAP_REVERSION",
            direction,
            entry,
            stop,
            target,
            68,
            [
                "Price is stretched from VWAP.",
                "RSI confirms exhaustion.",
                "Target returns toward VWAP.",
            ],
            {
                "vwap": vwap,
                "rsi": rsi,
                "atr": atr,
            },
        ))

    # --------------------------------------------------------
    # MEAN_REVERSION
    # --------------------------------------------------------
    extreme = (
        rsi <= 30 or rsi >= 70
    )
    if extreme and not aligned:
        if rsi <= 30:
            direction = "BULLISH"
            entry = close
            stop = min(swing_low, entry - atr)
            target = entry + 1.5 * (entry - stop)
        else:
            direction = "BEARISH"
            entry = close
            stop = max(swing_high, entry + atr)
            target = entry - 1.5 * (stop - entry)

        out.append(_make_candidate(
            symbol,
            "MEAN_REVERSION",
            direction,
            entry,
            stop,
            target,
            60,
            [
                "RSI is at an extreme.",
                "15m/5m are not strongly aligned.",
                "Mean-reversion target uses ATR-defined risk.",
            ],
            {
                "rsi": rsi,
                "atr": atr,
            },
        ))

    # --------------------------------------------------------
    # LIQUIDITY_SWEEP_RECLAIM
    # --------------------------------------------------------
    if st.get("sweep_low_reclaim"):
        entry = close
        stop = min(swing_low, entry - 0.8 * atr)
        target = entry + 1.6 * (entry - stop)
        out.append(_make_candidate(
            symbol,
            "LIQUIDITY_SWEEP_RECLAIM",
            "BULLISH",
            entry,
            stop,
            target,
            72,
            [
                "Low liquidity sweep detected.",
                "Close reclaimed prior low.",
            ],
            {
                "atr": atr,
                "structure": st,
            },
        ))

    if st.get("sweep_high_reject"):
        entry = close
        stop = max(swing_high, entry + 0.8 * atr)
        target = entry - 1.6 * (stop - entry)
        out.append(_make_candidate(
            symbol,
            "LIQUIDITY_SWEEP_RECLAIM",
            "BEARISH",
            entry,
            stop,
            target,
            72,
            [
                "High liquidity sweep detected.",
                "Close rejected prior high.",
            ],
            {
                "atr": atr,
                "structure": st,
            },
        ))

    # --------------------------------------------------------
    # ORB_BREAKOUT
    # --------------------------------------------------------
    # Approximation using first 6 five-minute bars of the current session.
    if len(frame_5m) >= 30:
        day = frame_5m.index[-1].date()
        today = frame_5m[frame_5m.index.date == day]
        if len(today) >= 6:
            orb = today.iloc[:6]
            orb_high = float(orb["High"].max())
            orb_low = float(orb["Low"].min())

            if close > orb_high and direction_5m == "BULLISH":
                entry = close
                stop = min(orb_high, entry - atr)
                target = entry + 1.8 * (entry - stop)
                out.append(_make_candidate(
                    symbol,
                    "ORB_BREAKOUT",
                    "BULLISH",
                    entry,
                    stop,
                    target,
                    65,
                    [
                        "Price broke above opening range.",
                        "5m direction is bullish.",
                    ],
                    {
                        "orb_high": orb_high,
                        "orb_low": orb_low,
                        "atr": atr,
                    },
                ))

            if close < orb_low and direction_5m == "BEARISH":
                entry = close
                stop = max(orb_low, entry + atr)
                target = entry - 1.8 * (stop - entry)
                out.append(_make_candidate(
                    symbol,
                    "ORB_BREAKOUT",
                    "BEARISH",
                    entry,
                    stop,
                    target,
                    65,
                    [
                        "Price broke below opening range.",
                        "5m direction is bearish.",
                    ],
                    {
                        "orb_high": orb_high,
                        "orb_low": orb_low,
                        "atr": atr,
                    },
                ))

    return [
        x for x in out
        if x.get("candidate") is not None
    ]
