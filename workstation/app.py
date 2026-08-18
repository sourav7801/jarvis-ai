"""Canonical authenticated local workstation for OMNI-JARVIS."""

from __future__ import annotations

import hmac
import json
import math
import re
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import main as jarvis_main
from config import (
    LIVE_TRADING_ENABLED,
    WORKSTATION_API_TOKEN,
    WORKSTATION_HOST,
    WORKSTATION_PORT,
)
from omni.runtime import audit_event, get_audit_store, get_memory_store
from omni.company_os import COMPANY_OS
from omni.control_plane import ControlPlane, is_control_plane_request
from omni.mission_control import is_mission_request
from omni.agent_registry import AgentRequest
from agents.universal_operator_agent import is_operator_request
from agents.web_intelligence_agent import WEB_INTELLIGENCE_AGENT, is_web_request
from tools.capabilities import capabilities_for
from tools.registry import list_tools
from agents.fyers_data_adapter import get_intraday_data
from workstation.jarvis_trading_workstation_v7 import app as v7
from workstation.market_news import search_market_news
from workstation.market_runtime import MARKET_RUNTIME
from workstation.paper_market_data import ASSET_UNIVERSE, PAPER_MARKET_DATA
from workstation.paper_runtime import PAPER_RUNTIME
from workstation.news_briefing import (
    build_news_briefing,
    latest_news,
    parse_news_followup,
    remember_news,
)
from workstation.trading_intelligence import analyze_symbol


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "jarvis_trading_workstation_v7" / "static"
MAX_BODY_BYTES = 64 * 1024
MAX_COMMAND_CHARS = 4_000
COMMAND_LOCK = threading.RLock()
CANDLE_LOCK = threading.RLock()
CANDLE_CACHE: dict[tuple[str, str, int], tuple[float, dict[str, Any]]] = {}
CANDLE_CACHE_TTL_SECONDS = 15.0
MAX_CANDLE_BARS = 7_500
API_TOKEN = WORKSTATION_API_TOKEN or secrets.token_urlsafe(32)
MISSION_CONTROL = jarvis_main.MISSION_CONTROL
CONTROL_PLANE = ControlPlane(Path(__file__).resolve().parents[1])


def _loopback_host(host: str) -> bool:
    return host.lower() in {"127.0.0.1", "localhost", "::1"}


if not _loopback_host(WORKSTATION_HOST) and not WORKSTATION_API_TOKEN:
    raise RuntimeError(
        "A configured JARVIS_WORKSTATION_API_TOKEN is required for non-loopback binding."
    )


def system_telemetry() -> dict[str, Any]:
    payload: dict[str, Any] = {"available": False}
    try:
        import psutil

        memory = psutil.virtual_memory()
        payload = {
            "available": True,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": memory.percent,
            "memory_used_bytes": memory.used,
            "memory_total_bytes": memory.total,
            "process_count": len(psutil.pids()),
        }
    except Exception as error:
        payload["error"] = type(error).__name__
    return payload


def tool_manifest() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": metadata.get("description", ""),
            "risk": metadata.get("risk", "UNKNOWN"),
            "capabilities": sorted(capabilities_for(name)),
        }
        for name, metadata in sorted(list_tools().items())
    ]


def control_plane_snapshot() -> dict[str, Any]:
    """Return one bounded runtime snapshot for the authenticated operator."""

    telemetry = system_telemetry()
    market = MARKET_RUNTIME.public_state()
    company = COMPANY_OS.snapshot()
    missions = MISSION_CONTROL.snapshot()
    web = WEB_INTELLIGENCE_AGENT.snapshot()
    return CONTROL_PLANE.snapshot(
        live_trading_enabled=LIVE_TRADING_ENABLED,
        workstation_host=WORKSTATION_HOST,
        telemetry=telemetry,
        market=market,
        mission_control=missions,
        company=company,
        web=web,
    )


def public_state() -> dict[str, Any]:
    with COMMAND_LOCK:
        state = {
            key: value
            for key, value in v7.STATE.items()
            if key not in {"messages"}
        }
    telemetry = system_telemetry()
    market = MARKET_RUNTIME.public_state()
    company = COMPANY_OS.snapshot()
    missions = MISSION_CONTROL.snapshot()
    web = WEB_INTELLIGENCE_AGENT.snapshot()
    paper = PAPER_RUNTIME.public_state()
    state.update(
        {
            "canonical": True,
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "agents": sorted(jarvis_main.AGENT_MAP),
            "tools": tool_manifest(),
            "telemetry": telemetry,
            "market": market,
            "company": company,
            "mission_control": missions,
            "web_intelligence": web,
            "paper": paper,
            "control_plane": CONTROL_PLANE.snapshot(
                live_trading_enabled=LIVE_TRADING_ENABLED,
                workstation_host=WORKSTATION_HOST,
                telemetry=telemetry,
                market=market,
                mission_control=missions,
                company=company,
                web=web,
            ),
        }
    )
    return state


def _paper_symbol(command: str) -> str | None:
    normalized = command.lower()
    aliases = (
        ("natural gas", "NATURALGAS"), ("natgas", "NATURALGAS"),
        ("crude oil", "CRUDEOIL"), ("crudeoil", "CRUDEOIL"),
        ("bank nifty", "BANKNIFTY"), ("banknifty", "BANKNIFTY"),
        ("nifty 50", "NIFTY"), ("nifty", "NIFTY"), ("sensex", "SENSEX"),
        ("bitcoin", "BTC"), ("btc", "BTC"),
        ("ethereum", "ETH"), ("ether", "ETH"), ("eth", "ETH"),
        ("solana", "SOL"), ("sol", "SOL"),
        ("silver", "SILVER"), ("gold", "GOLD"),
    )
    for alias, symbol in aliases:
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return symbol
    return None


