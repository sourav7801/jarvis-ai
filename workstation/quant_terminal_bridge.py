from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

TRADING_HOST = "127.0.0.1"
TRADING_PORT = 8787
TRADING_URL = f"http://{TRADING_HOST}:{TRADING_PORT}"

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
    ("gold", "GOLD"),
    ("silver", "SILVER"),
    ("bitcoin", "BTC"),
    ("btc", "BTC"),
    ("ethereum", "ETH"),
    ("ether", "ETH"),
    ("eth", "ETH"),
    ("solana", "SOL"),
    ("sol", "SOL"),
    ("nifty", "NIFTY"),
)
_TERMINAL_NAMES = (
    "trading terminal",
    "trading intelligence",
    "quant trading",
    "quant terminal",
    "trading workstation",
)
_OPEN_VERBS = ("open", "launch", "start", "show")
_MONITOR_MARKERS = ("keep eye", "keep an eye", "watch", "monitor")
_PAPER_DESK_OPEN_RE = re.compile(
    r"\b(?:open|launch|show|start)\s+(?:the\s+)?paper\s+trading(?:\s+(?:terminal|desk))?\b",
    flags=re.IGNORECASE,
)
_PAPER_DESK_REQUEST_RE = re.compile(
    r"\b(?:"
    r"paper\s+(?:trading\s+)?(?:portfolio|positions?|p\s*(?:&|and)?\s*l|pnl|risk|exposure)|"
    r"my\s+paper\s+(?:trading\s+)?positions?|"
    r"current\s+paper\s+(?:trading\s+)?portfolio|"
    r"(?:open|launch|show|start)\s+(?:the\s+)?paper\s+trading(?:\s+(?:terminal|desk))?|"
    r"(?:start|stop|enable|disable|run|turn\s+on|turn\s+off)\s+(?:autonomous|automatic|auto)\s+paper\s+trading|"
    r"(?:autonomous|automatic|auto)\s+paper\s+trading\s+(?:status|state)"
    r")\b",
    flags=re.IGNORECASE,
)
_TRADING_ACTION_RE = re.compile(
    r"\b(?:"
    r"scan|analy[sz]e|watch|monitor|"
    r"trade|trades|trading|setup|setups|"
    r"scalp|scalping|intraday|breakout|"
    r"vwap|fvg|fair value gap|option chain|option|call|put|expiry|"
    r"open interest|oi|buy|sell|paper trade|paper trading"
    r")\b",
    flags=re.IGNORECASE,
)
_TERMINAL_DIAGNOSTIC_RE = re.compile(
    r"\b(?:scan|check|diagnos(?:e|is)|inspect|fix|repair|self[- ]?heal|why)\b"
    r"[^.]{0,100}\b(?:quant|trading)\b[^.]{0,80}"
    r"\b(?:window|terminal|chart|charts|data|loading|working)\b|"
    r"\b(?:quant|trading)\b[^.]{0,100}"
    r"\b(?:chart|charts|window|terminal)\b[^.]{0,80}"
    r"\b(?:not loading|blank|stuck|not working|failed|broken|fix|repair)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class QuantTerminalDispatch:
    success: bool
    response: str
    workspace_actions: tuple[dict, ...]
    symbols: tuple[str, ...]
    monitor_sessions: tuple[str, ...]
    terminal_agent: dict | None
    browser_opened: bool
    paper_only: bool = True
    live_execution: bool = False

    def to_dict(self):
        return {
            "success": self.success,
            "response": self.response,
            "workspace_actions": list(self.workspace_actions),
            "symbols": list(self.symbols),
            "monitor_sessions": list(self.monitor_sessions),
            "terminal_agent": self.terminal_agent,
            "browser_opened": self.browser_opened,
            "paper_only": self.paper_only,
            "live_execution": self.live_execution,
        }


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def requested_symbols(text: str) -> tuple[str, ...]:
    """Resolve supported markets in the same order the user mentioned them.

    Longer aliases win when aliases overlap, e.g. ``bank nifty`` beats the
    nested ``nifty`` token and ``nifty 50`` beats ``nifty``.
    """

    value = normalize(text)
    candidates = []

    for alias, symbol in _SYMBOL_ALIASES:
        for match in re.finditer(
            rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
            value,
        ):
            start, end = match.span()
            candidates.append((start, -(end - start), end, symbol))

    candidates.sort()

    found = []
    occupied = []

    for start, _negative_length, end, symbol in candidates:
        if any(
            start < right and end > left
            for left, right in occupied
        ):
            continue

        occupied.append((start, end))

        if symbol not in found:
            found.append(symbol)

    # Recover narrowly-scoped speech splits/typos such as ``bitcoi n`` using
    # the same resolver as deterministic paper execution.  Exact matches
    # above remain authoritative and fuzzy results only fill missing markets.
    try:
        from workstation.paper_trade_action_router import resolve_trade_symbols

        for symbol in resolve_trade_symbols(text):
            if symbol not in found:
                found.append(symbol)
    except Exception:
        pass

    try:
        from workstation.equity_universe import resolve_equity_symbols_from_text

        for symbol in resolve_equity_symbols_from_text(text):
            if symbol not in found:
                found.append(symbol)
    except Exception:
        pass

    return tuple(found)


def _looks_like_terminal_phrase(value: str) -> bool:
    """Recognize explicit terminal names even with small speech/typing errors.

    Voice transcription commonly drops a character from ``terminal``.  Keep
    this tolerance narrowly scoped to phrases such as ``trading <terminal>``
    so ordinary uses of the word trading are not hijacked by the Quant router.
    """

    if any(name in value for name in _TERMINAL_NAMES):
        return True

    words = re.findall(r"[a-z0-9]+", value)
    for index, word in enumerate(words[:-1]):
        if word not in {"trading", "quant"}:
            continue
        candidate = words[index + 1]
        if SequenceMatcher(None, candidate, "terminal").ratio() >= 0.72:
            return True

    return False


def is_explicit_terminal_open(text: str) -> bool:
    value = normalize(text)
    if _PAPER_DESK_OPEN_RE.search(value):
        return True
    return (
        _looks_like_terminal_phrase(value)
        and any(verb in value for verb in _OPEN_VERBS)
    )


def is_quant_terminal_request(text: str) -> bool:
    """Route explicit terminal opens and supported market trading commands.

    A user should not have to repeat "open trading terminal" before every
    follow-up.  Requests such as "scan Nifty 50" or "analyze crude oil" go
    directly to Quant Trading Intelligence, while ordinary factual questions
    such as "what is Nifty 50" stay with Master JARVIS.
    """

    if is_explicit_terminal_open(text) or is_terminal_diagnostic_request(text):
        return True

    if _PAPER_DESK_REQUEST_RE.search(normalize(text)):
        return True

    from workstation.nautilus_universe_router import is_universe_scan_request

    if is_universe_scan_request(text):
        return True

    from workstation.paper_trade_action_router import is_paper_trade_action_request
    from workstation.quant_intelligence_commands import is_quant_intelligence_command

    if is_paper_trade_action_request(text) or is_quant_intelligence_command(text):
        return True

    if not requested_symbols(text):
        return False

    return bool(_TRADING_ACTION_RE.search(normalize(text)))


def is_terminal_diagnostic_request(text: str) -> bool:
    return bool(_TERMINAL_DIAGNOSTIC_RE.search(normalize(text)))


def requested_timeframe(text: str, default: str = "15m") -> str:
    value = normalize(text)
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
        (r"\b(?:daily|day\s+chart|swing)\b", "1d"),
    )

    for pattern, timeframe in patterns:
        if re.search(pattern, value):
            return timeframe

    return default


