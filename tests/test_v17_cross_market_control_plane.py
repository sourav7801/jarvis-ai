import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workstation import v17_autopilot_preferences as preferences
from workstation.fyers_live_bridge_service import (
    _subscription_quarantine_reason,
    subscribe_payload,
)
from workstation.v17_cross_market_control_plane import V17CrossMarketControlPlane


class _FakeRuntime:
    def __init__(self):
        self.running = {"INTRADAY": False, "SWING": False, "INVESTMENT": False}
        self.controls = []

    def status(self, workspace):
        running = bool(self.running.get(workspace, False))
        return {
            "success": True,
            "running": running,
            "state": "RUNNING" if running else "PAUSED",
            "session": {"entry_session": "RUNNING" if running else "PAUSED"},
        }

    def control(self, workspace, action):
        self.controls.append((workspace, action))
        self.running[workspace] = action == "start"
        return self.status(workspace)


class _FakeCryptoLane:
    def __init__(self):
        self.running = False
        self.starts = 0
        self.stops = 0

    def status(self):
        return {
            "success": True,
            "running": self.running,
            "state": "RUNNING" if self.running else "PAUSED",
            "scan_cycles": 0,
            "mcx_underlying_paper": {
                "success": True,
                "running": False,
                "state": "WAITING_FOR_MCX_SESSION",
                "session_open": False,
                "scan_cycles": 0,
            },
        }

    def start(self):
        self.running = True
        self.starts += 1
        return self.status()

    def stop_new_entries(self):
        self.running = False
        self.stops += 1
        return self.status()


class V17CrossMarketControlPlaneTests(unittest.TestCase):
    def test_armed_preference_is_durable_and_defaults_disarmed(self):
        self.assertFalse(preferences.DEFAULTS["armed"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefs.json"
            with mock.patch.object(preferences, "PREFERENCES_PATH", path):
                saved = preferences.save_preferences({"armed": True})
                self.assertTrue(saved["armed"])
                self.assertTrue(preferences.load_preferences()["armed"])
                saved = preferences.save_preferences({"armed": False})
                self.assertFalse(saved["armed"])

    def test_control_plane_auto_resumes_only_when_armed(self):
        runtime = _FakeRuntime()
        crypto = _FakeCryptoLane()
        plane = V17CrossMarketControlPlane()
        armed = {
            **preferences.DEFAULTS,
            "armed": True,
            "start_workspaces": ["INTRADAY", "SWING", "INVESTMENT"],
        }

        with mock.patch(
            "workstation.v17_cross_market_control_plane.crypto_paper_lane",
            crypto,
        ):
            status = plane.reconcile(runtime, preferences=armed, force=True)
            self.assertTrue(status["armed"])
            self.assertEqual(crypto.starts, 1)
            self.assertTrue(crypto.running)
            self.assertEqual(
                runtime.controls,
                [
                    ("INTRADAY", "start"),
                    ("SWING", "start"),
                    ("INVESTMENT", "start"),
                ],
            )

            plane.reconcile(runtime, preferences=armed, force=False)
            self.assertEqual(crypto.starts, 1)

            disarmed = {**armed, "armed": False}
            status = plane.reconcile(runtime, preferences=disarmed, force=True)
            self.assertFalse(status["armed"])
            self.assertEqual(crypto.stops, 1)
            self.assertTrue(all(not value for value in runtime.running.values()))

    def test_mcx_option_research_is_quarantined_before_websocket(self):
        symbol = "MCX:CRUDEOIL26SEP7900CE"
        self.assertEqual(
            _subscription_quarantine_reason(symbol),
            "MCX_OPTION_RESEARCH_ONLY",
        )
        with mock.patch(
            "workstation.fyers_live_bridge_service.fyers_live_stream.subscribe"
        ) as subscribe:
            payload = subscribe_payload(symbol)
        self.assertFalse(payload["success"])
        self.assertTrue(payload["quarantined"])
        self.assertEqual(payload["reason"], "MCX_OPTION_RESEARCH_ONLY")
        subscribe.assert_not_called()

    def test_option_research_no_longer_mutates_shared_stream(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "workstation" / "option_chart_data.py").read_text(
            encoding="utf-8"
        )
        section = text.split("def option_live(", 1)[1].split(
            "def attach_chart_directive", 1
        )[0]
        self.assertNotIn('"/api/subscribe"', section)
        self.assertIn("research_quote_fallback", section)
        self.assertIn("stream_subscription_attempted", section)

    def test_v17_http_and_ui_expose_control_plane_contract(self):
        root = Path(__file__).resolve().parents[1]
        http = (root / "workstation" / "v17_terminal_http.py").read_text(
            encoding="utf-8"
        )
        ui = (
            root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v17_runtime.js"
        ).read_text(encoding="utf-8")
        cross_ui = (
            root
            / "workstation"
            / "quant_terminal_v2_static"
            / "v17_crypto_paper_runtime.js"
        ).read_text(encoding="utf-8")

        self.assertIn('"version": "17.3"', http)
        self.assertIn('"control_plane": control_plane', http)
        self.assertIn('/v17_runtime.js?v=170300', http)
        self.assertIn('/v17_crypto_paper_runtime.js?v=170300', http)
        self.assertIn('id="v17ArmedState"', ui)
        self.assertIn("ARMED · AUTO-RESUME", ui)
        self.assertIn("V17.3 is DISARMED", cross_ui)


if __name__ == "__main__":
    unittest.main()
