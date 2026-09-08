from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "trading" / "v15_market_beliefs.sqlite3"
STORE_VERSION = "MARKET_BELIEF_STORE_V15"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _changes(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> list[dict[str, Any]]:
    before = dict(previous or {})
    after = dict(current or {})
    keys = sorted(set(before) | set(after))
    changed: list[dict[str, Any]] = []
    for key in keys:
        if before.get(key) != after.get(key):
            changed.append({"field": key, "previous": before.get(key), "current": after.get(key)})
    return changed[:40]


class MarketBeliefStoreV15:
    """Persistent local history of explainable market beliefs.

    The store contains model state only.  It does not create market data and it
    is never an execution or broker surface.  Previous/current belief snapshots
    let the UI explain what changed between completed-bar updates.
    """

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
                CREATE TABLE IF NOT EXISTS v15_market_beliefs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    reasoning_version TEXT,
                    belief_json TEXT NOT NULL,
                    hypotheses_json TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    UNIQUE(symbol, profile, recorded_at)
                );
                CREATE INDEX IF NOT EXISTS idx_v15_belief_symbol_profile
                ON v15_market_beliefs(symbol, profile, id DESC);
                """
            )

    @staticmethod
    def _decode(value: Any, default: Any) -> Any:
        try:
            parsed = json.loads(str(value or ""))
            return parsed
        except Exception:
            return default

    def latest(self, symbol: str, profile: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM v15_market_beliefs WHERE symbol=? AND profile=? ORDER BY id DESC LIMIT 1",
                (str(symbol).upper(), str(profile)),
            ).fetchone()
        if row is None:
            return None
        return {
            "symbol": row["symbol"],
            "profile": row["profile"],
            "recorded_at": row["recorded_at"],
            "reasoning_version": row["reasoning_version"],
            "market_belief": self._decode(row["belief_json"], {}),
            "hypotheses": self._decode(row["hypotheses_json"], []),
            "provenance": self._decode(row["provenance_json"], []),
        }

    def record(self, reasoning: Mapping[str, Any]) -> dict[str, Any]:
        symbol = str(reasoning.get("symbol") or "").upper()
        profile = str(reasoning.get("profile") or "")
        belief = dict(reasoning.get("market_belief") or {})
        hypotheses = list(reasoning.get("hypotheses") or [])
        provenance = list(reasoning.get("data_provenance") or [])
        if not symbol or not belief:
            return {
                "success": False,
                "reason": "BELIEF_NOT_RECORDABLE",
                "paper_only": True,
                "live_execution": False,
            }
        previous = self.latest(symbol, profile)
        recorded_at = _now()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO v15_market_beliefs(symbol,profile,recorded_at,reasoning_version,belief_json,hypotheses_json,provenance_json) VALUES(?,?,?,?,?,?,?)",
                (
                    symbol,
                    profile,
                    recorded_at,
                    str(reasoning.get("reasoning_version") or ""),
                    json.dumps(belief, sort_keys=True, default=str),
                    json.dumps(hypotheses, sort_keys=True, default=str),
                    json.dumps(provenance, sort_keys=True, default=str),
                ),
            )
            conn.commit()
        return {
            "success": True,
            "version": "15.0",
            "service": STORE_VERSION,
            "symbol": symbol,
            "profile": profile,
            "recorded_at": recorded_at,
            "previous_belief": (previous or {}).get("market_belief"),
            "current_belief": belief,
            "changes": _changes((previous or {}).get("market_belief"), belief),
            "history_fabricated": False,
            "paper_only": True,
            "live_execution": False,
        }

    def history(self, symbol: str, profile: str, limit: int = 20) -> dict[str, Any]:
        bounded = max(1, min(int(limit), 100))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM v15_market_beliefs WHERE symbol=? AND profile=? ORDER BY id DESC LIMIT ?",
                (str(symbol).upper(), str(profile), bounded),
            ).fetchall()
        items = []
        for row in rows:
            items.append({
                "recorded_at": row["recorded_at"],
                "reasoning_version": row["reasoning_version"],
                "market_belief": self._decode(row["belief_json"], {}),
                "hypotheses": self._decode(row["hypotheses_json"], []),
            })
        return {
            "success": True,
            "version": "15.0",
            "service": STORE_VERSION,
            "symbol": str(symbol).upper(),
            "profile": str(profile),
            "items": items,
            "count": len(items),
            "history_fabricated": False,
            "paper_only": True,
            "live_execution": False,
        }

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "15.0",
            "service": STORE_VERSION,
            "persistent": True,
            "market_data_created": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


MARKET_BELIEF_STORE_V15 = MarketBeliefStoreV15()

__all__ = ["MarketBeliefStoreV15", "MARKET_BELIEF_STORE_V15", "STORE_VERSION"]
