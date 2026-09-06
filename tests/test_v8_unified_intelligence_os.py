from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from omni.agent_registry import default_agent_specs
from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
from omni.unified_intent_router import route_intent, workspace_actions
from scripts import jarvis_runtime_supervisor_v8 as runtime_v8
from workstation import jarvis_os_v3 as v3
from workstation.jarvis_os_v8 import create_server


ROOT = Path(__file__).resolve().parents[1]


class V8UnifiedIntentTests(unittest.TestCase):
    def test_open_apps_workspace_is_deterministic(self):
        decision = route_intent("open apps workspace")
        self.assertEqual(decision.kind, "WORKSPACE_CONTROL")
        self.assertEqual(decision.route, "WORKSPACE_CONTROL")
        self.assertTrue(decision.deterministic)
        self.assertIn(
            {"type": "open_window", "window": "apps"},
            list(decision.workspace_actions),
        )
        self.assertIn("Computer & Apps", decision.response)
        self.assertNotIn("couldn't understand", decision.response.lower())

    def test_master_prefix_preserves_workspace_control(self):
        decision = route_intent("Jarvis, open apps workspace")
        self.assertTrue(decision.deterministic)
        self.assertEqual(decision.kind, "WORKSPACE_CONTROL")

    def test_research_workspace_navigation_is_deterministic(self):
        decision = route_intent("open research workspace")
        self.assertTrue(decision.deterministic)
        self.assertEqual(decision.kind, "WORKSPACE_CONTROL")
        self.assertTrue(
            any(
                action.get("type") == "open_window" and action.get("window") == "research"
                for action in decision.workspace_actions
            )
        )

    def test_dedicated_completion_and_memory_workspaces_are_loopback(self):
        completion = route_intent("open completion center")
        memory = route_intent("open memory fabric")
        self.assertTrue(completion.deterministic)
        self.assertTrue(memory.deterministic)
        self.assertEqual(completion.workspace_actions[0]["type"], "open_url")
        self.assertEqual(completion.workspace_actions[0]["url"], "http://127.0.0.1:8799/")
        self.assertIn("section=memory", memory.workspace_actions[0]["url"])
        self.assertTrue(completion.workspace_actions[0]["loopback_only"])

    def test_compound_open_and_analyze_still_reaches_domain_router(self):
        decision = route_intent("open NIFTY 15m chart and analyze it")
        self.assertFalse(decision.deterministic)
        self.assertEqual(decision.kind, "MARKETS")
        self.assertTrue(any(item.get("type") == "chart_symbol" for item in decision.workspace_actions))

    def test_workspace_action_deduplication(self):
        actions = workspace_actions("open apps workspace")
        keys = [repr(sorted(item.items())) for item in actions]
        self.assertEqual(len(keys), len(set(keys)))


class V8MasterCommandHttpTests(unittest.TestCase):
    def test_open_apps_workspace_returns_success_without_broad_dispatch(self):
        server = create_server("127.0.0.1", 0)
        port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = json.dumps({"text": "open apps workspace", "input_mode": "typed"}).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/command",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Jarvis-Token": v3.TOKEN,
                },
            )
            with patch("workstation.jarvis_os_v3.dispatch_command") as broad_dispatch:
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                broad_dispatch.assert_not_called()
            self.assertEqual(payload["route"], "WORKSPACE_CONTROL")
            self.assertIn("Computer & Apps", payload["response"])
            self.assertIn(
                {"type": "open_window", "window": "apps"},
                payload["workspace_actions"],
            )
            self.assertNotIn("couldn't understand", payload["response"].lower())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


