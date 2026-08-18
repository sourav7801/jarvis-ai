
from __future__ import annotations

from typing import Any, Dict

from .market_structure import detect_structure
from .pattern_engine import detect_fvg, detect_liquidity, detect_orb, volume_anomaly


def score_signal(
    context_regime: dict,
    trigger_regime: dict,
    structure_15m: dict,
    structure_5m: dict,
    orb: dict,
    fvg: dict,
    liquidity: dict,
    volume: dict,
) -> Dict[str, Any]:
    score = 0.0
    reasons = []

    # Context/trigger alignment.
    if context_regime.get("direction") == trigger_regime.get("direction") and \
       context_regime.get("direction") in {"BULLISH", "BEARISH"}:
        score += 25
        reasons.append("15m and 5m direction agree.")
    else:
        reasons.append("15m and 5m direction do not fully agree.")

    # Momentum.
    trigger_momentum = float(trigger_regime.get("momentum_score", 50))
    if trigger_momentum >= 65 or trigger_momentum <= 35:
        score += 15
        reasons.append("5m momentum is decisive.")
    elif trigger_momentum >= 55 or trigger_momentum <= 45:
        score += 7
        reasons.append("5m momentum is moderate.")

    # Structure.
    if structure_5m.get("bos"):
        score += 15
        reasons.append("5m break of structure detected.")
    elif structure_5m.get("choch"):
        score += 10
        reasons.append("5m change of character detected.")

    # ORB.
    if orb.get("status") == "CONFIRMED":
        score += 10
        reasons.append(f"ORB breakout confirmed: {orb.get('breakout')}.")

    # FVG.
    if fvg.get("found"):
        score += 8
        reasons.append(f"Recent {fvg.get('type')} FVG/imbalance detected.")

    # Liquidity.
    if liquidity.get("sweep"):
        score += 10
        reasons.append(f"Liquidity sweep detected: {liquidity.get('type')}.")

    # Volume.
    if volume.get("status") == "HIGH":
        score += 10
        reasons.append("Volume expansion detected.")
    elif volume.get("status") == "ELEVATED":
        score += 5
        reasons.append("Volume is elevated.")

    return {
        "score": round(min(100.0, score), 2),
        "reasons": reasons,
    }


def analyze_trigger_package(
    df_15m,
    df_5m,
    context_regime: dict,
    trigger_regime: dict,
) -> dict:
    s15 = detect_structure(df_15m)
    s5 = detect_structure(df_5m)
    orb = detect_orb(df_5m)
    fvg = detect_fvg(df_5m)
    liq = detect_liquidity(df_5m)
    vol = volume_anomaly(df_5m)

    score = score_signal(
        context_regime,
        trigger_regime,
        s15,
        s5,
        orb,
        fvg,
        liq,
        vol,
    )

    return {
        "score": score["score"],
        "reasons": score["reasons"],
        "structure_15m": s15,
        "structure_5m": s5,
        "orb": orb,
        "fvg": fvg,
        "liquidity": liq,
        "volume": vol,
    }
