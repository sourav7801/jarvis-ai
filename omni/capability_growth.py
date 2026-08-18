from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import hashlib
import json
import re
import time


from omni.dynamic_specialists import (
    dynamic_specialists,
)

from omni.self_improvement_lab import (
    self_improvement_lab,
)

from omni.universal_learning import (
    universal_learning,
)


@dataclass(frozen=True)
class ModelRoleRoute:

    role: str

    reason: str

    privacy_required: bool = False

    fallback_role: str | None = None


class ModelRoleRouter:

    def route(
        self,
        request,
        *,
        sensitive=False,
        offline=False,
    ):

        text = str(
            request
            or ""
        ).lower()


        if sensitive or offline:

            return ModelRoleRoute(
                role=
                    "local_private",

                reason=
                    "Private/offline request.",

                privacy_required=
                    True,

                fallback_role=None,
            )


        if any(
            word in text

            for word in (
                "debug",
                "python",
                "codebase",
                "repository",
                "refactor",
                "implement",
                "write code",
            )
        ):

            return ModelRoleRoute(
                role="coding",

                reason=
                    "Software engineering task.",

                fallback_role=
                    "reasoning",
            )


        if any(
            word in text

            for word in (
                "research",
                "latest",
                "news",
                "search",
                "sources",
                "learn about",
                "current information",
            )
        ):

            return ModelRoleRoute(
                role="research",

                reason=
                    "Research/current information task.",

                fallback_role=
                    "reasoning",
            )


        if any(
            word in text

            for word in (
                "analyze",
                "architecture",
                "strategy",
                "evaluate",
                "plan",
                "reason",
                "improve jarvis",
            )
        ):

            return ModelRoleRoute(
                role="reasoning",

                reason=
                    "Complex reasoning task.",

                fallback_role=
                    "fast",
            )


        return ModelRoleRoute(
            role="fast",

            reason=
                "Routine low-complexity request.",

            fallback_role=
                "reasoning",
        )


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


    def extract_from_mission(
        self,
        result,
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
                None,
            )
            or getattr(
                plan,
                "goal",
                None,
            )
            or "mission"
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
                re.sub(
                    r"[^a-zA-Z0-9]+",
                    "_",
                    goal.lower(),
                ).strip(
                    "_"
                )[:60],

            "purpose":
                goal[:2000],

            "source_mission":
                str(
                    getattr(
                        result,
                        "mission_id",
                        "",
                    )
                ),

            "reflection_score":
                float(
                    reflection_score
                ),

            "agents":
                sorted(
                    {
                        str(
                            getattr(
                                task,
                                "agent",
                                "",
                            )
                        )

                        for task
                        in tasks

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

                for task
                in tasks
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


        temp.replace(
            path
        )


        return proposal


    def proposals(self):

        if not self.root.exists():

            return ()


        output = []


        for path in self.root.glob(
            "skill-proposal-*.json"
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


        return tuple(
            output
        )


class CapabilityGrowthEngine:

    def status(self):

        return {
            "permanent_agents":
                29,

            "learning_artifacts":
                len(
                    universal_learning
                    .artifacts()
                ),

            "skill_proposals":
                len(
                    skill_extractor
                    .proposals()
                ),

            "specialist_candidates":
                len(
                    dynamic_specialists
                    .promotion_recommendations()
                ),

            "known_weaknesses":
                len(
                    self_improvement_lab
                    .weaknesses()
                ),

            "dynamic_specialists":
                True,

            "automatic_permanent_agents":
                False,

            "automatic_skill_promotion":
                False,

            "automatic_self_modification":
                False,
        }


    def next_actions(self):

        actions = []


        for weakness in (
            self_improvement_lab
            .weaknesses()
        ):

            actions.append(
                {
                    "type":
                        "improve_capability",

                    "capability":
                        weakness[
                            "capability"
                        ],

                    "score":
                        weakness[
                            "score"
                        ],
                }
            )


        for proposal in (
            skill_extractor
            .proposals()
        ):

            if (
                proposal.get(
                    "state"
                )
                == "proposal"
            ):

                actions.append(
                    {
                        "type":
                            "evaluate_skill",

                        "proposal_id":
                            proposal[
                                "proposal_id"
                            ],
                    }
                )


        for specialist in (
            dynamic_specialists
            .promotion_recommendations()
        ):

            actions.append(
                {
                    "type":
                        "review_specialist",

                    "specialist_id":
                        specialist[
                            "specialist_id"
                        ],

                    "domain":
                        specialist[
                            "domain"
                        ],

                    "score":
                        specialist[
                            "average_score"
                        ],
                }
            )


        return tuple(
            actions
        )


model_role_router = (
    ModelRoleRouter()
)

skill_extractor = (
    SkillExtractor()
)

capability_growth = (
    CapabilityGrowthEngine()
)
