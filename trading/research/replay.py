"""Deterministic next-bar replay with explicit transaction costs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Callable

from .market_data import Candle, MarketDataset
from .risk import PortfolioGuard, RiskLimits


SignalFunction = Callable[[tuple[Candle, ...], int], int]


@dataclass(frozen=True)
class ReplayConfig:
    starting_capital: float = 1_000_000.0
    quantity: float = 1.0
    commission_bps: float = 1.0
    fixed_fee_per_fill: float = 0.0
    slippage_bps: float = 2.0

    def __post_init__(self) -> None:
        numeric = (
            self.starting_capital,
            self.quantity,
            self.commission_bps,
            self.fixed_fee_per_fill,
            self.slippage_bps,
        )
        if any(not math.isfinite(float(value)) for value in numeric):
            raise ValueError("Replay configuration must contain finite numbers.")
        if self.starting_capital <= 0 or self.quantity <= 0:
            raise ValueError("Capital and quantity must be positive.")
        if min(self.commission_bps, self.fixed_fee_per_fill, self.slippage_bps) < 0:
            raise ValueError("Fees and slippage cannot be negative.")


@dataclass(frozen=True)
class ReplayTrade:
    symbol: str
    side: str
    quantity: float
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: float
    exit_price: float
    gross_pnl: float
    fees: float
    net_pnl: float
    exit_reason: str


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    equity: float


@dataclass(frozen=True)
class ReplayResult:
    dataset_checksum: str
    starting_capital: float
    ending_equity: float
    net_pnl: float
    total_fees: float
    maximum_drawdown_pct: float
    trades: tuple[ReplayTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    rejected_signals: int
    halted: bool
    halt_reason: str | None


class ReplayEngine:
    def __init__(
        self,
        config: ReplayConfig | None = None,
        risk_limits: RiskLimits | None = None,
    ):
        self.config = config or ReplayConfig()
        self.risk_limits = risk_limits or RiskLimits()

    def _fill_price(self, price: float, order_side: str) -> float:
        adjustment = float(price) * self.config.slippage_bps / 10_000
        return float(price) + adjustment if order_side == "BUY" else float(price) - adjustment

    def _fee(self, price: float, quantity: float) -> float:
        return (
            abs(float(price) * float(quantity))
            * self.config.commission_bps
            / 10_000
            + self.config.fixed_fee_per_fill
        )

    def run(self, dataset: MarketDataset, strategy: SignalFunction) -> ReplayResult:
        candles = dataset.candles
        balance = self.config.starting_capital
        position = 0.0
        entry_price = 0.0
        entry_fee = 0.0
        entry_timestamp: datetime | None = None
        signal_timestamp: datetime | None = None
        total_fees = 0.0
        rejected = 0
        trades: list[ReplayTrade] = []
        curve: list[EquityPoint] = []
        guard = PortfolioGuard(self.config.starting_capital, self.risk_limits)

        def equity(mark: float) -> float:
            return balance + position * (float(mark) - entry_price)

        def close(candle: Candle, raw_price: float, reason: str) -> None:
            nonlocal balance, position, entry_price, entry_fee, total_fees
            nonlocal entry_timestamp, signal_timestamp
            if not position:
                return
            order_side = "SELL" if position > 0 else "BUY"
            exit_price = self._fill_price(raw_price, order_side)
            exit_fee = self._fee(exit_price, abs(position))
            gross = position * (exit_price - entry_price)
            balance += gross - exit_fee
            total_fees += exit_fee
            trades.append(
                ReplayTrade(
                    symbol=dataset.symbol,
                    side="LONG" if position > 0 else "SHORT",
                    quantity=abs(position),
                    signal_timestamp=signal_timestamp or entry_timestamp or candle.timestamp,
                    entry_timestamp=entry_timestamp or candle.timestamp,
                    exit_timestamp=candle.timestamp,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_pnl=gross,
                    fees=entry_fee + exit_fee,
                    net_pnl=gross - entry_fee - exit_fee,
                    exit_reason=reason,
                )
            )
            position = 0.0
            entry_price = 0.0
            entry_fee = 0.0
            entry_timestamp = None
            signal_timestamp = None

        for index in range(1, len(candles)):
            candle = candles[index]
            marked_equity = equity(candle.open)
            guard.update_equity(marked_equity)

            desired = int(strategy(candles, index - 1))
            if desired not in {-1, 0, 1}:
                raise ValueError("Strategy signals must be -1, 0, or 1.")
            if guard.halted:
                desired = 0

            current_direction = 1 if position > 0 else -1 if position < 0 else 0
            if desired != current_direction:
                close(candle, candle.open, "SIGNAL" if desired else "FLAT")

                if desired:
                    order_side = "BUY" if desired > 0 else "SELL"
                    proposed_price = self._fill_price(candle.open, order_side)
                    proposed_position = desired * self.config.quantity
                    assessment = guard.evaluate_positions(
                        {dataset.symbol: proposed_position},
                        {dataset.symbol: proposed_price},
                        balance,
                    )
                    if assessment["allowed"]:
                        position = proposed_position
                        entry_price = proposed_price
                        entry_fee = self._fee(entry_price, abs(position))
                        balance -= entry_fee
                        total_fees += entry_fee
                        entry_timestamp = candle.timestamp
                        signal_timestamp = candles[index - 1].timestamp
                    else:
                        rejected += 1

            point_equity = equity(candle.close)
            guard.update_equity(point_equity)
            curve.append(EquityPoint(candle.timestamp, point_equity))

        final_candle = candles[-1]
        if position:
            close(final_candle, final_candle.close, "END_OF_DATA")
            curve.append(EquityPoint(final_candle.timestamp, balance))

        peak = self.config.starting_capital
        maximum_drawdown = 0.0
        for point in curve:
            peak = max(peak, point.equity)
            if peak > 0:
                maximum_drawdown = max(
                    maximum_drawdown, 100 * (peak - point.equity) / peak
                )

        return ReplayResult(
            dataset_checksum=dataset.checksum,
            starting_capital=self.config.starting_capital,
            ending_equity=balance,
            net_pnl=balance - self.config.starting_capital,
            total_fees=total_fees,
            maximum_drawdown_pct=maximum_drawdown,
            trades=tuple(trades),
            equity_curve=tuple(curve),
            rejected_signals=rejected,
            halted=guard.halted,
            halt_reason=guard.halt_reason,
        )
