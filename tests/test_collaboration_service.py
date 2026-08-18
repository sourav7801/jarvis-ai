import unittest
from unittest.mock import patch

import main
from workstation import app

from omni.collaboration import (
    AgentContribution,
    CollaborationResult,
)

from omni import collaboration_service


class FakeEngine:

    def collaborate(
        self,
        request,
        runner,
    ):

        runner(
            "chat",
            request,
            {
                "role": "lead",
                "specialist_findings": [
                    "finance finding",
                    "research finding",
                ],
            },
        )

        return CollaborationResult(
            request=request,
            intent="conversation",
            lead_agent="chat",
            contributions=(
                AgentContribution(
                    agent="chat",
                    role="lead",
                    success=True,
                    output="done",
                ),
            ),
            final_answer="done",
            success=True,
        )


class FakeRuntime:

    def __init__(self):
        self.engine = FakeEngine()
        self.seen_prompt = None
        self.seen_context = None

    def runner(
        self,
        agent,
        prompt,
        context,
    ):
        self.seen_prompt = prompt
        self.seen_context = context
        return "done"


class CollaborationServiceTests(
    unittest.TestCase
):

    def test_memory_and_specialist_context_reach_text(self):

        runtime = FakeRuntime()

        memories = (
            {
                "content":
                "Previous relevant decision"
            },
        )

        with patch(
            "omni.collaboration_service.build_runtime",
            return_value=runtime,
        ), patch(
            "omni.collaboration_service.recall_context",
            return_value=memories,
        ), patch(
            "omni.collaboration_service.remember_collaboration",
        ):

            result = (
                collaboration_service.
                collaborate("Hello")
            )

        self.assertTrue(
            result.success
        )

        self.assertIn(
            "Previous relevant decision",
            runtime.seen_prompt,
        )

        self.assertIn(
            "finance finding",
            runtime.seen_prompt,
        )

        self.assertIn(
            "research finding",
            runtime.seen_prompt,
        )

        # Context has already been safely serialized
        # into AgentRequest text.
        self.assertEqual(
            runtime.seen_context,
            {},
        )

    def test_success_is_written_back(self):

        runtime = FakeRuntime()

        with patch(
            "omni.collaboration_service.build_runtime",
            return_value=runtime,
        ), patch(
            "omni.collaboration_service.recall_context",
            return_value=(),
        ), patch(
            "omni.collaboration_service.remember_collaboration",
        ) as remember:

            result = (
                collaboration_service.
                collaborate("Hello")
            )

        remember.assert_called_once_with(
            "Hello",
            result,
        )

    def test_main_entry_preserved(self):

        self.assertTrue(
            callable(
                main.jarvis_collaborate
            )
        )

    def test_workstation_entry_preserved(self):

        self.assertTrue(
            callable(
                app.jarvis_collaboration_payload
            )
        )


if __name__ == "__main__":
    unittest.main()
