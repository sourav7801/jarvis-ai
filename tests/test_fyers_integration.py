import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import pandas as pd
import agents.fyers_auth_manager as fyers_auth_manager

from agents.fyers_auth_manager import (
    FyersSettings,
    create_client,
    extract_auth_code,
    interactive_login_settings,
    load_token,
    save_token,
    websocket_access_token,
)
from agents.fyers_data_adapter import (
    get_intraday_data,
    get_quote,
    normalize_symbol,
)
from agents.fyers_live_stream import FyersLiveStream
from workstation.market_runtime import MarketRuntime


class FakeHistoryClient:
    def __init__(self):
        self.requests = []

    def history(self, data):
        self.requests.append(dict(data))
        base = 1_700_000_000
        candles = [
            [base + index * 300, 100 + index, 102 + index, 99 + index, 101 + index, 1000]
            for index in range(40)
        ]
        return {"s": "ok", "candles": candles}

    def quotes(self, data):
        return {
            "s": "ok",
            "d": [
                {
                    "n": data["symbols"],
                    "v": {
                        "lp": 24500.5,
                        "ch": 100.0,
                        "chp": 0.41,
                        "open_price": 24400.0,
                        "high_price": 24520.0,
                        "low_price": 24350.0,
                        "prev_close_price": 24400.5,
                        "volume": 12345,
                        "bid": 24500.0,
                        "ask": 24501.0,
                        "tt": 1_700_000_000,
                    },
                }
            ],
        }


class FakeSdkModel:
    class FyersModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def get_profile(self):
            return {"s": "ok", "data": {"name": "Test User"}}


class FyersAuthenticationTests(unittest.TestCase):
    def settings(self, directory):
        return FyersSettings(
            app_id="TESTAPP-100",
            secret_id="secret",
            redirect_uri="http://127.0.0.1:8765/callback",
            token_file=Path(directory) / "fyers.json",
        )

    def test_extract_auth_code_accepts_code_or_redirect_url(self):
        self.assertEqual(extract_auth_code("abc123"), "abc123")
        self.assertEqual(
            extract_auth_code(
                "http://127.0.0.1:8765/callback?s=ok&auth_code=xyz789"
            ),
            "xyz789",
        )

    def test_token_round_trip_excludes_app_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(directory)
            save_token(
                {"access_token": "token-value", "refresh_token": "refresh"},
                settings,
            )
            payload = load_token(settings)
            self.assertEqual(payload["access_token"], "token-value")
            self.assertNotIn("secret_id", payload)
            self.assertNotIn("secret", settings.token_file.read_text(encoding="utf-8"))

    def test_client_and_websocket_token_use_saved_token(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(directory)
            save_token({"access_token": "token-value"}, settings)
            with patch("agents.fyers_auth_manager._sdk_model", return_value=FakeSdkModel):
                client = create_client(settings, validate_profile=True)
            self.assertEqual(client.kwargs["client_id"], "TESTAPP-100")
            self.assertEqual(
                websocket_access_token(settings), "TESTAPP-100:token-value"
            )

    def test_app_id_is_recovered_from_saved_token(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(directory)
            save_token({"access_token": "token-value"}, settings)
            with patch.dict(
                os.environ,
                {
                    "FYERS_APP_ID": "",
                    "JARVIS_FYERS_TOKEN_FILE": str(settings.token_file),
                },
            ):
                recovered = FyersSettings.from_env()
            self.assertEqual(recovered.app_id, "TESTAPP-100")

    def test_login_prompts_for_missing_secret_without_saving_it(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = FyersSettings(
                app_id="TESTAPP-100",
                secret_id="",
                redirect_uri="http://127.0.0.1:8765/callback",
                token_file=Path(directory) / "fyers.json",
            )
            prompts = []
            completed = interactive_login_settings(
                settings,
                input_fn=lambda _prompt: self.fail("App ID should be recovered"),
                secret_fn=lambda prompt: prompts.append(prompt) or "temporary-secret",
            )

            self.assertEqual(completed.secret_id, "temporary-secret")
            self.assertEqual(len(prompts), 1)
            self.assertFalse(settings.token_file.exists())

    def test_cancelled_login_exits_without_traceback(self):
        with patch.object(fyers_auth_manager, "login", side_effect=KeyboardInterrupt):
            self.assertEqual(fyers_auth_manager.main(["login"]), 130)


class FyersMarketDataTests(unittest.TestCase):
    def test_symbol_aliases_and_full_symbols(self):
        self.assertEqual(normalize_symbol("NIFTY"), "NSE:NIFTY50-INDEX")
        self.assertEqual(normalize_symbol("nse:sbin-eq"), "NSE:SBIN-EQ")

    def test_history_is_normalized_for_trading_core(self):
        client = FakeHistoryClient()
        result = get_intraday_data("NIFTY", timeframe="5m", bars=30, client=client)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "FYERS")
        self.assertEqual(result["bars"], 30)
        self.assertEqual(
            list(result["data"].columns),
            ["Open", "High", "Low", "Close", "Volume"],
        )
        self.assertIsNotNone(result["data"].index.tz)
        self.assertEqual(client.requests[0]["resolution"], "5")

    def test_large_daily_history_is_chunked(self):
        client = FakeHistoryClient()
        result = get_intraday_data("NIFTY", timeframe="1d", bars=500, client=client)
        self.assertTrue(result["success"])
        self.assertGreater(len(client.requests), 1)
        self.assertEqual(client.requests[0]["resolution"], "D")

    def test_quote_is_normalized(self):
        result = get_quote("NIFTY", client=FakeHistoryClient())
        self.assertTrue(result["success"])
        self.assertEqual(result["ltp"], 24500.5)
        self.assertEqual(result["provider_symbol"], "NSE:NIFTY50-INDEX")

    def test_market_data_agent_prefers_fyers(self):
        from agents.market_data_agent import MarketDataAgent

        frame = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [102.0],
                "Low": [99.0],
                "Close": [101.0],
                "Volume": [1000.0],
            },
            index=pd.DatetimeIndex(["2026-08-14"], name="Timestamp"),
        )
        provider_result = {
            "success": True,
            "source": "FYERS",
            "symbol": "NIFTY",
            "provider_symbol": "NSE:NIFTY50-INDEX",
            "timeframe": "1d",
            "bars": 1,
            "data": frame,
        }
        with patch.dict(os.environ, {"JARVIS_MARKET_DATA_PROVIDER": "AUTO"}):
            with patch(
                "workstation.fyers_isolated_history_bridge.get_intraday_data_isolated_frame",
                return_value=provider_result,
            ):
                result = MarketDataAgent().get_market_data("NIFTY", bars=1)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "FYERS")
        self.assertIn("close", result["data"].columns)


