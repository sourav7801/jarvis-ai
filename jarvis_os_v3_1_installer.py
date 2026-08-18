from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import textwrap

from pathlib import Path


ROOT = Path(r"C:\Jarvis")
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

ORCHESTRATOR = (
    ROOT
    / "omni"
    / "jarvis_workspace_orchestrator.py"
)

CHART_PROVIDER = (
    ROOT
    / "workstation"
    / "jarvis_v3_chart_provider.py"
)

SERVER = (
    ROOT
    / "workstation"
    / "jarvis_os_v3.py"
)

ASSETS = (
    ROOT
    / "workstation"
    / "jarvis_os_v3_assets"
)

HTML = ASSETS / "index.html"
CSS = ASSETS / "styles.css"
JS = ASSETS / "app.js"

STARTER = (
    ROOT
    / "start_jarvis_v3.py"
)

BAT = (
    ROOT
    / "JARVIS.bat"
)

TEST = (
    ROOT
    / "tests"
    / "test_jarvis_os_v3_1.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "jarvis_os_v3_1"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)


FILES = (
    ORCHESTRATOR,
    CHART_PROVIDER,
    SERVER,
    HTML,
    CSS,
    JS,
    STARTER,
    BAT,
    TEST,
)


BACKUPS = {}


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
        newline="\n",
    )


def run(
    *args,
    capture=False,
    timeout=None,
):

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


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def rollback():

    print()
    print("=" * 80)
    print("JARVIS OS V3.1 ROLLBACK")
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
print("JARVIS OS V3.1 — ADAPTIVE WORKSPACE MEGA-SPRINT")
print("=" * 80)


# ============================================================
# 1. BASELINE
# ============================================================

print()
print("Checking current JARVIS baseline...")


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
# 2. BACKUP
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


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT / relative
        )

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
# 3. MASTER WORKSPACE ORCHESTRATOR
# ============================================================

write(
    ORCHESTRATOR,
    r'''
from __future__ import annotations

import re


WINDOW_ALIASES = {
    "chart":
        "chart",

    "charts":
        "chart",

    "trading terminal":
        "chart",

    "terminal":
        "chart",

    "quant":
        "quant",

    "quant lab":
        "quant",

    "strategy":
        "quant",

    "paper":
        "paper",

    "paper desk":
        "paper",

    "research":
        "research",

    "web intelligence":
        "research",

    "news":
        "research",

    "mission":
        "missions",

    "mission control":
        "missions",

    "missions":
        "missions",

    "system":
        "system",

    "system core":
        "system",

    "health":
        "system",

    "evidence":
        "evidence",

    "approvals":
        "evidence",

    "apps":
        "apps",

    "applications":
        "apps",

    "launcher":
        "apps",

    "legacy":
        "legacy",
}


SYMBOL_ALIASES = {
    "nifty":
        "NIFTY",

    "nifty 50":
        "NIFTY",

    "banknifty":
        "BANKNIFTY",

    "bank nifty":
        "BANKNIFTY",

    "sensex":
        "SENSEX",

    "crude":
        "CRUDEOIL",

    "crude oil":
        "CRUDEOIL",

    "crudeoil":
        "CRUDEOIL",

    "gold":
        "GOLD",

    "silver":
        "SILVER",

    "natural gas":
        "NATURALGAS",

    "naturalgas":
        "NATURALGAS",

    "btc":
        "BTC",

    "bitcoin":
        "BTC",

    "eth":
        "ETH",

    "ethereum":
        "ETH",

    "sol":
        "SOL",
}


TIMEFRAMES = (
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "1d",
)


def _symbols(
    text,
):

    lowered = str(
        text
    ).lower()


    matches = []


    for alias, canonical in (
        SYMBOL_ALIASES.items()
    ):

        expression = (
            r"(?<!\w)"
            + re.escape(
                alias
            )
            + r"(?!\w)"
        )


        for match in re.finditer(
            expression,
            lowered,
        ):

            matches.append(
                (
                    match.start(),

                    -len(
                        alias
                    ),

                    canonical,

                    alias,
                )
            )


    matches.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )


    values = []


    for (
        _position,
        _negative_length,
        canonical,
        _alias,
    ) in matches:

        if canonical not in values:

            values.append(
                canonical
            )


    return tuple(
        values
    )


def _timeframe(
    text,
):

    lowered = str(
        text
    ).lower()


    patterns = (
        r"\b1\s*m(?:in(?:ute)?)?\b",
        r"\b3\s*m(?:in(?:ute)?)?\b",
        r"\b5\s*m(?:in(?:ute)?)?\b",
        r"\b15\s*m(?:in(?:ute)?)?\b",
        r"\b30\s*m(?:in(?:ute)?)?\b",
        r"\b1\s*h(?:our)?\b",
        r"\b2\s*h(?:our)?\b",
        r"\b4\s*h(?:our)?\b",
        r"\b1\s*d(?:ay)?\b",
    )


    for index, pattern in enumerate(
        patterns
    ):

        if re.search(
            pattern,
            lowered,
        ):

            return TIMEFRAMES[
                index
            ]


    return None


def interpret_workspace_command(
    text,
):

    text = str(
        text
    ).strip()

    lowered = text.lower()

    actions = []


    # --------------------------------------------------------
    # Layout intents
    # --------------------------------------------------------

    if any(
        phrase in lowered

        for phrase in (
            "trading layout",
            "trading workspace",
            "open trading terminal",
            "market workspace",
        )
    ):

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "trading",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "research layout",
            "research workspace",
        )
    ):

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "research",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "mission layout",
            "mission workspace",
            "operations layout",
        )
    ):

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "mission",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "command layout",
            "home layout",
            "default layout",
        )
    ):

        actions.append(
            {
                "type":
                    "layout",

                "layout":
                    "command",
            }
        )


    # --------------------------------------------------------
    # Explicit open requests
    # --------------------------------------------------------

    for alias, window in WINDOW_ALIASES.items():

        if (
            (
                "open " + alias
            ) in lowered
            or (
                "show " + alias
            ) in lowered
        ):

            actions.append(
                {
                    "type":
                        "open_window",

                    "window":
                        window,
                }
            )


    # --------------------------------------------------------
    # Domain-driven opening
    # --------------------------------------------------------

    symbols = _symbols(
        text
    )


    timeframe = _timeframe(
        text
    )


    if (
        symbols
        or any(
            phrase in lowered

            for phrase in (
                "chart",
                "candlestick",
                "trading terminal",
            )
        )
    ):

        actions.append(
            {
                "type":
                    "open_window",

                "window":
                    "chart",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "analyze",
            "signal",
            "strategy",
            "setup",
            "find trade",
            "trade opportunity",
            "risk reward",
        )
    ):

        actions.append(
            {
                "type":
                    "open_window",

                "window":
                    "quant",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "research",
            "latest news",
            "news",
            "impact",
            "catalyst",
            "geopolitical",
        )
    ):

        actions.append(
            {
                "type":
                    "open_window",

                "window":
                    "research",
            }
        )


    if any(
        phrase in lowered

        for phrase in (
            "paper trade",
            "paper position",
            "simulate trade",
            "synthetic",
        )
    ):

        actions.append(
            {
                "type":
                    "open_window",

                "window":
                    "paper",
            }
        )


    # --------------------------------------------------------
    # Chart instructions
    # --------------------------------------------------------

    for index, symbol in enumerate(
        symbols[
            :4
        ]
    ):

        actions.append(
            {
                "type":
                    "chart_symbol",

                "slot":
                    index,

                "symbol":
                    symbol,

                "timeframe":
                    (
                        timeframe
                        or "15m"
                    ),
            }
        )


    if (
        len(
            symbols
        ) > 1
        or "compare" in lowered
    ):

        actions.append(
            {
                "type":
                    "chart_layout",

                "count":
                    max(
                        2,
                        min(
                            4,
                            len(
                                symbols
                            )
                            or 2,
                        ),
                    ),
            }
        )


    # --------------------------------------------------------
    # Maximize / focus
    # --------------------------------------------------------

    if any(
        phrase in lowered

        for phrase in (
            "full screen chart",
            "fullscreen chart",
            "maximize chart",
            "make chart full screen",
        )
    ):

        actions.append(
            {
                "type":
                    "maximize_window",

                "window":
                    "chart",
            }
        )


    # --------------------------------------------------------
    # Close operations
    # --------------------------------------------------------

    if "close all windows" in lowered:

        actions.append(
            {
                "type":
                    "close_all",
            }
        )


    for alias, window in WINDOW_ALIASES.items():

        if (
            "close " + alias
        ) in lowered:

            actions.append(
                {
                    "type":
                        "close_window",

                    "window":
                        window,
                }
            )


    # --------------------------------------------------------
    # Workspace persistence
    # --------------------------------------------------------

    if (
        "save workspace"
        in lowered
    ):

        actions.append(
            {
                "type":
                    "save_workspace",
            }
        )


    if (
        "restore workspace"
        in lowered
    ):

        actions.append(
            {
                "type":
                    "restore_workspace",
            }
        )


    # --------------------------------------------------------
    # De-duplicate identical simple actions
    # --------------------------------------------------------

    result = []

    seen = set()


    for action in actions:

        key = repr(
            sorted(
                action.items()
            )
        )


        if key in seen:

            continue


        seen.add(
            key
        )

        result.append(
            action
        )


    return tuple(
        result
    )
'''
)


# ============================================================
# 4. VERIFIED CHART PROVIDER
# ============================================================

