import unittest

from omni.brain import JarvisBrain, DelegationPlan


class BrainDelegationTests(unittest.TestCase):

    def setUp(self):
        self.brain = JarvisBrain()

    def test_trading_creates_multi_agent_plan(self):
        plan = self.brain.plan(
            "Analyze NIFTY and find a paper trading opportunity"
        )

        self.assertIsInstance(plan, DelegationPlan)
        self.assertEqual(plan.lead_agent, "trading")
        self.assertIn("research", plan.agents)
        self.assertIn("web_intelligence", plan.agents)

    def test_company_plan_uses_multiple_departments(self):
        plan = self.brain.plan(
            "Build a business plan for my startup"
        )

        self.assertEqual(plan.lead_agent, "strategy")
        self.assertIn("product", plan.agents)
        self.assertIn("finance", plan.agents)
        self.assertIn("marketing", plan.agents)
        self.assertIn("operations", plan.agents)

    def test_coding_plan_uses_engineering_and_security(self):
        plan = self.brain.plan(
            "Design and debug a Python application"
        )

        self.assertEqual(plan.lead_agent, "coding")
        self.assertIn("engineering", plan.agents)
        self.assertIn("security", plan.agents)

    def test_simple_chat_stays_single_agent(self):
        plan = self.brain.plan("Hello Jarvis")

        self.assertEqual(plan.lead_agent, "chat")
        self.assertEqual(plan.agent_count, 1)

    def test_no_duplicate_agents(self):
        plan = self.brain.plan(
            "Build a startup business plan"
        )

        self.assertEqual(
            len(plan.agents),
            len(set(plan.agents)),
        )

    def test_lead_agent_is_first(self):
        plan = self.brain.plan(
            "Analyze NIFTY market"
        )

        self.assertEqual(
            plan.steps[0].agent,
            plan.lead_agent,
        )

    def test_steps_expose_capabilities(self):
        plan = self.brain.plan(
            "Analyze NIFTY"
        )

        lead = plan.steps[0]

        self.assertIn(
            "market.read",
            lead.capabilities,
        )


if __name__ == "__main__":
    unittest.main()
