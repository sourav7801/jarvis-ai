import unittest
from datetime import datetime, timezone

from workstation.market_data_contract import MarketEventType, canonical_market_event
from workstation.market_event_bus import MarketEventBus


SOURCE = {
    "success": True, "source": "FYERS", "provider_symbol": "NSE:NIFTY50-INDEX",
    "data_quality": "BROKER_LIVE", "exchange_timestamp": "2026-08-26T06:00:00+00:00",
}


class MarketEventBusTests(unittest.TestCase):
    def test_validated_bar_is_delivered_and_retained(self):
        bus = MarketEventBus(capacity=10)
        delivered = []
        bus.subscribe("features", delivered.append, {MarketEventType.BAR})
        event = canonical_market_event(
            SOURCE, {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10},
            event_type=MarketEventType.BAR, timeframe="5m",
            received_at=datetime(2026, 8, 26, 6, 0, 1, tzinfo=timezone.utc),
        )
        result = bus.publish(event)
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(bus.snapshot()["retained"], 1)
        self.assertFalse(result["live_execution"])

    def test_invalid_event_shapes_fail_before_publication(self):
        with self.assertRaises(ValueError):
            canonical_market_event(SOURCE, {"open": 100, "high": 90, "low": 80, "close": 95}, event_type=MarketEventType.BAR)
        with self.assertRaises(ValueError):
            canonical_market_event(SOURCE, {"calls": []}, event_type=MarketEventType.OPTION_CHAIN_SNAPSHOT)
        with self.assertRaises(ValueError):
            canonical_market_event(SOURCE, {"status": "MAYBE"}, event_type=MarketEventType.PROVIDER_HEALTH)

    def test_subscriber_failure_isolated_and_capacity_bounded(self):
        bus = MarketEventBus(capacity=10)
        bus.subscribe("broken", lambda _event: (_ for _ in ()).throw(RuntimeError("boom")))
        for index in range(12):
            event = canonical_market_event(
                {**SOURCE, "exchange_timestamp": f"2026-08-26T06:00:{index:02d}+00:00"},
                {"ltp": 100.0 + index}, event_type=MarketEventType.QUOTE_TICK,
                received_at=datetime(2026, 8, 26, 6, 1, tzinfo=timezone.utc),
            )
            bus.publish(event)
        state = bus.snapshot()
        self.assertEqual(state["retained"], 10)
        self.assertEqual(state["subscriber_errors"], 12)


if __name__ == "__main__":
    unittest.main()
