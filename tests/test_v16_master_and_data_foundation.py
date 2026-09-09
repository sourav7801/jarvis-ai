from __future__ import annotations

import inspect
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agents import fyers_data_adapter as fyers
from omni.agent_registry import default_agent_specs
from omni.trading_intelligence.market_reasoning_v15 import AUTONOMOUS_MARKET_REASONING_V15
from workstation.jarvis_os_v16_bridge import V16BridgeHandler


ROOT = Path(__file__).resolve().parents[1]


class V16MasterSurfaceTests(unittest.TestCase):
    def test_v16_master_preserves_protected_parent_and_exposes_managed_surfaces(self):
        source = inspect.getsource(V16BridgeHandler)
        for marker in (
            "/api/v16/status",
            "/api/v16/capabilities",
            "/api/v16/files",
            "/api/v16/files/search",
            "/api/v16/files/text",
            "/api/v16/files/upload",
            "/api/v16/artifacts/create",
            "/api/v16/projects/create",
            "/api/v16/tools/execute",
            "/v16/files",
        ):
            self.assertIn(marker, source)
        self.assertIn("if not self.authorized()", source)
        for forbidden in ("place_order(", "submit_order(", "modify_order(", "cancel_order("):
            self.assertNotIn(forbidden, source)

    def test_files_ui_has_real_drag_drop_upload_search_and_preview(self):
        html = (ROOT / "workstation" / "jarvis_os_v3_assets" / "v16_files.html").read_text(encoding="utf-8")
        for marker in (
            "Drop files here",
            "/api/v16/files/upload",
            "/api/v16/files/search",
            "/api/v16/files/text",
            "content_base64",
            "dataTransfer.files",
            "ASK / PREVIEW",
            "__JARVIS_TOKEN__",
        ):
            self.assertIn(marker, html)

    def test_permanent_agent_boundary_unchanged(self):
        names = {spec.name for spec in default_agent_specs()}
        self.assertEqual(len(names), 29)
        self.assertIn("critic", names)


class V16FyersGovernanceTests(unittest.TestCase):
    def test_429_is_rate_limited_not_expired_token_guess(self):
        details = fyers._response_details({"s": "error", "code": 429, "message": "Bad request"})
        self.assertEqual(details["provider_state"], "RATE_LIMITED")
        self.assertEqual(details["provider_code"], 429)
        self.assertNotIn("expired", details["message"].lower())

    def test_provider_state_distinguishes_permission_and_credentials(self):
        permission = fyers._response_details({"s": "error", "code": -403, "message": "denied"})
        credentials = fyers._response_details({"s": "error", "code": -5, "message": "bad"})
        generic = fyers._response_details({"s": "error", "code": 400, "message": "Bad request"})
        self.assertEqual(permission["provider_state"], "PERMISSION_REQUIRED")
        self.assertEqual(credentials["provider_state"], "CREDENTIAL_MISMATCH")
        self.assertEqual(generic["provider_state"], "REQUEST_REJECTED")

    def test_verified_429_starts_shared_cooldown_without_second_provider_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(fyers, "_GOVERNOR_DIR", root), patch.object(fyers, "_GOVERNOR_STATE", root / "state.json"), patch.object(fyers, "_GOVERNOR_LOCK", root / "provider.lock"), patch.object(fyers, "_HISTORY_CACHE_DIR", root / "history_cache"), patch.object(fyers, "_MIN_REQUEST_INTERVAL_SECONDS", 0.0), patch.object(fyers, "_RATE_LIMIT_COOLDOWN_SECONDS", 3.0):
                calls = []
                first = fyers._governed_provider_call(lambda: calls.append(1) or {"s": "error", "code": 429, "message": "Bad request"})
                self.assertEqual(first.get("code"), 429)
                with self.assertRaises(fyers.FyersRateLimited):
                    fyers._governed_provider_call(lambda: calls.append(2) or {"s": "ok"})
                self.assertEqual(calls, [1])
                state = json.loads((root / "state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["last_provider_code"], 429)
                self.assertGreater(float(state["cooldown_until_epoch"]), time.time())


class V16NoDataReasoningTests(unittest.TestCase):
    def test_no_verified_evidence_suppresses_probabilities_and_hypotheses(self):
        result = AUTONOMOUS_MARKET_REASONING_V15.reason(
            {
                "symbol": "NIFTY",
                "profile": "5m_only",
                "candidate_side": "WAIT",
                "evidence": [
                    {
                        "timeframe": "5m",
                        "available": False,
                        "source": "FYERS",
                        "data_quality": "UNAVAILABLE",
                        "provider_state": "RATE_LIMITED",
                        "provider_code": 429,
                        "retry_after_seconds": 42,
                        "raw_bars": 0,
                        "complete_bars": 0,
                        "message": "rate limited",
                    }
                ],
            }
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["hypotheses"], [])
        self.assertIsNone(result["dominant_hypothesis"])
        belief = result["market_belief"]
        self.assertIsNone(belief["range_probability"])
        self.assertIsNone(belief["breakout_probability"])
        self.assertEqual(belief["uncertainty"], 1.0)
        self.assertEqual(result["provider_state"], "RATE_LIMITED")
        self.assertEqual(result["provider_code"], 429)
        self.assertTrue(result["hypotheses_suppressed_no_verified_evidence"])
        self.assertFalse(result["market_data_fabricated"])


if __name__ == "__main__":
    unittest.main()
