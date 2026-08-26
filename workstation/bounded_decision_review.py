"""Bounded, auditable adaptation for closed synthetic paper trades.

The coordinator is deliberately separated from execution.  It reads the local
Paper Desk journal, attributes outcomes, and publishes conservative policy
overrides for strategy/timeframe cohorts.  It cannot place an order, mutate a
strategy implementation, or grant live-execution permission.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import threading
from typing import Any, Callable
from uuid import uuid4

from workstation.paper_trading_desk import DB_PATH


LEDGER_PATH = Path(__file__).resolve().parents[1] / "data" / "trading" / "decision_review_ledger.json"
SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(timezone.utc).isoformat()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
        return dict(parsed) if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _cohort_key(strategy: str, timeframe: str) -> str:
    return f"{strategy.upper()}|{timeframe.lower()}"


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BoundedDecisionReviewCoordinator:
    """Continuously review synthetic closes without touching execution code.

    Adaptation is monotonic-conservative: it may reduce risk, raise entry gates,
    or temporarily disable a weak strategy/timeframe pair.  It never increases
    risk or lowers an entry gate.  Consumers must explicitly consult
    :meth:`policy_for`; this module has no broker or exchange dependency.
    """

    def __init__(
        self,
        *,
        db_path: Path | str = DB_PATH,
        ledger_path: Path | str = LEDGER_PATH,
        interval_seconds: float = 60.0,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.db_path = Path(db_path)
        self.ledger_path = Path(ledger_path)
        self.interval_seconds = max(10.0, min(float(interval_seconds), 3600.0))
        self.clock = clock
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._cycles = 0
        self._last_run_at: str | None = None
        self._last_error: str | None = None
        self._state = self._load_state()

    @property
    def live_execution(self) -> bool:
        return False

    def _empty_state(self) -> dict[str, Any]:
        now = _iso(self.clock())
        return {
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "generation": 0,
            "reviewed_trades": {},
            "cohort_scorecards": {},
            "active_policies": {},
            "policy_revisions": [],
            "rollback_events": [],
            "safety": {
                "paper_only": True,
                "live_execution": False,
                "self_modifying_code": False,
                "risk_can_only_decrease": True,
                "entry_gates_can_only_tighten": True,
            },
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return self._empty_state()
        try:
            value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or int(value.get("schema_version") or 0) != SCHEMA_VERSION:
                return self._empty_state()
            empty = self._empty_state()
            empty.update(value)
            for key in ("reviewed_trades", "cohort_scorecards", "active_policies"):
                if not isinstance(empty.get(key), dict):
                    empty[key] = {}
            for key in ("policy_revisions", "rollback_events"):
                if not isinstance(empty.get(key), list):
                    empty[key] = []
            return empty
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self._empty_state()

    def _save_state(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._state["updated_at"] = _iso(self.clock())
        temporary = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.ledger_path)

    def _closed_rows(self, limit: int) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        connection.row_factory = sqlite3.Row
        try:
            tables = {
                str(row[0])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if "paper_positions" not in tables:
                return []
            rows = connection.execute(
                "SELECT * FROM paper_positions WHERE status='CLOSED' ORDER BY id ASC LIMIT ?",
                (max(1, min(int(limit), 5000)),),
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["exit_reason"] = "UNKNOWN_EXIT"
                if "paper_events" in tables:
                    event = connection.execute(
                        "SELECT payload_json FROM paper_events "
                        "WHERE position_id=? AND event_type='CLOSE' ORDER BY id DESC LIMIT 1",
                        (int(row["id"]),),
                    ).fetchone()
                    if event:
                        item["exit_reason"] = str(_json_object(event[0]).get("reason") or "UNKNOWN_EXIT")
                results.append(item)
            return results
        finally:
            connection.close()

    def _attribute(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = _json_object(row.get("metadata_json"))
        trade_id = f"paper_desk:{int(row['id'])}"
        strategy = str(row.get("strategy") or metadata.get("strategy") or "UNCLASSIFIED").upper()
        timeframe = str(row.get("timeframe") or metadata.get("timeframe") or "UNKNOWN").lower()
        regime = str(metadata.get("regime") or "UNKNOWN").upper()
        side = str(row.get("side") or "UNKNOWN").upper()
        entry = _number(row.get("entry"))
        exit_price = _number(row.get("exit_price"))
        stop = _number(row.get("stop")) if row.get("stop") is not None else None
        target = _number(row.get("target")) if row.get("target") is not None else None
        quantity = max(_number(row.get("quantity")), 0.0)
        pnl = _number(row.get("realized_pnl"))
        initial_risk = abs(entry - stop) * quantity if stop is not None else 0.0
        planned_reward = abs(target - entry) * quantity if target is not None else 0.0
        planned_rr = planned_reward / initial_risk if initial_risk > 0 else None
        realized_r = pnl / initial_risk if initial_risk > 0 else None
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"
        score = _number(row.get("score")) if row.get("score") is not None else None
        alignment = _number(metadata.get("alignment")) if metadata.get("alignment") is not None else None
        opened_at = _parse_timestamp(row.get("opened_at"))
        closed_at = _parse_timestamp(row.get("closed_at"))
        hold_seconds = (
            max(0.0, (closed_at - opened_at).total_seconds())
            if opened_at is not None and closed_at is not None
            else None
        )

        patterns: list[str] = []
        for value in metadata.get("patterns") or metadata.get("chart_patterns") or []:
            if str(value) not in patterns:
                patterns.append(str(value))
        for decision in metadata.get("decisions") or []:
            if isinstance(decision, dict):
                for value in decision.get("patterns") or decision.get("chart_patterns") or []:
                    if str(value) not in patterns:
                        patterns.append(str(value))

        exit_reason = str(row.get("exit_reason") or "UNKNOWN_EXIT").upper()
        causes: list[str] = []
        if stop is None:
            causes.append("MISSING_INITIAL_STOP")
        if target is None:
            causes.append("MISSING_INITIAL_TARGET")
        if planned_rr is not None and planned_rr < 1.8:
            causes.append("PLANNED_REWARD_RISK_BELOW_1_8")
        if score is not None and score < 68.0:
            causes.append("ENTRY_SCORE_BELOW_AUTONOMY_GATE")
        if alignment is not None and alignment < 0.67:
            causes.append("WEAK_TIMEFRAME_ALIGNMENT")
        if outcome == "LOSS" and "STOP" in exit_reason:
            causes.append("THESIS_INVALIDATED_AT_STOP")
        elif outcome == "LOSS":
            causes.append("ADVERSE_DISCRETIONARY_OR_RISK_EXIT")
        if outcome == "WIN" and "TARGET" in exit_reason:
            causes.append("PLANNED_TARGET_REALIZED")
        if regime in {"RANGE", "RANGE_OR_TRANSITION", "MIXED"} and "BREAKOUT" in strategy:
            causes.append("BREAKOUT_STRATEGY_IN_NON_TREND_REGIME")

        reward_capture = pnl / planned_reward if planned_reward > 0 and pnl > 0 else 0.0
        return {
            "trade_id": trade_id,
            "journal_position_id": int(row["id"]),
            "reviewed_at": _iso(self.clock()),
            "closed_at": str(row.get("closed_at") or ""),
            "symbol": str(row.get("symbol") or "").upper(),
            "asset_type": str(row.get("asset_type") or "UNKNOWN").upper(),
            "synthetic_paper": True,
            "strategy": strategy,
            "timeframe": timeframe,
            "regime": regime,
            "cohort": _cohort_key(strategy, timeframe),
            "setup": {
                "side": side,
                "patterns": patterns[:12],
                "score": score,
                "alignment": alignment,
                "decision_version": metadata.get("decision_version"),
            },
            "risk": {
                "entry": entry,
                "stop": stop,
                "initial_risk": round(initial_risk, 6),
                "planned_reward": round(planned_reward, 6),
                "planned_risk_reward": round(planned_rr, 4) if planned_rr is not None else None,
            },
            "reward": {
                "exit": exit_price,
                "net_pnl": round(pnl, 6),
                "realized_r": round(realized_r, 4) if realized_r is not None else None,
                "reward_capture": round(reward_capture, 4),
            },
            "outcome": outcome,
            "exit_reason": exit_reason,
            "hold_seconds": hold_seconds,
            "attribution_flags": causes,
            "source": str(row.get("source") or "PAPER_DESK"),
            "live_execution": False,
        }

    @staticmethod
    def _scorecard(cohort: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(reviews, key=lambda item: (str(item.get("closed_at") or ""), item["trade_id"]))
        r_values = [
            _number(item["reward"].get("realized_r"))
            for item in ordered
            if item["reward"].get("realized_r") is not None
        ]
        wins = sum(item["outcome"] == "WIN" for item in ordered)
        losses = sum(item["outcome"] == "LOSS" for item in ordered)
        gross_profit = sum(max(_number(item["reward"].get("net_pnl")), 0.0) for item in ordered)
        gross_loss = abs(sum(min(_number(item["reward"].get("net_pnl")), 0.0) for item in ordered))
        streak = max_streak = 0
        cumulative_r = peak_r = max_drawdown_r = 0.0
        for item in ordered:
            if item["outcome"] == "LOSS":
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
            value = item["reward"].get("realized_r")
            if value is not None:
                cumulative_r += _number(value)
                peak_r = max(peak_r, cumulative_r)
                max_drawdown_r = max(max_drawdown_r, peak_r - cumulative_r)
        regimes: dict[str, dict[str, Any]] = {}
        for regime in sorted({str(item.get("regime") or "UNKNOWN") for item in ordered}):
            subset = [item for item in ordered if item.get("regime") == regime]
            regimes[regime] = {
                "trades": len(subset),
                "wins": sum(item["outcome"] == "WIN" for item in subset),
                "net_pnl": round(sum(_number(item["reward"].get("net_pnl")) for item in subset), 4),
            }
        strategy, timeframe = cohort.split("|", 1)
        return {
            "cohort": cohort,
            "strategy": strategy,
            "timeframe": timeframe,
            "trades": len(ordered),
            "wins": wins,
            "losses": losses,
            "flats": len(ordered) - wins - losses,
            "win_rate": round(wins / len(ordered), 4) if ordered else 0.0,
            "net_pnl": round(sum(_number(item["reward"].get("net_pnl")) for item in ordered), 4),
            "expectancy_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
            "max_consecutive_losses": max_streak,
            "max_drawdown_r": round(max_drawdown_r, 4),
            "regime_breakdown": regimes,
            "last_trade_at": str(ordered[-1].get("closed_at") or "") if ordered else None,
        }

    def _recommendation(self, card: dict[str, Any]) -> dict[str, Any] | None:
        trades = int(card.get("trades") or 0)
        if trades < 5:
            return None
        expectancy = _number(card.get("expectancy_r"))
        win_rate = _number(card.get("win_rate"))
        streak = int(card.get("max_consecutive_losses") or 0)
        evidence = {
            "trades": trades,
            "win_rate": win_rate,
            "expectancy_r": card.get("expectancy_r"),
            "profit_factor": card.get("profit_factor"),
            "max_consecutive_losses": streak,
            "max_drawdown_r": card.get("max_drawdown_r"),
        }
        if trades >= 6 and (streak >= 4 or (expectancy <= -0.35 and win_rate <= 0.34)):
            return {
                "action": "TEMPORARILY_DISABLE_COMBINATION",
                "allowed": False,
                "risk_multiplier": 0.5,
                "minimum_score_delta": 8.0,
                "minimum_risk_reward_delta": 0.4,
                "cooldown_hours": 24,
                "rationale": "Weak strategy/timeframe evidence crossed the hard paper-only quarantine gate.",
                "evidence": evidence,
            }
        if expectancy < 0.0 or streak >= 3:
            severity = min(1.0, max(abs(expectancy), streak / 5.0))
            return {
                "action": "REDUCE_RISK_AND_TIGHTEN_GATES",
                "allowed": True,
                "risk_multiplier": round(max(0.5, 1.0 - 0.5 * severity), 2),
                "minimum_score_delta": round(min(8.0, 2.0 + 6.0 * severity), 1),
                "minimum_risk_reward_delta": round(min(0.4, 0.1 + 0.3 * severity), 2),
                "cooldown_hours": 0,
                "rationale": "Negative paper expectancy requires smaller risk and stronger evidence.",
                "evidence": evidence,
            }
        return {
            "action": "BASELINE_NO_RISK_INCREASE",
            "allowed": True,
            "risk_multiplier": 1.0,
            "minimum_score_delta": 0.0,
            "minimum_risk_reward_delta": 0.0,
            "cooldown_hours": 0,
            "rationale": "Evidence does not justify a restriction; wins never authorize an automatic risk increase.",
            "evidence": evidence,
        }

    def _apply_recommendation(self, cohort: str, recommendation: dict[str, Any]) -> bool:
        current = dict(self._state["active_policies"].get(cohort) or {})
        comparable_keys = (
            "action", "allowed", "risk_multiplier", "minimum_score_delta",
            "minimum_risk_reward_delta", "cooldown_hours", "evidence",
        )
        comparable = {key: recommendation.get(key) for key in comparable_keys}
        recommendation_hash = _stable_hash(comparable)
        old_comparable = {key: current.get(key) for key in comparable_keys}
        if current and recommendation_hash == _stable_hash(old_comparable):
            return False
        # An operator rollback remains authoritative until fresh closed-trade
        # evidence changes the recommendation.  A continuous loop must not
        # silently re-apply the exact revision on its next cycle.
        latest_rollback = next(
            (
                item for item in reversed(self._state["rollback_events"])
                if item.get("cohort") == cohort
            ),
            None,
        )
        if latest_rollback and latest_rollback.get("recommendation_hash") == recommendation_hash:
            return False
        now = self.clock()
        rollback_token = uuid4().hex
        revision_id = f"review-policy-{uuid4().hex}"
        policy = {
            **recommendation,
            "cohort": cohort,
            "policy_version": revision_id,
            "activated_at": _iso(now),
            "expires_at": (
                _iso(now + timedelta(hours=int(recommendation.get("cooldown_hours") or 0)))
                if int(recommendation.get("cooldown_hours") or 0) > 0
                else None
            ),
            "rollback_token": rollback_token,
            "paper_only": True,
            "live_execution": False,
        }
        revision = {
            "revision_id": revision_id,
            "cohort": cohort,
            "created_at": _iso(now),
            "trigger": "CLOSED_SYNTHETIC_TRADE_REVIEW",
            "before": current or None,
            "after": policy,
            "before_hash": _stable_hash(current or None),
            "after_hash": _stable_hash(policy),
            "rollback_token": rollback_token,
            "recommendation_hash": recommendation_hash,
            "status": "ACTIVE",
            "code_modified": False,
            "live_execution": False,
        }
        self._state["active_policies"][cohort] = policy
        self._state["policy_revisions"].append(revision)
        self._state["policy_revisions"] = self._state["policy_revisions"][-1000:]
        return True

    def review_once(self, *, limit: int = 5000) -> dict[str, Any]:
        with self._lock:
            rows = self._closed_rows(limit)
            added = 0
            for row in rows:
                trade_id = f"paper_desk:{int(row['id'])}"
                if trade_id in self._state["reviewed_trades"]:
                    continue
                self._state["reviewed_trades"][trade_id] = self._attribute(row)
                added += 1

            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for review in self._state["reviewed_trades"].values():
                if isinstance(review, dict) and review.get("cohort"):
                    grouped[str(review["cohort"])].append(review)
            cards = {key: self._scorecard(key, values) for key, values in sorted(grouped.items())}
            self._state["cohort_scorecards"] = cards
            revisions = 0
            for cohort, card in cards.items():
                recommendation = self._recommendation(card)
                if recommendation is not None and self._apply_recommendation(cohort, recommendation):
                    revisions += 1
            self._state["generation"] = int(self._state.get("generation") or 0) + 1
            self._cycles += 1
            self._last_run_at = _iso(self.clock())
            self._last_error = None
            self._save_state()
            return {
                "success": True,
                "closed_rows": len(rows),
                "new_reviews": added,
                "cohorts": len(cards),
                "policy_revisions": revisions,
                "generation": self._state["generation"],
                "paper_only": True,
                "live_execution": False,
                "self_modifying_code": False,
            }

    def policy_for(self, strategy: str, timeframe: str) -> dict[str, Any]:
        cohort = _cohort_key(str(strategy or "UNCLASSIFIED"), str(timeframe or "UNKNOWN"))
        with self._lock:
            policy = dict(self._state["active_policies"].get(cohort) or {})
        if not policy:
            policy = {
                "cohort": cohort,
                "action": "BASELINE_INSUFFICIENT_EVIDENCE",
                "allowed": True,
                "risk_multiplier": 1.0,
                "minimum_score_delta": 0.0,
                "minimum_risk_reward_delta": 0.0,
                "paper_only": True,
                "live_execution": False,
            }
        expires_at = _parse_timestamp(policy.get("expires_at"))
        if not policy.get("allowed", True) and expires_at and expires_at <= self.clock():
            policy = {
                **policy,
                "action": "COOLDOWN_EXPIRED_REQUIRES_FRESH_REVIEW",
                "allowed": True,
                "risk_multiplier": min(1.0, _number(policy.get("risk_multiplier"), 1.0)),
            }
        return policy

    def rollback(self, rollback_token: str, *, reason: str) -> dict[str, Any]:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            return {"success": False, "reason": "ROLLBACK_REASON_REQUIRED", "paper_only": True}
        with self._lock:
            revision = next(
                (
                    item for item in reversed(self._state["policy_revisions"])
                    if item.get("rollback_token") == str(rollback_token)
                    and item.get("status") == "ACTIVE"
                ),
                None,
            )
            if revision is None:
                return {"success": False, "reason": "ROLLBACK_TOKEN_NOT_ACTIVE", "paper_only": True}
            cohort = str(revision["cohort"])
            current = dict(self._state["active_policies"].get(cohort) or {})
            before = revision.get("before")
            if isinstance(before, dict) and before:
                self._state["active_policies"][cohort] = dict(before)
            else:
                self._state["active_policies"].pop(cohort, None)
            revision["status"] = "ROLLED_BACK"
            revision["rolled_back_at"] = _iso(self.clock())
            event = {
                "rollback_id": f"rollback-{uuid4().hex}",
                "revision_id": revision["revision_id"],
                "cohort": cohort,
                "rolled_back_at": revision["rolled_back_at"],
                "reason": clean_reason[:500],
                "from_hash": _stable_hash(current),
                "to_hash": _stable_hash(before or None),
                "recommendation_hash": revision.get("recommendation_hash"),
                "live_execution": False,
            }
            self._state["rollback_events"].append(event)
            self._state["rollback_events"] = self._state["rollback_events"][-1000:]
            self._save_state()
            return {"success": True, **event, "paper_only": True}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "success": True,
                "running": self._running and not self._stop.is_set(),
                "cycles": self._cycles,
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "reviewed_trades": len(self._state["reviewed_trades"]),
                "active_policies": len(self._state["active_policies"]),
                "paper_only": True,
                "live_execution": False,
                "self_modifying_code": False,
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return self.status()
            self._stop.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="JarvisBoundedDecisionReview",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def stop(self, *, join_timeout: float = 2.0) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, min(float(join_timeout), 5.0)))
        with self._lock:
            self._running = False
        return self.status()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.review_once()
            except Exception as exc:  # fail closed and retain diagnostics
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"[:500]
            if self._stop.wait(self.interval_seconds):
                break
        with self._lock:
            self._running = False


decision_review_coordinator = BoundedDecisionReviewCoordinator()
