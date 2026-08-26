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
            self.assertGreaterEqual(len(plan["artifacts"]), 13)
            self.assertTrue(all(Path(item["path"]).is_file() for item in plan["artifacts"]))
            self.assertTrue(
                any(item["name"] == "website/index.html" for item in plan["artifacts"])
            )
            self.assertIn(
                "APPROVAL",
                plan["autopilot"]["publishing"],
            )
            self.assertEqual(len(plan["external_actions"]), 4)
            self.assertTrue(
                all(item["status"] == "DRAFT_REVIEW_REQUIRED" for item in plan["external_actions"])
            )
            self.assertTrue(all(not item["executed"] for item in plan["external_actions"]))
            self.assertIn("next_due_at", plan["opportunity_radar_schedule"])
            self.assertTrue(
                any(item["name"] == "15-executive-status-report.md" for item in plan["artifacts"])
            )
            self.assertIn("research_program", plan)
            self.assertEqual(plan["research_program"]["truth_policy"], "HYPOTHESES_ARE_NOT_FACTS")
            self.assertTrue(
                any(item["name"] == "10-long-horizon-roadmap.md" for item in plan["artifacts"])
            )
            self.assertTrue(
                any(item["name"] == "11-department-workboard.json" for item in plan["artifacts"])
            )
            restored = CompanyOperatingSystem(path).snapshot()
            self.assertEqual(restored["latest_plan"]["id"], plan["id"])
            self.assertEqual(restored["external_action_queue"]["counts"]["DRAFT_REVIEW_REQUIRED"], 4)
            self.assertFalse(restored["external_action_queue"]["external_actions_executed"])

    def test_background_research_updates_citable_evidence_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            operating_system = CompanyOperatingSystem(Path(directory) / "state.json")
            with patch("omni.company_os.audit_event"):
                plan = operating_system.create_plan(
                    "A privacy-first service that helps small retailers forecast inventory."
                )
            research = {
                "query": "inventory forecasting competitors",
                "sources": [
                    {
                        "title": "Retail inventory study",
                        "url": "https://example.com/study",
                        "excerpt": "Small retailers report forecasting constraints.",
                        "provider": "PUBLIC_WEB",
                        "read_status": "EXTRACTED",
                    }
                ],
                "notice": "Public evidence requires review.",
            }
            with patch(
                "agents.web_intelligence_agent.web_intelligence",
                return_value=research,
            ), patch("omni.company_os.audit_event"):
                operating_system._research_worker(plan)

            latest = operating_system.snapshot()["latest_plan"]
            self.assertEqual(
                latest["autopilot"]["research"],
                "EVIDENCE_READY_FOR_REVIEW",
            )
            self.assertIn("APPROVAL", latest["autopilot"]["publishing"])
            evidence = (
                operating_system.projects_root
                / plan["id"]
                / "05-market-research-evidence.md"
            ).read_text(encoding="utf-8")
            self.assertIn("https://example.com/study", evidence)

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

    def test_department_worker_persists_real_local_briefs_without_external_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            operating_system = CompanyOperatingSystem(Path(directory) / "state.json")
            with patch("omni.company_os.audit_event"):
                plan = operating_system.create_plan(
                    "A movable modular home platform with safe physical prototypes."
                )

            def execute(agent: str, _text: str, _correlation_id: str):
                return {
                    "success": True,
                    "message": f"{agent} local brief ready",
                    "data": {"approval_gate": "LOCKED"},
                    "error_type": None,
                }

            with patch.object(operating_system, "_registry_executor", side_effect=execute), patch(
                "omni.company_os.audit_event"
            ):
                operating_system._department_worker(plan)

            latest = operating_system.snapshot()["latest_plan"]
            packet = latest["department_run"]
            self.assertEqual(packet["successful_departments"], len(DEPARTMENT_AGENTS))
            self.assertFalse(packet["external_actions_executed"])
            self.assertFalse(packet["live_execution"])
            self.assertEqual(
                latest["autopilot"]["department_workboard"],
                "LOCAL_DEPARTMENT_PACKET_READY",
            )
            self.assertTrue(
                any(item["name"] == "13-department-specialist-packet.json" for item in latest["artifacts"])
            )
            locked = [task for task in latest["tasks"] if task["approval_required"]]
            self.assertTrue(all(task["status"] == "AWAITING_APPROVAL" for task in locked))


if __name__ == "__main__":
    unittest.main()