class V8ExecutiveControlTests(unittest.TestCase):
    def test_executive_plan_is_bounded_and_safe(self):
        with patch("omni.executive_control_plane.context_snapshot", return_value={"success": True}):
            plan = EXECUTIVE_CONTROL_PLANE.plan("open apps workspace")
        self.assertEqual(plan["domain"], "OPERATING_SYSTEM")
        self.assertEqual(plan["mode"], "DETERMINISTIC")
        self.assertEqual(plan["steps"][0]["capability"], "workspace.control")
        self.assertIs(plan["safety"]["paper_only"], True)
        self.assertIs(plan["safety"]["live_execution"], False)
        self.assertIs(plan["safety"]["automatic_broker_order"], False)

    def test_market_plan_has_data_reasoning_risk_and_verification(self):
        with patch("omni.executive_control_plane.context_snapshot", return_value={"success": True}):
            plan = EXECUTIVE_CONTROL_PLANE.plan("analyze BTC 15m and find the strongest paper setup")
        phases = {row["phase"] for row in plan["steps"]}
        self.assertTrue({"PERCEPTION", "CONTEXT", "REASON", "RISK", "VERIFY"} <= phases)
        self.assertEqual(plan["domain"], "MARKETS")

    def test_executive_agent_is_registered(self):
        specs = {spec.name: spec for spec in default_agent_specs()}
        self.assertIn("executive", specs)
        self.assertIn("workspace.control", specs["executive"].capabilities)
        self.assertIn("goal.plan", specs["executive"].capabilities)


class V8RuntimeContractTests(unittest.TestCase):
    def test_v8_master_surface_requires_home_and_runtime_markers(self):
        def fake_http(url: str, timeout: float = 1.5):
            if url.endswith("/v8_runtime.js"):
                return 200, b"function executeWorkspaceActionsV8(){}"
            return 200, b"JARVIS OMNI OPERATING COMMAND CENTER V8 UNIFIED INTELLIGENCE"

        with patch.object(runtime_v8, "_http", side_effect=fake_http):
            state = runtime_v8.master_v8_surface_status()
        self.assertTrue(state["current"])

    def test_v8_master_surface_rejects_old_master(self):
        with patch.object(runtime_v8, "_http", return_value=(200, b"JARVIS V7")):
            state = runtime_v8.master_v8_surface_status()
        self.assertFalse(state["current"])

    def test_launcher_and_startup_use_v8_runtime(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        startup = (ROOT / "start_jarvis_v3.py").read_text(encoding="utf-8")
        self.assertIn("scripts.jarvis_runtime_supervisor_v8", launcher)
        self.assertIn("workstation.jarvis_os_v8", startup)
        self.assertNotIn("place_order(", launcher)

    def test_master_v8_source_has_deterministic_workspace_short_circuit(self):
        source = (ROOT / "workstation" / "jarvis_os_v8.py").read_text(encoding="utf-8")
        self.assertIn('intent.get("kind") == "WORKSPACE_CONTROL"', source)
        self.assertIn("conversation_turns.remember", source)
        self.assertIn('"workspace_actions": actions', source)

    def test_browser_runtime_allows_only_loopback_workspace_urls(self):
        source = (ROOT / "workstation" / "jarvis_os_v8_assets" / "runtime.js").read_text(encoding="utf-8")
        self.assertIn('new Set(["127.0.0.1", "localhost"])', source)
        self.assertIn('action.type === "open_url"', source)
        self.assertIn("safeWorkspaceUrl", source)

    def test_completion_center_exposes_executive_api(self):
        source = (ROOT / "workstation" / "completion_console.py").read_text(encoding="utf-8")
        html = (ROOT / "workstation" / "completion_console_static" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "workstation" / "completion_console_static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('path == "/api/executive"', source)
        self.assertIn('data-section="executive"', html)
        self.assertIn("planExecutive", app)

    def test_new_v8_modules_have_no_live_order_api(self):
        files = (
            "omni/unified_intent_router.py",
            "omni/context_fabric.py",
            "omni/executive_control_plane.py",
            "workstation/jarvis_os_v8.py",
            "scripts/jarvis_runtime_supervisor_v8.py",
        )
        forbidden = ("place_order(", "modify_order(", "cancel_order(", "submit_order(")
        for relative in files:
            source = (ROOT / relative).read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, source, msg=f"{token} present in {relative}")


if __name__ == "__main__":
    unittest.main()
