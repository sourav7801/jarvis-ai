# ============================================================
# JARVIS PAPER BROKER
# V2
# ============================================================
#
# PAPER TRADING ONLY
#
# Features:
#   - Long / short positions
#   - Cash protection
#   - Optional leverage
#   - Stop loss
#   - Take profit
#   - Position averaging
#   - Partial close
#   - Full close
#   - Realized P&L
#   - Unrealized P&L
#   - Equity
#   - Order history
#   - Trade history
#   - Fees hook
#   - Slippage hook
#
# No live broker connection.
# ============================================================

from __future__ import annotations

import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class Position:

    symbol: str
    quantity: float
    average_price: float
    side: str
    current_price: float

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    realized_pnl: float = 0.0
    opened_at: str = ""


@dataclass
class Order:

    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float

    order_type: str
    status: str
    created_at: str

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    fees: float = 0.0
    slippage: float = 0.0

    reason: str = ""


@dataclass
class Trade:

    trade_id: str
    symbol: str
    side: str

    quantity: float

    entry_price: float
    exit_price: float

    pnl: float

    fees: float
    net_pnl: float

    opened_at: str
    closed_at: str

    reason: str = ""


# ============================================================
# PAPER BROKER
# ============================================================

class PaperBroker:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        max_leverage: float = 1.0,
        commission_per_order: float = 0.0,
        slippage_percent: float = 0.0,
    ):

        if starting_capital <= 0:
            raise ValueError(
                "starting_capital must be positive."
            )

        if max_leverage <= 0:
            raise ValueError(
                "max_leverage must be positive."
            )

        if commission_per_order < 0:
            raise ValueError(
                "commission_per_order cannot be negative."
            )

        if slippage_percent < 0:
            raise ValueError(
                "slippage_percent cannot be negative."
            )

        self.starting_capital = float(
            starting_capital
        )

        self.cash = float(
            starting_capital
        )

        self.max_leverage = float(
            max_leverage
        )

        self.commission_per_order = float(
            commission_per_order
        )

        self.slippage_percent = float(
            slippage_percent
        )

        self.positions: Dict[
            str,
            Position,
        ] = {}

        self.orders: List[
            Order
        ] = []

        self.trades: List[
            Trade
        ] = []

        self.prices: Dict[
            str,
            float,
        ] = {}

        self.realized_pnl = 0.0

        self.total_fees = 0.0

    # ========================================================
    # TIME
    # ========================================================

    def _now(self) -> str:

        return datetime.now().isoformat(
            timespec="seconds"
        )

    # ========================================================
    # SLIPPAGE
    # ========================================================

    def _execution_price(
        self,
        side: str,
        price: float,
    ) -> float:

        if self.slippage_percent <= 0:
            return float(price)

        adjustment = (
            price
            * self.slippage_percent
            / 100.0
        )

        if side == "BUY":
            return float(
                price + adjustment
            )

        return float(
            price - adjustment
        )

    # ========================================================
    # MARGIN / NOTIONAL
    # ========================================================

    def current_gross_exposure(self) -> float:

        exposure = 0.0

        for position in self.positions.values():

            exposure += abs(
                position.current_price
                * position.quantity
            )

        return exposure

    def maximum_exposure(self) -> float:

        return (
            self.starting_capital
            * self.max_leverage
        )

    def available_exposure(self) -> float:

        return max(
            0.0,
            self.maximum_exposure()
            -
            self.current_gross_exposure(),
        )

    # ========================================================
    # PRICE
    # ========================================================

    def update_price(
        self,
        symbol: str,
        price: float,
    ) -> Dict[str, Any]:

        symbol = str(
            symbol
        ).upper().strip()

        try:
            price = float(price)
        except Exception:
            return {
                "success": False,
                "message": "Invalid price.",
            }

        if price <= 0:

            return {
                "success": False,
                "message": "Price must be positive.",
            }

        self.prices[
            symbol
        ] = price

        self._refresh_position_price(
            symbol,
            price,
        )

        self._check_protective_orders(
            symbol
        )

        return {
            "success": True,
            "symbol": symbol,
            "price": price,
        }

    def _refresh_position_price(
        self,
        symbol: str,
        price: float,
    ):

        position = self.positions.get(
            symbol
        )

        if position is not None:

            position.current_price = (
                float(price)
            )

    def get_price(
        self,
        symbol: str,
    ) -> Optional[float]:

        return self.prices.get(
            str(symbol).upper().strip()
        )

    # ========================================================
    # BUY
    # ========================================================

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reason: str = "",
    ) -> Dict[str, Any]:

        return self._execute(
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
        )

    # ========================================================
    # SELL
    # ========================================================

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reason: str = "",
    ) -> Dict[str, Any]:

        return self._execute(
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
        )

    # ========================================================
    # EXECUTE
    # ========================================================

    def _execute(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float],
        reason: str,
    ) -> Dict[str, Any]:

        symbol = str(
            symbol
        ).upper().strip()

        side = str(
            side
        ).upper().strip()

        try:
            quantity = float(quantity)
        except Exception:
            return {
                "success": False,
                "message": "Invalid quantity.",
            }

        if side not in {"BUY", "SELL"}:

            return {
                "success": False,
                "message": "Side must be BUY or SELL.",
            }

        if quantity <= 0:

            return {
                "success": False,
                "message": "Quantity must be positive.",
            }

        if price is None:

            price = self.get_price(
                symbol
            )

        if price is None:

            return {
                "success": False,
                "message":
                    f"No market price available for {symbol}.",
            }

        try:
            price = float(price)
        except Exception:
            return {
                "success": False,
                "message": "Invalid execution price.",
            }

        if price <= 0:

            return {
                "success": False,
                "message": "Execution price must be positive.",
            }

        execution_price = (
            self._execution_price(
                side,
                price,
            )
        )

        fees = (
            self.commission_per_order
        )

        position = self.positions.get(
            symbol
        )

        # ----------------------------------------------------
        # Existing position
        # ----------------------------------------------------

        if position is not None:

            same_direction = (

                (
                    position.side == "LONG"
                    and
                    side == "BUY"
                )

                or

                (
                    position.side == "SHORT"
                    and
                    side == "SELL"
                )

            )

            if same_direction:

                result = self._add_position(
                    position=position,
                    side=side,
                    quantity=quantity,
                    price=execution_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    fees=fees,
                    reason=reason,
                )

            else:

                result = self._close_or_reverse(
                    position=position,
                    side=side,
                    quantity=quantity,
                    price=execution_price,
                    fees=fees,
                    reason=reason,
                )

        else:

            result = self._open_position(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=execution_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                fees=fees,
                reason=reason,
            )

        if result.get(
            "success",
            False,
        ):

            order_id = str(
                uuid.uuid4()
            )

            order = Order(

                order_id=order_id,

                symbol=symbol,

                side=side,

                quantity=quantity,

                price=execution_price,

                order_type="MARKET",

                status="FILLED",

                created_at=self._now(),

                stop_loss=stop_loss,

                take_profit=take_profit,

                fees=fees,

                slippage=(
                    execution_price
                    - price
                ),

                reason=reason,

            )

            self.orders.append(
                order
            )

            self.total_fees += fees

            result[
                "order_id"
            ] = order_id

            result[
                "execution_price"
            ] = execution_price

        return result

    # ========================================================
    # OPEN
    # ========================================================

    def _open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        fees: float,
        reason: str,
    ) -> Dict[str, Any]:

        notional = (
            price
            * quantity
        )

        current_exposure = (
            self.current_gross_exposure()
        )

        available = (
            self.maximum_exposure()
            -
            current_exposure
        )

        if notional > (
            available + 1e-9
        ):

            return {

                "success": False,

                "message":
                    (
                        "Order rejected: exposure "
                        f"{notional:.2f} exceeds "
                        f"available exposure "
                        f"{max(available, 0):.2f}."
                    ),

            }

        if side == "BUY":

            required_cash = (
                notional
                + fees
            )

            if required_cash > (
                self.cash + 1e-9
            ):

                # At leverage > 1 we permit
                # notional exposure, but never
                # unlimited borrowing.
                max_supported = (
                    self.cash
                    * self.max_leverage
                )

                if (
                    notional
                    >
                    max_supported
                ):

                    return {

                        "success": False,

                        "message":
                            (
                                "Order rejected: "
                                "insufficient paper "
                                "buying power."
                            ),

                    }

            self.cash -= (
                notional
                + fees
            )

            position_side = "LONG"

        else:

            self.cash += (
                notional
                - fees
            )

            position_side = "SHORT"

        self.positions[
            symbol
        ] = Position(

            symbol=symbol,

            quantity=quantity,

            average_price=price,

            side=position_side,

            current_price=price,

            stop_loss=stop_loss,

            take_profit=take_profit,

            opened_at=self._now(),

        )

        return {

            "success": True,

            "action": "OPEN",

            "symbol": symbol,

            "side": position_side,

            "quantity": quantity,

            "price": price,

            "message":
                (
                    f"Opened {position_side} "
                    f"{quantity:g} {symbol} "
                    f"at {price:.2f}."
                ),

        }

    # ========================================================
    # ADD POSITION
    # ========================================================

    def _add_position(
        self,
        position: Position,
        side: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        fees: float,
        reason: str,
    ) -> Dict[str, Any]:

        extra_notional = (
            price
            * quantity
        )

        available = (
            self.available_exposure()
        )

        if extra_notional > (
            available + 1e-9
        ):

            return {

                "success": False,

                "message":
                    (
                        "Order rejected: "
                        "maximum exposure exceeded."
                    ),

            }

        if side == "BUY":

            if (
                extra_notional
                + fees
                >
                self.cash
                + 1e-9
                and
                self.max_leverage <= 1.0
            ):

                return {

                    "success": False,

                    "message":
                        (
                            "Order rejected: "
                            "insufficient cash."
                        ),

                }

            self.cash -= (
                extra_notional
                + fees
            )

        else:

            self.cash += (
                extra_notional
                - fees
            )

        old_quantity = (
            position.quantity
        )

        new_quantity = (
            old_quantity
            + quantity
        )

        position.average_price = (

            (
                position.average_price
                * old_quantity
            )

            +

            (
                price
                * quantity
            )

        ) / new_quantity

        position.quantity = (
            new_quantity
        )

        position.current_price = (
            price
        )

        if stop_loss is not None:

            position.stop_loss = (
                stop_loss
            )

        if take_profit is not None:

            position.take_profit = (
                take_profit
            )

        return {

            "success": True,

            "action": "ADD",

            "symbol": position.symbol,

            "quantity": quantity,

            "price": price,

            "message":
                (
                    f"Added {quantity:g} "
                    f"to {position.symbol}."
                ),

        }

    # ========================================================
    # CLOSE / REVERSE
    # ========================================================

    def _close_or_reverse(
        self,
        position: Position,
        side: str,
        quantity: float,
        price: float,
        fees: float,
        reason: str,
    ) -> Dict[str, Any]:

        close_quantity = min(
            quantity,
            position.quantity,
        )

        if position.side == "LONG":

            pnl = (
                price
                - position.average_price
            ) * close_quantity

            self.cash += (
                price
                * close_quantity
            )

        else:

            pnl = (
                position.average_price
                - price
            ) * close_quantity

            self.cash -= (
                price
                * close_quantity
            )

        net_pnl = (
            pnl
            - fees
        )

        self.realized_pnl += (
            net_pnl
        )

        remaining = (
            position.quantity
            - close_quantity
        )

        trade = Trade(

            trade_id=str(
                uuid.uuid4()
            ),

            symbol=position.symbol,

            side=position.side,

            quantity=close_quantity,

            entry_price=position.average_price,

            exit_price=price,

            pnl=pnl,

            fees=fees,

            net_pnl=net_pnl,

            opened_at=position.opened_at,

            closed_at=self._now(),

            reason=reason,

        )

        self.trades.append(
            trade
        )

        if remaining <= 0:

            symbol = (
                position.symbol
            )

            del self.positions[
                symbol
            ]

            return {

                "success": True,

                "action": "CLOSE",

                "symbol": symbol,

                "quantity":
                    close_quantity,

                "price": price,

                "pnl": pnl,

                "net_pnl":
                    net_pnl,

                "message":
                    (
                        f"Closed {symbol}. "
                        f"Net P&L: "
                        f"{net_pnl:.2f}"
                    ),

            }

        position.quantity = (
            remaining
        )

        position.current_price = (
            price
        )

        return {

            "success": True,

            "action": "REDUCE",

            "symbol":
                position.symbol,

            "quantity":
                close_quantity,

            "remaining":
                remaining,

            "pnl":
                pnl,

            "net_pnl":
                net_pnl,

            "message":
                (
                    f"Reduced "
                    f"{position.symbol}. "
                    f"Net P&L: "
                    f"{net_pnl:.2f}"
                ),

        }

    # ========================================================
    # PROTECTIVE ORDERS
    # ========================================================

    def _check_protective_orders(
        self,
        symbol: str,
    ):

        # Get a fresh reference because a protective
        # order can remove the position.
        position = self.positions.get(
            symbol
        )

        if position is None:
            return

        price = (
            position.current_price
        )

        # LONG STOP
        if (
            position.side == "LONG"
            and
            position.stop_loss is not None
            and
            price <= position.stop_loss
        ):

            quantity = (
                position.quantity
            )

            self.sell(
                symbol=symbol,
                quantity=quantity,
                price=price,
                reason="STOP_LOSS",
            )

            return

        # LONG TARGET
        if (
            position.side == "LONG"
            and
            position.take_profit is not None
            and
            price >= position.take_profit
        ):

            quantity = (
                position.quantity
            )

            self.sell(
                symbol=symbol,
                quantity=quantity,
                price=price,
                reason="TAKE_PROFIT",
            )

            return

        # SHORT STOP
        if (
            position.side == "SHORT"
            and
            position.stop_loss is not None
            and
            price >= position.stop_loss
        ):

            quantity = (
                position.quantity
            )

            self.buy(
                symbol=symbol,
                quantity=quantity,
                price=price,
                reason="STOP_LOSS",
            )

            return

        # SHORT TARGET
        if (
            position.side == "SHORT"
            and
            position.take_profit is not None
            and
            price <= position.take_profit
        ):

            quantity = (
                position.quantity
            )

            self.buy(
                symbol=symbol,
                quantity=quantity,
                price=price,
                reason="TAKE_PROFIT",
            )

    # ========================================================
    # UNREALIZED P&L
    # ========================================================

    def unrealized_pnl(
        self,
        symbol: str,
    ) -> float:

        position = self.positions.get(
            symbol
        )

        if position is None:
            return 0.0

        current = (
            self.get_price(
                symbol
            )
            or
            position.current_price
        )

        if position.side == "LONG":

            return (
                current
                - position.average_price
            ) * position.quantity

        return (
            position.average_price
            - current
        ) * position.quantity

    def total_unrealized_pnl(self) -> float:

        return sum(

            self.unrealized_pnl(
                symbol
            )

            for symbol
            in self.positions

        )

    # ========================================================
    # EQUITY
    # ========================================================

    def equity(self) -> float:

        unrealized = (
            self.total_unrealized_pnl()
        )

        return (
            self.starting_capital
            + self.realized_pnl
            + unrealized
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    def account_summary(
        self,
    ) -> Dict[str, Any]:

        equity = self.equity()

        return {

            "starting_capital":
                self.starting_capital,

            "cash":
                self.cash,

            "equity":
                equity,

            "realized_pnl":
                self.realized_pnl,

            "unrealized_pnl":
                self.total_unrealized_pnl(),

            "total_pnl":
                (
                    equity
                    - self.starting_capital
                ),

            "gross_exposure":
                self.current_gross_exposure(),

            "available_exposure":
                self.available_exposure(),

            "open_positions":
                len(
                    self.positions
                ),

            "total_fees":
                self.total_fees,

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
            ] = self.unrealized_pnl(
                position.symbol
            )

            result.append(
                data
            )

        return result

    # ========================================================
    # ORDERS
    # ========================================================

    def get_orders(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            asdict(order)
            for order
            in self.orders
        ]

    # ========================================================
    # TRADES
    # ========================================================

    def get_trades(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            asdict(trade)
            for trade
            in self.trades
        ]

    # ========================================================
    # CLOSE ALL
    # ========================================================

    def close_all(
        self,
    ) -> Dict[str, Any]:

        results = []

        for symbol in list(
            self.positions.keys()
        ):

            position = self.positions.get(
                symbol
            )

            if position is None:
                continue

            price = (
                self.get_price(
                    symbol
                )
                or
                position.current_price
            )

            if position.side == "LONG":

                result = self.sell(
                    symbol=symbol,
                    quantity=position.quantity,
                    price=price,
                    reason="CLOSE_ALL",
                )

            else:

                result = self.buy(
                    symbol=symbol,
                    quantity=position.quantity,
                    price=price,
                    reason="CLOSE_ALL",
                )

            results.append(
                result
            )

        return {
            "success": True,
            "results": results,
        }


# ============================================================
# GLOBAL BROKER
# ============================================================

paper_broker = PaperBroker()


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS PAPER BROKER V2")
    print("=" * 60)
    print()

    broker = PaperBroker(
        starting_capital=100_000.0,
        max_leverage=1.0,
        commission_per_order=10.0,
        slippage_percent=0.01,
    )

    broker.update_price(
        "NIFTY",
        24_366.0,
    )

    print("INITIAL ACCOUNT")
    print(
        broker.account_summary()
    )

    print()
    print("OPENING POSITION")

    result = broker.buy(
        symbol="NIFTY",
        quantity=4,
        price=24_366.0,
        stop_loss=24_000.0,
        take_profit=24_800.0,
        reason="Paper test",
    )

    print(result)

    print()
    print("ACCOUNT AFTER ENTRY")
    print(
        broker.account_summary()
    )

    print()
    print("MOVING PRICE TO 24,700")

    broker.update_price(
        "NIFTY",
        24_700.0,
    )

    print(
        broker.account_summary()
    )

    print()
    print("MOVING PRICE ABOVE TARGET")

    broker.update_price(
        "NIFTY",
        24_900.0,
    )

    print(
        broker.account_summary()
    )

    print()

    print("OPEN POSITIONS")
    for position in (
        broker.get_positions()
    ):
        print(position)

    print()

    print("TRADES")

    for trade in (
        broker.get_trades()
    ):
        print(trade)

    print()

    print("ORDERS")

    for order in (
        broker.get_orders()
    ):
        print(order)

    print()

    print(
        "Paper Broker V2 loaded successfully."
    )