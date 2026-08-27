from __future__ import annotations

from datetime import datetime, timezone
import unittest

from workstation.market_data_contract import VenueSessionService
from workstation.official_exchange_calendar import load_official_calendars


UTC = timezone.utc


class OfficialExchangeCalendarTests(unittest.TestCase):
    def test_snapshot_is_official_versioned_and_complete_for_governed_venues(self):
        calendars = load_official_calendars()

        self.assertEqual(set(calendars), {"NSE", "BSE", "MCX"})
        for calendar in calendars.values():
            self.assertEqual(calendar.calendar_year, 2026)
            self.assertEqual(calendar.timezone, "Asia/Kolkata")
            self.assertEqual(calendar.source_url.split(":", 1)[0], "https")
            self.assertTrue(calendar.source_kind.startswith("OFFICIAL_EXCHANGE"))

    def test_equity_holiday_is_closed_from_official_snapshot(self):
        service = VenueSessionService()
        status = service.evaluate(
            "NSE",
            at=datetime(2026, 1, 26, 5, 0, tzinfo=UTC),
        )

        self.assertFalse(status.entry_eligible)
        self.assertEqual(status.reason, "OFFICIAL_EXCHANGE_HOLIDAY")
        self.assertIn("nseindia.com", status.calendar_source)

    def test_mcx_partial_holiday_uses_only_verified_evening_window(self):
        service = VenueSessionService()
        morning = service.evaluate(
            "MCX",
            at=datetime(2026, 3, 3, 6, 0, tzinfo=UTC),
        )
        evening = service.evaluate(
            "MCX",
            at=datetime(2026, 3, 3, 12, 30, tzinfo=UTC),
        )

        self.assertFalse(morning.entry_eligible)
        self.assertEqual(morning.reason, "OUTSIDE_OFFICIAL_SPECIAL_SESSION")
        self.assertTrue(evening.entry_eligible)
        self.assertEqual(evening.reason, "OFFICIAL_SPECIAL_SESSION")

    def test_pending_muhurat_timing_and_uncovered_year_fail_closed(self):
        service = VenueSessionService()
        pending = service.evaluate(
            "BSE",
            at=datetime(2026, 11, 8, 13, 0, tzinfo=UTC),
        )
        future = service.evaluate(
            "NSE",
            at=datetime(2027, 1, 4, 5, 0, tzinfo=UTC),
        )

        self.assertFalse(pending.entry_eligible)
        self.assertEqual(pending.reason, "SPECIAL_SESSION_TIMING_UNVERIFIED")
        self.assertFalse(future.entry_eligible)
        self.assertEqual(future.reason, "CALENDAR_YEAR_UNVERIFIED")

    def test_missing_calendar_cannot_fall_back_to_weekday_guess(self):
        status = VenueSessionService(calendars={}).evaluate(
            "NSE",
            at=datetime(2026, 8, 27, 5, 0, tzinfo=UTC),
        )

        self.assertFalse(status.entry_eligible)
        self.assertEqual(status.reason, "OFFICIAL_CALENDAR_UNAVAILABLE")
        self.assertEqual(status.calendar_source, "FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main()
