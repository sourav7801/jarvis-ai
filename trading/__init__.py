"""Canonical trading research package. Live execution is prohibited."""

from config import LIVE_TRADING_ENABLED

if LIVE_TRADING_ENABLED:
    raise RuntimeError("Canonical trading package cannot enable live execution.")

