import unittest
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import patch

from omni.memory_scope import (
    MemoryScope,
)

from omni.memory_lifecycle import (
    decay_factor,
    effective_importance,
    enrich_lifecycle_metadata,
    forget_record,
    mark_superseded,
    recall_eligible,
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
    score: float = 0.9


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


class MemoryLifecycleTests(
    unittest.TestCase
):

    def test_preference_has_high_importance(self):

        metadata = enrich_lifecycle_metadata(
            MemoryScope.PREFERENCE,
            {},
        )

        self.assertGreaterEqual(
            metadata["importance"],
            0.9,
        )

        self.assertEqual(
            metadata["memory_state"],
            "active",
        )

    def test_conversation_decays_faster_than_preference(self):

        created = (
            datetime.now(
                timezone.utc
            )
            - timedelta(
                days=30
            )
        ).isoformat()

        metadata = {
            "created_at": created,
            "importance": 0.9,
        }

        conversation = decay_factor(
            MemoryScope.CONVERSATION,
            metadata,
        )

        preference = decay_factor(
            MemoryScope.PREFERENCE,
            metadata,
        )

        self.assertLess(
            conversation,
            preference,
        )

    def test_effective_importance_decays(self):

        recent = {
            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "importance": 0.8,
        }

        old = {
            "created_at":
                (
                    datetime.now(
                        timezone.utc
                    )
                    - timedelta(
                        days=365
                    )
                ).isoformat(),
            "importance": 0.8,
        }

        recent_score = (
            effective_importance(
                MemoryScope.AGENT_FINDING,
                recent,
            )
        )

        old_score = (
            effective_importance(
                MemoryScope.AGENT_FINDING,
                old,
            )
        )

        self.assertGreater(
            recent_score,
            old_score,
        )

    def test_soft_forget_blocks_recall(self):

        memory = FakeMemory()

        record = Record(
            content="Old memory",
            record_id="old",
            metadata={
                "memory_scope": "decision",
                "memory_state": "active",
                "importance": 0.9,
            },
        )

        memory.records[
            "old"
        ] = record

        forget_record(
            memory,
            "old",
        )

        item = {
            "record_id": "old",
            "content": "Old memory",
            "metadata": record.metadata,
        }

        self.assertFalse(
            recall_eligible(
                memory,
                item,
            )
        )

    def test_superseded_memory_blocks_recall(self):

        memory = FakeMemory()

        memory.records[
            "old"
        ] = Record(
            "Old decision",
            "old",
        )

        memory.records[
            "new"
        ] = Record(
            "New decision",
            "new",
        )

        mark_superseded(
            memory,
            "old",
            "new",
        )

        item = {
            "record_id": "old",
            "content": "Old decision",
            "metadata": {
                "memory_scope": "decision",
                "importance": 0.9,
            },
        }

        self.assertFalse(
            recall_eligible(
                memory,
                item,
            )
        )

    def test_control_records_never_enter_recall(self):

        memory = FakeMemory()

        item = {
            "record_id": "control",
            "content": "forget something",
            "metadata": {
                "memory_control": "forget",
            },
        }

        self.assertFalse(
            recall_eligible(
                memory,
                item,
            )
        )

    def test_new_scoped_memory_has_lifecycle_metadata(self):

        memory = FakeMemory()

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            record = (
                memory_context.
                remember_scoped(
                    "Use governed execution",
                    MemoryScope.DECISION,
                )
            )

        self.assertIn(
            "importance",
            record.metadata,
        )

        self.assertIn(
            "created_at",
            record.metadata,
        )

        self.assertEqual(
            record.metadata[
                "memory_state"
            ],
            "active",
        )

    def test_recall_filters_forgotten_memory(self):

        memory = FakeMemory()

        record = Record(
            content="Forgotten architecture",
            record_id="old",
            tags=(
                "scope:decision",
            ),
            metadata={
                "memory_scope": "decision",
                "memory_state": "active",
                "importance": 0.9,
            },
        )

        memory.records[
            "old"
        ] = record

        memory.hits = [
            Hit(record)
        ]

        forget_record(
            memory,
            "old",
        )

        with patch(
            "omni.memory_context.resolve_memory",
            return_value=memory,
        ):

            result = (
                memory_context.
                recall_scoped(
                    "architecture",
                    scopes=[
                        MemoryScope.DECISION
                    ],
                )
            )

        self.assertEqual(
            result,
            (),
        )


if __name__ == "__main__":
    unittest.main()
