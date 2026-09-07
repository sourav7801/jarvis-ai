from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(frozen=True)
class TradingTimeframeProfile:
    name: str
    timeframes: tuple[str, ...]
    minimum_score: float
    minimum_alignment: int
    minimum_risk_reward: float
    require_confirmed_pattern: bool
    scan_interval_seconds: float
    risk_multiplier: float
    description: str
    require_pattern_or_strategy_confirmation: bool = False

    @property
    def single_timeframe(self) -> bool:
        return len(self.timeframes) == 1

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "single_timeframe": self.single_timeframe}


PROFILES: dict[str, TradingTimeframeProfile] = {
    "adaptive_intraday": TradingTimeframeProfile(
        name="adaptive_intraday",
        timeframes=("5m", "15m"),
        minimum_score=67.0,
        minimum_alignment=100,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=False,
        scan_interval_seconds=5.0,
        risk_multiplier=0.25,
        description=(
            "Reduced-risk 5m/15m paper entries with full directional agreement "
            "and a confirmed chart pattern or regime-compatible strategy vote."
        ),
        require_pattern_or_strategy_confirmation=True,
    ),
    "intraday": TradingTimeframeProfile(
        name="intraday",
        timeframes=("5m", "15m", "1h"),
        minimum_score=68.0,
        minimum_alignment=67,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=False,
        scan_interval_seconds=15.0,
        risk_multiplier=1.0,
        description="Governed 5m/15m/1h intraday consensus.",
    ),
    "paper_exploration": TradingTimeframeProfile(
        name="paper_exploration",
        timeframes=("5m",),
        minimum_score=62.0,
        minimum_alignment=100,
        minimum_risk_reward=1.5,
        require_confirmed_pattern=False,
        scan_interval_seconds=5.0,
        risk_multiplier=0.25,
        description=(
            "Low-risk synthetic learning on completed 5m bars. It may explore "
            "valid stop/target setups in range regimes and sizes each new paper trade at 25% of normal risk."
        ),
    ),
    "swing": TradingTimeframeProfile(
        name="swing",
        timeframes=("1h", "4h", "1d"),
        minimum_score=68.0,
        minimum_alignment=67,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=False,
        scan_interval_seconds=60.0,
        risk_multiplier=1.0,
        description="Governed 1h/4h/1d swing consensus.",
    ),
    "investment": TradingTimeframeProfile(
        name="investment",
        timeframes=("1d",),
        minimum_score=75.0,
        minimum_alignment=100,
        minimum_risk_reward=2.5,
        require_confirmed_pattern=False,
        scan_interval_seconds=900.0,
        risk_multiplier=0.50,
        description=(
            "Long-only daily paper-investment mandate with a higher evidence gate "
            "and half-sized risk."
        ),
    ),
    "1m_only": TradingTimeframeProfile(
        name="1m_only",
        timeframes=("1m",),
        minimum_score=74.0,
        minimum_alignment=100,
        minimum_risk_reward=2.0,
        require_confirmed_pattern=True,
        scan_interval_seconds=2.0,
        risk_multiplier=1.0,
        description="One-minute paper scalping on completed 1m bars with a confirmed breakout or breakdown.",
    ),
    "5m_only": TradingTimeframeProfile(
        name="5m_only",
        timeframes=("5m",),
        minimum_score=70.0,
        minimum_alignment=100,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=True,
        scan_interval_seconds=5.0,
        risk_multiplier=1.0,
        description="Five-minute paper trading on completed 5m bars with a confirmed breakout or breakdown.",
    ),
    "10m_only": TradingTimeframeProfile(
        name="10m_only",
        timeframes=("10m",),
        minimum_score=69.0,
        minimum_alignment=100,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=True,
        scan_interval_seconds=7.5,
        risk_multiplier=0.75,
        description=(
            "Ten-minute paper trading derived only from two contiguous completed 5m provider bars, "
            "with a confirmed breakout or breakdown and reduced risk sizing."
        ),
    ),
    "15m_only": TradingTimeframeProfile(
        name="15m_only",
        timeframes=("15m",),
        minimum_score=68.0,
        minimum_alignment=100,
        minimum_risk_reward=1.8,
        require_confirmed_pattern=True,
        scan_interval_seconds=10.0,
        risk_multiplier=1.0,
        description="Fifteen-minute paper trading on completed 15m bars with a confirmed breakout or breakdown.",
    ),
}


ALIASES = {
    "adaptive": "adaptive_intraday",
    "adaptiveintraday": "adaptive_intraday",
    "flexible": "adaptive_intraday",
    "flexibleintraday": "adaptive_intraday",
    "default": "intraday",
    "mtf": "intraday",
    "multi": "intraday",
    "explore": "paper_exploration",
    "exploration": "paper_exploration",
    "paperexploration": "paper_exploration",
    "paperlearn": "paper_exploration",
    "learning": "paper_exploration",
    "daily": "swing",
    "position": "swing",
    "positional": "swing",
    "invest": "investment",
    "investment": "investment",
    "longterm": "investment",
    "longterminvestment": "investment",
    "scalp": "1m_only",
    "scalping": "1m_only",
    "1m": "1m_only",
    "1min": "1m_only",
    "1minute": "1m_only",
    "1monly": "1m_only",
    "5m": "5m_only",
    "5min": "5m_only",
    "5minute": "5m_only",
    "5monly": "5m_only",
    "10m": "10m_only",
    "10min": "10m_only",
    "10minute": "10m_only",
    "10monly": "10m_only",
    "15m": "15m_only",
    "15min": "15m_only",
    "15minute": "15m_only",
    "15monly": "15m_only",
}


def resolve_trading_profile(value: str | None) -> TradingTimeframeProfile:
    normalized = re.sub(r"[^a-z0-9]+", "", str(value or "intraday").lower())
    key = ALIASES.get(normalized, normalized)
    return PROFILES.get(key, PROFILES["intraday"])


def requested_trading_profile(text: str, *, default: str = "intraday") -> TradingTimeframeProfile:
    value = " ".join(str(text or "").lower().split())
    explicit_only = bool(re.search(r"\b(?:only|solely|strictly|single\s*timeframe)\b", value))
    patterns = (
        (r"\b1\s*(?:m|min|minute)s?\b", "1m_only"),
        (r"\b5\s*(?:m|min|minute)s?\b", "5m_only"),
        (r"\b10\s*(?:m|min|minute)s?\b", "10m_only"),
        (r"\b15\s*(?:m|min|minute)s?\b", "15m_only"),
    )
    for pattern, profile in patterns:
        if re.search(pattern, value) and (explicit_only or re.search(r"\b(?:trade|trading|setup|strategy|mode|scan)\b", value)):
            return PROFILES[profile]
    if re.search(
        r"\b(?:paper\s+(?:exploration|learning)|exploration\s+mode|"
        r"learn\s+from\s+paper\s+trades|more\s+paper\s+trades)\b",
        value,
    ):
        return PROFILES["paper_exploration"]
    if re.search(r"\b(?:adaptive|flexible)\s+(?:intraday|paper|trading)\b", value):
        return PROFILES["adaptive_intraday"]
    if re.search(r"\b(?:scalp|scalping)\b", value):
        return PROFILES["1m_only"]
    if re.search(r"\b(?:swing|positional|daily\s+strategy)\b", value):
        return PROFILES["swing"]
    return resolve_trading_profile(default)
