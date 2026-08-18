from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)

from enum import Enum

import json
from pathlib import Path
import time
import uuid
from typing import Any


class MissionStatus(str, Enum):

    PLANNED = "planned"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MissionTask:

    task_id: str
    agent: str
    role: str
    objective: str

    dependencies: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    status: TaskStatus = TaskStatus.PENDING

    attempts: int = 0

    output: Any = None
    error: str | None = None


@dataclass
class MissionPlan:

    mission_id: str

    goal: str
    intent: str

    lead_agent: str

    tasks: tuple[MissionTask, ...]

    confidence: float = 1.0

    requires_approval: bool = False

    created_at: float = field(
        default_factory=time.time
    )


@dataclass
class MissionResult:

    mission_id: str
    goal: str

    status: MissionStatus

    plan: MissionPlan

    final_answer: str = ""

    success: bool = False
    verified: bool = False

    recovery_count: int = 0

    errors: tuple[str, ...] = ()

    completed_at: float = field(
        default_factory=time.time
    )


def new_mission_id():

    return (
        "mission-"
        + uuid.uuid4().hex[:16]
    )


class MissionStore:
    """
    Durable operational mission history.

    HybridMemory remains the semantic memory system.
    """

    def __init__(
        self,
        root: Path | str,
    ):

        self.root = Path(
            root
        )


    def _path(
        self,
        mission_id,
    ):

        return (
            self.root
            / f"{mission_id}.json"
        )


    def save(
        self,
        result: MissionResult,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = asdict(
            result
        )

        payload[
            "status"
        ] = result.status.value

        for task in payload[
            "plan"
        ][
            "tasks"
        ]:

            status = task.get(
                "status"
            )

            if hasattr(
                status,
                "value",
            ):

                task[
                    "status"
                ] = status.value

        path = self._path(
            result.mission_id
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            path
        )

        return path


    def exists(
        self,
        mission_id,
    ):

        return self._path(
            mission_id
        ).exists()


    def read_raw(
        self,
        mission_id,
    ):

        return json.loads(
            self._path(
                mission_id
            ).read_text(
                encoding="utf-8"
            )
        )