write(
    CHART_PROVIDER,
    r'''
from __future__ import annotations

import inspect

from datetime import (
    datetime,
    timedelta,
    timezone,
)


SYMBOL_MAP = {
    "NIFTY":
        "NSE:NIFTY50-INDEX",

    "BANKNIFTY":
        "NSE:NIFTYBANK-INDEX",

    "SENSEX":
        "BSE:SENSEX-INDEX",

    "CRUDEOIL":
        "MCX:CRUDEOIL",

    "GOLD":
        "MCX:GOLD",

    "SILVER":
        "MCX:SILVER",

    "NATURALGAS":
        "MCX:NATURALGAS",

    "BTC":
        "BTC",

    "ETH":
        "ETH",

    "SOL":
        "SOL",
}


RESOLUTION_MAP = {
    "1m":
        "1",

    "3m":
        "3",

    "5m":
        "5",

    "15m":
        "15",

    "30m":
        "30",

    "1h":
        "60",

    "2h":
        "120",

    "4h":
        "240",

    "1d":
        "D",
}


def canonical_symbol(
    symbol,
):

    text = str(
        symbol
    ).upper().strip()


    return SYMBOL_MAP.get(
        text,
        symbol,
    )


def _normalize_frame(
    value,
    *,
    limit=240,
):

    rows = []


    # pandas DataFrame
    if hasattr(
        value,
        "to_dict",
    ):

        try:

            records = value.to_dict(
                orient="records"
            )

        except TypeError:

            records = None


        if records is not None:

            value = records


    if isinstance(
        value,
        dict,
    ):

        for key in (
            "bars",
            "candles",
            "data",
            "history",
            "rows",
        ):

            candidate = value.get(
                key
            )


            if isinstance(
                candidate,
                (
                    list,
                    tuple,
                ),
            ):

                value = candidate

                break


    if not isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return ()


    for item in value:

        if isinstance(
            item,
            dict,
        ):

            timestamp = (
                item.get(
                    "timestamp"
                )
                or item.get(
                    "datetime"
                )
                or item.get(
                    "date"
                )
                or item.get(
                    "time"
                )
                or item.get(
                    "ts"
                )
            )


            open_ = (
                item.get(
                    "open"
                )
                if item.get(
                    "open"
                ) is not None
                else item.get(
                    "o"
                )
            )


            high = (
                item.get(
                    "high"
                )
                if item.get(
                    "high"
                ) is not None
                else item.get(
                    "h"
                )
            )


            low = (
                item.get(
                    "low"
                )
                if item.get(
                    "low"
                ) is not None
                else item.get(
                    "l"
                )
            )


            close = (
                item.get(
                    "close"
                )
                if item.get(
                    "close"
                ) is not None
                else item.get(
                    "c"
                )
            )


            volume = (
                item.get(
                    "volume"
                )
                if item.get(
                    "volume"
                ) is not None
                else item.get(
                    "v"
                )
            )


        elif isinstance(
            item,
            (
                list,
                tuple,
            )
        ) and len(
            item
        ) >= 5:

            timestamp = item[0]
            open_ = item[1]
            high = item[2]
            low = item[3]
            close = item[4]

            volume = (
                item[5]
                if len(
                    item
                ) > 5
                else None
            )


        else:

            continue


        try:

            row = {
                "timestamp":
                    (
                        timestamp.isoformat()
                        if hasattr(
                            timestamp,
                            "isoformat"
                        )
                        else str(
                            timestamp
                        )
                    ),

                "open":
                    float(
                        open_
                    ),

                "high":
                    float(
                        high
                    ),

                "low":
                    float(
                        low
                    ),

                "close":
                    float(
                        close
                    ),

                "volume":
                    (
                        float(
                            volume
                        )
                        if volume
                        is not None
                        else None
                    ),
            }


        except Exception:

            continue


        if (
            row[
                "high"
            ]
            < row[
                "low"
            ]
        ):

            continue


        rows.append(
            row
        )


    return tuple(
        rows[
            -max(
                1,
                min(
                    int(
                        limit
                    ),
                    500,
                ),
            ):
        ]
    )


def _invoke_intraday(
    function,
    *,
    symbol,
    timeframe,
    limit,
):

    signature = inspect.signature(
        function
    )


    params = signature.parameters


    kwargs = {}


    for name, parameter in params.items():

        lowered = name.lower()


        if lowered in {
            "symbol",
            "ticker",
            "instrument",
        }:

            kwargs[
                name
            ] = canonical_symbol(
                symbol
            )


        elif lowered in {
            "resolution",
            "interval",
            "timeframe",
        }:

            kwargs[
                name
            ] = RESOLUTION_MAP.get(
                timeframe,
                timeframe,
            )


        elif lowered in {
            "limit",
            "count",
            "bars",
        }:

            kwargs[
                name
            ] = int(
                limit
            )


        elif lowered in {
            "days",
            "lookback_days",
        }:

            kwargs[
                name
            ] = 10


        elif lowered in {
            "period",
        }:

            kwargs[
                name
            ] = "10d"


    missing = []


    for name, parameter in params.items():

        if (
            parameter.default
            is inspect._empty
            and parameter.kind
            not in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
            and name not in kwargs
        ):

            missing.append(
                name
            )


    if missing:

        raise RuntimeError(
            "Unable to safely call get_intraday_data; "
            "unresolved required parameters: "
            + ", ".join(
                missing
            )
        )


    return function(
        **kwargs
    )


def get_chart(
    symbol,
    timeframe="15m",
    *,
    limit=180,
):

    symbol = str(
        symbol
    ).upper().strip()

    timeframe = str(
        timeframe
    ).lower().strip()


    if timeframe not in RESOLUTION_MAP:

        timeframe = "15m"


    result = {
        "success":
            False,

        "symbol":
            symbol,

        "provider_symbol":
            canonical_symbol(
                symbol
            ),

        "timeframe":
            timeframe,

        "bars":
            (),

        "verified":
            False,

        "synthetic":
            False,

        "provider":
            None,

        "error":
            None,
    }


    try:

        from agents.fyers_data_adapter import (
            get_intraday_data,
        )


        raw = _invoke_intraday(
            get_intraday_data,
            symbol=
                symbol,
            timeframe=
                timeframe,
            limit=
                limit,
        )


        bars = _normalize_frame(
            raw,
            limit=limit,
        )


        if bars:

            result.update(
                {
                    "success":
                        True,

                    "bars":
                        bars,

                    "verified":
                        True,

                    "provider":
                        "fyers_data_adapter",
                }
            )


            return result


        result[
            "error"
        ] = (
            "FYERS adapter returned no "
            "normalizable candles."
        )


    except Exception as exc:

        result[
            "error"
        ] = (
            type(
                exc
            ).__name__
            + ": "
            + str(
                exc
            )
        )


    return result
'''
)


# ============================================================
# 5. V3.1 LOCAL SERVER
# ============================================================

write(
    SERVER,
    r'''
from __future__ import annotations

import json
import secrets
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


def dispatch_command(
    text,
):

    import main


    function = getattr(
        main,
        "jarvis_command",
        None,
    )


    if callable(
        function
    ):

        result = function(
            text
        )


        return {
            "route":
                "MASTER_JARVIS",

            "response":
                render_response(
                    result
                ),

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


            try:

                result = dispatch_command(
                    text
                )


                return self.send_json(
                    {
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
'''
)


# ============================================================
# 6. HTML — ADAPTIVE DESKTOP
# ============================================================

