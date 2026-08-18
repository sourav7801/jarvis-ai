import unittest
from dataclasses import dataclass
from unittest.mock import patch

from omni.memory_scope import (
    MemoryScope,
    current_memory_context,
    use_memory_context,
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

    def get(self, record_id):
        return self.records.get(
            record_id
        )

    def remember(self, **kwargs):

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


class ScopedMemoryTests(unittest.TestCase):

    def test_context_is_restored(self):

        self.assertIsNone(
            current_memory_context().
            project_id
        )

        with use_memory_context(
            project_id="Jarvis Project",
            conversation_id="ABC 123",
        ):

            context = (
                current_memory_context()
            )

            self.assertEqual(
                context.project_id,
                "jarvis-project",
            )

            self.assertEqual(
                context.conversation_id,
                "abc-123",
            )

        self.assertIsNone(
            current_memory_context().
            project_id
        )

    def test_project_memory_is_tagged(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            record = (
                memory_context.
                remember_project(
                    "Jarvis",
                    "Use governed agents",
                )
            )

        self.assertIn(
            "scope:project",
            record.tags,
        )

        self.assertIn(
            "project:jarvis",
            record.tags,
        )

    def test_project_isolation(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content="Jarvis fact",
                    record_id="1",
                    tags=(
                        "scope:project",
                        "project:jarvis",
                    ),
                    metadata={
                        "memory_scope":
                            "project",
                        "project_id":
                            "jarvis",
                    },
                )
            ),
            Hit(
                Record(
                    content="Other project fact",
                    record_id="2",
                    tags=(
                        "scope:project",
                        "project:other",
                    ),
                    metadata={
                        "memory_scope":
                            "project",
                        "project_id":
                            "other",
                    },
                )
            ),
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_scoped(
                    "architecture",
                    scopes=[
                        MemoryScope.PROJECT
                    ],
                    project_id="jarvis",
                )
            )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result[0]["content"],
            "Jarvis fact",
        )

    def test_conversation_isolation(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content="Current conversation",
                    record_id="1",
                    tags=(
                        "scope:conversation",
                        "conversation:a",
                    ),
                    metadata={
                        "memory_scope":
                            "conversation",
                        "conversation_id":
                            "a",
                    },
                )
            ),
            Hit(
                Record(
                    content="Other conversation",
                    record_id="2",
                    tags=(
                        "scope:conversation",
                        "conversation:b",
                    ),
                    metadata={
                        "memory_scope":
                            "conversation",
                        "conversation_id":
                            "b",
                    },
                )
            ),
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_scoped(
                    "conversation",
                    scopes=[
                        MemoryScope.CONVERSATION
                    ],
                    conversation_id="a",
                )
            )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            result[0]["content"],
            "Current conversation",
        )

    def test_no_project_leak_without_project_id(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content="Secret project",
                    record_id="1",
                    tags=(
                        "scope:project",
                        "project:alpha",
                    ),
                    metadata={
                        "memory_scope":
                            "project",
                        "project_id":
                            "alpha",
                    },
                )
            )
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_scoped(
                    "secret",
                    scopes=[
                        MemoryScope.PROJECT
                    ],
                )
            )

        self.assertEqual(
            result,
            (),
        )

    def test_preferences_are_global(self):

        memory = FakeMemory()

        memory.hits = [
            Hit(
                Record(
                    content="Prefer concise answers",
                    record_id="1",
                    tags=(
                        "scope:preference",
                    ),
                    metadata={
                        "memory_scope":
                            "preference",
                    },
                )
            )
        ]

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.recall_scoped(
                    "answers",
                    scopes=[
                        MemoryScope.PREFERENCE
                    ],
                )
            )

        self.assertEqual(
            len(result),
            1,
        )


if __name__ == "__main__":
    unittest.main()
