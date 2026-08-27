from __future__ import annotations

import json
import sqlite3
import threading
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "trading" / "paper_scan_history.sqlite3"


class PaperScanLedger:
    """Bounded, append-only evidence for autonomous paper scan cycles."""

    def __init__(self, path: Path | None = None, *, retention_cycles: int = 2000) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self.retention_cycles = max(10, int(retention_cycles))
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scan_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_at TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    timeframes_json TEXT NOT NULL,
                    elapsed_ms REAL NOT NULL,
                    funnel_json TEXT NOT NULL,
                    rejection_counts_json TEXT NOT NULL,
                    provider_failures_json TEXT NOT NULL,
                    paper_only INTEGER NOT NULL CHECK (paper_only = 1),
                    live_execution INTEGER NOT NULL CHECK (live_execution = 0)
                );
                CREATE TABLE IF NOT EXISTS scan_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id INTEGER NOT NULL REFERENCES scan_cycles(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    score REAL,
                    qualified INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    source TEXT,
                    data_quality TEXT,
                    session_open INTEGER,
                    blockers_json TEXT NOT NULL,
                    message TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_scan_cycles_at ON scan_cycles(scan_at DESC);
                CREATE INDEX IF NOT EXISTS idx_scan_rows_cycle ON scan_rows(cycle_id);
                """
            )
            connection.commit()
        finally:
            connection.close()

    def record(self, payload: dict[str, Any]) -> int:
        rows = list(payload.get("rows") or [])
        with self._lock:
            connection = self._connect()
            try:
                cursor = connection.execute(
                """
                INSERT INTO scan_cycles (
                    scan_at, profile, timeframes_json, elapsed_ms, funnel_json,
                    rejection_counts_json, provider_failures_json, paper_only, live_execution
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
                """,
                (
                    str(payload["scan_at"]),
                    str(payload.get("profile") or "unknown"),
                    json.dumps(list(payload.get("timeframes") or []), separators=(",", ":")),
                    float(payload.get("elapsed_ms") or 0.0),
                    json.dumps(dict(payload.get("funnel") or {}), sort_keys=True, separators=(",", ":")),
                    json.dumps(dict(payload.get("rejection_counts") or {}), sort_keys=True, separators=(",", ":")),
                    json.dumps(dict(payload.get("provider_failures") or {}), sort_keys=True, separators=(",", ":")),
                ),
            )
                cycle_id = int(cursor.lastrowid)
                connection.executemany(
                """
                INSERT INTO scan_rows (
                    cycle_id, symbol, side, score, qualified, success, source,
                    data_quality, session_open, blockers_json, message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        cycle_id,
                        str(row.get("symbol") or "UNKNOWN"),
                        str(row.get("side") or "WAIT"),
                        float(row["score"]) if row.get("score") is not None else None,
                        int(bool(row.get("qualified"))),
                        int(bool(row.get("success"))),
                        str(row.get("source") or "") or None,
                        str(row.get("data_quality") or "") or None,
                        None if row.get("session_open") is None else int(bool(row.get("session_open"))),
                        json.dumps(list(row.get("blockers") or []), separators=(",", ":")),
                        str(row.get("message") or "")[:500] or None,
                    )
                    for row in rows
                ],
            )
                connection.execute(
                """
                DELETE FROM scan_cycles
                WHERE id NOT IN (SELECT id FROM scan_cycles ORDER BY id DESC LIMIT ?)
                """,
                (self.retention_cycles,),
            )
                connection.commit()
                return cycle_id
            finally:
                connection.close()

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 100))
        with self._lock:
            connection = self._connect()
            try:
                cycles = connection.execute(
                    "SELECT * FROM scan_cycles ORDER BY id DESC LIMIT ?", (bounded,)
                ).fetchall()
                result: list[dict[str, Any]] = []
                for cycle in cycles:
                    row_counts = connection.execute(
                        "SELECT COUNT(*) AS total, SUM(qualified) AS qualified FROM scan_rows WHERE cycle_id = ?",
                        (cycle["id"],),
                    ).fetchone()
                    result.append(
                        {
                            "id": int(cycle["id"]),
                            "scan_at": cycle["scan_at"],
                            "profile": cycle["profile"],
                            "timeframes": json.loads(cycle["timeframes_json"]),
                            "elapsed_ms": float(cycle["elapsed_ms"]),
                            "funnel": json.loads(cycle["funnel_json"]),
                            "rejection_counts": json.loads(cycle["rejection_counts_json"]),
                            "provider_failures": json.loads(cycle["provider_failures_json"]),
                            "rows": int(row_counts["total"] or 0),
                            "qualified_rows": int(row_counts["qualified"] or 0),
                            "paper_only": True,
                            "live_execution": False,
                        }
                    )
                return result
            finally:
                connection.close()

    def trends(self, limit: int = 50) -> dict[str, Any]:
        """Aggregate a bounded recent window without claiming predictive value."""

        cycles = list(reversed(self.recent(limit)))
        if not cycles:
            return {
                "cycles": 0,
                "series": [],
                "funnel_totals": {},
                "rates": {},
                "provider_failures": {},
                "blockers": {},
                "paper_only": True,
                "live_execution": False,
            }
        funnel_totals: Counter[str] = Counter()
        provider_failures: Counter[str] = Counter()
        blockers: Counter[str] = Counter()
        series: list[dict[str, Any]] = []
        elapsed_values: list[float] = []
        for cycle in cycles:
            funnel = dict(cycle.get("funnel") or {})
            funnel_totals.update({key: int(value or 0) for key, value in funnel.items()})
            provider_failures.update(
                {key: int(value or 0) for key, value in dict(cycle.get("provider_failures") or {}).items()}
            )
            blockers.update(
                {key: int(value or 0) for key, value in dict(cycle.get("rejection_counts") or {}).items()}
            )
            elapsed = float(cycle.get("elapsed_ms") or 0.0)
            elapsed_values.append(elapsed)
            scanned = int(funnel.get("scanned") or 0)
            data_ok = int(funnel.get("data_ok") or 0)
            series.append(
                {
                    "scan_at": cycle.get("scan_at"),
                    "elapsed_ms": elapsed,
                    "data_ok_rate": round((data_ok / scanned * 100.0) if scanned else 0.0, 2),
                    "qualified": int(funnel.get("qualified") or 0),
                    "opened": int(funnel.get("opened") or 0),
                    "provider_failures": sum(int(value or 0) for value in dict(cycle.get("provider_failures") or {}).values()),
                }
            )
        scanned = int(funnel_totals.get("scanned") or 0)
        data_ok = int(funnel_totals.get("data_ok") or 0)
        session_open = int(funnel_totals.get("session_open") or 0)
        qualified = int(funnel_totals.get("qualified") or 0)
        return {
            "cycles": len(cycles),
            "from": cycles[0].get("scan_at"),
            "to": cycles[-1].get("scan_at"),
            "average_elapsed_ms": round(sum(elapsed_values) / len(elapsed_values), 2),
            "maximum_elapsed_ms": round(max(elapsed_values), 2),
            "funnel_totals": dict(funnel_totals),
            "rates": {
                "data_ok_percent": round((data_ok / scanned * 100.0) if scanned else 0.0, 2),
                "session_open_percent": round((session_open / scanned * 100.0) if scanned else 0.0, 2),
                "qualified_percent": round((qualified / data_ok * 100.0) if data_ok else 0.0, 2),
                "opened_percent": round(
                    (int(funnel_totals.get("opened") or 0) / qualified * 100.0) if qualified else 0.0,
                    2,
                ),
            },
            "provider_failures": dict(provider_failures.most_common()),
            "blockers": dict(blockers.most_common()),
            "series": series,
            "paper_only": True,
            "live_execution": False,
        }


paper_scan_ledger = PaperScanLedger()
