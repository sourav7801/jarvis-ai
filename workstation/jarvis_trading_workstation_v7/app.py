
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
HOST = os.getenv("JARVIS_WORKSTATION_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_WORKSTATION_PORT", "8787"))

OLLAMA_URL = os.getenv(
    "JARVIS_OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate",
)
OLLAMA_MODEL = os.getenv(
    "JARVIS_OLLAMA_MODEL",
    "llama3.2:3b",
)

SYMBOLS = {
    "NIFTY": ("NIFTY", "NIFTY 50"),
    "BANKNIFTY": ("BANKNIFTY", "BANKNIFTY"),
    "SENSEX": ("SENSEX", "SENSEX"),
    "GOLD": ("MCX:GOLD1!", "GOLD"),
    "SILVER": ("MCX:SILVER1!", "SILVER"),
    "CRUDE OIL": ("MCX:CRUDEOIL1!", "CRUDE OIL"),
    "NATURAL GAS": ("MCX:NATURALGAS1!", "NATURAL GAS"),
}

LAYOUTS = [1, 2, 3, 4, 6, 8]
CONVERSATION_CONTEXTS = (
    "master",
    "system",
    "mission",
    "web",
    "charts",
    "quant",
    "paper",
    "news",
    "company",
)
FYERS_NATIVE_CHART_SYMBOLS = {"NIFTY", "BANKNIFTY", "SENSEX"}

STATE = {
    "version": "V7",
    "status": "CONNECTED",
    "provider": "FYERS_NATIVE_CHARTS",
    "layout": 4,
    "charts": [
        {"symbol": "NIFTY", "label": "NIFTY 50", "interval": "5", "range": "3M"},
        {"symbol": "BANKNIFTY", "label": "BANKNIFTY", "interval": "5", "range": "3M"},
        {"symbol": "SENSEX", "label": "SENSEX", "interval": "5", "range": "3M"},
        {"symbol": "NIFTY", "label": "NIFTY 50", "interval": "15", "range": "3M"},
    ],
    "selected": 0,
    "messages": [],
    "conversations": {
        "master": [],
        "system": [],
        "mission": [],
        "web": [],
        "charts": [],
        "quant": [],
        "paper": [],
        "news": [],
        "company": [],
    },
    "message_id": 0,
    "events": [],
    "trade_candidates": [],
}
STATE["conversations"]["master"] = STATE["messages"]


def normalize_context(context: str) -> str:
    value = str(context or "master").strip().lower()
    if value not in CONVERSATION_CONTEXTS:
        raise ValueError(f"Unknown conversation context: {context}")
    return value


def conversation_messages(context: str = "master") -> list[dict[str, Any]]:
    return STATE["conversations"][normalize_context(context)]


def add_message(role: str, text: str, context: str = "master") -> None:
    conversation = conversation_messages(context)
    STATE["message_id"] += 1
    conversation.append(
        {
            "id": STATE["message_id"],
            "role": role,
            "text": text,
            "context": normalize_context(context),
            "ts": datetime.now().isoformat(),
        }
    )
    if len(conversation) > 100:
        del conversation[:-100]


def add_event(text: str, level: str = "INFO") -> None:
    STATE["events"].insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "text": text,
        },
    )
    STATE["events"] = STATE["events"][:40]


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[,.!?;:]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_symbol(text: str):
    aliases = [
        ("natural gas", "NATURAL GAS"),
        ("naturalgas", "NATURAL GAS"),
        ("crude oil", "CRUDE OIL"),
        ("crudeoil", "CRUDE OIL"),
        ("bank nifty", "BANKNIFTY"),
        ("banknifty", "BANKNIFTY"),
        ("nifty 50", "NIFTY"),
        ("nifty50", "NIFTY"),
        ("nifty", "NIFTY"),
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
    ]
    for alias, key in aliases:
        if alias in text:
            return key
    return None


def parse_range(text: str) -> tuple[str, str]:
    checks = [
        (r"\b(?:2|two)\s*months?\b", ("2M", "2 months")),
        (r"\b(?:3|three)\s*months?\b", ("3M", "3 months")),
        (r"\b(?:6|six)\s*months?\b", ("6M", "6 months")),
        (r"\b(?:1|one)\s*(?:year|yr)\b", ("12M", "1 year")),
        (r"\b(?:2|two)\s*(?:years?|yrs?)\b", ("24M", "2 years")),
        (r"\b(?:5|five)\s*(?:years?|yrs?)\b", ("60M", "5 years")),
        (r"\b(?:30|thirty)\s*days?\b", ("1M", "30 days")),
        (r"\b(?:60|sixty)\s*days?\b", ("2M", "60 days")),
        (r"\b(?:90|ninety)\s*days?\b", ("3M", "90 days")),
        (r"\blast\s*2\s*months?\b", ("2M", "last 2 months")),
        (r"\blast\s*3\s*months?\b", ("3M", "last 3 months")),
        (r"\blast\s*6\s*months?\b", ("6M", "last 6 months")),
        (r"\blast\s*(?:year|12\s*months?)\b", ("12M", "last 1 year")),
        (r"\blast\s*2\s*years?\b", ("24M", "last 2 years")),
    ]
    for pattern, value in checks:
        if re.search(pattern, text):
            return value
    return ("3M", "3 months")