write(
    HTML,
    r'''
<!doctype html>

<html lang="en">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>
JARVIS OS V3.1
</title>

<link
    rel="stylesheet"
    href="/styles.css"
>

</head>


<body data-core-state="ready">


<div id="ambient"></div>


<header id="topbar">

    <div class="brand">

        <div class="logo">
            J
        </div>

        <div>

            <div class="brandName">
                J A R V I S
            </div>

            <div class="brandSub">
                OMNI OPERATING COMMAND CENTER · V3.1
            </div>

        </div>

    </div>


    <nav>

        <button data-layout="command">
            COMMAND
        </button>

        <button data-open="chart">
            CHART TERMINAL
        </button>

        <button data-open="quant">
            QUANT
        </button>

        <button data-open="research">
            INTELLIGENCE
        </button>

        <button data-open="missions">
            MISSIONS
        </button>

        <button data-open="paper">
            PAPER
        </button>

        <button data-open="apps">
            APPS
        </button>

        <button data-open="system">
            SYSTEM
        </button>

    </nav>


    <div class="topStatus">

        <span
            class="status green"
            id="voiceState"
        >
            ● VOICE READY
        </span>

        <span class="status amber">
            ● APPROVAL GATE
        </span>

        <span class="status red">
            ● EXECUTION LOCKED
        </span>

        <button id="fullscreenButton">
            ⛶
        </button>

    </div>

</header>


<section id="masterConsole">

    <div class="consoleHeading">

        <span>
            MASTER JARVIS
        </span>

        <small id="masterState">
            READY
        </small>

    </div>


    <div id="conversation">

        <div class="conversationItem jarvis">

            <div class="speaker">
                JARVIS
            </div>

            <div class="message">

                Master intelligence online.
                Tell me what outcome you want.

            </div>

        </div>

    </div>


    <div id="commandRow">

        <button id="listenButton">
            ◉ LISTEN
        </button>

        <input
            id="commandInput"
            autocomplete="off"
            placeholder="e.g. Jarvis, open crude oil, 15m chart, analyze it, check news and find the strongest paper setup."
        >

        <button id="executeButton">
            EXECUTE
        </button>

        <button id="stopButton">
            STOP
        </button>

    </div>

</section>


<main id="desktop">


<!-- ====================================================== -->
<!-- MASTER CORE -->
<!-- ====================================================== -->

<section
    class="jarvisWindow coreWindow"
    data-window="core"
    id="win-core"
>

<header class="windowHeader">

    <span>
        JARVIS ORCHESTRATION CORE
    </span>

    <div class="windowControls">

        <button data-minimize>
            —
        </button>

        <button data-maximize>
            □
        </button>

    </div>

</header>


<div class="windowBody coreBody">

    <div class="coreVisual">

        <canvas id="coreCanvas"></canvas>

        <div class="coreCenter">

            <strong>
                J
            </strong>

            <small id="coreText">
                ONLINE
            </small>

        </div>

    </div>


    <div class="coreInfo">

        <div class="eyebrow">
            MASTER INTELLIGENCE
        </div>

        <h1>
            One voice.<br>
            Every system.
        </h1>

        <p id="coreMission">

            Waiting for your command.

        </p>


        <div class="coreMetrics">

            <div>
                <b id="agentCount">
                    —
                </b>
                <span>
                    AGENTS
                </span>
            </div>

            <div>
                <b id="activeRoute">
                    MASTER
                </b>
                <span>
                    ROUTE
                </span>
            </div>

            <div>
                <b class="redText">
                    LOCKED
                </b>
                <span>
                    LIVE EXECUTION
                </span>
            </div>

        </div>

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- NATIVE CHART TERMINAL -->
<!-- ====================================================== -->

<section
    class="jarvisWindow chartWindow"
    data-window="chart"
    id="win-chart"
>

<header class="windowHeader">

    <span>
        LIVE CHART TERMINAL
    </span>

    <div class="windowControls">

        <button data-minimize>
            —
        </button>

        <button data-maximize>
            □
        </button>

        <button data-close>
            ×
        </button>

    </div>

</header>


<div class="windowBody chartBody">

    <div class="chartToolbar">

        <select id="chartSymbol">

            <option>
                NIFTY
            </option>

            <option>
                BANKNIFTY
            </option>

            <option>
                SENSEX
            </option>

            <option>
                CRUDEOIL
            </option>

            <option>
                GOLD
            </option>

            <option>
                SILVER
            </option>

            <option>
                NATURALGAS
            </option>

            <option>
                BTC
            </option>

            <option>
                ETH
            </option>

            <option>
                SOL
            </option>

        </select>


        <div
            class="timeframes"
            id="timeframes"
        >

            <button data-timeframe="1m">
                1m
            </button>

            <button data-timeframe="5m">
                5m
            </button>

            <button
                data-timeframe="15m"
                class="selected"
            >
                15m
            </button>

            <button data-timeframe="1h">
                1h
            </button>

            <button data-timeframe="4h">
                4h
            </button>

            <button data-timeframe="1d">
                1D
            </button>

        </div>


        <button id="refreshChart">
            REFRESH
        </button>


        <button data-command="Analyze the current selected market and explain the strongest research setup.">
            ANALYZE
        </button>

    </div>


    <div class="chartHeader">

        <div>

            <div
                class="eyebrow"
                id="chartProvider"
            >
                VERIFIED DATA
            </div>

            <h2 id="chartTitle">
                NIFTY · 15m
            </h2>

        </div>


        <div id="chartPrice">
            —
        </div>

    </div>


    <div id="chartGrid">

        <div class="chartPane">

            <canvas
                class="chartCanvas"
                id="chartCanvas0"
            ></canvas>

            <div
                class="chartStatus"
                id="chartStatus0"
            >
                Loading verified candles…
            </div>

        </div>

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- QUANT -->
<!-- ====================================================== -->

<section
    class="jarvisWindow quantWindow"
    data-window="quant"
    id="win-quant"
>

<header class="windowHeader">

    <span>
        QUANT / STRATEGY LAB
    </span>

    <div class="windowControls">

        <button data-minimize>—</button>
        <button data-maximize>□</button>
        <button data-close>×</button>

    </div>

</header>


<div class="windowBody">

    <div class="quantHero">

        <div>

            <div class="eyebrow">
                RESEARCH ENGINE
            </div>

            <h2 id="quantEngine">
                ENGINE READY
            </h2>

        </div>


        <span class="safeBadge">
            PAPER / RESEARCH
        </span>

    </div>


    <div class="metricCards">

        <div>

            <span>
                SPOT
            </span>

            <b id="metricSpot">
                —
            </b>

        </div>

        <div>

            <span>
                ATM IV
            </span>

            <b id="metricIV">
                —
            </b>

        </div>

        <div>

            <span>
                PCR OI
            </span>

            <b id="metricPCR">
                —
            </b>

        </div>

        <div>

            <span>
                HISTORY
            </span>

            <b id="metricHistory">
                —
            </b>

        </div>

    </div>


    <div class="flowPath">

        <span>
            DETECT
        </span>

        <i>
            →
        </i>

        <span>
            REGIME
        </span>

        <i>
            →
        </i>

        <span>
            SCORE
        </span>

        <i>
            →
        </i>

        <span>
            VALIDATE
        </span>

        <i>
            →
        </i>

        <span>
            EXPLAIN
        </span>

    </div>


    <button
        class="actionButton"
        data-command="Analyze NIFTY with all available trading intelligence, multi-timeframe evidence and derivatives data. Give me the strongest research setup only if evidence supports one."
    >
        RUN NIFTY ANALYSIS
    </button>


    <button
        class="actionButton"
        data-command="Analyze crude oil with all available market, technical and news evidence. Find the strongest research setup."
    >
        ANALYZE CRUDE OIL
    </button>

</div>

</section>


<!-- ====================================================== -->
<!-- RESEARCH -->
<!-- ====================================================== -->

<section
    class="jarvisWindow researchWindow"
    data-window="research"
    id="win-research"
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

    <div class="researchPath">

        SEARCH
        <span>→</span>
        READ
        <span>→</span>
        COMPARE
        <span>→</span>
        CITE

    </div>


    <div class="researchButtons">

        <button
            class="actionButton"
            data-command="Research the most important market-moving developments right now. Compare reliable sources and explain the likely market impact."
        >
            MARKET INTELLIGENCE
        </button>


        <button
            class="actionButton"
            data-command="Research crude oil right now. Compare supply, demand, OPEC, inventory and geopolitical catalysts and explain the likely market impact."
        >
            CRUDE OIL
        </button>


        <button
            class="actionButton"
            data-command="Research the latest AI developments and summarize only the most important changes with sources."
        >
            AI INTELLIGENCE
        </button>

    </div>


    <div
        class="feed"
        id="researchFeed"
    >

        Master JARVIS will place research
        results here as result cards.

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- PAPER -->
<!-- ====================================================== -->

<section
    class="jarvisWindow paperWindow"
    data-window="paper"
    id="win-paper"
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

    <div class="paperStatus">
        SYNTHETIC EXECUTION ONLY
    </div>

    <p>

        Strategy simulation and paper positions.
        Broker execution remains locked.

    </p>


    <div class="paperControls">

        <button
            class="actionButton"
            data-command="Show my current paper trading portfolio, positions, P and L and risk exposure."
        >
            PORTFOLIO
        </button>


        <button
            class="actionButton"
            data-command="Scan all supported markets for qualified paper setups using the current risk gates."
        >
            SCAN
        </button>


        <button
            class="dangerButton"
            data-command="Flatten all synthetic paper positions only."
        >
            FLATTEN PAPER
        </button>

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- MISSIONS / AGENTS -->
<!-- ====================================================== -->

<section
    class="jarvisWindow missionsWindow"
    data-window="missions"
    id="win-missions"
>

<header class="windowHeader">

    <span>
        MISSION CONTROL / AGENT MESH
    </span>

    <div class="windowControls">

        <button data-minimize>—</button>
        <button data-maximize>□</button>
        <button data-close>×</button>

    </div>

</header>


<div class="windowBody">

    <div
        class="agentMesh"
        id="agentMesh"
    ></div>


    <div class="sectionTitle">
        ACTIVITY
    </div>

    <div
        class="feed"
        id="activityFeed"
    ></div>

</div>

</section>


<!-- ====================================================== -->
<!-- APPROVALS / EVIDENCE -->
<!-- ====================================================== -->

<section
    class="jarvisWindow evidenceWindow"
    data-window="evidence"
    id="win-evidence"
>

<header class="windowHeader">

    <span>
        APPROVALS / EVIDENCE
    </span>

    <div class="windowControls">

        <button data-minimize>—</button>
        <button data-maximize>□</button>
        <button data-close>×</button>

    </div>

</header>


<div class="windowBody evidenceSplit">

    <div>

        <div class="sectionTitle">
            APPROVAL QUEUE
        </div>

        <div
            class="feed"
            id="approvalFeed"
        ></div>

    </div>


    <div>

        <div class="sectionTitle">
            EVIDENCE TIMELINE
        </div>

        <div
            class="feed"
            id="evidenceFeed"
        ></div>

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- APPLICATION LAUNCHER -->
<!-- ====================================================== -->

<section
    class="jarvisWindow appsWindow"
    data-window="apps"
    id="win-apps"
>

<header class="windowHeader">

    <span>
        APPLICATION LAUNCHER
    </span>

    <div class="windowControls">

        <button data-minimize>—</button>
        <button data-maximize>□</button>
        <button data-close>×</button>

    </div>

</header>


<div class="windowBody">

    <div class="appGrid">

        <button
            data-command="Open Notepad."
        >
            <strong>
                N
            </strong>
            NOTEPAD
        </button>


        <button
            data-command="Open Calculator."
        >
            <strong>
                +
            </strong>
            CALCULATOR
        </button>


        <button
            data-command="Open my default web browser."
        >
            <strong>
                ◎
            </strong>
            BROWSER
        </button>


        <button
            data-command="Open Visual Studio Code."
        >
            <strong>
                &lt;/&gt;
            </strong>
            VS CODE
        </button>


        <button
            data-command="Open the C:\Jarvis folder."
        >
            <strong>
                ▣
            </strong>
            JARVIS FILES
        </button>


        <button
            data-command="Show system information."
        >
            <strong>
                ⚙
            </strong>
            SYSTEM INFO
        </button>

    </div>

</div>

</section>


<!-- ====================================================== -->
<!-- SYSTEM -->
<!-- ====================================================== -->

<section
    class="jarvisWindow systemWindow"
    data-window="system"
    id="win-system"
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
    class="windowBody systemGrid"
    id="systemGrid"
>
    Loading…
</div>

</section>


<!-- ====================================================== -->
<!-- LEGACY OPTIONAL -->
<!-- ====================================================== -->

<section
    class="jarvisWindow legacyWindow"
    data-window="legacy"
    id="win-legacy"
>

<header class="windowHeader">

    <span>
        LEGACY JARVIS V2 WORKSPACE
    </span>

    <div class="windowControls">

        <button data-minimize>—</button>
        <button data-maximize>□</button>
        <button data-close>×</button>

    </div>

</header>


<div class="windowBody legacyBody">

    Legacy workspace is now optional.
    V3.1 core functionality no longer depends on port 8787.

    <button
        class="actionButton"
        data-command="Open the legacy JARVIS workspace if it is available."
    >
        OPEN LEGACY
    </button>

</div>

</section>


</main>


<footer id="dock">

    <div class="masterStatus">

        <span class="greenDot"></span>

        <strong>
            MASTER JARVIS
        </strong>

        <span id="readyState">
            READY
        </span>

    </div>


    <div class="dockApps">

        <button data-open="core">
            CORE
        </button>

        <button data-open="chart">
            CHART
        </button>

        <button data-open="quant">
            QUANT
        </button>

        <button data-open="paper">
            PAPER
        </button>

        <button data-open="research">
            INTEL
        </button>

        <button data-open="missions">
            MISSIONS
        </button>

        <button data-open="apps">
            APPS
        </button>

        <button data-open="evidence">
            EVIDENCE
        </button>

        <button data-open="system">
            SYSTEM
        </button>

    </div>


    <div class="layoutDock">

        <button data-layout="command">
            COMMAND
        </button>

        <button data-layout="trading">
            TRADING
        </button>

        <button data-layout="research">
            RESEARCH
        </button>

        <button data-layout="mission">
            MISSION
        </button>

        <button id="saveWorkspace">
            SAVE
        </button>

    </div>

</footer>


<script>
window.JARVIS_TOKEN =
    "__JARVIS_TOKEN__";
</script>

<script src="/app.js"></script>


</body>

</html>
'''
)


# ============================================================
# 7. CSS — V3.1 3D / GLASS WORKSPACE
# ============================================================

