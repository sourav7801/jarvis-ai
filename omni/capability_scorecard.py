from __future__ import annotations

import json
from pathlib import Path
import threading
import time


class CapabilityScorecard:

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


    def _empty(self):

        return {
            "capabilities": {},
            "updated_at": None,
        }


    def _load(self):

        if not self.path.exists():
            return self._empty()

        try:

            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            data.setdefault(
                "capabilities",
                {},
            )

            return data

        except Exception:

            return self._empty()


    def _save(
        self,
        data,
    ):

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = (
            self.path
            .with_suffix(
                ".tmp"
            )
        )

        temp.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            self.path
        )


    def record(
        self,
        capability,
        score,
        *,
        evidence,
        source="benchmark",
    ):

        capability = str(
            capability
        ).strip()

        if not capability:

            raise ValueError(
                "capability cannot be empty"
            )

        score = max(
            0.0,
            min(
                float(score),
                100.0,
            ),
        )

        with self._lock:

            data = self._load()

            current = data[
                "capabilities"
            ].get(
                capability,
                {
                    "score": 0.0,
                    "evidence_count": 0,
                    "history": [],
                },
            )

            count = int(
                current.get(
                    "evidence_count",
                    0,
                )
            )

            previous = float(
                current.get(
                    "score",
                    0.0,
                )
            )

            new_score = (
                (
                    previous * count
                )
                + score
            ) / (
                count + 1
            )

            history = list(
                current.get(
                    "history",
                    [],
                )
            )

            history.append(
                {
                    "score":
                        score,

                    "evidence":
                        str(
                            evidence
                        )[:1000],

                    "source":
                        str(source),

                    "timestamp":
                        time.time(),
                }
            )

            history = history[
                -100:
            ]

            data[
                "capabilities"
            ][
                capability
            ] = {
                "score":
                    round(
                        new_score,
                        4,
                    ),

                "evidence_count":
                    count + 1,

                "last_evidence":
                    str(
                        evidence
                    )[:1000],

                "last_source":
                    str(source),

                "history":
                    history,
            }

            data[
                "updated_at"
            ] = time.time()

            self._save(
                data
            )

            return dict(
                data[
                    "capabilities"
                ][
                    capability
                ]
            )


    def get(
        self,
        capability,
    ):

        return (
            self._load()[
                "capabilities"
            ].get(
                str(
                    capability
                )
            )
        )


    def snapshot(self):

        return dict(
            self._load()[
                "capabilities"
            ]
        )


    def weaknesses(
        self,
        *,
        threshold=75.0,
        minimum_evidence=1,
    ):

        threshold = float(
            threshold
        )

        results = []

        for (
            capability,
            data,
        ) in self.snapshot().items():

            if (
                int(
                    data.get(
                        "evidence_count",
                        0,
                    )
                )
                < minimum_evidence
            ):
                continue

            score = float(
                data.get(
                    "score",
                    0.0,
                )
            )

            if score < threshold:

                results.append(
                    {
                        "capability":
                            capability,

                        "score":
                            score,

                        "gap":
                            threshold
                            - score,

                        "evidence_count":
                            data.get(
                                "evidence_count",
                                0,
                            ),
                    }
                )

        results.sort(
            key=lambda item:
                item[
                    "score"
                ]
        )

        return tuple(
            results
        )
