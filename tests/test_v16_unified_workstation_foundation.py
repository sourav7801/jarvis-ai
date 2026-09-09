from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

from omni.agent_registry import default_agent_specs
from omni.v16_artifact_service import ArtifactServiceV16
from omni.v16_capability_registry import install_v16_capabilities
from omni.v16_file_service import ManagedFileServiceV16
from omni.v16_tool_contract import ToolRegistryV16, ToolRisk, ToolSpec
from omni.v16_workspace_service import WorkspaceServiceV16


ROOT = Path(__file__).resolve().parents[1]


class V16ToolContractTests(unittest.TestCase):
    def test_namespaced_contract_and_approval_gate(self):
        registry = ToolRegistryV16()
        called = []
        spec = ToolSpec(
            name="email.send",
            capability="communication.send",
            description="Consequential test action",
            risk=ToolRisk.CONSEQUENTIAL,
            idempotent=False,
        )
        registry.register(spec, lambda recipient: called.append(recipient) or {"sent": True})
        blocked = registry.execute("email.send", {"recipient": "test@example.com"})
        self.assertFalse(blocked.success)
        self.assertTrue(blocked.approval_required)
        self.assertEqual(called, [])
        allowed = registry.execute("email.send", {"recipient": "test@example.com"}, approval_granted=True)
        self.assertTrue(allowed.success)
        self.assertEqual(called, ["test@example.com"])

    def test_live_broker_capability_cannot_be_registered(self):
        with self.assertRaises(ValueError):
            ToolSpec(
                name="broker.place",
                capability="broker.place_order",
                description="forbidden",
                risk=ToolRisk.CONSEQUENTIAL,
            )

    def test_foundation_capability_inventory(self):
        registry = ToolRegistryV16()
        payload = install_v16_capabilities(registry)
        names = {item["name"] for item in payload["registry"]["tools"]}
        for expected in (
            "file.upload",
            "file.list",
            "file.search",
            "file.read_text",
            "artifact.create",
            "workspace.create_project",
            "workspace.list",
            "workspace.attach_file",
            "web.fetch_public",
        ):
            self.assertIn(expected, names)
        self.assertFalse(payload["live_execution"])
        self.assertFalse(payload["automatic_broker_order"])


class V16FileServiceTests(unittest.TestCase):
    def test_upload_hash_search_duplicate_and_workspace_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ManagedFileServiceV16(Path(directory) / "files", max_bytes=4096)
            first = service.ingest_bytes("notes.md", b"alpha market research", workspace="WORK")
            self.assertTrue(first["success"])
            self.assertFalse(first["duplicate"])
            record = first["file"]
            self.assertEqual(len(record["sha256"]), 64)
            self.assertEqual(record["workspace"], "WORK")
            second = service.ingest_bytes("notes.md", b"alpha market research", workspace="WORK")
            self.assertTrue(second["duplicate"])
            self.assertEqual(second["file"]["file_id"], record["file_id"])
            service.ingest_bytes("notes.md", b"alpha market research", workspace="TRADING")
            work = service.search("market", workspace="WORK")
            trading = service.search("market", workspace="TRADING")
            self.assertEqual(work["count"], 1)
            self.assertEqual(trading["count"], 1)
            text = service.extracted_text(record["file_id"])
            self.assertIn("alpha market research", text["text"])

    def test_path_traversal_and_unsupported_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ManagedFileServiceV16(Path(directory) / "files")
            with self.assertRaises(ValueError):
                service.ingest_bytes("../secret.txt", b"no")
            with self.assertRaises(ValueError):
                service.ingest_bytes("payload.exe", b"no")

    def test_upload_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ManagedFileServiceV16(Path(directory) / "files", max_bytes=10)
            with self.assertRaises(ValueError):
                service.ingest_bytes("large.txt", b"01234567890")


class V16WorkspaceTests(unittest.TestCase):
    def test_canonical_workspaces_project_file_and_mission_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            service = WorkspaceServiceV16(Path(directory) / "workspace")
            listed = service.list()
            ids = {row["workspace_id"] for row in listed["workspaces"]}
            self.assertTrue({"HOME", "WORK", "TRADING", "COMPANY", "AUTOMATION"}.issubset(ids))
            project = service.create_project("All Machine Care", parent_kind="WORK")
            project_id = project["workspace"]["workspace_id"]
            attached = service.attach_file(project_id, "file-123")
            self.assertIn("file-123", attached["workspace"]["file_ids"])
            attached = service.attach_mission(project_id, "mission-456")
            self.assertIn("mission-456", attached["workspace"]["mission_ids"])
            activity = service.recent_activity(project_id)
            self.assertGreaterEqual(activity["count"], 2)


class V16ArtifactTests(unittest.TestCase):
    def test_text_artifact_is_reopened_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ArtifactServiceV16(Path(directory) / "artifacts")
            result = service.create(
                "md",
                "research.md",
                "# Research\nVerified artifact.",
                workspace="WORK",
                register_file=False,
            )
            self.assertTrue(result["success"])
            self.assertTrue(result["verification"]["verified"])
            self.assertTrue(Path(result["path"]).is_file())

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl unavailable")
    def test_xlsx_artifact_supports_multiple_sheets_and_reopen_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ArtifactServiceV16(Path(directory) / "artifacts")
            result = service.create(
                "xlsx",
                "analysis.xlsx",
                {
                    "sheets": [
                        {
                            "name": "Dashboard",
                            "rows": [["Metric", "Value"], ["Revenue", 100], ["Margin", "=B2/2"]],
                            "header_row": 1,
                            "freeze_panes": "A2",
                            "auto_filter": True,
                        },
                        {"name": "Data", "rows": [["Date", "Sales"], ["2026-09-09", 100]]},
                    ]
                },
                workspace="WORK",
                register_file=False,
            )
            self.assertTrue(result["verification"]["verified"])
            self.assertEqual(result["verification"]["sheet_count"], 2)
            self.assertEqual(result["verification"]["sheets"], ["Dashboard", "Data"])


class V16SafetyBoundaryTests(unittest.TestCase):
    def test_permanent_agents_remain_29_including_critic(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)

    def test_v16_foundation_has_no_live_broker_calls(self):
        paths = (
            "omni/v16_tool_contract.py",
            "omni/v16_file_service.py",
            "omni/v16_artifact_service.py",
            "omni/v16_workspace_service.py",
            "omni/v16_capability_registry.py",
        )
        text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, text)
        self.assertIn("live_execution", text)
        self.assertIn("automatic_broker_order", text)


if __name__ == "__main__":
    unittest.main()