def parse_interval(text: str) -> str:
    checks = [
        (r"\b1\s*(?:minute|min|m)\b", "1"),
        (r"\b3\s*(?:minute|min|m)\b", "3"),
        (r"\b5\s*(?:minute|min|m)\b", "5"),
        (r"\b15\s*(?:minute|min|m)\b", "15"),
        (r"\b30\s*(?:minute|min|m)\b", "30"),
        (r"\b1\s*hour\b", "60"),
        (r"\b2\s*hours?\b", "120"),
        (r"\b4\s*hours?\b", "240"),
        (r"\b(?:daily|1\s*day)\b", "D"),
        (r"\b(?:weekly|1\s*week)\b", "W"),
    ]
    for pattern, value in checks:
        if re.search(pattern, text):
            return value
    return "5"


def parse_news_query(text: str) -> str:
    query = normalize(text)
    query = re.sub(r"^jarvis\s+", "", query)
    query = re.sub(r"^(?:hi|hey|hello)\s+", "", query)
    query = re.sub(r"\btop\s+\d+\b", " ", query)
    query = re.sub(
        r"\b(?:show|give|find|open|load|read|tell|brief|summarize|speak|please|top|latest|current|today|me|the|what|is|are|news|headline|headlines|impact|impacting|about|on|for|to|related|regarding|concerning)\b",
        " ",
        query,
    )
    query = re.sub(r"\s+", " ", query).strip()
    return query or "India markets NIFTY Sensex"


def chart_request(text: str):
    t = normalize(text)
    symbol_key = parse_symbol(t)
    if not symbol_key:
        return None
    if not any(x in t for x in ("chart", "open", "show", "display", "history", "historical", "last")):
        return None

    range_value, range_label = parse_range(t)
    interval = parse_interval(t)
    tv_symbol, label = SYMBOLS[symbol_key]

    return {
        "symbol": tv_symbol,
        "label": label,
        "interval": interval,
        "range": range_value,
        "range_label": range_label,
        "native_supported": symbol_key in FYERS_NATIVE_CHART_SYMBOLS,
    }


def set_chart(index: int, chart: dict[str, Any]) -> None:
    while len(STATE["charts"]) < max(index + 1, 1):
        STATE["charts"].append(
            {"symbol": "NIFTY", "label": "NIFTY 50", "interval": "5", "range": "3M"}
        )
    STATE["charts"][index] = chart
    STATE["selected"] = index


def local_agent(text: str) -> dict[str, Any] | None:
    t = normalize(text)

    # layout commands
    m = re.search(r"\b([123468])\s*charts?\b", t)
    if m and any(k in t for k in ("show", "open", "display", "give", "make")):
        count = int(m.group(1))
        STATE["layout"] = count
        add_event(f"Chart layout changed to {count}.", "JARVIS")
        return {
            "action": "set_layout",
            "layout": count,
            "speech": f"Done. I switched the workstation to {count} charts.",
        }

    # compare command: "compare nifty and banknifty"
    if "compare" in t:
        found = []
        for key in ("NIFTY", "BANKNIFTY", "SENSEX", "GOLD", "SILVER", "CRUDE OIL", "NATURAL GAS"):
            if key.lower() in t:
                found.append(key)
        if len(found) >= 2:
            STATE["layout"] = min(max(len(found), 2), 8)
            for i, key in enumerate(found[:8]):
                tv_symbol, label = SYMBOLS[key]
                set_chart(
                    i,
                    {
                        "symbol": tv_symbol,
                        "label": label,
                        "interval": "5",
                        "range": "3M",
                    },
                )
            add_event(
                "Comparison workspace loaded: " + ", ".join(found[:8]),
                "JARVIS",
            )
            return {
                "action": "set_layout",
                "layout": STATE["layout"],
                "charts": STATE["charts"][:STATE["layout"]],
                "speech": (
                    "Done. I loaded a comparison workspace for "
                    + ", ".join(found[:8])
                    + "."
                ),
            }

    parsed = chart_request(text)
    if parsed:
        if not parsed.get("native_supported", False):
            return {
                "action": "chart_unavailable",
                "symbol": parsed["label"],
                "speech": (
                    f"I did not replace your chart with a blank {parsed['label']} panel. "
                    "FYERS requires an active MCX futures contract symbol for this "
                    "commodity; the friendly continuous symbol is not valid broker data."
                ),
            }
        set_chart(STATE["selected"], parsed)
        add_event(
            f"Chart opened: {parsed['label']} {parsed['range_label']} {parsed['interval']}.",
            "JARVIS",
        )
        return {
            "action": "set_chart",
            "slot": STATE["selected"],
            "chart": parsed,
            "charts": STATE["charts"][:STATE["layout"]],
            "speech": (
                f"Done. Opening {parsed['label']} for {parsed['range_label']} "
                f"on the {('daily' if parsed['interval'] == 'D' else parsed['interval'] + ' minute')} chart."
            ),
        }

    # Time-sensitive market questions must never fall through to free-form
    # chat, where a local language model could invent a current price. Indexes
    # use broker-backed Quant Lab; friendly commodity aliases use current,
    # source-attributed news until an active FYERS contract is supplied.
    market_symbol = parse_symbol(t)
    market_check = market_symbol and any(
        phrase in t
        for phrase in (
            "how is", "how it is", "how its", "how behaving", "how is it behaving",
            "check", "current", "latest", "price", "outlook", "trend", "future",
            "futures", "market update", "what is happening", "what's happening",
        )
    )
    if market_check and market_symbol in FYERS_NATIVE_CHART_SYMBOLS:
        return {
            "action": "open_quant",
            "symbol": market_symbol,
            "speech": (
                f"Opening verified multi-timeframe FYERS intelligence for {market_symbol}. "
                "I will not quote or infer a current market value without broker data."
            ),
        }
    if market_check and market_symbol in {"GOLD", "SILVER", "CRUDE OIL", "NATURAL GAS"}:
        return {
            "action": "open_quant",
            "symbol": market_symbol,
            "speech": (
                f"Opening verified multi-timeframe market intelligence for {market_symbol}. "
                "The canonical workstation resolves the current FYERS MCX contract automatically."
            ),
        }

    if re.search(r"\b(?:find(?:\s+the)?\s+trades?|scan|analy[sz]e)\b", t):
        requested_symbol = parse_symbol(t) or "BANKNIFTY"
        return {
            "action": "open_quant",
            "symbol": requested_symbol,
            "speech": (
                f"Opening read-only multi-timeframe intelligence for {requested_symbol}. "
                "I will use actual FYERS candles and keep every setup paper-only."
            ),
        }

    if "news" in t or "what news" in t or "impact" in t:
        query = parse_news_query(text)
        requested_limit = re.search(r"\btop\s+(\d+)\b", t)
        news_limit = min(max(int(requested_limit.group(1)), 1), 50) if requested_limit else 10
        auto_brief = any(
            word in t
            for word in ("read", "tell", "brief", "summarize", "speak")
        )
        return {
            "action": "open_news",
            "query": query,
            "limit": news_limit,
            "timespan": "1d" if any(word in t for word in ("today", "current")) else "3d",
            "auto_brief": auto_brief,
            "speech": (
                f"I will find and read a current headline briefing for {query}."
                if auto_brief
                else f"Loading the latest source headlines for {query}."
            ),
        }

    if "help" in t:
        return {
            "action": "help",
            "speech": (
                "Try: open Nifty 50 last 2 months. "
                "Give me 8 charts. Compare Nifty and BankNifty. "
                "Find trades on BankNifty. "
                "Show news impacting Nifty today. "
                "Or say: I have a company idea for..."
            ),
        }

    return None


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            return self.send_json(STATE)
        if path == "/":
            return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
        if path == "/style.css":
            return self.send_file(STATIC / "style.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self.send_file(STATIC / "app.js", "application/javascript; charset=utf-8")
        if path == "/api/health":
            return self.send_json({"ok": True, "version": "V7"})
        self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/agent":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode())
        except Exception:
            body = {}

        text = str(body.get("text", "")).strip()
        if not text:
            return self.send_json({"ok": False, "error": "Empty command."}, 400)

        add_message("user", text)
        result = local_agent(text)

        if result is None:
            result = {
                "action": "conversation_only",
                "speech": (
                    "I heard you. That request is not yet wired to a "
                    "deterministic trading action, so I will not pretend it ran."
                ),
            }

        add_message("assistant", result["speech"])
        result["messages"] = STATE["messages"]
        result["state"] = {
            "layout": STATE["layout"],
            "charts": STATE["charts"][:STATE["layout"]],
            "selected": STATE["selected"],
        }
        return self.send_json(result)

    def log_message(self, *args):
        pass


def main():
    print("=" * 60)
    print("JARVIS TRADING WORKSTATION V7")
    print("=" * 60)
    print(f"http://{HOST}:{PORT}")
    print("Pages: COMMAND CENTER | CHART LAB | QUANT LAB | NEWS")
    print("Layouts: 1 / 2 / 3 / 4 / 6 / 8")
    print("TradingView widget charts")
    print("Research / paper intelligence only")
    print("NO LIVE ORDERS")
    print()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
