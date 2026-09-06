from __future__ import annotations

import re
from typing import Any


_MISTAKE_RE = re.compile(
    r"\b(?:analy[sz]e|review|show|explain)?\s*(?:my\s+|the\s+)?(?:trading\s+)?mistakes?\b|"
    r"\bwhat\s+(?:did|have)\s+(?:you|jarvis)\s+learn(?:ed)?\b",
    flags=re.IGNORECASE,
)
_LEADERBOARD_RE = re.compile(
    r"\b(?:strategy|strategies)\s+(?:leaderboard|ranking|performance)\b|"
    r"\b(?:best|top)\s+(?:performing\s+)?strateg(?:y|ies)\b",
    flags=re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"\b(?:create|make|design|research|invent|develop|test)\s+(?:a\s+|new\s+)?(?:trading\s+)?strateg(?:y|ies)\b|"
    r"\bstrateg(?:y|ies)\s+(?:research|lab|generation|synthesis)\b",
    flags=re.IGNORECASE,
)
_EXPLAIN_RE = re.compile(
    r"\b(?:explain|show|analy[sz]e)\s+(?:the\s+|my\s+)?(?:current\s+)?(?:setup|quant\s+decision|market\s+structure|confluence)\b",
    flags=re.IGNORECASE,
)
_STATUS_RE = re.compile(
    r"\b(?:quant|trading)\s+(?:intelligence|brain|learning)\s+(?:status|state)\b|"
    r"\bjarvis\s+(?:trading\s+)?brain\s+(?:status|state)\b",
    flags=re.IGNORECASE,
)


def is_quant_intelligence_command(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        _MISTAKE_RE.search(value)
        or _LEADERBOARD_RE.search(value)
        or _RESEARCH_RE.search(value)
        or _EXPLAIN_RE.search(value)
        or _STATUS_RE.search(value)
    )


def _symbol(text: str, default: str = "BTC") -> str:
    value = str(text or "").lower()
    aliases = (
        ("natural gas", "NATURALGAS"),
        ("crude oil", "CRUDEOIL"),
        ("bank nifty", "BANKNIFTY"),
        ("nifty 50", "NIFTY"),
        ("bitcoin", "BTC"),
        ("btc", "BTC"),
        ("ethereum", "ETH"),
        ("ether", "ETH"),
        ("eth", "ETH"),
        ("solana", "SOL"),
        ("sensex", "SENSEX"),
        ("nifty", "NIFTY"),
        ("gold", "GOLD"),
        ("silver", "SILVER"),
        ("naturalgas", "NATURALGAS"),
        ("crudeoil", "CRUDEOIL"),
    )
    for alias, symbol in aliases:
        if alias in value:
            return symbol
    return default


def _timeframe(text: str, default: str = "15m") -> str:
    value = str(text or "").lower()
    patterns = (
        (r"\b1\s*(?:m|min|minute)s?\b", "1m"),
        (r"\b3\s*(?:m|min|minute)s?\b", "3m"),
        (r"\b5\s*(?:m|min|minute)s?\b", "5m"),
        (r"\b15\s*(?:m|min|minute)s?\b", "15m"),
        (r"\b30\s*(?:m|min|minute)s?\b", "30m"),
        (r"\b1\s*(?:h|hour)s?\b", "1h"),
        (r"\b2\s*(?:h|hour)s?\b", "2h"),
        (r"\b4\s*(?:h|hour)s?\b", "4h"),
        (r"\b1\s*(?:d|day)s?\b", "1d"),
    )
    for pattern, timeframe in patterns:
        if re.search(pattern, value):
            return timeframe
    return default


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def _decision_speech(result: dict[str, Any]) -> str:
    structure = result.get("structure") if isinstance(result.get("structure"), dict) else {}
    indicators = result.get("indicators") if isinstance(result.get("indicators"), dict) else {}
    top_votes = list(result.get("votes") or [])[:6]
    vote_text = "; ".join(
        f"{vote.get('strategy')} {vote.get('side')} {float(vote.get('score') or 0):.0f}"
        for vote in top_votes
    ) or "no qualified strategy votes"
    return (
        f"Adaptive Quant Brain {result.get('symbol')} {result.get('timeframe')}: "
        f"{result.get('side')} score {_fmt(result.get('score'),1)}, regime {result.get('regime')}. "
        f"Structure {structure.get('bias')}, BOS {structure.get('bos')}, CHOCH {structure.get('choch')}, "
        f"liquidity {structure.get('liquidity_sweep')}. "
        f"Nearest support {_fmt(structure.get('nearest_support'))}, resistance {_fmt(structure.get('nearest_resistance'))}. "
        f"RSI {_fmt(indicators.get('rsi14'),1)}, ADX {_fmt(indicators.get('adx'),1)}, "
        f"RVOL {_fmt(indicators.get('relative_volume'),2)}, MACD hist {_fmt(indicators.get('macd_hist'),4)}. "
        f"Entry {_fmt(result.get('entry'))}, stop {_fmt(result.get('stop'))}, target {_fmt(result.get('target'))}, "
        f"RR {_fmt(result.get('risk_reward'),2)}. Top evidence: {vote_text}."
    )


