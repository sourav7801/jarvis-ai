"""Governed decision bridge from verified option chains to the Paper Options Desk."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable

from workstation.defined_risk_options_paper_desk import (
    DefinedRiskOptionsPaperDesk,
    select_debit_vertical,
)
from workstation.options_chain_analytics import NormalizedOptionContract


class OptionsPaperAutonomyEngine:
    def __init__(self, desk: DefinedRiskOptionsPaperDesk, *, minimum_score: float = 80.0):
        self.desk = desk
        self.minimum_score = max(50.0, min(float(minimum_score), 100.0))
        self._lock = RLock()
        self._processed = 0
        self._opened = 0
        self._rejections: Counter[str] = Counter()
        self._last_result: dict[str, Any] | None = None

    def _reject(self, reason: str) -> dict[str, Any]:
        result = {"success": False, "status": "REJECTED", "reason": reason, "paper_only": True, "live_execution": False}
        with self._lock:
            self._processed += 1
            self._rejections[reason] += 1
            self._last_result = result
        return result

    def process_chain(
        self,
        contracts: Iterable[NormalizedOptionContract],
        *,
        signal: dict[str, Any],
        expiry: str,
        contract_multiplier: float,
        currency: str,
        certificate: dict[str, Any],
        equity: float,
    ) -> dict[str, Any]:
        if certificate.get("verified") is not True or certificate.get("stale") is True:
            return self._reject("CHAIN_UNVERIFIED_OR_STALE")
        if certificate.get("session_open") is not True:
            return self._reject("SESSION_CLOSED")
        if not certificate.get("received_at"):
            return self._reject("CHAIN_TIMESTAMP_MISSING")
        try:
            received = datetime.fromisoformat(str(certificate["received_at"]).replace("Z", "+00:00"))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - received.astimezone(timezone.utc)).total_seconds() > 120:
                return self._reject("CHAIN_TOO_OLD")
        except ValueError:
            return self._reject("CHAIN_TIMESTAMP_INVALID")
        action = str(signal.get("action") or signal.get("direction") or "").upper()
        direction = "LONG" if action in {"BUY", "LONG"} else "SHORT" if action in {"SELL", "SHORT"} else ""
        if not direction:
            return self._reject("UNDERLYING_SIGNAL_WAIT")
        if float(signal.get("score") or 0.0) < self.minimum_score:
            return self._reject("UNDERLYING_SCORE_BELOW_GATE")
        if signal.get("contradictions"):
            return self._reject("UNDERLYING_SIGNAL_CONTRADICTION")
        if signal.get("paper_only") is not True or signal.get("live_execution") is not False:
            return self._reject("SIGNAL_SAFETY_CONTRACT_INVALID")
        try:
            candidate = select_debit_vertical(
                contracts, direction=direction, expiry=expiry,
                contract_multiplier=contract_multiplier, currency=currency,
                evidence_timestamp=str(certificate["received_at"]), verified=True, stale=False,
            )
            opened = self.desk.open_spread(candidate, equity=equity)
        except (TypeError, ValueError) as error:
            return self._reject(f"SPREAD_POLICY:{type(error).__name__}")
        result = {
            **opened, "candidate": candidate.to_dict(),
            "underlying_signal": {"direction": direction, "score": float(signal["score"])},
            "paper_only": True, "live_execution": False,
        }
        with self._lock:
            self._processed += 1
            if opened.get("success"):
                self._opened += 1
            else:
                self._rejections[str(opened.get("status") or "DESK_REJECTED")] += 1
            self._last_result = result
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "processed": self._processed, "opened": self._opened,
                "rejections": dict(self._rejections), "last_result": self._last_result,
                "minimum_score": self.minimum_score,
                "strategy_scope": ["BULL_CALL_DEBIT", "BEAR_PUT_DEBIT"],
                "naked_short_options": "BLOCKED", "paper_only": True, "live_execution": False,
            }


from workstation.defined_risk_options_paper_desk import DEFINED_RISK_OPTIONS_DESK

OPTIONS_PAPER_AUTONOMY = OptionsPaperAutonomyEngine(DEFINED_RISK_OPTIONS_DESK)
