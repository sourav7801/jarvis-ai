import unittest

import main


class BrainMainIntegrationTests(unittest.TestCase):

    def test_web_fallback_upgrades(self):
        self.assertEqual(
            main._brain_route_override(
                "chat",
                "Search the internet for latest AI news",
            ),
            "web_intelligence",
        )

    def test_trading_fallback_upgrades(self):
        self.assertEqual(
            main._brain_route_override(
                "chat",
                "Analyze NIFTY market",
            ),
            "trading",
        )

    def test_code_fallback_upgrades(self):
        self.assertEqual(
            main._brain_route_override(
                "chat",
                "Debug this Python program",
            ),
            "coding",
        )

    def test_existing_specialist_is_preserved(self):
        self.assertEqual(
            main._brain_route_override(
                "research",
                "Analyze NIFTY",
            ),
            "research",
        )

    def test_structured_tool_is_preserved(self):
        action = {
            "action": "tool",
            "tool": "current_time",
            "arguments": {},
        }

        self.assertIs(
            main._brain_route_override(
                action,
                "What time is it?",
            ),
            action,
        )

    def test_time_fallback_stays_chat(self):
        self.assertEqual(
            main._brain_route_override(
                "chat",
                "What time is it?",
            ),
            "chat",
        )


if __name__ == "__main__":
    unittest.main()
