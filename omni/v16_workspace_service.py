"""Persistent workspace/project model for JARVIS V16.

The service supplies one navigation/state vocabulary to Chat, Files, Office,
Trading, Company and Automation.  It does not replace the existing mission
engine; missions are linked by identifier so long-running work can survive UI
reloads and process restarts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Any, Mapping
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT_ROOT / "data" / "workspaces" / "v16"
DEFAULT_WORKSPACES = ("HOME", "WORK", "TRADING", "COMPANY", "AUTOMATION")
_SAFE_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")


class WorkspaceServiceV16:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "workspace.sqlite3"
        self._lock = RLock()
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=20.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_db(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS workspace_files (
                    workspace_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    attached_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_id, file_id)
                );
                CREATE TABLE IF NOT EXISTS workspace_missions (
                    workspace_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    attached_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_id, mission_id)
                );
                CREATE TABLE IF NOT EXISTS workspace_activity (
                    activity_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            for name in DEFAULT_WORKSPACES:
                connection.execute(
                    "INSERT OR IGNORE INTO workspaces(workspace_id,name,kind,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (name, name.title(), name, now, now),
                )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _token(value: str, field: str) -> str:
        token = str(value or "").strip().upper().replace(" ", "_")
        if not _SAFE_TOKEN.fullmatch(token):
            raise ValueError(f"invalid {field}")
        return token

    def create_project(
        self,
        name: str,
        *,
        parent_kind: str = "WORK",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        display = str(name or "").strip()
        if not display:
            raise ValueError("project name is required")
        kind = self._token(parent_kind, "parent kind")
        if kind not in DEFAULT_WORKSPACES:
            raise ValueError("project parent must be a canonical workspace")
        workspace_id = "PROJECT_" + uuid.uuid4().hex[:16].upper()
        now = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO workspaces(workspace_id,name,kind,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?)",
                (workspace_id, display[:180], kind, now, now, json.dumps(dict(metadata or {}), default=str)),
            )
            connection.commit()
        finally:
            connection.close()
        return self.get(workspace_id)

    def get(self, workspace_id: str) -> dict[str, Any]:
        token = self._token(workspace_id, "workspace id")
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM workspaces WHERE workspace_id=?", (token,)).fetchone()
            if not row:
                return {"success": False, "reason": "WORKSPACE_NOT_FOUND", "workspace_id": token}
            files = [item[0] for item in connection.execute("SELECT file_id FROM workspace_files WHERE workspace_id=? ORDER BY attached_at DESC", (token,)).fetchall()]
            missions = [item[0] for item in connection.execute("SELECT mission_id FROM workspace_missions WHERE workspace_id=? ORDER BY attached_at DESC", (token,)).fetchall()]
            payload = {
                "workspace_id": str(row["workspace_id"]),
                "name": str(row["name"]),
                "kind": str(row["kind"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "metadata": json.loads(str(row["metadata_json"] or "{}")),
                "file_ids": files,
                "mission_ids": missions,
            }
        finally:
            connection.close()
        return {"success": True, "workspace": payload}

    def list(self, *, kind: str | None = None) -> dict[str, Any]:
        connection = self._connect()
        try:
            if kind is None:
                rows = connection.execute("SELECT * FROM workspaces ORDER BY created_at ASC").fetchall()
            else:
                token = self._token(kind, "kind")
                rows = connection.execute("SELECT * FROM workspaces WHERE kind=? ORDER BY created_at DESC", (token,)).fetchall()
            values = [
                {
                    "workspace_id": str(row["workspace_id"]),
                    "name": str(row["name"]),
                    "kind": str(row["kind"]),
                    "updated_at": str(row["updated_at"]),
                }
                for row in rows
            ]
        finally:
            connection.close()
        return {"success": True, "workspaces": values, "count": len(values)}

    def attach_file(self, workspace_id: str, file_id: str) -> dict[str, Any]:
        token = self._token(workspace_id, "workspace id")
        identifier = str(file_id or "").strip()
        if not identifier:
            raise ValueError("file_id is required")
        if not self.get(token).get("success"):
            raise ValueError("workspace does not exist")
        now = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            connection.execute("INSERT OR REPLACE INTO workspace_files(workspace_id,file_id,attached_at) VALUES(?,?,?)", (token, identifier, now))
            connection.execute("UPDATE workspaces SET updated_at=? WHERE workspace_id=?", (now, token))
            connection.commit()
        finally:
            connection.close()
        self.activity(token, "FILE_ATTACHED", f"File {identifier} attached", {"file_id": identifier})
        return self.get(token)

    def attach_mission(self, workspace_id: str, mission_id: str) -> dict[str, Any]:
        token = self._token(workspace_id, "workspace id")
        identifier = str(mission_id or "").strip()
        if not identifier:
            raise ValueError("mission_id is required")
        if not self.get(token).get("success"):
            raise ValueError("workspace does not exist")
        now = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            connection.execute("INSERT OR REPLACE INTO workspace_missions(workspace_id,mission_id,attached_at) VALUES(?,?,?)", (token, identifier, now))
            connection.execute("UPDATE workspaces SET updated_at=? WHERE workspace_id=?", (now, token))
            connection.commit()
        finally:
            connection.close()
        self.activity(token, "MISSION_ATTACHED", f"Mission {identifier} attached", {"mission_id": identifier})
        return self.get(token)

    def activity(
        self,
        workspace_id: str,
        activity_type: str,
        summary: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self._token(workspace_id, "workspace id")
        activity_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            connection.execute(
                "INSERT INTO workspace_activity(activity_id,workspace_id,activity_type,summary,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                (activity_id, token, str(activity_type)[:80], str(summary)[:500], json.dumps(dict(payload or {}), default=str), now),
            )
            connection.commit()
        finally:
            connection.close()
        return {"success": True, "activity_id": activity_id}

    def recent_activity(self, workspace_id: str | None = None, *, limit: int = 50) -> dict[str, Any]:
        cap = max(1, min(int(limit), 200))
        connection = self._connect()
        try:
            if workspace_id is None:
                rows = connection.execute("SELECT * FROM workspace_activity ORDER BY created_at DESC LIMIT ?", (cap,)).fetchall()
            else:
                token = self._token(workspace_id, "workspace id")
                rows = connection.execute("SELECT * FROM workspace_activity WHERE workspace_id=? ORDER BY created_at DESC LIMIT ?", (token, cap)).fetchall()
            values = [
                {
                    "activity_id": str(row["activity_id"]),
                    "workspace_id": str(row["workspace_id"]),
                    "type": str(row["activity_type"]),
                    "summary": str(row["summary"]),
                    "payload": json.loads(str(row["payload_json"] or "{}")),
                    "created_at": str(row["created_at"]),
                }
                for row in rows
            ]
        finally:
            connection.close()
        return {"success": True, "activities": values, "count": len(values)}

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "version": "16.0",
            "service": "JARVIS_V16_WORKSPACE_SERVICE",
            "canonical_workspaces": list(DEFAULT_WORKSPACES),
            "projects_supported": True,
            "file_bindings": True,
            "mission_bindings": True,
            "persistent": True,
        }


WORKSPACE_SERVICE_V16 = WorkspaceServiceV16()


__all__ = ["WorkspaceServiceV16", "WORKSPACE_SERVICE_V16", "DEFAULT_WORKSPACES"]
