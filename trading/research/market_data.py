"""Canonical timestamped OHLCV data contracts and validation."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Market timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _utc(self.timestamp))
        values = (self.open, self.high, self.low, self.close)
        if any(not math.isfinite(float(value)) or float(value) <= 0 for value in values):
            raise ValueError("OHLC prices must be positive.")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("Candle high is inconsistent with OHLC values.")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Candle low is inconsistent with OHLC values.")
        if not math.isfinite(float(self.volume)) or float(self.volume) < 0:
            raise ValueError("Candle volume cannot be negative.")

    def canonical(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
        }


@dataclass(frozen=True)
class DataProvenance:
    provider: str
    source: str
    retrieved_at: datetime
    environment: str = "RESEARCH"

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.source.strip():
            raise ValueError("Data provider and source are required.")
        object.__setattr__(self, "retrieved_at", _utc(self.retrieved_at))
        if self.environment.upper() not in {"RESEARCH", "PAPER"}:
            raise ValueError("Only RESEARCH and PAPER provenance is accepted.")


@dataclass(frozen=True)
class MarketDataset:
    symbol: str
    timeframe: str
    candles: tuple[Candle, ...]
    provenance: DataProvenance
    checksum: str = field(init=False)

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        timeframe = self.timeframe.strip().lower()
        if not symbol or not timeframe:
            raise ValueError("Dataset symbol and timeframe are required.")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "timeframe", timeframe)
        object.__setattr__(self, "candles", tuple(self.candles))
        self.validate()
        object.__setattr__(self, "checksum", self.compute_checksum())

    @classmethod
    def create(
        cls,
        symbol: str,
        timeframe: str,
        candles: Iterable[Candle],
        provenance: DataProvenance,
    ) -> "MarketDataset":
        return cls(symbol, timeframe, tuple(candles), provenance)

    def validate(self) -> None:
        if len(self.candles) < 2:
            raise ValueError("A market dataset requires at least two candles.")
        timestamps = [candle.timestamp for candle in self.candles]
        if timestamps != sorted(timestamps):
            raise ValueError("Candles must be ordered by ascending timestamp.")
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("Duplicate candle timestamps are not allowed.")
        if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            raise ValueError("Candle timestamps must be strictly increasing.")

    def compute_checksum(self) -> str:
        payload = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "provenance": {
                **asdict(self.provenance),
                "retrieved_at": self.provenance.retrieved_at.isoformat(),
            },
            "candles": [candle.canonical() for candle in self.candles],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def assert_fresh(
        self, maximum_age: timedelta, now: datetime | None = None
    ) -> None:
        if maximum_age.total_seconds() <= 0:
            raise ValueError("maximum_age must be positive.")
        reference = _utc(now or datetime.now(timezone.utc))
        age = reference - self.provenance.retrieved_at
        if age < timedelta(0):
            raise ValueError("Dataset retrieval timestamp is in the future.")
        if age > maximum_age:
            raise ValueError(f"Dataset is stale by {age - maximum_age}.")
