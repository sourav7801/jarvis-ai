from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


class V16OptionChartRaceTests(unittest.TestCase):
    def test_latest_contract_selection_owns_chart_render(self):
        js = (STATIC / "option_chart_runtime.js").read_text(encoding="utf-8")
        self.assertIn("optionLoadVersion", js)
        self.assertIn("sameOptionRequest", js)
        self.assertIn("AbortController", js)
        self.assertIn("optionAbortController", js)
        self.assertIn('error?.name === "AbortError"', js)
        self.assertIn("!sameOptionRequest(slot, spec, version)", js)

    def test_option_header_changes_immediately_before_async_candles_return(self):
        js = (STATIC / "option_chart_runtime.js").read_text(encoding="utf-8")
        marker = "OPTION SELECTED"
        load_call = "void loadSlot(index)"
        self.assertIn(marker, js)
        self.assertIn(load_call, js)
        self.assertLess(js.index(marker), js.index(load_call))

    def test_old_deribit_or_rest_updates_cannot_repaint_new_contract(self):
        js = (STATIC / "option_chart_runtime.js").read_text(encoding="utf-8")
        self.assertIn("connectDeribitOptionSocket(slot, spec, version)", js)
        self.assertIn("pollOptionLive(slot, spec, version)", js)
        self.assertIn('String(slot.optionChart.instrument_name || "")', js)
        self.assertIn('String(spec?.instrument_name || "")', js)


if __name__ == "__main__":
    unittest.main()
