from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time


class SkillExtractor:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "skill_proposals"
            )
        )


    @staticmethod
    def safe_name(
        value,
    ):

        value = re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            str(value).lower(),
        ).strip(
            "_"
        )

        return (
            value[:60]
            or "mission_skill"
        )


    def extract_from_mission(
        self,
        result,
        *,
        reflection_score,
    ):

        if not bool(
            getattr(
                result,
                "success",
                False,
            )
        ):
            return None

        if not bool(
            getattr(
                result,
                "verified",
                False,
            )
        ):
            return None

        if float(
            reflection_score
        ) < 85:
            return None


        plan = getattr(
            result,
            "plan",
            None,
        )

        tasks = tuple(
            getattr(
                plan,
                "tasks",
                (),
            )
            or ()
        )

        if len(tasks) < 2:
            return None


        goal = str(
            getattr(
                result,
                "goal",
                "mission",
            )
        )

        mission_id = str(
            getattr(
                result,
                "mission_id",
                "unknown",
            )
        )


        signature = hashlib.sha256(
            (
                goal
                + "|"
                + "|".join(
                    str(
                        getattr(
                            task,
                            "agent",
                            "",
                        )
                    )
                    for task
                    in tasks
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:16]


        proposal = {
            "proposal_id":
                (
                    "skill-proposal-"
                    + signature
                ),

            "name":
                self.safe_name(
                    goal
                ),

            "purpose":
                goal[:2000],

            "source_mission":
                mission_id,

            "reflection_score":
                float(
                    reflection_score
                ),

            "required_agents":
                sorted(
                    {
                        str(
                            getattr(
                                task,
                                "agent",
                                "",
                            )
                        )
                        for task in tasks
                        if getattr(
                            task,
                            "agent",
                            None,
                        )
                    }
                ),

            "procedure": [
                {
                    "agent":
                        str(
                            getattr(
                                task,
                                "agent",
                                "",
                            )
                        ),

                    "role":
                        str(
                            getattr(
                                task,
                                "role",
                                "",
                            )
                        ),

                    "objective":
                        str(
                            getattr(
                                task,
                                "objective",
                                "",
                            )
                        )[:2000],
                }

                for task in tasks
            ],

            "state":
                "proposal",

            "automatic_code_generation":
                False,

            "automatic_promotion":
                False,

            "requires_skill_builder":
                True,

            "requires_security_review":
                True,

            "requires_evaluator":
                True,

            "created_at":
                time.time(),
        }


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = (
            self.root
            / (
                proposal[
                    "proposal_id"
                ]
                + ".json"
            )
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                proposal,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(path)

        return proposal


    def proposals(self):

        if not self.root.exists():
            return ()

        output = []

        for path in sorted(
            self.root.glob(
                "skill-proposal-*.json"
            )
        ):

            try:
                output.append(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:
                continue

        return tuple(output)


skill_extractor = SkillExtractor()
