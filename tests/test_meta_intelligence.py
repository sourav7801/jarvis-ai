import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from workstation import app

from omni.knowledge_graph import (
    KnowledgeGraph,
)

from omni.meta_intelligence import (
    MetaIntelligenceEngine,
)

from omni.skill_factory import (
    SkillFactory,
)


class MetaIntelligenceTests(
    unittest.TestCase
):

    def engine(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        root = Path(
            temp.name
        )

        return MetaIntelligenceEngine(
            graph=KnowledgeGraph(
                root
                / "graph.json"
            ),

            skill_factory=SkillFactory(
                root
                / "skills"
            ),
        )


    def test_gap_detected(self):

        engine = self.engine()

        with patch(
            "omni.meta_intelligence."
            "recall_context",
            return_value=(),
        ):

            result = (
                engine
                .detect_knowledge_gap(
                    "quantum networking"
                )
            )

        self.assertTrue(
            result.gap_detected
        )


    def test_existing_knowledge(self):

        engine = self.engine()

        with patch(
            "omni.meta_intelligence."
            "recall_context",
            return_value=(
                {"content": "a"},
                {"content": "b"},
                {"content": "c"},
            ),
        ):

            result = (
                engine
                .detect_knowledge_gap(
                    "distributed systems"
                )
            )

        self.assertFalse(
            result.gap_detected
        )


    def test_improvement_proposal(self):

        engine = self.engine()

        proposal = (
            engine
            .propose_improvement(
                "planning",
                60,
                90,
            )
        )

        self.assertEqual(
            proposal.gap,
            30,
        )

        self.assertTrue(
            proposal.requires_approval
        )


    def test_main_api(self):

        self.assertTrue(
            callable(
                main.jarvis_learn
            )
        )

        self.assertTrue(
            callable(
                main.jarvis_knowledge_gap
            )
        )


    def test_workstation_api(self):

        self.assertTrue(
            callable(
                app.jarvis_meta_status_payload
            )
        )


if __name__ == "__main__":
    unittest.main()
