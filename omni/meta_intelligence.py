from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omni.autonomy_engine import (
    autonomy_engine,
)

from omni.knowledge_graph import (
    KnowledgeGraph,
)

from omni.memory_context import (
    recall_context,
)

from omni.skill_factory import (
    SkillFactory,
)


@dataclass(frozen=True)
class KnowledgeGap:

    subject: str

    gap_detected: bool

    confidence: float

    evidence_count: int


@dataclass(frozen=True)
class ImprovementProposal:

    capability: str

    current_score: float

    target_score: float

    gap: float

    recommendation: str

    requires_approval: bool = True


class MetaIntelligenceEngine:

    def __init__(
        self,
        *,
        graph=None,
        skill_factory=None,
    ):

        self.graph = (
            graph
            or KnowledgeGraph(
                Path("data")
                / "knowledge"
                / "world_model.json"
            )
        )

        self.skill_factory = (
            skill_factory
            or SkillFactory(
                Path("data")
                / "skill_factory"
            )
        )


    def detect_knowledge_gap(
        self,
        subject,
    ):

        subject = str(
            subject or ""
        ).strip()

        if not subject:

            raise ValueError(
                "subject cannot be empty"
            )

        try:

            evidence = recall_context(
                subject,
                limit=4,
            )

        except Exception:

            evidence = ()

        count = len(
            evidence
        )

        confidence = {
            0: 1.00,
            1: 0.75,
            2: 0.45,
        }.get(
            count,
            0.20,
        )

        return KnowledgeGap(
            subject=subject,

            gap_detected=(
                count < 3
            ),

            confidence=
                confidence,

            evidence_count=
                count,
        )


    def learn(
        self,
        subject,
        *,
        runner=None,
        project_id=None,
    ):

        subject = str(
            subject or ""
        ).strip()

        if not subject:

            raise ValueError(
                "subject cannot be empty"
            )

        goal = (
            "Learn deeply about "
            f"{subject}. "
            "Identify knowledge gaps, "
            "gather reliable evidence, "
            "structure the knowledge, "
            "separate facts from assumptions, "
            "and produce reusable knowledge "
            "for future JARVIS missions."
        )

        result = (
            autonomy_engine.execute(
                goal,
                runner=runner,
                project_id=project_id,
            )
        )

        if result.success:

            topic = (
                "topic:"
                + subject
                .lower()
                .replace(
                    " ",
                    "-"
                )[:100]
            )

            mission = (
                "mission:"
                + result.mission_id
            )

            self.graph.upsert_node(
                topic,

                kind="topic",

                label=subject,

                attributes={
                    "last_mission":
                        result.mission_id,

                    "verified":
                        result.verified,
                },
            )

            self.graph.upsert_node(
                mission,

                kind=
                    "learning_mission",

                label=
                    result.mission_id,

                attributes={
                    "success": True,

                    "verified":
                        result.verified,
                },
            )

            self.graph.link(
                mission,
                "learned_about",
                topic,
            )

        return result


    @staticmethod
    def propose_improvement(
        capability,
        current_score,
        target_score,
    ):

        current = max(
            0.0,
            min(
                float(
                    current_score
                ),
                100.0,
            ),
        )

        target = max(
            current,
            min(
                float(
                    target_score
                ),
                100.0,
            ),
        )

        gap = (
            target
            - current
        )

        if gap <= 0:

            recommendation = (
                "No capability gap detected."
            )

        elif gap < 10:

            recommendation = (
                "Run focused experiments "
                "against the existing implementation."
            )

        elif gap < 25:

            recommendation = (
                "Benchmark alternatives and "
                "build a sandbox candidate."
            )

        else:

            recommendation = (
                "Launch a learning mission, "
                "research alternative architecture, "
                "build isolated candidates, benchmark "
                "them, run security review and require "
                "approval before promotion."
            )

        return ImprovementProposal(
            capability=
                str(capability),

            current_score=
                current,

            target_score=
                target,

            gap=gap,

            recommendation=
                recommendation,

            requires_approval=True,
        )


meta_intelligence = (
    MetaIntelligenceEngine()
)
