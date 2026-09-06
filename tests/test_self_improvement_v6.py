from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omni.trading_intelligence.self_improvement_coordinator import SelfImprovementCoordinator
from omni.trading_intelligence.trade_learning_engine import TradeLearningEngine


class SelfImprovementV6Tests(unittest.TestCase):
    def test_coordinator_is_research_only(self):
        coordinator = SelfImprovementCoordinator(interval_seconds=300)
        status = coordinator.status()
        self.assertTrue(status["research_only"])
        self.assertFalse(status["live_execution"])

    def test_learning_does_not_rewrite_production(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = TradeLearningEngine(Path(folder) / "state.json")
            status = engine.status()
            governance = status["governance"]
            self.assertFalse(governance["automatic_strategy_code_rewrite"])
            self.assertFalse(governance["live_execution"])


if __name__ == "__main__":
    unittest.main()
