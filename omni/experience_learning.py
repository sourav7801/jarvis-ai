from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

import json
from pathlib import Path
import threading
import time
import uuid


@dataclass(frozen=True)
class ExperienceRecord:

    experience_id: str

    kind: str

    capability: str

    success: bool

    score: float

    summary: str

    lessons: tuple[str, ...]

    metadata: dict

    created_at: float


class ExperienceStore:

    def __init__(
        self,
        path,
    ):

        self.path = Path(
            path
        )

        self._lock = (
            threading.RLock()
        )


    def append(
        self,
        *,
        kind,
        capability,
        success,
        score,
        summary,
        lessons=(),
        metadata=None,
    ):

        record = ExperienceRecord(
            experience_id=(
                "exp-"
                + uuid.uuid4().hex[:16]
            ),

            kind=str(
                kind
            ),

            capability=str(
                capability
            ),

            success=bool(
                success
            ),

            score=max(
                0.0,
                min(
                    float(score),
                    100.0,
                ),
            ),

            summary=str(
                summary
            )[:4000],

            lessons=tuple(
                str(x)[:1000]
                for x in lessons
            ),

            metadata=dict(
                metadata
                or {}
            ),

            created_at=time.time(),
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        line = json.dumps(
            asdict(record),
            ensure_ascii=False,
            default=str,
        )

        with self._lock:

            with self.path.open(
                "a",
                encoding="utf-8",
            ) as handle:

                handle.write(
                    line
                    + "\n"
                )

        return record


    def all(self):

        if not self.path.exists():
            return ()

        records = []

        for line in (
            self.path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        ):

            line = line.strip()

            if not line:
                continue

            try:

                data = json.loads(
                    line
                )

                records.append(
                    ExperienceRecord(
                        experience_id=
                            data[
                                "experience_id"
                            ],

                        kind=
                            data[
                                "kind"
                            ],

                        capability=
                            data[
                                "capability"
                            ],

                        success=
                            bool(
                                data[
                                    "success"
                                ]
                            ),

                        score=
                            float(
                                data[
                                    "score"
                                ]
                            ),

                        summary=
                            data[
                                "summary"
                            ],

                        lessons=
                            tuple(
                                data.get(
                                    "lessons",
                                    ()
                                )
                            ),

                        metadata=
                            dict(
                                data.get(
                                    "metadata",
                                    {},
                                )
                            ),

                        created_at=
                            float(
                                data[
                                    "created_at"
                                ]
                            ),
                    )
                )

            except Exception:
                continue

        return tuple(
            records
        )


    def recent(
        self,
        limit=20,
    ):

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

        return self.all()[
            -limit:
        ]


    def capability_history(
        self,
        capability,
        limit=50,
    ):

        value = str(
            capability
        )

        matches = [
            item
            for item in self.all()
            if (
                item.capability
                == value
            )
        ]

        return tuple(
            matches[
                -limit:
            ]
        )
