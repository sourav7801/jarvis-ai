# ============================================================
# JARVIS PORTFOLIO ENGINE
# V1
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


# ============================================================
# POSITION
# ============================================================

@dataclass
class PortfolioPosition:

    symbol: str

    market: str

    asset_type: str

    side: str

    quantity: float

    average_entry: float

    current_price: float

    stop_loss: Optional[float] = None

    take_profit: Optional[float] = None

    realized_pnl: float = 0.0

    opened_at: str = ""


# ============================================================
# PORTFOLIO ENGINE
# ============================================================

class PortfolioEngine:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
    ):

        if starting_capital <= 0:

            raise ValueError(
                "Starting capital must be positive."
            )

        self.starting_capital = float(
            starting_capital
        )

        self.cash = float(
            starting_capital
        )

        self.positions: Dict[
            str,
            PortfolioPosition,
        ] = {}

        self.closed_pnl = 0.0

        self.daily_realized_pnl = 0.0

        self.daily_start_equity = (
            float(starting_capital)
        )

        self.equity_history = []

    # ========================================================
    # TIME
    # ========================================================

    def _now(self) -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    # ========================================================
    # POSITION KEY
    # ========================================================

    def position_key(
        self,
        symbol: str,
        asset_type: str = "STOCK",
    ) -> str:

        return (
            f"{str(symbol).upper().strip()}:"
            f"{str(asset_type).upper().strip()}"
        )

    # ========================================================
    # OPEN POSITION
    # ========================================================

    def open_position(
        self,
        symbol: str,
        market: str,
        asset_type: str,
        side: str,
        quantity: float,
        entry_price: float,
        current_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]:

        symbol = str(
            symbol
        ).upper().strip()

        market = str(
            market
        ).upper().strip()

        asset_type = str(
            asset_type
        ).upper().strip()

        side = str(
            side
        ).upper().strip()

        quantity = float(
            quantity
        )

        entry_price = float(
            entry_price
        )

        if current_price is None:

            current_price = entry_price

        current_price = float(
            current_price
        )

        if side not in {
            "LONG",
            "SHORT",
        }:

            return {
                "success": False,
                "message":
                    "Side must be LONG or SHORT.",
            }

        if quantity <= 0:

            return {
                "success": False,
                "message":
                    "Quantity must be positive.",
            }

        if entry_price <= 0:

            return {
                "success": False,
                "message":
                    "Entry price must be positive.",
            }

        key = self.position_key(
            symbol,
            asset_type,
        )

        existing = self.positions.get(
            key
        )

        # ----------------------------------------------------
        # New position
        # ----------------------------------------------------

        if existing is None:

            self.positions[key] = (
                PortfolioPosition(

                    symbol=symbol,

                    market=market,

                    asset_type=asset_type,

                    side=side,

                    quantity=quantity,

                    average_entry=entry_price,

                    current_price=current_price,

                    stop_loss=stop_loss,

                    take_profit=take_profit,

                    opened_at=self._now(),

                )
            )

            return {
                "success": True,
                "action": "OPEN",
                "message":
                    (
                        f"Opened {side} "
                        f"{quantity} {symbol} "
                        f"at {entry_price:.2f}."
                    ),
            }

        # ----------------------------------------------------
        # Same direction: add
        # ----------------------------------------------------

        if existing.side == side:

            old_quantity = (
                existing.quantity
            )

            new_quantity = (
                old_quantity
                + quantity
            )

            existing.average_entry = (

                (
                    existing.average_entry
                    * old_quantity
                )
                +
                (
                    entry_price
                    * quantity
                )

            ) / new_quantity

            existing.quantity = (
                new_quantity
            )

            existing.current_price = (
                current_price
            )

            if stop_loss is not None:

                existing.stop_loss = (
                    stop_loss
                )

            if take_profit is not None:

                existing.take_profit = (
                    take_profit
                )

            return {
                "success": True,
                "action": "ADD",
                "message":
                    (
                        f"Added {quantity} "
                        f"to {symbol}."
                    ),
            }

        # ----------------------------------------------------
        # Opposite side: reduce/close
        # ----------------------------------------------------

        close_quantity = min(
            quantity,
            existing.quantity,
        )

        if existing.side == "LONG":

            pnl = (
                entry_price
                - existing.average_entry
            ) * close_quantity

        else:

            pnl = (
                existing.average_entry
                - entry_price
            ) * close_quantity

        existing.realized_pnl += pnl

        self.closed_pnl += pnl

        self.daily_realized_pnl += pnl

        remaining = (
            existing.quantity
            - close_quantity
        )

        if remaining <= 0:

            del self.positions[
                key
            ]

            return {
                "success": True,
                "action": "CLOSE",
                "symbol": symbol,
                "quantity": close_quantity,
                "pnl": pnl,
                "message":
                    (
                        f"Closed {symbol}. "
                        f"Realized P&L: "
                        f"{pnl:.2f}"
                    ),
            }

        existing.quantity = (
            remaining
        )

        existing.current_price = (
            current_price
        )

        return {
            "success": True,
            "action": "REDUCE",
            "symbol": symbol,
            "quantity": close_quantity,
            "remaining": remaining,
            "pnl": pnl,
            "message":
                (
                    f"Reduced {symbol}. "
                    f"Realized P&L: "
                    f"{pnl:.2f}"
                ),
        }

    # ========================================================
    # UPDATE PRICE
    # ========================================================

    def update_price(
        self,
        symbol: str,
        asset_type: str,
        price: float,
    ) -> Dict[str, Any]:

        key = self.position_key(
            symbol,
            asset_type,
        )

        position = self.positions.get(
            key
        )

        if position is None:

            return {
                "success": False,
                "message":
                    (
                        f"No open position for "
                        f"{symbol}."
                    ),
            }

        price = float(
            price
        )

        if price <= 0:

            return {
                "success": False,
                "message":
                    "Price must be positive.",
            }

        position.current_price = (
            price
        )

        return {
            "success": True,
            "symbol": symbol,
            "price": price,
        }

    # ========================================================
    # UNREALIZED P&L
    # ========================================================

    def position_unrealized_pnl(
        self,
        position: PortfolioPosition,
    ) -> float:

        if position.side == "LONG":

            return (
                position.current_price
                - position.average_entry
            ) * position.quantity

        return (
            position.average_entry
            - position.current_price
        ) * position.quantity

    # ========================================================
    # TOTAL UNREALIZED
    # ========================================================

    def total_unrealized_pnl(self) -> float:

        return sum(

            self.position_unrealized_pnl(
                position
            )

            for position
            in self.positions.values()

        )

    # ========================================================
    # TOTAL P&L
    # ========================================================

    def total_pnl(self) -> float:

        return (
            self.closed_pnl
            +
            self.total_unrealized_pnl()
        )

    # ========================================================
    # EQUITY
    # ========================================================

    def equity(self) -> float:

        return (
            self.starting_capital
            +
            self.total_pnl()
        )

    # ========================================================
    # RETURN %
    # ========================================================

    def return_percent(self) -> float:

        return (
            self.total_pnl()
            /
            self.starting_capital
            * 100.0
        )

    # ========================================================
    # EXPOSURE
    # ========================================================

    def gross_exposure(self) -> float:

        exposure = 0.0

        for position in (
            self.positions.values()
        ):

            exposure += (
                abs(
                    position.current_price
                    *
                    position.quantity
                )
            )

        return exposure

    # ========================================================
    # LONG EXPOSURE
    # ========================================================

    def long_exposure(self) -> float:

        total = 0.0

        for position in (
            self.positions.values()
        ):

            if position.side == "LONG":

                total += (
                    position.current_price
                    *
                    position.quantity
                )

        return total

    # ========================================================
    # SHORT EXPOSURE
    # ========================================================

    def short_exposure(self) -> float:

        total = 0.0

        for position in (
            self.positions.values()
        ):

            if position.side == "SHORT":

                total += (
                    position.current_price
                    *
                    position.quantity
                )

        return total

    # ========================================================
    # MAX DRAWDOWN
    # ========================================================

    def max_drawdown(self) -> float:

        if not self.equity_history:

            return 0.0

        peak = self.equity_history[0]

        maximum_drawdown = 0.0

        for value in self.equity_history:

            peak = max(
                peak,
                value,
            )

            drawdown = (
                peak
                - value
            )

            maximum_drawdown = max(
                maximum_drawdown,
                drawdown,
            )

        return maximum_drawdown

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def snapshot(self) -> Dict[str, Any]:

        current_equity = (
            self.equity()
        )

        self.equity_history.append(
            current_equity
        )

        return {

            "timestamp":
                self._now(),

            "starting_capital":
                self.starting_capital,

            "equity":
                current_equity,

            "return_percent":
                self.return_percent(),

            "realized_pnl":
                self.closed_pnl,

            "unrealized_pnl":
                self.total_unrealized_pnl(),

            "total_pnl":
                self.total_pnl(),

            "gross_exposure":
                self.gross_exposure(),

            "long_exposure":
                self.long_exposure(),

            "short_exposure":
                self.short_exposure(),

            "open_positions":
                len(
                    self.positions
                ),

            "max_drawdown":
                self.max_drawdown(),

        }

    # ========================================================
    # POSITIONS
    # ========================================================

    def get_positions(
        self,
    ) -> List[Dict[str, Any]]:

        result = []

        for position in (
            self.positions.values()
        ):

            data = asdict(
                position
            )

            data[
                "unrealized_pnl"
            ] = self.position_unrealized_pnl(
                position
            )

            result.append(
                data
            )

        return result

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):

        self.cash = (
            self.starting_capital
        )

        self.positions.clear()

        self.closed_pnl = 0.0

        self.daily_realized_pnl = 0.0

        self.daily_start_equity = (
            self.starting_capital
        )

        self.equity_history.clear()


