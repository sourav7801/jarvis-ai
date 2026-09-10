from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from omni.trading_intelligence.adaptive_opportunity_policy import (
    ADAPTIVE_OPPORTUNITY_POLICY,
    POLICY_VERSION,
)
from workstation.paper_autonomy_engine import (
    DEFAULT_UNIVERSE,
    REENTRY_POLICY_VERSION,
    PaperAutonomyEngine,
    _journal_entry_evidence,
    paper_desk,
)
from workstation.paper_scan_ledger import paper_scan_ledger


STRATEGY_VERSION = "QUANT_ADAPTIVE_EXPECTED_VALUE_V12"


class AdaptivePaperAutonomyEngine(PaperAutonomyEngine):
    """Paper-only execution engine driven by continuous evidence and expected value.

    V11/V8 compatibility fields such as ``min_score`` remain observable, but V12
    does not use score 67/68/70 (or alignment/R:R profile thresholds) as binary
    entry authority.  The Adaptive Opportunity Policy decides PRIMARY / PROBE /
    WAIT from continuous evidence and outcome priors.  Data, session, accounting
    and stale-feed failures remain hard blockers.
    """

    @property
    def live_execution(self) -> bool:
        return False

    @staticmethod
    def _rank_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
        adaptive = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), dict) else {}
        return (
            float(adaptive.get("utility") or -999.0),
            float(adaptive.get("expected_value_r") or -999.0),
            float(adaptive.get("confidence") or 0.0),
            float(row.get("risk_reward") or 0.0),
        )

    def status(self) -> dict[str, Any]:
        payload = dict(super().status())
        payload["adaptive_intelligence"] = {
            **ADAPTIVE_OPPORTUNITY_POLICY.status(),
            "strategy_version": STRATEGY_VERSION,
            "legacy_min_score_observability_only": payload.get("min_score"),
            "legacy_min_risk_reward_observability_only": payload.get("min_risk_reward"),
            "one_probe_per_scan": True,
        }
        payload["decision_authority"] = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"
        payload["paper_only"] = True
        payload["live_execution"] = False
        return payload

    def _scan_once_unlocked(self) -> dict[str, Any]:
        started = time.perf_counter()
        rows: list[dict[str, Any]] = []
        from workstation.terminal_data import scan_rows
        from workstation import workspace_accounts
        from workstation.paper_trading_desk import live_mark_snapshot
        ticket = workspace_accounts.session(paper_desk, self.portfolio_bucket)
        session_generation = ticket.get("generation")
        rows = list(scan_rows(self._scan_symbol, self.universe, self._stop))

        rows = ADAPTIVE_OPPORTUNITY_POLICY.evaluate_many(
            rows,
            allowed_sides=self.allowed_sides,
        )
        candidates = [
            row
            for row in rows
            if row.get("success")
            and isinstance(row.get("adaptive_decision"), dict)
            and row["adaptive_decision"].get("executable") is True
            and str(row["adaptive_decision"].get("side") or "").upper() in self.allowed_sides
            and row.get("entry") is not None
            and row.get("stop") is not None
            and row.get("target") is not None
        ]
        candidates.sort(key=self._rank_key, reverse=True)

        rejection_counts = Counter()
        normalized_blockers: dict[int, list[str]] = {}
        provider_failures = Counter()
        for row in rows:
            adaptive = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), dict) else {}
            hard = [str(item) for item in list(adaptive.get("hard_blockers") or [])]
            soft = [str(item) for item in list(adaptive.get("soft_evidence") or [])]
            if not row.get("success") and not hard:
                hard = ["DATA_UNAVAILABLE"]
            if not adaptive.get("executable") and not hard:
                hard = ["ADAPTIVE_WAIT"]
            normalized_blockers[id(row)] = hard
            rejection_counts.update(hard)
            rejection_counts.update(f"SOFT_{item}" for item in soft)
            if not row.get("success"):
                provider = str(row.get("source") or row.get("provider") or "UNKNOWN_PROVIDER").upper()
                provider_failures[provider] += 1

        snapshot = paper_desk.snapshot()
        already_open = {
            str(item.get("symbol") or "").upper()
            for item in snapshot.get("positions") or []
            if str(item.get("portfolio_bucket") or "GENERAL").upper() == self.portfolio_bucket
        }
        try:
            recently_closed = list(paper_desk.closed_positions(200))
        except Exception:
            recently_closed = []
        scan_now = datetime.now(timezone.utc)
        opened = []
        probe_budget_remaining = 1

        for row in candidates:
            if self._stop.is_set():
                break
            adaptive = dict(row.get("adaptive_decision") or {})
            action = str(adaptive.get("action") or "WAIT").upper()
            if action == "PROBE" and probe_budget_remaining <= 0:
                rejection_counts["ADAPTIVE_PROBE_BUDGET_USED"] += 1
                continue

            symbol = str(row.get("symbol") or "").upper()
            side = str(adaptive.get("side") or "").upper()
            if not symbol or symbol in already_open:
                continue

            strategy = STRATEGY_VERSION
            cooldown_remaining = self._cooldown_remaining_seconds(
                symbol=symbol,
                strategy=strategy,
                closed_positions=recently_closed,
                now=scan_now,
            )
            if cooldown_remaining > 0:
                rejection_counts["REENTRY_COOLDOWN_ACTIVE"] += 1
                normalized_blockers.setdefault(id(row), []).append("REENTRY_COOLDOWN_ACTIVE")
                continue

            try:
                from workstation.bounded_decision_review import decision_review_coordinator

                cohort_policy = decision_review_coordinator.policy_for(strategy, self.profile)
            except Exception:
                cohort_policy = {"allowed": True, "risk_multiplier": 1.0}
            if not cohort_policy.get("allowed", True):
                rejection_counts["ADAPTIVE_COHORT_QUARANTINED"] += 1
                continue

            certificate = live_mark_snapshot(symbol)
            if not certificate.get("eligible_for_entry"):
                rejection_counts[str(certificate.get("reason") or "LIVE_MARK_UNAVAILABLE")] += 1
                continue
            row["entry_certificate"] = certificate
            live_candidate = dict(row)
            live_candidate["side"] = side
            try:
                from workstation.paper_trade_action_router import _live_entry

                live_entry, live_blocker = _live_entry(live_candidate)
            except Exception:
                live_entry, live_blocker = None, "LIVE_ENTRY_VALIDATION_FAILED"
            if live_entry is None:
                rejection_counts[str(live_blocker or "LIVE_ENTRY_VALIDATION_FAILED")] += 1
                continue

            if ticket and symbol in {"NIFTY", "BANKNIFTY", "SENSEX"}:
                from workstation.options_runtime_v151 import plan as option_plan
                from workstation.options_paper_execution_v151 import OPTIONS_PAPER_EXECUTION_V151
                proposal = option_plan(symbol, underlying_decision=adaptive, resolve_specs=True)
                row["option_proposal"] = proposal
                signal_bar = next((str(e.get("last_candle_time")) for e in row.get("evidence", []) if e.get("last_candle_time")), None)
                if not signal_bar:
                    rejection_counts["SIGNAL_BAR_ID_REQUIRED"] += 1
                    continue
                result = OPTIONS_PAPER_EXECUTION_V151.open_plan(proposal, desk=paper_desk,
                    portfolio_bucket=self.portfolio_bucket, bucket_allocation_fraction=self.allocation_fraction,
                    session_generation=session_generation, signal_id=signal_bar)
                row["execution_result"] = result
                if result.get("reason") == "PAPER_POSITION_OPENED":
                    opened.append(result)
                    already_open.add(symbol)
                else:
                    rejection_counts[result.get("reason") or "NO_OPTION_TRADE"] += 1
                continue

            valuation_multiplier = 1.0
            try:
                from workstation.paper_market_data import PAPER_MARKET_DATA

                instrument_spec = PAPER_MARKET_DATA.instrument_spec(symbol)
            except Exception:
                rejection_counts["INSTRUMENT_SPEC_UNAVAILABLE"] += 1
                continue

            if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
                try:
                    valuation_quote = PAPER_MARKET_DATA.quote(symbol)
                    native_ltp = float(valuation_quote.get("native_ltp") or 0.0)
                    valuation_ltp = float(valuation_quote.get("valuation_ltp") or 0.0)
                    if not valuation_quote.get("success") or native_ltp <= 0 or valuation_ltp <= 0:
                        raise ValueError("crypto valuation reference unavailable")
                    valuation_multiplier = valuation_ltp / native_ltp
                except Exception:
                    rejection_counts["VALUATION_FX_UNAVAILABLE"] += 1
                    continue

            evidence = list(row.get("evidence") or [])
            signal_bar = next(
                (
                    str(item.get("last_candle_time"))
                    for item in evidence
                    if item.get("last_candle_time") is not None
                ),
                None,
            )
            if signal_bar is None:
                rejection_counts["SIGNAL_BAR_ID_REQUIRED"] += 1
                continue
            journal_evidence = _journal_entry_evidence(row)
            adaptive_risk = float(adaptive.get("risk_multiplier") or 0.0)
            final_risk_multiplier = (
                self.profile_risk_multiplier
                * float(cohort_policy.get("risk_multiplier") or 1.0)
                * adaptive_risk
            )
            result = paper_desk.open_position(
                symbol=symbol,
                side=side,
                entry=float(live_entry),
                stop=float(row["stop"]),
                target=float(row["target"]),
                quantity=None,
                timeframe=str(row.get("timeframe") or ""),
                strategy=strategy,
                score=float(row.get("score") or 0.0),
                source="ADAPTIVE_AUTONOMOUS_PAPER",
                asset_type=(
                    "CRYPTO"
                    if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}
                    else "COMMODITY"
                    if symbol in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
                    else "EQUITY"
                    if symbol not in DEFAULT_UNIVERSE
                    else "MARKET"
                ),
                external_id=(
                    "adaptive:"
                    + symbol
                    + ":"
                    + str(row.get("timeframe") or "")
                    + ":"
                    + self.profile
                    + ":"
                    + self.portfolio_bucket
                    + ":"
                    + action
                    + ":"
                    + signal_bar
                ),
                metadata={
                    "session_generation": session_generation,
                    "entry_certificate": certificate,
                    **journal_evidence,
                    "adaptive_decision": adaptive,
                    "adaptive_policy_version": POLICY_VERSION,
                    "adaptive_action": action,
                    "adaptive_expected_value_r": adaptive.get("expected_value_r"),
                    "adaptive_confidence": adaptive.get("confidence"),
                    "adaptive_probability_win": adaptive.get("probability_win"),
                    "legacy_qualified": row.get("qualified"),
                    "legacy_score": row.get("score"),
                    "legacy_profile_min_score": self.min_score,
                    "legacy_profile_min_risk_reward": self.min_risk_reward,
                    "legacy_numeric_gates_are_execution_authority": False,
                    "regime": row.get("regime"),
                    "alignment": row.get("alignment"),
                    "risk_reward": row.get("risk_reward"),
                    "votes": row.get("votes") or [],
                    "decisions": row.get("decisions") or [],
                    "decision_version": row.get("decision_version"),
                    "risk_model": row.get("risk_model"),
                    "evidence_graph": row.get("evidence_graph") or [],
                    "contradictions": row.get("contradictions") or [],
                    "reasons_not_to_trade": row.get("reasons_not_to_trade") or [],
                    "profile": self.profile,
                    "portfolio_bucket": self.portfolio_bucket,
                    "bucket_allocation_fraction": self.allocation_fraction,
                    "reentry_policy_version": REENTRY_POLICY_VERSION,
                    "reentry_cooldown_minutes": self._reentry_cooldown_minutes(),
                    "profile_risk_multiplier": self.profile_risk_multiplier,
                    "cohort_policy": cohort_policy,
                    "adaptive_risk_multiplier": adaptive_risk,
                    "final_risk_multiplier": final_risk_multiplier,
                    "initial_risk": abs(float(live_entry) - float(row["stop"])),
                    "entry_levels": {
                        "decision_entry": row.get("entry"),
                        "validated_live_entry": live_entry,
                        "stop": row.get("stop"),
                        "target": row.get("target"),
                        "risk_reward": row.get("risk_reward"),
                    },
                    "exit_policy": {
                        "breakeven_at_r": 1.0 if self.profile in {"swing", "investment"} else 0.75,
                        "trailing_at_r": 1.5 if self.profile in {"swing", "investment"} else 1.0,
                        "trailing_distance_r": 0.75 if self.profile in {"swing", "investment"} else 0.50,
                        "trailing_target_r": 1.5 if self.profile in {"swing", "investment"} else 1.0,
                        "scale_out": [
                            {"at_r": 1.0, "fraction": 0.34},
                            {"at_r": 2.0, "fraction": 0.50},
                        ],
                        "max_hold_minutes": (
                            525600 if self.profile == "investment" else 10080 if self.profile == "swing" else 390
                        ),
                    },
                },
                risk_multiplier=final_risk_multiplier,
                valuation_multiplier=valuation_multiplier,
                instrument_spec=instrument_spec,
                portfolio_bucket=self.portfolio_bucket,
                bucket_allocation_fraction=self.allocation_fraction,
            )
            row["execution_result"] = result
            if result.get("success") and result.get("reason") == "PAPER_POSITION_OPENED":
                opened.append(result)
                already_open.add(symbol)
                if action == "PROBE":
                    probe_budget_remaining -= 1
            else:
                rejection_counts[str(result.get("reason") or "PAPER_DESK_ENTRY_REJECTED")] += 1

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        scan_at = datetime.now(timezone.utc).isoformat()
        rows_summary = []
        for row in rows:
            adaptive = dict(row.get("adaptive_decision") or {})
            rows_summary.append(
                {
                    "symbol": row.get("symbol"),
                    "side": adaptive.get("side"), "action": adaptive.get("action"),
                    "reason": (row.get("execution_result") or {}).get("reason") or ", ".join(normalized_blockers.get(id(row), [])),
                    "workspace_sizing": (row.get("execution_result") or {}).get("sizing"),
                    "execution_result": row.get("execution_result"),
                    "strategy": row.get("strategy") or STRATEGY_VERSION,
                    "entry": row.get("entry"), "stop": row.get("stop"), "target": row.get("target"),
                    "risk_reward": row.get("risk_reward"), "timeframe": row.get("timeframe"),
                    "evidence": row.get("evidence"), "option_proposal": row.get("option_proposal"),
                    "legacy_side": row.get("side"),
                    "candidate_side": row.get("candidate_side"),
                    "legacy_score": row.get("score"),
                    "legacy_qualified": row.get("qualified"),
                    "adaptive_action": adaptive.get("action"),
                    "adaptive_side": adaptive.get("side"),
                    "adaptive_executable": adaptive.get("executable"),
                    "adaptive_probability_win": adaptive.get("probability_win"),
                    "adaptive_expected_value_r": adaptive.get("expected_value_r"),
                    "adaptive_confidence": adaptive.get("confidence"),
                    "adaptive_risk_multiplier": adaptive.get("risk_multiplier"),
                    "hard_blockers": adaptive.get("hard_blockers") or [],
                    "soft_evidence": adaptive.get("soft_evidence") or [],
                    "success": bool(row.get("success")),
                    "source": row.get("source") or row.get("provider"),
                    "data_quality": row.get("data_quality"),
                    "session_open": row.get("session_open"),
                    "message": row.get("message"),
                }
            )

        primary_count = sum(
            1 for row in candidates if str((row.get("adaptive_decision") or {}).get("action")) == "PRIMARY"
        )
        probe_count = sum(
            1 for row in candidates if str((row.get("adaptive_decision") or {}).get("action")) == "PROBE"
        )
        legacy_qualified = sum(1 for row in rows if row.get("qualified") is True)
        funnel = {
            "scanned": len(rows),
            "data_ok": sum(1 for row in rows if row.get("success")),
            "session_open": sum(1 for row in rows if row.get("session_open") is True),
            "legacy_qualified": legacy_qualified,
            "adaptive_executable": len(candidates),
            "adaptive_primary": primary_count,
            "adaptive_probe": probe_count,
            "opened": len(opened),
        }

        ledger_id = None
        ledger_error = None
        if self.scan_ledger is not None:
            try:
                ledger_id = self.scan_ledger.record(
                    {
                        "scan_at": scan_at,
                        "profile": self.profile,
                        "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                        "adaptive_policy_version": POLICY_VERSION,
                        "timeframes": self.timeframes,
                        "elapsed_ms": elapsed_ms,
                        "funnel": funnel,
                        "rejection_counts": dict(rejection_counts),
                        "provider_failures": dict(provider_failures),
                        "rows": rows_summary,
                    }
                )
            except Exception as exc:
                ledger_error = f"{type(exc).__name__}: {exc}"[:500]

        with self._lock:
            self._scan_cycles += 1
            self._positions_opened += len(opened)
            self._last_scan_at = scan_at
            self._last_scan_elapsed_ms = elapsed_ms
            self._last_scan_funnel = funnel
            self._last_provider_failure_counts = dict(provider_failures)
            self._last_candidates = [
                {
                    "symbol": row.get("symbol"),
                    "timeframe": row.get("timeframe"),
                    "side": (row.get("adaptive_decision") or {}).get("side"),
                    "adaptive_action": (row.get("adaptive_decision") or {}).get("action"),
                    "expected_value_r": (row.get("adaptive_decision") or {}).get("expected_value_r"),
                    "confidence": (row.get("adaptive_decision") or {}).get("confidence"),
                    "risk_multiplier": (row.get("adaptive_decision") or {}).get("risk_multiplier"),
                    "legacy_score": row.get("score"),
                    "regime": row.get("regime"),
                    "risk_reward": row.get("risk_reward"),
                    "alignment": row.get("alignment"),
                    "decision_version": row.get("decision_version"),
                }
                for row in candidates[:20]
            ]
            self._last_rejection_counts = dict(rejection_counts)
            self._last_rows_summary = rows_summary
            self._last_scan_ledger_id = ledger_id
            self._last_scan_ledger_error = ledger_error

        return {
            "success": True,
            "elapsed_ms": elapsed_ms,
            "rows": len(rows),
            "candidate_count": len(candidates),
            "opened": opened,
            "profile": self.profile,
            "timeframes": list(self.timeframes),
            "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "adaptive_policy_version": POLICY_VERSION,
            "funnel": funnel,
            "rejection_counts": dict(rejection_counts),
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


adaptive_paper_autonomy = AdaptivePaperAutonomyEngine(scan_ledger=paper_scan_ledger)

__all__ = [
    "AdaptivePaperAutonomyEngine",
    "STRATEGY_VERSION",
    "adaptive_paper_autonomy",
]