def _paper_quantity(command: str) -> float:
    patterns = (
        r"\b(?:buy|sell)\s+(\d+(?:\.\d+)?)\s+(?:units?\s+of\s+)?[a-z0-9 ]+\b",
        r"\b(?:qty|quantity|units?)\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        r"\b(?:nifty|bank\s*nifty|sensex|gold|silver|crude\s*oil|natural\s*gas|bitcoin|btc|ethereum|eth|solana|sol)\s+(\d+(?:\.\d+)?)\s*(?:units?)?\b",
    )
    for pattern in patterns:
        match = re.search(pattern, command, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 1.0


def _paper_option_request(command: str) -> dict[str, Any] | None:
    """Parse an exact commodity-option request without treating strike as quantity."""

    value = re.sub(r"\s+", " ", str(command or "")).strip().lower()
    if not re.search(r"\b(?:call|put|ce|pe|option|strike|expiry)\b", value):
        return None
    underlying = _paper_symbol(command)
    if underlying not in {"CRUDEOIL", "GOLD", "SILVER", "NATURALGAS"}:
        return None
    option_type = "CE" if re.search(r"\b(?:call|ce)\b", value) else (
        "PE" if re.search(r"\b(?:put|pe)\b", value) else None
    )
    strike_match = re.search(r"\b(\d{3,7}(?:\.\d+)?)\s*(?:call|put|ce|pe)\b", value)
    if not strike_match:
        strike_match = re.search(r"\bstrike\s*[:=]?\s*(\d{3,7}(?:\.\d+)?)\b", value)
    if not option_type or not strike_match:
        return {
            "underlying": underlying,
            "error": "Specify both an option strike and CALL/CE or PUT/PE.",
        }
    quantity_match = re.search(
        r"\b(?:qty|quantity|lots?|units?)\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        value,
    )
    if not quantity_match:
        quantity_match = re.search(
            r"\b(?:buy|sell)\s+(\d+(?:\.\d+)?)\s+(?:units?\s+of\s+)?(?:crude|gold|silver|natural)",
            value,
        )
    return {
        "underlying": underlying,
        "strike": float(strike_match.group(1)),
        "option_type": option_type,
        "expiry_query": command,
        "quantity": float(quantity_match.group(1)) if quantity_match else 1.0,
    }


def _is_conversational_smalltalk(command: str) -> bool:
    """Keep greetings and social turns out of specialist execution paths."""

    normalized = re.sub(r"[^a-z0-9\s]", " ", str(command or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"^jarvis\s+", "", normalized).strip()
    return bool(
        re.fullmatch(
            r"(?:hi|hello|hey|good morning|good afternoon|good evening|how are you|thank you|thanks|ok|okay)",
            normalized,
        )
    )


def _market_symbol(command: str) -> str | None:
    parsed = v7.parse_symbol(str(command or "").lower())
    return {
        "CRUDE OIL": "CRUDEOIL",
        "NATURAL GAS": "NATURALGAS",
    }.get(str(parsed or "").upper(), str(parsed or "").upper()) or None


def _market_analysis_request(command: str) -> bool:
    if not _market_symbol(command):
        return False
    return bool(
        re.search(
            r"\b(?:analy[sz]e|analysis|check|assess|trade|trading|setup|signal|trend|"
            r"support|resistance|momentum|regime|outlook|can i|should i|find)\b",
            command,
            flags=re.IGNORECASE,
        )
    )


def _paper_monitoring_request(command: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ping|notify|alert|monitor|watch)\b|"
            r"\bwhen(?:ever)?\b[^.]{0,50}\b(?:trade|setup|signal|entry)\b|"
            r"\b(?:execute|take|place)\b[^.]{0,30}\btrade\b",
            command,
            flags=re.IGNORECASE,
        )
    )


def _uncertain_transcript(command: str, speech_confidence: float | None = None) -> bool:
    try:
        confidence = float(speech_confidence) if speech_confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None and 0 < confidence < 0.30:
        return True
    words = set(re.findall(r"[a-z]+", str(command or "").lower()))
    roman_hindi = {
        "aakhri", "akhir", "tak", "idhar", "udhar", "koi", "nahi", "nahin",
        "vaisa", "waisa", "aisa", "kya", "kaise", "kyun", "hai", "hain", "mujhe",
    }
    return len(words.intersection(roman_hindi)) >= 3


def _web_followup_request(command: str) -> bool:
    """Detect references to a result from the preceding public-web search."""

    value = re.sub(r"\s+", " ", str(command or "")).strip().lower()
    action = re.search(
        r"\b(?:analy[sz]e|assess|review|check|compare|read|open|suitable|fit|qualified|hire|handle)\b",
        value,
    )
    referent = re.search(
        r"\b(?:this|that)\b.{0,24}\b(?:profile|person|candidate|result|source|link|page|one)\b|"
        r"\b(?:first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th|"
        r"seventh|7th|eighth|8th|ninth|9th|tenth|10th)\b.{0,16}"
        r"\b(?:profile|person|candidate|result|source|link|page|one)\b|"
        r"\b(?:profile|result|source|link)\s*(?:number|no\.?|#)?\s*\d{1,2}\b",
        value,
    )
    return bool(action and referent)


def _web_result_index(command: str) -> int:
    value = str(command or "").lower()
    words = {
        "first": 1, "1st": 1, "second": 2, "2nd": 2,
        "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7, "eighth": 8, "8th": 8,
        "ninth": 9, "9th": 9, "tenth": 10, "10th": 10,
    }
    for marker, number in words.items():
        if re.search(rf"\b{re.escape(marker)}\b", value):
            return number - 1
    match = re.search(
        r"\b(?:profile|result|source|link)\s*(?:number|no\.?|#)?\s*(\d{1,2})\b",
        value,
    )
    return max(int(match.group(1)) - 1, 0) if match else 0


def _sources_from_web_conversation() -> dict[str, Any] | None:
    """Recover the last real search result when a vague search already replaced latest."""

    pattern = re.compile(
        r"(?ms)^\s*(\d{1,2})\.\s+([^\r\n]+)\r?\n(.*?)^\s*Source:\s+(https?://\S+)"
    )
    for message in reversed(v7.conversation_messages("web")):
        if message.get("role") != "assistant":
            continue
        body = str(message.get("text") or "")
        origin_match = re.search(r"(?im)^Web Intelligence found .*? for:\s*(.+)$", body)
        origin_query = origin_match.group(1).strip() if origin_match else ""
        if origin_query and _web_followup_request(origin_query):
            continue
        sources = []
        for _number, title, excerpt, url in pattern.findall(body):
            sources.append(
                {
                    "title": title.strip(),
                    "url": url.rstrip(".,);]"),
                    "excerpt": re.sub(r"\s+", " ", excerpt).strip(),
                    "provider": "CONVERSATION_RESULT",
                    "read_status": "PREVIOUSLY_RETRIEVED",
                    "checksum": "",
                }
            )
        if sources:
            return {"query": origin_query, "sources": sources}
    return None


def _latest_web_search_result() -> dict[str, Any] | None:
    snapshot = WEB_INTELLIGENCE_AGENT.snapshot()
    latest = (snapshot.get("latest") or {})
    if (
        isinstance(latest, dict)
        and latest.get("sources")
        and not _web_followup_request(str(latest.get("query") or ""))
        and str(latest.get("mode") or "") != "SOURCE_ASSESSMENT"
    ):
        return latest
    for prior in snapshot.get("recent_results") or []:
        if (
            isinstance(prior, dict)
            and prior.get("sources")
            and not _web_followup_request(str(prior.get("query") or ""))
            and str(prior.get("mode") or "") != "SOURCE_ASSESSMENT"
        ):
            return prior
    conversation_result = _sources_from_web_conversation()
    if conversation_result:
        return conversation_result
    for summary in snapshot.get("history") or []:
        query = str((summary or {}).get("query") or "").strip()
        if (
            query
            and (summary or {}).get("success")
            and str((summary or {}).get("mode") or "") == "WEB_SEARCH"
            and not _web_followup_request(query)
        ):
            return WEB_INTELLIGENCE_AGENT.research(f"search the web for {query}")
    return None