class FakeSocket:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.background_flag = False
        self.subscriptions = []
        self.closed = False

    def connect(self):
        self.kwargs["on_connect"]()

    def subscribe(self, symbols, data_type):
        self.subscriptions.append((symbols, data_type))

    def unsubscribe(self, symbols, data_type):
        return None

    def close_connection(self):
        self.closed = True


class FyersLiveStreamTests(unittest.TestCase):
    def test_data_socket_updates_snapshot(self):
        stream = FyersLiveStream()
        created = []

        def factory(**kwargs):
            socket = FakeSocket(**kwargs)
            created.append(socket)
            return socket

        with patch(
            "agents.fyers_live_stream.websocket_access_token",
            return_value="TESTAPP-100:token",
        ):
            stream.start(["NIFTY"], socket_factory=factory)
        deadline = time.monotonic() + 1.0
        while not created[0].subscriptions and time.monotonic() < deadline:
            time.sleep(0.01)
        created[0].kwargs["on_message"](
            {
                "symbol": "NSE:NIFTY50-INDEX",
                "ltp": 24500.5,
                "open_price": 24400.0,
                "high_price": 24520.0,
                "low_price": 24350.0,
            }
        )
        snapshot = stream.snapshot("NIFTY")
        self.assertEqual(snapshot["source"], "FYERS")
        self.assertEqual(snapshot["ltp"], 24500.5)
        self.assertEqual(created[0].subscriptions[0][1], "SymbolUpdate")
        self.assertFalse(created[0].kwargs["reconnect"])
        self.assertTrue(created[0].background_flag)
        stream.stop()
        self.assertTrue(created[0].closed)

    def test_integration_exposes_no_order_api(self):
        import agents.fyers_auth_manager as auth
        import agents.fyers_data_adapter as data

        for forbidden in ("place_order", "modify_order", "cancel_order"):
            self.assertFalse(hasattr(auth, forbidden))
            self.assertFalse(hasattr(data, forbidden))


class FakeRuntimeStream:
    def __init__(self):
        self.started_with = None
        self.stopped = False

    def start(self, symbols, lite_mode=False):
        self.started_with = (tuple(symbols), lite_mode)
        return self.status()

    def stop(self):
        self.stopped = True

    def status(self):
        return {
            "provider": "FYERS",
            "running": not self.stopped,
            "connected": not self.stopped,
            "symbols": list(self.started_with[0]) if self.started_with else [],
            "snapshots": 0,
            "error": None,
            "data_only": True,
        }

    def snapshot(self, _symbol):
        return None


class WorkstationMarketRuntimeTests(unittest.TestCase):
    def test_runtime_owns_stream_and_seeds_dashboard_quotes(self):
        stream = FakeRuntimeStream()

        def quote(symbol):
            return {
                "success": True,
                "source": "FYERS",
                "symbol": symbol,
                "ltp": 100.0,
                "change": 1.0,
                "change_percent": 1.0,
            }

        runtime = MarketRuntime(
            enabled=True,
            provider="AUTO",
            symbols=("NIFTY", "BANKNIFTY"),
            stream_loader=lambda: stream,
            configured_check=lambda: True,
            quote_loader=quote,
        )
        status = runtime.start()
        state = runtime.public_state()
        self.assertTrue(status["running"])
        self.assertTrue(status["connected"])
        self.assertEqual(
            stream.started_with,
            (("NIFTY", "BANKNIFTY"), False),
        )
        self.assertEqual(
            state["symbols"]["NIFTY"]["snapshot_kind"], "QUOTE_SEED"
        )
        self.assertFalse(state["live_trading_enabled"])
        self.assertFalse(state["stream"]["live_orders"])
        runtime.stop()
        self.assertTrue(stream.stopped)

    def test_disabled_runtime_does_not_load_stream(self):
        loader_called = False

        def loader():
            nonlocal loader_called
            loader_called = True
            return FakeRuntimeStream()

        runtime = MarketRuntime(
            enabled=False,
            stream_loader=loader,
            configured_check=lambda: True,
        )
        status = runtime.start()
        self.assertFalse(status["running"])
        self.assertFalse(loader_called)

    def test_restart_reloads_stream_after_token_refresh(self):
        streams = []

        def loader():
            stream = FakeRuntimeStream()
            streams.append(stream)
            return stream

        runtime = MarketRuntime(
            enabled=True,
            provider="AUTO",
            symbols=("NIFTY",),
            stream_loader=loader,
            configured_check=lambda: True,
            quote_loader=None,
        )
        runtime.start()
        status = runtime.restart()

        self.assertEqual(len(streams), 2)
        self.assertTrue(streams[0].stopped)
        self.assertTrue(status["running"])


if __name__ == "__main__":
    unittest.main()
