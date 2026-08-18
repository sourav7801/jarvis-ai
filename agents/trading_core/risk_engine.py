
from __future__ import annotations

from math import floor
from .models import Setup


def position_size(
    setup: Setup,
    capital: float,
    risk_per_trade_pct: float = 0.005,
) -> dict:
    if not setup.entry or not setup.stop:
        return {"qty": 0, "risk_cash": 0.0, "risk_per_unit": 0.0}

    risk_cash = max(0.0, capital * risk_per_trade_pct)
    risk_per_unit = abs(setup.entry - setup.stop)
    qty = floor(risk_cash / max(risk_per_unit, 1e-9))

    return {
        "qty": int(max(0, qty)),
        "risk_cash": round(risk_cash, 2),
        "risk_per_unit": round(risk_per_unit, 4),
    }
