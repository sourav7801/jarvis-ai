from __future__ import annotations

import unittest
from pathlib import Path


class QuantIntelligenceTargetContractTests(unittest.TestCase):
    def test_target_contract_preserves_full_intelligence_mission(self):
        root = Path(__file__).resolve().parents[1]
        text = (
            root
            / "omni"
            / "trading_intelligence"
            / "QUANT_INTELLIGENCE_TARGET.md"
        ).read_text(encoding="utf-8").lower()

        required = (
            "support/resistance",
            "bos / choch",
            "fair value gaps",
            "indicator registry",
            "pattern engine",
            "option chain",
            "change in oi",
            "implied volatility",
            "strategy families",
            "champion/challenger",
            "self-improvement / mistake analysis",
            "autonomous paper trading",
            "nautilus",
            "paper_only = true",
            "live_execution = false",
        )

        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_contract_does_not_define_win_rate_as_the_only_goal(self):
        root = Path(__file__).resolve().parents[1]
        text = (
            root
            / "omni"
            / "trading_intelligence"
            / "QUANT_INTELLIGENCE_TARGET.md"
        ).read_text(encoding="utf-8").lower()
        self.assertIn("must not optimize for win rate alone", text)
        self.assertIn("expectancy", text)
        self.assertIn("walk-forward", text)
        self.assertIn("out-of-sample", text)


if __name__ == "__main__":
    unittest.main()
