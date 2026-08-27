from __future__ import annotations

import importlib
import json
import re
import secrets
import threading
import time
import traceback

from http import (
    HTTPStatus,
)

from http.server import (
    BaseHTTPRequestHandler,
)

from pathlib import (
    Path,
)

from urllib.parse import (
    parse_qs,
    urlparse,
)


from omni.jarvis_workspace_orchestrator import (
    interpret_workspace_command,
)
from omni.loopback_http import exclusive_server
from omni.service_health_contract import ServiceHealthClock

from workstation.jarvis_v3_chart_provider import (
    get_chart,
)

from omni.conversation_turns import (
    conversation_turns,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

ASSETS = (
    Path(__file__)
    .resolve()
    .parent
    / "jarvis_os_v3_assets"
)


HOST = "127.0.0.1"
PORT = 8797

TOKEN = secrets.token_urlsafe(
    32
)
HEALTH = ServiceHealthClock("JARVIS_MASTER_CONTROL_PLANE", "3.1")


SENSITIVE = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
)


# V3.2B low-latency command coordination.
#
# Technical chart analysis should not enter the broad research/collaboration
# path before FYERS analysis. A small in-flight/cache boundary also prevents
# repeated voice transcripts from launching the same expensive command twice.
COMMAND_LOCK = threading.RLock()
COMMAND_INFLIGHT = set()
COMMAND_CACHE = {}
COMMAND_CACHE_SECONDS = 6.0
VOICE_CONFIDENCE_FLOOR = 0.62


def uncertain_voice_transcript(text, confidence=None):
    """Reject unreliable dictation before any agent can invent an interpretation."""

    try:
        score = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        score = None
    if score is not None and 0 < score < VOICE_CONFIDENCE_FLOOR:
        return True
    value = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    return len(value) < 2


def agent_readiness(specs):
    """Report entrypoint readiness without pretending an idle agent is executing."""

    result = []
    for spec in specs:
        name = str(getattr(spec, "name", "") or "").strip()
        module_name = str(getattr(spec, "module", "") or "").strip()
        entrypoint = str(getattr(spec, "entrypoint", "") or "").strip()
        enabled = bool(getattr(spec, "enabled", True))
        status_name = "DEGRADED"
        detail = "Entrypoint unavailable."
        if not enabled:
            status_name = "DISABLED"
            detail = "Disabled by registry configuration."
        elif name and module_name and entrypoint:
            try:
                module = importlib.import_module(module_name)
                target = getattr(module, entrypoint, None)
                if callable(target):
                    status_name = "READY"
                    detail = "Registered callable; executes on demand."
                else:
                    detail = "Registered entrypoint is not callable."
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"[:180]
        result.append(
            {
                "name": name,
                "label": str(getattr(spec, "label", name) or name),
                "status": status_name,
                "detail": detail,
                "execution_mode": "ON_DEMAND",
            }
        )
    return result


def safe(
    value,
    depth=0,
):

    if depth > 7:

        return str(
            value
        )


    if value is None:

        return None


    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value


    if isinstance(
        value,
        dict,
    ):

        result = {}


        for key, item in value.items():

            key_text = str(
                key
            )


            if any(
                word in key_text.lower()

                for word in SENSITIVE
            ):

                result[
                    key_text
                ] = "<REDACTED>"

            else:

                result[
                    key_text
                ] = safe(
                    item,
                    depth + 1,
                )


        return result


    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return [
            safe(
                item,
                depth + 1,
            )

            for item in value
        ]


    if hasattr(
        value,
        "__dict__",
    ):

        return safe(
            vars(
                value
            ),
            depth + 1,
        )


    return str(
        value
    )


def render_response(
    value,
):

    if isinstance(
        value,
        str,
    ):

        return value


    if isinstance(
        value,
        dict,
    ):

        for key in (
            "response",
            "answer",
            "message",
            "text",
            "output",
            "result",
        ):

            item = value.get(
                key
            )


            if (
                isinstance(
                    item,
                    str,
                )
                and item.strip()
            ):

                return item.strip()


    for key in (
        "response",
        "answer",
        "message",
        "text",
        "output",
    ):

        item = getattr(
            value,
            key,
            None,
        )


        if isinstance(
            item,
            str,
        ):

            return item


    return str(
        value
    )



