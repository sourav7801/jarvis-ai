"""Bounded persistent store for verified completed-bar feature snapshots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class MultiTimeframeFeatureStore:
    def __init__(self, path: Path | None = None, *, retention_per_series: int = 500):
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "state" / "multi_timeframe_features.sqlite3"
        self.retention_per_series = max(10, min(int(retention_per_series), 10_000))
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS feature_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    bar_time TEXT NOT NULL,
                    feature_version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_symbol TEXT,
                    data_quality TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(symbol, timeframe, bar_time, feature_version)
                );
                CREATE INDEX IF NOT EXISTS idx_feature_latest
                ON feature_snapshots(symbol, timeframe, id DESC);
                """
            )
            connection.commit()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value if value is not None else "").strip()

    def record(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        data = snapshot.get("data") if isinstance(snapshot, dict) else None
        if not snapshot.get("success") or not isinstance(data, dict):
            raise ValueError("Only successful feature snapshots can be stored.")
        if not data.get("verified") or data.get("stale"):
            raise ValueError("Feature storage requires verified, fresh market data.")
        required = {
            "symbol": snapshot.get("symbol"), "timeframe": snapshot.get("timeframe"),
            "bar_time": data.get("last_time"), "feature_version": snapshot.get("feature_version"),
            "provider": data.get("provider"), "data_quality": data.get("quality"),
        }
        if any(not self._text(value) for value in required.values()):
            raise ValueError("Feature snapshot is missing provenance or completed-bar identity.")
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        generated_at = self._text(snapshot.get("generated_at")) or datetime.now(timezone.utc).isoformat()
        values = (
            self._text(required["symbol"]).upper(), self._text(required["timeframe"]).lower(),
            self._text(required["bar_time"]), self._text(required["feature_version"]),
            self._text(required["provider"]), self._text(data.get("provider_symbol")),
            self._text(required["data_quality"]), generated_at, digest, canonical,
        )
        with self._lock, closing(self._connect()) as connection:
            before = connection.total_changes
            connection.execute(
                """INSERT OR IGNORE INTO feature_snapshots
                (symbol,timeframe,bar_time,feature_version,provider,provider_symbol,data_quality,generated_at,payload_hash,payload_json)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            inserted = connection.total_changes > before
            connection.execute(
                """DELETE FROM feature_snapshots WHERE id IN (
                    SELECT id FROM feature_snapshots WHERE symbol=? AND timeframe=?
                    ORDER BY id DESC LIMIT -1 OFFSET ?
                )""",
                (values[0], values[1], self.retention_per_series),
            )
            connection.commit()
        return {
            "stored": inserted, "deduplicated": not inserted,
            "symbol": values[0], "timeframe": values[1], "bar_time": values[2],
            "feature_version": values[3], "payload_hash": digest,
            "paper_only": True, "live_execution": False,
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        payload = json.loads(row["payload_json"])
        payload["store"] = {
            "id": row["id"], "payload_hash": row["payload_hash"],
            "stored_at": row["generated_at"], "bar_time": row["bar_time"],
        }
        return payload

    def latest(self, symbol: str, timeframe: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM feature_snapshots WHERE symbol=? AND timeframe=? ORDER BY id DESC LIMIT 1",
                (self._text(symbol).upper(), self._text(timeframe).lower()),
            ).fetchone()
        return self._decode(row) if row else None

    def latest_matrix(self, symbol: str) -> dict[str, Any]:
        normalized = self._text(symbol).upper()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT f.* FROM feature_snapshots f JOIN (
                    SELECT timeframe, MAX(id) AS max_id FROM feature_snapshots
                    WHERE symbol=? GROUP BY timeframe
                ) latest ON f.id=latest.max_id ORDER BY f.timeframe""",
                (normalized,),
            ).fetchall()
        return {
            "symbol": normalized,
            "timeframes": {row["timeframe"]: self._decode(row) for row in rows},
            "snapshot_count": len(rows), "paper_only": True, "live_execution": False,
        }


MULTI_TIMEFRAME_FEATURE_STORE = MultiTimeframeFeatureStore()
