from __future__ import annotations

"""Canonical V17 crypto-underlying PAPER lane.

This lane reuses the existing AdaptivePaperAutonomyEngine and canonical
PaperTradingDesk.  It never creates a crypto-specific ledger and never exposes
broker-order methods.  Deribit option-chain data remains research-only;
execution here is underlying BTC/ETH/SOL PAPER exposure only after the existing
fresh-data, session, adaptive expected-value, risk geometry, capital,
reconciliation and duplicate-exposure gates pass.

The one-touch V17 control surface also carries the session-aware MCX PAPER lane
as a nested status/result so no second HTTP control plane or ledger is created.
"""

from typing import Any

from omni.trading_intelligence.adaptive_opportunity_policy import POLICY_VERSION
from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
from workstation.paper_scan_ledger import paper_scan_ledger
from workstation.paper_trading_desk import paper_desk
from workstation.v17_mcx_paper_lane import mcx_paper_lane

CRYPTO_PAPER_UNIVERSE = ("BTC", "ETH", "SOL")
CRYPTO_PORTFOLIO_BUCKET = "INTRADAY"
CRYPTO_ALLOCATION_FRACTION = 0.20
ADAPTIVE_AUTHORITY = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"


class V17CryptoPaperLane:
    def __init__(self) -> None:
        self.engine = AdaptivePaperAutonomyEngine(
            universe=CRYPTO_PAPER_UNIVERSE,
            profile="intraday",
            scan_interval_seconds=15.0,
            max_workers=3,
            scan_ledger=paper_scan_ledger,
            portfolio_bucket=CRYPTO_PORTFOLIO_BUCKET,
            allocation_fraction=CRYPTO_ALLOCATION_FRACTION,
            allowed_sides=("LONG", "SHORT"),
            # Canonical workspace/Paper Desk remains the position-management
            # authority.  This lane owns new-entry scanning only.
            manage_marks=False,
        )

    @property
    def live_execution(self) -> bool:
        return False

    def start(self) -> dict[str, Any]:
        status = dict(self.engine.start(profile="intraday", scan_now=True))
        decorated = self._decorate(status, action="START")
        decorated["mcx_underlying_paper"] = mcx_paper_lane.start()
        return decorated

    def stop_new_entries(self) -> dict[str, Any]:
        status = dict(self.engine.stop())
        decorated = self._decorate(status, action="PAUSE_NEW_ENTRIES")
        decorated["mcx_underlying_paper"] = mcx_paper_lane.stop_new_entries()
        return decorated

    def status(self) -> dict[str, Any]:
        decorated = self._decorate(dict(self.engine.status()), action="STATUS")
        decorated["mcx_underlying_paper"] = mcx_paper_lane.status()
        return decorated

    def _positions(self) -> list[dict[str, Any]]:
        try:
            rows = list(paper_desk.snapshot().get("positions") or [])
        except Exception:
            return []
        wanted = set(CRYPTO_PAPER_UNIVERSE)
        return [
            dict(row)
            for row in rows
            if str(row.get("symbol") or "").upper() in wanted
            and str(row.get("portfolio_bucket") or CRYPTO_PORTFOLIO_BUCKET).upper()
            == CRYPTO_PORTFOLIO_BUCKET
        ]

    def _decorate(self, payload: dict[str, Any], *, action: str) -> dict[str, Any]:
        positions = self._positions()
        adaptive = payload.get("adaptive_intelligence") if isinstance(payload.get("adaptive_intelligence"), dict) else {}
        running = bool(payload.get("running"))
        return {
            **payload,
            "success": payload.get("success") is not False,
            "service": "JARVIS_V17_CANONICAL_CRYPTO_UNDERLYING_PAPER",
            "action": action,
            "state": "RUNNING" if running else "PAUSED",
            "universe": list(CRYPTO_PAPER_UNIVERSE),
            "portfolio_bucket": CRYPTO_PORTFOLIO_BUCKET,
            "allocation_fraction": CRYPTO_ALLOCATION_FRACTION,
            "positions": positions,
            "open_positions": len(positions),
            "execution_instrument": "CRYPTO_UNDERLYING",
            "qualification_authority": ADAPTIVE_AUTHORITY,
            "decision_authority": str(payload.get("decision_authority") or ADAPTIVE_AUTHORITY),
            "adaptive_policy_version": str(adaptive.get("policy_version") or POLICY_VERSION),
            "legacy_numeric_gates_are_execution_authority": False,
            "hard_safety_gates_preserved": True,
            "last_rows_summary": list(payload.get("last_rows_summary") or []),
            "deribit_options_execution": False,
            "deribit_options_research_only": True,
            "canonical_paper_desk": True,
            "separate_crypto_ledger": False,
            "mcx_lane_attached": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
        }


crypto_paper_lane = V17CryptoPaperLane()


__all__ = [
    "CRYPTO_PAPER_UNIVERSE",
    "CRYPTO_PORTFOLIO_BUCKET",
    "CRYPTO_ALLOCATION_FRACTION",
    "ADAPTIVE_AUTHORITY",
    "V17CryptoPaperLane",
    "crypto_paper_lane",
]
