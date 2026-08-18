from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omni.experience_learning import (
    ExperienceStore,
)

from omni.capability_scorecard import (
    CapabilityScorecard,
)


@dataclass(frozen=True)
class Reflection:

    mission_id: str

    success: bool

    verified: bool

    score: float

    strengths: tuple[str, ...]

    weaknesses: tuple[str, ...]

    lessons: tuple[str, ...]


def reflect_mission(
    result,
):

    success = bool(
        getattr(
            result,
            "success",
            False,
        )
    )

    verified = bool(
        getattr(
            result,
            "verified",
            False,
        )
    )

    errors = tuple(
        getattr(
            result,
            "errors",
            (),
        )
        or ()
    )

    recovery_count = int(
        getattr(
            result,
            "recovery_count",
            0,
        )
        or 0
    )

    score = 100.0

    strengths = []
    weaknesses = []
    lessons = []


    if success:

        strengths.append(
            "Mission produced a usable result."
        )

    else:

        score -= 45.0

        weaknesses.append(
            "Mission did not complete successfully."
        )

        lessons.append(
            "Investigate planning, capability "
            "availability and failure recovery."
        )


    if verified:

        strengths.append(
            "Independent verification completed."
        )

    else:

        score -= 15.0

        weaknesses.append(
            "Result was not independently verified."
        )

        lessons.append(
            "Strengthen verification before trusting "
            "similar mission outputs."
        )


    if recovery_count:

        score -= min(
            20.0,
            recovery_count
            * 8.0,
        )

        weaknesses.append(
            "Mission required recovery."
        )

        lessons.append(
            "Review lead-agent selection and "
            "failure-handling strategy."
        )


    if errors:

        penalty = min(
            25.0,
            len(errors)
            * 5.0,
        )

        score -= penalty

        weaknesses.append(
            f"{len(errors)} execution error(s) occurred."
        )

        lessons.append(
            "Analyze repeated specialist failures "
            "and capability gaps."
        )


    plan = getattr(
        result,
        "plan",
        None,
    )

    tasks = (
        getattr(
            plan,
            "tasks",
            (),
        )
        if plan is not None
        else ()
    )

    repeated_attempts = sum(
        max(
            0,
            int(
                getattr(
                    task,
                    "attempts",
                    0,
                )
                or 0
            )
            - 1,
        )
        for task in tasks
    )

    if repeated_attempts:

        score -= min(
            15.0,
            repeated_attempts
            * 3.0,
        )

        weaknesses.append(
            "One or more tasks required retries."
        )

        lessons.append(
            "Investigate prompts, dependencies "
            "or unreliable specialist execution."
        )


    score = max(
        0.0,
        min(
            score,
            100.0,
        ),
    )

    return Reflection(
        mission_id=str(
            getattr(
                result,
                "mission_id",
                "unknown",
            )
        ),

        success=success,

        verified=verified,

        score=score,

        strengths=tuple(
            strengths
        ),

        weaknesses=tuple(
            weaknesses
        ),

        lessons=tuple(
            lessons
        ),
    )


def record_mission_reflection(
    result,
    *,
    project_id=None,
):

    reflection = reflect_mission(
        result
    )

    root = Path("data") / "self_improvement"

    store = ExperienceStore(
        root
        / "experience.jsonl"
    )

    scorecard = CapabilityScorecard(
        root
        / "capability_scorecard.json"
    )

    record = store.append(
        kind="mission_reflection",

        capability="mission_execution",

        success=
            reflection.success,

        score=
            reflection.score,

        summary=(
            "Mission "
            + reflection.mission_id
            + " reflection"
        ),

        lessons=
            reflection.lessons,

        metadata={
            "mission_id":
                reflection.mission_id,

            "verified":
                reflection.verified,

            "strengths":
                reflection.strengths,

            "weaknesses":
                reflection.weaknesses,

            "project_id":
                project_id,
        },
    )

    scorecard.record(
        "mission_execution",

        reflection.score,

        evidence=(
            "Mission "
            + reflection.mission_id
        ),

        source=
            "reflection",
    )

    # Semantic memory is reserved for notable lessons,
    # not every successful mission.

    if (
        reflection.weaknesses
        or reflection.lessons
    ):

        try:

            from omni.memory_context import (
                remember_scoped,
            )

            from omni.memory_scope import (
                MemoryScope,
            )

            content = (
                "JARVIS mission reflection\n"
                "Mission: "
                + reflection.mission_id
                + "\nScore: "
                + str(
                    reflection.score
                )
                + "\nLessons: "
                + "; ".join(
                    reflection.lessons
                )
            )

            remember_scoped(
                content,

                MemoryScope.AGENT_FINDING,

                source="jarvis",

                project_id=
                    project_id,

                tags=(
                    "mission-reflection",
                    "self-improvement",
                ),

                metadata={
                    "mission_id":
                        reflection.mission_id,

                    "reflection_score":
                        reflection.score,
                },
            )

        except Exception:
            pass


    # High-quality verified missions may become reusable skill proposals.
    try:
        if (reflection.success and reflection.verified and reflection.score >= 85.0):
            from omni.capability_growth import skill_extractor
            skill_extractor.extract_from_mission(
                result,
                reflection.score,
            )
    except Exception:
        pass

    return (
        reflection,
        record,
    )
