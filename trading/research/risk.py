"""Portfolio exposure firewall and sticky simulation kill switch."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class RiskLimits:
    max_gross_exposure_pct: float = 50.0
    max_net_exposure_pct: float = 30.0
    max_symbol_exposure_pct: float = 20.0
    max_open_positions: int = 10
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0

    def __post_init__(self) -> None:
        percentages = (
            self.max_gross_exposure_pct,
            self.max_net_exposure_pct,
            self.max_symbol_exposure_pct,
            self.max_daily_loss_pct,
            self.max_drawdown_pct,
        )
        if any(value <= 0 or value > 100 for value in percentages):
            raise ValueError("Risk percentages must be in the range (0, 100].")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be positive.")


class PortfolioGuard:
    def __init__(self, starting_equity: float, limits: RiskLimits | None = None):
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive.")
        self.starting_equity = float(starting_equity)
        self.peak_equity = float(starting_equity)
        self.day_start_equity = float(starting_equity)
        self.limits = limits or RiskLimits()
        self.halted = False
        self.halt_reason: str | None = None

    def update_equity(self, equity: float) -> bool:
        equity = float(equity)
        self.peak_equity = max(self.peak_equity, equity)
        daily_loss = 100 * (self.day_start_equity - equity) / self.day_start_equity
        drawdown = 100 * (self.peak_equity - equity) / self.peak_equity
        if daily_loss >= self.limits.max_daily_loss_pct:
            self._halt("MAX_DAILY_LOSS")
        if drawdown >= self.limits.max_drawdown_pct:
            self._halt("MAX_DRAWDOWN")
        return not self.halted

    def evaluate_positions(
        self,
        positions: Mapping[str, float],
        prices: Mapping[str, float],
        equity: float,
    ) -> dict:
        if self.halted:
            return {"allowed": False, "reason": self.halt_reason}
        if equity <= 0:
            self._halt("NON_POSITIVE_EQUITY")
            return {"allowed": False, "reason": self.halt_reason}

        missing_prices = [
            symbol
            for symbol, quantity in positions.items()
            if quantity and symbol not in prices
        ]
        if missing_prices:
            return {
                "allowed": False,
                "reason": "MISSING_PRICE",
                "missing_symbols": sorted(missing_prices),
            }
        if not math.isfinite(float(equity)) or any(
            not math.isfinite(float(price)) or float(price) <= 0
            for price in prices.values()
        ) or any(
            not math.isfinite(float(quantity))
            for quantity in positions.values()
        ):
            return {"allowed": False, "reason": "INVALID_NUMERIC_INPUT"}

        notionals = {
            symbol: float(quantity) * float(prices[symbol])
            for symbol, quantity in positions.items()
            if quantity and symbol in prices
        }
        active = len(notionals)
        gross = sum(abs(value) for value in notionals.values())
        net = abs(sum(notionals.values()))
        gross_pct = 100 * gross / equity
        net_pct = 100 * net / equity
        largest_pct = max((100 * abs(value) / equity for value in notionals.values()), default=0.0)

        reason = None
        if active > self.limits.max_open_positions:
            reason = "MAX_OPEN_POSITIONS"
        elif gross_pct > self.limits.max_gross_exposure_pct:
            reason = "MAX_GROSS_EXPOSURE"
        elif net_pct > self.limits.max_net_exposure_pct:
            reason = "MAX_NET_EXPOSURE"
        elif largest_pct > self.limits.max_symbol_exposure_pct:
            reason = "MAX_SYMBOL_EXPOSURE"

        return {
            "allowed": reason is None,
            "reason": reason,
            "gross_exposure_pct": gross_pct,
            "net_exposure_pct": net_pct,
            "largest_symbol_exposure_pct": largest_pct,
            "open_positions": active,
        }

    def reset_for_new_day(self, equity: float, explicit: bool = False) -> None:
        if not explicit:
            raise PermissionError("Kill-switch reset requires explicit=True.")
        if equity <= 0:
            raise ValueError("equity must be positive.")
        self.day_start_equity = float(equity)
        self.peak_equity = max(self.peak_equity, float(equity))
        self.halted = False
        self.halt_reason = None

    def _halt(self, reason: str) -> None:
        if not self.halted:
            self.halted = True
            self.halt_reason = reason
