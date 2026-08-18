
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

try:
    from agents.market_regime_engine import workstation_regime
except Exception:
    workstation_regime = None


def market_policy(
    now: datetime | None = None,
    nifty_momentum: float = 50,
    banknifty_momentum: float = 50,
    sensex_momentum: float = 50,
) -> Dict[str, Any]:
    if workstation_regime is not None:
        try:
            return workstation_regime(
                nifty_momentum=nifty_momentum,
                banknifty_momentum=banknifty_momentum,
                sensex_momentum=sensex_momentum,
                now=now,
            )
        except Exception:
            pass

    # Safe fallback, matching the agreed user policy.
    if banknifty_momentum >= 70:
        preferred = "BANKNIFTY"
        priority = ["BANKNIFTY", "NIFTY", "SENSEX"]
    elif nifty_momentum >= 50:
        preferred = "NIFTY"
        priority = ["NIFTY", "SENSEX", "BANKNIFTY"]
    else:
        preferred = "SENSEX"
        priority = ["SENSEX", "NIFTY", "BANKNIFTY"]

    return {
        "preferred_symbol": preferred,
        "priority": priority,
        "reason": "Fallback policy.",
        "snapshots": {},
    }
