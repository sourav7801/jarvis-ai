import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workstation.defined_risk_options_paper_desk import DefinedRiskOptionsPaperDesk
from workstation.options_chain_analytics import NormalizedOptionContract
from workstation.options_paper_autonomy import OptionsPaperAutonomyEngine


def row(symbol, strike, delta, expiry):
    return NormalizedOptionContract(
        symbol=symbol, underlying="NIFTY", expiry=expiry, strike=strike, option_type="CE",
        ltp=100, bid=99, ask=101, open_interest=1000, change_in_oi=20,
        volume=500, iv=18, delta=delta, gamma=.01, theta=-2, vega=3,
        provider="FYERS", provider_symbol="NSE:NIFTY50-INDEX",
    )


class OptionsPaperAutonomyTests(unittest.TestCase):
    def setUp(self):
        self.expiry = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()
        self.certificate = {
            "verified": True, "stale": False, "session_open": True,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        self.signal = {"action": "BUY", "score": 90, "contradictions": [], "paper_only": True, "live_execution": False}

    def test_qualified_snapshot_opens_atomic_paper_spread(self):
        with tempfile.TemporaryDirectory() as directory:
            desk = DefinedRiskOptionsPaperDesk(Path(directory) / "desk.sqlite3", max_risk_percent=1)
            engine = OptionsPaperAutonomyEngine(desk)
            result = engine.process_chain(
                [row("A", 24000, .5, self.expiry), row("B", 24200, .25, self.expiry)],
                signal=self.signal, expiry=self.expiry, contract_multiplier=25,
                currency="INR", certificate=self.certificate, equity=1_000_000,
            )
            self.assertTrue(result["success"])
            self.assertEqual(engine.status()["opened"], 1)
            self.assertFalse(result["live_execution"])

    def test_wait_closed_stale_and_contradictory_inputs_record_blockers(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = OptionsPaperAutonomyEngine(DefinedRiskOptionsPaperDesk(Path(directory) / "desk.sqlite3"))
            contracts = [row("A", 24000, .5, self.expiry), row("B", 24200, .25, self.expiry)]
            wait = engine.process_chain(contracts, signal={**self.signal, "action": "WAIT"}, expiry=self.expiry, contract_multiplier=25, currency="INR", certificate=self.certificate, equity=1_000_000)
            closed = engine.process_chain(contracts, signal=self.signal, expiry=self.expiry, contract_multiplier=25, currency="INR", certificate={**self.certificate, "session_open": False}, equity=1_000_000)
            stale = engine.process_chain(contracts, signal=self.signal, expiry=self.expiry, contract_multiplier=25, currency="INR", certificate={**self.certificate, "stale": True}, equity=1_000_000)
            conflict = engine.process_chain(contracts, signal={**self.signal, "contradictions": ["trend conflict"]}, expiry=self.expiry, contract_multiplier=25, currency="INR", certificate=self.certificate, equity=1_000_000)
            self.assertEqual({wait["reason"], closed["reason"], stale["reason"], conflict["reason"]}, {"UNDERLYING_SIGNAL_WAIT", "SESSION_CLOSED", "CHAIN_UNVERIFIED_OR_STALE", "UNDERLYING_SIGNAL_CONTRADICTION"})
            self.assertEqual(engine.status()["processed"], 4)


if __name__ == "__main__":
    unittest.main()
