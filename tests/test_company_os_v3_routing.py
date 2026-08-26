from __future__ import annotations

import unittest
from unittest.mock import patch

from workstation.jarvis_os_v3 import dispatch_command


class CompanyOSV3RoutingTests(unittest.TestCase):
    @patch("omni.company_os.COMPANY_OS.snapshot", return_value={"autonomy": "SUPERVISED"})
    @patch("omni.company_os.COMPANY_OS.create_plan")
    @patch("workstation.jarvis_os_v3.conversation_turns.remember")
    def test_idea_build_command_routes_to_durable_company_os(self, _remember, create_plan, _snapshot):
        create_plan.return_value = {
            "company_name": "Movable Habitat Labs",
            "artifacts": [{"name": "brief"}],
            "tasks": [{"id": "T01"}],
            "research_program": {
                "research_tracks": [{"id": "R01"}],
                "horizons": [{"horizon": "YEAR 1"}, {"horizon": "YEAR 4"}, {"horizon": "YEAR 5"}],
            },
        }
        result = dispatch_command(
            "Jarvis, I have an idea for movable modular homes; start building the company"
        )
        self.assertEqual(result["route"], "COMPANY_OS")
        self.assertEqual(result["raw"]["action"], "open_company")
        self.assertFalse(result["raw"]["live_execution"])
        create_plan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
