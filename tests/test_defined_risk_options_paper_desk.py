import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workstation.defined_risk_options_paper_desk import DefinedRiskOptionsPaperDesk, select_debit_vertical
from workstation.options_chain_analytics import NormalizedOptionContract


def contract(symbol, strike, kind, bid, ask, delta, *, expiry, provider="FYERS"):
    return NormalizedOptionContract(
        symbol=symbol, underlying="NIFTY", expiry=expiry, strike=strike, option_type=kind,
        ltp=(bid + ask) / 2, bid=bid, ask=ask, open_interest=1000,
        change_in_oi=10, volume=500, iv=18, delta=delta, gamma=0.01,
        theta=-2, vega=4, provider=provider, provider_symbol="NSE:NIFTY50-INDEX",
    )


class DefinedRiskOptionsPaperDeskTests(unittest.TestCase):
    def setUp(self):
        self.expiry = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()

    def test_bull_call_uses_conservative_quotes_and_atomic_defined_risk_fill(self):
        rows = [
            contract("NIFTY-A-CE", 24000, "CE", 198, 200, .50, expiry=self.expiry),
            contract("NIFTY-B-CE", 24200, "CE", 78, 80, .25, expiry=self.expiry),
        ]
        candidate = select_debit_vertical(
            rows, direction="LONG", expiry=self.expiry, contract_multiplier=25,
            currency="INR", evidence_timestamp="2026-08-26T06:00:00+00:00", verified=True, stale=False,
        )
        self.assertEqual(candidate.net_debit, 122)
        self.assertEqual(candidate.max_loss_per_lot, 3050)
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "options.sqlite3", max_risk_percent=1)
            opened = desk.open_spread(candidate, equity=1_000_000)
            self.assertTrue(opened["success"])
            self.assertEqual(opened["quantity"], 3)
            self.assertEqual(opened["legs"][1]["side"], "SELL_TO_HEDGE")
            self.assertFalse(opened["live_execution"])
            self.assertEqual(desk.snapshot()["open_count"], 1)

    def test_stale_incomplete_or_cross_provider_chain_fails_closed(self):
        rows = [
            contract("A", 24000, "CE", 198, 200, .50, expiry=self.expiry),
            contract("B", 24200, "CE", 78, 80, .25, expiry=self.expiry, provider="OTHER"),
        ]
        with self.assertRaises(ValueError):
            select_debit_vertical(rows, direction="LONG", expiry=self.expiry, contract_multiplier=25, currency="INR", evidence_timestamp="x", verified=True, stale=False)
        with self.assertRaises(ValueError):
            select_debit_vertical(rows, direction="LONG", expiry=self.expiry, contract_multiplier=25, currency="INR", evidence_timestamp="x", verified=True, stale=True)

    def test_risk_budget_and_idempotency_are_enforced(self):
        rows = [
            contract("A", 24000, "CE", 198, 200, .50, expiry=self.expiry),
            contract("B", 24200, "CE", 78, 80, .25, expiry=self.expiry),
        ]
        candidate = select_debit_vertical(rows, direction="LONG", expiry=self.expiry, contract_multiplier=25, currency="INR", evidence_timestamp="x", verified=True, stale=False)
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "options.sqlite3", max_risk_percent=.1)
            self.assertEqual(desk.open_spread(candidate, equity=100_000)["status"], "RISK_BUDGET_TOO_SMALL")
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "other.sqlite3", max_risk_percent=2)
            self.assertTrue(desk.open_spread(candidate, equity=1_000_000)["success"])
            self.assertEqual(desk.open_spread(candidate, equity=1_000_000)["status"], "ALREADY_RECORDED")

    def test_verified_marks_value_and_close_spread_at_bounded_profit(self):
        rows = [
            contract("A", 24000, "CE", 198, 200, .50, expiry=self.expiry),
            contract("B", 24200, "CE", 78, 80, .25, expiry=self.expiry),
        ]
        candidate = select_debit_vertical(
            rows, direction="LONG", expiry=self.expiry, contract_multiplier=25,
            currency="INR", evidence_timestamp="x", verified=True, stale=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "options.sqlite3", max_risk_percent=1)
            desk.open_spread(candidate, equity=1_000_000)
            marked = desk.mark_spread(
                candidate.candidate_id, long_bid=150, short_ask=20,
                certificate={"verified": True, "stale": False, "received_at": datetime.now(timezone.utc).isoformat()},
            )
            self.assertEqual(marked["status"], "OPEN")
            self.assertGreater(marked["pnl"], 0)
            closed = desk.mark_spread(
                candidate.candidate_id, long_bid=191, short_ask=10,
                certificate={"verified": True, "stale": False, "received_at": datetime.now(timezone.utc).isoformat()},
            )
            self.assertEqual(closed["status"], "CLOSED")
            self.assertEqual(closed["exit_reason"], "PROFIT_TARGET")
            snapshot = desk.snapshot()
            self.assertEqual(snapshot["open_count"], 0)
            self.assertGreater(snapshot["realized_pnl"], 0)

    def test_stale_mark_cannot_close_or_mutate_an_open_spread(self):
        rows = [
            contract("A", 24000, "CE", 198, 200, .50, expiry=self.expiry),
            contract("B", 24200, "CE", 78, 80, .25, expiry=self.expiry),
        ]
        candidate = select_debit_vertical(
            rows, direction="LONG", expiry=self.expiry, contract_multiplier=25,
            currency="INR", evidence_timestamp="x", verified=True, stale=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "options.sqlite3", max_risk_percent=1)
            desk.open_spread(candidate, equity=1_000_000)
            with self.assertRaises(ValueError):
                desk.mark_spread(
                    candidate.candidate_id, long_bid=0, short_ask=0,
                    certificate={
                        "verified": True, "stale": False,
                        "received_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                    },
                )
            self.assertEqual(desk.snapshot()["open_count"], 1)

    def test_exact_expiry_uses_verified_official_settlement(self):
        expiry = datetime.now(timezone.utc).date().isoformat()
        rows = [
            contract("A", 24000, "CE", 198, 200, .50, expiry=expiry),
            contract("B", 24200, "CE", 78, 80, .25, expiry=expiry),
        ]
        candidate = select_debit_vertical(
            rows, direction="LONG", expiry=expiry, contract_multiplier=25,
            currency="INR", evidence_timestamp="x", verified=True, stale=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "options.sqlite3", max_risk_percent=1)
            desk.open_spread(candidate, equity=1_000_000)
            settled = desk.settle_expired(
                candidate.candidate_id, settlement_price=24300,
                certificate={
                    "verified": True, "stale": False, "official_settlement": True,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.assertEqual(settled["status"], "CLOSED")
            self.assertEqual(settled["exit_reason"], "EXPIRY_SETTLEMENT")
            self.assertGreater(settled["pnl"], 0)


if __name__ == "__main__":
    unittest.main()