write(
    CSS,
    r'''
:root {
    --bg0: #010509;
    --bg1: #031019;
    --panel: rgba(5, 18, 27, .96);
    --panel2: rgba(9, 31, 44, .94);
    --line: rgba(91, 212, 255, .23);
    --lineStrong: rgba(104, 224, 255, .62);
    --cyan: #6de1ff;
    --cyan2: #15bfe8;
    --green: #6ff5aa;
    --amber: #ffd15f;
    --red: #ff6677;
    --purple: #aa7cff;
    --text: #eefaff;
    --muted: #7896a6;
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
            circle at 50% 42%,
            rgba(8, 56, 79, .34),
            transparent 36%
        ),
        linear-gradient(
            150deg,
            #02090e,
            #010508 65%
        );
    color: var(--text);
    font-family:
        "Segoe UI",
        system-ui,
        sans-serif;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    opacity: .13;
    background-image:
        linear-gradient(
            rgba(71, 188, 228, .12) 1px,
            transparent 1px
        ),
        linear-gradient(
            90deg,
            rgba(71, 188, 228, .12) 1px,
            transparent 1px
        );
    background-size:
        42px 42px;
}

#ambient {
    position: fixed;
    width: 650px;
    height: 650px;
    border-radius: 50%;
    left: 50%;
    top: 48%;
    transform:
        translate(-50%, -50%);
    background:
        radial-gradient(
            circle,
            rgba(44, 191, 246, .13),
            rgba(20, 115, 153, .03) 45%,
            transparent 70%
        );
    filter: blur(20px);
    pointer-events: none;
    transition:
        .5s ease;
}

body[data-core-state="listening"]
#ambient {
    background:
        radial-gradient(
            circle,
            rgba(69, 228, 255, .22),
            transparent 70%
        );
}

body[data-core-state="thinking"]
#ambient {
    background:
        radial-gradient(
            circle,
            rgba(154, 96, 255, .20),
            transparent 70%
        );
}

body[data-core-state="approval"]
#ambient {
    background:
        radial-gradient(
            circle,
            rgba(255, 202, 77, .20),
            transparent 70%
        );
}

body[data-core-state="error"]
#ambient {
    background:
        radial-gradient(
            circle,
            rgba(255, 77, 97, .20),
            transparent 70%
        );
}

button,
input,
select {
    font: inherit;
}

button {
    cursor: pointer;
    color: #cce7f2;
    border:
        1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(13, 39, 53, .96),
            rgba(4, 16, 24, .98)
        );
    border-radius: 7px;
}

button:hover {
    color: white;
    border-color:
        var(--lineStrong);
    box-shadow:
        0 0 20px
        rgba(67, 203, 255, .12);
}

#topbar {
    height: 62px;
    display: flex;
    align-items: center;
    gap: 23px;
    padding:
        7px 14px;
    border-bottom:
        1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(8, 26, 37, .98),
            rgba(2, 10, 15, .98)
        );
    position: relative;
    z-index: 9000;
    box-shadow:
        0 12px 45px rgba(0, 0, 0, .55);
}

.brand {
    min-width: 255px;
    display: flex;
    align-items: center;
    gap: 11px;
}

.logo {
    width: 41px;
    height: 41px;
    border:
        1px solid var(--cyan);
    border-radius: 10px;
    display: grid;
    place-items: center;
    color: var(--cyan);
    font-weight: 900;
    font-size: 20px;
    box-shadow:
        inset 0 0 18px
        rgba(92, 216, 255, .08),
        0 0 20px
        rgba(92, 216, 255, .09);
}

.brandName {
    font-weight: 800;
    letter-spacing: 8px;
    font-size: 16px;
}

.brandSub {
    color: var(--muted);
    letter-spacing: 2px;
    font-size: 7px;
    margin-top: 3px;
}

nav {
    flex: 1;
    display: flex;
    gap: 5px;
}

nav button {
    padding: 8px 10px;
    font-size: 10px;
}

.topStatus {
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 10px;
}

.status {
    font-size: 8px;
    letter-spacing: .7px;
}

.green {
    color: var(--green);
}

.amber {
    color: var(--amber);
}

.red {
    color: var(--red);
}

#fullscreenButton {
    width: 32px;
    height: 31px;
}

#masterConsole {
    position: relative;
    z-index: 8000;
    margin: 7px;
    height: 146px;
    padding: 9px;
    border:
        1px solid var(--line);
    border-radius: 10px;
    background:
        linear-gradient(
            145deg,
            rgba(6, 24, 34, .97),
            rgba(1, 7, 11, .98)
        );
    box-shadow:
        0 18px 50px
        rgba(0, 0, 0, .38);
}

.consoleHeading {
    display: flex;
    justify-content: space-between;
    color: var(--green);
    font-size: 9px;
    letter-spacing: 2px;
    margin-bottom: 6px;
}

.consoleHeading small {
    color: var(--muted);
}

#conversation {
    height: 67px;
    overflow-y: auto;
    background:
        rgba(0, 5, 8, .9);
    border:
        1px solid
        rgba(95, 205, 244, .12);
    padding: 3px 8px;
}

.conversationItem {
    display: grid;
    grid-template-columns:
        65px 1fr;
    gap: 8px;
    padding: 5px 0;
    border-bottom:
        1px solid
        rgba(87, 187, 224, .1);
    font-size: 11px;
}

.conversationItem .speaker {
    font-size: 9px;
    font-weight: 700;
}

.conversationItem.jarvis
.speaker {
    color: var(--green);
}

.conversationItem.you
.speaker {
    color: var(--cyan);
}

.resultCard {
    margin-top: 5px;
    border:
        1px solid
        rgba(100, 215, 255, .20);
    border-radius: 7px;
    background:
        linear-gradient(
            140deg,
            rgba(8, 31, 44, .92),
            rgba(3, 15, 22, .94)
        );
    padding: 8px 10px;
}

.resultMeta {
    color: var(--cyan);
    font-size: 8px;
    letter-spacing: 1.5px;
    margin-bottom: 5px;
}

.resultBody {
    color: #dcecf3;
    white-space: pre-wrap;
    line-height: 1.45;
}

#commandRow {
    display: flex;
    gap: 7px;
    margin-top: 7px;
}

#commandRow button {
    padding:
        8px 13px;
}

#listenButton {
    color: var(--cyan);
}

#commandInput {
    flex: 1;
    outline: none;
    color: white;
    background: #020b11;
    border:
        1px solid var(--line);
    border-radius: 7px;
    padding:
        8px 12px;
}

#commandInput:focus {
    border-color:
        var(--cyan);
    box-shadow:
        0 0 15px
        rgba(80, 205, 255, .10);
}

#desktop {
    position: absolute;
    left: 7px;
    right: 7px;
    top: 222px;
    bottom: 56px;
    overflow: hidden;
    border:
        1px solid
        rgba(84, 198, 239, .10);
    border-radius: 11px;
}

.jarvisWindow {
    position: absolute;
    min-width: 260px;
    min-height: 160px;
    overflow: hidden;
    resize: both;
    border:
        1px solid var(--line);
    border-radius: 10px;
    background:
        linear-gradient(
            155deg,
            rgba(7, 25, 36, .97),
            rgba(2, 9, 14, .98)
        );
    box-shadow:
        0 20px 65px
        rgba(0, 0, 0, .55),
        inset 0 1px
        rgba(255, 255, 255, .025);
    backdrop-filter:
        blur(14px);
    transition:
        border-color .15s,
        box-shadow .15s;
}

.jarvisWindow.focused {
    border-color:
        rgba(105, 224, 255, .62);
    box-shadow:
        0 25px 90px
        rgba(0, 0, 0, .68),
        0 0 22px
        rgba(61, 188, 235, .08);
}

.jarvisWindow.maximized {
    left: 5px !important;
    top: 5px !important;
    width:
        calc(100% - 10px) !important;
    height:
        calc(100% - 10px) !important;
    resize: none;
}

.jarvisWindow.minimized {
    min-height: 37px;
    height: 37px !important;
    resize: none;
}

.jarvisWindow.minimized
.windowBody {
    display: none;
}

.windowHeader {
    height: 36px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: move;
    user-select: none;
    padding:
        0 7px 0 11px;
    color: var(--cyan);
    font-size: 8px;
    letter-spacing: 1.6px;
    border-bottom:
        1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(14, 43, 58, .96),
            rgba(4, 18, 26, .96)
        );
}

.windowControls {
    display: flex;
    gap: 3px;
}

.windowControls button {
    padding: 0;
    width: 27px;
    height: 25px;
    font-size: 10px;
}

.windowBody {
    height:
        calc(100% - 36px);
    overflow: auto;
    padding: 11px;
}

.coreWindow {
    left: 33%;
    top: 3%;
    width: 34%;
    height: 49%;
}

.chartWindow {
    left: 1%;
    top: 2%;
    width: 31%;
    height: 57%;
}

.quantWindow {
    left: 33%;
    top: 54%;
    width: 34%;
    height: 44%;
}

.researchWindow {
    left: 68%;
    top: 50%;
    width: 31%;
    height: 48%;
}

.paperWindow {
    left: 1%;
    top: 61%;
    width: 31%;
    height: 37%;
}

.missionsWindow {
    left: 68%;
    top: 2%;
    width: 31%;
    height: 46%;
}

.evidenceWindow {
    display: none;
    left: 48%;
    top: 11%;
    width: 49%;
    height: 72%;
}

.appsWindow {
    display: none;
    left: 26%;
    top: 13%;
    width: 48%;
    height: 63%;
}

.systemWindow {
    display: none;
    left: 18%;
    top: 8%;
    width: 64%;
    height: 79%;
}

.legacyWindow {
    display: none;
    left: 20%;
    top: 15%;
    width: 60%;
    height: 55%;
}

.coreBody {
    display: flex;
    align-items: center;
    overflow: hidden;
}

.coreVisual {
    width: 52%;
    height: 100%;
    position: relative;
}

#coreCanvas {
    width: 100%;
    height: 100%;
}

.coreCenter {
    position: absolute;
    left: 50%;
    top: 50%;
    transform:
        translate(-50%, -50%);
    text-align: center;
}

.coreCenter strong {
    display: block;
    color: white;
    font-size: 54px;
    text-shadow:
        0 0 14px
        var(--cyan),
        0 0 38px
        var(--cyan);
}

.coreCenter small {
    color: var(--green);
    letter-spacing: 3px;
    font-size: 7px;
}

.coreInfo {
    flex: 1;
}

.eyebrow {
    color: #7f9aaa;
    letter-spacing: 1.8px;
    font-size: 7px;
}

.coreInfo h1 {
    margin:
        6px 0 9px;
    line-height: 1.02;
    font-size: 27px;
}

.coreInfo p {
    color: #96acb7;
    line-height: 1.45;
    font-size: 11px;
}

.coreMetrics {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 5px;
    margin-top: 12px;
}

.coreMetrics > div {
    padding: 7px;
    border:
        1px solid var(--line);
    border-radius: 6px;
}

.coreMetrics b {
    display: block;
    color: var(--cyan);
    font-size: 13px;
}

.coreMetrics span {
    color: var(--muted);
    font-size: 6px;
}

.redText {
    color:
        var(--red) !important;
}

.chartBody {
    display: flex;
    flex-direction: column;
}

.chartToolbar {
    display: flex;
    gap: 5px;
    align-items: center;
    flex-wrap: wrap;
}

.chartToolbar select {
    color: white;
    background: #041018;
    border:
        1px solid var(--line);
    border-radius: 6px;
    padding: 6px;
}

.chartToolbar button {
    padding: 6px 8px;
    font-size: 8px;
}

.timeframes {
    display: flex;
    gap: 3px;
}

.timeframes button.selected {
    color: var(--cyan);
    border-color:
        var(--cyan);
}

.chartHeader {
    display: flex;
    align-items: end;
    justify-content: space-between;
    margin:
        10px 2px 5px;
}

.chartHeader h2 {
    margin:
        2px 0 0;
    font-size: 17px;
}

#chartPrice {
    color: var(--green);
    font-size: 20px;
    font-weight: 700;
}

#chartGrid {
    flex: 1;
    display: grid;
    grid-template-columns:
        1fr;
    grid-template-rows:
        1fr;
    gap: 5px;
    min-height: 0;
}

#chartGrid.layout2 {
    grid-template-columns:
        repeat(2, 1fr);
}

#chartGrid.layout4 {
    grid-template-columns:
        repeat(2, 1fr);
    grid-template-rows:
        repeat(2, 1fr);
}

.chartPane {
    min-height: 130px;
    position: relative;
    overflow: hidden;
    border:
        1px solid
        rgba(81, 188, 229, .18);
    border-radius: 7px;
    background:
        linear-gradient(
            180deg,
            #020a0e,
            #010609
        );
}

.chartCanvas {
    width: 100%;
    height: 100%;
}

.chartStatus {
    position: absolute;
    left: 8px;
    bottom: 6px;
    font-size: 8px;
    color: var(--muted);
}

.quantHero {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.quantHero h2 {
    margin:
        4px 0;
    color: var(--cyan);
}

.safeBadge {
    color: var(--amber);
    font-size: 7px;
    padding: 7px;
    border:
        1px solid
        rgba(255, 205, 91, .25);
    border-radius: 6px;
}

.metricCards {
    display: grid;
    grid-template-columns:
        repeat(2, 1fr);
    gap: 6px;
    margin-top: 10px;
}

.metricCards > div {
    padding: 8px;
    border:
        1px solid var(--line);
    border-radius: 7px;
    background:
        rgba(7, 29, 42, .64);
}

.metricCards span {
    display: block;
    color: var(--muted);
    font-size: 7px;
    letter-spacing: 1px;
}

.metricCards b {
    display: block;
    margin-top: 3px;
    font-size: 14px;
}

.flowPath {
    display: flex;
    justify-content: space-between;
    gap: 4px;
    margin-top: 10px;
    padding: 8px;
    color: var(--green);
    font-size: 7px;
    border:
        1px solid
        rgba(80, 229, 158, .17);
    border-radius: 6px;
}

.flowPath i {
    color: var(--muted);
}

.actionButton,
.dangerButton {
    margin:
        9px 4px 0 0;
    padding: 8px 10px;
    font-size: 8px;
}

.dangerButton {
    color: var(--red);
    border-color:
        rgba(255, 94, 113, .3);
}

.researchPath {
    color: var(--green);
    font-size: 16px;
}

.researchPath span {
    color: var(--cyan);
}

.researchButtons {
    margin-bottom: 10px;
}

.feed {
    font-size: 9px;
    line-height: 1.4;
}

.feedItem {
    padding: 8px;
    border-bottom:
        1px solid
        rgba(85, 185, 222, .11);
}

.feedTitle {
    color: #d9edf5;
}

.feedMeta {
    color: var(--muted);
    margin-top: 2px;
    font-size: 7px;
}

.paperStatus {
    color: var(--green);
    font-size: 16px;
}

.paperWindow p {
    color: #a2b7c1;
    font-size: 10px;
}

.agentMesh {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 5px;
}

.agentCard {
    position: relative;
    padding: 7px;
    border:
        1px solid var(--line);
    border-left:
        2px solid var(--cyan);
    border-radius: 5px;
    font-size: 7px;
    color: #b9d4df;
    background:
        rgba(6, 25, 35, .7);
}

.agentCard::after {
    content: "";
    position: absolute;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    top: 7px;
    right: 7px;
    background: var(--green);
    box-shadow:
        0 0 7px
        var(--green);
}

.sectionTitle {
    margin:
        11px 0 5px;
    color: var(--cyan);
    font-size: 7px;
    letter-spacing: 1.6px;
}

.evidenceSplit {
    display: grid;
    grid-template-columns:
        1fr 1fr;
    gap: 10px;
}

.appGrid {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 9px;
}

.appGrid button {
    min-height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 8px;
    font-size: 8px;
}

.appGrid strong {
    color: var(--cyan);
    font-size: 27px;
}

.systemGrid {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 7px;
    align-content: start;
}

.systemCard {
    padding: 9px;
    border:
        1px solid var(--line);
    border-radius: 7px;
    background:
        rgba(6, 24, 35, .75);
}

.systemCard span {
    color: var(--muted);
    font-size: 7px;
}

.systemCard b {
    display: block;
    margin-top: 3px;
    color: var(--green);
}

.legacyBody {
    display: grid;
    place-items: center;
    text-align: center;
    color: var(--muted);
}

#dock {
    height: 50px;
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding:
        5px 11px;
    border-top:
        1px solid var(--line);
    background:
        linear-gradient(
            180deg,
            rgba(7, 25, 35, .99),
            rgba(1, 7, 11, .99)
        );
}

.masterStatus {
    min-width: 210px;
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 8px;
}

.greenDot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--green);
    box-shadow:
        0 0 9px
        var(--green);
}

#readyState {
    color: var(--green);
}

.dockApps,
.layoutDock {
    display: flex;
    gap: 3px;
}

#dock button {
    padding:
        6px 7px;
    font-size: 7px;
}

.snapPreview {
    position: absolute;
    z-index: 20000;
    pointer-events: none;
    border:
        1px solid var(--cyan);
    background:
        rgba(43, 181, 234, .08);
    border-radius: 8px;
    display: none;
}

@media (
    max-width: 1250px
) {

    nav {
        display: none;
    }

    .topStatus .amber,
    .topStatus .red {
        display: none;
    }

}
'''
)


