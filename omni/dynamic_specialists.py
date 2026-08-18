from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


from omni.collaboration_runtime import (
    build_runtime,
)


class DynamicSpecialistFactory:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "dynamic_specialists"
            )
        )


    def _path(
        self,
        specialist_id,
    ):

        return (
            self.root
            / (
                str(
                    specialist_id
                )
                + ".json"
            )
        )


    def _save(
        self,
        profile,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = self._path(
            profile[
                "specialist_id"
            ]
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                profile,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            path
        )


    def get(
        self,
        specialist_id,
    ):

        return json.loads(
            self._path(
                specialist_id
            ).read_text(
                encoding="utf-8"
            )
        )


    def create(
        self,
        domain,
        purpose,
    ):

        domain = " ".join(
            str(
                domain
            )
            .strip()
            .split()
        )

        if not domain:

            raise ValueError(
                "domain cannot be empty"
            )


        profile = {
            "specialist_id":
                (
                    "specialist-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "domain":
                domain[:200],

            "purpose":
                str(
                    purpose
                )[:2000],

            "status":
                "temporary",

            "missions":
                0,

            "successes":
                0,

            "score_total":
                0.0,

            "average_score":
                0.0,

            "promotion_eligible":
                False,

            "created_at":
                time.time(),

            "updated_at":
                time.time(),
        }


        self._save(
            profile
        )

        return profile


    def execute(
        self,
        specialist_id,
        task,
        runner=None,
    ):

        profile = self.get(
            specialist_id
        )


        if (
            profile[
                "status"
            ]
            == "retired"
        ):

            raise RuntimeError(
                "specialist is retired"
            )


        if runner is None:

            runner = (
                build_runtime()
                .runner
            )


        prompt = (
            "TEMPORARY JARVIS DOMAIN SPECIALIST\n"
            "Domain: "
            + profile[
                "domain"
            ]
            + "\nPurpose: "
            + profile[
                "purpose"
            ]
            + "\n\nTask:\n"
            + str(task)
            + "\n\n"
            "Use focused domain reasoning. "
            "Separate evidence from assumptions. "
            "State uncertainty explicitly."
        )


        # Temporary specialists never become arbitrary
        # ungoverned executors.
        #
        # Existing Research remains the governed carrier.

        return runner(
            "research",

            prompt,

            {
                "temporary_specialist":
                    specialist_id,

                "domain":
                    profile[
                        "domain"
                    ],
            },
        )


    def evaluate(
        self,
        specialist_id,
        score,
        success=True,
    ):

        profile = self.get(
            specialist_id
        )


        score = max(
            0.0,

            min(
                float(
                    score
                ),
                100.0,
            ),
        )


        profile[
            "missions"
        ] += 1


        if success:

            profile[
                "successes"
            ] += 1


        profile[
            "score_total"
        ] += score


        profile[
            "average_score"
        ] = round(
            profile[
                "score_total"
            ]
            / profile[
                "missions"
            ],
            2,
        )


        success_rate = (
            profile[
                "successes"
            ]
            / profile[
                "missions"
            ]
        )


        profile[
            "promotion_eligible"
        ] = bool(
            profile[
                "missions"
            ]
            >= 3

            and profile[
                "average_score"
            ]
            >= 85

            and success_rate
            >= 0.80
        )


        if (
            profile[
                "missions"
            ]
            >= 3

            and profile[
                "average_score"
            ]
            < 45
        ):

            profile[
                "status"
            ] = "retired"


        profile[
            "updated_at"
        ] = time.time()


        self._save(
            profile
        )

        return profile


    def promotion_recommendations(
        self,
    ):

        if not self.root.exists():
            return ()


        output = []


        for path in self.root.glob(
            "specialist-*.json"
        ):

            try:

                profile = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )


                if profile.get(
                    "promotion_eligible",
                    False,
                ):

                    output.append(
                        profile
                    )

            except Exception:
                continue


        return tuple(
            sorted(
                output,

                key=lambda item:
                    item.get(
                        "average_score",
                        0,
                    ),

                reverse=True,
            )
        )


dynamic_specialists = (
    DynamicSpecialistFactory()
)