def normalize_master_command(
    text,
):

    value = str(
        text
    ).strip()


    patterns = (
        r"^(?:hey\s+)?jarvis\s*[,;:\-]?\s*",
        r"^hi\s+jarvis\s*[,;:\-]?\s*",
        r"^hello\s+jarvis\s*[,;:\-]?\s*",
        r"^ok(?:ay)?\s+jarvis\s*[,;:\-]?\s*",
    )


    for pattern in patterns:

        cleaned = re.sub(
            pattern,
            "",
            value,
            count=1,
            flags=re.IGNORECASE,
        )


        if cleaned != value:

            cleaned = cleaned.strip()


            return (
                cleaned
                if cleaned
                else value
            )


    return value



def normalize_agent_command(
    text,
):

    """
    Convert natural trading requests into a compact command
    before they reach legacy trading parsers.

    UI still receives the user's full natural-language command.

    Examples:

      open crude oil trading terminal 15 minute chart and analyze it
          -> CRUDEOIL 15m analyze

      can you analyse the nifty 5 minute chart and tell me the trade setup
          -> NIFTY 5m analyze

    Non-trading commands are preserved unchanged.
    """

    value = normalize_master_command(
        text
    )


    lowered = value.lower()


    analysis_intent = any(
        phrase in lowered

        for phrase in (
            "analyze",
            "analyse",
            "analysis",
            "signal",
            "setup",
            "trade setup",
            "strategy",
            "find trade",
            "market setup",
            "look on",
            "looks on",
            "look at",
            "keep eye",
            "keep an eye",
            "watch",
            "monitor",
            "paper trade",
            "paper trading",
            "how does",
            "how is",
            "tell me",
        )
    )


    if not analysis_intent:

        return value


    try:

        actions = tuple(
            interpret_workspace_command(
                value
            )
        )

    except Exception:

        return value


    chart_actions = [
        action

        for action in actions

        if (
            action.get(
                "type"
            )
            == "chart_symbol"
        )
    ]


    if not chart_actions:

        return value


    first = chart_actions[0]


    symbol = str(
        first.get(
            "symbol",
            "",
        )
    ).strip()


    timeframe = str(
        first.get(
            "timeframe",
            "",
        )
        or "15m"
    ).strip()


    if not symbol:

        return value


    return (
        symbol
        + " "
        + timeframe
        + " analyze"
    )



def paper_monitor_request(text):
    value = re.sub(
        r"\s+",
        " ",
        str(text or "").strip().lower(),
    )

    return (
        any(
            phrase in value
            for phrase in (
                "keep eye on",
                "keep an eye on",
                "keep watching",
                "watch ",
                "monitor ",
            )
        )
        and any(
            phrase in value
            for phrase in (
                "paper trade",
                "paper trading",
                "paper position",
                "simulate trade",
            )
        )
        and any(
            phrase in value
            for phrase in (
                "if you find any trade",
                "if you find a trade",
                "when you find a trade",
                "when there is a trade",
                "trade opportunity",
            )
        )
    )


def paper_monitor_symbol_timeframe(text):
    for action in tuple(
        interpret_workspace_command(
            text
        )
    ):
        if action.get("type") == "chart_symbol":
            symbol = str(action.get("symbol") or "").strip()
            timeframe = str(action.get("timeframe") or "15m").strip()
            if symbol:
                return symbol, timeframe

    return None, None


def paper_monitor_control_request(text):
    value = re.sub(
        r"\s+",
        " ",
        str(text or "").strip().lower(),
    )

    status_phrases = (
        "paper monitor status",
        "paper trading status",
        "show paper monitors",
        "show monitoring",
        "what are you monitoring",
        "what are you watching",
        "monitoring status",
    )

    if any(phrase in value for phrase in status_phrases):
        return "status"

    stop_phrases = (
        "stop monitoring",
        "stop watching",
        "stop paper monitor",
        "stop paper trading",
        "cancel paper monitor",
        "cancel monitoring",
    )

    if any(phrase in value for phrase in stop_phrases):
        return "stop"

    return None


