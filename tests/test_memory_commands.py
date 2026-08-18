import unittest
from dataclasses import dataclass
from unittest.mock import patch

import main
from workstation import app

from omni.memory_scope import (
    MemoryScope,
    use_memory_context,
)

from omni.memory_contradiction import (
    explicit_replacement_hint,
)

from omni import memory_context

from omni.memory_commands import (
    memory_command_answer,
)


@dataclass
class Record:
    content: str
    record_id: str
    kind: str = "semantic"
    source: str = "user"
    tags: tuple[str, ...] = ()
    metadata: dict | None = None


class FakeMemory:

    def __init__(self):
        self.records = {}

    def get(
        self,
        record_id,
    ):
        return self.records.get(
            record_id
        )

    def remember(
        self,
        **kwargs,
    ):

        record = Record(
            content=kwargs["content"],
            record_id=kwargs["record_id"],
            kind=kwargs["kind"],
            source=kwargs["source"],
            tags=kwargs["tags"],
            metadata=kwargs["metadata"],
        )

        self.records[
            record.record_id
        ] = record

        return record


class MemoryCommandTests(
    unittest.TestCase
):

    def test_preference_replacement_parser(self):

        hint = explicit_replacement_hint(
            "I now prefer detailed answers "
            "instead of concise answers",
            MemoryScope.PREFERENCE,
        )

        self.assertIsNotNone(
            hint
        )

        self.assertEqual(
            hint.old_query,
            "concise answers",
        )


    def test_decision_replacement_parser(self):

        hint = explicit_replacement_hint(
            "We decided to use FYERS "
            "instead of Upstox",
            MemoryScope.DECISION,
        )

        self.assertIsNotNone(
            hint
        )

        self.assertEqual(
            hint.old_query,
            "Upstox",
        )


    def test_semantic_similarity_not_enough(self):

        hint = explicit_replacement_hint(
            "FYERS is useful for trading",
            MemoryScope.DECISION,
        )

        self.assertIsNone(
            hint
        )


    def test_preference_not_locked_to_chat(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            with use_memory_context(
                conversation_id="chat-a",
            ):

                record = (
                    memory_context.
                    remember_scoped(
                        "Prefer concise answers",
                        MemoryScope.PREFERENCE,
                    )
                )

        self.assertNotIn(
            "conversation_id",
            record.metadata,
        )


    def test_agent_finding_keeps_chat_scope(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            with use_memory_context(
                conversation_id="chat-a",
            ):

                record = (
                    memory_context.
                    remember_scoped(
                        "Research finding",
                        MemoryScope.AGENT_FINDING,
                    )
                )

        self.assertEqual(
            record.metadata[
                "conversation_id"
            ],
            "chat-a",
        )


    def test_recall_command(self):

        result = (
            {
                "record_id": "abc",
                "content": "Use FYERS",
                "metadata": {
                    "memory_scope":
                        "decision",
                },
            },
        )

        with patch(
            "omni.memory_commands.recall_context",
            return_value=result,
        ):

            answer = memory_command_answer(
                "What do you remember about FYERS?",
                conversation_id="test",
            )

        self.assertIn(
            "Use FYERS",
            answer,
        )

        self.assertIn(
            "abc",
            answer,
        )


    def test_forget_by_id(self):

        with patch(
            "omni.memory_commands.forget_memory",
        ) as forget:

            answer = memory_command_answer(
                "Forget memory decision-123",
                conversation_id="test",
            )

        forget.assert_called_once()

        self.assertIn(
            "logically forgotten",
            answer,
        )


    def test_ambiguous_forget_is_blocked(self):

        matches = (
            {
                "record_id": "1",
                "content": "First",
                "metadata": {
                    "memory_scope":
                        "decision",
                },
            },
            {
                "record_id": "2",
                "content": "Second",
                "metadata": {
                    "memory_scope":
                        "decision",
                },
            },
        )

        with patch(
            "omni.memory_commands.recall_scoped",
            return_value=matches,
        ), patch(
            "omni.memory_commands.forget_memory",
        ) as forget:

            answer = memory_command_answer(
                "Forget the decision about broker",
                conversation_id="test",
            )

        forget.assert_not_called()

        self.assertIn(
            "multiple",
            answer.lower(),
        )


    def test_normal_command_not_intercepted(self):

        answer = memory_command_answer(
            "Open calculator",
            conversation_id="test",
        )

        self.assertIsNone(
            answer
        )


    def test_main_memory_helpers_exist(self):

        self.assertTrue(
            callable(
                main.jarvis_capture_salient_input
            )
        )

        self.assertTrue(
            callable(
                main.jarvis_memory_command_answer
            )
        )


    def test_workstation_helper_exists(self):

        self.assertTrue(
            callable(
                app.jarvis_memory_command_payload
            )
        )


if __name__ == "__main__":
    unittest.main()