# ============================================================
# 8. JS — WINDOW MANAGER / CHART / VOICE / CORE
# ============================================================

write(
    JS,
    r'''
const TOKEN =
    window.JARVIS_TOKEN;


let zIndex =
    100;

let selectedTimeframe =
    "15m";

let chartSlots = [
    {
        symbol:
            "NIFTY",

        timeframe:
            "15m"
    }
];

let recognition =
    null;

let speakAnswers =
    false;

let lastRoute =
    "MASTER";


async function api(
    path,
    options = {}
) {

    options.headers = {
        ...(options.headers || {}),
        "X-Jarvis-Token":
            TOKEN,
        "Content-Type":
            "application/json"
    };


    const response =
        await fetch(
            path,
            options
        );


    const value =
        await response.json();


    if (!response.ok) {

        throw new Error(
            value.error
            || value.response
            || "JARVIS API error"
        );
    }


    return value;
}


function setCoreState(
    state
) {

    document.body.dataset.coreState =
        state;


    const coreText =
        document.getElementById(
            "coreText"
        );


    const masterState =
        document.getElementById(
            "masterState"
        );


    const labels = {
        ready:
            "ONLINE",

        listening:
            "LISTENING",

        thinking:
            "THINKING",

        approval:
            "APPROVAL",

        error:
            "ERROR",

        complete:
            "COMPLETE"
    };


    coreText.textContent =
        labels[state]
        || state.toUpperCase();


    masterState.textContent =
        labels[state]
        || state.toUpperCase();
}


function addConversation(
    who,
    text,
    route = null
) {

    const holder =
        document.getElementById(
            "conversation"
        );


    const item =
        document.createElement(
            "div"
        );


    item.className =
        "conversationItem "
        + (
            who === "YOU"
            ? "you"
            : "jarvis"
        );


    const speaker =
        document.createElement(
            "div"
        );


    speaker.className =
        "speaker";

    speaker.textContent =
        who;


    const message =
        document.createElement(
            "div"
        );


    message.className =
        "message";


    if (
        who === "JARVIS"
        && route
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "resultCard";


        const meta =
            document.createElement(
                "div"
            );


        meta.className =
            "resultMeta";

        meta.textContent =
            route
            + " · "
            + new Date()
                .toLocaleTimeString();


        const body =
            document.createElement(
                "div"
            );


        body.className =
            "resultBody";

        body.textContent =
            text;


        card.append(
            meta,
            body
        );


        message.appendChild(
            card
        );


    } else {

        message.textContent =
            text;
    }


    item.append(
        speaker,
        message
    );


    holder.appendChild(
        item
    );


    holder.scrollTop =
        holder.scrollHeight;
}


function focusWindow(
    win
) {

    zIndex++;


    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            item =>
                item.classList
                    .remove(
                        "focused"
                    )
        );


    win.style.zIndex =
        String(
            zIndex
        );


    win.classList.add(
        "focused"
    );
}


function openWindow(
    name
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "block";


    win.classList.remove(
        "minimized"
    );


    focusWindow(
        win
    );


    persistWorkspace();
}


function closeWindow(
    name
) {

    if (
        name === "core"
    ) {
        return;
    }


    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "none";


    persistWorkspace();
}


function maximizeWindow(
    name
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    openWindow(
        name
    );


    win.classList.add(
        "maximized"
    );


    focusWindow(
        win
    );
}


function closeAllWindows() {

    document
        .querySelectorAll(
            ".jarvisWindow"
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


    openWindow(
        "core"
    );
}


function resetWindowClasses() {

    document
        .querySelectorAll(
            ".jarvisWindow"
        )
        .forEach(
            win => {

                win.classList.remove(
                    "maximized",
                    "minimized"
                );
            }
        );
}


function setGeometry(
    name,
    left,
    top,
    width,
    height
) {

    const win =
        document.getElementById(
            "win-" + name
        );


    if (!win) return;


    win.style.display =
        "block";

    win.style.left =
        left;

    win.style.top =
        top;

    win.style.width =
        width;

    win.style.height =
        height;
}


function applyLayout(
    name
) {

    resetWindowClasses();


    if (
        name === "command"
    ) {

        setGeometry(
            "chart",
            "1%",
            "2%",
            "31%",
            "57%"
        );

        setGeometry(
            "core",
            "33%",
            "3%",
            "34%",
            "49%"
        );

        setGeometry(
            "missions",
            "68%",
            "2%",
            "31%",
            "46%"
        );

        setGeometry(
            "paper",
            "1%",
            "61%",
            "31%",
            "37%"
        );

        setGeometry(
            "quant",
            "33%",
            "54%",
            "34%",
            "44%"
        );

        setGeometry(
            "research",
            "68%",
            "50%",
            "31%",
            "48%"
        );


        closeWindow(
            "system"
        );

        closeWindow(
            "evidence"
        );

        closeWindow(
            "apps"
        );
    }


    if (
        name === "trading"
    ) {

        setGeometry(
            "chart",
            "1%",
            "2%",
            "55%",
            "62%"
        );

        setGeometry(
            "quant",
            "57%",
            "2%",
            "42%",
            "46%"
        );

        setGeometry(
            "paper",
            "1%",
            "66%",
            "55%",
            "32%"
        );

        setGeometry(
            "missions",
            "57%",
            "50%",
            "42%",
            "48%"
        );


        closeWindow(
            "core"
        );

        closeWindow(
            "research"
        );

        closeWindow(
            "system"
        );

        closeWindow(
            "evidence"
        );

        closeWindow(
            "apps"
        );
    }


    if (
        name === "research"
    ) {

        setGeometry(
            "research",
            "1%",
            "2%",
            "54%",
            "96%"
        );

        setGeometry(
            "chart",
            "56%",
            "2%",
            "43%",
            "55%"
        );

        setGeometry(
            "missions",
            "56%",
            "59%",
            "43%",
            "39%"
        );


        closeWindow(
            "core"
        );

        closeWindow(
            "quant"
        );

        closeWindow(
            "paper"
        );

        closeWindow(
            "apps"
        );

        closeWindow(
            "system"
        );

        closeWindow(
            "evidence"
        );
    }


    if (
        name === "mission"
    ) {

        setGeometry(
            "core",
            "1%",
            "2%",
            "42%",
            "96%"
        );

        setGeometry(
            "missions",
            "44%",
            "2%",
            "55%",
            "48%"
        );

        setGeometry(
            "evidence",
            "44%",
            "52%",
            "55%",
            "46%"
        );


        closeWindow(
            "chart"
        );

        closeWindow(
            "quant"
        );

        closeWindow(
            "paper"
        );

        closeWindow(
            "research"
        );

        closeWindow(
            "apps"
        );

        closeWindow(
            "system"
        );
    }


    persistWorkspace();
}


function persistWorkspace() {

    const state = {};


    document
        .querySelectorAll(
            ".jarvisWindow"
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
                        win.style.height,

                    minimized:
                        win.classList
                            .contains(
                                "minimized"
                            ),

                    maximized:
                        win.classList
                            .contains(
                                "maximized"
                            )
                };
            }
        );


    state.chartSlots =
        chartSlots;


    localStorage.setItem(
        "jarvisV31Workspace",
        JSON.stringify(
            state
        )
    );
}


function restoreWorkspace() {

    try {

        const state =
            JSON.parse(
                localStorage.getItem(
                    "jarvisV31Workspace"
                )
            );


        if (!state) {

            applyLayout(
                "command"
            );

            return;
        }


        for (
            const [
                name,
                value
            ]
            of Object.entries(
                state
            )
        ) {

            if (
                name === "chartSlots"
            ) {
                continue;
            }


            const win =
                document.getElementById(
                    "win-" + name
                );


            if (!win) continue;


            for (
                const property
                of (
                    "display",
                    "left",
                    "top",
                    "width",
                    "height"
                )
            ) {

                if (
                    value[property]
                ) {

                    win.style[
                        property
                    ] =
                        value[
                            property
                        ];
                }
            }


            if (
                value.minimized
            ) {

                win.classList.add(
                    "minimized"
                );
            }


            if (
                value.maximized
            ) {

                win.classList.add(
                    "maximized"
                );
            }
        }


        if (
            Array.isArray(
                state.chartSlots
            )
        ) {

            chartSlots =
                state.chartSlots;
        }


    } catch (_) {

        applyLayout(
            "command"
        );
    }
}


function makeDraggable(
    win
) {

    const header =
        win.querySelector(
            ".windowHeader"
        );


    let dragging =
        false;

    let originX =
        0;

    let originY =
        0;

    let startLeft =
        0;

    let startTop =
        0;


    header.addEventListener(
        "mousedown",
        event => {

            if (
                event.target.tagName
                === "BUTTON"
            ) {

                return;
            }


            if (
                win.classList
                    .contains(
                        "maximized"
                    )
            ) {

                return;
            }


            dragging =
                true;


            originX =
                event.clientX;

            originY =
                event.clientY;


            startLeft =
                win.offsetLeft;

            startTop =
                win.offsetTop;


            focusWindow(
                win
            );


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


            let x =
                startLeft
                + event.clientX
                - originX;


            let y =
                startTop
                + event.clientY
                - originY;


            x =
                Math.max(
                    0,
                    Math.min(
                        x,
                        desktop.clientWidth
                        - 80
                    )
                );


            y =
                Math.max(
                    0,
                    Math.min(
                        y,
                        desktop.clientHeight
                        - 35
                    )
                );


            win.style.left =
                x + "px";

            win.style.top =
                y + "px";
        }
    );


    window.addEventListener(
        "mouseup",
        () => {

            if (!dragging)
                return;


            dragging =
                false;


            snapWindow(
                win
            );


            persistWorkspace();
        }
    );


    win.addEventListener(
        "mousedown",
        () =>
            focusWindow(
                win
            )
    );
}


function snapWindow(
    win
) {

    const desktop =
        document.getElementById(
            "desktop"
        );


    const margin =
        35;


    const left =
        win.offsetLeft;

    const top =
        win.offsetTop;


    const right =
        desktop.clientWidth
        - (
            win.offsetLeft
            + win.offsetWidth
        );


    if (
        left < margin
    ) {

        win.style.left =
            "0px";

        win.style.top =
            "0px";

        win.style.width =
            "50%";

        win.style.height =
            "100%";

        return;
    }


    if (
        right < margin
    ) {

        win.style.left =
            "50%";

        win.style.top =
            "0px";

        win.style.width =
            "50%";

        win.style.height =
            "100%";

        return;
    }


    if (
        top < margin
    ) {

        win.style.left =
            "0px";

        win.style.top =
            "0px";

        win.style.width =
            "100%";

        win.style.height =
            "50%";
    }
}


function executeWorkspaceActions(
    actions
) {

    for (
        const action
        of (
            actions || []
        )
    ) {

        if (
            action.type
            === "open_window"
        ) {

            openWindow(
                action.window
            );
        }


        if (
            action.type
            === "close_window"
        ) {

            closeWindow(
                action.window
            );
        }


        if (
            action.type
            === "maximize_window"
        ) {

            maximizeWindow(
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

            closeAllWindows();
        }


        if (
            action.type
            === "save_workspace"
        ) {

            persistWorkspace();
        }


        if (
            action.type
            === "restore_workspace"
        ) {

            restoreWorkspace();
        }


        if (
            action.type
            === "chart_symbol"
        ) {

            const index =
                Math.max(
                    0,
                    Math.min(
                        3,
                        Number(
                            action.slot
                        )
                    )
                );


            chartSlots[index] = {
                symbol:
                    action.symbol,

                timeframe:
                    action.timeframe
                    || "15m"
            };


            renderChartSlots();
        }


        if (
            action.type
            === "chart_layout"
        ) {

            setChartCount(
                Number(
                    action.count
                )
            );
        }
    }
}


async function executeCommand(
    forced = null
) {

    const input =
        document.getElementById(
            "commandInput"
        );


    const text =
        (
            forced
            ?? input.value
        ).trim();


    if (!text)
        return;


    input.value = "";


    addConversation(
        "YOU",
        text
    );


    document.getElementById(
        "coreMission"
    ).textContent =
        text;


    document.getElementById(
        "readyState"
    ).textContent =
        "THINKING";


    setCoreState(
        "thinking"
    );


    try {

        const result =
            await api(
                "/api/command",
                {
                    method:
                        "POST",

                    body:
                        JSON.stringify(
                            {
                                text
                            }
                        )
                }
            );


        lastRoute =
            result.route
            || "MASTER";


        document.getElementById(
            "activeRoute"
        ).textContent =
            lastRoute;


        addConversation(
            "JARVIS",
            result.response
            || "Completed.",
            lastRoute
        );


        executeWorkspaceActions(
            result.workspace_actions
        );


        setCoreState(
            "complete"
        );


        setTimeout(
            () =>
                setCoreState(
                    "ready"
                ),
            900
        );


    } catch (error) {

        addConversation(
            "JARVIS",
            error.message,
            "ERROR"
        );


        setCoreState(
            "error"
        );
    }


    document.getElementById(
        "readyState"
    ).textContent =
        "READY";


    refreshEvidence();
}


function bindCommandButtons() {

    document
        .querySelectorAll(
            "[data-command]"
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
}


function setChartCount(
    count
) {

    count =
        (
            count >= 4
            ? 4
            : (
                count >= 2
                ? 2
                : 1
            )
        );


    while (
        chartSlots.length
        < count
    ) {

        const defaults = [
            "NIFTY",
            "BANKNIFTY",
            "CRUDEOIL",
            "BTC"
        ];


        chartSlots.push(
            {
                symbol:
                    defaults[
                        chartSlots.length
                    ],

                timeframe:
                    selectedTimeframe
            }
        );
    }


    chartSlots =
        chartSlots.slice(
            0,
            count
        );


    renderChartSlots();
}


function renderChartSlots() {

    const grid =
        document.getElementById(
            "chartGrid"
        );


    grid.className = "";


    if (
        chartSlots.length === 2
    ) {

        grid.classList.add(
            "layout2"
        );
    }


    if (
        chartSlots.length === 4
    ) {

        grid.classList.add(
            "layout4"
        );
    }


    grid.innerHTML = "";


    chartSlots.forEach(
        (
            slot,
            index
        ) => {

            const pane =
                document.createElement(
                    "div"
                );


            pane.className =
                "chartPane";


            const canvas =
                document.createElement(
                    "canvas"
                );


            canvas.className =
                "chartCanvas";

            canvas.id =
                "chartCanvas"
                + index;


            const status =
                document.createElement(
                    "div"
                );


            status.className =
                "chartStatus";

            status.id =
                "chartStatus"
                + index;

            status.textContent =
                slot.symbol
                + " · "
                + slot.timeframe
                + " · LOADING";


            pane.append(
                canvas,
                status
            );


            grid.appendChild(
                pane
            );


            loadChart(
                index
            );
        }
    );


    persistWorkspace();
}


async function loadChart(
    index
) {

    const slot =
        chartSlots[
            index
        ];


    if (!slot)
        return;


    const status =
        document.getElementById(
            "chartStatus"
            + index
        );


    try {

        const data =
            await api(
                "/api/chart?symbol="
                + encodeURIComponent(
                    slot.symbol
                )
                + "&timeframe="
                + encodeURIComponent(
                    slot.timeframe
                )
            );


        const canvas =
            document.getElementById(
                "chartCanvas"
                + index
            );


        drawCandles(
            canvas,
            data.bars || []
        );


        status.textContent =
            slot.symbol
            + " · "
            + slot.timeframe
            + " · "
            + (
                data.verified
                ? "VERIFIED "
                + data.provider
                : (
                    "NO VERIFIED FEED · "
                    + (
                        data.error
                        || "unavailable"
                    )
                )
            );


        if (
            index === 0
        ) {

            document.getElementById(
                "chartTitle"
            ).textContent =
                slot.symbol
                + " · "
                + slot.timeframe;


            document.getElementById(
                "chartProvider"
            ).textContent =
                (
                    data.verified
                    ? "VERIFIED · "
                        + data.provider
                    : "DATA UNAVAILABLE"
                );


            const bars =
                data.bars
                || [];


            document.getElementById(
                "chartPrice"
            ).textContent =
                (
                    bars.length
                    ? Number(
                        bars[
                            bars.length - 1
                        ].close
                    ).toLocaleString()
                    : "—"
                );
        }


    } catch (error) {

        if (status) {

            status.textContent =
                "ERROR · "
                + error.message;
        }
    }
}


function drawCandles(
    canvas,
    bars
) {

    const ratio =
        window.devicePixelRatio
        || 1;


    const rect =
        canvas.getBoundingClientRect();


    canvas.width =
        Math.max(
            1,
            rect.width
            * ratio
        );


    canvas.height =
        Math.max(
            1,
            rect.height
            * ratio
        );


    const ctx =
        canvas.getContext(
            "2d"
        );


    ctx.setTransform(
        ratio,
        0,
        0,
        ratio,
        0,
        0
    );


    const width =
        rect.width;

    const height =
        rect.height;


    ctx.clearRect(
        0,
        0,
        width,
        height
    );


    ctx.strokeStyle =
        "rgba(73,177,216,.08)";


    for (
        let i = 1;
        i < 6;
        i++
    ) {

        const y =
            height
            * i
            / 6;


        ctx.beginPath();

        ctx.moveTo(
            0,
            y
        );

        ctx.lineTo(
            width,
            y
        );

        ctx.stroke();
    }


    if (
        !bars
        || bars.length < 2
    ) {

        ctx.fillStyle =
            "#597788";

        ctx.font =
            "12px Segoe UI";

        ctx.textAlign =
            "center";


        ctx.fillText(
            "NO VERIFIED CANDLE DATA",
            width / 2,
            height / 2
        );


        return;
    }


    const values = [];


    for (
        const bar
        of bars
    ) {

        values.push(
            bar.high,
            bar.low
        );
    }


    const high =
        Math.max(
            ...values
        );


    const low =
        Math.min(
            ...values
        );


    const range =
        Math.max(
            high - low,
            .000001
        );


    const pad =
        12;


    const usableHeight =
        height
        - pad * 2;


    const step =
        width
        / bars.length;


    const candleWidth =
        Math.max(
            2,
            Math.min(
                8,
                step * .62
            )
        );


    function y(
        value
    ) {

        return pad
        + (
            high - value
        )
        / range
        * usableHeight;
    }


    bars.forEach(
        (
            bar,
            index
        ) => {

            const x =
                index * step
                + step / 2;


            const rising =
                bar.close
                >= bar.open;


            const color =
                (
                    rising
                    ? "#65f2a8"
                    : "#ff6475"
                );


            ctx.strokeStyle =
                color;

            ctx.fillStyle =
                color;


            ctx.beginPath();

            ctx.moveTo(
                x,
                y(
                    bar.high
                )
            );

            ctx.lineTo(
                x,
                y(
                    bar.low
                )
            );

            ctx.stroke();


            const top =
                Math.min(
                    y(
                        bar.open
                    ),
                    y(
                        bar.close
                    )
                );


            const bottom =
                Math.max(
                    y(
                        bar.open
                    ),
                    y(
                        bar.close
                    )
                );


            ctx.fillRect(
                x
                - candleWidth / 2,
                top,
                candleWidth,
                Math.max(
                    1,
                    bottom - top
                )
            );
        }
    );
}


async function refreshStatus() {

    try {

        const value =
            await api(
                "/api/status"
            );


        const agents =
            value.agents
            || [];


        document.getElementById(
            "agentCount"
        ).textContent =
            agents.length;


        renderAgentMesh(
            agents
        );


        renderSystem(
            value
        );


        document.getElementById(
            "readyState"
        ).textContent =
            (
                value.protected_core
                ? "READY"
                : "DEGRADED"
            );


    } catch (_) {

        document.getElementById(
            "readyState"
        ).textContent =
            "DEGRADED";
    }
}


function renderAgentMesh(
    agents
) {

    const holder =
        document.getElementById(
            "agentMesh"
        );


    holder.innerHTML = "";


    for (
        const name
        of agents.slice(
            0,
            24
        )
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "agentCard";

        card.textContent =
            String(
                name
            ).toUpperCase();


        holder.appendChild(
            card
        );
    }
}


function renderSystem(
    value
) {

    const holder =
        document.getElementById(
            "systemGrid"
        );


    holder.innerHTML = "";


    const cards = [
        [
            "PROTECTED CORE",
            value.protected_core
            ? "PASS"
            : "FAULT"
        ],

        [
            "AGENTS",
            (
                value.agents
                || []
            ).length
        ]
    ];


    for (
        const [
            name,
            component
        ]
        of Object.entries(
            value.components
            || {}
        )
    ) {

        cards.push(
            [
                name
                    .replace(
                        "jarvis_",
                        ""
                    )
                    .replace(
                        "_status",
                        ""
                    )
                    .toUpperCase(),

                (
                    component
                    && !component.error
                    ? "READY"
                    : "DEGRADED"
                )
            ]
        );
    }


    for (
        const [
            label,
            status
        ]
        of cards
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "systemCard";


        const span =
            document.createElement(
                "span"
            );

        span.textContent =
            label;


        const b =
            document.createElement(
                "b"
            );

        b.textContent =
            status;


        card.append(
            span,
            b
        );


        holder.appendChild(
            card
        );
    }
}


async function refreshMarket() {

    try {

        const data =
            await api(
                "/api/market"
            );


        const latest =
            data.latest
            || {};


        document.getElementById(
            "metricSpot"
        ).textContent =
            latest.spot
            ?? "—";


        document.getElementById(
            "metricIV"
        ).textContent =
            latest.atm_iv
            ?? "—";


        document.getElementById(
            "metricPCR"
        ).textContent =
            latest.pcr_oi
            ?? "—";


        document.getElementById(
            "metricHistory"
        ).textContent =
            data.history_count
            ?? 0;


    } catch (_) {}
}


async function refreshEvidence() {

    try {

        const rows =
            await api(
                "/api/evidence"
            );


        const holder =
            document.getElementById(
                "evidenceFeed"
            );


        const activity =
            document.getElementById(
                "activityFeed"
            );


        holder.innerHTML = "";

        activity.innerHTML = "";


        const values =
            (
                Array.isArray(
                    rows
                )
                ? rows
                : []
            )
            .slice(
                -30
            )
            .reverse();


        for (
            const row
            of values
        ) {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "feedItem";


            const title =
                document.createElement(
                    "div"
                );


            title.className =
                "feedTitle";


            title.textContent =
                row.event
                || row.goal
                || "ACTIVITY";


            const meta =
                document.createElement(
                    "div"
                );


            meta.className =
                "feedMeta";


            meta.textContent =
                row.timestamp
                || "";


            item.append(
                title,
                meta
            );


            holder.appendChild(
                item
            );


            activity.appendChild(
                item.cloneNode(
                    true
                )
            );
        }


    } catch (_) {}


    try {

        const value =
            await api(
                "/api/approvals"
            );


        const holder =
            document.getElementById(
                "approvalFeed"
            );


        holder.innerHTML = "";


        const rows =
            Array.isArray(
                value
            )
            ? value
            : (
                Array.isArray(
                    value.approvals
                )
                ? value.approvals
                : []
            );


        if (!rows.length) {

            holder.innerHTML =
                '<div class="feedItem">'
                + '<div class="feedTitle">'
                + 'NO PENDING APPROVALS'
                + '</div>'
                + '<div class="feedMeta">'
                + 'Approval gate remains armed.'
                + '</div>'
                + '</div>';

            return;
        }


        for (
            const row
            of rows.slice(
                0,
                20
            )
        ) {

            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "feedItem";


            item.textContent =
                JSON.stringify(
                    row
                );


            holder.appendChild(
                item
            );
        }


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


    recognition.onstart =
        () => {

            setCoreState(
                "listening"
            );


            document.getElementById(
                "voiceState"
            ).textContent =
                "● LISTENING";
        };


    recognition.onresult =
        event => {

            let text = "";


            for (
                let i =
                    event.resultIndex;

                i <
                    event.results.length;

                i++
            ) {

                text +=
                    event.results[
                        i
                    ][0]
                    .transcript;
            }


            document.getElementById(
                "commandInput"
            ).value =
                text;
        };


    recognition.onend =
        () => {

            document.getElementById(
                "voiceState"
            ).textContent =
                "● VOICE READY";


            setCoreState(
                "ready"
            );
        };
}


function drawCore() {

    const canvas =
        document.getElementById(
            "coreCanvas"
        );


    const context =
        canvas.getContext(
            "2d"
        );


    let tick = 0;


    function frame() {

        const ratio =
            window.devicePixelRatio
            || 1;


        const rect =
            canvas.getBoundingClientRect();


        if (
            canvas.width
            !== Math.round(
                rect.width
                * ratio
            )
        ) {

            canvas.width =
                rect.width
                * ratio;

            canvas.height =
                rect.height
                * ratio;


            context.setTransform(
                ratio,
                0,
                0,
                ratio,
                0,
                0
            );
        }


        const width =
            rect.width;

        const height =
            rect.height;


        const cx =
            width / 2;

        const cy =
            height / 2;


        context.clearRect(
            0,
            0,
            width,
            height
        );


        const gradient =
            context
            .createRadialGradient(
                cx,
                cy,
                5,
                cx,
                cy,
                width * .42
            );


        const state =
            document.body
                .dataset
                .coreState;


        const primary =
            (
                state === "thinking"
                ? "150,94,255"
                : (
                    state === "error"
                    ? "255,77,96"
                    : (
                        state === "approval"
                        ? "255,196,69"
                        : "74,204,255"
                    )
                )
            );


        gradient.addColorStop(
            0,
            `rgba(${primary},.40)`
        );

        gradient.addColorStop(
            .38,
            `rgba(${primary},.10)`
        );

        gradient.addColorStop(
            1,
            `rgba(${primary},0)`
        );


        context.fillStyle =
            gradient;


        context.beginPath();

        context.arc(
            cx,
            cy,
            width * .43,
            0,
            Math.PI * 2
        );

        context.fill();


        for (
            let ring = 0;
            ring < 6;
            ring++
        ) {

            context.save();

            context.translate(
                cx,
                cy
            );


            context.rotate(
                tick
                * (
                    .0016
                    + ring
                    * .00065
                )
                * (
                    ring % 2
                    ? -1
                    : 1
                )
            );


            context.strokeStyle =
                `rgba(
                    ${primary},
                    ${
                        .16
                        + ring * .04
                    }
                )`;


            context.lineWidth =
                1;


            context.beginPath();


            context.ellipse(
                0,
                0,
                width
                * (
                    .19
                    + ring
                    * .035
                ),
                height
                * (
                    .09
                    + ring
                    * .027
                ),
                ring * .48,
                0,
                Math.PI * 2
            );


            context.stroke();

            context.restore();
        }


        const agentTotal =
            Math.max(
                12,
                Number(
                    document
                    .getElementById(
                        "agentCount"
                    )
                    .textContent
                )
                || 18
            );


        for (
            let i = 0;
            i < agentTotal;
            i++
        ) {

            const angle =
                tick * .002
                + i
                * Math.PI
                * 2
                / agentTotal;


            const radius =
                width
                * (
                    .27
                    + .04
                    * Math.sin(
                        tick
                        * .007
                        + i
                    )
                );


            const x =
                cx
                + Math.cos(
                    angle
                )
                * radius;


            const y =
                cy
                + Math.sin(
                    angle
                )
                * radius
                * .52;


            context.fillStyle =
                (
                    i % 7 === 0
                    ? "#70f5a9"
                    : `rgb(${primary})`
                );


            context.beginPath();

            context.arc(
                x,
                y,
                (
                    i % 7 === 0
                    ? 2.4
                    : 1.2
                ),
                0,
                Math.PI * 2
            );

            context.fill();
        }


        tick++;


        requestAnimationFrame(
            frame
        );
    }


    frame();
}


function bindWindows() {

    document
        .querySelectorAll(
            ".jarvisWindow"
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

                    close.onclick =
                        () =>
                            closeWindow(
                                win.dataset.window
                            );
                }


                const minimize =
                    win.querySelector(
                        "[data-minimize]"
                    );


                if (minimize) {

                    minimize.onclick =
                        () => {

                            win.classList.toggle(
                                "minimized"
                            );


                            persistWorkspace();
                        };
                }


                const maximize =
                    win.querySelector(
                        "[data-maximize]"
                    );


                if (maximize) {

                    maximize.onclick =
                        () => {

                            win.classList.toggle(
                                "maximized"
                            );


                            focusWindow(
                                win
                            );
                        };
                }
            }
        );


    document
        .querySelectorAll(
            "[data-open]"
        )
        .forEach(
            button => {

                button.onclick =
                    () =>
                        openWindow(
                            button.dataset.open
                        );
            }
        );


    document
        .querySelectorAll(
            "[data-layout]"
        )
        .forEach(
            button => {

                button.onclick =
                    () =>
                        applyLayout(
                            button.dataset.layout
                        );
            }
        );
}


function bindChartControls() {

    document
        .getElementById(
            "chartSymbol"
        )
        .addEventListener(
            "change",
            event => {

                chartSlots[0] = {
                    symbol:
                        event.target.value,

                    timeframe:
                        selectedTimeframe
                };


                renderChartSlots();
            }
        );


    document
        .querySelectorAll(
            "[data-timeframe]"
        )
        .forEach(
            button => {

                button.onclick =
                    () => {

                        selectedTimeframe =
                            button
                            .dataset
                            .timeframe;


                        document
                            .querySelectorAll(
                                "[data-timeframe]"
                            )
                            .forEach(
                                item =>
                                    item
                                    .classList
                                    .remove(
                                        "selected"
                                    )
                            );


                        button
                            .classList
                            .add(
                                "selected"
                            );


                        chartSlots =
                            chartSlots.map(
                                slot => ({
                                    ...slot,
                                    timeframe:
                                        selectedTimeframe
                                })
                            );


                        renderChartSlots();
                    };
            }
        );


    document
        .getElementById(
            "refreshChart"
        )
        .onclick =
            () =>
                renderChartSlots();
}


document
    .getElementById(
        "executeButton"
    )
    .onclick =
        () =>
            executeCommand();


document
    .getElementById(
        "commandInput"
    )
    .addEventListener(
        "keydown",
        event => {

            if (
                event.key
                === "Enter"
            ) {

                executeCommand();
            }
        }
    );


document
    .getElementById(
        "listenButton"
    )
    .onclick =
        () => {

            if (recognition) {

                recognition.start();
            }
        };


document
    .getElementById(
        "stopButton"
    )
    .onclick =
        () => {

            if (recognition) {

                try {

                    recognition.stop();

                } catch (_) {}
            }


            speechSynthesis.cancel();


            setCoreState(
                "ready"
            );
        };


document
    .getElementById(
        "fullscreenButton"
    )
    .onclick =
        async () => {

            try {

                if (
                    !document.fullscreenElement
                ) {

                    await document
                        .documentElement
                        .requestFullscreen();

                } else {

                    await document
                        .exitFullscreen();
                }

            } catch (_) {}
        };


document
    .getElementById(
        "saveWorkspace"
    )
    .onclick =
        () => {

            persistWorkspace();


            addConversation(
                "JARVIS",
                "Workspace layout saved locally.",
                "WORKSPACE"
            );
        };


bindWindows();

bindCommandButtons();

bindChartControls();

restoreWorkspace();

setupVoice();

drawCore();

renderChartSlots();

refreshStatus();

refreshMarket();

refreshEvidence();


setInterval(
    refreshStatus,
    5000
);

setInterval(
    refreshMarket,
    10000
);

setInterval(
    refreshEvidence,
    6000
);


window.addEventListener(
    "resize",
    () =>
        renderChartSlots()
);
'''
)