def format_paper_monitor_status(payload):
    sessions = list(payload.get("sessions") or [])

    if not sessions:
        return (
            "No paper monitors are registered. "
            "Live broker execution remains locked."
        )

    lines = [
        "JARVIS PAPER MONITORS",
        "--------------------------------------------------",
    ]

    for item in sessions:
        state = "ACTIVE" if item.get("active") else "STOPPED"
        lines.append(
            f"- {item.get('symbol', 'UNKNOWN')} "
            f"{item.get('timeframe', '')}: {state}; "
            f"last={item.get('last_action', 'WAIT')}; "
            f"checks={item.get('checks', 0)}"
        )

        trade = item.get("paper_trade")
        if isinstance(trade, dict):
            lines.append(
                f"  PAPER {trade.get('side', '')} "
                f"{trade.get('status', '')} "
                f"entry={trade.get('entry')} "
                f"exit={trade.get('exit')}"
            )

    lines.append("")
    lines.append("Live broker execution remains locked.")

    return "\n".join(lines)


def fast_trading_command(
    text,
):

    """
    Return True only for the compact technical-analysis envelope produced by
    normalize_agent_command(), for example ``NIFTY 5m analyze``.

    This deliberately excludes news, fundamentals, research, portfolio, and
    other broad trading requests so those continue through Master JARVIS.
    """

    value = str(
        text
        or ""
    ).strip()

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9:_\-.]{0,47}"
            r"\s+"
            r"(?:1m|3m|5m|15m|30m|1h|2h|4h|1d)"
            r"\s+"
            r"analy(?:ze|se)",
            value,
            flags=re.IGNORECASE,
        )
    )


def command_key(
    text,
):

    normalized = normalize_agent_command(
        text
    )

    return re.sub(
        r"\s+",
        " ",
        normalized.strip().lower(),
    )


def cached_command_result(
    key,
):

    now = time.monotonic()

    with COMMAND_LOCK:

        item = COMMAND_CACHE.get(
            key
        )

        if not item:
            return None

        created_at, result = item

        if (
            now - created_at
            > COMMAND_CACHE_SECONDS
        ):

            COMMAND_CACHE.pop(
                key,
                None,
            )

            return None

        return result


def is_reliability_command(
    text,
):

    value = re.sub(
        r"\s+",
        " ",
        str(text or "").strip().lower(),
    )


    return any(
        phrase in value

        for phrase in (
            "diagnose yourself",
            "diagnose jarvis",
            "system doctor",
            "reliability status",
            "repair yourself",
            "self heal",
            "self-heal",
            "fix yourself",
            "improve yourself",
            "make yourself better",
            "improvement plan",
        )
    )


