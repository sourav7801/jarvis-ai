import sys
import tempfile
import unittest
from pathlib import Path

from omni.approval import ApprovalService
from omni.audit import AuditStore
from omni.sandbox import SandboxPolicy, SubprocessSandbox
from tools.capabilities import validate_capability_manifest
from tools.registry import list_tools
from tools.safety import authorize_tool, verify_tool_postcondition


class CapabilityTests(unittest.TestCase):
    def test_every_registered_tool_has_capabilities(self):
        self.assertEqual(validate_capability_manifest(list_tools()), [])

    def test_high_risk_requires_all_capabilities(self):
        denied = authorize_tool("admin", "HIGH", {"system.admin"}, set())
        allowed = authorize_tool(
            "admin", "HIGH", {"system.admin"}, {"system.admin"}
        )
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)


class ApprovalTests(unittest.TestCase):
    def test_approval_is_scoped_and_single_use(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AuditStore(Path(directory) / "audit.sqlite3")
            service = ApprovalService(store)
            grant = service.issue("delete_file", "filesystem.delete")

            self.assertFalse(
                service.consume(grant.token, "other_action", "filesystem.delete")
            )
            self.assertTrue(
                service.consume(grant.token, "delete_file", "filesystem.delete")
            )
            self.assertFalse(
                service.consume(grant.token, "delete_file", "filesystem.delete")
            )


class PostconditionTests(unittest.TestCase):
    def test_tool_identity_mismatch_fails(self):
        result = verify_tool_postcondition(
            "current_time",
            {},
            {"success": True, "tool": "other", "message": "ok"},
        )
        self.assertFalse(result["verified"])


class SandboxTests(unittest.TestCase):
    def test_denies_unlisted_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = SubprocessSandbox(
                SandboxPolicy(frozenset(), (Path(directory),))
            )
            with self.assertRaises(PermissionError):
                sandbox.run([sys.executable, "-c", "print('no')"], directory)

    def test_runs_allowlisted_executable_in_allowed_root(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(sys.executable).name
            sandbox = SubprocessSandbox(
                SandboxPolicy(frozenset({executable}), (Path(directory),))
            )
            result = sandbox.run(
                [sys.executable, "-c", "print('sandbox-ok')"], directory
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "sandbox-ok")


if __name__ == "__main__":
    unittest.main()

