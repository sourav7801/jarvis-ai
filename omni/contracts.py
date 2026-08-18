"""Typed, serializable contracts shared by planners and executors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


@dataclass
class Step:
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    max_attempts: int = 1
    id: str = field(default_factory=lambda: uuid4().hex)
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    output: Any = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.action = str(self.action).strip()
        if not self.action:
            raise ValueError("Step action cannot be empty.")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5.")
        if self.id in self.depends_on:
            raise ValueError("A step cannot depend on itself.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Step":
        payload = dict(data)
        payload["status"] = StepStatus(payload.get("status", StepStatus.PENDING))
        return cls(**payload)


@dataclass
class Plan:
    objective: str
    steps: list[Step]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)
    cancelled: bool = False

    def __post_init__(self) -> None:
        self.objective = str(self.objective).strip()
        if not self.objective:
            raise ValueError("Plan objective cannot be empty.")
        self.validate()

    def validate(self) -> None:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Step IDs must be unique.")
        known = set(ids)
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(
                    f"Step '{step.id}' has unknown dependencies: {sorted(missing)}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()
        dependencies = {step.id: step.depends_on for step in self.steps}

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise ValueError("Plan contains a dependency cycle.")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in ids:
            visit(step_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "created_at": self.created_at,
            "cancelled": self.cancelled,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        payload = dict(data)
        payload["steps"] = [Step.from_dict(item) for item in payload.get("steps", [])]
        return cls(**payload)


@dataclass(frozen=True)
class StepResult:
    success: bool
    output: Any = None
    error: str | None = None