def dispatch_command(
    text,
):

    import main


    original_text = str(text or "").strip()

    # Performance review owns trade-outcome questions before the broad quant
    # router sees words such as "trading" or "analyze".  The response is
    # calculated from the same durable Paper Desk database as the portfolio,
    # preventing stale learning summaries from contradicting actual fills.
    from workstation.paper_trading_desk import is_performance_review_request

    if is_performance_review_request(original_text):
        from workstation.paper_trading_desk import paper_desk

        review = paper_desk.performance_review(days=2)
        daily = review.get("days") or []
        trades = review.get("trades") or []
        if trades:
            sessions = "; ".join(
                f"{item['date']}: {item['trades']} closed, {item['wins']} win, "
                f"{item['losses']} loss, net {float(item['net_pnl']):+,.2f}"
                for item in daily
            )
            findings = "; ".join(review.get("findings") or [])
            response = (
                f"Verified Paper Desk review ({review['timezone']}): {sessions}. "
                + (f"Evidence-based findings: {findings}. " if findings else "No repeated loss pattern was detected. ")
                + "I used the durable portfolio ledger, including stop exits, MFE/MAE, strategy conflicts, "
                "regime compatibility and trailing-policy activation. Adaptation remains bounded and paper-only."
            )
        else:
            response = "No closed Paper Desk trade exists for today or yesterday, so I will not invent a loss explanation."
        conversation_turns.remember(original_text, response, "PAPER_PERFORMANCE_REVIEW")
        return {
            "route": "PAPER_PERFORMANCE_REVIEW",
            "response": response,
            "workspace_actions": [{"type": "open_window", "window": "paper"}],
            "raw": safe(review),
        }

    from agents.local_media_agent import (
        analyze_local_media_request,
        is_local_media_request,
    )

    if is_local_media_request(original_text):
        media = analyze_local_media_request(original_text)
        response = render_response(media)
        conversation_turns.remember(
            original_text,
            response,
            "LOCAL_MEDIA_INTELLIGENCE",
        )
        return {
            "route": "LOCAL_MEDIA_INTELLIGENCE",
            "response": response,
            "raw": safe(media),
        }


    from workstation.quant_terminal_bridge import (
        dispatch_quant_terminal,
        is_quant_terminal_request,
    )


    if is_quant_terminal_request(
        original_text
    ):
        terminal = dispatch_quant_terminal(
            original_text
        )

        payload = terminal.to_dict()

        conversation_turns.remember(
            original_text,
            terminal.response,
            "QUANT_TRADING_INTELLIGENCE",
        )

        return {
            "route":
                "QUANT_TRADING_INTELLIGENCE",

            "response":
                terminal.response,

            "workspace_actions":
                payload[
                    "workspace_actions"
                ],

            "raw":
                safe(
                    payload
                ),
        }


    normalized_original = re.sub(
        r"\s+",
        " ",
        original_text.strip().lower(),
    )

    if re.search(r"\b(?:sing|singing)\b", normalized_original):
        response = (
            "I can sing this short original JARVIS verse through my voice: "
            "Lights in the circuit, stars in the sky; tell me your mission, together we fly. "
            "Data and courage, steady and true; JARVIS is ready to build it with you."
        )
        conversation_turns.remember(
            original_text,
            response,
            "VOICE_ORIGINAL_SONG",
        )
        return {
            "route": "VOICE_ORIGINAL_SONG",
            "response": response,
            "raw": {
                "success": True,
                "original_content": True,
                "speech_enabled": True,
            },
        }


    company_request = bool(
        re.search(
            r"\b(?:i have (?:this |an? )?idea|(?:build|create|start|set ?up|launch) "
            r"(?:a |my )?(?:company|business|startup|venture))\b",
            original_text,
            flags=re.IGNORECASE,
        )
    )
    if company_request:
        from omni.company_os import COMPANY_OS

        plan = COMPANY_OS.create_plan(original_text)
        response = (
            f"Company OS created the supervised venture workspace for {plan['company_name']}. "
            f"It generated {len(plan['artifacts'])} local artifacts, {len(plan['tasks'])} department tasks, "
            f"{len(plan['research_program']['research_tracks'])} evidence tracks, and 1, 4 and 5 year decision gates. "
            "Local research and drafting can continue automatically; publishing, accounts, spending, contracts and outreach remain approval-gated."
        )
        result = {
            "success": True,
            "action": "open_company",
            "plan": plan,
            "company": COMPANY_OS.snapshot(),
            "paper_only": True,
            "live_execution": False,
        }
        conversation_turns.remember(original_text, response, "COMPANY_OS")
        return {"route": "COMPANY_OS", "response": response, "raw": safe(result)}


    from agents.web_intelligence_agent import (
        is_web_request,
        web_intelligence,
    )

    if is_web_request(original_text):
        research = web_intelligence(original_text)
        response = render_response(research)
        conversation_turns.remember(
            original_text,
            response,
            "WEB_INTELLIGENCE",
        )
        return {
            "route": "WEB_INTELLIGENCE",
            "response": response,
            "raw": safe(research),
        }


    if is_reliability_command(
        original_text
    ):

        from agents.reliability_agent import (
            reliability,
        )


        result = reliability(
            original_text
        )


        return {
            "route":
                "RELIABILITY",

            "response":
                render_response(
                    result
                ),

            "raw":
                safe(
                    result
                ),
        }


    monitor_control = paper_monitor_control_request(
        original_text
    )

    if monitor_control:
        from omni.paper_trade_monitor import (
            paper_trade_monitor,
        )

        if monitor_control == "status":
            result = paper_trade_monitor.status()
            response = format_paper_monitor_status(result)

        else:
            symbol, _timeframe = paper_monitor_symbol_timeframe(
                original_text
            )
            result = paper_trade_monitor.stop(
                symbol=symbol,
            )
            stopped = list(result.get("stopped") or [])

            if stopped:
                response = (
                    "Stopped the requested paper monitor. "
                    "Live broker execution remains locked."
                )
            else:
                response = (
                    "No matching active paper monitor was found. "
                    "Live broker execution remains locked."
                )

        conversation_turns.remember(
            original_text,
            response,
            "PAPER_MONITOR_CONTROL",
        )

        return {
            "route": "PAPER_MONITOR_CONTROL",
            "response": response,
            "raw": safe(result),
        }


    if paper_monitor_request(
        original_text
    ):
        symbol, timeframe = paper_monitor_symbol_timeframe(
            original_text
        )

        if not symbol:
            return {
                "route": "PAPER_MONITOR",
                "response": (
                    "I recognized the paper-monitor request, but I could not resolve "
                    "the instrument. I will not silently substitute NIFTY."
                ),
                "raw": {
                    "success": False,
                    "paper_only": True,
                    "live_execution": False,
                },
            }

        from omni.paper_trade_monitor import (
            paper_trade_monitor,
        )

        result = paper_trade_monitor.start(
            symbol,
            timeframe or "15m",
            request=original_text,
        )

        response = (
            f"Paper monitor started for {symbol} on {timeframe or '15m'}. "
            f"I will keep analyzing it in the background and only record a PAPER "
            f"trade when the existing signal and risk engines approve a setup. "
            f"Live broker execution remains locked. Session: {result['session_id']}."
        )

        conversation_turns.remember(
            original_text,
            response,
            "PAPER_MONITOR",
        )

        return {
            "route": "PAPER_MONITOR",
            "response": response,
            "raw": safe(result),
        }


    text = normalize_agent_command(
        original_text
    )


    # --------------------------------------------------------
    # V3.2B FAST TECHNICAL TRADING PATH
    #
    # A compact chart-analysis command has already been
    # classified and normalized by the V3 boundary above.
    # Route it through the governed AgentRegistry directly.
    #
    # This intentionally bypasses broad Master collaboration,
    # which may add research/news agents and network latency.
    # --------------------------------------------------------

    if fast_trading_command(
        text
    ):

        result = main.route_agent(
            "trading",
            text,
        )


        response = render_response(
            result
        )


        conversation_turns.remember(
            original_text,
            response,
            "TRADING_FAST",
        )


        return {
            "route":
                "TRADING_FAST",

            "response":
                response,

            "raw":
                safe(
                    result
                ),
        }


    function = getattr(
        main,
        "jarvis_command",
        None,
    )


    if (
        conversation_turns.is_explanation_followup(
            original_text
        )
        or conversation_turns.is_reference_followup(
            original_text
        )
    ):
        contextual_text = conversation_turns.augment(
            original_text
        )

        result = main.route_agent(
            "chat",
            contextual_text,
        )

        response = render_response(
            result
        )

        conversation_turns.remember(
            original_text,
            response,
            "CHAT_FOLLOWUP",
        )

        return {
            "route": "CHAT_FOLLOWUP",
            "response": response,
            "raw": safe(result),
        }


    if callable(
        function
    ):

        contextual_text = conversation_turns.augment(
            original_text
        )


        result = function(
            contextual_text
        )


        response = render_response(
            result
        )


        conversation_turns.remember(
            original_text,
            response,
            "MASTER_JARVIS",
        )


        return {
            "route":
                "MASTER_JARVIS",

            "response":
                response,

            "raw":
                safe(
                    result
                ),
        }


    operator_request = getattr(
        main,
        "is_operator_request",
        None,
    )


    if (
        callable(
            operator_request
        )
        and operator_request(
            text
        )
    ):

        result = (
            main
            .jarvis_operator_run(
                text
            )
        )


        return {
            "route":
                "OPERATOR",

            "response":
                render_response(
                    result
                ),

            "raw":
                safe(
                    result
                ),
        }


    result = (
        main
        .route_agent(
            "chat",
            text,
        )
    )


    return {
        "route":
            "CHAT",

        "response":
            render_response(
                result
            ),

        "raw":
            safe(
                result
            ),
    }