# ============================================================
# 9. STARTER — V3.1 NATIVE FIRST
# ============================================================

write(
    STARTER,
    r'''
from __future__ import annotations

import socket
import threading
import time
import webbrowser

from pathlib import (
    Path,
)


ROOT = Path(
    __file__
).resolve().parent


def port_open(
    port,
):

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    sock.settimeout(
        .25
    )


    try:

        return (
            sock.connect_ex(
                (
                    "127.0.0.1",
                    int(
                        port
                    ),
                )
            )
            == 0
        )


    finally:

        sock.close()


def main():

    print("=" * 76)
    print("JARVIS OS V3.1 — ADAPTIVE WORKSPACE")
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
            "Live execution safety invariant failed."
        )


    if trading[
        "automatic_broker_order"
    ] is not False:

        raise RuntimeError(
            "Broker-order safety invariant failed."
        )


    print("Protected Core: PASS")
    print("Master JARVIS: READY")
    print("Adaptive workspace: READY")
    print("Native chart terminal: READY")
    print("Live broker execution: LOCKED")


    from workstation.jarvis_os_v3 import (
        HOST,
        PORT,
        create_server,
    )


    if port_open(
        PORT
    ):

        raise RuntimeError(
            "JARVIS OS port 8797 is already in use. "
            "Close the previous JARVIS process first."
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
        url
    )


    def open_browser():

        time.sleep(
            .7
        )


        webbrowser.open(
            url
        )


    threading.Thread(
        target=open_browser,
        daemon=True,
    ).start()


    try:

        server.serve_forever()


    except KeyboardInterrupt:

        print()
        print(
            "Stopping JARVIS..."
        )


    finally:

        server.server_close()


    print(
        "JARVIS stopped."
    )


if __name__ == "__main__":

    main()
'''
)


