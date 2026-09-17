from __future__ import annotations

import unittest

from scripts.jarvis_runtime_supervisor_v17 import (
    V17_ADAPTIVE_AUTHORITY,
    V17_CRYPTO_SERVICE,
    V17_QUANT_SERVICE,
    _current_quant_contract,
    v17_services,
)


class V17SupervisorQuantContractTests(unittest.TestCase):
    def _current_payload(self) -> dict:
        return {
            "success": True,
            "service": V17_QUANT_SERVICE,
            "crypto_underlying_paper": {
                "service": V17_CRYPTO_SERVICE,
                "qualification_authority": V17_ADAPTIVE_AUTHORITY,
                "decision_authority": V17_ADAPTIVE_AUTHORITY,
                "adaptive_policy_version": "ADAPTIVE_OPPORTUNITY_POLICY_V12",
                "legacy_numeric_gates_are_execution_authority": False,
                "paper_only": True,
                "live_execution": False,
                "last_rows_summary": [
                    {
                        "symbol": "BTC",
                        "adaptive_action": "WAIT",
                        "adaptive_side": "LONG",
                    }
                ],
            },
        }

    def test_current_adaptive_crypto_contract_is_accepted(self) -> None:
        self.assertTrue(_current_quant_contract(self._current_payload()))

    def test_blank_legacy_crypto_contract_is_rejected(self) -> None:
        payload = self._current_payload()
        crypto = payload["crypto_underlying_paper"]
        crypto["qualification_authority"] = ""
        crypto["decision_authority"] = ""
        crypto["adaptive_policy_version"] = ""
        crypto["last_rows_summary"] = [{"symbol": "BTC"}, {"symbol": "ETH"}, {"symbol": "SOL"}]
        self.assertFalse(_current_quant_contract(payload))

    def test_legacy_numeric_gate_authority_is_rejected(self) -> None:
        payload = self._current_payload()
        payload["crypto_underlying_paper"]["legacy_numeric_gates_are_execution_authority"] = True
        self.assertFalse(_current_quant_contract(payload))

    def test_quant_service_uses_v17_status_contract_not_generic_health(self) -> None:
        quant = next(service for service in v17_services() if service.name == "quant")
        self.assertIn("/api/v17/trading/status", quant.health_url)
        self.assertEqual(quant.expected_service, V17_QUANT_SERVICE)


if __name__ == "__main__":
    unittest.main()
