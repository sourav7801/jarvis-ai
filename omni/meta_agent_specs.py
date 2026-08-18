from __future__ import annotations

from omni.agent_registry import AgentSpec


def meta_agent_specs():

    return (

        AgentSpec(
            name="learning",
            module="agents.meta_learning",
            entrypoint="run",
            label="Learning Agent",
            capabilities=frozenset({
                "learning.acquire",
            }),
        ),

        AgentSpec(
            name="knowledge",
            module="agents.meta_knowledge",
            entrypoint="run",
            label="Knowledge Agent",
            capabilities=frozenset({
                "knowledge.structure",
            }),
        ),

        AgentSpec(
            name="skill_builder",
            module="agents.meta_skill_builder",
            entrypoint="run",
            label="Skill Builder Agent",
            capabilities=frozenset({
                "skill.propose",
            }),
        ),

        AgentSpec(
            name="experiment",
            module="agents.meta_experiment",
            entrypoint="run",
            label="Experiment Agent",
            capabilities=frozenset({
                "experiment.design",
            }),
        ),

        AgentSpec(
            name="evaluator",
            module="agents.meta_evaluator",
            entrypoint="run",
            label="Evaluator Agent",
            capabilities=frozenset({
                "evaluation.score",
            }),
        ),

        AgentSpec(
            name="critic",
            module="agents.meta_critic",
            entrypoint="run",
            label="Critic Agent",
            capabilities=frozenset({
                "critique.review",
            }),
        ),

        AgentSpec(
            name="meta_improvement",
            module="agents.meta_improvement",
            entrypoint="run",
            label="Meta Improvement Agent",
            capabilities=frozenset({
                "system.improvement.propose",
            }),
        ),
    )
