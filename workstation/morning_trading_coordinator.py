from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any


_START_RE = re.compile(
    r"^\s*(?:hi\s+)?(?:jarvis[, ]+)?(?:please\s+)?(?:start|begin|run|enable|arm)\b"
    r".*\b(?:trading|trading system|trading autopilot|market scan|paper desk)\b",
    flags=re.IGNORECASE,
)


def is_morning_start_request(text: str) -> bool:
    return bool(_START_RE.match(str(text or "")))


def start_morning_paper_workflow(
    *,
    profile: str = "adaptive_intraday",
    universes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    from workstation.bounded_decision_review import decision_review_coordinator
    from workstation.multi_market_scanner import DEFAULT_MORNING_UNIVERSES, multi_market_scanner
    from workstation.paper_portfolio_controller import paper_portfolio_controller
    from workstation.trading_timeframe_profiles import resolve_trading_profile

    profile_spec = resolve_trading_profile(profile)
    selected_universes = tuple(universes or DEFAULT_MORNING_UNIVERSES)
    reviewer = decision_review_coordinator.start()
    portfolio = paper_portfolio_controller.start(intraday_profile=profile_spec.name)
    autonomy = portfolio.get("mandates", {}).get("INTRADAY", {})
    scanner = multi_market_scanner.start(
        universes=selected_universes,
        force=True,
        auto_enroll=True,
        profile=profile_spec.name,
        continuous=True,
        interval_seconds=300.0,
    )
    return {
        "success": True,
        "action": "start_morning_paper_workflow",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "autonomy": autonomy,
        "paper_portfolio_controller": portfolio,
        "multi_market_scanner": scanner,
        "decision_review": reviewer,
        "profile": profile_spec.to_dict(),
        "selected_universes": list(selected_universes),
        "workflow": [
            "refresh governed NIFTY 50, BANKNIFTY, SENSEX, index, MCX and crypto universes",
            "repeat broad discovery every five minutes while AUTO remains on",
            "scan completed-bar breakout and breakdown structure",
            "enroll a bounded eligible shortlist into the governed paper watchlist",
            "run 50% intraday, 30% swing and 20% long-only investment paper risk buckets",
            "size from stop distance and portfolio risk",
            "mark open paper positions and close at synthetic stop or target",
            "review closed paper decisions and only tighten weak cohort gates",
        ],
        "speech": (
            "JARVIS all-day paper portfolio started: 50 percent intraday, 30 percent swing "
            "and 20 percent long-only investment. "
            "It is scanning NIFTY 50, BANKNIFTY, SENSEX, Indian indices, MCX and crypto, "
            "will enroll a bounded eligible shortlist, and will only open synthetic positions after "
            "5 and 15 minute agreement, score, pattern or compatible-strategy, risk/reward, "
            "fresh-price, session and portfolio-risk gates pass. "
            "It will not force a position when the evidence gates reject a setup. "
            "Real broker and crypto-exchange orders remain locked."
        ),
        "paper_only": True,
        "live_execution": False,
    }


def morning_command_payload(text: str) -> dict[str, Any] | None:
    if not is_morning_start_request(text):
        return None
    from workstation.multi_market_scanner import _requested_universes
    from workstation.trading_timeframe_profiles import requested_trading_profile

    profile = requested_trading_profile(text)
    requested = _requested_universes(text)
    universes = requested if requested != ("NIFTY50",) or re.search(r"nifty\s*50", text, re.I) else None
    return start_morning_paper_workflow(profile=profile.name, universes=universes)
