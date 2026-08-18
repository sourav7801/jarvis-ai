from dataclasses import dataclass
from typing import Optional


@dataclass
class Instrument:

    symbol: str

    market: str

    asset_type: str

    exchange: Optional[str] = None

    currency: str = "INR"

    expiry: Optional[str] = None

    strike: Optional[float] = None

    option_type: Optional[str] = None


@dataclass
class MarketSnapshot:

    instrument: Instrument

    price: float

    timestamp: Optional[str] = None

    volume: Optional[float] = None

    open_interest: Optional[float] = None