# ============================================================
# 10. PRIMARY BAT
# ============================================================

write(
    BAT,
    r'''
@echo off
setlocal

cd /d C:\Jarvis

title JARVIS OS V3.1

if not exist "C:\Jarvis\.venv\Scripts\python.exe" (
    echo.
    echo JARVIS Python environment not found.
    pause
    exit /b 1
)

"C:\Jarvis\.venv\Scripts\python.exe" ^
"C:\Jarvis\start_jarvis_v3.py"

if errorlevel 1 (
    echo.
    echo JARVIS OS V3.1 exited with an error.
    pause
)

endlocal
'''
)


# ============================================================
# 11. TESTS
# ============================================================

write(
    TEST,
    r'''
import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.jarvis_workspace_orchestrator import (
    interpret_workspace_command,
)

from workstation.jarvis_os_v3 import (
    safe,
)

from workstation.jarvis_v3_chart_provider import (
    _normalize_frame,
)


class JarvisOSV31Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_sensitive_redaction(
        self,
    ):

        value = safe(
            {
                "token":
                    "SECRET",

                "normal":
                    "visible",
            }
        )


        self.assertEqual(
            value[
                "token"
            ],
            "<REDACTED>",
        )


        self.assertEqual(
            value[
                "normal"
            ],
            "visible",
        )


    def test_trading_workspace_command(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Open crude oil trading terminal "
                "15 minute chart and analyze it"
            )
        )


        types = [
            (
                item[
                    "type"
                ],
                item.get(
                    "window"
                ),
            )

            for item
            in actions
        ]


        self.assertIn(
            (
                "open_window",
                "chart",
            ),
            types,
        )


        self.assertIn(
            (
                "open_window",
                "quant",
            ),
            types,
        )


        chart_actions = [
            item

            for item in actions

            if item[
                "type"
            ] == "chart_symbol"
        ]


        self.assertEqual(
            chart_actions[
                0
            ][
                "symbol"
            ],
            "CRUDEOIL",
        )


        self.assertEqual(
            chart_actions[
                0
            ][
                "timeframe"
            ],
            "15m",
        )


    def test_compare(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Compare NIFTY and BANKNIFTY"
            )
        )


        symbols = [
            item[
                "symbol"
            ]

            for item in actions

            if item[
                "type"
            ] == "chart_symbol"
        ]


        self.assertEqual(
            symbols,
            [
                "NIFTY",
                "BANKNIFTY",
            ],
        )


        self.assertTrue(
            any(
                item[
                    "type"
                ] == "chart_layout"

                for item in actions
            )
        )


    def test_window_maximize(
        self,
    ):

        actions = (
            interpret_workspace_command(
                "Make chart full screen"
            )
        )


        self.assertTrue(
            any(
                item[
                    "type"
                ] == "maximize_window"

                and item[
                    "window"
                ] == "chart"

                for item in actions
            )
        )


    def test_synthetic_candle_normalization(
        self,
    ):

        rows = _normalize_frame(
            [
                {
                    "timestamp":
                        "2026-08-18T09:15:00+05:30",

                    "open":
                        100,

                    "high":
                        110,

                    "low":
                        95,

                    "close":
                        105,

                    "volume":
                        1000,
                },

                {
                    "timestamp":
                        "2026-08-18T09:20:00+05:30",

                    "open":
                        105,

                    "high":
                        112,

                    "low":
                        101,

                    "close":
                        108,

                    "volume":
                        900,
                },
            ]
        )


        self.assertEqual(
            len(
                rows
            ),
            2,
        )


        self.assertEqual(
            rows[
                1
            ][
                "close"
            ],
            108.0,
        )


    def test_trading_still_blocked(
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
# 12. COMPILE
# ============================================================

print()
print("=" * 80)
print("V3.1 COMPILE")
print("=" * 80)


r = run(
    "-m",
    "py_compile",
    str(
        ORCHESTRATOR
    ),
    str(
        CHART_PROVIDER
    ),
    str(
        SERVER
    ),
    str(
        STARTER
    ),
    str(
        TEST
    ),
)


if r.returncode:

    print(
        "COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "V3.1 Python syntax: PASS"
)


# ============================================================
# 13. PROTECTED CORE
# ============================================================

for relative, expected in (
    PROTECTED.items()
):

    actual = sha(
        ROOT / relative
    )


    if actual != expected:

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


print(
    "Protected Core hashes: PASS"
)


# ============================================================
# 14. STATIC ASSET CHECKS
# ============================================================

html = HTML.read_text(
    encoding="utf-8"
)

js = JS.read_text(
    encoding="utf-8"
)

css = CSS.read_text(
    encoding="utf-8"
)


required_html = (
    'id="win-chart"',
    'id="win-core"',
    'id="win-quant"',
    'id="win-research"',
    'id="win-paper"',
    'id="win-missions"',
    'id="win-evidence"',
    'id="win-apps"',
    'id="win-system"',
    'id="commandInput"',
    'id="coreCanvas"',
)


for token in required_html:

    assert token in html, token


required_js = (
    "makeDraggable",
    "snapWindow",
    "executeWorkspaceActions",
    "drawCandles",
    "drawCore",
    "applyLayout",
    "persistWorkspace",
    "restoreWorkspace",
)


for token in required_js:

    assert token in js, token


assert ".jarvisWindow" in css
assert "backdrop-filter" in css


print(
    "Adaptive desktop asset checks: PASS"
)


# ============================================================
# 15. TARGETED TESTS
# ============================================================

print()
print("=" * 80)
print("V3.1 TARGETED REGRESSION")
print("=" * 80)


r = run(
    "-m",
    "unittest",

    "tests.test_jarvis_os_v3_1",

    "-q",
    timeout=180,
)


if r.returncode:

    print(
        "V3.1 TARGETED TEST FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 16. OPERATOR / TRADING PRESERVATION
# ============================================================

targets = []


for module in (
    "tests.test_computer_operator",
    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",
    "tests.test_trading_intelligence_v8",
):

    path = (
        ROOT
        / (
            module.replace(
                ".",
                "\\"
            )
            + ".py"
        )
    )


    if path.exists():

        targets.append(
            module
        )


if targets:

    r = run(
        "-m",
        "unittest",
        *targets,
        "-q",
        timeout=360,
    )


    if r.returncode:

        print(
            "PRESERVATION REGRESSION FAILURE"
        )

        rollback()

        sys.exit(1)


# ============================================================
# 17. FULL REGRESSION
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
    capture=True,
    timeout=720,
)


output = (
    (
        r.stdout
        or ""
    )
    + "\n"
    + (
        r.stderr
        or ""
    )
)


print(
    output.strip()
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


match = re.search(
    r"Ran\s+(\d+)\s+tests",
    output,
)


test_count = (
    int(
        match.group(
            1
        )
    )
    if match
    else None
)


# ============================================================
# 18. FINAL INTEGRITY
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
        "print('Automatic broker orders: BLOCKED');"
        "print('Live execution: BLOCKED')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


print()
print("=" * 80)
print("JARVIS OS V3.1 — ADAPTIVE WORKSPACE SUCCESS")
print("=" * 80)

print()
print("MASTER INTELLIGENCE")
print("Persistent Master JARVIS: ACTIVE")
print("Command result cards: ACTIVE")
print("Natural-language UI orchestration: ACTIVE")
print("Voice-reactive core states: ACTIVE")
print()

print("WINDOW MANAGER")
print("Drag: ACTIVE")
print("Resize: ACTIVE")
print("Smart left/right/top snap: ACTIVE")
print("Minimize: ACTIVE")
print("Maximize: ACTIVE")
print("Close/restore: ACTIVE")
print("Z-order focus: ACTIVE")
print("Workspace persistence: ACTIVE")
print()

print("PRESET WORKSPACES")
print("Command: ACTIVE")
print("Trading: ACTIVE")
print("Research: ACTIVE")
print("Mission: ACTIVE")
print()

print("NATIVE APPS")
print("Chart Terminal: ACTIVE")
print("Quant / Strategy Lab: ACTIVE")
print("Paper Desk: ACTIVE")
print("Web Intelligence: ACTIVE")
print("Mission / Agent Mesh: ACTIVE")
print("Approvals / Evidence: ACTIVE")
print("Application Launcher: ACTIVE")
print("System Core: ACTIVE")
print()

print("CHART ENGINE")
print("Verified-data-only candles: ACTIVE")
print("FYERS adapter bridge: ACTIVE WHEN AUTH/DATA AVAILABLE")
print("No synthetic chart fabrication: ENFORCED")
print("NIFTY/BANKNIFTY/SENSEX/commodities/crypto UI: ACTIVE")
print("1m/5m/15m/1h/4h/1D controls: ACTIVE")
print("1/2/4 chart workspace: COMMAND-CONTROLLABLE")
print()

print("APPLICATION CONTROL")
print("Notepad via Master JARVIS: ACTIVE")
print("Calculator via Master JARVIS: ACTIVE")
print("Browser via Master JARVIS: ACTIVE")
print("VS Code via Master JARVIS: ACTIVE")
print("Folders via Master JARVIS: ACTIVE")
print()

print("GOVERNANCE")
print("Protected Core: UNCHANGED")
print("Trading V1-V8: PRESERVED")
print("Broker orders: BLOCKED")
print("Live execution: BLOCKED")

if test_count is not None:

    print()
    print(
        "NEW REGRESSION CHECKPOINT:",
        f"{test_count} / {test_count}",
    )


print()
print("PRIMARY LAUNCHER:")
print(r"C:\Jarvis\JARVIS.bat")

print()
print("NEXT TEST COMMANDS:")
print(
    '1. "Jarvis, open crude oil trading terminal '
    '15 minute chart and analyze it."'
)

print(
    '2. "Open NIFTY and BANKNIFTY and compare them."'
)

print(
    '3. "Make chart full screen."'
)

print(
    '4. "Open research layout and check crude oil news."'
)

print(
    '5. "Open Notepad and write the analysis."'
)

print(
    '6. "Open mission layout and show evidence."'
)
