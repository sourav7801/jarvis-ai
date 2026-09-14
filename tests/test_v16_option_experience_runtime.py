from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_option_experience_runtime.js"
HTTP = ROOT / "workstation" / "v16_terminal_http.py"


class V16OptionExperienceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = RUNTIME.read_text(encoding="utf-8")
        cls.http = HTTP.read_text(encoding="utf-8")

    def test_runtime_is_loaded_after_authoritative_options_router(self):
        self.assertIn("/v16_option_experience_runtime.js", self.http)
        router = self.http.index('<script defer src=\\"/v16_workspace_router.js\\"></script>')
        experience = self.http.index('<script defer src=\\"/v16_option_experience_runtime.js\\"></script>')
        self.assertLess(router, experience)

    def test_capital_uses_canonical_workspace_state_and_all_three_mandates(self):
        self.assertIn("state?.capital", self.js)
        self.assertIn("state?.accounts", self.js)
        self.assertIn('CAPITAL_WORKSPACES = ["INTRADAY", "SWING", "INVESTMENT"]', self.js)
        self.assertIn("TOTAL PAPER CAPITAL", self.js)
        self.assertIn("OPTIONS · SHARED MANDATE", self.js)
        self.assertIn("not a fourth capital pool", self.js)
        self.assertIn("committed_capital", self.js)
        self.assertIn("open_risk", self.js)

    def test_manual_chain_row_is_chart_first_but_remains_view_only(self):
        self.assertIn('#v16OptionRows tr[data-v16-contract]', self.js)
        self.assertIn("v16OpenOptionChart", self.js)
        self.assertIn("open.click()", self.js)
        self.assertIn("MANUAL VIEW · NO EXECUTION AUTHORITY", self.js)
        self.assertIn("v16BackToOptionChain", self.js)

    def test_autonomous_focus_uses_engine_selected_exact_candidate(self):
        self.assertIn("scan_decisions?.autonomous_options", self.js)
        self.assertIn("candidate_contract", self.js)
        self.assertIn('"ACTIONABLE"', self.js)
        self.assertIn('direction === "LONG"', self.js)
        self.assertIn('optionType === "CALL"', self.js)
        self.assertIn('direction === "SHORT"', self.js)
        self.assertIn('optionType === "PUT"', self.js)
        self.assertIn("AUTONOMOUS CANDIDATE · ENGINE SELECTED", self.js)

    def test_experience_layer_is_observer_only_and_never_places_orders(self):
        self.assertNotIn("setInterval(", self.js)
        self.assertNotIn("/api/v16/trading/option-order", self.js)
        self.assertNotIn('method: "POST"', self.js)
        self.assertIn("response.clone().json()", self.js)
        self.assertIn("paper_only", self.js)
        self.assertIn("live_execution", self.js)
        self.assertIn("automatic_broker_order", self.js)


if __name__ == "__main__":
    unittest.main()
