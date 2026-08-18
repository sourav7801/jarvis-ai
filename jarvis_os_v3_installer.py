from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

from pathlib import Path


ROOT = Path(r"C:\Jarvis")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

SERVER = ROOT / "workstation" / "jarvis_os_v3.py"

ASSETS = (
    ROOT
    / "workstation"
    / "jarvis_os_v3_assets"
)

HTML = ASSETS / "index.html"
CSS = ASSETS / "styles.css"
JS = ASSETS / "app.js"

STARTER = ROOT / "start_jarvis_v3.py"
BAT = ROOT / "JARVIS.bat"
FALLBACK_BAT = ROOT / "JARVIS_V2_FALLBACK.bat"

TEST = (
    ROOT
    / "tests"
    / "test_jarvis_os_v3.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "jarvis_os_v3"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)


FILES = (
    SERVER,
    HTML,
    CSS,
    JS,
    STARTER,
    BAT,
    FALLBACK_BAT,
    TEST,
)


BACKUPS = {}


def write(path, text):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(text).lstrip(),
        encoding="utf-8",
        newline="\n",
    )


def run(*args, capture=False, timeout=None):

    return subprocess.run(
        [
            str(PYTHON),
            *args,
        ],
        cwd=ROOT,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def sha(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def rollback():

    print()
    print("=" * 80)
    print("JARVIS OS V3 ROLLBACK")
    print("=" * 80)

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / "backup"
            / path.relative_to(ROOT)
        )

        if existed:

            if backup.exists():

                path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    backup,
                    path,
                )

        else:

            path.unlink(
                missing_ok=True
            )

    print("Rollback: COMPLETE")


print("=" * 80)
print("JARVIS OS V3")
print("MASTER INTELLIGENCE + DOCKABLE MULTI-WINDOW COMMAND CENTER")
print("=" * 80)


# ============================================================
# BASELINE
# ============================================================

print()
print("Checking current JARVIS architecture...")


