"""Durable, deterministic learning ledger for synthetic paper trades.

This is policy adaptation, not model retraining.  It records the thesis that
opened each paper position, measures closed outcomes in risk units, and reduces
or pauses strategies with repeated losses.  It never grants live-order access.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import math
from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class PaperLearningLedger:
    """Track paper-trade experience and expose bounded adaptive policy."""

    def __init__(self) -> None:
        self.entry_context: dict[str, dict[str, Any]] = {}
        self.trade_reviews: list[dict[str, Any]] = []
        self.strategy_scorecards: dict[str, dict[str, Any]] = {}
        self.daily_reviews: dict[str, dict[str, Any]] = {}
        self.reviewed_trade_ids: set[str] = set()

    def load(self, payload: dict[str, Any] | None) -> None:
        data = payload if isinstance(payload, dict) else {}
        self.entry_context = {
            str(key).upper(): dict(value)
            for key, value in (data.get("entry_context") or {}).items()
            if isinstance(value, dict)
        }
        self.trade_reviews = [
            dict(item) for item in (data.get("trade_reviews") or [])[-500:]
            if isinstance(item, dict)
        ]
        raw_cards = data.get("strategy_scorecards") or {}
        if isinstance(raw_cards, list):
            raw_cards = {str(item.get("strategy")): item for item in raw_cards if isinstance(item, dict)}
        self.strategy_scorecards = {
            str(key): dict(value)
            for key, value in raw_cards.items()
            if isinstance(value, dict)
        }
        raw_days = data.get("daily_reviews") or {}
        if isinstance(raw_days, list):
            raw_days = {str(item.get("date")): item for item in raw_days if isinstance(item, dict)}
        self.daily_reviews = {
            str(key): dict(value)
            for key, value in raw_days.items()
            if isinstance(value, dict)
        }
        self.reviewed_trade_ids = {
            str(item.get("trade_id")) for item in self.trade_reviews if item.get("trade_id")
        }

    def remember_entry(self, symbol: str, context: dict[str, Any]) -> None:
        normalized = str(symbol or "").upper().replace(" ", "")
        if not normalized:
            return
        clean = {
            "symbol": normalized,
            "strategy": str(context.get("strategy") or "UNCLASSIFIED").upper(),
            "patterns": [str(item) for item in (context.get("patterns") or [])[:8]],
            "confidence": round(_number(context.get("confidence")), 2),
            "risk_reward": round(_number(context.get("risk_reward")), 3),
            "regime": str(context.get("regime") or "UNKNOWN").upper(),
            "entry_price": _number(context.get("entry_price")),
            "stop_loss": _number(context.get("stop_loss")) or None,
            "take_profit": _number(context.get("take_profit")) or None,
            "quantity": _number(context.get("quantity")),
            "asset_class": str(context.get("asset_class") or "ASSET").upper(),
            "opened_at": str(context.get("opened_at") or _iso(_utc_now())),
        }
        self.entry_context[normalized] = clean

    def policy(self, strategy: str) -> dict[str, Any]:
        key = str(strategy or "UNCLASSIFIED").upper()
        card = self.strategy_scorecards.get(key) or {}
        pause_until = _parse(card.get("pause_until"))
        paused = bool(pause_until and pause_until > _utc_now())
        consecutive_losses = int(card.get("consecutive_losses") or 0)
        average_r = _number(card.get("average_r"))
        multiplier = 1.0 - min(consecutive_losses, 3) * 0.20
        if average_r < 0:
            multiplier += max(average_r * 0.10, -0.20)
        elif average_r > 0:
            multiplier += min(average_r * 0.05, 0.10)
        multiplier = round(max(0.35, min(multiplier, 1.0)), 2)
        reason = (
            f"Paused until {_iso(pause_until)} after repeated paper losses."
            if paused and pause_until
            else f"Adaptive risk multiplier {multiplier:.2f} from {int(card.get('trades') or 0)} reviewed trade(s)."
        )
        return {
            "strategy": key,
            "allowed": not paused,
            "risk_multiplier": multiplier,
            "reason": reason,
        }

    def review_trade(self, trade: dict[str, Any], *, position_still_open: bool = False) -> dict[str, Any] | None:
        trade_id = str(trade.get("trade_id") or "")
        if not trade_id or trade_id in self.reviewed_trade_ids:
            return None
        symbol = str(trade.get("symbol") or "").upper()
        context = dict(self.entry_context.get(symbol) or {})
        strategy = str(context.get("strategy") or "UNCLASSIFIED").upper()
        net_pnl = _number(trade.get("net_pnl"))
        quantity = max(_number(trade.get("quantity")), 0.0)
        entry_price = _number(trade.get("entry_price"))
        stop_loss = _number(context.get("stop_loss"))
        initial_risk = abs(entry_price - stop_loss) * quantity if stop_loss and quantity else 0.0
        r_multiple = round(net_pnl / initial_risk, 3) if initial_risk > 0 else None
        outcome = "WIN" if net_pnl > 0 else "LOSS" if net_pnl < 0 else "FLAT"
        flags: list[str] = []
        if strategy == "UNCLASSIFIED":
            flags.append("ENTRY_THESIS_NOT_RECORDED")
        if not stop_loss:
            flags.append("NO_INITIAL_PROTECTIVE_STOP")
        if _number(context.get("risk_reward")) < 1.8:
            flags.append("RISK_REWARD_BELOW_POLICY")
        if _number(context.get("confidence")) < 80:
            flags.append("LOW_ALIGNMENT_AT_ENTRY")
        if not context.get("patterns"):
            flags.append("NO_PATTERN_CONFIRMATION")
        reason = str(trade.get("reason") or "UNKNOWN_EXIT").upper()
        if outcome == "LOSS" and reason == "STOP_LOSS":
            flags.append("THESIS_INVALIDATED_AT_STOP")
        if outcome == "LOSS" and reason.endswith("REVERSAL_EXIT"):
            flags.append("REGIME_REVERSED_BEFORE_TARGET")

        review = {
            "trade_id": trade_id,
            "timestamp": str(trade.get("closed_at") or _iso(_utc_now())),
            "symbol": symbol,
            "strategy": strategy,
            "patterns": context.get("patterns") or [],
            "outcome": outcome,
            "net_pnl": round(net_pnl, 2),
            "r_multiple": r_multiple,
            "exit_reason": reason,
            "review_flags": flags,
            "lesson": self._lesson(outcome, flags),
        }
        self.trade_reviews.append(review)
        self.trade_reviews = self.trade_reviews[-500:]
        self.reviewed_trade_ids.add(trade_id)
        self._update_scorecard(review)
        self._update_daily(review)
        if not position_still_open:
            self.entry_context.pop(symbol, None)
        return review

    @staticmethod
    def _lesson(outcome: str, flags: list[str]) -> str:
        if outcome == "WIN":
            return "Keep the recorded setup eligible; do not increase risk solely because one trade won."
        if "NO_INITIAL_PROTECTIVE_STOP" in flags:
            return "Do not repeat an unprotected entry; require a validated stop and target before the next fill."
        if "RISK_REWARD_BELOW_POLICY" in flags:
            return "Reject the next setup unless projected reward is at least 1.8 times initial risk."
        if "LOW_ALIGNMENT_AT_ENTRY" in flags:
            return "Require stronger multi-timeframe agreement before the next entry."
        return "Reduce strategy risk after this loss and wait for a fully qualified setup."

    def _update_scorecard(self, review: dict[str, Any]) -> None:
        strategy = review["strategy"]
        card = dict(self.strategy_scorecards.get(strategy) or {})
        trades = int(card.get("trades") or 0) + 1
        wins = int(card.get("wins") or 0) + (1 if review["outcome"] == "WIN" else 0)
        losses = int(card.get("losses") or 0) + (1 if review["outcome"] == "LOSS" else 0)
        consecutive_losses = (
            int(card.get("consecutive_losses") or 0) + 1
            if review["outcome"] == "LOSS" else 0
        )
        r_values = [
            _number(item.get("r_multiple"))
            for item in self.trade_reviews
            if item.get("strategy") == strategy and item.get("r_multiple") is not None
        ]
        average_r = round(sum(r_values) / len(r_values), 3) if r_values else 0.0
        pause_until = card.get("pause_until")
        status = "ELIGIBLE"
        if consecutive_losses >= 3 or (trades >= 5 and average_r < -0.15):
            pause_until = _iso(_utc_now() + timedelta(hours=24))
            status = "COOLING_OFF"
        elif (_parse(pause_until) or _utc_now()) > _utc_now():
            status = "COOLING_OFF"
        self.strategy_scorecards[strategy] = {
            "strategy": strategy,
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades * 100, 1),
            "net_pnl": round(_number(card.get("net_pnl")) + _number(review.get("net_pnl")), 2),
            "average_r": average_r,
            "consecutive_losses": consecutive_losses,
            "status": status,
            "pause_until": pause_until,
            "updated_at": _iso(_utc_now()),
        }

    def _update_daily(self, review: dict[str, Any]) -> None:
        parsed = _parse(review.get("timestamp")) or _utc_now()
        key = parsed.date().isoformat()
        relevant = [
            item for item in self.trade_reviews
            if ((_parse(item.get("timestamp")) or _utc_now()).date().isoformat() == key)
        ]
        flags = Counter(flag for item in relevant for flag in item.get("review_flags") or [])
        wins = sum(item.get("outcome") == "WIN" for item in relevant)
        losses = sum(item.get("outcome") == "LOSS" for item in relevant)
        net = round(sum(_number(item.get("net_pnl")) for item in relevant), 2)
        self.daily_reviews[key] = {
            "date": key,
            "trades": len(relevant),
            "wins": wins,
            "losses": losses,
            "net_pnl": net,
            "top_review_flags": [name for name, _count in flags.most_common(5)],
            "summary": (
                f"{len(relevant)} closed paper trade(s): {wins} win(s), {losses} loss(es), net P&L {net:,.2f}."
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        policies = {
            key: self.policy(key) for key in self.strategy_scorecards
        }
        return {
            "mode": "DETERMINISTIC_POLICY_ADAPTATION",
            "entry_context": dict(self.entry_context),
            "trade_reviews": list(self.trade_reviews[-100:]),
            "strategy_scorecards": [
                {**value, "policy": policies.get(key)}
                for key, value in sorted(self.strategy_scorecards.items())
            ],
            "daily_reviews": [
                self.daily_reviews[key] for key in sorted(self.daily_reviews, reverse=True)[:30]
            ],
            "reviewed_trade_ids": sorted(self.reviewed_trade_ids)[-500:],
        }
