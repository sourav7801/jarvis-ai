from __future__ import annotations

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
    ThreadingHTTPServer,
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


            if isinstance(
                item,
                str,
            ):

                return item


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

                return self.send_json(
                    {
                        "success":
                            True,

                        "version":
                            "3.1",
                    }
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


            if not text:

                return self.send_json(
                    {
                        "error":
                            "command required"
                    },
                    400,
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

    return ThreadingHTTPServer(
        (
            host,
            int(
                port
            ),
        ),
        Handler,
    )


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
