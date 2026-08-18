import tempfile
import unittest

from pathlib import Path


import main


from omni.action_engine import (
    ActionEngine,
    ActionPolicy,
    ActionRisk,
    ToolBridge,
)

from omni.browser_actions import (
    BrowserActions,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.document_intelligence import (
    DocumentIntelligence,
)

from omni.git_actions import (
    GitActions,
)

from omni.workflow_engine import (
    WorkflowEngine,
)


class FakeBridge:

    def __init__(self):

        self.calls = []


    def names(self):

        return (
            "current_time",
            "open_website",
            "dangerous_unknown",
        )


    def invoke(
        self,
        name,
        arguments=None,
    ):

        self.calls.append(
            (
                name,
                arguments,
            )
        )

        return {
            "tool":
                name,

            "arguments":
                arguments,
        }


class RealWorldActionTests(
    unittest.TestCase
):


    def engine(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        bridge = FakeBridge()

        engine = ActionEngine(
            bridge=bridge,

            audit_path=
                Path(
                    temp.name
                )
                / "actions.jsonl",
        )

        return (
            bridge,
            engine,
        )


    def test_protected_core_still_ok(self):

        result = (
            verify_protected_core()
        )

        self.assertTrue(
            result.ok
        )


    def test_read_action_executes_without_approval(self):

        bridge, engine = (
            self.engine()
        )

        result = engine.execute(
            "current_time"
        )

        self.assertTrue(
            result.success
        )

        self.assertEqual(
            len(
                bridge.calls
            ),
            1,
        )


    def test_medium_action_requires_approval(self):

        bridge, engine = (
            self.engine()
        )

        result = engine.execute(
            "open_website",

            {
                "url":
                    "https://example.com"
            },
        )

        self.assertFalse(
            result.success
        )

        self.assertEqual(
            result.error,
            "Explicit approval required.",
        )

        self.assertEqual(
            len(
                bridge.calls
            ),
            0,
        )


    def test_medium_action_runs_after_approval(self):

        bridge, engine = (
            self.engine()
        )

        result = engine.execute(
            "open_website",

            {
                "url":
                    "https://example.com"
            },

            approved=True,
        )

        self.assertTrue(
            result.success
        )

        self.assertEqual(
            len(
                bridge.calls
            ),
            1,
        )


    def test_unknown_action_blocked(self):

        bridge, engine = (
            self.engine()
        )

        result = engine.execute(
            "dangerous_unknown",
            approved=True,
        )

        self.assertFalse(
            result.success
        )

        self.assertEqual(
            result.risk,
            ActionRisk.BLOCKED,
        )


    def test_trading_execution_blocked(self):

        policy = ActionPolicy(
            {
                "place_trade":
                    ActionRisk.LOW,
            }
        )

        # Safety override wins.

        self.assertEqual(
            policy.classify(
                "place_trade"
            ),
            ActionRisk.BLOCKED,
        )


    def test_workflow_success(self):

        bridge, engine = (
            self.engine()
        )

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        workflow = WorkflowEngine(
            engine=engine,

            audit_path=
                Path(
                    temp.name
                )
                / "workflow.jsonl",
        )

        result = workflow.run(
            (
                {
                    "step_id":
                        "one",

                    "tool":
                        "current_time",
                },

                {
                    "step_id":
                        "two",

                    "tool":
                        "open_website",

                    "arguments": {
                        "url":
                            "https://example.com",
                    },

                    "approved":
                        True,
                },
            )
        )

        self.assertEqual(
            result.state.value,
            "completed",
        )

        self.assertEqual(
            result.completed_steps,
            2,
        )


    def test_workflow_blocks_for_approval(self):

        bridge, engine = (
            self.engine()
        )

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        workflow = WorkflowEngine(
            engine=engine,

            audit_path=
                Path(
                    temp.name
                )
                / "workflow.jsonl",
        )

        result = workflow.run(
            (
                {
                    "tool":
                        "current_time",
                },

                {
                    "tool":
                        "open_website",

                    "arguments": {
                        "url":
                            "https://example.com",
                    },
                },
            )
        )

        self.assertEqual(
            result.state.value,
            "blocked",
        )


    def test_browser_rejects_javascript_scheme(self):

        browser = BrowserActions()

        with self.assertRaises(
            ValueError
        ):

            browser.validate_url(
                "javascript:alert(1)"
            )


    def test_document_text(self):

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "doc.txt"
            )

            path.write_text(
                "Jarvis architecture test.",
                encoding="utf-8",
            )

            docs = (
                DocumentIntelligence()
            )

            result = docs.read(
                path
            )

            self.assertIn(
                "Jarvis architecture",
                result[
                    "text"
                ],
            )


    def test_document_search(self):

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "doc.txt"
            )

            path.write_text(
                (
                    "Alpha\n"
                    "Jarvis memory architecture\n"
                    "Omega"
                ),
                encoding="utf-8",
            )

            docs = (
                DocumentIntelligence()
            )

            result = docs.search(
                path,
                "memory",
            )

            self.assertEqual(
                result[
                    "count"
                ],
                1,
            )


    def test_git_push_blocked(self):

        git = GitActions()

        with self.assertRaises(
            PermissionError
        ):

            git.push()


    def test_public_apis_exist(self):

        self.assertTrue(
            callable(
                main
                .jarvis_action_status
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_execute_action
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_run_workflow
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_system_state
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_read_document
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_discover_tools
            )
        )


if __name__ == "__main__":
    unittest.main()