def paper_command_payload(command: str) -> dict[str, Any]:
    """Handle explicit synthetic paper-account commands without broker orders."""

    normalized = re.sub(r"\s+", " ", command.lower()).strip()
    normalized = normalized.replace("startpaper", "start paper").replace("papertrading", "paper trading")
    symbol = _paper_symbol(command)
    option_request = _paper_option_request(command)
    option_contract: dict[str, Any] | None = None
    paper_fill: dict[str, Any] | None = None
    paper_analysis: dict[str, Any] | None = None
    action_message = ""
    if re.search(r"\b(?:start|arm|enable|resume|activate)\b", normalized) and re.search(
        r"\b(?:paper|autopilot|auto\s*paper)\b", normalized
    ):
        paper = PAPER_RUNTIME.set_autopilot(True)
        if re.search(r"\b(?:analy[sz]e|scan|find setup)\b", normalized):
            paper = PAPER_RUNTIME.scan_once()
        action_message = (
            "Paper autopilot is armed and will also arm whenever JARVIS starts. It scans "
            "Indian indices, MCX commodities, and major crypto using qualified multi-timeframe signals. "
            "All fills are synthetic; no broker order can be sent."
        )
    elif re.search(r"\b(?:stop|pause|disable|disarm|deactivate)\b", normalized) and re.search(
        r"\b(?:paper|autopilot|auto\s*paper)\b", normalized
    ):
        paper = PAPER_RUNTIME.set_autopilot(False)
        action_message = "Paper autopilot is paused. Existing synthetic positions remain visible and no live order was sent."
    elif re.search(r"\b(?:flatten|close all|exit all)\b", normalized) and "paper" in normalized:
        result = PAPER_RUNTIME.close_all()
        paper = result["state"]
        action_message = f"Closed {result['closed']} synthetic paper position{'s' if result['closed'] != 1 else ''}. No broker order was sent."
    elif re.search(r"\b(?:buy|sell)\b", normalized) and option_request:
        paper = PAPER_RUNTIME.public_state()
        if option_request.get("error"):
            action_message = (
                f"No synthetic fill was created. {option_request['error']} "
                "JARVIS did not substitute the underlying commodity."
            )
        else:
            try:
                option_contract = PAPER_MARKET_DATA.resolve_option_contract(
                    str(option_request["underlying"]),
                    float(option_request["strike"]),
                    str(option_request["option_type"]),
                    str(option_request["expiry_query"]),
                )
                side = "BUY" if re.search(r"\bbuy\b", normalized) else "SELL"
                result = PAPER_RUNTIME.place_option_order(
                    option_contract,
                    side,
                    float(option_request["quantity"]),
                )
                paper = result["state"]
                paper_fill = result["result"]
                action_message = (
                    f"Exact-contract synthetic option fill: {side} {float(option_request['quantity']):g} "
                    f"{option_contract['description']} at premium "
                    f"₹{float(paper_fill.get('execution_price') or paper_fill.get('price') or 0):,.2f}. "
                    f"Protective stop {float(paper_fill.get('stop_loss') or 0):,.2f}, target "
                    f"{float(paper_fill.get('take_profit') or 0):,.2f}. This is one synthetic option unit, "
                    "not an exchange lot; no FYERS broker order was sent."
                )
            except (RuntimeError, ValueError) as error:
                paper = PAPER_RUNTIME.public_state()
                action_message = (
                    f"No synthetic fill was created because the exact FYERS option contract could not be "
                    f"validated: {error} JARVIS did not substitute the underlying commodity."
                )
    elif re.search(r"\b(?:close|exit)\b", normalized) and symbol:
        result = PAPER_RUNTIME.close_position(symbol)
        paper = result["state"]
        action_message = f"Closed the {symbol} synthetic paper position at the current market-data mark. No broker order was sent."
    elif re.search(r"\b(?:buy|sell)\b", normalized) and symbol:
        side = "BUY" if re.search(r"\bbuy\b", normalized) else "SELL"
        quantity = _paper_quantity(command)
        result = PAPER_RUNTIME.place_guarded_order(symbol, side, quantity)
        paper = result["state"]
        fill = result["result"]
        action_message = (
            f"Synthetic paper fill: {side} {quantity:g} {symbol} at "
            f"{float(fill.get('execution_price') or fill.get('price') or 0):,.2f}. "
            "No broker order was sent."
        )
    elif symbol and re.search(
        r"\b(?:analy[sz]e|analysis|check|review|assess|setup|signal|trend|chart|trade\s+or\s+wait|"
        r"whether\s+(?:i\s+)?(?:should|need\s+to)\s+trade)\b",
        normalized,
    ):
        paper_analysis = PAPER_MARKET_DATA.analyze(symbol)
        paper = PAPER_RUNTIME.public_state()
        if paper_analysis.get("success"):
            setup = str(paper_analysis.get("setup") or "NO_QUALIFIED_SETUP")
            decision = str(paper_analysis.get("decision_gate") or "WAIT")
            confidence = float(paper_analysis.get("confidence") or 0)
            risk_reward = float(paper_analysis.get("risk_reward") or 0)
            strategy = str(paper_analysis.get("strategy") or "NO_EDGE").replace("_", " ").lower()
            patterns = ", ".join(
                str(item).replace("_", " ").lower()
                for item in (paper_analysis.get("chart_patterns") or [])[:3]
            ) or "no confirmed chart pattern"
            if decision == "QUALIFIED":
                decision_text = f"QUALIFIED PAPER WATCH {setup.replace('PAPER_WATCH_', '')}"
                next_step = (
                    "The armed paper loop will independently recheck every session, exposure, and risk gate "
                    "before it can create a synthetic fill."
                )
            else:
                decision_text = "WAIT — NO QUALIFIED SETUP"
                next_step = "JARVIS will keep monitoring; this analysis did not create a position."
            action_message = (
                f"{symbol} multi-timeframe analysis: {decision_text}. "
                f"Alignment confidence {confidence:g} percent, strategy {strategy}, "
                f"projected risk/reward {risk_reward:.2f}, evidence {patterns}. "
                f"Regime {str(paper_analysis.get('regime') or 'MIXED').lower()}, "
                f"support {paper_analysis.get('support')}, resistance {paper_analysis.get('resistance')}. "
                f"{next_step} This is research and synthetic paper monitoring, not personal trading advice; "
                "live broker execution remains locked."
            )
        else:
            action_message = (
                f"JARVIS could not complete verified {symbol} multi-timeframe analysis: "
                f"{paper_analysis.get('message') or 'market data was unavailable'}. "
                "No synthetic fill or broker order was created."
            )
    elif re.search(r"\b(?:scan|check signals?|find setups?)\b", normalized):
        paper = PAPER_RUNTIME.scan_once()
        action_message = (
            "Multi-asset paper scan completed against FYERS and public crypto data. "
            + (
                "Qualified signals may create synthetic fills because paper autopilot is armed."
                if paper.get("autopilot")
                else "Autopilot is paused, so signals were recorded without creating a fill."
            )
        )
    elif re.search(r"\b(?:review|mistakes?|learn|why)\b", normalized) and re.search(
        r"\b(?:loss|losses|trades?|performance|today|paper)\b", normalized
    ):
        paper = PAPER_RUNTIME.public_state()
        learning = paper.get("learning") or {}
        daily = (learning.get("daily_reviews") or [])[:1]
        reviews = learning.get("trade_reviews") or []
        scorecards = learning.get("strategy_scorecards") or []
        if daily:
            day = daily[0]
            flags = ", ".join(str(item).replace("_", " ").lower() for item in day.get("top_review_flags") or [])
            action_message = (
                f"Automatic paper review for {day.get('date')}: {day.get('summary')} "
                + (f"Main issues detected: {flags}. " if flags else "No repeated process issue was detected. ")
                + f"JARVIS has updated {len(scorecards)} strategy scorecard(s); repeated-loss strategies are reduced or cooled off automatically."
            )
        elif reviews:
            latest = reviews[-1]
            action_message = (
                f"Latest paper-trade review: {latest.get('symbol')} {latest.get('outcome')}, "
                f"R multiple {latest.get('r_multiple')}. {latest.get('lesson')}"
            )
        else:
            action_message = "No closed paper trade is available to review yet. Entry theses, stops, targets, patterns, and risk/reward are now recorded automatically for future reviews."
    else:
        paper = PAPER_RUNTIME.public_state()
        account = paper.get("account") or {}
        connection = "connected" if paper.get("market_connected") else "waiting for market data"
        action_message = (
            f"Multi-asset Paper Desk is {connection}. Equity is ₹{float(account.get('equity') or 0):,.2f} "
            f"with {int(account.get('open_positions') or 0)} open synthetic position(s). "
            f"Autopilot is {'armed' if paper.get('autopilot') else 'paused'} and auto-arms at startup; live broker execution remains locked."
        )
    response = {
        "action": "open_paper",
        "source": "paper_runtime",
        "speech": action_message,
        "paper": paper,
    }
    if option_contract:
        response["option_contract"] = option_contract
    if paper_fill:
        response["paper_fill"] = paper_fill
    if paper_analysis:
        response["trading_intelligence"] = paper_analysis
    return response


