from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


class OperatorMemory:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "operator"
                / "missions.jsonl"
            )
        )


    def record(
        self,
        *,
        goal,
        success,
        steps,
        failed_step=None,
        lesson=None,
        metadata=None,
        project_id=None,
    ):

        record = {
            "operator_memory_id":
                (
                    "operator-memory-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "goal":
                str(
                    goal
                )[:4000],

            "success":
                bool(
                    success
                ),

            "steps":
                int(
                    steps
                ),

            "failed_step":
                failed_step,

            "lesson":
                str(
                    lesson
                    or ""
                )[:4000],

            "metadata":
                dict(
                    metadata
                    or {}
                ),

            "created_at":
                time.time(),
        }


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


        if (
            failed_step
            or lesson
        ):

            try:

                from omni.memory_context import (
                    remember_scoped,
                )

                from omni.memory_scope import (
                    MemoryScope,
                )


                scope = (
                    MemoryScope.PROJECT
                    if project_id
                    else MemoryScope.AGENT_FINDING
                )


                remember_scoped(
                    (
                        "JARVIS computer operator "
                        "experience\nGoal: "
                        + str(
                            goal
                        )[:2000]
                        + "\nSuccess: "
                        + str(
                            bool(
                                success
                            )
                        )
                        + "\nFailed step: "
                        + str(
                            failed_step
                            or ""
                        )
                        + "\nLesson: "
                        + str(
                            lesson
                            or ""
                        )[:2000]
                    ),

                    scope,

                    source=
                        "jarvis",

                    project_id=
                        project_id,

                    tags=(
                        "computer-operator",
                        "operator-learning",
                    ),

                    metadata={
                        "failed_step":
                            failed_step,

                        "success":
                            bool(
                                success
                            ),
                    },
                )


            except Exception:

                pass


        return record


    def recent(
        self,
        limit=20,
    ):

        if not self.path.exists():

            return ()


        output = []


        for line in (
            self.path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        ):

            try:

                output.append(
                    json.loads(
                        line
                    )
                )

            except Exception:

                continue


        return tuple(
            output[
                -max(
                    1,
                    int(
                        limit
                    ),
                ):
            ]
        )


operator_memory = (
    OperatorMemory()
)
