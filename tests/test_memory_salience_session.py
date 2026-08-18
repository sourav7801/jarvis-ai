import unittest
from dataclasses import dataclass
from unittest.mock import patch

from omni.memory_salience import (
    classify_salience,
)

from omni.memory_scope import (
    MemoryScope,
    use_memory_context,
)

from omni.session_context import (
    get_session_id,
    new_session,
)

from omni import memory_context


@dataclass
class Record:
    content: str
    record_id: str
    kind: str = "semantic"
    source: str = "user"
    tags: tuple[str, ...] = ()
    metadata: dict | None = None


@dataclass
class Hit:
    record: Record
    score: float = 1.0


class FakeMemory:

    def __init__(self):
        self.records = {}
        self.hits = []

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

    def search(
        self,
        query,
        limit=10,
    ):
        return self.hits[:limit]

    def lexical_search(
        self,
        query,
        limit=20,
    ):
        return self.hits[:limit]


class MemorySalienceTests(
    unittest.TestCase
):

    def test_preference_is_salient(self):

        result = classify_salience(
            "From now on I prefer concise responses."
        )

        self.assertTrue(
            result.remember
        )

        self.assertEqual(
            result.scope,
            MemoryScope.PREFERENCE,
        )

    def test_decision_is_salient(self):

        result = classify_salience(
            "We decided to use FYERS as the "
            "canonical market provider."
        )

        self.assertTrue(
            result.remember
        )

        self.assertEqual(
            result.scope,
            MemoryScope.DECISION,
        )

    def test_project_state_requires_project(self):

        text = (
            "Phase 5 project architecture is "
            "event driven."
        )

        without_project = classify_salience(
            text,
            has_project=False,
        )

        with_project = classify_salience(
            text,
            has_project=True,
        )

        self.assertFalse(
            without_project.remember
        )

        self.assertTrue(
            with_project.remember
        )

        self.assertEqual(
            with_project.scope,
            MemoryScope.PROJECT,
        )

    def test_normal_chat_is_not_saved(self):

        self.assertFalse(
            classify_salience(
                "Hello Jarvis"
            ).remember
        )

        self.assertFalse(
            classify_salience(
                "Can you explain this Python code?"
            ).remember
        )

    def test_runtime_session_is_stable(self):

        first = get_session_id(
            "workstation-test"
        )

        second = get_session_id(
            "workstation-test"
        )

        self.assertEqual(
            first,
            second,
        )

        third = new_session(
            "workstation-test"
        )

        self.assertNotEqual(
            first,
            third,
        )

    def test_salient_input_is_saved(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.
                remember_salient_input(
                    "I prefer concise answers."
                )
            )

        self.assertIsNotNone(
            result
        )

        self.assertIn(
            "scope:preference",
            result.tags,
        )

    def test_non_salient_input_is_ignored(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.
                remember_salient_input(
                    "How are you today?"
                )
            )

        self.assertIsNone(
            result
        )

        self.assertEqual(
            memory.records,
            {},
        )

    def test_conversation_bound_finding_does_not_leak(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content=(
                        "Private finding "
                        "from conversation A"
                    ),
                    record_id="a",
                    tags=(
                        "scope:agent_finding",
                        "conversation:a",
                    ),
                    metadata={
                        "memory_scope":
                            "agent_finding",
                        "conversation_id":
                            "a",
                    },
                )
            )
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            with use_memory_context(
                conversation_id="b",
            ):

                result = (
                    memory_context.
                    recall_context(
                        "private finding"
                    )
                )

        self.assertEqual(
            result,
            (),
        )

    def test_same_conversation_can_recall_finding(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content="Useful finding",
                    record_id="a",
                    tags=(
                        "scope:agent_finding",
                        "conversation:a",
                    ),
                    metadata={
                        "memory_scope":
                            "agent_finding",
                        "conversation_id":
                            "a",
                    },
                )
            )
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            with use_memory_context(
                conversation_id="a",
            ):

                result = (
                    memory_context.
                    recall_context(
                        "useful finding"
                    )
                )

        self.assertEqual(
            len(result),
            1,
        )


if __name__ == "__main__":
    unittest.main()