# ============================================================
# GLOBAL
# ============================================================

portfolio_engine = PortfolioEngine()


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS PORTFOLIO ENGINE"
    )

    print(
        "=" * 60
    )

    print()

    portfolio = PortfolioEngine(
        starting_capital=1_000_000
    )

    print(
        "STARTING SNAPSHOT"
    )

    print(
        portfolio.snapshot()
    )

    print()

    print(
        "OPEN NIFTY POSITION"
    )

    result = portfolio.open_position(

        symbol="NIFTY",

        market="INDIA",

        asset_type="INDEX",

        side="LONG",

        quantity=10,

        entry_price=24_366,

        current_price=24_366,

        stop_loss=24_000,

        take_profit=25_000,

    )

    print(
        result
    )

    print()

    portfolio.update_price(

        symbol="NIFTY",

        asset_type="INDEX",

        price=24_700,

    )

    print(
        "AFTER PRICE UPDATE"
    )

    print(
        portfolio.snapshot()
    )

    print()

    print(
        "POSITIONS"
    )

    for position in (
        portfolio.get_positions()
    ):

        print(
            position
        )

    print()

    print(
        "CLOSE POSITION"
    )

    result = portfolio.open_position(

        symbol="NIFTY",

        market="INDIA",

        asset_type="INDEX",

        side="SHORT",

        quantity=10,

        entry_price=24_700,

    )

    print(
        result
    )

    print()

    print(
        "FINAL SNAPSHOT"
    )

    print(
        portfolio.snapshot()
    )

    print()

    print(
        "Portfolio Engine loaded successfully."
    )