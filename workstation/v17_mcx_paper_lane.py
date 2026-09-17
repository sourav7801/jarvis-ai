from __future__ import annotations

"""Canonical V17 MCX underlying/futures PAPER lane.

The lane reuses AdaptivePaperAutonomyEngine and the singleton PaperTradingDesk.
It never submits broker orders and never pretends MCX option execution is
verified.  CRUDEOIL/GOLD/SILVER/NATURALGAS are expressed as provider-resolved
front-month MCX FUTURE paper positions only when the MCX session is open and the
existing adaptive/data/risk/capital/reconciliation gates pass.
"""

import threading
from typing import Any

from omni.trading_intelligence.adaptive_opportunity_policy import POLICY_VERSION
from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine
from workstation.paper_market_data import PAPER_MARKET_DATA
from workstation.paper_scan_ledger import paper_scan_ledger
from workstation.paper_trading_desk import paper_desk

MCX_PAPER_UNIVERSE = ("CRUDEOIL", "GOLD", "SILVER", "NATURALGAS")
MCX_PORTFOLIO_BUCKET = "INTRADAY"
MCX_ALLOCATION_FRACTION = 0.20
ADAPTIVE_AUTHORITY = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"


class V17MCXPaperLane:
    """Session-aware autonomous MCX PAPER scanning over verified FUTURE specs."""

    def __init__(self) -> None:
        self.engine = AdaptivePaperAutonomyEngine(
            universe=MCX_PAPER_UNIVERSE,
            profile="intraday",
            scan_interval_seconds=45.0,
            max_workers=2,
            scan_ledger=paper_scan_ledger,
            portfolio_bucket=MCX_PORTFOLIO_BUCKET,
            allocation_fraction=MCX_ALLOCATION_FRACTION,
            allowed_sides=("LONG", "SHORT"),
            manage_marks=False,
        )
        self._lock = threading.RLock()
        self._enabled = False
        self._session_thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def live_execution(self) -> bool:
        return False

    def _session_status(self) -> dict[str, Any]:
        try:
            return dict(PAPER_MARKET_DATA.session_status("CRUDEOIL"))
        except Exception as exc:
            return {
                "session_open": False,
                "venue": "MCX",
                "reason": f"SESSION_STATUS_UNAVAILABLE:{type(exc).__name__}",
            }

    def _ensure_session_thread(self) -> None:
        with self._lock:
            if self._session_thread and self._session_thread.is_alive():
                return
            self._stop.clear()
            self._session_thread = threading.Thread(
                target=self._session_loop,
                name="JarvisV17MCXSessionGuard",
                daemon=True,
            )
            self._session_thread.start()

    def _session_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                enabled = self._enabled
            session = self._session_status()
            open_now = bool(session.get("session_open", session.get("is_open", False)))
            status = self.engine.status()
            running = bool(status.get("running"))

            if enabled and open_now and not running:
                try:
                    self.engine.start(profile="intraday", scan_now=True)
                except Exception:
                    # Engine status exposes its own startup/scan errors.  The
                    # guard retries on the next bounded session tick.
                    pass
            elif running and (not enabled or not open_now):
                # Signal only this entry scanner to stop.  Do not call the
                # engine-wide coordinator stop hook while crypto/other lanes
                # may still be active in the same process.
                self.engine._stop.set()

            self._stop.wait(20.0)

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = True
        self._ensure_session_thread()
        session = self._session_status()
        if bool(session.get("session_open", session.get("is_open", False))):
            status = dict(self.engine.start(profile="intraday", scan_now=True))
        else:
            status = dict(self.engine.status())
        return self._decorate(status, action="START")

    def stop_new_entries(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = False
        self.engine._stop.set()
        return self._decorate(dict(self.engine.status()), action="PAUSE_NEW_ENTRIES")

    def status(self) -> dict[str, Any]:
        return self._decorate(dict(self.engine.status()), action="STATUS")

    def _positions(self) -> list[dict[str, Any]]:
        try:
            rows = list(paper_desk.snapshot().get("positions") or [])
        except Exception:
            return []
        wanted = set(MCX_PAPER_UNIVERSE)
        return [
            dict(row)
            for row in rows
            if str(row.get("symbol") or "").upper() in wanted
            and str(row.get("portfolio_bucket") or MCX_PORTFOLIO_BUCKET).upper()
            == MCX_PORTFOLIO_BUCKET
        ]

    def _decorate(self, payload: dict[str, Any], *, action: str) -> dict[str, Any]:
        positions = self._positions()
        adaptive = payload.get("adaptive_intelligence") if isinstance(payload.get("adaptive_intelligence"), dict) else {}
        session = self._session_status()
        session_open = bool(session.get("session_open", session.get("is_open", False)))
        with self._lock:
            enabled = self._enabled
        running = bool(payload.get("running"))
        state = (
            "RUNNING"
            if running and session_open
            else "WAITING_FOR_MCX_SESSION"
            if enabled and not session_open
            else "STARTING"
            if enabled and session_open and not running
            else "PAUSED"
        )
        return {
            **payload,
            "success": payload.get("success") is not False,
            "service": "JARVIS_V17_CANONICAL_MCX_UNDERLYING_PAPER",
            "action": action,
            "state": state,
            "enabled": enabled,
            "running": running,
            "session": session,
            "session_open": session_open,
            "universe": list(MCX_PAPER_UNIVERSE),
            "portfolio_bucket": MCX_PORTFOLIO_BUCKET,
            "allocation_fraction": MCX_ALLOCATION_FRACTION,
            "positions": positions,
            "open_positions": len(positions),
            "execution_instrument": "MCX_FRONT_MONTH_FUTURE_PAPER",
            "qualification_authority": ADAPTIVE_AUTHORITY,
            "decision_authority": str(payload.get("decision_authority") or ADAPTIVE_AUTHORITY),
            "adaptive_policy_version": str(adaptive.get("policy_version") or POLICY_VERSION),
            "legacy_numeric_gates_are_execution_authority": False,
            "hard_safety_gates_preserved": True,
            "last_rows_summary": list(payload.get("last_rows_summary") or []),
            "mcx_options_execution": False,
            "mcx_options_reason": "EXACT_MCX_OPTION_EXECUTION_PATH_NOT_VERIFIED",
            "canonical_paper_desk": True,
            "separate_mcx_ledger": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
        }


mcx_paper_lane = V17MCXPaperLane()


__all__ = [
    "MCX_PAPER_UNIVERSE",
    "MCX_PORTFOLIO_BUCKET",
    "MCX_ALLOCATION_FRACTION",
    "ADAPTIVE_AUTHORITY",
    "V17MCXPaperLane",
    "mcx_paper_lane",
]
