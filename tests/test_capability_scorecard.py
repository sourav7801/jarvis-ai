import tempfile
import unittest
from pathlib import Path

from omni.capability_scorecard import (
    CapabilityScorecard,
)


class CapabilityScorecardTests(
    unittest.TestCase
):

    def test_score_accumulates_evidence(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        card = CapabilityScorecard(
            Path(temp.name)
            / "score.json"
        )

        card.record(
            "planning",
            60,
            evidence="test1",
        )

        card.record(
            "planning",
            80,
            evidence="test2",
        )

        item = card.get(
            "planning"
        )

        self.assertEqual(
            item[
                "evidence_count"
            ],
            2,
        )

        self.assertEqual(
            item[
                "score"
            ],
            70.0,
        )


    def test_weakness_detection(self):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        card = CapabilityScorecard(
            Path(temp.name)
            / "score.json"
        )

        card.record(
            "planning",
            55,
            evidence="benchmark",
        )

        card.record(
            "coding",
            95,
            evidence="benchmark",
        )

        weak = card.weaknesses(
            threshold=75,
        )

        self.assertEqual(
            len(weak),
            1,
        )

        self.assertEqual(
            weak[0][
                "capability"
            ],
            "planning",
        )


if __name__ == "__main__":
    unittest.main()
