from __future__ import annotations

import ast
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(r"C:\Jarvis")

SERVER = (
    ROOT
    / "workstation"
    / "jarvis_os_v3.py"
)

APP = (
    ROOT
    / "workstation"
    / "jarvis_os_v3_assets"
    / "app.js"
)


class V32BLatencyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.server = SERVER.read_text(
            encoding="utf-8"
        )

        cls.app = APP.read_text(
            encoding="utf-8"
        )

        cls.tree = ast.parse(
            cls.server
        )


    def test_server_syntax(self):

        compile(
            self.server,
            str(SERVER),
            "exec",
        )


    def test_fast_trading_boundary_exists(self):

        names = {
            node.name
            for node in ast.walk(
                self.tree
            )
            if isinstance(
                node,
                ast.FunctionDef,
            )
        }

        self.assertIn(
            "fast_trading_command",
            names,
        )

        self.assertIn(
            "TRADING_FAST",
            self.server,
        )


    def test_fast_path_uses_governed_registry_route(self):

        dispatch = next(
            node
            for node in self.tree.body
            if isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "dispatch_command"
        )

        calls = [
            node
            for node in ast.walk(
                dispatch
            )
            if isinstance(
                node,
                ast.Call,
            )
        ]

        routed = False

        for call in calls:

            target = call.func

            if not (
                isinstance(
                    target,
                    ast.Attribute,
                )
                and isinstance(
                    target.value,
                    ast.Name,
                )
                and target.value.id
                == "main"
                and target.attr
                == "route_agent"
            ):

                continue

            if (
                len(
                    call.args
                )
                >= 2
                and isinstance(
                    call.args[0],
                    ast.Constant,
                )
                and call.args[0].value
                == "trading"
            ):

                routed = True

                break

        self.assertTrue(
            routed,
            "Fast technical analysis must still cross AgentRegistry through main.route_agent().",
        )


    def test_fast_path_precedes_master_bridge(self):

        fast = self.server.find(
            "if fast_trading_command("
        )

        master = self.server.find(
            'getattr(\n        main,\n        "jarvis_command"'
        )

        self.assertGreaterEqual(
            fast,
            0,
        )

        self.assertGreater(
            master,
            fast,
        )


    def test_natural_chart_phrasing_is_normalized(self):

        for phrase in (
            '"look on"',
            '"looks on"',
            '"look at"',
            '"how does"',
            '"tell me"',
        ):

            self.assertIn(
                phrase,
                self.server,
            )


    def test_server_duplicate_suppression(self):

        self.assertIn(
            "COMMAND_INFLIGHT",
            self.server,
        )

        self.assertIn(
            "DUPLICATE_SUPPRESSED",
            self.server,
        )

        self.assertIn(
            "COMMAND_CACHE_SECONDS",
            self.server,
        )

        self.assertIn(
            "cached_command_result",
            self.server,
        )


    def test_browser_busy_boundary(self):

        self.assertIn(
            "let commandInFlight",
            self.app,
        )

        self.assertIn(
            "commandInFlightText",
            self.app,
        )

        self.assertIn(
            "I'm finishing the current request first.",
            self.app,
        )

        self.assertIn(
            "JARVIS voice command deferred while busy:",
            self.app,
        )


    def test_browser_command_state_released_in_finally(self):

        execute_start = self.app.find(
            "async function executeCommand("
        )

        execute_end = self.app.find(
            "function bindCommandButtons(",
            execute_start,
        )

        section = self.app[
            execute_start:
            execute_end
        ]

        self.assertIn(
            "} finally {",
            section,
        )

        self.assertRegex(
            section,
            re.compile(
                r"finally\s*\{[\s\S]*?"
                r"commandInFlight\s*=\s*false",
            ),
        )


    def test_javascript_syntax_when_node_available(self):

        node = shutil.which(
            "node"
        )

        if not node:

            self.skipTest(
                "Node.js unavailable."
            )

        result = subprocess.run(
            [
                node,
                "--check",
                str(APP),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stderr,
        )


    def test_no_live_order_code_added_to_ui(self):

        start = self.app.find(
            "JARVIS_V32_HYBRID_VOICE"
        )

        section = self.app[
            start:
        ]

        for token in (
            "place_order(",
            "modify_order(",
            "cancel_order(",
        ):

            self.assertNotIn(
                token,
                section,
            )


if __name__ == "__main__":
    unittest.main()
