import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V1731BridgeContractTests(unittest.TestCase):
    def test_bridge_advertises_quarantine_contract(self):
        text = (ROOT / "workstation" / "fyers_live_bridge_service.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('BRIDGE_CONTRACT_VERSION = "1.1"', text)
        self.assertIn('"version": BRIDGE_CONTRACT_VERSION', text)
        self.assertIn('"subscription_quarantine": True', text)
        self.assertIn('"quarantined_count": len(_QUARANTINED_SUBSCRIPTIONS)', text)

    def test_quant_does_not_treat_open_port_as_current_bridge(self):
        text = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(
            encoding="utf-8"
        )
        start = text.split("def start_live_bridge() -> bool:", 1)[1].split(
            "def _start_live_bridge_unlocked", 1
        )[0]
        self.assertIn("if _live_bridge_contract_current():", start)
        self.assertIn("if _port_open(LIVE_BRIDGE_HOST, LIVE_BRIDGE_PORT):", start)
        self.assertIn("if not _replace_stale_live_bridge():", start)
        self.assertIn("INCOMPATIBLE_BRIDGE", start)

    def test_only_trusted_bridge_process_can_be_replaced(self):
        text = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(
            encoding="utf-8"
        )
        helper = text.split("def _trusted_stale_live_bridge_pid()", 1)[1].split(
            "def _replace_stale_live_bridge", 1
        )[0]
        self.assertIn("identity.get(\"service\") != LIVE_BRIDGE_EXPECTED_SERVICE", helper)
        self.assertIn("workstation.fyers_live_bridge_service", helper)
        self.assertIn('\"python\" not in name', helper)
        self.assertNotIn("fyers_python().resolve()", helper)
        self.assertIn("return None", helper)

    def test_owned_bridge_is_stopped_with_quant_runtime(self):
        text = (ROOT / "workstation" / "quant_terminal_v2.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _stop_owned_live_bridge()", text)
        main = text.split("def main() -> int:", 1)[1]
        self.assertIn("finally:", main)
        self.assertIn("_stop_owned_live_bridge()", main)


if __name__ == "__main__":
    unittest.main()
