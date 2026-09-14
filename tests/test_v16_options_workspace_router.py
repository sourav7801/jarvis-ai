from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class V16OptionsWorkspaceRouterTests(unittest.TestCase):
    def test_options_workspace_owns_a_dedicated_sidebar(self):
        js = (STATIC / "v16_workspace_router.js").read_text(encoding="utf-8")
        self.assertIn('id = "v16OptionsSidebar"', js)
        self.assertIn("OPTIONS AUTOPILOT", js)
        self.assertIn("setOptionsVisibility", js)
        self.assertIn("intel.prepend(optionsCard)", js)

    def test_options_sidebar_exposes_authenticated_session_controls(self):
        js = (STATIC / "v16_workspace_router.js").read_text(encoding="utf-8")
        for text in ("START SESSION", "PAUSE NEW ENTRIES", "RESUME", "STOP SCANNER"):
            self.assertIn(text, js)
        for action in ("start", "pause_new_entries", "resume", "stop_scanner"):
            self.assertIn(f'data-v16-option-control="{action}"', js)
        self.assertIn("/api/terminal/session", js)
        self.assertIn("X-Jarvis-Token", js)
        self.assertIn("csrf_token", js)

    def test_verified_non_index_option_chains_are_visible_but_not_overstated(self):
        js = (STATIC / "v16_workspace_router.js").read_text(encoding="utf-8")
        for symbol in ("CRUDEOIL", "GOLD", "SILVER", "NATURALGAS", "BTC", "ETH"):
            self.assertIn(symbol, js)
        self.assertIn("FYERS MCX OPTION CHAIN V3", js)
        self.assertIn("DERIBIT PUBLIC OPTIONS", js)
        self.assertIn("Canonical V16 automated option execution is not yet audited for MCX", js)
        self.assertIn("No separate crypto paper ledger is used in V16", js)

    def test_index_auto_paper_remains_canonical_and_live_locked(self):
        js = (STATIC / "v16_workspace_router.js").read_text(encoding="utf-8")
        self.assertIn("NIFTY / BANKNIFTY · AUTO PAPER", js)
        self.assertIn("canonical Paper Desk", js)
        self.assertIn("LIVE BROKER", js)
        self.assertIn("LOCKED", js)

    def test_v16_http_loads_router_and_retires_legacy_browser_poller(self):
        source = (ROOT / "workstation" / "v16_terminal_http.py").read_text(encoding="utf-8")
        self.assertIn("/v16_workspace_router.js", source)
        self.assertIn("paper_desk_runtime.js", source)
        self.assertIn("html.replace", source)
        self.assertIn("competing sidebar surface", source)


if __name__ == "__main__":
    unittest.main()
