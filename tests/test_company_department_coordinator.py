from __future__ import annotations

import unittest

from omni.company_department_coordinator import (
    ASSIGNMENTS,
    coordinate_departments,
)


class CompanyDepartmentCoordinatorTests(unittest.TestCase):
    def test_runs_every_department_and_keeps_external_actions_locked(self):
        calls: list[tuple[str, str, str]] = []

        def execute(agent: str, text: str, correlation_id: str):
            calls.append((agent, text, correlation_id))
            return {
                "success": True,
                "message": f"{agent} local brief",
                "data": {"deliverable": {"approval_gate": "LOCKED"}},
                "error_type": None,
            }

        result = coordinate_departments(
            {"id": "plan-1", "company_name": "Habitat Labs", "idea": "movable modular homes"},
            execute,
        )

        self.assertEqual(result["department_count"], len(ASSIGNMENTS))
        self.assertEqual(result["successful_departments"], len(ASSIGNMENTS))
        self.assertFalse(result["external_actions_executed"])
        self.assertFalse(result["live_execution"])
        self.assertEqual(len(calls), len(ASSIGNMENTS))
        self.assertTrue(all("Do not claim" in call[1] for call in calls))

    def test_one_department_failure_is_isolated_and_reported(self):
        def execute(agent: str, _text: str, _correlation_id: str):
            if agent == "legal":
                raise RuntimeError("legal service unavailable")
            return {"success": True, "message": "ready", "data": None, "error_type": None}

        result = coordinate_departments(
            {"id": "plan-2", "company_name": "Test Labs", "idea": "testable venture idea"},
            execute,
        )
        self.assertEqual(result["failed_departments"], 1)
        self.assertEqual(result["status"], "LOCAL_DEPARTMENT_PACKET_DEGRADED")
        legal = next(item for item in result["results"] if item["department_id"] == "legal")
        self.assertEqual(legal["status"], "FAILED_SAFE")
        self.assertEqual(legal["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
