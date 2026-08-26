from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SpecialistWindowRenderingTests(unittest.TestCase):
    def test_command_endpoint_preserves_safe_specialist_payload(self):
        source = (ROOT / "workstation" / "jarvis_os_v3.py").read_text(encoding="utf-8")
        self.assertIn('"raw":\n                        safe(', source)
        self.assertIn('result.get(\n                                "raw"', source)

    def test_web_and_paper_windows_have_route_owned_feeds(self):
        markup = (ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="researchFeed"', markup)
        self.assertIn('id="paperFeed"', markup)

    def test_browser_routes_results_and_uses_safe_dom_text(self):
        source = (ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("renderSpecialistResult(\n            result", source)
        self.assertIn('feed: "researchFeed"', source)
        self.assertIn('feed: "paperFeed"', source)
        self.assertIn("body.textContent =", source)
        self.assertNotIn("body.innerHTML =", source)
        self.assertIn('link.rel = "noopener noreferrer"', source)

    def test_paper_window_has_live_portfolio_journal_and_telemetry(self):
        markup = (ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js").read_text(encoding="utf-8")
        server = (ROOT / "workstation" / "jarvis_os_v3.py").read_text(encoding="utf-8")
        for element in (
            "paperEquity", "paperPositions", "paperClosedTrades", "paperBlockers",
            "paperDailyPnl", "paperDrawdown", "paperEntryGate", "paperCorrelation",
        ):
            self.assertIn(f'id="{element}"', markup)
        self.assertIn('api("/api/paper-portfolio")', script)
        self.assertIn('parsed.path == "/api/paper-portfolio"', server)
        self.assertIn("refreshPaperPortfolio", script)
        self.assertIn("Exit policy: breakeven", script)
        self.assertIn("trailing_at_r", script)

    def test_spatial_depth_mode_is_explicit_optional_and_accessible(self):
        markup = (ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "workstation" / "jarvis_os_v3_assets" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="depthButton"', markup)
        self.assertIn('aria-pressed="true"', markup)
        self.assertIn('localStorage.getItem("jarvis-spatial-depth")', script)
        self.assertIn("prefers-reduced-motion: reduce", styles)
        self.assertIn("body.spatial-mode .jarvisWindow", styles)

    def test_company_os_has_route_owned_long_horizon_workspace(self):
        markup = (ROOT / "workstation" / "jarvis_os_v3_assets" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "workstation" / "jarvis_os_v3_assets" / "app.js").read_text(encoding="utf-8")
        server = (ROOT / "workstation" / "jarvis_os_v3.py").read_text(encoding="utf-8")
        for element in ("companyFeed", "companyWorkboard", "companyRoadmap", "companyResearchState"):
            self.assertIn(f'id="{element}"', markup)
        self.assertIn('api("/api/company-os")', script)
        self.assertIn('feed: "companyFeed"', script)
        self.assertIn('parsed.path == "/api/company-os"', server)


if __name__ == "__main__":
    unittest.main()
