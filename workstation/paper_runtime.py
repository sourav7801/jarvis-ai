"""Durable, multi-asset paper trading for the canonical workstation.

This module has no broker or exchange execution client. FYERS market data marks
Indian index and MCX simulations, while public crypto data marks synthetic
crypto positions. Automatic entries require a qualified deterministic
multi-timeframe signal and remain local to the paper account.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Iterable, Optional

from agents.paper_broker import Order, PaperBroker, Position, Trade
from config import STATE_DIR
from workstation.market_runtime import MARKET_RUNTIME, MarketRuntime
from workstation.paper_market_data import ASSET_UNIVERSE, PAPER_MARKET_DATA
from workstation.paper_learning import PaperLearningLedger
from workstation.trading_intelligence import analyze_symbol


Analyzer = Callable[[str], dict[str, Any]]
ALLOWED_SYMBOLS = tuple(ASSET_UNIVERSE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number and abs(number) != float("inf") else default
    except (TypeError, ValueError):
        return default


class PaperTradingRuntime:
    """Own one local paper account and an optional bounded signal loop."""

    def __init__(
        self,
        *,
        state_file: Path = STATE_DIR / "paper_portfolio.json",
        market_runtime: MarketRuntime = MARKET_RUNTIME,
        analyzer: Optional[Analyzer] = None,
        symbols: Optional[Iterable[str]] = None,
        market_data: Any = None,
        interval_seconds: int = 300,
        starting_capital: float = 1_000_000.0,
        auto_arm_on_start: bool = True,
    ) -> None:
        self.state_file = Path(state_file)
        self.market_runtime = market_runtime
        self.market_data = market_data or (
            PAPER_MARKET_DATA if market_runtime is MARKET_RUNTIME else None
        )
        self.analyzer = analyzer or (
            self.market_data.analyze if self.market_data is not None else analyze_symbol
        )
        default_symbols = (
            self.market_data.symbols
            if self.market_data is not None
            else ("NIFTY", "BANKNIFTY", "SENSEX")
        )
        requested_symbols = symbols if symbols is not None else default_symbols
        self.symbols = tuple(
            symbol for symbol in dict.fromkeys(str(item).strip().upper() for item in requested_symbols)
            if symbol in ALLOWED_SYMBOLS
        )
        self.interval_seconds = max(int(interval_seconds), 15)
        self.auto_arm_on_start = bool(auto_arm_on_start)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._autopilot = False
        self._last_scan: Optional[str] = None
        self._last_error: Optional[str] = None
        self._signals: dict[str, dict[str, Any]] = {}
        self._activity: list[dict[str, Any]] = []
        self._last_action_at: dict[str, float] = {}
        self._latest_quotes: dict[str, dict[str, Any]] = {}
        self.learning = PaperLearningLedger()
        self.broker = PaperBroker(
            starting_capital=starting_capital,
            max_leverage=1.0,
            commission_per_order=20.0,
            slippage_percent=0.02,
        )
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            account = payload.get("account") or {}
            self.broker.starting_capital = _number(
                account.get("starting_capital"), self.broker.starting_capital
            )
            self.broker.cash = _number(account.get("cash"), self.broker.starting_capital)
            self.broker.realized_pnl = _number(account.get("realized_pnl"))
            self.broker.total_fees = _number(account.get("total_fees"))
            self.broker.prices = {
                str(key).upper(): _number(value)
                for key, value in (payload.get("prices") or {}).items()
                if _number(value) > 0
            }
            self.broker.positions = {
                str(item["symbol"]).upper(): Position(**item)
                for item in payload.get("positions") or []
                if isinstance(item, dict) and item.get("symbol")
            }
            self.broker.orders = [
                Order(**item) for item in payload.get("orders") or []
                if isinstance(item, dict)
            ][-500:]
            self.broker.trades = [
                Trade(**item) for item in payload.get("trades") or []
                if isinstance(item, dict)
            ][-500:]
            self._autopilot = bool(payload.get("autopilot", False))
            self._signals = dict(payload.get("signals") or {})
            self._activity = list(payload.get("activity") or [])[-100:]
            self.learning.load(payload.get("learning") or {})
        except (OSError, ValueError, TypeError, KeyError):
            self._last_error = "Saved paper account could not be loaded; a clean account is active."

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "updated_at": _now(),
            "autopilot": self._autopilot,
            "account": {
                "starting_capital": self.broker.starting_capital,
                "cash": self.broker.cash,
                "realized_pnl": self.broker.realized_pnl,
                "total_fees": self.broker.total_fees,
            },
            "prices": dict(self.broker.prices),
            "positions": [asdict(item) for item in self.broker.positions.values()],
            "orders": [asdict(item) for item in self.broker.orders[-500:]],
            "trades": [asdict(item) for item in self.broker.trades[-500:]],
            "signals": self._signals,
            "activity": self._activity[-100:],
            "learning": self.learning.snapshot(),
        }
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self.state_file)

    def _record(self, kind: str, message: str, **details: Any) -> None:
        self._activity.append(
            {"timestamp": _now(), "kind": kind, "message": message, **details}
        )
        self._activity = self._activity[-100:]

    def _live_quote(self, symbol: str) -> dict[str, Any]:
        if self.market_data is not None:
            quote = self.market_data.quote(symbol)
            if quote.get("success"):
                self._latest_quotes[symbol] = dict(quote)
            return quote
        snapshot = self.market_runtime.snapshot(symbol)
        price = _number((snapshot or {}).get("ltp"))
        if price <= 0:
            return {"success": False, "symbol": symbol, "message": "Live FYERS price is unavailable."}
        quote = {
            **(snapshot or {}),
            "success": True,
            "symbol": symbol,
            "native_ltp": price,
            "valuation_ltp": price,
            "currency": "INR",
            "valuation_currency": "INR",
            "source": "FYERS",
            "session_open": True,
        }
        self._latest_quotes[symbol] = quote
        return quote

    def _live_price(self, symbol: str) -> Optional[float]:
        quote = self._live_quote(symbol)
        price = _number(quote.get("valuation_ltp"))
        return price if quote.get("success") and price > 0 else None

    def _update_broker_price(self, symbol: str, price: float) -> None:
        trades_before = len(self.broker.trades)
        self.broker.update_price(symbol, price)
        if len(self.broker.trades) > trades_before:
            trade = self.broker.trades[-1]
            self._record(
                "RISK_EXIT",
                f"{trade.symbol} paper {trade.reason.lower().replace('_', ' ')} at {trade.exit_price:,.2f}",
                symbol=trade.symbol,
                pnl=trade.net_pnl,
            )
            self._learn_new_trades()
            self._save()

    def _learn_new_trades(self) -> None:
        """Review every newly closed trade exactly once and persist its lesson."""

        for trade in self.broker.trades:
            review = self.learning.review_trade(
                asdict(trade),
                position_still_open=trade.symbol in self.broker.positions,
            )
            if review is None:
                continue
            self._record(
                "LEARNING_REVIEW",
                f"{review['symbol']} {review['outcome'].lower()} reviewed: {review['lesson']}",
                symbol=review["symbol"],
                strategy=review["strategy"],
                r_multiple=review["r_multiple"],
                review_flags=review["review_flags"],
            )

    def _sync_marks(self) -> None:
        for symbol in list(self.broker.positions):
            price = self._live_price(symbol)
            if price is not None:
                self._update_broker_price(symbol, price)

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return self.public_state()
            if self.auto_arm_on_start:
                self._autopilot = True
                self._signals = {}
                self._last_scan = None
                self._record(
                    "STARTUP",
                    "Paper autopilot armed automatically at JARVIS startup.",
                )
                self._save()
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-paper-autopilot",
                daemon=True,
            )
            self._thread.start()
            return self.public_state()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=3)
        with self._lock:
            self._running = False
            self._thread = None
            self._save()

    def _run(self) -> None:
        while not self._stop_event.wait(2):
            try:
                if self._autopilot:
                    self.scan_once()
                else:
                    with self._lock:
                        self._sync_marks()
            except Exception as error:
                with self._lock:
                    self._last_error = f"{type(error).__name__}: {error}"[:240]
            if self._stop_event.wait(self.interval_seconds - 2):
                break

    def set_autopilot(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self._autopilot = bool(enabled)
            self._last_error = None
            self._record(
                "CONTROL",
                "Paper autopilot armed." if self._autopilot else "Paper autopilot paused.",
            )
            self._save()
            return self.public_state()

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float = 1.0,
        *,
        reason: str = "MANUAL_PAPER_ORDER",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        decision_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper().replace(" ", "")
        direction = str(side or "").strip().upper()
        size = _number(quantity)
        option_contract = bool(re.fullmatch(r"MCX:[A-Z0-9_-]+(?:CE|PE)", normalized))
        if normalized not in self.symbols and not option_contract:
            raise ValueError(
                "Paper trading supports configured indices, MCX commodities, and crypto assets."
            )
        if direction not in {"BUY", "SELL"}:
            raise ValueError("Paper side must be BUY or SELL.")
        if size <= 0 or size > 100:
            raise ValueError("Paper quantity must be between 0 and 100 synthetic units.")
        live_price = price if price is not None else self._live_price(normalized)
        if live_price is None or _number(live_price) <= 0:
            raise RuntimeError(
                "No validated market-data price is available. Paper orders wait for a connected read-only feed."
            )
        with self._lock:
            self._update_broker_price(normalized, _number(live_price))
            result = (
                self.broker.buy(
                    normalized,
                    size,
                    price=_number(live_price),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=reason,
                )
                if direction == "BUY"
                else self.broker.sell(
                    normalized,
                    size,
                    price=_number(live_price),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=reason,
                )
            )
            if not result.get("success"):
                raise RuntimeError(str(result.get("message") or "Paper order was rejected."))
            if result.get("action") in {"OPEN", "ADD"}:
                context = dict(decision_context or {})
                context.update(
                    {
                        "entry_price": _number(result.get("price") or live_price),
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "quantity": size,
                        "opened_at": _now(),
                    }
                )
                self.learning.remember_entry(normalized, context)
            if result.get("action") in {"CLOSE", "REDUCE"}:
                self._learn_new_trades()
            self._record(
                "PAPER_FILL",
                f"{direction} {size:g} {normalized} at {_number(live_price):,.2f}",
                symbol=normalized,
                side=direction,
                quantity=size,
                price=_number(live_price),
                reason=reason,
            )
            self._save()
            return {"ok": True, "paper_only": True, "result": result, "state": self.public_state()}

    def close_position(self, symbol: str, *, reason: str = "MANUAL_PAPER_CLOSE") -> dict[str, Any]:
        normalized = str(symbol or "").strip().upper().replace(" ", "")
        with self._lock:
            position = self.broker.positions.get(normalized)
            if position is None:
                raise ValueError(f"No open paper position exists for {normalized}.")
            side = "SELL" if position.side == "LONG" else "BUY"
            quantity = position.quantity
        return self.place_order(normalized, side, quantity, reason=reason)

    def place_guarded_order(self, symbol: str, side: str, quantity: float = 1.0) -> dict[str, Any]:
        """Place an explicit paper order only after attaching a stop and target."""

        normalized = str(symbol or "").strip().upper().replace(" ", "")
        direction = str(side or "").strip().upper()
        if self.market_data is not None and not self.market_data.session_open(normalized):
            raise RuntimeError(
                f"The {normalized} market session is closed. New paper entries wait for the market to reopen."
            )
        intelligence = self.analyzer(normalized)
        if not intelligence.get("success"):
            raise RuntimeError("Paper order rejected because validated multi-timeframe data is unavailable.")
        quote = self._live_quote(normalized)
        price = _number(quote.get("valuation_ltp"))
        native_price = _number(quote.get("native_ltp"), price)
        native_atr = _number(intelligence.get("atr14"))
        conversion = price / native_price if native_price else 1.0
        risk_distance = native_atr * conversion * 1.5
        if price <= 0 or risk_distance <= 0:
            raise RuntimeError("Paper order rejected because a protective risk distance could not be validated.")
        stop_loss = price - risk_distance if direction == "BUY" else price + risk_distance
        take_profit = price + risk_distance * 2.2 if direction == "BUY" else price - risk_distance * 2.2
        return self.place_order(
            normalized,
            direction,
            quantity,
            reason="MANUAL_GUARDED_PAPER_ORDER",
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            decision_context={
                "strategy": "MANUAL_GUARDED",
                "patterns": intelligence.get("chart_patterns") or [],
                "confidence": intelligence.get("confidence", 0),
                "risk_reward": 2.2,
                "regime": intelligence.get("regime"),
                "asset_class": quote.get("asset_class"),
            },
        )

    def place_option_order(
        self,
        contract: dict[str, Any],
        side: str,
        quantity: float = 1.0,
    ) -> dict[str, Any]:
        """Place a protected synthetic option fill using an exact FYERS contract."""

        provider_symbol = str(contract.get("provider_symbol") or "").strip().upper()
        direction = str(side or "").strip().upper()
        if not re.fullmatch(r"MCX:[A-Z0-9_-]+(?:CE|PE)", provider_symbol):
            raise ValueError("A verified FYERS MCX option contract is required.")
        if direction not in {"BUY", "SELL"}:
            raise ValueError("Paper option side must be BUY or SELL.")
        with self._lock:
            existing = self.broker.positions.get(provider_symbol)
        if direction == "SELL" and existing is None:
            raise ValueError(
                "Naked option selling is disabled. JARVIS only permits protected long-option paper positions."
            )
        if self.market_data is None:
            raise RuntimeError("Exact option quotes require the unified FYERS market-data adapter.")
        underlying = str(contract.get("underlying") or "CRUDEOIL").strip().upper()
        is_new_exposure = direction == "BUY"
        if is_new_exposure and not self.market_data.session_open(underlying):
            raise RuntimeError(
                f"The {underlying} market session is closed. New paper entries wait for the exchange to reopen."
            )
        quote = self._live_quote(provider_symbol)
        premium = _number(quote.get("valuation_ltp"))
        if not quote.get("success") or premium <= 0:
            raise RuntimeError("No validated FYERS premium is available for the exact option contract.")
        if is_new_exposure and quote.get("session_open") is not True:
            raise RuntimeError(
                "FYERS returned a last-traded option price, but the exchange session is closed. "
                "JARVIS will not treat that stale mark as an executable paper fill."
            )
        if direction == "SELL":
            size = min(_number(quantity), existing.quantity if existing else 0.0)
            return self.place_order(
                provider_symbol,
                "SELL",
                size,
                reason="MANUAL_OPTION_PAPER_CLOSE",
                price=premium,
            )

        tick_size = max(_number(contract.get("tick_size"), 0.05), 0.01)
        risk_distance = max(premium * 0.50, tick_size)
        stop_loss = max(premium - risk_distance, tick_size)
        take_profit = premium + risk_distance * 2.0
        result = self.place_order(
            provider_symbol,
            "BUY",
            quantity,
            reason="MANUAL_PROTECTED_OPTION_PAPER_ORDER",
            price=premium,
            stop_loss=stop_loss,
            take_profit=take_profit,
            decision_context={
                "strategy": "MANUAL_LONG_OPTION",
                "patterns": [],
                "confidence": 0,
                "risk_reward": 2.0,
                "regime": "MANUAL_OPTION_REQUEST",
                "asset_class": "OPTION",
                "underlying": contract.get("underlying"),
                "strike": contract.get("strike"),
                "option_type": contract.get("option_type"),
                "expiry": contract.get("expiry"),
                "provider_symbol": provider_symbol,
                "maximum_premium_risk": premium * _number(quantity),
            },
        )
        position = next(
            (
                item for item in (result.get("state") or {}).get("positions", [])
                if item.get("symbol") == provider_symbol
            ),
            {},
        )
        result["result"] = {
            **(result.get("result") or {}),
            "stop_loss": position.get("stop_loss", stop_loss),
            "take_profit": position.get("take_profit", take_profit),
        }
        result["contract"] = dict(contract)
        return result

    def close_all(self) -> dict[str, Any]:
        with self._lock:
            symbols = list(self.broker.positions)
        results = []
        for symbol in symbols:
            results.append(self.close_position(symbol, reason="PAPER_FLATTEN_ALL"))
        return {"ok": True, "paper_only": True, "closed": len(results), "state": self.public_state()}

    def scan_once(self) -> dict[str, Any]:
        market = self.market_data.status() if self.market_data is not None else self.market_runtime.status()
        if self.market_data is None and not market.get("connected"):
            with self._lock:
                self._last_scan = _now()
                self._last_error = "Paper autopilot is waiting for the live FYERS data socket."
                self._record("WAITING", self._last_error)
                self._save()
                return self.public_state()

        for symbol in self.symbols:
            if self.market_data is not None and not self.market_data.session_open(symbol):
                with self._lock:
                    metadata = ASSET_UNIVERSE.get(symbol, {})
                    self._signals[symbol] = {
                        "symbol": symbol,
                        "timestamp": _now(),
                        "success": False,
                        "setup": "SESSION_CLOSED",
                        "confidence": 0,
                        "regime": "CLOSED",
                        "asset_class": metadata.get("asset_class", "ASSET"),
                        "currency": metadata.get("currency", "INR"),
                        "message": "This asset's configured market session is closed.",
                    }
                continue
            quote = self._live_quote(symbol)
            price = _number(quote.get("valuation_ltp"))
            native_price = _number(quote.get("native_ltp"), price)
            if not quote.get("success") or price <= 0:
                with self._lock:
                    self._signals[symbol] = {
                        "symbol": symbol,
                        "timestamp": _now(),
                        "success": False,
                        "setup": "DATA_UNAVAILABLE",
                        "confidence": 0,
                        "regime": "UNKNOWN",
                        "message": quote.get("message") or "Market quote unavailable.",
                    }
                continue
            intelligence = self.analyzer(symbol)
            signal = {
                "symbol": symbol,
                "timestamp": intelligence.get("timestamp") or _now(),
                "success": bool(intelligence.get("success")),
                "setup": intelligence.get("setup") or "NO_QUALIFIED_SETUP",
                "confidence": intelligence.get("confidence", 0),
                "regime": intelligence.get("regime") or "UNKNOWN",
                "price": native_price,
                "valuation_price": price,
                "currency": quote.get("currency") or "INR",
                "asset_class": quote.get("asset_class") or "INDEX",
                "provider": quote.get("source") or quote.get("provider") or "FYERS",
                "provider_symbol": quote.get("provider_symbol") or symbol,
                "strategy": intelligence.get("strategy") or "NO_EDGE",
                "strategy_score": intelligence.get("strategy_score", 0),
                "chart_patterns": intelligence.get("chart_patterns") or [],
                "risk_reward": intelligence.get("risk_reward", 0),
                "stop_loss": intelligence.get("stop_loss"),
                "take_profit": intelligence.get("take_profit"),
                "decision_gate": intelligence.get("decision_gate") or "WAIT",
            }
            policy = self.learning.policy(str(signal["strategy"]))
            signal["adaptive_policy"] = policy
            with self._lock:
                self._update_broker_price(symbol, price)
                self._signals[symbol] = signal
                position = self.broker.positions.get(symbol)
                if position and (position.stop_loss is None or position.take_profit is None):
                    native_atr = _number(intelligence.get("atr14"))
                    conversion = price / native_price if native_price else 1.0
                    risk_distance = native_atr * conversion * 1.5
                    if risk_distance > 0:
                        position.stop_loss = (
                            price - risk_distance if position.side == "LONG" else price + risk_distance
                        )
                        position.take_profit = (
                            price + risk_distance * 2.2 if position.side == "LONG" else price - risk_distance * 2.2
                        )
                        self.learning.remember_entry(
                            symbol,
                            {
                                "strategy": intelligence.get("strategy") or "LEGACY_REPAIRED",
                                "patterns": intelligence.get("chart_patterns") or [],
                                "confidence": intelligence.get("confidence", 0),
                                "risk_reward": 2.2,
                                "regime": intelligence.get("regime"),
                                "entry_price": position.average_price,
                                "stop_loss": position.stop_loss,
                                "take_profit": position.take_profit,
                                "quantity": position.quantity,
                                "asset_class": quote.get("asset_class"),
                                "opened_at": position.opened_at,
                            },
                        )
                        self._record(
                            "RISK_REPAIR",
                            f"Added a synthetic protective stop and target to legacy {symbol} position.",
                            symbol=symbol,
                        )
                if position and symbol not in self.learning.entry_context:
                    initial_risk = abs(position.average_price - _number(position.stop_loss))
                    reward = abs(_number(position.take_profit) - position.average_price)
                    self.learning.remember_entry(
                        symbol,
                        {
                            "strategy": "UNCLASSIFIED",
                            "patterns": [],
                            "confidence": 0,
                            "risk_reward": reward / initial_risk if initial_risk > 0 else 0,
                            "regime": "LEGACY_POSITION",
                            "entry_price": position.average_price,
                            "stop_loss": position.stop_loss,
                            "take_profit": position.take_profit,
                            "quantity": position.quantity,
                            "asset_class": quote.get("asset_class"),
                            "opened_at": position.opened_at,
                        },
                    )
                    self._record(
                        "LEARNING_REPAIR",
                        f"Backfilled an unclassified learning record for legacy {symbol} position.",
                        symbol=symbol,
                    )
            setup = str(signal["setup"])
            if (
                not self._autopilot
                or _number(signal["confidence"]) < 80
                or _number(signal["risk_reward"]) < 1.8
                or not policy["allowed"]
            ):
                continue
            desired = "LONG" if setup == "PAPER_WATCH_LONG" else "SHORT" if setup == "PAPER_WATCH_SHORT" else ""
            if not desired:
                continue
            with self._lock:
                position = self.broker.positions.get(symbol)
                last_action = self._last_action_at.get(symbol, 0.0)
            if time.monotonic() - last_action < 300:
                continue
            if position and position.side == desired:
                continue
            account = self.broker.account_summary()
            if _number(account.get("total_pnl")) <= -self.broker.starting_capital * 0.02:
                with self._lock:
                    self._autopilot = False
                    self._last_error = "Paper autopilot hit the 2% portfolio loss halt and was paused."
                    self._record("RISK_HALT", self._last_error)
                    self._save()
                break
            if not position and len(self.broker.positions) >= 6:
                continue
            if position:
                self.close_position(symbol, reason="PAPER_AUTOPILOT_REVERSAL_EXIT")
            else:
                native_stop = _number(intelligence.get("stop_loss"))
                conversion = price / native_price if native_price else 1.0
                risk_distance = abs(native_price - native_stop) * conversion if native_stop else 0.0
                if risk_distance <= 0:
                    with self._lock:
                        self._record("SKIPPED", f"{symbol} has no validated initial risk distance.", symbol=symbol)
                    continue
                equity = _number(account.get("equity"), self.broker.starting_capital)
                risk_budget = equity * 0.0035 * _number(policy["risk_multiplier"], 1.0)
                target_notional = min(
                    self.broker.starting_capital * 0.05 * _number(policy["risk_multiplier"], 1.0),
                    self.broker.available_exposure(),
                )
                quantity = min(round(risk_budget / risk_distance, 6), round(target_notional / price, 6), 10.0)
                if quantity < 0.0001:
                    with self._lock:
                        self._record(
                            "SKIPPED",
                            f"{symbol} paper entry skipped because synthetic exposure is full.",
                            symbol=symbol,
                        )
                    continue
                try:
                    stop_loss = (
                        price - risk_distance if desired == "LONG" else price + risk_distance
                    ) if risk_distance > 0 else None
                    take_profit = (
                        price + risk_distance * _number(intelligence.get("risk_reward"), 2.2)
                        if desired == "LONG" else price - risk_distance * _number(intelligence.get("risk_reward"), 2.2)
                    ) if risk_distance > 0 else None
                    self.place_order(
                        symbol,
                        "BUY" if desired == "LONG" else "SELL",
                        quantity,
                        reason=f"PAPER_AUTOPILOT_{setup}",
                        price=price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        decision_context={
                            "strategy": intelligence.get("strategy") or "NO_EDGE",
                            "patterns": intelligence.get("chart_patterns") or [],
                            "confidence": intelligence.get("confidence", 0),
                            "risk_reward": intelligence.get("risk_reward", 0),
                            "regime": intelligence.get("regime"),
                            "asset_class": quote.get("asset_class"),
                        },
                    )
                except RuntimeError as error:
                    with self._lock:
                        self._record("SKIPPED", str(error), symbol=symbol)
                    continue
            with self._lock:
                self._last_action_at[symbol] = time.monotonic()

        with self._lock:
            self._last_scan = _now()
            if self._autopilot:
                self._last_error = None
            self._save()
            return self.public_state()


    def health_status(self) -> dict[str, Any]:
        """
        Return a minimal non-blocking snapshot for liveness endpoints.

        This intentionally avoids building the full public_state payload.
        """
        with self._lock:
            return {
                "paper_only": True,
                "live_orders": False,
                "running": bool(getattr(self, "_running", False)),
                "autopilot": bool(getattr(self, "_autopilot", False)),
            }

    def public_state(self) -> dict[str, Any]:
        with self._lock:
            self._sync_marks()
            account = self.broker.account_summary()
            positions = self.broker.get_positions()
            market = self.market_data.status() if self.market_data is not None else self.market_runtime.status()
            for position in positions:
                metadata = ASSET_UNIVERSE.get(position["symbol"], {})
                quote = self._latest_quotes.get(position["symbol"], {})
                position.update(
                    {
                        "asset_class": quote.get("asset_class") or metadata.get("asset_class", "INDEX"),
                        "label": quote.get("description") or metadata.get("label", position["symbol"]),
                        "native_currency": quote.get("currency") or metadata.get("currency", "INR"),
                        "native_ltp": quote.get("native_ltp"),
                        "provider": quote.get("provider") or metadata.get("provider", "FYERS"),
                    }
                )
            providers = market.get("providers") or {
                "FYERS": {"ready": bool(market.get("connected")), "error": market.get("error")}
            }
            return {
                "mode": "AUTONOMOUS_MULTI_ASSET_PAPER",
                "paper_only": True,
                "live_orders": False,
                "running": self._running,
                "autopilot": self._autopilot,
                "auto_arm_on_start": self.auto_arm_on_start,
                "market_connected": any(bool(item.get("ready")) for item in providers.values()),
                "market_provider": "FYERS + BINANCE PUBLIC",
                "providers": providers,
                "universe": (
                    self.market_data.public_universe()
                    if self.market_data is not None
                    else [{"symbol": symbol, **ASSET_UNIVERSE[symbol]} for symbol in self.symbols]
                ),
                "last_scan": self._last_scan,
                "last_error": self._last_error,
                "account": account,
                "positions": positions,
                "orders": self.broker.get_orders()[-50:][::-1],
                "trades": self.broker.get_trades()[-50:][::-1],
                "signals": [self._signals[key] for key in sorted(self._signals)],
                "activity": self._activity[-50:][::-1],
                "learning": self.learning.snapshot(),
                "guardrails": {
                    "starting_capital": self.broker.starting_capital,
                    "max_leverage": self.broker.max_leverage,
                    "max_order_quantity": 100,
                    "autopilot_min_confidence": 80,
                    "autopilot_cooldown_seconds": 300,
                    "max_open_positions": 6,
                    "portfolio_loss_halt_percent": 2,
                    "position_target_percent": 5,
                    "risk_per_trade_percent": 0.35,
                    "minimum_risk_reward": 1.8,
                    "strategy_cooldown_after_losses": 3,
                    "strategy_cooldown_hours": 24,
                    "long_options_only": True,
                    "naked_option_selling": False,
                    "manual_option_stop_percent": 50,
                    "manual_option_risk_reward": 2.0,
                    "requires_live_market_price": True,
                    "session_gating": True,
                    "auto_arm_on_start": self.auto_arm_on_start,
                },
            }


PAPER_RUNTIME = PaperTradingRuntime()
