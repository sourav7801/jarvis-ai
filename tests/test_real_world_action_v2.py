import tempfile
import unittest

from pathlib import Path


import main


from omni.approval_queue import (
    ApprovalQueue,
)

from omni.browser_automation_v2 import (
    BrowserAutomation,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.desktop_automation import (
    DesktopAutomation,
)

from omni.integration_status import (
    IntegrationStatus,
)

from omni.observed_workflow import (
    ObservedWorkflowEngine,
)


class ActionV2Tests(
    unittest.TestCase
):


    def queue(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        return ApprovalQueue(
            Path(
                temp.name
            )
        )


    def test_protected_core_ok(self):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_approval_signature(self):

        queue = self.queue()

        request = queue.request(
            "click",
            {
                "x": 10,
                "y": 20,
            },
        )

        queue.approve(
            request[
                "approval_id"
            ]
        )

        self.assertTrue(
            queue.consume(
                request[
                    "approval_id"
                ],

                "click",

                {
                    "x": 10,
                    "y": 20,
                },
            )
        )


    def test_approval_cannot_change_payload(self):

        queue = self.queue()

        request = queue.request(
            "click",
            {
                "x": 10,
                "y": 20,
            },
        )

        queue.approve(
            request[
                "approval_id"
            ]
        )


        with self.assertRaises(
            PermissionError
        ):

            queue.consume(
                request[
                    "approval_id"
                ],

                "click",

                {
                    "x": 999,
                    "y": 999,
                },
            )


    def test_approval_one_time_only(self):

        queue = self.queue()

        request = queue.request(
            "x",
            {
                "a": 1,
            },
        )

        queue.approve(
            request[
                "approval_id"
            ]
        )

        queue.consume(
            request[
                "approval_id"
            ],
            "x",
            {
                "a": 1,
            },
        )


        with self.assertRaises(
            PermissionError
        ):

            queue.consume(
                request[
                    "approval_id"
                ],
                "x",
                {
                    "a": 1,
                },
            )


    def test_rejected_approval_cannot_execute(self):

        queue = self.queue()

        request = queue.request(
            "x",
            {},
        )

        queue.reject(
            request[
                "approval_id"
            ]
        )


        with self.assertRaises(
            PermissionError
        ):

            queue.consume(
                request[
                    "approval_id"
                ],
                "x",
                {},
            )


    def test_desktop_windows_returns_tuple(self):

        desktop = DesktopAutomation()

        self.assertIsInstance(
            desktop.windows(),
            tuple,
        )


    def test_sensitive_typing_blocked(self):

        desktop = DesktopAutomation()

        result = desktop.type_text(
            "secret",
            sensitive=True,
        )

        self.assertFalse(
            result[
                "success"
            ]
        )


    def test_browser_blocks_unsafe_scheme(self):

        browser = (
            BrowserAutomation()
        )


        with self.assertRaises(
            ValueError
        ):

            browser.validate_url(
                "javascript:alert(1)"
            )


    def test_browser_requires_approval_before_provider(self):

        browser = (
            BrowserAutomation()
        )

        result = browser.inspect(
            "https://example.com"
        )

        self.assertTrue(
            result[
                "requires_approval"
            ]
        )


    def test_browser_password_fill_blocked(self):

        browser = (
            BrowserAutomation()
        )

        result = browser.fill(
            "https://example.com",
            'input[type="password"]',
            "secret",
        )

        self.assertFalse(
            result[
                "success"
            ]
        )


    def test_observed_workflow_retry(self):

        calls = {
            "count": 0,
        }


        def executor(
            step,
        ):

            calls[
                "count"
            ] += 1


            if (
                calls[
                    "count"
                ]
                == 1
            ):

                return {
                    "success":
                        False,

                    "error":
                        "temporary",
                }


            return {
                "success":
                    True,
            }


        engine = (
            ObservedWorkflowEngine(
                executor,
                observer=
                    lambda: {
                        "state":
                            "observed"
                    },
            )
        )


        result = engine.run(
            (
                {
                    "step_id":
                        "one",

                    "retries":
                        1,
                },
            )
        )


        self.assertTrue(
            result.success
        )

        self.assertEqual(
            calls[
                "count"
            ],
            2,
        )


    def test_observed_failure_requests_replan(self):

        engine = (
            ObservedWorkflowEngine(
                lambda step: {
                    "success":
                        False,

                    "error":
                        "failure",
                }
            )
        )


        result = engine.run(
            (
                {
                    "step_id":
                        "broken",
                },
            )
        )


        self.assertFalse(
            result.success
        )

        self.assertTrue(
            result.needs_replan
        )

        self.assertEqual(
            result.failed_step,
            "broken",
        )


    def test_integration_status(self):

        status = (
            IntegrationStatus()
            .status()
        )


        self.assertIn(
            "playwright",
            status,
        )

        self.assertIn(
            "gmail",
            status,
        )

        self.assertIn(
            "google_calendar",
            status,
        )

        self.assertIn(
            "voice",
            status,
        )


    def test_public_apis(self):

        self.assertTrue(
            callable(
                main
                .jarvis_pending_approvals
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_approve_action
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_windows
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_click
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_browser_inspect
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_integration_status
            )
        )


if __name__ == "__main__":
    unittest.main()
