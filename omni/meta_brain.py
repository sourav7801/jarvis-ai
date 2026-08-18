from __future__ import annotations

from omni.brain import (
    BrainDecision,
    DelegationPlan,
    DelegationStep,
    brain as base_brain,
)

from omni.agent_registry import (
    default_agent_specs,
)


META_AGENTS = {
    "learning",
    "knowledge",
    "skill_builder",
    "experiment",
    "evaluator",
    "critic",
    "meta_improvement",
}


class MetaBrain:

    def __init__(
        self,
        base=base_brain,
    ):
        self.base = base


    def specs(self):

        return {
            spec.name: spec
            for spec
            in default_agent_specs()
        }


    def agent_names(self):

        return tuple(
            self.specs().keys()
        )


    def capabilities(
        self,
        agent,
    ):

        spec = self.specs().get(
            agent
        )

        if spec is None:
            return ()

        return tuple(
            sorted(
                spec.capabilities
            )
        )


    @staticmethod
    def contains(
        text,
        values,
    ):

        return any(
            value in text
            for value in values
        )


    def decide(
        self,
        request,
    ):

        text = str(
            request or ""
        ).lower()


        if self.contains(
            text,
            (
                "improve yourself",
                "improve jarvis",
                "make jarvis better",
                "upgrade jarvis",
                "self improve",
                "self-improve",
                "improve your capability",
                "improve your architecture",
            ),
        ):

            return BrainDecision(
                intent=
                    "meta_improvement",

                primary_agent=
                    "meta_improvement",

                supporting_agents=(
                    "evaluator",
                    "critic",
                    "engineering",
                    "security",
                ),

                confidence=0.99,

                reason=(
                    "Explicit JARVIS "
                    "improvement request."
                ),

                capabilities=(
                    "system.improvement.propose",
                ),
            )


        if self.contains(
            text,
            (
                "create a skill",
                "build a skill",
                "new skill",
                "create capability",
                "new capability",
                "skill factory",
            ),
        ):

            return BrainDecision(
                intent=
                    "skill_creation",

                primary_agent=
                    "skill_builder",

                supporting_agents=(
                    "coding",
                    "security",
                    "evaluator",
                ),

                confidence=0.98,

                reason=(
                    "Reusable skill request."
                ),

                capabilities=(
                    "skill.propose",
                ),
            )


        if self.contains(
            text,
            (
                "knowledge graph",
                "world model",
                "structure knowledge",
                "organize knowledge",
            ),
        ):

            return BrainDecision(
                intent="knowledge",

                primary_agent="knowledge",

                supporting_agents=(
                    "research",
                    "learning",
                ),

                confidence=0.97,

                reason=(
                    "Structured knowledge request."
                ),

                capabilities=(
                    "knowledge.structure",
                ),
            )


        if self.contains(
            text,
            (
                "learn ",
                "learn about",
                "learn how",
                "study ",
                "master ",
                "teach yourself",
                "knowledge gap",
            ),
        ):

            return BrainDecision(
                intent="learning",

                primary_agent="learning",

                supporting_agents=(
                    "research",
                    "web_intelligence",
                    "knowledge",
                ),

                confidence=0.98,

                reason=(
                    "Knowledge acquisition request."
                ),

                capabilities=(
                    "learning.acquire",
                ),
            )


        if self.contains(
            text,
            (
                "benchmark",
                "evaluate jarvis",
                "evaluate performance",
                "capability score",
                "score jarvis",
            ),
        ):

            return BrainDecision(
                intent="evaluation",

                primary_agent="evaluator",

                supporting_agents=(
                    "experiment",
                    "critic",
                    "quality",
                ),

                confidence=0.98,

                reason=(
                    "Evaluation request."
                ),

                capabilities=(
                    "evaluation.score",
                ),
            )


        if self.contains(
            text,
            (
                "run experiment",
                "controlled experiment",
                "a/b test",
                "ab test",
                "compare approaches",
            ),
        ):

            return BrainDecision(
                intent="experiment",

                primary_agent="experiment",

                supporting_agents=(
                    "evaluator",
                    "research",
                ),

                confidence=0.97,

                reason=(
                    "Controlled experiment request."
                ),

                capabilities=(
                    "experiment.design",
                ),
            )


        if self.contains(
            text,
            (
                "critique",
                "find flaws",
                "challenge this plan",
                "red team this",
                "attack this plan",
            ),
        ):

            return BrainDecision(
                intent="critique",

                primary_agent="critic",

                supporting_agents=(
                    "evaluator",
                    "quality",
                ),

                confidence=0.97,

                reason=(
                    "Independent critique request."
                ),

                capabilities=(
                    "critique.review",
                ),
            )


        return self.base.decide(
            request
        )


    def plan(
        self,
        request,
    ):

        decision = self.decide(
            request
        )

        if (
            decision.primary_agent
            not in META_AGENTS
        ):

            return self.base.plan(
                request
            )

        specs = self.specs()

        requested = [
            decision.primary_agent,
            *decision.supporting_agents,
        ]

        agents = []

        for agent in requested:

            if (
                agent in specs
                and agent not in agents
            ):
                agents.append(agent)

        steps = tuple(
            DelegationStep(
                order=index,

                agent=agent,

                role=(
                    "lead"
                    if index == 1
                    else "support"
                ),

                capabilities=
                    self.capabilities(
                        agent
                    ),
            )

            for index, agent
            in enumerate(
                agents,
                1,
            )
        )

        return DelegationPlan(
            request=str(request),

            intent=
                decision.intent,

            lead_agent=
                decision.primary_agent,

            steps=steps,

            confidence=
                decision.confidence,

            requires_approval=
                decision.requires_approval,
        )


meta_brain = MetaBrain()