def status():

    import main

    from omni.core_integrity import (
        verify_protected_core,
    )


    core = verify_protected_core()


    result = {
        "protected_core":
            core.ok,

        "agents":
            [],

        "agent_health":
            [],

        "components":
            {},
    }


    specs = getattr(
        main,
        "default_agent_specs",
        None,
    )


    if callable(
        specs
    ):

        try:

            values = specs()

            result["agent_health"] = agent_readiness(values)


            for item in values:

                name = (
                    getattr(
                        item,
                        "name",
                        None,
                    )
                    or (
                        item.get(
                            "name"
                        )
                        if isinstance(
                            item,
                            dict,
                        )
                        else None
                    )
                )


                if name:

                    result[
                        "agents"
                    ].append(
                        str(
                            name
                        )
                    )


        except Exception:

            pass



    if "reliability" not in result[
        "agents"
    ]:

        result[
            "agents"
        ].append(
            "reliability"
        )


    for name in (
        "jarvis_operator_v5_status",
        "jarvis_voice_v2_status",
        "jarvis_trading_v8_status",
        "jarvis_nautilus_c3_status",
        "jarvis_connected_services_v3_status",
        "jarvis_action_v3_status",
    ):

        function = getattr(
            main,
            name,
            None,
        )


        if callable(
            function
        ):

            try:

                result[
                    "components"
                ][
                    name
                ] = safe(
                    function()
                )

            except Exception as exc:

                result[
                    "components"
                ][
                    name
                ] = {
                    "error":
                        (
                            type(
                                exc
                            ).__name__
                            + ": "
                            + str(
                                exc
                            )
                        )
                }


    try:
        from omni.paper_trade_monitor import (
            paper_trade_monitor,
        )

        result[
            "components"
        ][
            "paper_monitors"
        ] = safe(
            paper_trade_monitor.status()
        )

    except Exception as exc:
        result[
            "components"
        ][
            "paper_monitors"
        ] = {
            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )
        }


    return result


