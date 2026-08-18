import tempfile
import unittest
from pathlib import Path

from omni.knowledge_graph import (
    KnowledgeGraph,
)


class KnowledgeGraphTests(
    unittest.TestCase
):

    def test_nodes_edges(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        graph = KnowledgeGraph(
            Path(temp.name)
            / "graph.json"
        )

        graph.upsert_node(
            "jarvis",
            kind="system",
            label="JARVIS",
        )

        graph.upsert_node(
            "fyers",
            kind="broker",
            label="FYERS",
        )

        graph.link(
            "jarvis",
            "uses",
            "fyers",
        )

        self.assertEqual(
            graph.stats(),
            {
                "nodes": 2,
                "edges": 1,
            },
        )


    def test_attribute_merge(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        graph = KnowledgeGraph(
            Path(temp.name)
            / "graph.json"
        )

        graph.upsert_node(
            "x",
            kind="topic",
            label="X",
            attributes={
                "a": 1,
            },
        )

        graph.upsert_node(
            "x",
            kind="topic",
            label="X",
            attributes={
                "b": 2,
            },
        )

        node = graph.get(
            "x"
        )

        self.assertEqual(
            node["attributes"]["a"],
            1,
        )

        self.assertEqual(
            node["attributes"]["b"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
