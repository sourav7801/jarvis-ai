"""SQLite-backed episodic event and task-state store."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from .contracts import Plan, Step, utc_now


class AuditStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    correlation_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    cancelled INTEGER NOT NULL,
                    plan_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    step_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(plan_id) REFERENCES plans(id)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT UNIQUE NOT NULL,
                    action TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                );
                """
            )

    def record_event(
        self,
        category: str,
        name: str,
        status: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> str:
        event_id = uuid4().hex
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events
                (id, timestamp, category, name, status, correlation_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    utc_now(),
                    category,
                    name,
                    status,
                    correlation_id,
                    json.dumps(payload or {}, default=str, sort_keys=True),
                ),
            )
        return event_id

    def save_plan(self, plan: Plan) -> None:
        serialized = json.dumps(plan.to_dict(), default=str, sort_keys=True)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO plans (id, objective, created_at, cancelled, plan_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    cancelled=excluded.cancelled,
                    plan_json=excluded.plan_json
                """,
                (
                    plan.id,
                    plan.objective,
                    plan.created_at,
                    int(plan.cancelled),
                    serialized,
                ),
            )
            for step in plan.steps:
                self._save_step(connection, plan.id, step)

    def save_step(self, plan_id: str, step: Step) -> None:
        with self._lock, self._connect() as connection:
            self._save_step(connection, plan_id, step)

    @staticmethod
    def _save_step(
        connection: sqlite3.Connection, plan_id: str, step: Step
    ) -> None:
        connection.execute(
            """
            INSERT INTO steps
            (id, plan_id, action, status, attempts, step_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                attempts=excluded.attempts,
                step_json=excluded.step_json,
                updated_at=excluded.updated_at
            """,
            (
                step.id,
                plan_id,
                step.action,
                step.status.value,
                step.attempts,
                json.dumps(step.to_dict(), default=str, sort_keys=True),
                utc_now(),
            ),
        )

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = min(max(int(limit), 1), 1000)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def save_approval(
        self,
        approval_id: str,
        token_hash: str,
        action: str,
        capability: str,
        issued_at: str,
        expires_at: str,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals
                (id, token_hash, action, capability, issued_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    token_hash,
                    action,
                    capability,
                    issued_at,
                    expires_at,
                ),
            )

    def consume_approval(
        self, token_hash: str, action: str, capability: str, consumed_at: str
    ) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approvals
                SET consumed_at = ?
                WHERE token_hash = ?
                  AND action = ?
                  AND capability = ?
                  AND consumed_at IS NULL
                  AND expires_at >= ?
                """,
                (consumed_at, token_hash, action, capability, consumed_at),
            )
            return cursor.rowcount == 1

    def recent_plans(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = min(max(int(limit), 1), 200)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT plan_json FROM plans ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [json.loads(row["plan_json"]) for row in rows]

    def steps_for_plan(self, plan_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT step_json FROM steps
                WHERE plan_id = ? ORDER BY updated_at, id
                """,
                (plan_id,),
            ).fetchall()
        return [json.loads(row["step_json"]) for row in rows]

    def load_plan(self, plan_id: str) -> Plan | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT plan_json FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if row is None:
                return None
            step_rows = connection.execute(
                "SELECT step_json FROM steps WHERE plan_id = ?",
                (plan_id,),
            ).fetchall()

        payload = json.loads(row["plan_json"])
        latest_steps = {
            item["id"]: item
            for item in (json.loads(step_row["step_json"]) for step_row in step_rows)
        }
        payload["steps"] = [
            latest_steps.get(item["id"], item) for item in payload.get("steps", [])
        ]
        return Plan.from_dict(payload)

    def search_events(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        term = str(query).strip()
        if not term:
            return self.recent_events(limit)
        safe_limit = min(max(int(limit), 1), 500)
        pattern = f"%{term}%"
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE category LIKE ? OR name LIKE ? OR status LIKE ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (pattern, pattern, pattern, safe_limit),
            ).fetchall()
        return [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]
