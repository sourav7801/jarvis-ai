"""Bounded provenance-aware world state graph for JARVIS V9.3.

The world model stores observations about JARVIS-owned local state. It is a
reasoning/context surface, not an execution engine. Every observation carries
source, timestamp, freshness and confidence metadata so stale state cannot be
silently presented as current.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "state" / "world_model.json"
MAX_NODES = 500
MAX_EDGES = 1000


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().isoformat()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return _clean(value, 1200)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, Mapping):
        return {
            str(key)[:120]: _bounded(item, depth=depth + 1)
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_bounded(item, depth=depth + 1) for item in list(value)[:50]]
    return _clean(value, 2000)


class WorldStateGraph:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or DEFAULT_PATH)
        self._lock = RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("nodes", [])
                value.setdefault("edges", [])
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "nodes": [], "edges": [], "updated_at": None}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def observe(
        self,
        node_id: str,
        *,
        kind: str,
        label: str,
        state: Mapping[str, Any] | Any,
        source: str,
        confidence: float = 1.0,
        observed_at: str | None = None,
        stale_after_seconds: float = 300.0,
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        node_key = _clean(node_id, 180)
        if not node_key:
            raise ValueError("world-model node_id is required")
        source_text = _clean(source, 180)
        if not source_text:
            raise ValueError("world-model source is required")
        observed = _parse_time(observed_at) or _now_dt()
        stale_after = max(1.0, min(float(stale_after_seconds), 7 * 24 * 3600.0))
        record = {
            "node_id": node_key,
            "kind": _clean(kind, 100) or "STATE",
            "label": _clean(label, 240) or node_key,
            "state": _bounded(state),
            "source": source_text,
            "observed_at": observed.isoformat(),
            "stale_after_seconds": stale_after,
            "confidence": round(max(0.0, min(float(confidence), 1.0)), 4),
            "provenance": _bounded(dict(provenance or {})),
            "updated_at": _now(),
        }
        with self._lock:
            nodes = list(self._state.get("nodes") or [])
            existing_index = next(
                (index for index, item in enumerate(nodes) if item.get("node_id") == node_key),
                None,
            )
            if existing_index is None:
                nodes.insert(0, record)
            else:
                nodes.pop(existing_index)
                nodes.insert(0, record)
            self._state["nodes"] = nodes[:MAX_NODES]
            self._state["updated_at"] = record["updated_at"]
            self._save()
        return self.node(node_key)

    def connect(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        provenance: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        edge = {
            "source": _clean(source, 180),
            "target": _clean(target, 180),
            "relation": _clean(relation, 120),
            "provenance": _bounded(dict(provenance or {})),
            "updated_at": _now(),
        }
        if not edge["source"] or not edge["target"] or not edge["relation"]:
            raise ValueError("world-model edges require source, target and relation")
        identity = (edge["source"], edge["target"], edge["relation"])
        with self._lock:
            edges = [
                item
                for item in (self._state.get("edges") or [])
                if (item.get("source"), item.get("target"), item.get("relation")) != identity
            ]
            edges.insert(0, edge)
            self._state["edges"] = edges[:MAX_EDGES]
            self._state["updated_at"] = edge["updated_at"]
            self._save()
        return dict(edge)

    @staticmethod
    def _with_freshness(record: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        result = json.loads(json.dumps(record))
        observed = _parse_time(result.get("observed_at"))
        instant = now or _now_dt()
        age = max(0.0, (instant - observed).total_seconds()) if observed else None
        stale_after = float(result.get("stale_after_seconds") or 1.0)
        result["freshness_seconds"] = round(age, 3) if age is not None else None
        result["stale"] = age is None or age > stale_after
        result["freshness"] = "STALE" if result["stale"] else "FRESH"
        return result

    def node(self, node_id: str) -> dict[str, Any]:
        value = str(node_id or "").strip()
        with self._lock:
            row = next((item for item in (self._state.get("nodes") or []) if item.get("node_id") == value), None)
            if row is None:
                raise KeyError("Unknown world-model node.")
            return self._with_freshness(row)

    def observe_cognitive_event(self, event: Any) -> None:
        event_type = str(getattr(event, "event_type", "") or "")
        subject = str(getattr(event, "subject", "") or "")
        payload = getattr(event, "payload", {}) or {}
        provenance = getattr(event, "provenance", {}) or {}
        timestamp = str(getattr(event, "timestamp", "") or "")
        source = str(getattr(event, "source", "") or "cognitive_event_bus")
        if not event_type or not subject:
            return
        self.observe(
            f"event-subject:{subject}"[:180],
            kind="COGNITIVE_EVENT_SUBJECT",
            label=subject,
            state={"event_type": event_type, "payload": payload},
            source=source,
            observed_at=timestamp,
            stale_after_seconds=900,
            confidence=0.95,
            provenance={"event": provenance, "event_type": event_type},
        )

    def refresh_local(self) -> dict[str, Any]:
        """Refresh a compact set of JARVIS-owned state observations.

        Every provider is isolated. A missing optional subsystem is represented as
        an unavailable observation rather than making the entire world model fail.
        """
        providers: list[tuple[str, str, str, Any, float]] = []
        try:
            from omni.mission_worker import MISSION_WORKER
            providers.append(("mission-worker", "MISSION_RUNTIME", "Mission Worker", MISSION_WORKER.status, 30.0))
        except Exception:
            pass
        try:
            from omni.goal_task_graph import GOAL_TASK_GRAPHS
            providers.append(("goal-graphs", "MISSION_GRAPH", "Goal / Task Graphs", lambda: GOAL_TASK_GRAPHS.snapshot(limit=20), 60.0))
        except Exception:
            pass
        try:
            from omni.mission_queue import MISSION_QUEUE
            providers.append(("mission-queue", "MISSION_QUEUE", "Mission Queue", lambda: MISSION_QUEUE.snapshot(limit=30), 30.0))
        except Exception:
            pass
        try:
            from omni.workspace_command_center import snapshot as workspace_snapshot
            providers.append(("workspaces", "SYSTEM", "Workspace Runtime", workspace_snapshot, 30.0))
        except Exception:
            pass
        try:
            from workstation.paper_trading_desk import paper_desk
            providers.append(("paper-portfolio", "PAPER_PORTFOLIO", "Paper Portfolio", paper_desk.snapshot, 30.0))
        except Exception:
            pass
        try:
            from workstation.market_event_bus import MARKET_EVENT_BUS
            providers.append(("market-events", "MARKET", "Verified Market Events", lambda: MARKET_EVENT_BUS.snapshot(limit=25), 60.0))
        except Exception:
            pass

        refreshed: list[str] = []
        failures: list[dict[str, str]] = []
        for node_id, kind, label, provider, stale_after in providers:
            try:
                value = provider()
                self.observe(
                    node_id,
                    kind=kind,
                    label=label,
                    state=value,
                    source=getattr(provider, "__module__", "jarvis.local"),
                    confidence=1.0,
                    stale_after_seconds=stale_after,
                    provenance={"scope": "JARVIS_LOCAL_STATE", "verified_read": True},
                )
                refreshed.append(node_id)
            except Exception as exc:
                failures.append({"node_id": node_id, "error_type": type(exc).__name__})
        return {
            "success": True,
            "refreshed": refreshed,
            "failures": failures,
            "paper_only": True,
            "live_execution": False,
            "external_actions": "APPROVAL_GATED",
        }

    def snapshot(
        self,
        *,
        limit: int = 100,
        kinds: Iterable[str] | None = None,
        include_stale: bool = True,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), MAX_NODES))
        allowed = {str(item).upper() for item in kinds} if kinds else None
        now = _now_dt()
        with self._lock:
            raw_nodes = json.loads(json.dumps(self._state.get("nodes") or []))
            raw_edges = json.loads(json.dumps(self._state.get("edges") or []))
            updated_at = self._state.get("updated_at")
        nodes = [self._with_freshness(item, now=now) for item in raw_nodes]
        if allowed is not None:
            nodes = [item for item in nodes if str(item.get("kind") or "").upper() in allowed]
        if not include_stale:
            nodes = [item for item in nodes if not item.get("stale")]
        nodes = nodes[:limit]
        visible_ids = {item.get("node_id") for item in nodes}
        edges = [
            item for item in raw_edges
            if item.get("source") in visible_ids or item.get("target") in visible_ids
        ][: min(MAX_EDGES, limit * 4)]
        stale_count = sum(1 for item in nodes if item.get("stale"))
        return {
            "success": True,
            "version": "9.3",
            "updated_at": updated_at,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "stale_count": stale_count,
            "nodes": nodes,
            "edges": edges,
            "persistent": True,
            "provenance_required": True,
            "freshness_explicit": True,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


WORLD_MODEL = WorldStateGraph()

# World-model updates are a safe internal reaction to cognitive events. Failure to
# install the subscriber must not prevent JARVIS startup; the explicit refresh
# path remains available.
try:
    from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS
    COGNITIVE_EVENT_BUS.subscribe("world-model", WORLD_MODEL.observe_cognitive_event)
except Exception:
    pass


__all__ = ["WORLD_MODEL", "WorldStateGraph"]
