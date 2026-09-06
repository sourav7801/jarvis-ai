from __future__ import annotations

import subprocess
import sys
import unittest
from unittest.mock import patch

from omni import workspace_command_center as center


class WorkspaceCommandCenterHealthTests(unittest.TestCase):
    def test_imports_in_a_fresh_interpreter(self):
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-c",
                (
                    "from omni.workspace_command_center import snapshot; "
                    "value=snapshot(); assert value['workspace_count'] >= 12"
                ),
            ],
            cwd=str(center.ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_workspace_uses_health_contract_not_port_only(self):
        with patch.object(
            center,
            "_fetch_health_payload",
            return_value={
                "status": "DEGRADED",
                "last_error": "FYERS session expired",
                "paper_only": True,
                "live_execution": False,
            },
        ):
            quant = center.get_workspace("quant")

        self.assertEqual(quant["status"], "DEGRADED")
        self.assertIn("FYERS session expired", quant["activity"])
        self.assertTrue(quant["health"]["paper_only"])
        self.assertFalse(quant["health"]["live_execution"])

    def test_snapshot_aggregates_real_endpoint_health(self):
        def health(port: int, _path: str):
            if port == 8787:
                return {"status": "READY", "paper_only": True, "live_execution": False}
            if port == 8790:
                return {"status": "DEGRADED", "paper_only": True, "live_execution": False}
            return None

        with patch.object(center, "_fetch_health_payload", side_effect=health), patch.object(
            center, "_port_open", return_value=True
        ):
            payload = center.snapshot()

        self.assertEqual(payload["health_source"], "LOOPBACK_SERVICE_HEALTH_ENDPOINTS")
        self.assertEqual(payload["health_contract"]["services"]["quant"], "READY")
        self.assertEqual(payload["health_contract"]["services"]["fyers"], "DEGRADED")
        self.assertEqual(payload["health_contract"]["overall"], "DEGRADED")


if __name__ == "__main__":
    unittest.main()
