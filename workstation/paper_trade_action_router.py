from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable


DEFAULT_TIMEFRAMES = ("5m", "15m", "1h")
MIN_SCORE = 68.0
MIN_RISK_REWARD = 1.8
MAX_ENTRY_DRIFT_FRACTION = 0.0075

_SYMBOL_ALIASES = (
    ("natural gas", "NATURALGAS"),
    ("naturalgas", "NATURALGAS"),
    ("crude oil", "CRUDEOIL"),
    ("crudeoil", "CRUDEOIL"),
    ("bank nifty", "BANKNIFTY"),
    ("banknifty", "BANKNIFTY"),
    ("nifty 50", "NIFTY"),
    ("nifty50", "NIFTY"),
    ("sensex", "SENSEX"),
    ("bitcoin", "BTC"),
    ("btc", "BTC"),
    ("ethereum", "ETH"),
    ("ether", "ETH"),
    ("eth", "ETH"),
    ("solana", "SOL"),
    ("sol", "SOL"),
    ("gold", "GOLD"),
    ("silver", "SILVER"),
    ("nifty", "NIFTY"),
)

_TRADE_ACTION_RE = re.compile(
    r"(?:\b(?:take|enter|execute|place|make|do|run)\b.{0,40}\b(?:paper\s+)?trad(?:e|ing)\b|"
    r"\bpaper\s+trad(?:e|ing)\b|"
    r"\b(?:take|enter|execute|place)\s+(?:a\s+)?trade\b)",
    flags=re.IGNORECASE,
)
_PLAIN_EXECUTE_RE = re.compile(r"^\s*execute\s*$", flags=re.IGNORECASE)
_PAPER_DESK_OPEN_RE = re.compile(
    r"^\s*(?:open|launch|show|start)\s+(?:the\s+)?paper\s+trading"
    r"(?:\s+(?:terminal|desk))?\s*$",
    flags=re.IGNORECASE,
)
_PAPER_STATUS_RE = re.compile(
    r"\b(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure|status)\b",
    flags=re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def resolve_trade_symbols(text: str) -> tuple[str, ...]:
    """Resolve supported markets with conservative speech/typing tolerance.

    This explicitly handles split words such as ``bitcoi n`` without adding a
    one-off typo every time.  Exact matches win; fuzzy matching is only used on
    one-to-three-token windows against known market aliases.
    """

    value = normalize_text(text)
    found: list[tuple[int, str]] = []

    for alias, symbol in _SYMBOL_ALIASES:
        for match in re.finditer(
            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
            value,
        ):
            found.append((match.start(), symbol))

    tokens = list(re.finditer(r"[a-z0-9]+", value))
    compact_aliases = [(_compact(alias), symbol) for alias, symbol in _SYMBOL_ALIASES]

    for start_index in range(len(tokens)):
        for width in (1, 2, 3):
            end_index = start_index + width
            if end_index > len(tokens):
                continue
            window = "".join(match.group(0) for match in tokens[start_index:end_index])
            if len(window) < 3:
                continue
            best_symbol = None
            best_ratio = 0.0
            for alias, symbol in compact_aliases:
                if not alias:
                    continue
                if window == alias:
                    best_symbol = symbol
                    best_ratio = 1.0
                    break
                if min(len(window), len(alias)) < 4:
                    continue
                ratio = SequenceMatcher(None, window, alias).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_symbol = symbol
            if best_symbol and best_ratio >= 0.86:
                found.append((tokens[start_index].start(), best_symbol))

    result: list[str] = []
    for _position, symbol in sorted(found, key=lambda item: item[0]):
        if symbol not in result:
            result.append(symbol)
    return tuple(result)


def is_paper_trade_action_request(text: str) -> bool:
    value = normalize_text(text)
    # Dashboard navigation and portfolio/status queries are owned by the
    # Paper Desk.  Only a market-specific command may cross into entry logic.
    if not resolve_trade_symbols(value):
        if _PAPER_DESK_OPEN_RE.fullmatch(value):
            return False
        if "paper" in value and _PAPER_STATUS_RE.search(value):
            return False
    return bool(_PLAIN_EXECUTE_RE.fullmatch(value) or _TRADE_ACTION_RE.search(value))


def _requested_timeframes(text: str) -> tuple[str, ...]:
    value = normalize_text(text)
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
            return (timeframe,)
    return DEFAULT_TIMEFRAMES


def _decision_rows(symbol: str, timeframes: Iterable[str]) -> list[dict[str, Any]]:
    from workstation.quant_firm_runtime import decision_payload

    rows: list[dict[str, Any]] = []
    for timeframe in timeframes:
        try:
            result = decision_payload(symbol, timeframe)
            row = dict(result) if isinstance(result, dict) else {}
        except Exception as exc:
            row = {
                "success": False,
                "symbol": symbol,
                "timeframe": timeframe,
                "message": f"{type(exc).__name__}: {exc}"[:300],
            }
        row.setdefault("symbol", symbol)
        row.setdefault("timeframe", timeframe)
        rows.append(row)
    return rows


def _consensus_payload(symbol: str, profile: str = "intraday") -> dict[str, Any]:
    from workstation.quant_terminal_v2 import scan_payload

    result = scan_payload(symbol, profile=profile)
    return dict(result) if isinstance(result, dict) else {}


def _qualified(row: dict[str, Any]) -> bool:
    return bool(
        row.get("success")
        and str(row.get("side") or "").upper() in {"LONG", "SHORT"}
        and float(row.get("score") or 0.0) >= MIN_SCORE
        and float(row.get("risk_reward") or 0.0) >= MIN_RISK_REWARD
        and row.get("entry") is not None
        and row.get("stop") is not None
        and row.get("target") is not None
    )


def _best_candidate(rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [dict(row) for row in rows if _qualified(row)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            float(row.get("score") or 0.0),
            float(row.get("risk_reward") or 0.0),
            {"1h": 3, "15m": 2, "5m": 1}.get(str(row.get("timeframe") or ""), 0),
        ),
        reverse=True,
    )
    return candidates[0]


def _already_open(symbol: str) -> dict[str, Any] | None:
    from workstation.paper_trading_desk import paper_desk

    snapshot = paper_desk.snapshot()
    for position in snapshot.get("positions") or []:
        if str(position.get("symbol") or "").upper() == symbol:
            return dict(position)
    return None


def _live_entry(candidate: dict[str, Any]) -> tuple[float | None, str | None]:
    from workstation.paper_trading_desk import live_mark_loader

    decision_entry = float(candidate["entry"])
    mark = live_mark_loader(str(candidate.get("symbol") or ""))
    if mark is None:
        return decision_entry, None

    mark = float(mark)
    if decision_entry <= 0 or mark <= 0:
        return None, "INVALID_MARK"
    drift = abs(mark - decision_entry) / decision_entry
    if drift > MAX_ENTRY_DRIFT_FRACTION:
        return None, "ENTRY_DRIFT_TOO_LARGE"

    side = str(candidate.get("side") or "").upper()
    stop = float(candidate["stop"])
    target = float(candidate["target"])
    if side == "LONG" and not (stop < mark < target):
        return None, "LIVE_MARK_OUTSIDE_SETUP"
    if side == "SHORT" and not (target < mark < stop):
        return None, "LIVE_MARK_OUTSIDE_SETUP"

    current_rr = abs(target - mark) / max(abs(mark - stop), 1e-12)
    if current_rr < 1.30:
        return None, "LIVE_RISK_REWARD_DEGRADED"
    return mark, None


def _arm_autonomy(profile: str = "intraday") -> dict[str, Any]:
    from workstation.paper_autonomy_engine import paper_autonomy

    return paper_autonomy.start(profile=profile, scan_now=True)


def _publish_event(payload: dict[str, Any]) -> None:
    try:
        from workstation.nautilus_core_client import publish_market_event

        publish_market_event(payload)
    except Exception:
        pass


def _speech_for_rows(symbol: str, rows: Iterable[dict[str, Any]]) -> str:
    pieces = []
    for row in rows:
        side = str(row.get("side") or "WAIT").upper()
        score = float(row.get("score") or 0.0)
        rr = row.get("risk_reward")
        rr_text = f" RR {float(rr):.2f}" if rr is not None else ""
        pieces.append(f"{row.get('timeframe')}: {side} {score:.1f}{rr_text}")
    return f"{symbol} evidence -> " + "; ".join(pieces)


def execute_paper_trade_request(text: str) -> dict[str, Any]:
    """Handle direct trade requests without ever bypassing Quant/risk gates.

    If a qualified setup exists, a synthetic position is opened in the
    persistent paper ledger.  If no setup qualifies, JARVIS arms autonomous
    paper scanning rather than forcing a low-quality trade.
    """

    from workstation.paper_trading_desk import paper_desk
    from workstation.trading_timeframe_profiles import requested_trading_profile

    symbols = resolve_trade_symbols(text)
    if not symbols:
        return {
            "success": False,
            "action": "paper_trade_context_required",
            "reason": "SUPPORTED_MARKET_REQUIRED",
            "speech": (
                "Execution is deterministic but no supported market was resolved. "
                "Say, for example, 'take trade in Bitcoin' or 'paper trade Nifty'. "
                "No trade was placed."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    symbol = symbols[0]
    profile_spec = requested_trading_profile(text)
    existing = _already_open(symbol)
    if existing is not None:
        return {
            "success": True,
            "action": "paper_trade_existing_position",
            "symbol": symbol,
            "position": existing,
            "speech": (
                f"A paper position in {symbol} is already open. JARVIS did not duplicate exposure."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    consensus = _consensus_payload(symbol, profile_spec.name)
    rows = list(consensus.get("decisions") or [])
    best = consensus if consensus.get("qualified") is True and _qualified(consensus) else None

    if best is None:
        autonomy = _arm_autonomy(profile_spec.name)
        _publish_event(
            {
                "type": "PAPER_TRADE_ARMED",
                "symbol": symbol,
                "provider": "JARVIS_QUANT_V5_4",
                "reason": "NO_CURRENT_QUALIFIED_SETUP",
            }
        )
        return {
            "success": True,
            "action": "paper_trade_armed",
            "symbol": symbol,
            "decisions": rows,
            "consensus": consensus,
            "autonomy": autonomy,
            "speech": (
                f"No current {symbol} setup clears the {profile_spec.description.lower()} "
                f"so JARVIS did not force a trade. {consensus.get('message') or _speech_for_rows(symbol, rows)} "
                "Autonomous paper scanning is armed and will enter only when the same qualified consensus appears."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    entry, live_rejection = _live_entry(best)
    if entry is None:
        autonomy = _arm_autonomy(profile_spec.name)
        return {
            "success": True,
            "action": "paper_trade_armed",
            "symbol": symbol,
            "candidate": best,
            "decisions": rows,
            "consensus": consensus,
            "risk_gate": live_rejection,
            "autonomy": autonomy,
            "speech": (
                f"{symbol} produced a candidate, but the live-entry validation rejected immediate paper entry: {live_rejection}. "
                "JARVIS did not chase the price. Autonomous paper scanning remains armed."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    now = datetime.now(timezone.utc)
    valuation_multiplier = 1.0
    try:
        from workstation.paper_market_data import PAPER_MARKET_DATA

        instrument_spec = PAPER_MARKET_DATA.instrument_spec(symbol)
    except Exception:
        return {
            "success": True,
            "action": "paper_trade_risk_rejected",
            "symbol": symbol,
            "candidate": best,
            "risk_gate": "INSTRUMENT_SPEC_UNAVAILABLE",
            "speech": "The setup is valid, but verified instrument accounting is unavailable. No synthetic exposure was opened.",
            "paper_only": True,
            "live_execution": False,
        }
    if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
        try:
            valuation_quote = PAPER_MARKET_DATA.quote(symbol)
            native_ltp = float(valuation_quote.get("native_ltp") or 0.0)
            valuation_ltp = float(valuation_quote.get("valuation_ltp") or 0.0)
            if not valuation_quote.get("success") or native_ltp <= 0 or valuation_ltp <= 0:
                raise ValueError("crypto valuation reference unavailable")
            valuation_multiplier = valuation_ltp / native_ltp
        except Exception:
            return {
                "success": True,
                "action": "paper_trade_risk_rejected",
                "symbol": symbol,
                "candidate": best,
                "risk_gate": "VALUATION_FX_UNAVAILABLE",
                "speech": "The crypto setup is valid, but the INR valuation reference is unavailable. No synthetic exposure was opened.",
                "paper_only": True,
                "live_execution": False,
            }
    result = paper_desk.open_position(
        symbol=symbol,
        side=str(best["side"]),
        entry=float(entry),
        stop=float(best["stop"]),
        target=float(best["target"]),
        quantity=None,
        timeframe=str(best.get("timeframe") or ""),
        strategy="QUANT_ENSEMBLE_V2_GOVERNED_CONSENSUS_V4_DIRECT",
        score=float(best.get("score") or 0.0),
        source="DIRECT_PAPER_TRADE_COMMAND",
        asset_type=(
            "CRYPTO"
            if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}
            else "COMMODITY"
            if symbol in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}
            else "MARKET"
        ),
        external_id=(
            f"direct:{symbol}:{best.get('timeframe')}:{now.strftime('%Y%m%dT%H%M')}"
        ),
        metadata={
            "regime": best.get("regime"),
            "risk_reward": best.get("risk_reward"),
            "votes": best.get("votes") or [],
            "decisions": best.get("decisions") or [],
            "alignment": best.get("alignment"),
            "decision_version": best.get("decision_version"),
            "evidence_graph": best.get("evidence_graph") or [],
            "contradictions": best.get("contradictions") or [],
            "reasons_not_to_trade": best.get("reasons_not_to_trade") or [],
            "command": str(text or "")[:500],
            "decision_entry": best.get("entry"),
            "profile": profile_spec.name,
            "initial_risk": abs(float(entry) - float(best["stop"])),
            "exit_policy": {
                "breakeven_at_r": 1.0,
                "trailing_at_r": 1.5,
                "trailing_distance_r": 0.75,
                "trailing_target_r": 1.5,
                "scale_out": [
                    {"at_r": 1.0, "fraction": 0.34},
                    {"at_r": 2.0, "fraction": 0.50},
                ],
                "max_hold_minutes": 10080 if profile_spec.name == "swing" else 390,
            },
        },
        valuation_multiplier=valuation_multiplier,
        instrument_spec=instrument_spec,
    )

    if not result.get("success"):
        autonomy = _arm_autonomy(profile_spec.name)
        return {
            "success": True,
            "action": "paper_trade_risk_rejected",
            "symbol": symbol,
            "candidate": best,
            "paper_result": result,
            "autonomy": autonomy,
            "speech": (
                f"{symbol} had a qualified setup, but the persistent portfolio risk gate rejected entry: {result.get('reason')}. "
                "No trade was forced; autonomous paper scanning remains armed."
            ),
            "paper_only": True,
            "live_execution": False,
        }

    _arm_autonomy(profile_spec.name)
    _publish_event(
        {
            "type": "PAPER_POSITION_OPENED",
            "symbol": symbol,
            "provider": "JARVIS_QUANT_V5_4",
            "side": result.get("side"),
            "entry": result.get("entry"),
            "stop": result.get("stop"),
            "target": result.get("target"),
            "score": best.get("score"),
            "regime": best.get("regime"),
        }
    )

    return {
        "success": True,
        "action": "paper_trade_opened",
        "symbol": symbol,
        "candidate": best,
        "consensus": consensus,
        "position": result,
        "decisions": rows,
        "speech": (
            f"Qualified {symbol} paper trade opened: {result.get('side')} at {float(result.get('entry') or 0):.4f}, "
            f"stop {float(result.get('stop') or 0):.4f}, target {float(result.get('target') or 0):.4f}, "
            f"Quant score {float(best.get('score') or 0):.1f}, regime {best.get('regime')}. "
            "The position is now managed by the paper risk engine."
        ),
        "paper_only": True,
        "live_execution": False,
    }


def paper_trade_action_payload(text: str) -> dict[str, Any] | None:
    if not is_paper_trade_action_request(text):
        return None
    return execute_paper_trade_request(text)
