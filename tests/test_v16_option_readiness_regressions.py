from contextlib import nullcontext
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from workstation.v16_option_readiness import option_readiness


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_JS = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_option_readiness_runtime.js"
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


class NoIORuntime:
    def __init__(self):
        self.desk = object()

    def reconcile(self):
        raise AssertionError("deterministic ticket blockers must not touch the ledger")


FRESH_CERTIFICATE = {
    "success": True,
    "symbol": SYMBOL,
    "mark": 100.0,
    "bid": 99.8,
    "ask": 100.2,
    "age_seconds": 1.0,
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


def ticket(**overrides):
    payload = {
        "execution_mode": "PAPER",
        "workspace": "INTRADAY",
        "symbol": SYMBOL,
        "option_type": "CE",
        "lots": "1",
        "stop": "90",
        "target": "125",
        "underlying": "NIFTY",
        "expiry": "2026-09-24",
    }
    payload.update(overrides)
    return payload


class V16OptionReadinessRegressionTests(unittest.TestCase):
    def test_invalid_lot_values_fail_before_ledger_session_or_quote_io(self):
        invalid_values = (True, 0, -1, 1.5, "1.5", "abc", 101, float("nan"), float("inf"))
        for lots in invalid_values:
            with self.subTest(lots=lots):
                with patch("workstation.v16_option_readiness._certificate") as certificate, patch(
                    "workstation.v16_option_readiness.accounts.session"
                ) as session:
                    result = option_readiness(NoIORuntime(), ticket(lots=lots))
                self.assertFalse(result["execution_ready"])
                self.assertEqual(result["reason"], "INVALID_QUANTITY")
                certificate.assert_not_called()
                session.assert_not_called()

    def test_incomplete_risk_ticket_fails_before_provider_io(self):
        with patch("workstation.v16_option_readiness._certificate") as certificate, patch(
            "workstation.v16_option_readiness.accounts.session"
        ) as session:
            result = option_readiness(NoIORuntime(), ticket(stop="", target=""))
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "MANUAL_RISK_LEVELS_REQUIRED")
        certificate.assert_not_called()
        session.assert_not_called()

    @patch("workstation.v16_option_readiness.option_instrument_spec", return_value=SPEC)
    @patch("workstation.v16_option_readiness._certificate", return_value=FRESH_CERTIFICATE)
    @patch("workstation.v16_option_readiness.accounts.session")
    @patch("workstation.v16_option_readiness.accounts.plan_admission")
    def test_omitted_lots_matches_execution_default_of_one(
        self, plan_admission, session, _certificate, _instrument
    ):
        runtime = FakeRuntime()
        session.return_value = {"state": "RUNNING", "generation": 11, "allocation": 0.5}
        plan_admission.return_value = (
            {},
            {
                "success": True,
                "sizing": {
                    "quantity": 1.0,
                    "capital_allocated": 7515.0,
                    "capital_at_risk": 800.0,
                    "risk_budget": 2500.0,
                    "available_capital_before": 100000.0,
                    "limiting_constraint": "Risk per trade including costs",
                    "quantity_caps": {"Requested quantity": 1.0},
                    "quantity_step": 1.0,
                    "contract_multiplier": 75.0,
                    "cost_status": "CONFIGURABLE_CONSERVATIVE_PAPER_ESTIMATE",
                },
            },
        )
        payload = ticket()
        payload.pop("lots")

        result = option_readiness(runtime, payload)

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["risk"]["requested_lots"], 1)
        request = plan_admission.call_args.args[2]
        self.assertEqual(request["quantity"], 1.0)
        self.assertEqual(request["metadata"]["requested_lots"], 1)

    @patch("workstation.v16_option_readiness.option_instrument_spec")
    @patch("workstation.v16_option_readiness.accounts.plan_admission")
    @patch("workstation.v16_option_readiness._certificate")
    @patch("workstation.v16_option_readiness.accounts.session")
    def test_eligible_certificate_without_positive_entry_is_precisely_blocked(
        self, session, certificate, plan_admission, instrument_spec
    ):
        runtime = FakeRuntime()
        session.return_value = {"state": "RUNNING", "generation": 12, "allocation": 0.5}
        certificate.return_value = {
            **FRESH_CERTIFICATE,
            "mark": None,
            "ask": None,
            "eligible_for_entry": True,
        }

        result = option_readiness(runtime, ticket())

        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "INVALID_ENTRY")
        plan_admission.assert_not_called()
        instrument_spec.assert_not_called()

    def test_invalid_static_stop_target_geometry_fails_without_quote_io(self):
        with patch("workstation.v16_option_readiness._certificate") as certificate:
            result = option_readiness(NoIORuntime(), ticket(stop="120", target="110"))
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["reason"], "INVALID_RISK_LEVELS")
        certificate.assert_not_called()


class V16ReadinessBrowserCancellationRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RUNTIME_JS.read_text(encoding="utf-8")

    def test_each_refresh_owns_its_abort_controller(self):
        self.assertIn("const requestController = new AbortController();", self.source)
        self.assertIn("controller = requestController;", self.source)
        self.assertIn("setTimeout(() => requestController.abort(), 5000)", self.source)
        self.assertIn("signal: requestController.signal", self.source)
        self.assertIn("if (controller === requestController) controller = null;", self.source)
        self.assertNotIn("setTimeout(() => controller?.abort(), 5000)", self.source)


if __name__ == "__main__":
    unittest.main()
