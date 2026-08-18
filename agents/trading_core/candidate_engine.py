
from __future__ import annotations

from typing import Any

from .models import Regime, Setup


def confirmation_state(
    context: dict[str, Any],
    setups: list[dict[str, Any]],
    option_state: dict[str, Any],
) -> dict[str, Any]:
    reasons = []

    if not context.get("tradeable"):
        return {
            "ready": False,
            "state": "WAIT",
            "score": 0.0,
            "reasons": ["15m context and 5m trigger are not aligned."],
        }

    trigger = context.get("trigger_regime") or {}
    score = float(trigger.get("confidence", 0.0))

    if not setups:
        return {
            "ready": False,
            "state": "WAIT",
            "score": round(score, 2),
            "reasons": ["No deterministic setup passed the setup filters."],
        }

    setup = setups[0]
    reasons.extend(setup.get("reasons", []))

    if float(setup.get("rr", 0.0)) < 1.2:
        reasons.append("R/R below minimum 1.20.")
        return {
            "ready": False,
            "state": "WAIT",
            "score": round(score, 2),
            "reasons": reasons,
        }

    # Option confirmation is advisory until a compatible option feed is connected.
    if not option_state.get("available"):
        reasons.append("Option confirmation unavailable.")
        return {
            "ready": False,
            "state": "WAIT_OPTION_CONFIRMATION",
            "score": round(score, 2),
            "reasons": reasons,
        }

    reasons.append("Option confirmation source available.")
    score = min(100.0, score + 15.0)

    return {
        "ready": True,
        "state": "PAPER_READY",
        "score": round(score, 2),
        "reasons": reasons,
    }