def evidence():

    import main


    function = getattr(
        main,
        "jarvis_operator_v5_evidence",
        None,
    )


    if callable(
        function
    ):

        try:

            return safe(
                function(
                    60
                )
            )

        except Exception:

            pass


    return []


def approvals():

    import main


    function = getattr(
        main,
        "jarvis_connected_approvals",
        None,
    )


    if callable(
        function
    ):

        try:

            return safe(
                function()
            )

        except Exception as exc:

            return {
                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )
            }


    return []


def market():

    import main


    result = {
        "history_count":
            0,

        "latest":
            None,

        "trading":
            None,
    }


    function = getattr(
        main,
        "jarvis_trading_v8_status",
        None,
    )


    if callable(
        function
    ):

        try:

            result[
                "trading"
            ] = safe(
                function()
            )

        except Exception:

            pass


    history = getattr(
        main,
        "jarvis_derivatives_history",
        None,
    )


    if callable(
        history
    ):

        try:

            rows = history(
                "NSE:NIFTY50-INDEX",
                limit=100,
            )


            result[
                "history_count"
            ] = len(
                rows
            )


            if rows:

                result[
                    "latest"
                ] = safe(
                    rows[0]
                )


        except Exception:

            pass


    return result



# ============================================================
# JARVIS OS V3 BACKWARD COMPATIBILITY
#
# V3.1 uses:
#     safe()
#     interpret_workspace_command()
#     market()
#
# Older V3 integrations/tests use:
#     _safe()
#     ui_actions()
#     market_snapshot()
#
# Keep both contracts alive.
# ============================================================


def _safe(
    value,
    depth=0,
):

    return safe(
        value,
        depth,
    )


def ui_actions(
    text,
):

    modern = tuple(
        interpret_workspace_command(
            text
        )
    )


    legacy = []

    seen = set()


    def add(
        action,
    ):

        key = repr(
            sorted(
                action.items()
            )
        )


        if key in seen:

            return


        seen.add(
            key
        )

        legacy.append(
            action
        )


    for action in modern:

        action = dict(
            action
        )


        action_type = action.get(
            "type"
        )


        # ----------------------------------------------------
        # V3's trading workspace was the legacy dashboard.
        #
        # V3.1's native trading surface is "chart".
        #
        # Preserve the historical V3 ui_actions() result
        # without changing V3.1's modern workspace behavior.
        # ----------------------------------------------------

        if (
            action_type
            == "open_window"

            and action.get(
                "window"
            )
            == "chart"
        ):

            add(
                {
                    "type":
                        "open_window",

                    "window":
                        "legacy",
                }
            )

            continue


        # Chart-specific V3.1 actions did not exist in V3.
        # They are intentionally omitted from the old shim.
        if action_type in {
            "chart_symbol",
            "chart_layout",
        }:

            continue


        add(
            action
        )


    return legacy


