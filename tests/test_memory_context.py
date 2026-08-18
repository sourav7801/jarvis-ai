import unittest
from dataclasses import dataclass
from unittest.mock import patch

from omni import memory_context


@dataclass
class FakeRecord:
    content: str
    record_id: str = "abc"
    kind: str = "semantic"
    source: str = "user"


@dataclass
class FakeHit:
    record: FakeRecord
    score: float = 0.95


class FakeMemory:

    def __init__(self):
        self.saved = []
        self.existing = None

    def search(
        self,
        query,
        limit=10,
    ):
        return [
            FakeHit(
                FakeRecord(
                    "Previous useful decision"
                )
            )
        ]

    def lexical_search(
        self,
        query,
        limit=20,
    ):
        return [
            FakeRecord(
                "Lexical fallback"
            )
        ]

    def get(
        self,
        record_id,
    ):
        return self.existing

    def remember(
        self,
        **kwargs,
    ):
        self.saved.append(
            kwargs
        )
        return kwargs


class FakeResult:
    success = True
    final_answer = "Use the governed architecture."
    intent = "coding"
    lead_agent = "coding"


class MemoryContextTests(
    unittest.TestCase
):

    def test_recall_normalizes_memory(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_context(
                    "Jarvis architecture"
                )
            )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result[0]["content"],
            "Previous useful decision",
        )

    def test_lexical_fallback(self):

        memory = FakeMemory()

        def broken_search(
            query,
            limit=10,
        ):
            raise RuntimeError(
                "semantic unavailable"
            )

        memory.search = broken_search

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_context(
                    "Jarvis"
                )
            )

        self.assertEqual(
            result[0]["content"],
            "Lexical fallback",
        )

    def test_success_is_remembered(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.
                remember_collaboration(
                    "Improve Jarvis",
                    FakeResult(),
                )
            )

        self.assertIsNotNone(
            result
        )

        self.assertEqual(
            len(memory.saved),
            1,
        )

        self.assertEqual(
            memory.saved[0]["kind"],
            "event",
        )

        self.assertEqual(
            memory.saved[0]["source"],
            "jarvis",
        )

    def test_duplicate_event_is_not_reinserted(self):

        memory = FakeMemory()

        memory.existing = (
            FakeRecord(
                "already stored"
            )
        )

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.
                remember_collaboration(
                    "Improve Jarvis",
                    FakeResult(),
                )
            )

        self.assertIsNotNone(
            result
        )

        self.assertEqual(
            memory.saved,
            [],
        )


if __name__ == "__main__":
    unittest.main()
