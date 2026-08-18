import unittest

from omni.agent_registry import (
    default_agent_specs,
)

from omni.meta_brain import (
    meta_brain,
)


class MetaAgentTests(
    unittest.TestCase
):

    def test_29_unique_agents(self):

        specs = default_agent_specs()

        self.assertEqual(
            len(specs),
            29,
        )

        self.assertEqual(
            len({
                x.name
                for x in specs
            }),
            29,
        )


    def test_meta_agents_present(self):

        names = {
            x.name
            for x
            in default_agent_specs()
        }

        expected = {
            "learning",
            "knowledge",
            "skill_builder",
            "experiment",
            "evaluator",
            "critic",
            "meta_improvement",
        }

        self.assertTrue(
            expected.issubset(
                names
            )
        )


    def test_learning_route(self):

        plan = meta_brain.plan(
            "Learn about distributed systems"
        )

        self.assertEqual(
            plan.lead_agent,
            "learning",
        )

        self.assertIn(
            "research",
            plan.agents,
        )


    def test_skill_route(self):

        plan = meta_brain.plan(
            "Create a skill for telemetry parsing"
        )

        self.assertEqual(
            plan.lead_agent,
            "skill_builder",
        )


    def test_improvement_route(self):

        plan = meta_brain.plan(
            "Improve Jarvis planning capability"
        )

        self.assertEqual(
            plan.lead_agent,
            "meta_improvement",
        )

        self.assertIn(
            "evaluator",
            plan.agents,
        )

        self.assertIn(
            "critic",
            plan.agents,
        )


if __name__ == "__main__":
    unittest.main()