def monitor_requested(text: str) -> bool:
    value = normalize(text)
    return any(marker in value for marker in _MONITOR_MARKERS)


def _open_terminal_browser(symbol: str | None = None, timeframe: str = "5m") -> bool:
    try:
        url = TRADING_URL
        if symbol:
            query = urllib.parse.urlencode(
                {"symbol": symbol, "timeframe": timeframe, "analyze": "1"}
            )
            url = f"{TRADING_URL}/?{query}"
        return bool(webbrowser.open(url, new=2))
    except Exception:
        return False


def _post_terminal_agent(text: str, timeout: float = 1.5):
    payload = json.dumps(
        {
            "text": str(text or "").strip(),
            "context": "master",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        TRADING_URL + "/api/agent",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            value = json.loads(raw)
            return value if isinstance(value, dict) else {"result": value}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _terminal_json(path: str, method: str = "GET", timeout: float = 8.0):
    body = b"{}" if method == "POST" else None
    request = urllib.request.Request(
        TRADING_URL + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _start_terminal_service() -> bool:
    if _terminal_json("/api/health", timeout=1.0):
        return True
    try:
        from pathlib import Path
        from omni.runtime_paths import fyers_python

        root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["JARVIS_WORKSTATION_PORT"] = str(TRADING_PORT)
        flags = 0
        if os.name == "nt":
            flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        subprocess.Popen(
            [str(fyers_python()), "-m", "workstation.quant_terminal_v2"],
            cwd=str(root),
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except Exception:
        return False

    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        if _terminal_json("/api/health", timeout=0.8):
            return True
        time.sleep(0.2)
    return False


def diagnose_and_repair_terminal() -> dict:
    started = _start_terminal_service()
    health = _terminal_json("/api/health", timeout=3.0) if started else None
    provider = _terminal_json("/api/provider", timeout=4.0) if health else None
    probe = (
        _terminal_json("/api/candles?symbol=BTC&timeframe=5m&bars=80", timeout=12.0)
        if health
        else None
    )
    actions = []

    if health and provider and str(provider.get("state") or "") not in {"CONNECTED", "LOGIN_REQUIRED"}:
        restarted = _terminal_json("/api/market/restart", method="POST", timeout=8.0)
        if restarted is not None:
            actions.append("restarted the read-only FYERS data bridge")
            provider = _terminal_json("/api/provider", timeout=4.0) or provider

    cache_busted_url = (
        f"{TRADING_URL}/?symbol=BTC&timeframe=5m&analyze=1&repair={int(time.time())}"
    )
    browser_opened = False
    if health:
        try:
            browser_opened = bool(webbrowser.open(cache_busted_url, new=2))
        except Exception:
            browser_opened = False
        actions.append("opened a fresh cache-busted Quant Terminal")

    data_ok = bool(probe and probe.get("success") and probe.get("candles"))
    terminal_ok = bool(health)
    if terminal_ok and data_ok:
        diagnosis = (
            f"I checked the Quant Terminal directly. Its service is healthy and the candle API returned "
            f"{int(probe.get('bars') or len(probe.get('candles') or []))} verified BTC 5 minute bars. "
            "The blank LOADING panels were a browser chart-rendering failure, not missing crypto data."
        )
    elif terminal_ok:
        diagnosis = (
            "I reached the Quant Terminal, but its candle probe did not return verified data. "
            f"Provider state is {str((provider or {}).get('state') or 'UNKNOWN').replace('_', ' ')}."
        )
    else:
        diagnosis = "The Quant Terminal service did not become reachable after an automatic restart attempt."

    if actions:
        diagnosis += " Automatic repair: " + "; ".join(actions) + "."
    if not browser_opened and health:
        diagnosis += f" If the repaired tab did not open, use {cache_busted_url}."
    diagnosis += " Live broker execution remains locked."

    return {
        "success": terminal_ok and data_ok,
        "speech": diagnosis,
        "health": health,
        "provider": provider,
        "probe": {
            "success": data_ok,
            "source": (probe or {}).get("source"),
            "bars": (probe or {}).get("bars"),
            "message": (probe or {}).get("message"),
        },
        "repair_actions": actions,
        "browser_opened": browser_opened,
        "paper_only": True,
        "live_execution": False,
    }


def _start_paper_monitors(
    symbols: Iterable[str],
    timeframe: str,
    request: str,
) -> tuple[str, ...]:
    from omni.paper_trade_monitor import paper_trade_monitor

    session_ids = []
    for symbol in symbols:
        result = paper_trade_monitor.start(
            symbol,
            timeframe,
            request=request,
        )
        session_id = str(result.get("session_id") or "").strip()
        if session_id:
            session_ids.append(session_id)

    return tuple(session_ids)


def dispatch_quant_terminal(text: str) -> QuantTerminalDispatch:
    symbols = requested_symbols(text)
    timeframe = requested_timeframe(text)
    sessions = ()
    explicit_open = is_explicit_terminal_open(text)

    if is_terminal_diagnostic_request(text):
        diagnosis = diagnose_and_repair_terminal()
        return QuantTerminalDispatch(
            success=bool(diagnosis.get("success")),
            response=str(diagnosis.get("speech") or "Quant Terminal diagnostics completed."),
            workspace_actions=(),
            symbols=(),
            monitor_sessions=(),
            terminal_agent=diagnosis,
            browser_opened=bool(diagnosis.get("browser_opened")),
        )

    if monitor_requested(text) and symbols:
        sessions = _start_paper_monitors(
            symbols,
            timeframe,
            str(text or "").strip(),
        )

    terminal_agent = _post_terminal_agent(text)
    chart_requested = bool(
        isinstance(terminal_agent, dict)
        and (
            terminal_agent.get("chart")
            or str(terminal_agent.get("action") or "") == "open_signal_chart"
        )
    )
    browser_opened = (
        _open_terminal_browser(symbols[0] if symbols else None, timeframe)
        if explicit_open or chart_requested
        else False
    )

    response_parts = []

    if explicit_open:
        response_parts.append("Quant Trading Intelligence terminal opened.")
    else:
        response_parts.append("Quant Trading Intelligence accepted the market command.")

    if symbols:
        response_parts.append(
            "Requested markets: " + ", ".join(symbols) + "."
        )

    if sessions:
        response_parts.append(
            "Paper-only background monitors started for "
            + ", ".join(symbols)
            + f" on {timeframe}."
        )
    elif monitor_requested(text):
        response_parts.append(
            "I did not start a background monitor because no supported instrument "
            "was resolved from the request."
        )

    if isinstance(terminal_agent, dict):
        speech = str(terminal_agent.get("speech") or "").strip()
        action = str(terminal_agent.get("action") or "").strip().lower()
        unwired = (
            action == "conversation_only"
            or "not wired to a deterministic trading action" in speech.lower()
        )
        if speech and not (explicit_open and unwired):
            response_parts.append(speech)
    else:
        response_parts.append(
            "The trading workstation command service is unavailable or still starting."
        )

    if explicit_open and not browser_opened:
        response_parts.append(
            f"If the browser did not open automatically, use {TRADING_URL}."
        )

    response_parts.append("Live broker execution remains locked.")

    return QuantTerminalDispatch(
        success=True,
        response=" ".join(response_parts),
        workspace_actions=(),
        symbols=symbols,
        monitor_sessions=sessions,
        terminal_agent=terminal_agent,
        browser_opened=browser_opened,
    )
