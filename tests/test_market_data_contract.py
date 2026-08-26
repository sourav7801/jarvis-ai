from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest

from workstation.market_data_contract import (
    MarketDataQuality,
    MarketEventType,
    VenueSessionService,
    canonical_market_datum,
)


UTC = timezone.utc


class MarketDataContractTests(unittest.TestCase):
    def test_fyers_quote_has_complete_provenance_and_freshness(self):
        received = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
        datum = canonical_market_datum(
            {"success": True, "source": "FYERS", "provider_symbol": "NSE:NIFTY50-INDEX", "timestamp": received.timestamp()},
            received_at=received,
        )
        self.assertEqual(datum.event_type, MarketEventType.QUOTE_TICK.value)
        self.assertEqual(datum.quality_flag, MarketDataQuality.BROKER_LIVE.value)
        self.assertTrue(datum.verified)
        self.assertFalse(datum.stale)

    def test_stale_exchange_timestamp_remains_diagnostic_but_stale(self):
        received = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
        datum = canonical_market_datum(
            {"success": True, "source": "BINANCE_PUBLIC", "provider_symbol": "BTCUSDT", "exchange_timestamp": (received - timedelta(minutes=5)).timestamp() * 1000},
            received_at=received,
            stale_after_seconds=90,
        )
        self.assertTrue(datum.verified)
        self.assertTrue(datum.stale)
        self.assertEqual(datum.freshness_basis, "EXCHANGE_TIMESTAMP")

    def test_unknown_provider_cannot_be_upgraded_to_verified(self):
        datum = canonical_market_datum(
            {"success": True, "source": "MYSTERY", "provider_symbol": "X"},
            received_at=datetime(2026, 8, 26, tzinfo=UTC),
        )
        self.assertFalse(datum.verified)
        self.assertEqual(datum.quality_flag, MarketDataQuality.UNVERIFIED.value)

    def test_venue_sessions_are_explicit_and_fail_closed(self):
        service = VenueSessionService(holidays={"NSE": {date(2026, 8, 26)}})
        instant = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
        self.assertEqual(service.evaluate("NSE", at=instant).reason, "CONFIGURED_HOLIDAY")
        self.assertTrue(service.evaluate("CRYPTO_24_7", at=instant).session_open)
        self.assertFalse(service.evaluate("UNKNOWN", at=instant).entry_eligible)
        self.assertFalse(service.evaluate("GLOBAL_RESEARCH_ONLY", at=instant).entry_eligible)

    def test_metadata_routes_to_venue_without_guessing_global_sessions(self):
        self.assertEqual(VenueSessionService.venue_for({"asset_class": "CRYPTO"}), "CRYPTO_24_7")
        self.assertEqual(VenueSessionService.venue_for({"asset_class": "COMMODITY"}), "MCX")
        self.assertEqual(VenueSessionService.venue_for({"asset_class": "EQUITY", "market": "USA"}), "GLOBAL_RESEARCH_ONLY")
        self.assertEqual(VenueSessionService.venue_for({"asset_class": "INDEX", "symbol": "SENSEX"}), "BSE")


if __name__ == "__main__":
    unittest.main()
