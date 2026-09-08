from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "trading" / "v15_execution_forensics.sqlite3"
FORENSICS_VERSION = "EXECUTION_FORENSICS_V15"
_ALLOWED_STAGES = {
    "DISCOVERY",
    "BELIEF_UPDATE",
    "HYPOTHESIS_BUILD",
    "DECISION",
    "PORTFOLIO_ALLOCATION",
    "LIVE_MARK_RECHECK",
    "SIZE_PLAN",
    "PAPER_DESK_ACCEPTED",
    "PAPER_DESK_REJECTED",
    "POSITION_OPENED",
    "POSITION_MANAGED",
    "POSITION_CLOSED",
    "POST_TRADE_REVIEW",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionForensicsV15:
    def __init__(self, db_path: Path | str = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self._lock = RLock()
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS v15_execution_forensics(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT,
                    profile TEXT,
                    stage TEXT NOT NULL,
                    reason TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_v15_forensics_symbol
                    ON v15_execution_forensics(symbol, id DESC);
                """
            )

    def record(
        self,
        stage: str,
        *,
        symbol: str | None = None,
        profile: str | None = None,
        reason: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = str(stage or "").upper()
        if normalized not in _ALLOWED_STAGES:
            return {
                "success": False,
                "reason": "UNSUPPORTED_FORENSIC_STAGE",
                "allowed_stages": sorted(_ALLOWED_STAGES),
                "paper_only": True,
                "live_execution": False,
            }
        created_at = _now()
        bounded_payload = dict(payload or {})
        bounded_payload["paper_only"] = True
        bounded_payload["live_execution"] = False
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO v15_execution_forensics(created_at,symbol,profile,stage,reason,payload_json) VALUES(?,?,?,?,?,?)",
                (
                    created_at,
                    str(symbol or "").upper() or None,
                    str(profile or "") or None,
                    normalized,
                    str(reason or "") or None,
                    json.dumps(bounded_payload, default=str, sort_keys=True)[:120000],
                ),
            )
            conn.commit()
            event_id = int(cursor.lastrowid)
        return {
            "success": True,
            "version": "15.0",
            "service": FORENSICS_VERSION,
            "event_id": event_id,
            "created_at": created_at,
            "stage": normalized,
            "reason": reason,
            "paper_only": True,
            "live_execution": False,
        }

    def snapshot(self, *, symbol: str | None = None, limit: int = 160) -> dict[str, Any]:
        bounded = max(1, min(int(limit), 500))
        with self._lock, self._connect() as conn:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM v15_execution_forensics WHERE symbol=? ORDER BY id DESC LIMIT ?",
                    (str(symbol).upper(), bounded),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM v15_execution_forensics ORDER BY id DESC LIMIT ?",
                    (bounded,),
                ).fetchall()
        events = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except Exception:
                payload = {}
            events.append({
                "id": int(row["id"]),
                "created_at": row["created_at"],
                "symbol": row["symbol"],
                "profile": row["profile"],
                "stage": row["stage"],
                "reason": row["reason"],
                "payload": payload,
            })
        return {
            "success": True,
            "version": "15.0",
            "service": FORENSICS_VERSION,
            "events": events,
            "count": len(events),
            "ambiguous_watching_terminal_state": False,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "service": FORENSICS_VERSION,
            "stages": sorted(_ALLOWED_STAGES),
            "ambiguous_watching_terminal_state": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


EXECUTION_FORENSICS_V15 = ExecutionForensicsV15()

__all__ = ["EXECUTION_FORENSICS_V15", "ExecutionForensicsV15", "FORENSICS_VERSION"]
