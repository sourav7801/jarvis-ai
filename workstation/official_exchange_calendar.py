"""Validated, versioned exchange-session snapshots for governed paper trading.

The runtime never scrapes a search result and never guesses a holiday.  A
checked-in snapshot names its official exchange source, coverage year, regular
windows, full holidays and verified or pending special sessions.  Missing,
malformed or out-of-year data fails closed at the session gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALENDAR_PATH = ROOT / "config" / "exchange_calendars" / "india_2026.json"
OFFICIAL_HOSTS = {
    "www.nseindia.com",
    "nseindia.com",
    "www.bseindia.com",
    "bseindia.com",
    "www.mcxindia.com",
    "mcxindia.com",
}


@dataclass(frozen=True)
class VenueCalendar:
    venue: str
    calendar_year: int
    timezone: str
    verified_through: date
    source_url: str
    source_kind: str
    regular_windows: tuple[tuple[time, time], ...]
    full_holidays: frozenset[date]
    special_sessions: Mapping[date, tuple[str, tuple[tuple[time, time], ...]]]

    def session_for(self, local: datetime) -> tuple[str, tuple[tuple[time, time], ...]]:
        day = local.date()
        if day.year != self.calendar_year:
            return "CALENDAR_YEAR_UNVERIFIED", ()
        special = self.special_sessions.get(day)
        if special is not None:
            status, windows = special
            if status != "VERIFIED":
                return "SPECIAL_SESSION_TIMING_UNVERIFIED", ()
            return "OFFICIAL_SPECIAL_SESSION", windows
        if day in self.full_holidays:
            return "OFFICIAL_EXCHANGE_HOLIDAY", ()
        if local.weekday() >= 5:
            return "WEEKEND", ()
        return "REGULAR_SESSION", self.regular_windows


def _clock(value: Any) -> time:
    text = str(value or "").strip()
    try:
        parsed = time.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid exchange-calendar time: {text!r}") from exc
    return parsed.replace(second=0, microsecond=0)


def _windows(value: Any) -> tuple[tuple[time, time], ...]:
    if not isinstance(value, list):
        raise ValueError("Exchange-calendar windows must be a list.")
    result: list[tuple[time, time]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Every exchange-calendar window must contain open and close times.")
        opening, closing = _clock(item[0]), _clock(item[1])
        if opening >= closing:
            raise ValueError("Exchange-calendar window close must be after open.")
        result.append((opening, closing))
    return tuple(result)


def load_official_calendars(path: Path | str = DEFAULT_CALENDAR_PATH) -> dict[str, VenueCalendar]:
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported exchange-calendar schema.")
    year = int(payload.get("calendar_year") or 0)
    verified_through = date.fromisoformat(str(payload.get("verified_through") or ""))
    if verified_through.year != year:
        raise ValueError("Exchange-calendar verification date must match its coverage year.")
    timezone_name = str(payload.get("timezone") or "").strip()
    if timezone_name != "Asia/Kolkata":
        raise ValueError("Indian exchange calendars must use Asia/Kolkata.")
    raw_venues = payload.get("venues")
    if not isinstance(raw_venues, dict):
        raise ValueError("Exchange-calendar venues are missing.")

    calendars: dict[str, VenueCalendar] = {}
    for raw_venue, raw in raw_venues.items():
        venue = str(raw_venue).strip().upper()
        if venue not in {"NSE", "BSE", "MCX"} or not isinstance(raw, dict):
            raise ValueError(f"Unsupported exchange-calendar venue: {venue!r}")
        source_url = str(raw.get("source_url") or "").strip()
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            raise ValueError(f"Calendar source is not an allowlisted official exchange URL: {source_url!r}")
        regular = _windows(raw.get("regular_windows"))
        if not regular:
            raise ValueError(f"{venue} regular session windows are missing.")
        holidays = frozenset(date.fromisoformat(str(item)) for item in raw.get("full_holidays", []))
        if any(item.year != year for item in holidays):
            raise ValueError(f"{venue} holiday lies outside calendar year {year}.")
        special: dict[date, tuple[str, tuple[tuple[time, time], ...]]] = {}
        raw_special = raw.get("special_sessions") or {}
        if not isinstance(raw_special, dict):
            raise ValueError(f"{venue} special sessions must be an object.")
        for raw_day, details in raw_special.items():
            day = date.fromisoformat(str(raw_day))
            if day.year != year or not isinstance(details, dict):
                raise ValueError(f"Invalid {venue} special session: {raw_day!r}")
            status = str(details.get("status") or "").strip().upper()
            if status not in {"VERIFIED", "PENDING_OFFICIAL_TIMING"}:
                raise ValueError(f"Invalid {venue} special-session status: {status!r}")
            windows = _windows(details.get("windows") or [])
            if status == "VERIFIED" and not windows:
                raise ValueError(f"Verified {venue} special session has no windows.")
            if status != "VERIFIED" and windows:
                raise ValueError(f"Pending {venue} special session cannot carry guessed windows.")
            special[day] = (status, windows)
        calendars[venue] = VenueCalendar(
            venue=venue,
            calendar_year=year,
            timezone=timezone_name,
            verified_through=verified_through,
            source_url=source_url,
            source_kind=str(raw.get("source_kind") or "OFFICIAL_EXCHANGE"),
            regular_windows=regular,
            full_holidays=holidays,
            special_sessions=special,
        )
    return calendars


def safe_official_calendars(path: Path | str = DEFAULT_CALENDAR_PATH) -> dict[str, VenueCalendar]:
    try:
        return load_official_calendars(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