def execute_command(
    text: str,
    context: str = "master",
    *,
    active_symbol: str | None = None,
    speech_confidence: float | None = None,
) -> dict[str, Any]:
    command = str(text or "").strip()
    if not command:
        raise ValueError("Command cannot be empty.")
    if len(command) > MAX_COMMAND_CHARS:
        raise ValueError(f"Command exceeds {MAX_COMMAND_CHARS} characters.")

    conversation_context = v7.normalize_context(context)
    with COMMAND_LOCK:
        v7.add_message("user", command, conversation_context)
        followup = (
            parse_news_followup(command)
            if conversation_context == "news" and latest_news().get("articles")
            else None
        )
        company_intent = (
            conversation_context == "company"
            and any(word in command.lower() for word in ("idea", "company", "business", "startup", "venture"))
        ) or bool(
            re.search(
                r"\b(?:i have (?:this |an? )?idea|(?:build|create|start|set ?up|launch) (?:a |my )?(?:company|business|startup|venture))\b",
                command,
                flags=re.IGNORECASE,
            )
        )
        requested_market_symbol = _market_symbol(command)
        quant_intent = _market_analysis_request(command) or (
            conversation_context == "quant" and bool(
                re.search(
                    r"\b(?:find|scan|analy[sz]e|check|show|review|assess|trade|setup|signal|trend|levels?|support|resistance|momentum|regime|outlook)\b",
                    command,
                    flags=re.IGNORECASE,
                )
            )
        )
        commodity_chart_intent = bool(
            requested_market_symbol in {"GOLD", "SILVER", "CRUDEOIL", "NATURALGAS"}
            and re.search(r"\bchart\b", command, flags=re.IGNORECASE)
            and re.search(r"\b(?:open|show|display)\b", command, flags=re.IGNORECASE)
            and not _market_analysis_request(command)
        )
        paper_intent = conversation_context == "paper" or bool(
            re.search(
                r"\b(?:paper\s+(?:trading|trade|portfolio|account|desk|autopilot|buy|sell|scan)|"
                r"(?:buy|sell|close|exit|flatten|start|stop|pause|arm|enable|disable)\b[^.]{0,45}\bpaper|"
                r"(?:start|stop|pause|arm|enable|disable)\s*paper|"
                r"paper[^.]{0,45}(?:review|mistake|loss|performance)|"
                r"(?:review|why|analy[sz]e)[^.]{0,45}paper[^.]{0,20}(?:loss|trade|performance))\b",
                command,
                flags=re.IGNORECASE,
            )
        )
        if _is_conversational_smalltalk(command):
            result = jarvis_main.process_command(command)
            message = str(result.get("message") or "Hello. Tell me the outcome you want and I will route it automatically.")
            response = {**result, "speech": message, "source": "orchestrator"}
        elif paper_intent:
            try:
                response = paper_command_payload(command)
                message = str(response["speech"])
            except (RuntimeError, ValueError) as error:
                paper = PAPER_RUNTIME.public_state()
                message = f"Paper Desk did not place a synthetic fill: {error} No broker order was sent."
                response = {
                    "action": "open_paper",
                    "source": "paper_runtime",
                    "speech": message,
                    "paper": paper,
                }
        elif conversation_context == "system" or is_control_plane_request(command):
            control_plane = control_plane_snapshot()
            summary = control_plane["summary"]
            message = (
                f"System Core is {control_plane['status'].lower()}: "
                f"{summary['agents_ready']} of {summary['agents_total']} registered "
                f"agents passed static readiness checks, {summary['tools_total']} "
                "governed tools are catalogued, and live broker execution is locked. "
                "The control plane trace intentionally excludes secrets and tool payloads."
            )
            response = {
                "action": "open_system",
                "source": "control_plane",
                "speech": message,
                "control_plane": control_plane,
            }
        elif commodity_chart_intent:
            contract = PAPER_MARKET_DATA.provider_symbol(str(requested_market_symbol))
            range_value, range_label = v7.parse_range(command.lower())
            interval = v7.parse_interval(command.lower())
            chart = {
                "symbol": contract["provider_symbol"],
                "label": contract.get("description") or contract.get("label") or requested_market_symbol,
                "interval": interval,
                "range": range_value,
                "range_label": range_label,
                "native_supported": True,
            }
            v7.set_chart(v7.STATE["selected"], chart)
            message = (
                f"Opening the active {chart['label']} FYERS contract for {range_label} "
                f"on the {interval} minute chart."
            )
            response = {
                "action": "set_chart",
                "source": "fyers_contract_resolver",
                "symbol": requested_market_symbol,
                "chart": chart,
                "speech": message,
            }
        elif quant_intent:
            fallback_symbol = str(active_symbol or "BANKNIFTY").strip().upper().replace(" ", "")
            symbol = requested_market_symbol or (
                fallback_symbol if fallback_symbol in ASSET_UNIVERSE else "BANKNIFTY"
            )
            intelligence = (
                PAPER_MARKET_DATA.analyze(symbol)
                if symbol in ASSET_UNIVERSE else analyze_symbol(symbol)
            )
            if intelligence.get("success"):
                setup = str(intelligence.get("setup") or "NO_QUALIFIED_SETUP").replace("_", " ")
                strategy = str(intelligence.get("strategy") or "NO_EDGE").replace("_", " ").lower()
                risk_reward = float(intelligence.get("risk_reward") or 0)
                patterns = ", ".join(
                    str(item).replace("_", " ").lower()
                    for item in (intelligence.get("chart_patterns") or [])[:3]
                ) or "no confirmed chart pattern"
                message = (
                    f"{symbol} broker analysis is ready: {setup}, "
                    f"{intelligence.get('confidence', 0)} percent timeframe-alignment confidence. "
                    f"Strategy {strategy}, projected risk/reward {risk_reward:.2f}, "
                    f"evidence {patterns}. Regime {str(intelligence.get('regime') or 'MIXED').lower()}, "
                    f"support {intelligence.get('support')}, resistance {intelligence.get('resistance')}. "
                    "This is a research and paper-watch result, not a live trade instruction."
                )
            else:
                message = str(
                    intelligence.get("message")
                    or f"No verified FYERS setup is available for {symbol}."
                )
            response = {
                "action": "open_quant",
                "source": "trading_intelligence",
                "symbol": symbol,
                "speech": message,
                "trading_intelligence": intelligence,
            }
            if _paper_monitoring_request(command):
                PAPER_RUNTIME.set_autopilot(True)
                paper = PAPER_RUNTIME.scan_once()
                position = next(
                    (item for item in paper.get("positions", []) if item.get("symbol") == symbol),
                    None,
                )
                if position:
                    monitoring = (
                        f" Protected paper monitoring is armed, and a synthetic {position.get('side')} "
                        f"position is already open with stop {position.get('stop_loss')} and target {position.get('take_profit')}."
                    )
                elif intelligence.get("decision_gate") == "QUALIFIED" and len(paper.get("positions", [])) >= int(
                    (paper.get("guardrails") or {}).get("max_open_positions", 6)
                ):
                    monitoring = " The setup qualified, but no new paper fill was added because the portfolio exposure limit is full."
                else:
                    monitoring = " Protected paper monitoring is armed; JARVIS will alert and create a synthetic fill only after every signal and risk gate passes."
                message += monitoring + " Live broker execution remains locked."
                response.update(
                    {
                        "speech": message,
                        "paper": paper,
                        "notification_requested": True,
                    }
                )
        elif _web_followup_request(command):
            previous = _latest_web_search_result()
            sources = list((previous or {}).get("sources") or [])
            selected_index = _web_result_index(command)
            if not sources:
                message = (
                    "I cannot reliably identify the profile you mean because no earlier public-web result is available. "
                    "Search for the person again, then say analyze the first profile."
                )
                research = {
                    "success": False,
                    "action": "open_web",
                    "mode": "SOURCE_REFERENCE_MISSING",
                    "query": command,
                    "answer": message,
                    "sources": [],
                    "providers": [],
                    "notice": "JARVIS did not start a vague replacement search or invent a profile.",
                }
            elif selected_index >= len(sources):
                message = (
                    f"That search has {len(sources)} result(s), so result {selected_index + 1} is unavailable. "
                    "Choose one of the displayed result numbers."
                )
                research = {
                    "success": False,
                    "action": "open_web",
                    "mode": "SOURCE_REFERENCE_OUT_OF_RANGE",
                    "query": command,
                    "answer": message,
                    "sources": sources,
                    "providers": [],
                    "notice": "No new search was started and no person was substituted.",
                }
            else:
                research = WEB_INTELLIGENCE_AGENT.assess_source(
                    sources[selected_index],
                    command,
                    selection_index=selected_index + 1,
                    origin_query=str((previous or {}).get("query") or ""),
                )
                message = str(research.get("answer") or research.get("message"))
            response = {
                **research,
                "action": "open_web",
                "source": "web_intelligence",
                "speech": message,
                "web_intelligence": (
                    WEB_INTELLIGENCE_AGENT.snapshot()
                    if research.get("mode") == "SOURCE_ASSESSMENT"
                    else {"latest": research}
                ),
            }
        elif company_intent:
            plan = COMPANY_OS.create_plan(command)
            message = (
                f"The supervised company blueprint for {plan['company_name']} is ready. "
                f"I created {len(plan['tasks'])} coordinated tasks; "
                f"{sum(1 for item in plan['tasks'] if item['approval_required'])} consequential actions are approval-gated, "
                f"and {len(plan.get('artifacts', []))} local operating documents were generated."
            )
            response = {
                "action": "open_company",
                "source": "company_os",
                "speech": message,
                "company": COMPANY_OS.snapshot(),
            }
        elif is_operator_request(command) or is_mission_request(command, conversation_context):
            mission = MISSION_CONTROL.create_mission(command)
            message = (
                f"Mission Control completed the local execution packet with "
                f"{len(mission['selected_agents'])} specialists, "
                f"{len(mission['artifacts'])} durable artifacts, and an independent "
                f"quality verdict of {mission['critic']['verdict'].replace('_', ' ').lower()}. "
                f"External actions remain locked for your approval."
            )
            response = {
                "action": "open_mission",
                "source": "mission_control",
                "speech": message,
                "mission_control": MISSION_CONTROL.snapshot(),
            }
        elif conversation_context == "web" or is_web_request(command):
            agent_response = jarvis_main.AGENT_REGISTRY.execute(
                AgentRequest("web_intelligence", command)
            )
            research = agent_response.data if isinstance(agent_response.data, dict) else {
                "success": False,
                "action": "open_web",
                "query": command,
                "sources": [],
                "notice": agent_response.message,
            }
            message = str(research.get("message") or agent_response.message)
            spoken_message = str(research.get("answer") or message)
            response = {
                **research,
                "action": "open_web",
                "source": "web_intelligence",
                "speech": spoken_message,
                "web_intelligence": WEB_INTELLIGENCE_AGENT.snapshot(),
            }
        elif followup is not None:
            response = {
                **build_news_briefing(
                    index=followup.get("index"),
                    limit=int(followup.get("limit") or 5),
                ),
                "source": "news_context",
            }
            message = str(response["speech"])
        elif _uncertain_transcript(command, speech_confidence):
            message = (
                "I may have heard that incorrectly. I will not invent a translation or meaning. "
                "Please repeat it a little more slowly in Hindi or English, or type the sentence."
            )
            response = {
                "action": "clarify_speech",
                "source": "speech_guardrail",
                "speech": message,
            }
        else:
            local_result = v7.local_agent(command)
            if local_result is not None:
                message = str(local_result.get("speech", "Command handled."))
                response = {**local_result, "source": "workstation"}
            else:
                result = jarvis_main.process_command(command)
                message = str(result.get("message") or "Command completed.")
                response = {**result, "speech": message, "source": "orchestrator"}
        routed_context = {
            "open_system": "system",
            "open_mission": "mission",
            "open_web": "web",
            "open_news": "news",
            "open_quant": "quant",
            "open_paper": "paper",
            "open_company": "company",
        }.get(str(response.get("action") or ""))
        if routed_context and routed_context != conversation_context:
            v7.add_message("user", command, routed_context)
            v7.add_message("assistant", message, routed_context)
            response["routed_context"] = routed_context
            response["routed_messages"] = v7.conversation_messages(routed_context)[-100:]
        v7.add_message("assistant", message, conversation_context)
        response["context"] = conversation_context
        response["messages"] = v7.conversation_messages(conversation_context)[-100:]
        response["state"] = {
            "layout": v7.STATE["layout"],
            "charts": v7.STATE["charts"][: v7.STATE["layout"]],
            "selected": v7.STATE["selected"],
        }
        audit_event(
            "workstation",
            "command",
            "SUCCEEDED",
            {
                "source": response["source"],
                "context": conversation_context,
                "character_count": len(command),
            },
        )
        return response


