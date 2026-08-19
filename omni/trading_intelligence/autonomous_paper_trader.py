from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from omni.trading_intelligence.quant_firm_engine import decide, position_size


@dataclass(frozen=True)
class PaperOrderIntent:
    symbol: str
    timeframe: str
    side: str
    quantity: int
    entry: float
    stop: float
    target: float
    score: float
    regime: str
    created_at: str
    status: str = "PAPER_INTENT"
    live_execution: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutonomousPaperTrader:
    """Research-only autonomous coordinator.

    It can turn a validated quant decision into a synthetic paper intent. It has
    no broker order method and intentionally cannot place live orders.
    """

    def __init__(
        self,
        *,
        equity: float = 100000.0,
        risk_fraction: float = 0.005,
        min_score: float = 64.0,
        max_open_positions: int = 4,
        max_daily_loss_fraction: float = 0.02,
    ) -> None:
        self.equity = float(equity)
        self.risk_fraction = float(risk_fraction)
        self.min_score = float(min_score)
        self.max_open_positions = int(max_open_positions)
        self.max_daily_loss_fraction = float(max_daily_loss_fraction)
        self.open_positions: dict[str, PaperOrderIntent] = {}
        self.closed_pnl = 0.0

    @property
    def live_execution(self) -> bool:
        return False

    def can_open(self) -> tuple[bool, str]:
        if len(self.open_positions) >= self.max_open_positions:
            return False, "MAX_OPEN_POSITIONS"
        if self.closed_pnl <= -(self.equity * self.max_daily_loss_fraction):
            return False, "DAILY_LOSS_LOCK"
        return True, "OK"

    def evaluate(self, symbol: str, timeframe: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
        decision = decide(symbol, timeframe, candles)
        allowed, reason = self.can_open()
        result = {
            "decision": decision.to_dict(),
            "paper_intent": None,
            "risk_gate": reason,
            "paper_only": True,
            "live_execution": False,
        }
        if not allowed:
            return result
        if decision.side not in {"LONG", "SHORT"}:
            result["risk_gate"] = "NO_DIRECTIONAL_EDGE"
            return result
        if decision.score < self.min_score:
            result["risk_gate"] = "SCORE_BELOW_GATE"
            return result
        if None in {decision.entry, decision.stop, decision.target}:
            result["risk_gate"] = "LEVELS_UNAVAILABLE"
            return result
        if symbol in self.open_positions:
            result["risk_gate"] = "POSITION_ALREADY_OPEN"
            return result

        quantity = position_size(
            self.equity,
            float(decision.entry),
            float(decision.stop),
            risk_fraction=self.risk_fraction,
        )
        if quantity <= 0:
            result["risk_gate"] = "POSITION_SIZE_ZERO"
            return result

        intent = PaperOrderIntent(
            symbol=str(symbol).upper(),
            timeframe=str(timeframe),
            side=decision.side,
            quantity=quantity,
            entry=float(decision.entry),
            stop=float(decision.stop),
            target=float(decision.target),
            score=float(decision.score),
            regime=decision.regime,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.open_positions[intent.symbol] = intent
        result["paper_intent"] = intent.to_dict()
        result["risk_gate"] = "PAPER_INTENT_CREATED"
        return result

    def mark_exit(self, symbol: str, exit_price: float) -> dict[str, Any]:
        key = str(symbol).upper()
        intent = self.open_positions.pop(key, None)
        if intent is None:
            return {"success": False, "message": "No open paper position.", "live_execution": False}
        direction = 1.0 if intent.side == "LONG" else -1.0
        pnl = (float(exit_price) - intent.entry) * direction * intent.quantity
        self.closed_pnl += pnl
        return {
            "success": True,
            "symbol": key,
            "paper_pnl": pnl,
            "closed_pnl": self.closed_pnl,
            "live_execution": False,
        }

    def scan_universe(
        self,
        universe: Iterable[str],
        timeframe: str,
        candle_loader: Callable[[str, str], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        results = []
        for symbol in universe:
            try:
                candles = candle_loader(str(symbol), str(timeframe))
                results.append({"symbol": str(symbol), **self.evaluate(str(symbol), timeframe, candles)})
            except Exception as exc:
                results.append(
                    {
                        "symbol": str(symbol),
                        "error": str(exc)[:300],
                        "paper_only": True,
                        "live_execution": False,
                    }
                )
        return results
