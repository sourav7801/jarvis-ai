from __future__ import annotations

from pathlib import Path
import unittest

from workstation.discovery_routing_bridge import _annotate_discovery_rows


ROOT = Path(__file__).resolve().parents[1]


class V11DiscoveryScoreContractTests(unittest.TestCase):
    def test_discovery_rows_are_explicitly_non_executable(self) -> None:
        rows = _annotate_discovery_rows([{
            "symbol": "CIPLA",
            "state": "CONFIRMED_BREAKOUT",
            "direction": "BULLISH",
            "score": 72.0,
            "candidate": True,
            "auto_paper_eligible": True,
        }])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["discovery_timeframe"], "1d")
        self.assertEqual(row["score_kind"], "DISCOVERY")
        self.assertFalse(row["execution_authority"])
        self.assertTrue(row["execution_score_required"])
        self.assertIn("INTRADAY", row["suggested_execution_horizons"])
        self.assertIn("SWING", row["suggested_execution_horizons"])
        self.assertIn("INVESTMENT", row["suggested_execution_horizons"])

    def test_unconfirmed_discovery_never_gains_execution_authority(self) -> None:
        row = _annotate_discovery_rows([{
            "symbol": "MARUTI",
            "state": "BREAKOUT_WATCH",
            "direction": "BULLISH",
            "score": 71.0,
        }])[0]
        self.assertFalse(row["execution_authority"])
        self.assertTrue(row["execution_score_required"])
        self.assertNotIn("INVESTMENT", row["suggested_execution_horizons"])


class V11CrossProcessAuthorityTests(unittest.TestCase):
    def test_quant_startup_installs_v11_bridges_in_owner_process(self) -> None:
        source = (ROOT / "start_jarvis_quant_terminal.py").read_text(encoding="utf-8")
        self.assertIn("install_v11_quant_bridges", source)
        self.assertIn("install_derived_timeframe_bridge", source)
        self.assertIn("install_discovery_routing_bridge", source)
        self.assertIn("server.serve_forever(", source)
        self.assertNotIn("place_order(", source)
        self.assertNotIn("submit_order(", source)

    def test_completion_does_not_create_shadow_quant_runtime(self) -> None:
        source = (ROOT / "workstation" / "completion_console_v11.py").read_text(encoding="utf-8")
        self.assertIn("_loopback_json", source)
        self.assertIn('/api/paper/portfolio-controller', source)
        self.assertIn('/api/scanner/multi', source)
        self.assertNotIn("from workstation.derived_timeframe_bridge import install_derived_timeframe_bridge", source)
        self.assertNotIn("from workstation.discovery_routing_bridge import install_discovery_routing_bridge", source)

    def test_decision_mesh_reads_authoritative_quant_loopback(self) -> None:
        source = (ROOT / "workstation" / "trading_decision_mesh.py").read_text(encoding="utf-8")
        self.assertIn('QUANT_BASE = "http://127.0.0.1:8787"', source)
        self.assertIn('/api/scanner/multi', source)
        self.assertIn('/api/paper/portfolio-controller', source)
        self.assertIn('"runtime_source": "QUANT_LOOPBACK_8787"', source)
        self.assertNotIn("place_order(", source)
        self.assertNotIn("submit_order(", source)


if __name__ == "__main__":
    unittest.main()
