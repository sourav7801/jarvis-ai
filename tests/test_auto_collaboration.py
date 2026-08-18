import unittest
from unittest.mock import patch

import main

from omni.auto_collaboration import (
    should_auto_collaborate,
    auto_collaboration_answer,
)


class AutoCollaborationTests(unittest.TestCase):

    def test_complex_trading_uses_team(self):

        self.assertTrue(
            should_auto_collaborate(
                "Analyze NIFTY and assess risk "
                "before giving a paper trade decision"
            )
        )

    def test_complex_company_request_uses_team(self):

        self.assertTrue(
            should_auto_collaborate(
                "Build a startup business plan and "
                "evaluate finance marketing and operations"
            )
        )

    def test_simple_chat_stays_fast(self):

        self.assertFalse(
            should_auto_collaborate(
                "Hello Jarvis"
            )
        )

    def test_time_stays_deterministic(self):

        self.assertFalse(
            should_auto_collaborate(
                "What time is it?"
            )
        )

    def test_simple_tool_stays_fast(self):

        self.assertFalse(
            should_auto_collaborate(
                "Open calculator"
            )
        )

    def test_collaboration_failure_falls_back(self):

        with patch(
            "omni.collaboration_service.collaborate",
            side_effect=RuntimeError(
                "temporary failure"
            ),
        ):
            result = auto_collaboration_answer(
                "Analyze NIFTY and assess "
                "risk and market conditions"
            )

        self.assertIsNone(result)

    def test_main_exposes_auto_collaboration(self):

        self.assertTrue(
            callable(
                main.jarvis_auto_collaboration_answer
            )
        )


if __name__ == "__main__":
    unittest.main()
