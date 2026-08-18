import unittest

from omni.collaboration import CollaborationEngine


class CollaborationTests(unittest.TestCase):

    def setUp(self):
        self.engine = CollaborationEngine()

    def test_company_specialists_feed_lead(self):

        calls = []

        def runner(agent, request, context):

            calls.append(
                (agent, context)
            )

            if context["role"] == "lead":

                findings = context[
                    "specialist_findings"
                ]

                return {
                    "answer":
                        f"Synthesized {len(findings)} findings"
                }

            return f"{agent} analysis"

        result = self.engine.collaborate(
            "Build a business plan for my startup",
            runner,
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.lead_agent,
            "strategy",
        )

        self.assertIn(
            "product",
            result.participating_agents,
        )

        self.assertIn(
            "finance",
            result.participating_agents,
        )

        self.assertIn(
            "marketing",
            result.participating_agents,
        )

        self.assertIn(
            "operations",
            result.participating_agents,
        )

        self.assertEqual(
            result.participating_agents[-1],
            "strategy",
        )

        self.assertEqual(
            result.final_answer,
            "Synthesized 4 findings",
        )

    def test_trading_collaboration(self):

        def runner(agent, request, context):

            if context["role"] == "lead":
                return "WAIT - insufficient edge"

            return f"{agent}: analysis complete"

        result = self.engine.collaborate(
            "Analyze NIFTY for a paper trading setup",
            runner,
        )

        self.assertEqual(
            result.lead_agent,
            "trading",
        )

        self.assertIn(
            "research",
            result.participating_agents,
        )

        self.assertIn(
            "web_intelligence",
            result.participating_agents,
        )

        self.assertEqual(
            result.final_answer,
            "WAIT - insufficient edge",
        )

    def test_support_failure_does_not_crash_team(self):

        def runner(agent, request, context):

            if (
                agent == "finance"
                and context["role"] == "support"
            ):
                raise RuntimeError(
                    "finance unavailable"
                )

            if context["role"] == "lead":
                return "Lead synthesis"

            return "OK"

        result = self.engine.collaborate(
            "Build a startup business plan",
            runner,
        )

        self.assertTrue(result.success)

        failures = [
            item
            for item in result.contributions
            if not item.success
        ]

        self.assertEqual(
            len(failures),
            1,
        )

        self.assertEqual(
            failures[0].agent,
            "finance",
        )

    def test_lead_failure_fails_result(self):

        def runner(agent, request, context):

            if context["role"] == "lead":
                raise RuntimeError("lead failed")

            return "support result"

        result = self.engine.collaborate(
            "Debug and secure Python software",
            runner,
        )

        self.assertFalse(
            result.success
        )

    def test_simple_chat_uses_only_lead(self):

        calls = []

        def runner(agent, request, context):
            calls.append(agent)
            return "Hello"

        result = self.engine.collaborate(
            "Hello Jarvis",
            runner,
        )

        self.assertEqual(
            calls,
            ["chat"],
        )

        self.assertEqual(
            result.final_answer,
            "Hello",
        )

    def test_context_is_bounded(self):

        engine = CollaborationEngine(
            max_context_items=2
        )

        seen = {}

        def runner(agent, request, context):

            if context["role"] == "lead":
                seen["count"] = len(
                    context[
                        "specialist_findings"
                    ]
                )
                return "done"

            return agent

        engine.collaborate(
            "Build a startup business plan",
            runner,
        )

        self.assertLessEqual(
            seen["count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