def quant_intelligence_command_payload(text: str) -> dict[str, Any] | None:
    value = str(text or "").strip()
    if not is_quant_intelligence_command(value):
        return None

    from omni.trading_intelligence.trade_learning_engine import learning_engine

    if _MISTAKE_RE.search(value):
        report = learning_engine.mistake_report()
        ranked = report.get("ranked_mistakes") or []
        if ranked:
            summary = ", ".join(f"{row['mistake']}={row['count']}" for row in ranked[:8])
        else:
            summary = "No statistically meaningful mistake pattern has been recorded yet."
        return {
            "success": True,
            "action": "quant_mistake_report",
            "report": report,
            "speech": (
                "JARVIS mistake analysis: " + summary + ". "
                "These are research hypotheses only; production strategy logic is not rewritten from a few trades."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    if _LEADERBOARD_RE.search(value):
        leaderboard = learning_engine.strategy_leaderboard()
        if leaderboard:
            summary = "; ".join(
                f"{row['strategy']} trades={row['trades']} avgR={_fmt(row.get('avg_r'),2)} weight={_fmt(row.get('weight'),3)}"
                for row in leaderboard[:8]
            )
        else:
            summary = "No strategy has enough closed paper outcomes for a leaderboard yet."
        return {
            "success": True,
            "action": "quant_strategy_leaderboard",
            "leaderboard": leaderboard,
            "speech": "Strategy leaderboard: " + summary,
            "paper_only": True,
            "live_execution": False,
        }

    if _RESEARCH_RE.search(value):
        from omni.trading_intelligence.strategy_research_lab import research_candidates
        from workstation.quant_terminal_v2 import candles_payload

        symbol = _symbol(value)
        timeframe = _timeframe(value)
        market = candles_payload(symbol, timeframe, 950)
        candles = list(market.get("candles") or []) if market.get("success") else []
        if len(candles) < 120:
            return {
                "success": False,
                "action": "quant_strategy_research",
                "symbol": symbol,
                "timeframe": timeframe,
                "speech": f"Strategy research for {symbol} could not run because verified historical data is insufficient.",
                "paper_only": True,
                "live_execution": False,
            }
        research = research_candidates(symbol, timeframe, candles)
        best = research.get("best_candidate") or {}
        candidate = best.get("candidate") or {}
        backtest = best.get("backtest") or {}
        speech = (
            f"Strategy Lab completed {symbol} {timeframe} research. Best candidate {candidate.get('name','N/A')} "
            f"status {best.get('status','REJECT')}, trades {backtest.get('trades',0)}, "
            f"expectancy {_fmt(backtest.get('expectancy_r'),3)}R, profit factor {_fmt(backtest.get('profit_factor'),2)}, "
            f"max drawdown {_fmt(backtest.get('max_drawdown_r'),2)}R. "
            "Candidates remain research/paper challengers until robustness gates pass."
        )
        return {
            "success": True,
            "action": "quant_strategy_research",
            "symbol": symbol,
            "timeframe": timeframe,
            "research": research,
            "speech": speech,
            "paper_only": True,
            "live_execution": False,
        }

    if _EXPLAIN_RE.search(value):
        from workstation.quant_firm_runtime import decision_payload

        symbol = _symbol(value)
        timeframe = _timeframe(value)
        result = decision_payload(symbol, timeframe)
        return {
            "success": bool(result.get("success")),
            "action": "quant_adaptive_explanation",
            "symbol": symbol,
            "timeframe": timeframe,
            "decision": result,
            "speech": _decision_speech(result) if result.get("success") else str(result.get("message") or "Adaptive decision unavailable."),
            "paper_only": True,
            "live_execution": False,
        }

    status = learning_engine.status()
    return {
        "success": True,
        "action": "quant_intelligence_status",
        "status": status,
        "speech": (
            "Adaptive Quant Brain is enabled in paper/research mode. It combines market structure, support/resistance, "
            "BOS/CHOCH, FVG, liquidity sweeps, candlestick patterns, multi-indicator confluence, regime weighting, "
            "bounded outcome learning and governed strategy research. Live broker execution remains locked."
        ),
        "paper_only": True,
        "live_execution": False,
    }
