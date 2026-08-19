from __future__ import annotations

"""Autonomous paper-only supervisor for JARVIS Quant V3.

The supervisor consumes local live snapshots plus cached candles, runs the
regime-aware strategy ensemble, applies portfolio risk gates, and manages
virtual positions.  It contains no broker-order API.  Option positions are
premium-defined paper positions using normalized contract units until a
provider lot-size model is explicitly available.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Iterable

from omni.trading_intelligence.quant_v3_strategy_engine import evaluate_strategies


SnapshotLoader = Callable[[str], dict[str, Any]]
CandleLoader = Callable[[str, str, int], dict[str, Any]]
OptionLoader = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class AutopilotConfig:
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.005
    option_risk_per_trade: float = 0.0025
    max_daily_loss_pct: float = 0.02
    max_portfolio_drawdown_pct: float = 0.06
    max_positions: int = 4
    max_notional_pct_per_symbol: float = 0.30
    min_timeframe_agreement: float = 2.0 / 3.0
    min_ensemble_confidence: float = 0.32
    minimum_rr: float = 1.6
    target_rr: float = 2.0
    slippage_bps: float = 2.0
    fixed_fee: float = 0.0
    cooldown_seconds: float = 180.0
    local_cycle_seconds: float = 0.25
    history_refresh_seconds: float = 8.0
    option_refresh_seconds: float = 10.0
    options_enabled: bool = True

    def __post_init__(self):
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.risk_per_trade <= 0.05:
            raise ValueError("risk_per_trade must be between 0 and 5%")
        if not 0 < self.option_risk_per_trade <= 0.05:
            raise ValueError("option_risk_per_trade must be between 0 and 5%")
        if self.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if self.local_cycle_seconds < 0.05:
            raise ValueError("local_cycle_seconds cannot be below 50ms")


@dataclass
class PaperPosition:
    symbol: str
    instrument: str
    side: str
    entry_price: float
    quantity: float
    stop_price: float
    target_price: float
    opened_at: str
    strategy: str
    confidence: float
    regime: str
    option_symbol: str | None = None
    option_type: str | None = None
    normalized_unit_model: bool = False
    highest_price: float | None = None
    lowest_price: float | None = None
    unrealized_pnl: float = 0.0


@dataclass
class SymbolRuntime:
    candles: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    history_loaded_at: float = 0.0
    option_context: dict[str, Any] | None = None
    option_loaded_at: float = 0.0
    last_decision: dict[str, Any] | None = None
    last_snapshot: dict[str, Any] | None = None


class QuantV3Autopilot:
    """Thread-safe autonomous virtual execution coordinator."""

    PAPER_ONLY = True
    LIVE_EXECUTION = False

    def __init__(self, config: AutopilotConfig | None = None, *, journal_path: str | Path | None = None):
        self.config = config or AutopilotConfig()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._kill_switch = False
        self._kill_reason: str | None = None
        self._symbols: tuple[str, ...] = ()
        self._snapshot_loader: SnapshotLoader | None = None
        self._candle_loader: CandleLoader | None = None
        self._option_loader: OptionLoader | None = None
        self._runtime: dict[str, SymbolRuntime] = {}
        self._positions: dict[str, PaperPosition] = {}
        self._closed_trades: list[dict[str, Any]] = []
        self._realized_pnl = 0.0
        self._peak_equity = self.config.initial_capital
        self._day_key = datetime.now(timezone.utc).date().isoformat()
        self._day_start_equity = self.config.initial_capital
        self._last_exit_monotonic: dict[str, float] = {}
        self._latency_samples_ms: list[float] = []
        self._cycles = 0
        self._errors: list[str] = []
        self._journal_path = Path(journal_path or Path("data") / "trading" / "quant_v3" / "autopilot.jsonl")

    def configure_loaders(
        self,
        *,
        snapshot_loader: SnapshotLoader,
        candle_loader: CandleLoader,
        option_loader: OptionLoader | None = None,
    ) -> None:
        with self._lock:
            self._snapshot_loader = snapshot_loader
            self._candle_loader = candle_loader
            self._option_loader = option_loader

    def _journal(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
            "paper_only": True,
            "live_execution": False,
            "broker_order": False,
        }
        try:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self._journal_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    @staticmethod
    def _snapshot_price(payload: dict[str, Any]) -> float | None:
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if not isinstance(snapshot, dict):
            snapshot = payload if isinstance(payload, dict) else None
        if not snapshot:
            return None
        try:
            value = float(snapshot.get("ltp"))
            return value if value > 0 else None
        except Exception:
            return None

    @staticmethod
    def _snapshot_dict(payload: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        snapshot = payload.get("snapshot")
        if isinstance(snapshot, dict):
            return dict(snapshot)
        return dict(payload) if payload.get("ltp") is not None else None

    def _equity(self, prices: dict[str, float] | None = None) -> float:
        equity = self.config.initial_capital + self._realized_pnl
        prices = prices or {}
        for symbol, position in self._positions.items():
            mark = prices.get(symbol)
            if mark is None:
                mark = position.entry_price
            direction = 1.0 if position.side == "LONG" else -1.0
            equity += (float(mark) - position.entry_price) * direction * position.quantity
        return equity

    def _reset_day_if_needed(self, equity: float) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._day_key:
            self._day_key = today
            self._day_start_equity = equity

    def _risk_state(self, prices: dict[str, float] | None = None) -> dict[str, Any]:
        equity = self._equity(prices)
        self._reset_day_if_needed(equity)
        self._peak_equity = max(self._peak_equity, equity)
        daily_pnl = equity - self._day_start_equity
        daily_loss_pct = max(0.0, -daily_pnl / max(self._day_start_equity, 1.0))
        drawdown_pct = max(0.0, (self._peak_equity - equity) / max(self._peak_equity, 1.0))
        blocked_reason = None
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            blocked_reason = "daily_loss_limit"
        elif drawdown_pct >= self.config.max_portfolio_drawdown_pct:
            blocked_reason = "portfolio_drawdown_limit"
        elif len(self._positions) >= self.config.max_positions:
            blocked_reason = "max_positions"
        return {
            "equity": equity,
            "realized_pnl": self._realized_pnl,
            "daily_pnl": daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "drawdown_pct": drawdown_pct,
            "open_positions": len(self._positions),
            "blocked_reason": blocked_reason,
        }

    @staticmethod
    def _bucket(epoch: float, timeframe: str) -> int:
        seconds = {"1m": 60, "5m": 300, "15m": 900}.get(timeframe, 300)
        return int(epoch // seconds * seconds)

    def _apply_tick_to_candles(self, runtime: SymbolRuntime, snapshot: dict[str, Any]) -> None:
        try:
            price = float(snapshot["ltp"])
        except Exception:
            return
        raw_time = snapshot.get("exchange_timestamp") or time.time()
        try:
            epoch = float(raw_time)
            if epoch > 1e12:
                epoch /= 1000.0
        except Exception:
            epoch = time.time()
        volume = float(snapshot.get("volume") or 0.0)
        for timeframe, rows in runtime.candles.items():
            if not rows:
                continue
            bucket = self._bucket(epoch, timeframe)
            last = rows[-1]
            last_time = int(float(last.get("time", last.get("timestamp", 0)) or 0))
            if last_time == bucket:
                last["high"] = max(float(last["high"]), price)
                last["low"] = min(float(last["low"]), price)
                last["close"] = price
                if volume > 0:
                    last["volume"] = volume
            elif bucket > last_time:
                previous_close = float(last["close"])
                rows.append(
                    {
                        "time": bucket,
                        "timestamp": bucket,
                        "open": previous_close,
                        "high": max(previous_close, price),
                        "low": min(previous_close, price),
                        "close": price,
                        "volume": volume,
                    }
                )
                if len(rows) > 500:
                    del rows[:-500]

    def _refresh_history(self, symbol: str, runtime: SymbolRuntime) -> bool:
        loader = self._candle_loader
        if loader is None:
            return False
        now = time.monotonic()
        if runtime.candles and now - runtime.history_loaded_at < self.config.history_refresh_seconds:
            return True
        loaded: dict[str, list[dict[str, Any]]] = {}
        for timeframe in ("1m", "5m", "15m"):
            payload = loader(symbol, timeframe, 300)
            candles = list(payload.get("candles") or ()) if isinstance(payload, dict) else []
            if len(candles) >= 55:
                loaded[timeframe] = [dict(row) for row in candles]
        if not loaded:
            return False
        runtime.candles.update(loaded)
        runtime.history_loaded_at = now
        return True

    def _refresh_options(self, symbol: str, runtime: SymbolRuntime) -> None:
        if not self.config.options_enabled or self._option_loader is None:
            return
        now = time.monotonic()
        if now - runtime.option_loaded_at < self.config.option_refresh_seconds:
            return
        try:
            result = self._option_loader(symbol)
            if isinstance(result, dict) and result.get("success"):
                runtime.option_context = result
                runtime.option_loaded_at = now
        except Exception as exc:
            self._errors.append(f"{symbol} options: {type(exc).__name__}: {exc}"[:300])

    @staticmethod
    def _option_confirmation(context: dict[str, Any] | None) -> dict[str, Any] | None:
        if not context:
            return None
        confirmation = context.get("confirmation")
        return dict(confirmation) if isinstance(confirmation, dict) else None

    def _decision(self, symbol: str, runtime: SymbolRuntime) -> dict[str, Any] | None:
        evaluations = []
        option_confirmation = self._option_confirmation(runtime.option_context)
        for timeframe in ("1m", "5m", "15m"):
            rows = runtime.candles.get(timeframe)
            if not rows or len(rows) < 55:
                continue
            result = evaluate_strategies(
                rows,
                symbol=symbol,
                timeframe=timeframe,
                option_context=option_confirmation,
            )
            if result.get("success"):
                evaluations.append(result)
        if not evaluations:
            return None
        long_count = sum(item["consensus"] == "LONG" for item in evaluations)
        short_count = sum(item["consensus"] == "SHORT" for item in evaluations)
        total = len(evaluations)
        if long_count > short_count:
            consensus = "LONG"
            agreement = long_count / total
        elif short_count > long_count:
            consensus = "SHORT"
            agreement = short_count / total
        else:
            consensus = "FLAT"
            agreement = 0.0
        matching = [item for item in evaluations if item["consensus"] == consensus]
        confidence = sum(float(item.get("confidence") or 0.0) for item in matching) / max(len(matching), 1)
        anchor = next((item for item in evaluations if item["timeframe"] == "5m"), evaluations[0])
        return {
            "symbol": symbol,
            "consensus": consensus,
            "timeframe_agreement": agreement,
            "confidence": confidence,
            "regime": anchor.get("regime"),
            "anchor": anchor,
            "evaluations": evaluations,
            "paper_only": True,
            "live_execution": False,
        }

    def _fill(self, price: float, side: str, entering: bool) -> float:
        bps = self.config.slippage_bps / 10_000.0
        if (side == "LONG" and entering) or (side == "SHORT" and not entering):
            return price * (1.0 + bps)
        return price * (1.0 - bps)

    def _quantity(self, equity: float, price: float, stop_distance: float) -> float:
        risk_budget = max(0.0, equity * self.config.risk_per_trade)
        by_risk = risk_budget / max(stop_distance, price * 0.001)
        notional_cap = max(0.0, equity * self.config.max_notional_pct_per_symbol)
        by_notional = notional_cap / max(price, 1e-9)
        return max(0.0, min(by_risk, by_notional))

    def _open_underlying(self, symbol: str, decision: dict[str, Any], price: float, risk: dict[str, Any]) -> dict[str, Any] | None:
        anchor = decision["anchor"]
        atr = float(anchor.get("features", {}).get("atr14") or 0.0)
        if atr <= 0:
            return None
        side = decision["consensus"]
        stop_distance = max(atr, price * 0.002)
        quantity = self._quantity(float(risk["equity"]), price, stop_distance)
        if quantity <= 0:
            return None
        entry = self._fill(price, side, True)
        if side == "LONG":
            stop = entry - stop_distance
            target = entry + stop_distance * self.config.target_rr
        else:
            stop = entry + stop_distance
            target = entry - stop_distance * self.config.target_rr
        position = PaperPosition(
            symbol=symbol,
            instrument="UNDERLYING",
            side=side,
            entry_price=entry,
            quantity=quantity,
            stop_price=stop,
            target_price=target,
            opened_at=datetime.now(timezone.utc).isoformat(),
            strategy="quant_v3_regime_ensemble",
            confidence=float(decision["confidence"]),
            regime=str(decision.get("regime") or "UNKNOWN"),
            highest_price=entry,
            lowest_price=entry,
        )
        self._positions[symbol] = position
        payload = {"action": "PAPER_OPEN", "position": asdict(position), "paper_only": True, "live_execution": False}
        self._journal("paper_open", payload)
        return payload

    def _select_option_contract(self, context: dict[str, Any] | None, side: str) -> dict[str, Any] | None:
        if not context:
            return None
        rows = context.get("legs") or context.get("contracts") or ()
        if not rows:
            return None
        desired = {"LONG": {"CE", "CALL"}, "SHORT": {"PE", "PUT"}}[side]
        spot = float(context.get("spot") or 0.0)
        candidates = []
        for row in rows:
            option_type = str(row.get("option_type") or "").upper()
            if option_type not in desired:
                continue
            strike = row.get("strike")
            ltp = row.get("ltp", row.get("premium"))
            if strike is None or ltp is None:
                continue
            premium = float(ltp)
            if premium <= 0:
                continue
            bid, ask = row.get("bid"), row.get("ask")
            spread_pct = None
            if bid is not None and ask is not None:
                mid = (float(bid) + float(ask)) / 2.0
                spread_pct = (float(ask) - float(bid)) / mid if mid > 0 else None
            if spread_pct is not None and spread_pct > 0.08:
                continue
            candidates.append((abs(float(strike) - spot), row, premium, spread_pct))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return dict(candidates[0][1])

    def _open_option(self, symbol: str, decision: dict[str, Any], risk: dict[str, Any], runtime: SymbolRuntime) -> dict[str, Any] | None:
        contract = self._select_option_contract(runtime.option_context, decision["consensus"])
        if not contract:
            return None
        premium = float(contract.get("ask") or contract.get("ltp") or contract.get("premium") or 0.0)
        if premium <= 0:
            return None
        risk_budget = float(risk["equity"]) * self.config.option_risk_per_trade
        quantity = max(1.0, min(10.0, risk_budget / max(premium, 1e-9)))
        # Normalized premium units: provider lot size is intentionally not
        # invented.  This keeps the option paper model bounded and explicit.
        side = decision["consensus"]
        stop = premium * 0.65
        target = premium * 1.70
        position = PaperPosition(
            symbol=symbol,
            instrument="OPTION_LONG_PREMIUM",
            side="LONG",
            entry_price=premium,
            quantity=quantity,
            stop_price=stop,
            target_price=target,
            opened_at=datetime.now(timezone.utc).isoformat(),
            strategy="quant_v3_option_directional",
            confidence=float(decision["confidence"]),
            regime=str(decision.get("regime") or "UNKNOWN"),
            option_symbol=str(contract.get("symbol") or contract.get("name") or ""),
            option_type="CALL" if side == "LONG" else "PUT",
            normalized_unit_model=True,
            highest_price=premium,
            lowest_price=premium,
        )
        self._positions[symbol] = position
        payload = {
            "action": "PAPER_OPTION_OPEN",
            "position": asdict(position),
            "defined_risk": True,
            "naked_short": False,
            "paper_only": True,
            "live_execution": False,
        }
        self._journal("paper_option_open", payload)
        return payload

    def _option_mark(self, position: PaperPosition, context: dict[str, Any] | None) -> float | None:
        if not context or not position.option_symbol:
            return None
        rows = context.get("legs") or context.get("contracts") or ()
        for row in rows:
            name = str(row.get("symbol") or row.get("name") or "")
            if name != position.option_symbol:
                continue
            value = row.get("bid") or row.get("ltp") or row.get("premium")
            try:
                mark = float(value)
                return mark if mark > 0 else None
            except Exception:
                return None
        return None

    def _close_position(self, symbol: str, mark: float, reason: str) -> dict[str, Any]:
        position = self._positions.pop(symbol)
        exit_price = self._fill(mark, position.side, False) if position.instrument == "UNDERLYING" else mark
        direction = 1.0 if position.side == "LONG" else -1.0
        pnl = (exit_price - position.entry_price) * direction * position.quantity - self.config.fixed_fee
        self._realized_pnl += pnl
        trade = {
            **asdict(position),
            "exit_price": exit_price,
            "exit_time": datetime.now(timezone.utc).isoformat(),
            "exit_reason": reason,
            "net_pnl": pnl,
            "paper_only": True,
            "broker_order": False,
            "live_execution": False,
        }
        self._closed_trades.append(trade)
        self._closed_trades = self._closed_trades[-1000:]
        self._last_exit_monotonic[symbol] = time.monotonic()
        self._journal("paper_close", trade)
        return {"action": "PAPER_CLOSE", "trade": trade, "paper_only": True, "live_execution": False}

    def _manage_position(self, symbol: str, price: float, decision: dict[str, Any] | None, runtime: SymbolRuntime) -> dict[str, Any] | None:
        position = self._positions.get(symbol)
        if not position:
            return None
        mark = price
        if position.instrument == "OPTION_LONG_PREMIUM":
            option_mark = self._option_mark(position, runtime.option_context)
            if option_mark is None:
                return None
            mark = option_mark
        position.highest_price = max(float(position.highest_price or mark), mark)
        position.lowest_price = min(float(position.lowest_price or mark), mark)
        direction = 1.0 if position.side == "LONG" else -1.0
        position.unrealized_pnl = (mark - position.entry_price) * direction * position.quantity
        if mark <= position.stop_price if position.side == "LONG" else mark >= position.stop_price:
            return self._close_position(symbol, mark, "stop_loss")
        if mark >= position.target_price if position.side == "LONG" else mark <= position.target_price:
            return self._close_position(symbol, mark, "target")
        if decision and decision["consensus"] in {"LONG", "SHORT"}:
            if position.instrument == "UNDERLYING" and decision["consensus"] != position.side:
                return self._close_position(symbol, mark, "opposite_ensemble")
            if position.instrument == "OPTION_LONG_PREMIUM":
                desired_option = "CALL" if decision["consensus"] == "LONG" else "PUT"
                if desired_option != position.option_type:
                    return self._close_position(symbol, mark, "opposite_option_ensemble")
        return None

    def process_symbol(self, symbol: str) -> dict[str, Any]:
        started = time.perf_counter_ns()
        runtime = self._runtime.setdefault(symbol, SymbolRuntime())
        if self._snapshot_loader is None:
            return {"success": False, "symbol": symbol, "reason": "snapshot_loader_missing"}
        snapshot_payload = self._snapshot_loader(symbol)
        snapshot = self._snapshot_dict(snapshot_payload)
        price = self._snapshot_price(snapshot_payload)
        if snapshot is None or price is None:
            return {"success": False, "symbol": symbol, "reason": "live_snapshot_unavailable"}
        runtime.last_snapshot = snapshot
        if not self._refresh_history(symbol, runtime):
            return {"success": False, "symbol": symbol, "reason": "history_unavailable"}
        self._apply_tick_to_candles(runtime, snapshot)
        self._refresh_options(symbol, runtime)
        decision = self._decision(symbol, runtime)
        runtime.last_decision = decision

        action = self._manage_position(symbol, price, decision, runtime)
        risk = self._risk_state({symbol: price})
        if action is None and decision and decision["consensus"] in {"LONG", "SHORT"}:
            blocked = risk.get("blocked_reason")
            cooldown = time.monotonic() - self._last_exit_monotonic.get(symbol, -1e9) < self.config.cooldown_seconds
            eligible = (
                not self._kill_switch
                and not blocked
                and symbol not in self._positions
                and not cooldown
                and decision["timeframe_agreement"] >= self.config.min_timeframe_agreement
                and decision["confidence"] >= self.config.min_ensemble_confidence
            )
            if eligible:
                option_eligible = self.config.options_enabled and symbol in {"NIFTY", "BANKNIFTY", "SENSEX", "BTC", "ETH"}
                action = self._open_option(symbol, decision, risk, runtime) if option_eligible else None
                if action is None:
                    action = self._open_underlying(symbol, decision, price, risk)

        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        self._latency_samples_ms.append(elapsed_ms)
        self._latency_samples_ms = self._latency_samples_ms[-1000:]
        self._cycles += 1
        return {
            "success": True,
            "symbol": symbol,
            "price": price,
            "decision": decision,
            "action": action,
            "risk": risk,
            "cycle_latency_ms": round(elapsed_ms, 3),
            "paper_only": True,
            "live_execution": False,
        }

    def _loop(self) -> None:
        while not self._stop_event.wait(self.config.local_cycle_seconds):
            if self._kill_switch:
                continue
            for symbol in self._symbols:
                try:
                    self.process_symbol(symbol)
                except Exception as exc:
                    with self._lock:
                        self._errors.append(f"{symbol}: {type(exc).__name__}: {exc}"[:300])
                        self._errors = self._errors[-100:]
        with self._lock:
            self._running = False

    def start(self, symbols: Iterable[str]) -> dict[str, Any]:
        clean = tuple(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        if not clean:
            raise ValueError("At least one symbol is required for Quant V3 autopilot.")
        with self._lock:
            if self._snapshot_loader is None or self._candle_loader is None:
                raise RuntimeError("Quant V3 autopilot data loaders are not configured.")
            self._symbols = clean
            self._kill_switch = False
            self._kill_reason = None
            if self._running:
                return self.status()
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="jarvis-quant-v3-autopilot", daemon=True)
            self._thread.start()
        self._journal("autopilot_start", {"symbols": clean})
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            self._running = False
            self._thread = None
        self._journal("autopilot_stop", {})
        return self.status()

    def kill(self, reason: str = "manual") -> dict[str, Any]:
        with self._lock:
            self._kill_switch = True
            self._kill_reason = str(reason)
        self._journal("autopilot_kill", {"reason": reason})
        return self.status()

    def resume(self) -> dict[str, Any]:
        with self._lock:
            self._kill_switch = False
            self._kill_reason = None
        self._journal("autopilot_resume", {})
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            latency = list(self._latency_samples_ms)
            runtime = {
                symbol: {
                    "last_decision": state.last_decision,
                    "last_snapshot": state.last_snapshot,
                    "options_available": bool(state.option_context),
                }
                for symbol, state in self._runtime.items()
            }
            positions = {symbol: asdict(position) for symbol, position in self._positions.items()}
            risk = self._risk_state()
            return {
                "running": self._running,
                "symbols": list(self._symbols),
                "kill_switch": self._kill_switch,
                "kill_reason": self._kill_reason,
                "positions": positions,
                "closed_trades": list(self._closed_trades[-50:]),
                "risk": risk,
                "cycles": self._cycles,
                "latency": {
                    "last_ms": round(latency[-1], 3) if latency else None,
                    "average_ms": round(sum(latency) / len(latency), 3) if latency else None,
                    "max_ms": round(max(latency), 3) if latency else None,
                },
                "runtime": runtime,
                "errors": list(self._errors[-20:]),
                "options_enabled": self.config.options_enabled,
                "option_execution_model": "normalized_premium_units_until_provider_lot_size_is_verified",
                "paper_only": True,
                "live_execution": False,
                "broker_order": False,
            }

    def __getattr__(self, name: str):
        lower = str(name).lower()
        if any(token in lower for token in ("broker_order", "place_order", "modify_order", "cancel_order", "live_execute")):
            raise PermissionError("Quant V3 autopilot cannot access live broker execution.")
        raise AttributeError(name)


quant_v3_autopilot = QuantV3Autopilot()
