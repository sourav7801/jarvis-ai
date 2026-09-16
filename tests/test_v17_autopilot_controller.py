from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation import v17_autopilot_preferences as preferences
from workstation.v17_autonomous_options import V17AutonomousOptionsRuntime
from workstation.v17_terminal_http import _autopilot_control, _normalize_capital_fraction


class FakeBridge:
    def __init__(self):
        self.calls = []

    def open_plan(self, plan, **kwargs):
        self.calls.append((dict(plan), dict(kwargs)))
        return {"success": True, "bucket_allocation_fraction": kwargs.get("bucket_allocation_fraction")}

    def status(self, workspace):
        return {"success": True, "workspace": workspace}


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def control(self, workspace, action):
        self.calls.append((workspace, action))
        return {"success": True, "state": "STARTING" if action == "start" else "PAUSED"}


class V17AutopilotControllerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "prefs.json"
        self.path_patch = patch.object(preferences, "PREFERENCES_PATH", self.path)
        self.path_patch.start()
        preferences.save_preferences({"options_capital_fraction": 0.50})

    def tearDown(self):
        self.path_patch.stop()
        self.tempdir.cleanup()

    def test_percent_normalization_accepts_fraction_percent_and_number(self):
        self.assertEqual(_normalize_capital_fraction(0.5), 0.5)
        self.assertEqual(_normalize_capital_fraction(50), 0.5)
        self.assertEqual(_normalize_capital_fraction("50%"), 0.5)
        with self.assertRaises(ValueError):
            _normalize_capital_fraction(2)
        with self.assertRaises(ValueError):
            _normalize_capital_fraction(101)

    def test_one_touch_start_persists_fraction_and_starts_enabled_workspaces(self):
        runtime = FakeRuntime()
        result = _autopilot_control(runtime, {"action": "start", "options_capital_percent": 50})
        self.assertTrue(result["success"])
        self.assertEqual(result["options_capital_fraction"], 0.5)
        self.assertEqual(runtime.calls, [("INTRADAY", "start"), ("SWING", "start"), ("INVESTMENT", "start")])
        self.assertFalse(result["daily_rebalance"])
        self.assertFalse(result["cross_workspace_top_up"])
        self.assertFalse(result["production_code_rewrite"])

    def test_one_touch_stop_pauses_all_entry_sessions(self):
        runtime = FakeRuntime()
        preferences.save_preferences({"start_workspaces": ["INTRADAY"]})
        result = _autopilot_control(runtime, {"action": "stop"})
        self.assertTrue(result["success"])
        self.assertEqual(runtime.calls, [("INTRADAY", "pause"), ("SWING", "pause"), ("INVESTMENT", "pause")])

    def test_v17_option_bridge_overrides_caller_fraction_with_durable_mandate(self):
        preferences.save_preferences({"options_capital_fraction": 0.65})
        bridge = FakeBridge()
        service = V17AutonomousOptionsRuntime(runtime=object(), v16_bridge=bridge)
        result = service.open_plan({"underlying": "NIFTY"}, bucket_allocation_fraction=0.10, portfolio_bucket="INTRADAY")
        self.assertTrue(result["success"])
        self.assertEqual(bridge.calls[-1][1]["bucket_allocation_fraction"], 0.65)
        self.assertEqual(result["options_capital_fraction"], 0.65)
        self.assertFalse(result["daily_rebalance"])
        self.assertFalse(result["cross_workspace_top_up"])

    def test_v17_single_option_controller_disables_legacy_chain_owner(self):
        project_root = Path(__file__).resolve().parents[1]
        workspace_js = (project_root / "workstation" / "quant_terminal_v2_static" / "v16_workspace.js").read_text(encoding="utf-8")
        terminal_http = (project_root / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")

        self.assertIn("window.JARVIS_V17_SINGLE_OPTION_CONTROLLER=true", terminal_http)
        self.assertIn(
            "const SINGLE_OPTION_CONTROLLER = window.JARVIS_V17_SINGLE_OPTION_CONTROLLER === true;",
            workspace_js,
        )
        self.assertIn("if (SINGLE_OPTION_CONTROLLER) return;", workspace_js)
        self.assertIn(
            'if (SINGLE_OPTION_CONTROLLER || currentMode() !== "OPTIONS") return;',
            workspace_js,
        )
        self.assertIn(
            'if (mode === "OPTIONS" && !SINGLE_OPTION_CONTROLLER)',
            workspace_js,
        )


if __name__ == "__main__":
    unittest.main()
