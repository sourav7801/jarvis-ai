
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class Regime:
    symbol: str
    direction: str = "NEUTRAL"
    regime: str = "UNKNOWN"
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    vwap_state: str = "UNKNOWN"
    ema_state: str = "UNKNOWN"
    structure_state: str = "UNKNOWN"
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class Setup:
    symbol: str
    strategy: str
    direction: str
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    rr: float
    score: float
    status: str = "WAIT"
    reasons: List[str] = field(default_factory=list)


@dataclass
class PaperPosition:
    id: str
    symbol: str
    direction: str
    entry: float
    stop: float
    target: float
    qty: int
    opened_at: datetime
    status: str = "OPEN"
    pnl: float = 0.0
    exit: Optional[float] = None
    closed_at: Optional[datetime] = None
