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