def company_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plan = COMPANY_OS.create_plan(
        str(payload.get("idea") or ""),
        company_name=str(payload.get("company_name") or "") or None,
        context=str(payload.get("context") or ""),
    )
    return {"ok": True, "plan": plan, "company": COMPANY_OS.snapshot()}


def mission_create_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mission = MISSION_CONTROL.create_mission(
        str(payload.get("objective") or payload.get("text") or ""),
        title=str(payload.get("title") or "") or None,
    )
    return {
        "ok": True,
        "mission": mission,
        "mission_control": MISSION_CONTROL.snapshot(),
    }


def web_research_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = WEB_INTELLIGENCE_AGENT.research(
        str(payload.get("query") or payload.get("text") or "")
    )
    return {
        "ok": bool(result.get("success")),
        "result": result,
        "web_intelligence": WEB_INTELLIGENCE_AGENT.snapshot(),
    }


def candle_payload(symbol: str, timeframe: str, bars: int) -> dict[str, Any]:
    requested_symbol = str(symbol or "").strip().upper()
    requested_timeframe = str(timeframe or "").strip().lower()
    if not requested_symbol or len(requested_symbol) > 64:
        raise ValueError("Invalid candle symbol.")
    if not re.fullmatch(r"[A-Z0-9 :_!.-]+", requested_symbol):
        raise ValueError("Invalid candle symbol.")
    if requested_timeframe not in {
        "1m", "2m", "3m", "5m", "10m", "15m", "20m", "30m",
        "1h", "2h", "4h", "1d", "1wk", "1mo",
    }:
        raise ValueError("Unsupported candle timeframe.")
    if not 30 <= bars <= MAX_CANDLE_BARS:
        raise ValueError(f"bars must be between 30 and {MAX_CANDLE_BARS}.")

    key = (requested_symbol, requested_timeframe, bars)
    now = time.monotonic()
    with CANDLE_LOCK:
        cached = CANDLE_CACHE.get(key)
        if cached and now - cached[0] < CANDLE_CACHE_TTL_SECONDS:
            return cached[1]

    result = get_intraday_data(
        requested_symbol,
        timeframe=requested_timeframe,
        bars=bars,
    )
    if not result.get("success"):
        payload = {
            "success": False,
            "source": "FYERS",
            "symbol": requested_symbol,
            "timeframe": requested_timeframe,
            "candles": [],
            "message": str(result.get("message") or "FYERS candle data is unavailable."),
        }
        return payload

    frame = result.get("data")
    candles: list[dict[str, Any]] = []
    if frame is not None:
        for timestamp, row in frame.iterrows():
            values = [row.get(name) for name in ("Open", "High", "Low", "Close", "Volume")]
            if not all(math.isfinite(float(value)) for value in values[:4]):
                continue
            volume = float(values[4]) if values[4] is not None else 0.0
            candles.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": float(values[0]),
                    "high": float(values[1]),
                    "low": float(values[2]),
                    "close": float(values[3]),
                    "volume": volume if math.isfinite(volume) else 0.0,
                }
            )

    payload = {
        "success": bool(candles),
        "source": result.get("source", "FYERS"),
        "data_quality": result.get("data_quality", "BROKER_HISTORICAL"),
        "symbol": requested_symbol,
        "provider_symbol": result.get("provider_symbol"),
        "timeframe": requested_timeframe,
        "bars": len(candles),
        "candles": candles,
        "message": result.get("message", "Historical candles loaded from FYERS."),
        "timestamp": result.get("timestamp"),
    }
    with CANDLE_LOCK:
        CANDLE_CACHE[key] = (now, payload)
    return payload