r = run(
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v8=main.jarvis_trading_v8_status();"
        "assert v8['live_execution'] is False;"
        "assert v8['automatic_broker_order'] is False;"
        "print('Protected Core: PASS');"
        "print('Trading V8: PASS');"
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    print("BASELINE FAILURE")
    sys.exit(1)


# ============================================================
# BACKUP
# ============================================================

for path in FILES:

    existed = path.exists()

    BACKUPS[path] = existed

    if existed:

        destination = (
            ARCHIVE
            / "backup"
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# Preserve currently working launcher separately.
if BAT.exists():

    shutil.copy2(
        BAT,
        ARCHIVE / "JARVIS_BEFORE_V3.bat",
    )


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(ROOT / relative)

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(PROTECTED),
)

print("Rollback foundation: PASS")


# ============================================================
# LOCAL JARVIS OS SERVER
# ============================================================

write(
    SERVER,
    r'''
from __future__ import annotations

import json
import secrets
import socket
import threading
import traceback

from http import HTTPStatus

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)

from pathlib import Path

from urllib.parse import (
    parse_qs,
    urlparse,
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

LEGACY_HOST = "127.0.0.1"
LEGACY_PORT = 8787

TOKEN = secrets.token_urlsafe(32)


def _safe(value, depth=0):

    if depth > 7:

        return str(value)


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


    if isinstance(value, dict):

        result = {}

        for key, item in value.items():

            lowered = str(key).lower()

            if any(
                word in lowered

                for word in (
                    "password",
                    "secret",
                    "token",
                    "authorization",
                    "cookie",
                )
            ):

                result[str(key)] = "<REDACTED>"

            else:

                result[str(key)] = _safe(
                    item,
                    depth + 1,
                )

        return result


    if isinstance(
        value,
        (
            tuple,
            list,
            set,
        ),
    ):

        return [
            _safe(
                item,
                depth + 1,
            )

            for item in value
        ]


    if hasattr(value, "__dict__"):

        return _safe(
            vars(value),
            depth + 1,
        )


    return str(value)


def port_open(port):

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    sock.settimeout(0.25)

    try:

        return (
            sock.connect_ex(
                (
                    "127.0.0.1",
                    int(port),
                )
            )
            == 0
        )

    finally:

        sock.close()


def ui_actions(text):

    lowered = str(text).lower()

    actions = []


    def opened(name):

        actions.append(
            {
                "type":
                    "open_window",

                "window":
                    name,
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "trading terminal",
            "chart lab",
            "open chart",
            "show chart",
            "live chart",
        )
    ):

        opened("legacy")


    if any(
        phrase in lowered

        for phrase in (
            "quant lab",
            "run strategy",
            "strategy signal",
            "give me the signal",
            "find trade",
            "analyze market",
        )
    ):

        opened("quant")


    if any(
        phrase in lowered

        for phrase in (
            "paper desk",
            "paper trade",
            "paper position",
            "paper portfolio",
        )
    ):

        opened("paper")


    if any(
        phrase in lowered

        for phrase in (
            "web intelligence",
            "research",
            "news impact",
            "latest news",
        )
    ):

        opened("research")


    if any(
        phrase in lowered

        for phrase in (
            "mission control",
            "mission queue",
            "active mission",
        )
    ):

        opened("missions")


    if any(
        phrase in lowered

        for phrase in (
            "system core",
            "system health",
            "diagnostics",
        )
    ):

        opened("system")


    if any(
        phrase in lowered

        for phrase in (
            "evidence",
            "approval",
        )
    ):

        opened("evidence")


    if "trading layout" in lowered:

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "trading",
            }
        )


    if "research layout" in lowered:

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "research",
            }
        )


    if "command layout" in lowered:

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "command",
            }
        )


    if "close all windows" in lowered:

        actions.append(
            {
                "type":
                    "close_all",
            }
        )


    return actions


def _render_response(value):

    if isinstance(value, str):

        return value


    if isinstance(value, dict):

        for key in (
            "response",
            "message",
            "answer",
            "text",
            "output",
        ):

            result = value.get(key)

            if isinstance(
                result,
                str,
            ):

                return result


    for key in (
        "response",
        "message",
        "answer",
        "text",
        "output",
    ):

        result = getattr(
            value,
            key,
            None,
        )

        if isinstance(
            result,
            str,
        ):

            return result


    return str(value)


def dispatch_command(text):

    import main


    # Prefer the unified master-command API installed
    # by the previous JARVIS sprint.
    function = getattr(
        main,
        "jarvis_command",
        None,
    )


    if callable(function):

        result = function(text)

        return {
            "route":
                "jarvis_command",

            "response":
                _render_response(result),

            "raw":
                _safe(result),
        }


    # Current workstation installations may expose
    # execute_command directly.
    function = getattr(
        main,
        "execute_command",
        None,
    )


    if callable(function):

        result = function(text)

        return {
            "route":
                "execute_command",

            "response":
                _render_response(result),

            "raw":
                _safe(result),
        }


    operator_request = getattr(
        main,
        "is_operator_request",
        None,
    )


    if (
        callable(operator_request)
        and operator_request(text)
    ):

        result = (
            main
            .jarvis_operator_run(
                text
            )
        )

        return {
            "route":
                "operator",

            "response":
                _render_response(result),

            "raw":
                _safe(result),
        }


    route_agent = getattr(
        main,
        "route_agent",
        None,
    )


    if callable(route_agent):

        result = route_agent(
            "chat",
            text,
        )

        return {
            "route":
                "chat",

            "response":
                _render_response(result),

            "raw":
                _safe(result),
        }


    raise RuntimeError(
        "No JARVIS master command route is available."
    )


def system_status():

    import main


    function = getattr(
        main,
        "jarvis_system_status",
        None,
    )


    if callable(function):

        status = function()

    else:

        status = {
            "protected_core":
                True,
        }


    extra = {}


    for name in (
        "jarvis_operator_v5_status",
        "jarvis_voice_v2_status",
        "jarvis_trading_v8_status",
        "jarvis_nautilus_c3_status",
        "jarvis_connected_services_v3_status",
    ):

        function = getattr(
            main,
            name,
            None,
        )


        if callable(function):

            try:

                extra[name] = function()

            except Exception as exc:

                extra[name] = {
                    "error":
                        (
                            type(exc).__name__
                            + ": "
                            + str(exc)
                        )
                }


    return {
        "system":
            _safe(status),

        "components":
            _safe(extra),

        "legacy_dashboard":
            port_open(
                LEGACY_PORT
            ),

        "legacy_url":
            "http://127.0.0.1:8787",
    }


def evidence():

    import main


    function = getattr(
        main,
        "jarvis_operator_v5_evidence",
        None,
    )


    if callable(function):

        try:

            return _safe(
                function(50)
            )

        except Exception:

            return []


    function = getattr(
        main,
        "jarvis_operator_memory",
        None,
    )


    if callable(function):

        try:

            return _safe(
                function(30)
            )

        except Exception:

            return []


    return []


def market_snapshot():

    import main


    result = {
        "nifty":
            None,

        "trading_status":
            None,

        "capture_history":
            0,
    }


    status = getattr(
        main,
        "jarvis_trading_v8_status",
        None,
    )


    if callable(status):

        try:

            result[
                "trading_status"
            ] = _safe(
                status()
            )

        except Exception:

            pass


    history = getattr(
        main,
        "jarvis_derivatives_history",
        None,
    )


    if callable(history):

        try:

            rows = history(
                "NSE:NIFTY50-INDEX",
                limit=10,
            )


            result[
                "capture_history"
            ] = len(rows)


            if rows:

                result[
                    "nifty"
                ] = _safe(
                    rows[0]
                )


        except Exception:

            pass


    return result


def missions():

    import main


    result = {
        "operator_memory":
            [],

        "evidence":
            [],
    }


    function = getattr(
        main,
        "jarvis_operator_memory",
        None,
    )


    if callable(function):

        try:

            result[
                "operator_memory"
            ] = _safe(
                function(20)
            )

        except Exception:

            pass


    result[
        "evidence"
    ] = evidence()


    return result


class Handler(
    BaseHTTPRequestHandler
):

    server_version = (
        "JarvisOSV3/1.0"
    )


    def log_message(
        self,
        format,
        *args,
    ):

        return


    def _json(
        self,
        value,
        status=200,
    ):

        payload = json.dumps(
            _safe(value),
            ensure_ascii=False,
            default=str,
        ).encode(
            "utf-8"
        )


        self.send_response(status)

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

        self.end_headers()

        self.wfile.write(
            payload
        )


    def _file(
        self,
        path,
        content_type,
    ):

        if not path.exists():

            self.send_error(
                HTTPStatus.NOT_FOUND
            )

            return


        data = path.read_bytes()


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
            "X-Frame-Options",
            "SAMEORIGIN",
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        self.end_headers()

        self.wfile.write(data)


    def _authorized(self):

        return secrets.compare_digest(
            self.headers.get(
                "X-Jarvis-Token",
                "",
            ),
            TOKEN,
        )


    def do_GET(self):

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


            source = source.replace(
                "__LEGACY_URL__",
                "http://127.0.0.1:8787",
            )


            data = source.encode(
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

            self.send_header(
                "X-Content-Type-Options",
                "nosniff",
            )

            self.end_headers()

            self.wfile.write(
                data
            )

            return


        if parsed.path == "/styles.css":

            return self._file(
                ASSETS / "styles.css",
                "text/css; charset=utf-8",
            )


        if parsed.path == "/app.js":

            return self._file(
                ASSETS / "app.js",
                "application/javascript; charset=utf-8",
            )


        if not self._authorized():

            return self._json(
                {
                    "error":
                        "unauthorized"
                },
                403,
            )


        try:

            if parsed.path == "/api/status":

                return self._json(
                    system_status()
                )


            if parsed.path == "/api/evidence":

                return self._json(
                    evidence()
                )


            if parsed.path == "/api/market":

                return self._json(
                    market_snapshot()
                )


            if parsed.path == "/api/missions":

                return self._json(
                    missions()
                )


            if parsed.path == "/api/health":

                return self._json(
                    {
                        "success":
                            True,

                        "jarvis_os":
                            "V3",

                        "legacy":
                            port_open(
                                LEGACY_PORT
                            ),
                    }
                )


            return self._json(
                {
                    "error":
                        "not found"
                },
                404,
            )


        except Exception as exc:

            traceback.print_exc()

            return self._json(
                {
                    "error":
                        (
                            type(exc).__name__
                            + ": "
                            + str(exc)
                        )
                },
                500,
            )


    def do_POST(self):

        if not self._authorized():

            return self._json(
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

            return self._json(
                {
                    "error":
                        "payload too large"
                },
                413,
            )


        body = self.rfile.read(
            length
        )


        try:

            data = json.loads(
                body.decode(
                    "utf-8"
                )
                or "{}"
            )

        except Exception:

            return self._json(
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

                return self._json(
                    {
                        "error":
                            "command required"
                    },
                    400,
                )


            try:

                routed = dispatch_command(
                    text
                )


                return self._json(
                    {
                        "success":
                            True,

                        "command":
                            text,

                        "response":
                            routed.get(
                                "response",
                                "",
                            ),

                        "route":
                            routed.get(
                                "route",
                            ),

                        "ui_actions":
                            ui_actions(
                                text
                            ),
                    }
                )


            except Exception as exc:

                traceback.print_exc()


                return self._json(
                    {
                        "success":
                            False,

                        "command":
                            text,

                        "response":
                            (
                                type(exc).__name__
                                + ": "
                                + str(exc)
                            ),

                        "ui_actions":
                            ui_actions(
                                text
                            ),
                    },
                    500,
                )


        return self._json(
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
            int(port),
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
        "JARVIS OS V3:",
        f"http://{host}:{port}",
    )

    print(
        "Legacy workspace:",
        (
            "ONLINE"
            if port_open(
                LEGACY_PORT
            )
            else "OFFLINE"
        ),
    )


    try:

        server.serve_forever()


    finally:

        server.server_close()


if __name__ == "__main__":

    run_server()
'''
)


print()
print("JARVIS OS V3 backend: SAVED")
print("Part 1 complete.")
print("Paste Part 2 now.")


# ============================================================
# V3 HTML
# ============================================================

write(
    HTML,
    r'''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1.0"
>
<title>JARVIS OS V3</title>
<link
    rel="stylesheet"
    href="/styles.css"
>
</head>

<body>

<div id="bootGlow"></div>

<header id="topbar">

    <div class="brand">
        <div class="brandMark">J</div>

        <div>
            <div class="brandName">
                J A R V I S
            </div>

            <div class="brandSub">
                OMNI OPERATING COMMAND CENTER · V3
            </div>
        </div>
    </div>


    <nav>

        <button
            data-layout="command"
        >
            COMMAND
        </button>

        <button
            data-open="system"
        >
            SYSTEM CORE
        </button>

        <button
            data-open="missions"
        >
            MISSION CONTROL
        </button>

        <button
            data-open="research"
        >
            WEB INTELLIGENCE
        </button>

        <button
            data-open="legacy"
        >
            LIVE WORKSPACE
        </button>

        <button
            data-open="quant"
        >
            QUANT
        </button>

        <button
            data-open="paper"
        >
            PAPER DESK
        </button>

    </nav>


    <div class="systemStrip">

        <span class="greenDot"></span>
        <span id="voiceState">
            VOICE READY
        </span>

        <span class="amber">
            ● APPROVAL GATE
        </span>

        <span class="red">
            ● LIVE EXECUTION LOCKED
        </span>

    </div>

</header>


<section id="masterConsole">

    <div class="consoleTitle">
        MASTER JARVIS
        <span>
            FULL ORCHESTRATOR
        </span>
    </div>


    <div id="conversation">

        <div class="jarvisLine">

            <b>JARVIS</b>

            Master command online.
            Tell me the outcome you want.

        </div>

    </div>


    <div id="commandRow">

        <button id="listenButton">
            ◉ LISTEN
        </button>

        <input
            id="commandInput"
            placeholder="Tell JARVIS what to do…"
            autocomplete="off"
        >

        <button id="executeButton">
            EXECUTE
        </button>

        <button id="stopVoiceButton">
            STOP
        </button>

    </div>

</section>


<main id="desktop">

    <div id="desktopGrid"></div>


    <!-- MASTER CORE -->

    <section
        class="window coreWindow"
        id="win-core"
        data-window="core"
    >

        <header class="windowHeader">

            <span>
                JARVIS ORCHESTRATION CORE
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
            </div>

        </header>


        <div class="windowBody coreBody">

            <div class="orbStage">

                <canvas
                    id="orbCanvas"
                ></canvas>

                <div class="orbCenter">

                    <div class="orbLetter">
                        J
                    </div>

                    <div class="orbOnline">
                        ONLINE
                    </div>

                </div>

            </div>


            <div class="coreSummary">

                <div class="eyebrow">
                    MASTER INTELLIGENCE
                </div>

                <h1>
                    One voice.<br>
                    Every system.
                </h1>

                <p>
                    Master JARVIS routes tools,
                    agents, research, market
                    intelligence and approved
                    computer actions.
                </p>


                <div class="coreBadges">

                    <span>
                        <b id="agentCount">
                            —
                        </b>
                        AGENTS
                    </span>

                    <span>
                        SUPERVISED
                    </span>

                    <span class="locked">
                        EXECUTION LOCKED
                    </span>

                </div>

            </div>

        </div>

    </section>


    <!-- EXISTING REAL WORKSPACE -->

    <section
        class="window legacyWindow"
        id="win-legacy"
        data-window="legacy"
    >

        <header class="windowHeader">

            <span>
                LIVE JARVIS WORKSPACE · EXISTING MODULES
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div class="windowBody iframeBody">

            <iframe
                id="legacyFrame"
                src="__LEGACY_URL__"
                title="Existing JARVIS workspace"
            ></iframe>

            <div
                id="legacyOffline"
                class="offlinePanel hidden"
            >

                Existing 8787 workspace is offline.

                <button id="legacyRefresh">
                    RETRY
                </button>

            </div>

        </div>

    </section>


    <!-- OPERATIONS -->

    <section
        class="window opsWindow"
        id="win-missions"
        data-window="missions"
    >

        <header class="windowHeader">

            <span>
                INTELLIGENCE & OPERATIONS
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div class="windowBody">

            <div class="metricGrid">

                <div>
                    <span>CORE</span>
                    <strong id="coreHealth">
                        …
                    </strong>
                </div>

                <div>
                    <span>LEGACY UI</span>
                    <strong id="legacyHealth">
                        …
                    </strong>
                </div>

                <div>
                    <span>TRADING</span>
                    <strong id="tradingHealth">
                        …
                    </strong>
                </div>

                <div>
                    <span>VOICE</span>
                    <strong id="voiceHealth">
                        …
                    </strong>
                </div>

            </div>


            <h3>
                RECENT ACTIVITY
            </h3>

            <div
                id="missionFeed"
                class="feed"
            ></div>

        </div>

    </section>


    <!-- SYSTEM -->

    <section
        class="window systemWindow"
        id="win-system"
        data-window="system"
    >

        <header class="windowHeader">

            <span>
                SYSTEM CORE
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div
            id="systemContent"
            class="windowBody dataPanel"
        >
            Loading…
        </div>

    </section>


    <!-- QUANT -->

    <section
        class="window quantWindow"
        id="win-quant"
        data-window="quant"
    >

        <header class="windowHeader">

            <span>
                QUANT / STRATEGY SIGNAL CENTER
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div class="windowBody">

            <div class="signalHero">

                <div>

                    <div class="eyebrow">
                        RESEARCH ENGINE
                    </div>

                    <h2 id="quantState">
                        READY
                    </h2>

                    <p>
                        V4 evolution → V5 validation
                        → Nautilus C3 validation
                    </p>

                </div>


                <div class="signalLock">
                    PAPER / RESEARCH
                </div>

            </div>


            <div
                id="marketSnapshot"
                class="marketCards"
            ></div>


            <button
                class="commandAction"
                data-command="Analyze NIFTY and give me the strongest research setup and explain the evidence."
            >
                RUN MARKET ANALYSIS
            </button>

        </div>

    </section>


    <!-- PAPER -->

    <section
        class="window paperWindow"
        id="win-paper"
        data-window="paper"
    >

        <header class="windowHeader">

            <span>
                PAPER EXECUTION DESK
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div class="windowBody">

            <div class="paperHero">
                SYNTHETIC EXECUTION
            </div>

            <p>
                Strategy simulation and paper
                positions only.
                No broker order is sent.
            </p>


            <button
                class="commandAction"
                data-command="Show my paper trading status and current simulated positions."
            >
                PAPER STATUS
            </button>

            <button
                class="commandAction"
                data-command="Scan the market for qualified paper setups."
            >
                SCAN NOW
            </button>

        </div>

    </section>


    <!-- RESEARCH -->

    <section
        class="window researchWindow"
        id="win-research"
        data-window="research"
    >

        <header class="windowHeader">

            <span>
                WEB INTELLIGENCE
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div class="windowBody">

            <div class="researchHero">

                SEARCH → READ →
                COMPARE → CITE

            </div>


            <button
                class="commandAction"
                data-command="Research the most important market-moving news right now and summarize the evidence."
            >
                RUN INTELLIGENCE SCAN
            </button>


            <button
                class="commandAction"
                data-command="Research crude oil and explain the major current catalysts."
            >
                CRUDE OIL RESEARCH
            </button>

        </div>

    </section>


    <!-- EVIDENCE -->

    <section
        class="window evidenceWindow"
        id="win-evidence"
        data-window="evidence"
    >

        <header class="windowHeader">

            <span>
                EVIDENCE / APPROVALS
            </span>

            <div class="windowControls">
                <button data-minimize>—</button>
                <button data-maximize>□</button>
                <button data-close>×</button>
            </div>

        </header>


        <div
            id="evidenceFeed"
            class="windowBody feed"
        ></div>

    </section>


</main>


<footer id="dock">

    <div class="dockStatus">

        <span class="greenDot"></span>

        <b>
            MASTER JARVIS
        </b>

        <span id="readyStatus">
            CONNECTING
        </span>

    </div>


    <div class="dockApps">

        <button data-open="core">
            ◉ CORE
        </button>

        <button data-open="legacy">
            ▦ LIVE WORKSPACE
        </button>

        <button data-open="quant">
            ◫ QUANT
        </button>

        <button data-open="paper">
            ◩ PAPER
        </button>

        <button data-open="research">
            ◎ RESEARCH
        </button>

        <button data-open="missions">
            ◈ MISSIONS
        </button>

        <button data-open="system">
            ⚙ SYSTEM
        </button>

        <button data-open="evidence">
            ✓ EVIDENCE
        </button>

    </div>


    <div class="layoutButtons">

        <button data-layout="command">
            COMMAND
        </button>

        <button data-layout="trading">
            TRADING
        </button>

        <button data-layout="research">
            RESEARCH
        </button>

    </div>

</footer>


<script>
window.JARVIS_TOKEN =
    "__JARVIS_TOKEN__";

window.LEGACY_URL =
    "__LEGACY_URL__";
</script>

<script src="/app.js"></script>

</body>
</html>
'''
)


# ============================================================
# V3 CSS
# ============================================================

write(
    CSS,
    r'''
:root {
    --bg: #02080d;
    --panel: rgba(5, 18, 28, .94);
    --panel2: rgba(8, 28, 41, .96);
    --line: rgba(94, 211, 255, .23);
    --cyan: #67dbff;
    --cyan2: #17bfe9;
    --green: #69f5aa;
    --amber: #ffd463;
    --red: #ff6673;
    --text: #ecf8ff;
    --muted: #7794a5;
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background:
        radial-gradient(
            circle at 50% 35%,
            #08283b 0,
            #03111a 28%,
            #01070b 70%
        );
    color: var(--text);
    font-family:
        "Segoe UI",
        system-ui,
        sans-serif;
}

button,
input {
    font: inherit;
}

button {
    cursor: pointer;
}

#bootGlow {
    position: fixed;
    inset: -50%;
    pointer-events: none;
    background:
        radial-gradient(
            circle,
            rgba(47, 199, 255, .06),
            transparent 40%
        );
    animation: pulseGlow 5s infinite alternate;
}

@keyframes pulseGlow {
    from {
        opacity: .35;
        transform: scale(.98);
    }

    to {
        opacity: .8;
        transform: scale(1.03);
    }
}

#topbar {
    height: 66px;
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 8px 16px;
    background:
        linear-gradient(
            180deg,
            rgba(8, 25, 36, .98),
            rgba(2, 10, 16, .98)
        );
    border-bottom: 1px solid var(--line);
    box-shadow:
        0 10px 45px rgba(0, 0, 0, .6);
    position: relative;
    z-index: 5000;
}

.brand {
    display: flex;
    align-items: center;
    min-width: 260px;
}

.brandMark {
    width: 43px;
    height: 43px;
    display: grid;
    place-items: center;
    border:
        1px solid var(--cyan);
    border-radius: 10px;
    color: var(--cyan);
    font-weight: 900;
    font-size: 21px;
    box-shadow:
        inset 0 0 20px rgba(75, 210, 255, .08),
        0 0 20px rgba(75, 210, 255, .08);
    margin-right: 12px;
}

.brandName {
    letter-spacing: 9px;
    font-size: 17px;
    font-weight: 800;
}

.brandSub {
    letter-spacing: 2px;
    font-size: 8px;
    color: var(--muted);
    margin-top: 3px;
}

nav {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1;
}

nav button,
#dock button,
.window button,
#commandRow button {
    color: #c8e1ec;
    border: 1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(11, 34, 47, .95),
            rgba(4, 17, 25, .95)
        );
    border-radius: 7px;
    padding: 8px 11px;
}

nav button:hover,
#dock button:hover,
.commandAction:hover {
    border-color: var(--cyan);
    color: white;
    box-shadow:
        0 0 18px rgba(60, 201, 255, .15);
}

.systemStrip {
    display: flex;
    align-items: center;
    gap: 11px;
    font-size: 10px;
    white-space: nowrap;
}

.greenDot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--green);
    box-shadow:
        0 0 10px var(--green);
    display: inline-block;
}

.amber {
    color: var(--amber);
}

.red {
    color: var(--red);
}

#masterConsole {
    height: 156px;
    margin: 8px;
    padding: 10px;
    border:
        1px solid var(--line);
    border-radius: 11px;
    background:
        linear-gradient(
            140deg,
            rgba(6, 22, 32, .97),
            rgba(2, 10, 16, .97)
        );
    position: relative;
    z-index: 4000;
    box-shadow:
        0 16px 45px rgba(0, 0, 0, .35);
}

.consoleTitle {
    color: var(--green);
    font-size: 10px;
    letter-spacing: 2px;
    margin-bottom: 7px;
}

.consoleTitle span {
    float: right;
    color: var(--muted);
}

#conversation {
    height: 69px;
    overflow-y: auto;
    border:
        1px solid rgba(95, 200, 238, .12);
    background: #010609;
    padding: 6px 9px;
    font-size: 12px;
}

.conversationLine {
    padding: 5px 0;
    border-bottom:
        1px solid rgba(91, 188, 225, .1);
}

.youLine b {
    color: var(--cyan);
    margin-right: 10px;
}

.jarvisLine b {
    color: var(--green);
    margin-right: 10px;
}

#commandRow {
    display: flex;
    gap: 7px;
    margin-top: 8px;
}

#commandInput {
    flex: 1;
    color: white;
    border: 1px solid var(--line);
    background: #020b11;
    border-radius: 7px;
    padding: 9px 12px;
    outline: none;
}

#commandInput:focus {
    border-color: var(--cyan);
    box-shadow:
        0 0 14px rgba(80, 211, 255, .12);
}

#listenButton {
    color: var(--cyan) !important;
}

#executeButton {
    border-color:
        rgba(100, 220, 255, .55) !important;
}

#desktop {
    position: absolute;
    left: 8px;
    right: 8px;
    top: 238px;
    bottom: 60px;
    overflow: hidden;
    border:
        1px solid rgba(89, 206, 249, .1);
    border-radius: 12px;
    background:
        linear-gradient(
            rgba(8, 30, 43, .08) 1px,
            transparent 1px
        ),
        linear-gradient(
            90deg,
            rgba(8, 30, 43, .08) 1px,
            transparent 1px
        );
    background-size:
        36px 36px;
}

.window {
    position: absolute;
    min-width: 280px;
    min-height: 180px;
    border:
        1px solid rgba(78, 197, 239, .24);
    border-radius: 10px;
    background:
        linear-gradient(
            155deg,
            rgba(7, 25, 36, .97),
            rgba(2, 10, 16, .98)
        );
    box-shadow:
        0 20px 70px rgba(0, 0, 0, .55),
        inset 0 1px 0 rgba(255, 255, 255, .025);
    overflow: hidden;
    resize: both;
    backdrop-filter: blur(14px);
}

.window.activeWindow {
    border-color:
        rgba(94, 216, 255, .55);
    box-shadow:
        0 24px 90px rgba(0, 0, 0, .7),
        0 0 28px rgba(44, 183, 232, .08);
}

.window.maximized {
    left: 6px !important;
    top: 6px !important;
    width: calc(100% - 12px) !important;
    height: calc(100% - 12px) !important;
    resize: none;
}

.window.minimized .windowBody {
    display: none;
}

.window.minimized {
    height: 39px !important;
    min-height: 39px;
    resize: none;
}

.windowHeader {
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: move;
    padding:
        0 8px 0 12px;
    font-size: 9px;
    letter-spacing: 1.7px;
    color: var(--cyan);
    background:
        linear-gradient(
            180deg,
            rgba(13, 41, 56, .96),
            rgba(4, 20, 29, .96)
        );
    border-bottom:
        1px solid var(--line);
    user-select: none;
}

.windowControls {
    display: flex;
    gap: 3px;
}

.windowControls button {
    width: 29px;
    height: 26px;
    padding: 0;
    font-size: 11px;
}

.windowBody {
    height: calc(100% - 38px);
    padding: 12px;
    overflow: auto;
}

.coreWindow {
    left: 35%;
    top: 4%;
    width: 30%;
    height: 50%;
}

.legacyWindow {
    left: 1%;
    top: 2%;
    width: 33%;
    height: 58%;
}

.opsWindow {
    left: 66%;
    top: 2%;
    width: 33%;
    height: 45%;
}

.quantWindow {
    left: 34%;
    top: 55%;
    width: 31%;
    height: 43%;
}

.paperWindow {
    left: 1%;
    top: 62%;
    width: 32%;
    height: 36%;
}

.researchWindow {
    left: 66%;
    top: 49%;
    width: 33%;
    height: 49%;
}

.systemWindow {
    display: none;
    left: 13%;
    top: 10%;
    width: 74%;
    height: 78%;
}

.evidenceWindow {
    display: none;
    left: 55%;
    top: 12%;
    width: 42%;
    height: 65%;
}

.coreBody {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 18px;
    overflow: hidden;
}

.orbStage {
    width: 52%;
    aspect-ratio: 1;
    position: relative;
}

#orbCanvas {
    width: 100%;
    height: 100%;
}

.orbCenter {
    position: absolute;
    left: 50%;
    top: 50%;
    transform:
        translate(-50%, -50%);
    text-align: center;
    pointer-events: none;
}

.orbLetter {
    font-size: 54px;
    font-weight: 900;
    color: white;
    text-shadow:
        0 0 15px var(--cyan),
        0 0 40px var(--cyan);
}

.orbOnline {
    color: var(--green);
    font-size: 8px;
    letter-spacing: 3px;
}

.coreSummary {
    flex: 1;
}

.coreSummary h1 {
    font-size: 28px;
    line-height: 1.03;
    margin: 7px 0 12px;
}

.coreSummary p {
    color: #9eb5c1;
    line-height: 1.5;
    font-size: 12px;
}

.eyebrow {
    color: #7b9aaa;
    font-size: 8px;
    letter-spacing: 2px;
}

.coreBadges {
    display: flex;
    gap: 6px;
    margin-top: 14px;
    flex-wrap: wrap;
}

.coreBadges span {
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 8px;
    font-size: 8px;
}

.coreBadges b {
    display: block;
    color: var(--cyan);
    font-size: 18px;
}

.coreBadges .locked {
    color: var(--red);
}

.iframeBody {
    padding: 0;
}

iframe {
    border: 0;
    width: 100%;
    height: 100%;
    background: #000;
}

.hidden {
    display: none !important;
}

.offlinePanel {
    position: absolute;
    inset: 38px 0 0;
    display: grid;
    place-items: center;
    text-align: center;
    background: #02090e;
    color: var(--red);
}

.metricGrid {
    display: grid;
    grid-template-columns:
        repeat(2, 1fr);
    gap: 7px;
}

.metricGrid > div,
.marketCards > div {
    padding: 11px;
    border:
        1px solid var(--line);
    background:
        rgba(9, 31, 44, .7);
    border-radius: 7px;
}

.metricGrid span,
.marketCards span {
    display: block;
    color: var(--muted);
    font-size: 8px;
    letter-spacing: 1.4px;
}

.metricGrid strong {
    display: block;
    margin-top: 4px;
    color: var(--green);
}

.window h3 {
    color: var(--cyan);
    font-size: 9px;
    letter-spacing: 1.6px;
    margin-top: 13px;
}

.feed {
    font-size: 10px;
}

.feedItem {
    padding: 8px;
    border-bottom:
        1px solid rgba(88, 191, 229, .12);
}

.feedItem .time {
    color: var(--muted);
}

.dataPanel {
    white-space: pre-wrap;
    font-family:
        Consolas,
        monospace;
    font-size: 10px;
    color: #9cc5d7;
}

.signalHero {
    display: flex;
    justify-content: space-between;
    border-bottom:
        1px solid var(--line);
    padding-bottom: 12px;
}

.signalHero h2 {
    color: var(--cyan);
    margin:
        5px 0 2px;
}

.signalHero p {
    margin: 0;
    color: var(--muted);
    font-size: 10px;
}

.signalLock {
    color: var(--amber);
    border:
        1px solid rgba(255, 202, 85, .3);
    border-radius: 7px;
    padding: 9px;
    height: fit-content;
    font-size: 8px;
}

.marketCards {
    display: grid;
    grid-template-columns:
        repeat(2, 1fr);
    gap: 7px;
    margin-top: 10px;
}

.marketCards strong {
    font-size: 16px;
    display: block;
    margin-top: 3px;
}

.commandAction {
    margin-top: 10px;
    margin-right: 5px;
}

.paperHero,
.researchHero {
    color: var(--green);
    font-size: 18px;
    margin-bottom: 9px;
}

#dock {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 53px;
    z-index: 6000;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 13px;
    border-top:
        1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(6, 22, 31, .98),
            rgba(1, 7, 11, .99)
        );
}

.dockStatus {
    min-width: 210px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 9px;
}

#readyStatus {
    color: var(--green);
}

.dockApps {
    display: flex;
    gap: 4px;
}

.layoutButtons {
    display: flex;
    gap: 4px;
}

#dock button {
    padding: 7px 8px;
    font-size: 8px;
}

@media (max-width: 1200px) {

    nav {
        display: none;
    }

    .systemStrip .amber,
    .systemStrip .red {
        display: none;
    }

    .dockApps button {
        font-size: 0;
        width: 34px;
    }

}
'''
)


# ============================================================
# V3 JS
# ============================================================

write(
    JS,
    r'''
const token =
    window.JARVIS_TOKEN;

let topZ = 50;

let recognition = null;

let speaking = false;


async function api(
    path,
    options = {}
) {

    options.headers = {
        ...(options.headers || {}),
        "X-Jarvis-Token": token,
        "Content-Type": "application/json"
    };


    const response =
        await fetch(
            path,
            options
        );


    const data =
        await response.json();


    if (!response.ok) {

        throw new Error(
            data.error ||
            "JARVIS API failure"
        );
    }


    return data;
}


function appendConversation(
    who,
    text
) {

    const conversation =
        document.getElementById(
            "conversation"
        );


    const line =
        document.createElement(
            "div"
        );


    line.className =
        "conversationLine " +
        (
            who === "YOU"
            ? "youLine"
            : "jarvisLine"
        );


    const label =
        document.createElement(
            "b"
        );


    label.textContent = who;


    line.appendChild(
        label
    );


    line.appendChild(
        document.createTextNode(
            text
        )
    );


    conversation.appendChild(
        line
    );


    conversation.scrollTop =
        conversation.scrollHeight;
}


function bringFront(win) {

    topZ += 1;

    win.style.zIndex =
        String(topZ);


    document
        .querySelectorAll(
            ".window"
        )
        .forEach(
            item =>
                item.classList
                    .remove(
                        "activeWindow"
                    )
        );


    win.classList.add(
        "activeWindow"
    );
}


function showWindow(id) {

    const win =
        document.getElementById(
            "win-" + id
        );


    if (!win) {
        return;
    }


    win.style.display =
        "block";


    win.classList.remove(
        "minimized"
    );


    bringFront(win);
}


function closeWindow(id) {

    const win =
        document.getElementById(
            "win-" + id
        );


    if (
        !win ||
        id === "core"
    ) {
        return;
    }


    win.style.display =
        "none";
}


function closeAll() {

    document
        .querySelectorAll(
            ".window"
        )
        .forEach(
            win => {

                if (
                    win.dataset.window
                    !== "core"
                ) {

                    win.style.display =
                        "none";
                }
            }
        );


    showWindow(
        "core"
    );
}


function applyLayout(name) {

    const ids = [
        "core",
        "legacy",
        "missions",
        "system",
        "quant",
        "paper",
        "research",
        "evidence"
    ];


    for (const id of ids) {

        const win =
            document.getElementById(
                "win-" + id
            );


        if (!win) continue;


        win.classList.remove(
            "maximized",
            "minimized"
        );
    }


    if (name === "command") {

        showWindow("core");
        showWindow("legacy");
        showWindow("missions");
        showWindow("quant");
        showWindow("paper");
        showWindow("research");

        closeWindow("system");
        closeWindow("evidence");
    }


    if (name === "trading") {

        showWindow("legacy");
        showWindow("quant");
        showWindow("paper");
        showWindow("missions");

        closeWindow("research");
        closeWindow("system");
        closeWindow("evidence");

        const legacy =
            document.getElementById(
                "win-legacy"
            );

        legacy.style.left = "1%";
        legacy.style.top = "2%";
        legacy.style.width = "54%";
        legacy.style.height = "60%";


        const quant =
            document.getElementById(
                "win-quant"
            );

        quant.style.left = "56%";
        quant.style.top = "2%";
        quant.style.width = "43%";
        quant.style.height = "45%";


        const paper =
            document.getElementById(
                "win-paper"
            );

        paper.style.left = "1%";
        paper.style.top = "64%";
        paper.style.width = "54%";
        paper.style.height = "34%";


        const missions =
            document.getElementById(
                "win-missions"
            );

        missions.style.left = "56%";
        missions.style.top = "49%";
        missions.style.width = "43%";
        missions.style.height = "49%";
    }


    if (name === "research") {

        showWindow("research");
        showWindow("legacy");
        showWindow("core");
        showWindow("missions");

        closeWindow("quant");
        closeWindow("paper");
        closeWindow("system");
        closeWindow("evidence");


        const research =
            document.getElementById(
                "win-research"
            );

        research.style.left = "1%";
        research.style.top = "2%";
        research.style.width = "55%";
        research.style.height = "96%";


        const legacy =
            document.getElementById(
                "win-legacy"
            );

        legacy.style.left = "57%";
        legacy.style.top = "2%";
        legacy.style.width = "42%";
        legacy.style.height = "55%";


        const missions =
            document.getElementById(
                "win-missions"
            );

        missions.style.left = "57%";
        missions.style.top = "59%";
        missions.style.width = "42%";
        missions.style.height = "39%";
    }


    saveLayout();
}


function saveLayout() {

    const state = {};


    document
        .querySelectorAll(
            ".window"
        )
        .forEach(
            win => {

                state[
                    win.dataset.window
                ] = {
                    display:
                        win.style.display,
                    left:
                        win.style.left,
                    top:
                        win.style.top,
                    width:
                        win.style.width,
                    height:
                        win.style.height
                };
            }
        );


    localStorage.setItem(
        "jarvisV3Layout",
        JSON.stringify(state)
    );
}


function restoreLayout() {

    try {

        const state =
            JSON.parse(
                localStorage.getItem(
                    "jarvisV3Layout"
                )
            );


        if (!state) return;


        for (
            const [id, value]
            of Object.entries(state)
        ) {

            const win =
                document.getElementById(
                    "win-" + id
                );


            if (!win) continue;


            if (value.display)
                win.style.display =
                    value.display;

            if (value.left)
                win.style.left =
                    value.left;

            if (value.top)
                win.style.top =
                    value.top;

            if (value.width)
                win.style.width =
                    value.width;

            if (value.height)
                win.style.height =
                    value.height;
        }

    } catch (_) {}
}


function makeDraggable(win) {

    const header =
        win.querySelector(
            ".windowHeader"
        );


    let dragging = false;

    let startX = 0;
    let startY = 0;

    let startLeft = 0;
    let startTop = 0;


    header.addEventListener(
        "mousedown",
        event => {

            if (
                event.target.tagName
                === "BUTTON"
            ) {
                return;
            }


            dragging = true;

            bringFront(win);


            startX =
                event.clientX;

            startY =
                event.clientY;


            startLeft =
                win.offsetLeft;

            startTop =
                win.offsetTop;


            event.preventDefault();
        }
    );


    window.addEventListener(
        "mousemove",
        event => {

            if (!dragging)
                return;


            const desktop =
                document.getElementById(
                    "desktop"
                );


            const newLeft =
                Math.max(
                    0,
                    Math.min(
                        desktop.clientWidth
                            - 120,

                        startLeft
                        + event.clientX
                        - startX
                    )
                );


            const newTop =
                Math.max(
                    0,
                    Math.min(
                        desktop.clientHeight
                            - 40,

                        startTop
                        + event.clientY
                        - startY
                    )
                );


            win.style.left =
                newLeft + "px";

            win.style.top =
                newTop + "px";
        }
    );


    window.addEventListener(
        "mouseup",
        () => {

            if (dragging) {

                dragging =
                    false;

                saveLayout();
            }
        }
    );


    win.addEventListener(
        "mousedown",
        () =>
            bringFront(win)
    );
}


async function executeCommand(
    forcedText = null
) {

    const input =
        document.getElementById(
            "commandInput"
        );


    const text =
        (
            forcedText
            ?? input.value
        ).trim();


    if (!text) return;


    input.value = "";


    appendConversation(
        "YOU",
        text
    );


    document.getElementById(
        "readyStatus"
    ).textContent =
        "THINKING";


    try {

        const result =
            await api(
                "/api/command",
                {
                    method: "POST",
                    body: JSON.stringify(
                        {
                            text
                        }
                    )
                }
            );


        appendConversation(
            "JARVIS",
            result.response ||
            "Completed."
        );


        for (
            const action
            of (
                result.ui_actions
                || []
            )
        ) {

            if (
                action.type
                === "open_window"
            ) {

                showWindow(
                    action.window
                );
            }


            if (
                action.type
                === "layout"
            ) {

                applyLayout(
                    action.layout
                );
            }


            if (
                action.type
                === "close_all"
            ) {

                closeAll();
            }
        }


        if (speaking) {

            speechSynthesis.cancel();


            const utterance =
                new SpeechSynthesisUtterance(
                    result.response ||
                    "Completed."
                );


            speechSynthesis.speak(
                utterance
            );
        }


    } catch (error) {

        appendConversation(
            "JARVIS",
            "ERROR: "
            + error.message
        );
    }


    document.getElementById(
        "readyStatus"
    ).textContent =
        "READY";
}


async function refreshStatus() {

    try {

        const status =
            await api(
                "/api/status"
            );


        const system =
            status.system || {};


        document.getElementById(
            "coreHealth"
        ).textContent =
            (
                system.protected_core
                ? "ONLINE"
                : "FAULT"
            );


        document.getElementById(
            "legacyHealth"
        ).textContent =
            (
                status.legacy_dashboard
                ? "ONLINE"
                : "OFFLINE"
            );


        const components =
            status.components || {};


        const trading =
            components
                .jarvis_trading_v8_status
                || {};


        document.getElementById(
            "tradingHealth"
        ).textContent =
            (
                trading.live_execution
                === false
                ? "RESEARCH"
                : "UNKNOWN"
            );


        const voice =
            components
                .jarvis_voice_v2_status
                || {};


        document.getElementById(
            "voiceHealth"
        ).textContent =
            (
                voice.speech_recognition
                ? "READY"
                : "DEGRADED"
            );


        document.getElementById(
            "systemContent"
        ).textContent =
            JSON.stringify(
                status,
                null,
                2
            );


        document.getElementById(
            "readyStatus"
        ).textContent =
            "READY";


        if (
            !status.legacy_dashboard
        ) {

            document.getElementById(
                "legacyOffline"
            ).classList.remove(
                "hidden"
            );

        } else {

            document.getElementById(
                "legacyOffline"
            ).classList.add(
                "hidden"
            );
        }


    } catch (_) {

        document.getElementById(
            "readyStatus"
        ).textContent =
            "DEGRADED";
    }
}


async function refreshEvidence() {

    try {

        const rows =
            await api(
                "/api/evidence"
            );


        const feed =
            document.getElementById(
                "evidenceFeed"
            );


        feed.innerHTML = "";


        for (
            const row
            of (
                rows || []
            ).slice(-30).reverse()
        ) {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "feedItem";


            const event =
                row.event
                || row.goal
                || "ACTIVITY";


            const time =
                row.timestamp
                || "";


            item.textContent =
                event
                + "  "
                + time;


            feed.appendChild(
                item
            );
        }


        const missionFeed =
            document.getElementById(
                "missionFeed"
            );


        missionFeed.innerHTML =
            feed.innerHTML;


    } catch (_) {}
}


async function refreshMarket() {

    try {

        const data =
            await api(
                "/api/market"
            );


        const holder =
            document.getElementById(
                "marketSnapshot"
            );


        const nifty =
            data.nifty || {};


        holder.innerHTML = `
            <div>
                <span>NIFTY SPOT</span>
                <strong>
                    ${
                        nifty.spot
                        ?? "NO STORED DATA"
                    }
                </strong>
            </div>

            <div>
                <span>ATM IV</span>
                <strong>
                    ${
                        nifty.atm_iv
                        ?? "—"
                    }
                </strong>
            </div>

            <div>
                <span>PCR OI</span>
                <strong>
                    ${
                        nifty.pcr_oi
                        ?? "—"
                    }
                </strong>
            </div>

            <div>
                <span>CHAIN HISTORY</span>
                <strong>
                    ${
                        data.capture_history
                        ?? 0
                    }
                </strong>
            </div>
        `;


        document.getElementById(
            "quantState"
        ).textContent =
            (
                data.trading_status
                ? "ENGINE READY"
                : "DEGRADED"
            );


    } catch (_) {}
}


function setupVoice() {

    const Recognition =
        window.SpeechRecognition
        || window.webkitSpeechRecognition;


    if (!Recognition) {

        document.getElementById(
            "listenButton"
        ).textContent =
            "MIC N/A";

        return;
    }


    recognition =
        new Recognition();


    recognition.lang =
        "en-IN";


    recognition.interimResults =
        true;


    recognition.continuous =
        false;


    recognition.onstart = () => {

        document.getElementById(
            "voiceState"
        ).textContent =
            "LISTENING";

        document.getElementById(
            "listenButton"
        ).textContent =
            "● LISTENING";
    };


    recognition.onresult =
        event => {

            let transcript = "";


            for (
                let i =
                    event.resultIndex;

                i <
                    event.results.length;

                i++
            ) {

                transcript +=
                    event.results[i][0]
                        .transcript;
            }


            document.getElementById(
                "commandInput"
            ).value =
                transcript;
        };


    recognition.onend = () => {

        document.getElementById(
            "voiceState"
        ).textContent =
            "VOICE READY";

        document.getElementById(
            "listenButton"
        ).textContent =
            "◉ LISTEN";
    };
}


function drawOrb() {

    const canvas =
        document.getElementById(
            "orbCanvas"
        );


    const ctx =
        canvas.getContext(
            "2d"
        );


    function resize() {

        const ratio =
            window.devicePixelRatio
            || 1;


        const rect =
            canvas.getBoundingClientRect();


        canvas.width =
            rect.width * ratio;

        canvas.height =
            rect.height * ratio;


        ctx.setTransform(
            ratio,
            0,
            0,
            ratio,
            0,
            0
        );
    }


    resize();


    window.addEventListener(
        "resize",
        resize
    );


    let t = 0;


    function render() {

        const rect =
            canvas.getBoundingClientRect();


        const w =
            rect.width;

        const h =
            rect.height;


        const cx =
            w / 2;

        const cy =
            h / 2;


        ctx.clearRect(
            0,
            0,
            w,
            h
        );


        const glow =
            ctx.createRadialGradient(
                cx,
                cy,
                5,
                cx,
                cy,
                w * .42
            );


        glow.addColorStop(
            0,
            "rgba(98,220,255,.45)"
        );

        glow.addColorStop(
            .3,
            "rgba(26,151,207,.16)"
        );

        glow.addColorStop(
            1,
            "rgba(0,0,0,0)"
        );


        ctx.fillStyle =
            glow;


        ctx.beginPath();

        ctx.arc(
            cx,
            cy,
            w * .42,
            0,
            Math.PI * 2
        );

        ctx.fill();


        for (
            let ring = 0;
            ring < 5;
            ring++
        ) {

            ctx.save();

            ctx.translate(
                cx,
                cy
            );


            ctx.rotate(
                t
                * (
                    .002
                    + ring * .0009
                )
                * (
                    ring % 2
                    ? -1
                    : 1
                )
            );


            ctx.strokeStyle =
                `rgba(
                    88,
                    214,
                    255,
                    ${
                        .18
                        + ring * .07
                    }
                )`;


            ctx.lineWidth =
                1;


            ctx.beginPath();


            ctx.ellipse(
                0,
                0,
                w
                    * (
                        .22
                        + ring * .035
                    ),
                h
                    * (
                        .10
                        + ring * .035
                    ),
                ring * .4,
                0,
                Math.PI * 2
            );


            ctx.stroke();

            ctx.restore();
        }


        for (
            let i = 0;
            i < 24;
            i++
        ) {

            const angle =
                t * .003
                + i
                * Math.PI
                * 2
                / 24;


            const radius =
                w
                * (
                    .28
                    + .055
                    * Math.sin(
                        i * 2.1
                        + t * .01
                    )
                );


            const x =
                cx
                + Math.cos(angle)
                * radius;


            const y =
                cy
                + Math.sin(angle)
                * radius
                * .53;


            ctx.fillStyle =
                i % 5 === 0
                ? "#79ffb7"
                : "#72dfff";


            ctx.beginPath();

            ctx.arc(
                x,
                y,
                i % 5 === 0
                    ? 2.5
                    : 1.3,
                0,
                Math.PI * 2
            );

            ctx.fill();
        }


        t++;

        requestAnimationFrame(
            render
        );
    }


    render();
}


document
    .querySelectorAll(
        ".window"
    )
    .forEach(
        win => {

            makeDraggable(
                win
            );


            const close =
                win.querySelector(
                    "[data-close]"
                );


            if (close) {

                close.addEventListener(
                    "click",
                    () =>
                        closeWindow(
                            win.dataset.window
                        )
                );
            }


            const minimize =
                win.querySelector(
                    "[data-minimize]"
                );


            if (minimize) {

                minimize.addEventListener(
                    "click",
                    () => {

                        win.classList.toggle(
                            "minimized"
                        );

                        saveLayout();
                    }
                );
            }


            const maximize =
                win.querySelector(
                    "[data-maximize]"
                );


            if (maximize) {

                maximize.addEventListener(
                    "click",
                    () => {

                        win.classList.toggle(
                            "maximized"
                        );

                        bringFront(win);
                    }
                );
            }
        }
    );


document
    .querySelectorAll(
        "[data-open]"
    )
    .forEach(
        button => {

            button.addEventListener(
                "click",
                () =>
                    showWindow(
                        button.dataset.open
                    )
            );
        }
    );


document
    .querySelectorAll(
        "[data-layout]"
    )
    .forEach(
        button => {

            button.addEventListener(
                "click",
                () =>
                    applyLayout(
                        button.dataset.layout
                    )
            );
        }
    );


document
    .querySelectorAll(
        ".commandAction"
    )
    .forEach(
        button => {

            button.addEventListener(
                "click",
                () =>
                    executeCommand(
                        button.dataset.command
                    )
            );
        }
    );


document.getElementById(
    "executeButton"
).addEventListener(
    "click",
    () => executeCommand()
);


document.getElementById(
    "commandInput"
).addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter"
        ) {

            executeCommand();
        }
    }
);


document.getElementById(
    "listenButton"
).addEventListener(
    "click",
    () => {

        if (recognition) {

            recognition.start();
        }
    }
);


document.getElementById(
    "stopVoiceButton"
).addEventListener(
    "click",
    () => {

        if (recognition) {

            try {
                recognition.stop();
            } catch (_) {}
        }


        speechSynthesis.cancel();
    }
);


document.getElementById(
    "legacyRefresh"
).addEventListener(
    "click",
    () => {

        document.getElementById(
            "legacyFrame"
        ).src =
            window.LEGACY_URL
            + "?t="
            + Date.now();


        refreshStatus();
    }
);


restoreLayout();

setupVoice();

drawOrb();

refreshStatus();

refreshEvidence();

refreshMarket();


setInterval(
    refreshStatus,
    5000
);

setInterval(
    refreshEvidence,
    6000
);

setInterval(
    refreshMarket,
    10000
);
'''
)


# ============================================================
# V3 STARTER
# ============================================================

write(
    STARTER,
    r'''
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import webbrowser

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parent

PYTHON = (
    ROOT
    / ".venv"
    / "Scripts"
    / "python.exe"
)

LEGACY_APP = (
    ROOT
    / "workstation"
    / "app.py"
)

LOG_DIR = (
    ROOT
    / "logs"
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def port_open(
    port,
):

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    sock.settimeout(
        .3
    )


    try:

        return (
            sock.connect_ex(
                (
                    "127.0.0.1",
                    int(port),
                )
            )
            == 0
        )


    finally:

        sock.close()


def launch_legacy():

    if port_open(
        8787
    ):

        print(
            "Existing JARVIS workspace: ONLINE"
        )

        return None


    if not LEGACY_APP.exists():

        print(
            "Existing workspace app.py: NOT FOUND"
        )

        return None


    stdout = (
        LOG_DIR
        / "legacy_workstation_v3.log"
    ).open(
        "a",
        encoding="utf-8",
    )


    process = subprocess.Popen(
        [
            str(PYTHON),
            str(LEGACY_APP),
        ],
        cwd=ROOT,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        creationflags=
            getattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            ),
    )


    for _ in range(
        20
    ):

        if port_open(
            8787
        ):

            print(
                "Existing JARVIS workspace: STARTED"
            )

            return process


        if process.poll() is not None:

            break


        time.sleep(
            .25
        )


    print(
        "Existing workspace did not bind 8787."
    )

    print(
        "V3 will continue without iframe workspace."
    )


    return process


def main():

    print("=" * 76)
    print("JARVIS OS V3")
    print("=" * 76)


    import main as jarvis_main

    from omni.core_integrity import (
        verify_protected_core,
    )


    core = verify_protected_core()


    if not core.ok:

        raise RuntimeError(
            "Protected Core validation failed."
        )


    trading = (
        jarvis_main
        .jarvis_trading_v8_status()
    )


    if trading[
        "live_execution"
    ] is not False:

        raise RuntimeError(
            "Trading execution safety invariant failed."
        )


    print("Protected Core: PASS")
    print("Master JARVIS: READY")
    print("Live broker execution: LOCKED")


    legacy_process = launch_legacy()


    from workstation.jarvis_os_v3 import (
        HOST,
        PORT,
        create_server,
    )


    server = create_server(
        HOST,
        PORT,
    )


    url = (
        f"http://{HOST}:{PORT}"
    )


    print(
        "JARVIS OS:",
        url,
    )


    def browser():

        time.sleep(
            .8
        )

        webbrowser.open(
            url
        )


    threading.Thread(
        target=browser,
        daemon=True,
    ).start()


    try:

        server.serve_forever()


    except KeyboardInterrupt:

        print()
        print(
            "Stopping JARVIS OS..."
        )


    finally:

        server.server_close()


        if (
            legacy_process is not None
            and legacy_process.poll()
            is None
        ):

            legacy_process.terminate()


    print(
        "JARVIS OS stopped."
    )


if __name__ == "__main__":

    main()
'''
)


# ============================================================
# FALLBACK LAUNCHER
# ============================================================

write(
    FALLBACK_BAT,
    r'''
@echo off
cd /d C:\Jarvis
title JARVIS V2 FALLBACK

"C:\Jarvis\.venv\Scripts\python.exe" ^
"C:\Jarvis\start_jarvis.py"

pause
'''
)


# ============================================================
# NEW PRIMARY LAUNCHER
# ============================================================

write(
    BAT,
    r'''
@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V3

if not exist "C:\Jarvis\.venv\Scripts\python.exe" (
    echo JARVIS Python environment missing.
    pause
    exit /b 1
)

"C:\Jarvis\.venv\Scripts\python.exe" ^
"C:\Jarvis\start_jarvis_v3.py"

if errorlevel 1 (
    echo.
    echo JARVIS OS V3 exited with an error.
    echo Use JARVIS_V2_FALLBACK.bat if required.
    pause
)

endlocal
'''
)


# ============================================================
# TESTS
# ============================================================

write(
    TEST,
    r'''
import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)


from workstation.jarvis_os_v3 import (
    _safe,
    ui_actions,
    market_snapshot,
)


class JarvisOSV3Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_safe_redaction(
        self,
    ):

        value = _safe(
            {
                "access_token":
                    "secret-value",

                "normal":
                    "visible",
            }
        )


        self.assertEqual(
            value[
                "access_token"
            ],
            "<REDACTED>",
        )


        self.assertEqual(
            value[
                "normal"
            ],
            "visible",
        )


    def test_trading_ui_intent(
        self,
    ):

        actions = ui_actions(
            "Open trading terminal "
            "and run strategy"
        )


        windows = {
            item.get(
                "window"
            )

            for item in actions

            if item.get(
                "type"
            )
            == "open_window"
        }


        self.assertIn(
            "legacy",
            windows,
        )


        self.assertIn(
            "quant",
            windows,
        )


    def test_research_layout_intent(
        self,
    ):

        actions = ui_actions(
            "Open research layout"
        )


        self.assertTrue(
            any(
                item.get(
                    "layout"
                )
                == "research"

                for item in actions
            )
        )


    def test_close_all(
        self,
    ):

        actions = ui_actions(
            "close all windows"
        )


        self.assertTrue(
            any(
                item.get(
                    "type"
                )
                == "close_all"

                for item in actions
            )
        )


    def test_market_snapshot_safe(
        self,
    ):

        result = market_snapshot()


        self.assertIn(
            "trading_status",
            result,
        )


    def test_live_execution_still_blocked(
        self,
    ):

        status = (
            main
            .jarvis_trading_v8_status()
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# COMPILE
# ============================================================

print()
print("=" * 80)
print("JARVIS OS V3 COMPILE")
print("=" * 80)


r = run(
    "-m",
    "py_compile",
    str(SERVER),
    str(STARTER),
    str(TEST),
)


if r.returncode:

    print(
        "V3 COMPILE FAILED"
    )

    rollback()

    sys.exit(1)


print(
    "V3 Python syntax: PASS"
)


# ============================================================
# PROTECTED CORE HASH CHECK
# ============================================================

for relative, expected in (
    PROTECTED.items()
):

    actual = sha(
        ROOT / relative
    )


    if actual != expected:

        print(
            "PROTECTED FILE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


print(
    "Protected Core hashes: PASS"
)


# ============================================================
# TARGETED TEST
# ============================================================

print()
print("=" * 80)
print("JARVIS OS V3 TARGETED TESTS")
print("=" * 80)


r = run(
    "-m",
    "unittest",
    "tests.test_jarvis_os_v3",
    "-q",
    timeout=180,
)


if r.returncode:

    print(
        "V3 TARGETED TEST FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# EXISTING OPERATOR / TRADING REGRESSION
# ============================================================

targets = [
    "tests.test_computer_operator",
    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",
    "tests.test_trading_intelligence_v8",
]


existing = [
    target

    for target in targets

    if (
        ROOT
        / (
            target.replace(
                ".",
                "\\"
            )
            + ".py"
        )
    ).exists()
]


if existing:

    r = run(
        "-m",
        "unittest",
        *existing,
        "-q",
        timeout=360,
    )


    if r.returncode:

        print(
            "EXISTING SUBSYSTEM REGRESSION FAILED"
        )

        rollback()

        sys.exit(1)


# ============================================================
# FULL REGRESSION
# ============================================================

print()
print("=" * 80)
print("FULL JARVIS REGRESSION")
print("=" * 80)


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
    timeout=720,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILED"
    )

    rollback()

    sys.exit(1)


# ============================================================
# FINAL SAFETY
# ============================================================

for relative, expected in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != expected:

        print(
            "FINAL PROTECTED CORE CHANGE:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v8=main.jarvis_trading_v8_status();"
        "assert v8['live_execution'] is False;"
        "assert v8['automatic_broker_order'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Trading V1-V8: PRESERVED');"
        "print('Live broker execution: BLOCKED')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


print()
print("=" * 80)
print("JARVIS OS V3 INSTALLATION SUCCESS")
print("=" * 80)

print()
print("MASTER JARVIS")
print("Persistent master command: ACTIVE")
print("Natural-language command routing: ACTIVE")
print("Voice browser interface: ACTIVE")
print("UI-action interpretation: ACTIVE")
print()

print("VIRTUAL DESKTOP")
print("Dockable windows: ACTIVE")
print("Draggable windows: ACTIVE")
print("Resizable windows: ACTIVE")
print("Minimize / maximize / close: ACTIVE")
print("Z-order management: ACTIVE")
print("Layout persistence: ACTIVE")
print()

print("LAYOUTS")
print("Command layout: ACTIVE")
print("Trading layout: ACTIVE")
print("Research layout: ACTIVE")
print()

print("INTERNAL APPS")
print("JARVIS orchestration core: ACTIVE")
print("Existing 8787 workspace bridge: ACTIVE")
print("Mission / operations center: ACTIVE")
print("Quant / strategy center: ACTIVE")
print("Paper desk controls: ACTIVE")
print("Web intelligence launcher: ACTIVE")
print("System Core: ACTIVE")
print("Evidence / approvals: ACTIVE")
print()

print("VISUAL ENGINE")
print("Animated holographic JARVIS core: ACTIVE")
print("Glass / layered 3D workspace: ACTIVE")
print("Agent/system status polling: ACTIVE")
print("Market snapshot polling: ACTIVE")
print("Evidence polling: ACTIVE")
print()

print("SAFETY")
print("Localhost binding only: YES")
print("Per-session API token: YES")
print("Credentials redacted: YES")
print("Live trading execution: BLOCKED")
print("Broker orders: BLOCKED")
print("Protected Core: UNCHANGED")
print()

print("FALLBACK:")
print(r"C:\Jarvis\JARVIS_V2_FALLBACK.bat")

print()
print("PRIMARY:")
print(r"C:\Jarvis\JARVIS.bat")
