from __future__ import annotations

import json
import re
import urllib.error
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

    if is_explicit_terminal_open(text):
        return True

    if not requested_symbols(text):
        return False

    return bool(_TRADING_ACTION_RE.search(normalize(text)))


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
    )

    for pattern, timeframe in patterns:
        if re.search(pattern, value):
            return timeframe

    return default


def monitor_requested(text: str) -> bool:
    value = normalize(text)
    return any(marker in value for marker in _MONITOR_MARKERS)


def _open_terminal_browser() -> bool:
    try:
        return bool(webbrowser.open(TRADING_URL, new=2))
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

    # Do not spawn a new browser tab for every scan/analyze follow-up.
    browser_opened = _open_terminal_browser() if explicit_open else False

    if monitor_requested(text) and symbols:
        sessions = _start_paper_monitors(
            symbols,
            timeframe,
            str(text or "").strip(),
        )

    terminal_agent = _post_terminal_agent(text)

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
        if speech:
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