class Handler(BaseHTTPRequestHandler):
    server_version = "OMNI-JARVIS/0.1"

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-Jarvis-Token", "")
        if not supplied:
            authorization = self.headers.get("Authorization", "")
            if authorization.startswith("Bearer "):
                supplied = authorization[7:]
        return hmac.compare_digest(supplied, API_TOKEN)

    def _json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file() or STATIC not in path.resolve().parents:
            self.send_error(404)
            return
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        audit_event("workstation", "authorization", "REJECTED")
        self._json({"ok": False, "error": "Unauthorized."}, 401)
        return False

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_BODY_BYTES:
            raise ValueError("Invalid request body size.")
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise ValueError("Content-Type must be application/json.")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            market_status = MARKET_RUNTIME.health_status()
            self._json(
                {
                    "ok": True,
                    "service": "OMNI-JARVIS",
                    "live_trading_enabled": LIVE_TRADING_ENABLED,
                    "market_data": {
                        "provider": market_status.get("provider"),
                        "running": market_status.get("running", False),
                        "connected": market_status.get("connected", False),
                        "data_only": True,
                    },
                    "paper_trading": {
                        "paper_only": True,
                        "live_orders": False,
                        "autopilot": PAPER_RUNTIME.health_status().get("autopilot", False),
                    },
                }
            )
            return
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
            "/system.css": ("system.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
        }
        if path in static_files:
            filename, content_type = static_files[path]
            self._file(STATIC / filename, content_type)
            return
        if not self._require_auth():
            return
        query = urllib.parse.parse_qs(parsed.query)
        try:
            limit = min(max(int(query.get("limit", ["100"])[0]), 1), 500)
        except (TypeError, ValueError):
            self._json({"ok": False, "error": "Invalid limit."}, 400)
            return
        if path == "/api/state":
            self._json(public_state())
        elif path == "/api/market":
            self._json(MARKET_RUNTIME.public_state())
        elif path == "/api/paper":
            self._json(PAPER_RUNTIME.public_state())
        elif path == "/api/candles":
            try:
                bars = int(query.get("bars", ["500"])[0])
                payload = candle_payload(
                    str(query.get("symbol", ["NIFTY"])[0]),
                    str(query.get("timeframe", ["5m"])[0]),
                    bars,
                )
                self._json(payload, 200 if payload.get("success") else 502)
            except (TypeError, ValueError) as error:
                self._json({"ok": False, "error": str(error)}, 400)
        elif path == "/api/news":
            try:
                news_limit = min(limit, 50)
                news_query = str(query.get("q", ["India markets NIFTY Sensex"])[0])
                requested_timespan = query.get("timespan", [None])[0]
                if requested_timespan is None:
                    payload = search_market_news(news_query, limit=news_limit)
                else:
                    payload = search_market_news(
                        news_query,
                        limit=news_limit,
                        timespan=str(requested_timespan),
                    )
                remember_news(payload)
                self._json(payload)
            except ValueError as error:
                self._json({"ok": False, "error": str(error)}, 400)
        elif path == "/api/telemetry":
            self._json(system_telemetry())
        elif path == "/api/events":
            self._json({"events": get_audit_store().recent_events(limit)})
        elif path == "/api/tasks":
            self._json({"plans": get_audit_store().recent_plans(limit)})
        elif path == "/api/capabilities":
            self._json({"tools": tool_manifest()})
        elif path == "/api/control-plane":
            self._json(control_plane_snapshot())
        elif path == "/api/company":
            self._json(COMPANY_OS.snapshot())
        elif path == "/api/missions":
            self._json(MISSION_CONTROL.snapshot())
        elif path == "/api/web":
            self._json(WEB_INTELLIGENCE_AGENT.snapshot())
        elif path == "/api/trading/intelligence":
            try:
                symbol = str(query.get("symbol", ["BANKNIFTY"])[0]).strip().upper().replace(" ", "")
                payload = (
                    PAPER_MARKET_DATA.analyze(symbol)
                    if symbol in ASSET_UNIVERSE else analyze_symbol(symbol)
                )
                self._json(payload, 200 if payload.get("success") else 502)
            except ValueError as error:
                self._json({"ok": False, "error": str(error)}, 400)
        elif path == "/api/memory":
            query_text = str(query.get("q", [""])[0]).strip()
            memory = get_memory_store()
            hits = memory.search(query_text, limit) if query_text else []
            self._json(
                {
                    "count": memory.count(),
                    "hits": [
                        {
                            "id": hit.record.id,
                            "content": hit.record.content,
                            "kind": hit.record.kind,
                            "source": hit.record.source,
                            "tags": hit.record.tags,
                            "score": hit.score,
                        }
                        for hit in hits
                    ],
                }
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path not in {
            "/api/agent", "/api/command", "/api/news/briefing",
            "/api/company/plan", "/api/missions/create",
            "/api/web/research", "/api/market/restart",
            "/api/paper/control", "/api/paper/order",
            "/api/paper/close", "/api/paper/scan",
        }:
            self.send_error(404)
            return
        if not self._require_auth():
            return
        try:
            payload = self._body()
            if path == "/api/market/restart":
                result = MARKET_RUNTIME.restart()
                audit_event(
                    "workstation",
                    "market_data_restart",
                    "SUCCEEDED" if result.get("running") else "DEGRADED",
                    {
                        "provider": result.get("provider"),
                        "configured": result.get("configured"),
                        "data_only": True,
                    },
                )
            elif path == "/api/paper/control":
                result = PAPER_RUNTIME.set_autopilot(bool(payload.get("enabled", False)))
                audit_event(
                    "paper_trading",
                    "autopilot_control",
                    "ARMED" if result.get("autopilot") else "PAUSED",
                    {"paper_only": True, "live_orders": False},
                )
            elif path == "/api/paper/order":
                result = PAPER_RUNTIME.place_guarded_order(
                    str(payload.get("symbol") or ""),
                    str(payload.get("side") or ""),
                    float(payload.get("quantity", 1)),
                )
                audit_event(
                    "paper_trading",
                    "synthetic_order",
                    "FILLED",
                    {"paper_only": True, "live_orders": False},
                )
            elif path == "/api/paper/close":
                result = (
                    PAPER_RUNTIME.close_all()
                    if payload.get("all")
                    else PAPER_RUNTIME.close_position(str(payload.get("symbol") or ""))
                )
                audit_event(
                    "paper_trading",
                    "synthetic_close",
                    "FILLED",
                    {"paper_only": True, "live_orders": False},
                )
            elif path == "/api/paper/scan":
                result = PAPER_RUNTIME.scan_once()
            elif path == "/api/company/plan":
                result = company_plan_payload(payload)
            elif path == "/api/missions/create":
                result = mission_create_payload(payload)
            elif path == "/api/web/research":
                result = web_research_payload(payload)
            elif path == "/api/news/briefing":
                context = v7.normalize_context(payload.get("chat_context", "news"))
                raw_index = payload.get("index")
                index = None if raw_index is None or raw_index == "" else int(raw_index)
                limit = min(max(int(payload.get("limit", 5)), 1), 10)
                result = build_news_briefing(index=index, limit=limit)
                v7.add_message("assistant", str(result["speech"]), context)
                result["context"] = context
                result["messages"] = v7.conversation_messages(context)[-100:]
            else:
                active_symbol = str(payload.get("active_symbol") or "").strip()
                raw_confidence = payload.get("speech_confidence")
                speech_confidence = None if raw_confidence is None or raw_confidence == "" else float(raw_confidence)
                command_kwargs: dict[str, Any] = {}
                if active_symbol:
                    command_kwargs["active_symbol"] = active_symbol
                if speech_confidence is not None:
                    command_kwargs["speech_confidence"] = speech_confidence
                result = execute_command(
                    payload.get("text", ""),
                    payload.get("context", "master"),
                    **command_kwargs,
                )
            self._json(result)
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            self._json({"ok": False, "error": str(error)}, 400)
        except Exception as error:
            audit_event(
                "workstation", "command", "FAILED", {"error": type(error).__name__}
            )
            self._json({"ok": False, "error": "Command execution failed."}, 500)

    def log_message(self, *_args) -> None:
            return


class JarvisHTTPServer(ThreadingHTTPServer):
    """Single-instance local server.

    ``HTTPServer`` enables ``SO_REUSEADDR``.  On Windows that can allow more
    than one process to listen on the same port, which is unsafe for a server
    that uses a per-process authentication token: requests can be delivered to
    the wrong process.  Disabling address reuse makes a second JARVIS launch
    fail closed instead of creating an intermittently unauthorized dashboard.
    """

    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True


def main() -> None:
    url = f"http://{WORKSTATION_HOST}:{WORKSTATION_PORT}/?token={API_TOKEN}"
    try:
        server = JarvisHTTPServer((WORKSTATION_HOST, WORKSTATION_PORT), Handler)
    except OSError as error:
        raise RuntimeError(
            f"JARVIS cannot bind {WORKSTATION_HOST}:{WORKSTATION_PORT}. "
            "Another process is already using the dashboard port."
        ) from error
    try:
        market_status = MARKET_RUNTIME.start()
        paper_status = PAPER_RUNTIME.start()
        audit_event(
            "workstation",
            "market_data_start",
            "SUCCEEDED" if market_status.get("running") else "DEGRADED",
            {
                "provider": market_status.get("provider"),
                "configured": market_status.get("configured"),
                "running": market_status.get("running"),
                "data_only": True,
            },
        )
        print("OMNI-JARVIS canonical workstation")
        print(url)
        print("Live trading: DISABLED")
        print(
            "Paper trading: "
            + ("AUTOPILOT ARMED" if paper_status.get("autopilot") else "READY / PAUSED")
        )
        print(
            "FYERS market data: "
            + (
                "CONNECTED"
                if market_status.get("connected")
                else "STARTING"
                if market_status.get("running")
                else "UNAVAILABLE"
            )
        )
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        PAPER_RUNTIME.stop()
        MARKET_RUNTIME.stop()
        server.server_close()
        audit_event("workstation", "market_data_stop", "SUCCEEDED")
        remaining_workers = [
            thread.name
            for thread in threading.enumerate()
            if thread is not threading.current_thread()
            and thread.is_alive()
            and not thread.daemon
        ]
        if remaining_workers:
            print(
                "Waiting for background library workers: "
                + ", ".join(remaining_workers)
            )


if __name__ == "__main__":
    main()



def jarvis_collaboration_payload(
    request,
    project_id=None,
    conversation_id=None,
):
    from omni.collaboration_service import (
        collaborate_payload,
    )

    return collaborate_payload(
        request,
        project_id=project_id,
        conversation_id=conversation_id,
        channel="workstation",
    )




def jarvis_memory_command_payload(
    request,
    project_id=None,
    conversation_id=None,
):
    """
    Workstation-safe memory command API.
    """

    from omni.memory_commands import (
        memory_command_answer,
    )

    try:

        answer = memory_command_answer(
            request,
            project_id=project_id,
            conversation_id=conversation_id,
            channel="workstation",
        )

        return {
            "handled": (
                answer is not None
            ),
            "success": True,
            "answer": answer,
        }

    except Exception as exc:

        return {
            "handled": True,
            "success": False,
            "answer": None,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }



def jarvis_mission_payload(
    goal,
    project_id=None,
    approved=False,
):

    from dataclasses import (
        asdict,
    )

    from omni.autonomy_engine import (
        autonomy_engine,
    )

    try:

        result = (
            autonomy_engine.execute(
                goal,
                project_id=project_id,
                approved=approved,
            )
        )

        return asdict(
            result
        )

    except Exception as exc:

        return {
            "success": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }


def jarvis_mission_plan_payload(
    goal,
):

    from dataclasses import (
        asdict,
    )

    from omni.autonomy_engine import (
        autonomy_engine,
    )

    try:

        return {
            "success": True,
            "plan": asdict(
                autonomy_engine.plan(
                    goal
                )
            ),
        }

    except Exception as exc:

        return {
            "success": False,
            "error": (
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        }



def jarvis_meta_status_payload():

    from omni.agent_registry import (
        default_agent_specs,
    )

    from omni.meta_intelligence import (
        meta_intelligence,
    )

    return {
        "success": True,

        "agents":
            len(
                default_agent_specs()
            ),

        "meta_agents": [
            "learning",
            "knowledge",
            "skill_builder",
            "experiment",
            "evaluator",
            "critic",
            "meta_improvement",
        ],

        "knowledge_graph":
            meta_intelligence
            .graph
            .stats(),

        "self_modification":
            "proposal-only",

        "automatic_promotion":
            False,
    }



def jarvis_self_improvement_payload():

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    try:

        return {
            "success": True,

            "lab":
                self_improvement_lab
                .status(),
        }

    except Exception as exc:

        return {
            "success": False,

            "error":
                f"{type(exc).__name__}: "
                f"{exc}",
        }



def jarvis_growth_payload():

    from omni.capability_growth import (
        capability_growth,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )


    try:

        integrity = (
            verify_protected_core()
        )

        return {
            "success": True,

            "protected_core": {
                "ok":
                    integrity.ok,

                "checked":
                    integrity.checked,

                "changed":
                    integrity.changed,

                "missing":
                    integrity.missing,
            },

            "growth":
                capability_growth.status(),

            "next_actions":
                capability_growth.next_actions(),
        }

    except Exception as exc:

        return {
            "success": False,

            "error":
                f"{type(exc).__name__}: {exc}",
        }



def jarvis_action_engine_payload():

    from omni.action_engine import (
        action_engine,
    )

    from omni.system_observer import (
        system_observer,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )


    try:

        integrity = (
            verify_protected_core()
        )

        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "actions":
                action_engine.status(),

            "system":
                system_observer.state(),
        }

    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_action_v2_payload():

    from omni.approval_queue import (
        approval_queue,
    )

    from omni.desktop_automation import (
        desktop_automation,
    )

    from omni.integration_status import (
        integration_status,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )


    try:

        integrity = (
            verify_protected_core()
        )

        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "visible_windows":
                len(
                    desktop_automation
                    .windows()
                ),

            "pending_approvals":
                approval_queue.pending(),

            "integrations":
                integration_status.status(),

            "acquisition_proposals":
                integration_status
                .acquisition_proposals(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_action_v3_payload():

    from omni.action_v3_status import (
        action_v3_status,
    )

    from omni.approval_queue import (
        approval_queue,
    )


    try:

        return {
            "success":
                True,

            "status":
                action_v3_status
                .status(),

            "pending_approvals":
                approval_queue
                .pending(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_computer_operator_payload():

    from omni.approval_batch import (
        approval_batches,
    )

    from omni.approval_queue import (
        approval_queue,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )

    from omni.semantic_ui import (
        semantic_ui,
    )

    from omni.tool_capability_graph import (
        tool_capability_graph,
    )


    try:

        integrity = (
            verify_protected_core()
        )


        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "visible_windows":
                len(
                    semantic_ui
                    .windows()
                ),

            "pending_approvals":
                approval_queue
                .pending(),

            "capabilities":
                tool_capability_graph
                .capabilities(),

            "graph":
                tool_capability_graph
                .snapshot(),

            "automatic_remote_write":
                False,

            "automatic_trading":
                False,
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_computer_operator_v2_payload():

    from omni.browser_observation_loop import (
        browser_observation_loop,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )

    from omni.operator_memory import (
        operator_memory,
    )

    from omni.vision_runtime import (
        vision_runtime,
    )


    try:

        integrity = verify_protected_core()


        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "browser_observation":
                browser_observation_loop
                .provider_probe(),

            "vision":
                vision_runtime.status(),

            "recent_operator_memory":
                operator_memory.recent(
                    10
                ),

            "model_dsl_auto_execute":
                False,

            "replan_auto_execute":
                False,
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_computer_operator_v3_payload():

    from omni.computer_operator_v3_status import (
        computer_operator_v3_status,
    )

    try:

        return {
            "success":
                True,

            "status":
                computer_operator_v3_status
                .status(),
        }

    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_computer_operator_v4_payload():

    from omni.core_integrity import (
        verify_protected_core,
    )

    from omni.operator_dashboard import (
        operator_dashboard,
    )

    from omni.vision_runtime import (
        vision_runtime,
    )


    try:

        integrity = (
            verify_protected_core()
        )


        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "vision":
                vision_runtime.status(),

            "operator":
                operator_dashboard.snapshot(),

            "unified_runtime":
                True,

            "automatic_approval":
                False,

            "automatic_replan_execution":
                False,

            "automatic_git_push":
                False,

            "trading_execution":
                False,
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_connected_services_v1_payload():

    from omni.connected_services_status import (
        connected_services_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                connected_services_status
                .status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_connected_services_v2_payload():

    from omni.connected_services_v2_status import (
        connected_services_v2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                connected_services_v2_status
                .status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_connected_services_v3_payload():

    from omni.connected_services_v3_status import connected_services_v3_status
    from omni.connected_approval_dashboard import connected_approval_dashboard

    try:
        return {
            "success": True,
            "status": connected_services_v3_status.status(),
            "approvals": connected_approval_dashboard.pending(),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": (
                type(exc).__name__
                + ": "
                + str(exc)
            ),
        }



def jarvis_trading_intelligence_v1_payload():

    from omni.trading_intelligence.trading_status import (
        trading_intelligence_v1_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v1_status
                .status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_intelligence_v2_payload():

    from omni.trading_intelligence.trading_v2_status import (
        trading_intelligence_v2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v2_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_intelligence_v3_payload():

    from omni.trading_intelligence.trading_v3_status import (
        trading_intelligence_v3_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v3_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_intelligence_v4_payload():

    from omni.trading_intelligence.trading_v4_status import (
        trading_intelligence_v4_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v4_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_intelligence_v5_payload():

    from omni.trading_intelligence.trading_v5_status import (
        trading_intelligence_v5_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v5_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                ),
        }



def jarvis_trading_intelligence_v6_payload():

    from omni.trading_intelligence.trading_v6_status import (
        trading_intelligence_v6_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v6_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_nautilus_research_payload():

    from omni.trading_intelligence.nautilus_status import (
        nautilus_kernel_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                nautilus_kernel_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_nautilus_c2_payload():

    from omni.trading_intelligence.nautilus_c2_status import (
        nautilus_c2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                nautilus_c2_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_nautilus_c3_payload():

    from omni.trading_intelligence.nautilus_c3_status import (
        nautilus_c3_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                nautilus_c3_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_v7_payload():

    from omni.trading_intelligence.trading_v7_status import (
        trading_v7_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_v7_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }



def jarvis_trading_v8_payload():

    from omni.trading_intelligence.trading_v8_status import (
        trading_v8_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_v8_status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }
