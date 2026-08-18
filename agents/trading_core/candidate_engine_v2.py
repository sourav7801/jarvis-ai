
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import math
import pandas as pd


MIN_RR = 1.20
ATR_PERIOD = 14


@dataclass
class Candidate:
    symbol: str
    strategy: str
    direction: str
    entry: float
    stop: float
    target: float
    rr: float
    score: float
    reasons: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def atr(frame: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    if frame is None or len(frame) < period + 1:
        return 0.0

    high = frame["High"].astype(float)
    low = frame["Low"].astype(float)
    close = frame["Close"].astype(float)

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    value = float(tr.rolling(period).mean().iloc[-1])

    return value if math.isfinite(value) else 0.0


def _last_swing(frame: pd.DataFrame, lookback: int = 8) -> dict[str, float]:
    recent = frame.tail(lookback)

    return {
        "high": float(recent["High"].max()),
        "low": float(recent["Low"].min()),
    }


def _structure_flags(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or len(frame) < 12:
        return {
            "bos_bullish": False,
            "bos_bearish": False,
            "sweep_low": False,
            "sweep_high": False,
        }

    recent = frame.tail(12)
    prev = frame.iloc[-2]
    last = frame.iloc[-1]

    prior_high = float(recent.iloc[:-2]["High"].max())
    prior_low = float(recent.iloc[:-2]["Low"].min())

    bos_bullish = float(last["Close"]) > prior_high
    bos_bearish = float(last["Close"]) < prior_low

    sweep_low = (
        float(last["Low"]) < prior_low
        and float(last["Close"]) > prior_low
    )

    sweep_high = (
        float(last["High"]) > prior_high
        and float(last["Close"]) < prior_high
    )

    return {
        "bos_bullish": bool(bos_bullish),
        "bos_bearish": bool(bos_bearish),
        "sweep_low": bool(sweep_low),
        "sweep_high": bool(sweep_high),
        "prior_high": prior_high,
        "prior_low": prior_low,
    }


def generate_candidate(
    symbol: str,
    frame_15m: pd.DataFrame,
    frame_5m: pd.DataFrame,
    direction_15m: str | None,
    direction_5m: str | None,
    momentum_5m: float | None,
) -> dict[str, Any]:
    """
    Conservative candidate generator.

    It does not decide whether a trade is authorized.
    It only answers:
       "Is there enough structure to create a candidate worth sending
        through the research/options/risk gates?"
    """

    diagnostics: dict[str, Any] = {
        "context_present": bool(
            frame_15m is not None and not frame_15m.empty
        ),
        "trigger_present": bool(
            frame_5m is not None and not frame_5m.empty
        ),
        "context_trigger_aligned": False,
        "momentum_ok": False,
        "structure_ok": False,
        "price_ok": False,
        "rr_ok": False,
        "atr": 0.0,
        "entry": None,
        "stop": None,
        "target": None,
        "rr": None,
        "missing": [],
    }

    reasons: list[str] = []

    if not diagnostics["context_present"]:
        diagnostics["missing"].append("15m context data unavailable.")

    if not diagnostics["trigger_present"]:
        diagnostics["missing"].append("5m trigger data unavailable.")

    if diagnostics["missing"]:
        return {
            "candidate": None,
            "diagnostics": diagnostics,
            "reason": "Required timeframe data is unavailable.",
        }

    if (
        direction_15m
        and direction_5m
        and direction_15m == direction_5m
        and direction_15m in {"BULLISH", "BEARISH"}
    ):
        diagnostics["context_trigger_aligned"] = True
        reasons.append(
            f"15m and 5m aligned {direction_15m}."
        )
    else:
        diagnostics["missing"].append(
            "15m context and 5m trigger are not aligned."
        )

    if momentum_5m is not None:
        if (
            direction_5m == "BULLISH"
            and float(momentum_5m) >= 55
        ) or (
            direction_5m == "BEARISH"
            and float(momentum_5m) <= 45
        ):
            diagnostics["momentum_ok"] = True
            reasons.append(
                f"5m momentum supports {direction_5m}."
            )
        else:
            diagnostics["missing"].append(
                "5m momentum does not confirm direction."
            )

    atr_value = atr(frame_5m)
    diagnostics["atr"] = atr_value

    if atr_value <= 0:
        diagnostics["missing"].append(
            "ATR is unavailable or zero."
        )

    structure = _structure_flags(frame_5m)

    structure_ok = (
        direction_5m == "BULLISH"
        and (
            structure["bos_bullish"]
            or structure["sweep_low"]
        )
    ) or (
        direction_5m == "BEARISH"
        and (
            structure["bos_bearish"]
            or structure["sweep_high"]
        )
    )

    diagnostics["structure_ok"] = bool(structure_ok)

    if structure_ok:
        reasons.append(
            "5m structure confirms the directional idea."
        )
    else:
        diagnostics["missing"].append(
            "No confirming 5m BOS/liquidity-sweep structure."
        )

    last_price = float(
        frame_5m["Close"].iloc[-1]
    )

    if not math.isfinite(last_price) or last_price <= 0:
        diagnostics["missing"].append(
            "Last trigger price is invalid."
        )

    # Candidate creation is intentionally conservative.
    if (
        not diagnostics["context_trigger_aligned"]
        or not diagnostics["momentum_ok"]
        or not diagnostics["structure_ok"]
        or atr_value <= 0
        or last_price <= 0
    ):
        return {
            "candidate": None,
            "diagnostics": diagnostics,
            "reason": (
                "Candidate rejected before R/R because one or more "
                "technical confirmation gates failed."
            ),
        }

    swing = _last_swing(
        frame_5m,
        8,
    )

    if direction_5m == "BULLISH":
        entry = last_price
        stop = min(
            swing["low"],
            entry - 1.0 * atr_value,
        )
        risk = entry - stop

        # First structural target. If too close, extend to 1.8R.
        target = max(
            swing["high"],
            entry + 1.8 * risk,
        )

        strategy = (
            "MOMENTUM_CONTINUATION"
            if structure["bos_bullish"]
            else "LIQUIDITY_SWEEP_RECLAIM"
        )

    else:
        entry = last_price
        stop = max(
            swing["high"],
            entry + 1.0 * atr_value,
        )
        risk = stop - entry

        target = min(
            swing["low"],
            entry - 1.8 * risk,
        )

        strategy = (
            "MOMENTUM_CONTINUATION"
            if structure["bos_bearish"]
            else "LIQUIDITY_SWEEP_RECLAIM"
        )

    if risk <= 0:
        diagnostics["missing"].append(
            "Computed risk distance is not positive."
        )
        return {
            "candidate": None,
            "diagnostics": diagnostics,
            "reason": "Invalid computed risk distance.",
        }

    if direction_5m == "BULLISH":
        reward = target - entry
    else:
        reward = entry - target

    rr = reward / risk if risk > 0 else 0.0

    diagnostics["entry"] = entry
    diagnostics["stop"] = stop
    diagnostics["target"] = target
    diagnostics["rr"] = rr

    if rr < MIN_RR:
        diagnostics["missing"].append(
            f"Computed R/R {rr:.2f} is below minimum {MIN_RR:.2f}."
        )
        return {
            "candidate": None,
            "diagnostics": diagnostics,
            "reason": "Minimum reward/risk gate failed.",
        }

    diagnostics["rr_ok"] = True

    score = 0.0
    if diagnostics["context_trigger_aligned"]:
        score += 30
    if diagnostics["momentum_ok"]:
        score += 20
    if diagnostics["structure_ok"]:
        score += 25
    if diagnostics["rr_ok"]:
        score += 25

    candidate = Candidate(
        symbol=symbol,
        strategy=strategy,
        direction=direction_5m,
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        rr=round(rr, 2),
        score=round(score, 2),
        reasons=reasons,
        diagnostics=diagnostics,
    )

    return {
        "candidate": candidate.to_dict(),
        "diagnostics": diagnostics,
        "reason": "Candidate created; authorization gates still apply.",
    }
