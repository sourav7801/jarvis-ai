from __future__ import annotations

import re
from typing import Any


INDICATOR_SET = ("EMA20", "EMA50", "VWAP", "BB20", "RSI14")

_SIGNAL_REQUEST_RE = re.compile(
    r"\b(?:analy[sz]e|analysis|chart|signal|setup|entry|buy|sell|trade|wait|"
    r"trend|indicator|support|resistance|stop|target)\b",
    flags=re.IGNORECASE,
)


def _chart(symbol: str, timeframe: str) -> dict[str, Any]:
    from workstation.quant_terminal_v2 import symbol_metadata

    metadata = symbol_metadata(symbol)
    return {
        "symbol": symbol,
        "label": metadata.get("label") or symbol,
        "kind": metadata.get("kind") or metadata.get("market") or "INDIA",
        "provider": metadata.get("provider"),
        "timeframe": timeframe,
        "layout": 1,
        "indicators": list(INDICATOR_SET),
        "auto_scan": True,
        "live": True,
    }


def _research_signal(decision: dict[str, Any]) -> str:
    side = str(decision.get("side") or "WAIT").upper()
    return {"LONG": "BUY", "SHORT": "SELL"}.get(side, "WAIT")


def _explain(symbol: str, timeframe: str, decision: dict[str, Any]) -> str:
    if not decision.get("success"):
        return (
            f"I opened the {symbol} {timeframe} signal chart, but verified market data "
            f"is unavailable: {decision.get('message') or 'no current decision'}. "
            "The safe signal is WAIT."
        )

    signal = _research_signal(decision)
    score = float(decision.get("score") or 0.0)
    regime = str(decision.get("regime") or "UNKNOWN").replace("_", " ")
    votes = list(decision.get("votes") or [])
    evidence = []
    for vote in votes[:3]:
        name = str(vote.get("strategy") or "strategy").replace("_", " ")
        side = str(vote.get("side") or "WAIT")
        evidence.append(f"{name} {side}")
    evidence_text = ", ".join(evidence) if evidence else "no strategy agreement"

    levels = ""
    if decision.get("entry") is not None:
        levels = (
            f" Entry {float(decision['entry']):.2f}, stop {float(decision['stop']):.2f}, "
            f"target {float(decision['target']):.2f}, reference R:R "
            f"{float(decision.get('risk_reward') or 0.0):.2f}."
        )
    conditional = ""
    if decision.get("research_candidate") and not decision.get("qualified"):
        conditional = (
            " These are conditional research levels only; the session/data eligibility gate "
            "blocks an automatic paper entry right now."
        )
    return (
        f"Opened the live {symbol} {timeframe} signal terminal. Paper signal: {signal}, "
        f"score {score:.1f}, regime {regime}; evidence: {evidence_text}.{levels} "
        f"This is a research and paper-trading signal, not a live broker order.{conditional}"
    )


def is_signal_terminal_request(text: str) -> bool:
    from workstation.quant_terminal_bridge import requested_symbols

    return bool(requested_symbols(text) and _SIGNAL_REQUEST_RE.search(str(text or "")))


def attach_signal_chart(text: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach a deterministic chart directive without changing action semantics."""

    from workstation.quant_terminal_bridge import requested_symbols, requested_timeframe

    result = dict(payload)
    symbols = requested_symbols(text)
    symbol = str(result.get("symbol") or (symbols[0] if symbols else "")).upper()
    if not symbol:
        return result
    timeframe = requested_timeframe(text, default="5m")
    result["chart"] = _chart(symbol, timeframe)
    result["paper_only"] = True
    result["live_execution"] = False
    return result


def signal_terminal_payload(text: str) -> dict[str, Any] | None:
    if not is_signal_terminal_request(text):
        return None

    from workstation.quant_terminal_bridge import requested_symbols, requested_timeframe
    from workstation.quant_terminal_v2 import scan_payload
    from workstation.trading_timeframe_profiles import requested_trading_profile

    symbol = requested_symbols(text)[0]
    timeframe = requested_timeframe(text, default="5m")
    profile = requested_trading_profile(
        text,
        default=("swing" if timeframe == "1d" or re.search(r"\b(?:swing|positional|daily)\b", text, re.I) else "intraday"),
    ).name
    try:
        decision = scan_payload(symbol, profile=profile)
    except Exception as exc:
        decision = {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "side": "WAIT",
            "score": 0.0,
            "message": f"{type(exc).__name__}: {exc}"[:300],
            "paper_only": True,
            "live_execution": False,
        }

    return {
        "success": bool(decision.get("success")),
        "action": "open_signal_chart",
        "symbol": symbol,
        "timeframe": timeframe,
        "profile": profile,
        "signal": _research_signal(decision),
        "decision": decision,
        "chart": _chart(symbol, timeframe),
        "speech": _explain(symbol, timeframe, decision),
        "paper_only": True,
        "live_execution": False,
    }