def market_snapshot():

    current = market()


    return {
        "nifty":
            current.get(
                "latest"
            ),

        "trading_status":
            current.get(
                "trading"
            ),

        "capture_history":
            current.get(
                "history_count",
                0,
            ),
    }


class Handler(
    BaseHTTPRequestHandler
):

    server_version = (
        "JarvisOSV31/1.0"
    )


    def log_message(
        self,
        format,
        *args,
    ):

        return


    def send_json(
        self,
        value,
        code=200,
    ):

        payload = json.dumps(
            safe(
                value
            ),
            ensure_ascii=False,
            default=str,
        ).encode(
            "utf-8"
        )


        self.send_response(
            code
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.send_header(
            "X-Frame-Options",
            "SAMEORIGIN",
        )

        self.end_headers()

        self.wfile.write(
            payload
        )


    def authorized(
        self,
    ):

        return secrets.compare_digest(
            self.headers.get(
                "X-Jarvis-Token",
                "",
            ),
            TOKEN,
        )


    def send_asset(
        self,
        path,
        content_type,
    ):

        if not path.exists():

            self.send_error(
                HTTPStatus.NOT_FOUND
            )

            return


        payload = path.read_bytes()


        self.send_response(
            HTTPStatus.OK
        )

        self.send_header(
            "Content-Type",
            content_type,
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.end_headers()

        self.wfile.write(
            payload
        )


    def do_GET(
        self,
    ):

        parsed = urlparse(
            self.path
        )


        if parsed.path == "/":

            source = (
                ASSETS
                / "index.html"
            ).read_text(
                encoding="utf-8"
            )


            source = source.replace(
                "__JARVIS_TOKEN__",
                TOKEN,
            )


            payload = source.encode(
                "utf-8"
            )


            self.send_response(
                HTTPStatus.OK
            )

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )

            self.send_header(
                "Cache-Control",
                "no-store",
            )

            self.end_headers()

            self.wfile.write(
                payload
            )

            return


        if parsed.path == "/styles.css":

            return self.send_asset(
                ASSETS / "styles.css",
                "text/css; charset=utf-8",
            )


        if parsed.path == "/app.js":

            return self.send_asset(
                ASSETS / "app.js",
                "application/javascript; charset=utf-8",
            )


        if not self.authorized():

            return self.send_json(
                {
                    "error":
                        "unauthorized"
                },
                403,
            )


        try:

            if parsed.path == "/api/status":

                return self.send_json(
                    status()
                )


            if parsed.path == "/api/evidence":

                return self.send_json(
                    evidence()
                )


            if parsed.path == "/api/approvals":

                return self.send_json(
                    approvals()
                )


            if parsed.path == "/api/market":

                return self.send_json(
                    market()
                )


            if parsed.path == "/api/paper-monitors":

                from omni.paper_trade_monitor import (
                    paper_trade_monitor,
                )

                return self.send_json(
                    paper_trade_monitor.status()
                )


            if parsed.path == "/api/paper-portfolio":

                from workstation.paper_trading_desk import (
                    paper_dashboard_payload,
                )

                return self.send_json(
                    paper_dashboard_payload()
                )


            if parsed.path == "/api/company-os":

                from omni.company_os import COMPANY_OS

                return self.send_json(
                    COMPANY_OS.snapshot()
                )


            if parsed.path == "/api/chart":

                query = parse_qs(
                    parsed.query
                )


                symbol = query.get(
                    "symbol",
                    [
                        "NIFTY"
                    ],
                )[0]


                timeframe = query.get(
                    "timeframe",
                    [
                        "15m"
                    ],
                )[0]


                return self.send_json(
                    get_chart(
                        symbol,
                        timeframe,
                        limit=180,
                    )
                )


            if parsed.path == "/api/health":
                from omni.core_integrity import verify_protected_core
                core = verify_protected_core()
                if core.ok:
                    HEALTH.mark_success()
                else:
                    HEALTH.mark_error("PROTECTED_CORE_VALIDATION_FAILED")
                return self.send_json(
                    HEALTH.payload(
                        status="READY" if core.ok else "DEGRADED",
                        healthy=bool(core.ok),
                        dependencies={"protected_core": "READY" if core.ok else "DEGRADED"},
                        protected_core=bool(core.ok),
                    )
                )


            return self.send_json(
                {
                    "error":
                        "not found"
                },
                404,
            )


        except Exception as exc:

            traceback.print_exc()


            return self.send_json(
                {
                    "error":
                        (
                            type(
                                exc
                            ).__name__
                            + ": "
                            + str(
                                exc
                            )
                        )
                },
                500,
            )


    def do_POST(
        self,
    ):

        if not self.authorized():

            return self.send_json(
                {
                    "error":
                        "unauthorized"
                },
                403,
            )


        length = int(
            self.headers.get(
                "Content-Length",
                "0",
            )
        )


        if length > 1_000_000:

            return self.send_json(
                {
                    "error":
                        "payload too large"
                },
                413,
            )


        try:

            body = self.rfile.read(
                length
            )


            data = json.loads(
                body.decode(
                    "utf-8"
                )
                or "{}"
            )


        except Exception:

            return self.send_json(
                {
                    "error":
                        "invalid JSON"
                },
                400,
            )


        if self.path == "/api/command":

            text = str(
                data.get(
                    "text",
                    "",
                )
            ).strip()

            input_mode = str(
                data.get("input_mode", "typed")
                or "typed"
            ).strip().lower()

            speech_confidence = data.get(
                "speech_confidence"
            )


            if not text:

                return self.send_json(
                    {
                        "error":
                            "command required"
                    },
                    400,
                )

            if (
                input_mode == "voice"
                and uncertain_voice_transcript(
                    text,
                    speech_confidence,
                )
            ):

                return self.send_json(
                    {
                        "success": True,
                        "route": "VOICE_CLARIFICATION",
                        "response": (
                            f'I may have heard "{text[:240]}" incorrectly. '
                            "I will not invent its meaning or origin. Please repeat it more slowly "
                            "in Hindi, Hinglish, or English, or type the sentence."
                        ),
                        "workspace_actions": [],
                    }
                )


            actions = (
                interpret_workspace_command(
                    text
                )
            )


            key = command_key(
                text
            )


            cached = cached_command_result(
                key
            )


            if cached is not None:

                return self.send_json(
                    {
                        **cached,
                        "duplicate":
                            "cached",
                    }
                )


            with COMMAND_LOCK:

                if key in COMMAND_INFLIGHT:

                    return self.send_json(
                        {
                            "success":
                                True,

                            "route":
                                "DUPLICATE_SUPPRESSED",

                            "response":
                                (
                                    "I'm already working on "
                                    "that request."
                                ),

                            "workspace_actions":
                                actions,

                            "duplicate":
                                "inflight",
                        }
                    )


                COMMAND_INFLIGHT.add(
                    key
                )


            try:

                result = dispatch_command(
                    text
                )


                payload = {
                    "success":
                        True,

                    "route":
                        result[
                            "route"
                        ],

                    "response":
                        result[
                            "response"
                        ],

                    # Preserve the specialist payload for route-owned windows.
                    # safe() removes non-JSON runtime objects; no credentials
                    # or broker-order capability is added at this boundary.
                    "raw":
                        safe(
                            result.get(
                                "raw"
                            )
                        ),

                    "workspace_actions":
                        actions,
                }


                with COMMAND_LOCK:

                    COMMAND_CACHE[
                        key
                    ] = (
                        time.monotonic(),
                        payload,
                    )


                return self.send_json(
                    payload
                )


            except Exception as exc:

                traceback.print_exc()


                return self.send_json(
                    {
                        "success":
                            False,

                        "route":
                            "ERROR",

                        "response":
                            (
                                type(
                                    exc
                                ).__name__
                                + ": "
                                + str(
                                    exc
                                )
                            ),

                        "workspace_actions":
                            actions,
                    },
                    500,
                )


            finally:

                with COMMAND_LOCK:

                    COMMAND_INFLIGHT.discard(
                        key
                    )


        return self.send_json(
            {
                "error":
                    "not found"
            },
            404,
        )


def create_server(
    host=HOST,
    port=PORT,
):

    return exclusive_server(host, int(port), Handler)


def run_server(
    host=HOST,
    port=PORT,
):

    server = create_server(
        host,
        port,
    )


    print(
        "JARVIS OS V3.1:",
        f"http://{host}:{port}",
    )


    try:

        server.serve_forever()


    finally:

        server.server_close()


if __name__ == "__main__":

    run_server()
