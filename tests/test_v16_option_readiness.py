from contextlib import nullcontext
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from workstation.v16_option_readiness import option_readiness


ROOT = Path(__file__).resolve().parents[1]
HTTP = ROOT / "workstation" / "v16_terminal_http.py"
RUNTIME = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_option_readiness_runtime.js"
SYMBOL = "NSE:NIFTY26SEP25000CE"


class FakeConnection:
    def __init__(self):
        self.commands = []

    def execute(self, sql, *args):
        self.commands.append(sql)
        return self


class FakeDesk:
    def __init__(self):
        self._lock = threading.RLock()
        self.connection = FakeConnection()

    def _connection(self):
        return nullcontext(self.connection)


class FakeRuntime:
    def __init__(self):
        self.desk = FakeDesk()

    def reconcile(self):
        return {"success": True, "issue_count": 0}


FRESH_CERTIFICATE = {
    "success": True,
    "symbol": SYMBOL,
    "mark": 100.0,
    "bid": 99.8,
    "ask": 100.2,
    "age_seconds": 1.4,
    "verified": True,
    "stale": False,
    "eligible_for_entry": True,
    "source": "FYERS_NSE",
    "reason": None,
}

SPEC = {
    "symbol": SYMBOL,
    "provider_symbol": SYMBOL,
    "instrument_type": "OPTION",
    "asset_class": "OPTION",
    "verified": True,
    "quantity_step": 1.0,
    "contract_multiplier": 75.0,
    "tick_size": 0.05,
    "strike": 25000.0,
    "expiry": "2026-09-24",
    "option_type": "CE",
}


def ticket(lots="2"):
    return {
        "execution_mode": "PAPER",
        "workspace": "INTRADAY",
        "symbol": SYMBOL,
        "option_type": "CE",
        "lots": lots,
        "stop": "90",
        "target": "125",
        "underlying": "NIFTY",
        "expiry": "2026-09-24",
    }


class V16OptionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.session = {"state": "RUNNING", "generation": 7, "allocation": 0.5}

    def plan(self, admitted=2.0):
        return {
            "success": True,
            "sizing": {
                "quantity": admitted,
                "capital_allocated": admitted * 7515.0,
                "capital_at_risk": admitted * 800.0,
                "risk_budget": 2500.0,
                "available_capital_before": 100000.0,
                "limiting_constraint": "Risk per trade including costs",
                "quantity_caps": {"Requested quantity": float(ticket()["lots"])},
                "quantity_step": 1.0,
                "contract_multiplier": 75.0,
                "cost_status": "CONFIGURABLE_CONSERVATIVE_PAPER_ESTIMATE",
            },
        }

    @patch("workstation.v16_option_readiness.option_instrument_spec", return_value=SPEC)
    @patch("workstation.v16_option_readiness._certificate", return_value=FRESH_CERTIFICATE)
    @patch("workstation.v16_option_readiness.accounts.session")
    @patch("workstation.v16_option_readiness.accounts.plan_admission")
    def test_ready_preview_reuses_canonical_admission_and_rolls_back_preview_writes(
        self, plan_admission, session, _certificate, _instrument
    ):
        session.return_value = self.session
        plan_admission.return_value = ({}, self.plan(admitted=2.0))

        result = option_readiness(self.runtime, ticket("2"))

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_mode"], "PAPER")
        self.assertTrue(result["paper_only"])
        self.assertFalse(result["live_execution"])
        self.assertEqual(result["quote"]["age_seconds"], 1.4)
        self.assertEqual(result["risk"]["recommended_lots"], 2)
        self.assertEqual(result["risk"]["risk_budget"], 2500.0)
        self.assertEqual(
            self.runtime.desk.connection.commands,
            [
                "SAVEPOINT v16_option_readiness",
                "ROLLBACK TO v16_option_readiness",
                "RELEASE v16_option_readiness",
            ],
        )
        request = plan_admission.call_args.args[2]
        self.assertEqual(request["metadata"]["session_generation"], 7)
        self.assertIs(request["metadata"]["entry_certificate"], FRESH_CERTIFICATE)
        self.assertEqual(request["risk_multiplier"], 0.25)

    @patch("workstation.v16_option_readiness.option_instrument_spec", return_value=SPEC)
    @patch("workstation.v16_option_readiness._certificate", return_value=FRESH_CERTIFICATE)
    @patch("workstation.v16_option_readiness.accounts.session")
    @patch("workstation.v16_option_readiness.accounts.plan_admission")
    def test_requested_lots_above_canonical_size_are_blocked_until_user_accepts_safe_size(
        self, plan_admission, session, _certificate, _instrument
    ):
        session.return_value = self.session
        reduced = self.plan(admitted=2.0)
        reduced["sizing"]["quantity_caps"]["Requested quantity"] = 5.0
        plan_admission.return_value = ({}, reduced)

        result = option_readiness(self.runtime, ticket("5"))

        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "REQUEST_EXCEEDS_RISK_ADMISSION")
        self.assertEqual(result["risk"]["requested_lots"], 5)
        self.assertEqual(result["risk"]["recommended_lots"], 2)

    @patch("workstation.v16_option_readiness.accounts.plan_admission")
    @patch("workstation.v16_option_readiness._certificate")
    @patch("workstation.v16_option_readiness.accounts.session")
    def test_stale_exact_quote_blocks_without_running_position_sizing(self, session, certificate, plan_admission):
        session.return_value = self.session
        certificate.return_value = {
            **FRESH_CERTIFICATE,
            "eligible_for_entry": False,
            "verified": False,
            "stale": True,
            "age_seconds": 45.0,
            "reason": "STALE_MARK",
        }

        result = option_readiness(self.runtime, ticket("2"))

        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "STALE_MARK")
        self.assertEqual(result["quote"]["age_seconds"], 45.0)
        self.assertEqual(result["quote"]["max_age_seconds"], 30.0)
        plan_admission.assert_not_called()

    def test_live_mode_is_rejected_before_market_or_desk_execution(self):
        payload = ticket("1")
        payload["execution_mode"] = "LIVE"
        result = option_readiness(self.runtime, payload)
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "LIVE_EXECUTION_LOCKED")
        self.assertFalse(result["live_execution"])


class V16OptionReadinessWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = HTTP.read_text(encoding="utf-8")
        cls.js = RUNTIME.read_text(encoding="utf-8")

    def test_http_loads_readiness_after_chart_first_option_experience(self):
        self.assertIn("OPTION_READINESS_PATH", self.http)
        self.assertIn("/api/v16/trading/option-readiness", self.http)
        self.assertIn("/v16_option_readiness_runtime.js", self.http)
        self.assertLess(
            self.http.index("/v16_option_experience_runtime.js"),
            self.http.index("/v16_option_readiness_runtime.js"),
        )

    def test_browser_gate_fails_closed_and_never_places_an_order(self):
        self.assertIn('/api/v16/trading/option-readiness', self.js)
        self.assertIn('method: "GET"', self.js)
        self.assertIn("execution_ready", self.js)
        self.assertIn("recommended_lots", self.js)
        self.assertIn("SERVER_READINESS_UNAVAILABLE", self.js)
        self.assertIn("stopImmediatePropagation", self.js)
        self.assertIn("MutationObserver", self.js)
        self.assertNotIn("/api/v16/trading/option-order", self.js)
        self.assertNotIn('method: "POST"', self.js)


if __name__ == "__main__":
    unittest.main()
