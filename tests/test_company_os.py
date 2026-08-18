import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omni.company_os import CompanyOperatingSystem, DEPARTMENT_AGENTS


class CompanyOperatingSystemTests(unittest.TestCase):
    def test_company_blueprint_is_durable_and_approval_gated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "company.json"
            operating_system = CompanyOperatingSystem(path)
            with patch("omni.company_os.audit_event"):
                plan = operating_system.create_plan(
                    "A privacy-first service that helps small retailers forecast inventory."
                )
            self.assertEqual(plan["status"], "BLUEPRINT_READY")
            self.assertEqual(len(plan["tasks"]), 18)
            external = [task for task in plan["tasks"] if task["approval_required"]]
            self.assertGreaterEqual(len(external), 4)
            self.assertTrue(all(task["status"] == "AWAITING_APPROVAL" for task in external))
            self.assertEqual(len(plan["artifacts"]), 5)
            self.assertTrue(all(Path(item["path"]).is_file() for item in plan["artifacts"]))
            restored = CompanyOperatingSystem(path).snapshot()
            self.assertEqual(restored["latest_plan"]["id"], plan["id"])

    def test_specialists_are_bounded_and_cover_company_functions(self):
        departments = {agent.department for agent in DEPARTMENT_AGENTS}
        self.assertGreaterEqual(len(DEPARTMENT_AGENTS), 16)
        self.assertIn("Engineering", departments)
        self.assertIn("Legal and Compliance", departments)
        self.assertIn("Market Intelligence", departments)
        self.assertTrue(all(agent.prohibited_actions for agent in DEPARTMENT_AGENTS))

    def test_short_idea_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            operating_system = CompanyOperatingSystem(Path(directory) / "state.json")
            with self.assertRaises(ValueError):
                operating_system.create_plan("an app")

    def test_voice_command_prefix_is_removed_from_venture(self):
        with tempfile.TemporaryDirectory() as directory:
            operating_system = CompanyOperatingSystem(Path(directory) / "state.json")
            with patch("omni.company_os.audit_event"):
                plan = operating_system.create_plan(
                    "Jarvis, I have an idea for a privacy-first inventory service for retailers"
                )
            self.assertTrue(plan["idea"].startswith("a privacy-first"))
            self.assertNotIn("Jarvis", plan["company_name"])


if __name__ == "__main__":
    unittest.main()
