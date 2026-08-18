"""Durable lexical memory with optional semantic rank fusion."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Protocol
from uuid import uuid4

from .contracts import utc_now


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    content: str
    kind: str
    source: str
    tags: tuple[str, ...]
    created_at: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SemanticHit:
    id: str
    score: float


@dataclass(frozen=True)
class MemoryHit:
    record: MemoryRecord
    score: float
    lexical_rank: int | None
    semantic_rank: int | None


class SemanticSearch(Protocol):
    def search(self, query: str, limit: int) -> list[SemanticHit]: ...


class HybridMemory:
    def __init__(self, path: Path | str, semantic: SemanticSearch | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.semantic = semantic
        self._lock = threading.RLock()
        self._fts_available = False
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                    USING fts5(id UNINDEXED, content, tags)
                    """
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False

    def remember(
        self,
        content: str,
        kind: str = "semantic",
        source: str = "user",
        tags: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> MemoryRecord:
        content = str(content).strip()
        kind = str(kind).strip().lower()
        source = str(source).strip()
        normalized_tags = tuple(sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()}))
        if not content or not kind or not source:
            raise ValueError("Memory content, kind, and source are required.")
        record = MemoryRecord(
            record_id or uuid4().hex,
            content,
            kind,
            source,
            normalized_tags,
            utc_now(),
            dict(metadata or {}),
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories
                (id, content, kind, source, tags_json, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content,
                    kind=excluded.kind,
                    source=excluded.source,
                    tags_json=excluded.tags_json,
                    metadata_json=excluded.metadata_json
                """,
                (
                    record.id,
                    record.content,
                    record.kind,
                    record.source,
                    json.dumps(record.tags),
                    record.created_at,
                    json.dumps(record.metadata, default=str, sort_keys=True),
                ),
            )
            if self._fts_available:
                connection.execute("DELETE FROM memory_fts WHERE id = ?", (record.id,))
                connection.execute(
                    "INSERT INTO memory_fts (id, content, tags) VALUES (?, ?, ?)",
                    (record.id, record.content, " ".join(record.tags)),
                )
        return record

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            row["id"],
            row["content"],
            row["kind"],
            row["source"],
            tuple(json.loads(row["tags_json"])),
            row["created_at"],
            json.loads(row["metadata_json"]),
        )

    def get(self, record_id: str) -> MemoryRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?", (record_id,)
            ).fetchone()
        return self._record(row) if row else None

    def count(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
        return int(row["count"])

    def lexical_search(self, query: str, limit: int = 20) -> list[MemoryRecord]:
        terms = re.findall(r"[\w-]+", str(query).lower(), flags=re.UNICODE)
        if not terms:
            return []
        safe_limit = min(max(int(limit), 1), 200)
        with self._lock, self._connect() as connection:
            if self._fts_available:
                expression = " OR ".join(f'"{term}"*' for term in terms)
                rows = connection.execute(
                    """
                    SELECT memories.* FROM memory_fts
                    JOIN memories ON memories.id = memory_fts.id
                    WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts) LIMIT ?
                    """,
                    (expression, safe_limit),
                ).fetchall()
            else:
                clauses = " OR ".join("lower(content) LIKE ?" for _ in terms)
                rows = connection.execute(
                    f"SELECT * FROM memories WHERE {clauses} ORDER BY created_at DESC LIMIT ?",
                    (*[f"%{term}%" for term in terms], safe_limit),
                ).fetchall()
        return [self._record(row) for row in rows]

    def search(self, query: str, limit: int = 10) -> list[MemoryHit]:
        safe_limit = min(max(int(limit), 1), 100)
        lexical = self.lexical_search(query, max(safe_limit * 2, 20))
        semantic = self.semantic.search(query, max(safe_limit * 2, 20)) if self.semantic else []
        scores: dict[str, float] = {}
        lexical_ranks = {record.id: rank for rank, record in enumerate(lexical, 1)}
        semantic_ranks = {hit.id: rank for rank, hit in enumerate(semantic, 1)}
        for record_id, rank in lexical_ranks.items():
            scores[record_id] = scores.get(record_id, 0.0) + 1 / (60 + rank)
        for record_id, rank in semantic_ranks.items():
            scores[record_id] = scores.get(record_id, 0.0) + 1 / (60 + rank)

        ordered = sorted(scores, key=lambda item: (-scores[item], item))[:safe_limit]
        output = []
        for record_id in ordered:
            record = self.get(record_id)
            if record:
                output.append(
                    MemoryHit(
                        record,
                        scores[record_id],
                        lexical_ranks.get(record_id),
                        semantic_ranks.get(record_id),
                    )
                )
        return output
