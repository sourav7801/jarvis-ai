import unittest
from unittest.mock import patch

import main
from agents.head_agent import detect_department
from tools.safety import authorize_tool, verify_tool_result
from tools.tool_schema import validate_tool_call


class RoutingTests(unittest.TestCase):
    def test_trading_department_is_reachable(self):
        self.assertEqual(detect_department("analyze NIFTY stock"), "trading")
        self.assertIn("trading", main.AGENT_MAP)
        self.assertEqual(
            main.AGENT_MAP["trading"][:2],
            ("agents.trading_agent", "trading"),
        )

    def test_company_specialist_departments_are_reachable(self):
        self.assertEqual(detect_department("create a marketing plan"), "marketing")
        self.assertEqual(detect_department("prepare a threat model"), "security")
        self.assertEqual(detect_department("model our unit economics"), "finance")

    def test_operator_and_web_intelligence_agents_are_reachable(self):
        self.assertEqual(detect_department("search the web for safe AI"), "web_intelligence")
        self.assertEqual(detect_department("read https://example.com/report"), "web_intelligence")
        self.assertIn("operator", main.AGENT_MAP)
        self.assertIn("web_intelligence", main.AGENT_MAP)

    def test_data_request_precedence(self):
        self.assertTrue(main.looks_like_data_request("analyze sales.xlsx"))

    def test_deterministic_command_precedes_chat_fallback(self):
        with (
            patch.object(main, "audit_event"),
            patch.object(main, "cancel_speech"),
            patch.object(main, "route_agent") as route_agent,
            patch.object(main, "execute_tool", return_value="time") as execute_tool,
        ):
            result = main.process_command("what time is it")

        route_agent.assert_not_called()
        execute_tool.assert_called_once()
        self.assertEqual(result["message"], "time")

    def test_universal_operator_routes_to_governed_mission(self):
        mission = {
            "selected_agents": ["operator", "strategy", "quality"],
            "artifacts": [{"name": "packet"}],
        }
        with (
            patch.object(main, "audit_event"),
            patch.object(main, "cancel_speech"),
            patch.object(main, "is_operator_request", return_value=True),
            patch.object(main.MISSION_CONTROL, "create_mission", return_value=mission) as create,
        ):
            result = main.process_command("Handle this end-to-end")
        self.assertEqual(result["action"], "open_mission")
        self.assertEqual(result["source"], "universal_operator")
        self.assertIn("approval-locked", result["message"])
        create.assert_called_once()


class SafetyTests(unittest.TestCase):
    def test_low_risk_is_allowed(self):
        self.assertTrue(authorize_tool("current_time", "LOW").allowed)

    def test_high_and_unknown_risk_fail_closed(self):
        self.assertFalse(authorize_tool("dangerous", "HIGH").allowed)
        self.assertFalse(authorize_tool("unclassified", "UNKNOWN").allowed)

    def test_failed_tool_result_is_not_verified(self):
        result = verify_tool_result({"success": False, "message": "failed"})
        self.assertFalse(result["verified"])

    def test_schema_rejects_unexpected_arguments(self):
        result = validate_tool_call("current_time", {"unexpected": True})
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
