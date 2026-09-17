from __future__ import annotations

"""Canonical V17 crypto-underlying PAPER lane.

This lane reuses the existing PaperAutonomyEngine and PaperTradingDesk.  It
never creates a crypto-specific ledger and never exposes broker-order methods.
Deribit option-chain data remains research-only; execution here is underlying
BTC/ETH/SOL PAPER exposure only after the existing completed-bar, fresh-mark,
risk, capital, reconciliation and duplicate-exposure gates pass.
"""

from typing import Any

from workstation.paper_autonomy_engine import PaperAutonomyEngine
from workstation.paper_scan_ledger import paper_scan_ledger
from workstation.paper_trading_desk import paper_desk

CRYPTO_PAPER_UNIVERSE = ("BTC", "ETH", "SOL")
CRYPTO_PORTFOLIO_BUCKET = "INTRADAY"
CRYPTO_ALLOCATION_FRACTION = 0.20


class V17CryptoPaperLane:
    def __init__(self) -> None:
        self.engine = PaperAutonomyEngine(
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
        return self._decorate(status, action="START")

    def stop_new_entries(self) -> dict[str, Any]:
        status = dict(self.engine.stop())
        return self._decorate(status, action="PAUSE_NEW_ENTRIES")

    def status(self) -> dict[str, Any]:
        return self._decorate(dict(self.engine.status()), action="STATUS")

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
        return {
            **payload,
            "success": payload.get("success") is not False,
            "service": "JARVIS_V17_CANONICAL_CRYPTO_UNDERLYING_PAPER",
            "action": action,
            "universe": list(CRYPTO_PAPER_UNIVERSE),
            "portfolio_bucket": CRYPTO_PORTFOLIO_BUCKET,
            "allocation_fraction": CRYPTO_ALLOCATION_FRACTION,
            "positions": positions,
            "open_positions": len(positions),
            "execution_instrument": "CRYPTO_UNDERLYING",
            "deribit_options_execution": False,
            "deribit_options_research_only": True,
            "canonical_paper_desk": True,
            "separate_crypto_ledger": False,
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
    "V17CryptoPaperLane",
    "crypto_paper_lane",
]
