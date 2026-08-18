"""
JARVIS MARKET REGIME ENGINE V1

Purpose
-------
Exchange-calendar-aware market/session/expiry regime logic for the
JARVIS Trading Workstation.

Research/data/decision layer only.
NO ORDER EXECUTION.

Current rules encoded from official exchange information available
when this file was prepared:

NSE equity derivatives:
- Normal market: 09:15-15:30 IST.
- NIFTY weekly/monthly index option expiry: Tuesday.
- BANKNIFTY monthly/quarterly expiry: last Tuesday.
- BANKNIFTY monthly options have a 3-month trading cycle.

BSE:
- SENSEX weekly expiry: Tuesday.
- BSE index/equity derivatives normal continuous trading is treated
  as 09:15-15:30 IST for workstation session gating.

Important:
The engine deliberately separates "contract calendar" from
"strategy eligibility". That prevents hard-coded weekday assumptions
from leaking into the trading logic.

User trading policy encoded:
1. BANKNIFTY is preferred on expiry day or the prior trading day.
2. BANKNIFTY requires a strong momentum regime.
3. Otherwise fall back to NIFTY.
4. SENSEX is the secondary fallback.
5. Outside the normal session, no live setup is evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")

NORMAL_OPEN = time(9, 15)
NORMAL_CLOSE = time(15, 30)

# NSE F&O holidays for 2026 from the published F&O holiday circular.
# This is intentionally stored separately so a new year's calendar
# can be swapped without changing regime logic.
NSE_FO_HOLIDAYS_2026 = {
    date(2026, 1, 26),
    date(2026, 3, 3),
    date(2026, 3, 26),
    date(2026, 3, 31),
    date(2026, 4, 3),
    date(2026, 4, 14),
    date(2026, 5, 1),
    date(2026, 5, 28),
    date(2026, 6, 26),
    date(2026, 9, 14),
    date(2026, 10, 2),
    date(2026, 10, 20),
    date(2026, 11, 10),
    date(2026, 11, 24),
    date(2026, 12, 25),
}

# BSE/NSE common continuous session gate for the workstation.
# The exchange can publish special-session timings; those should
# override this default when a special-session calendar is loaded.
BSE_FO_HOLIDAYS_2026 = set(NSE_FO_HOLIDAYS_2026)


class SessionState(str, Enum):
    CLOSED = "CLOSED"
    PRE_OPEN = "PRE_OPEN"
    OPEN = "OPEN"
    POST_CLOSE = "POST_CLOSE"
    HOLIDAY = "HOLIDAY"


class ExpiryPhase(str, Enum):
    NORMAL = "NORMAL"
    PRE_EXPIRY = "PRE_EXPIRY"
    EXPIRY = "EXPIRY"


class MomentumState(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


@dataclass
class RegimeSnapshot:
    as_of: str
    symbol: str
    exchange: str

    session: str
    trading_day: bool

    expiry_date: Optional[str]
    previous_trading_day: Optional[str]
    days_to_expiry: Optional[int]
    expiry_phase: str

    momentum_score: float
    momentum_state: str

    eligible: bool
    priority: int
    preferred_action: str

    reason: str


def _local_dt(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(IST)
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_nse_trading_day(d: date, year_holidays: Optional[set] = None) -> bool:
    holidays = year_holidays if year_holidays is not None else (
        NSE_FO_HOLIDAYS_2026 if d.year == 2026 else set()
    )
    return not _is_weekend(d) and d not in holidays


def is_bse_trading_day(d: date, year_holidays: Optional[set] = None) -> bool:
    holidays = year_holidays if year_holidays is not None else (
        BSE_FO_HOLIDAYS_2026 if d.year == 2026 else set()
    )
    return not _is_weekend(d) and d not in holidays


def previous_trading_day(
    d: date,
    exchange: str = "NSE",
) -> date:
    candidate = d - timedelta(days=1)

    while True:
        valid = (
            is_nse_trading_day(candidate)
            if exchange.upper() == "NSE"
            else is_bse_trading_day(candidate)
        )
        if valid:
            return candidate
        candidate -= timedelta(days=1)


def next_trading_day(
    d: date,
    exchange: str = "NSE",
) -> date:
    candidate = d + timedelta(days=1)

    while True:
        valid = (
            is_nse_trading_day(candidate)
            if exchange.upper() == "NSE"
            else is_bse_trading_day(candidate)
        )
        if valid:
            return candidate
        candidate += timedelta(days=1)


def session_state(
    now: datetime,
    exchange: str = "NSE",
) -> SessionState:
    now = _local_dt(now)
    d = now.date()

    trading = (
        is_nse_trading_day(d)
        if exchange.upper() == "NSE"
        else is_bse_trading_day(d)
    )

    if not trading:
        return SessionState.HOLIDAY

    t = now.time()

    if t < NORMAL_OPEN:
        return SessionState.PRE_OPEN

    if t <= NORMAL_CLOSE:
        return SessionState.OPEN

    return SessionState.POST_CLOSE


def last_tuesday_of_month(
    year: int,
    month: int,
) -> date:
    # Find first day of next month, then move backward.
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    d = next_month - timedelta(days=1)

    while d.weekday() != 1:  # Tuesday
        d -= timedelta(days=1)

    return d


def adjusted_expiry(
    nominal_expiry: date,
    exchange: str = "NSE",
) -> date:
    expiry = nominal_expiry

    while True:
        valid = (
            is_nse_trading_day(expiry)
            if exchange.upper() == "NSE"
            else is_bse_trading_day(expiry)
        )
        if valid:
            return expiry
        expiry -= timedelta(days=1)


def next_nifty_expiry(
    d: date,
) -> date:
    """
    NIFTY weekly/monthly index options:
    Tuesday expiry; holiday -> previous trading day.

    Returns the next Tuesday-derived expiry on/after d.
    """
    candidate = d
    while candidate.weekday() != 1:
        candidate += timedelta(days=1)

    return adjusted_expiry(candidate, "NSE")


def next_banknifty_monthly_expiry(
    d: date,
) -> date:
    """
    BANKNIFTY monthly contract:
    last Tuesday of the expiry month; holiday -> previous trading day.

    This reflects the current post-28-Aug-2025 expiry regime.
    """
    y = d.year
    m = d.month

    nominal = last_tuesday_of_month(y, m)
    expiry = adjusted_expiry(nominal, "NSE")

    if expiry >= d:
        return expiry

    if m == 12:
        y += 1
        m = 1
    else:
        m += 1

    nominal = last_tuesday_of_month(y, m)
    return adjusted_expiry(nominal, "NSE")


def next_sensex_weekly_expiry(
    d: date,
) -> date:
    """
    BSE SENSEX weekly expiry:
    Tuesday of the expiry week; holiday -> previous trading day.
    """
    candidate = d
    while candidate.weekday() != 1:
        candidate += timedelta(days=1)

    return adjusted_expiry(candidate, "BSE")


def expiry_info(
    symbol: str,
    now: datetime,
) -> Tuple[Optional[date], Optional[date], Optional[int], ExpiryPhase]:
    now = _local_dt(now)
    d = now.date()

    symbol = symbol.upper()

    if symbol == "NIFTY":
        expiry = next_nifty_expiry(d)
        prev_day = previous_trading_day(expiry, "NSE")

    elif symbol == "BANKNIFTY":
        expiry = next_banknifty_monthly_expiry(d)
        prev_day = previous_trading_day(expiry, "NSE")

    elif symbol == "SENSEX":
        expiry = next_sensex_weekly_expiry(d)
        prev_day = previous_trading_day(expiry, "BSE")

    else:
        return None, None, None, ExpiryPhase.NORMAL

    days = (expiry - d).days

    if d == expiry:
        phase = ExpiryPhase.EXPIRY
    elif d == prev_day:
        phase = ExpiryPhase.PRE_EXPIRY
    else:
        phase = ExpiryPhase.NORMAL

    return expiry, prev_day, days, phase


def classify_momentum(
    score: float,
) -> MomentumState:
    if score >= 70:
        return MomentumState.STRONG
    if score >= 50:
        return MomentumState.MODERATE
    return MomentumState.WEAK


def banknifty_policy(
    phase: ExpiryPhase,
    momentum: MomentumState,
) -> Tuple[bool, str]:
    if phase in {
        ExpiryPhase.PRE_EXPIRY,
        ExpiryPhase.EXPIRY,
    }:
        if momentum == MomentumState.STRONG:
            return True, "BANKNIFTY_PRIMARY"
        return False, "BANKNIFTY_BLOCKED_WEAK_MOMENTUM"

    return False, "BANKNIFTY_NOT_IN_USER_PRIMARY_WINDOW"


def preferred_market(
    now: datetime,
    nifty_momentum: float,
    banknifty_momentum: float,
    sensex_momentum: float,
) -> Dict[str, object]:
    now = _local_dt(now)

    bank_expiry, bank_prev, _, bank_phase = expiry_info(
        "BANKNIFTY",
        now,
    )

    bank_state = classify_momentum(
        banknifty_momentum
    )

    bank_ok, bank_action = banknifty_policy(
        bank_phase,
        bank_state,
    )

    if bank_ok:
        return {
            "preferred_symbol": "BANKNIFTY",
            "priority": ["BANKNIFTY", "NIFTY", "SENSEX"],
            "reason": (
                "BANKNIFTY is in the user-defined expiry/pre-expiry "
                "window and momentum is STRONG."
            ),
            "bank_phase": bank_phase.value,
            "bank_expiry": (
                bank_expiry.isoformat()
                if bank_expiry
                else None
            ),
            "bank_previous_trading_day": (
                bank_prev.isoformat()
                if bank_prev
                else None
            ),
        }

    nifty_state = classify_momentum(
        nifty_momentum
    )

    if nifty_state in {
        MomentumState.STRONG,
        MomentumState.MODERATE,
    }:
        return {
            "preferred_symbol": "NIFTY",
            "priority": ["NIFTY", "SENSEX", "BANKNIFTY"],
            "reason": (
                "BANKNIFTY is not eligible under the user policy; "
                "NIFTY is the primary fallback."
            ),
            "bank_phase": bank_phase.value,
            "bank_expiry": (
                bank_expiry.isoformat()
                if bank_expiry
                else None
            ),
        }

    return {
        "preferred_symbol": "SENSEX",
        "priority": ["SENSEX", "NIFTY", "BANKNIFTY"],
        "reason": (
            "BANKNIFTY is not eligible and NIFTY momentum is not "
            "strong enough; SENSEX is the secondary fallback."
        ),
        "bank_phase": bank_phase.value,
        "bank_expiry": (
            bank_expiry.isoformat()
            if bank_expiry
            else None
        ),
    }


def build_snapshot(
    symbol: str,
    momentum_score: float,
    now: Optional[datetime] = None,
) -> RegimeSnapshot:
    now = _local_dt(now)

    symbol = symbol.upper()

    exchange = (
        "BSE"
        if symbol == "SENSEX"
        else "NSE"
    )

    session = session_state(
        now,
        exchange,
    )

    trading_day = (
        session != SessionState.HOLIDAY
    )

    expiry, prev_day, days_to_expiry, phase = expiry_info(
        symbol,
        now,
    )

    momentum = classify_momentum(
        momentum_score
    )

    eligible = (
        session == SessionState.OPEN
    )

    priority = 99
    action = "WATCH"

    if symbol == "BANKNIFTY":
        if phase in {
            ExpiryPhase.PRE_EXPIRY,
            ExpiryPhase.EXPIRY,
        } and momentum == MomentumState.STRONG:
            priority = 1
            action = "PRIMARY"
        else:
            priority = 3
            action = "FALLBACK_ONLY"

    elif symbol == "NIFTY":
        priority = 2
        action = "PRIMARY_FALLBACK"

    elif symbol == "SENSEX":
        priority = 3
        action = "SECONDARY_FALLBACK"

    if session != SessionState.OPEN:
        eligible = False
        action = "MARKET_CLOSED"

    reason_parts = [
        f"Session={session.value}",
        f"ExpiryPhase={phase.value}",
        f"Momentum={momentum.value}",
    ]

    if expiry:
        reason_parts.append(
            f"Expiry={expiry.isoformat()}"
        )

    return RegimeSnapshot(
        as_of=now.isoformat(),
        symbol=symbol,
        exchange=exchange,
        session=session.value,
        trading_day=trading_day,
        expiry_date=(
            expiry.isoformat()
            if expiry
            else None
        ),
        previous_trading_day=(
            prev_day.isoformat()
            if prev_day
            else None
        ),
        days_to_expiry=days_to_expiry,
        expiry_phase=phase.value,
        momentum_score=float(
            momentum_score
        ),
        momentum_state=momentum.value,
        eligible=eligible,
        priority=priority,
        preferred_action=action,
        reason=" | ".join(reason_parts),
    )


def workstation_regime(
    nifty_momentum: float,
    banknifty_momentum: float,
    sensex_momentum: float,
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    now = _local_dt(now)

    preference = preferred_market(
        now,
        nifty_momentum,
        banknifty_momentum,
        sensex_momentum,
    )

    snapshots = {}

    for symbol, score in [
        ("BANKNIFTY", banknifty_momentum),
        ("NIFTY", nifty_momentum),
        ("SENSEX", sensex_momentum),
    ]:
        snapshot = build_snapshot(
            symbol,
            score,
            now,
        )
        snapshots[symbol] = asdict(
            snapshot
        )

    return {
        "as_of": now.isoformat(),
        "preferred_symbol":
            preference[
                "preferred_symbol"
            ],
        "priority":
            preference[
                "priority"
            ],
        "reason":
            preference[
                "reason"
            ],
        "banknifty_policy": {
            "phase":
                preference.get(
                    "bank_phase"
                ),
            "expiry":
                preference.get(
                    "bank_expiry"
                ),
            "previous_trading_day":
                preference.get(
                    "bank_previous_trading_day"
                ),
        },
        "snapshots":
            snapshots,
        "session": {
            "NSE":
                session_state(
                    now,
                    "NSE",
                ).value,
            "BSE":
                session_state(
                    now,
                    "BSE",
                ).value,
        },
    }


if __name__ == "__main__":
    now = datetime.now(IST)

    result = workstation_regime(
        nifty_momentum=68,
        banknifty_momentum=42,
        sensex_momentum=61,
        now=now,
    )

    import json

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )
