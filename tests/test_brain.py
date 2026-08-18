import unittest
from omni.brain import JarvisBrain


class JarvisBrainTests(unittest.TestCase):

    def setUp(self):
        self.brain = JarvisBrain()

    def test_agent_count(self):
        self.assertEqual(self.brain.agent_count, 29)

    def test_trading(self):
        d = self.brain.decide("Analyze NIFTY for a paper trade")
        self.assertEqual(d.primary_agent, "trading")

    def test_web(self):
        d = self.brain.decide("Search the internet for latest AI news")
        self.assertEqual(d.primary_agent, "web_intelligence")

    def test_code(self):
        d = self.brain.decide("Debug this Python program")
        self.assertEqual(d.primary_agent, "coding")

    def test_company(self):
        d = self.brain.decide("Create a business plan for my startup")
        self.assertEqual(d.primary_agent, "strategy")
        self.assertIn("finance", d.supporting_agents)

    def test_chat(self):
        d = self.brain.decide("Hello Jarvis")
        self.assertEqual(d.primary_agent, "chat")

    def test_capabilities(self):
        d = self.brain.decide("Analyze the market")
        self.assertIn("market.read", d.capabilities)


if __name__ == "__main__":
    unittest.main()
