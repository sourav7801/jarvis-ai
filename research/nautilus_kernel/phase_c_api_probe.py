from __future__ import annotations

import importlib
import inspect
import json
import sys

from importlib.metadata import (
    version,
)

from pathlib import (
    Path,
)


OUTPUT = Path(
    sys.argv[1]
)


def safe_signature(
    value,
):

    try:

        return str(
            inspect.signature(
                value
            )
        )

    except Exception as exc:

        return (
            "<unavailable: "
            + type(exc).__name__
            + ": "
            + str(exc)
            + ">"
        )


def safe_doc(
    value,
    limit=1200,
):

    try:

        doc = (
            inspect.getdoc(
                value
            )
            or ""
        )

    except Exception:

        doc = ""


    return doc[:limit]


def describe(
    value,
):

    return {
        "module":
            getattr(
                value,
                "__module__",
                None,
            ),

        "name":
            getattr(
                value,
                "__name__",
                type(value).__name__,
            ),

        "signature":
            safe_signature(
                value
            ),

        "doc":
            safe_doc(
                value
            ),
    }


print("=" * 80)
print("NAUTILUSTRADER PHASE C EXACT API PROBE")
print("=" * 80)

print()
print(
    "NautilusTrader:",
    version(
        "nautilus_trader"
    ),
)


report = {
    "nautilus_version":
        version(
            "nautilus_trader"
        ),

    "python":
        sys.version,

    "instrument_classes":
        {},

    "test_instrument_provider":
        {},

    "execution_models":
        {},

    "enums":
        {},

    "objects":
        {},

    "safety": {
        "network_request":
            False,

        "backtest_run":
            False,

        "broker_order":
            False,

        "trading_node":
            False,
    },
}


# ============================================================
# INSTRUMENT CONSTRUCTORS
# ============================================================

print()
print("=" * 80)
print("INSTRUMENT CLASSES")
print("=" * 80)


instrument_module = importlib.import_module(
    "nautilus_trader.model.instruments"
)


for name in (
    "Equity",
    "FuturesContract",
    "OptionContract",
    "CurrencyPair",
    "IndexInstrument",
    "FuturesSpread",
    "OptionSpread",
):

    value = getattr(
        instrument_module,
        name,
        None,
    )


    if value is None:

        print(
            name,
            ": NOT FOUND",
        )

        continue


    description = describe(
        value
    )


    report[
        "instrument_classes"
    ][
        name
    ] = description


    print()
    print(
        name,
        ": FOUND",
    )

    print(
        " module:",
        description[
            "module"
        ],
    )

    print(
        " signature:",
        description[
            "signature"
        ],
    )

    if description[
        "doc"
    ]:

        print(
            " doc:",
            description[
                "doc"
            ][
                :400
            ].replace(
                "\n",
                " ",
            ),
        )


# ============================================================
# TEST INSTRUMENT PROVIDER
# ============================================================

print()
print("=" * 80)
print("TEST INSTRUMENT PROVIDER")
print("=" * 80)


provider_module = importlib.import_module(
    "nautilus_trader.test_kit.providers"
)


provider = getattr(
    provider_module,
    "TestInstrumentProvider",
)


interesting_tokens = (
    "equity",
    "future",
    "futures",
    "option",
    "commodity",
    "index",
    "crypto",
    "currency",
    "fx",
)


for name in sorted(
    dir(
        provider
    )
):

    if name.startswith(
        "_"
    ):

        continue


    if not any(
        token in name.lower()

        for token
        in interesting_tokens
    ):

        continue


    value = getattr(
        provider,
        name
    )


    if not callable(
        value
    ):

        continue


    description = describe(
        value
    )


    report[
        "test_instrument_provider"
    ][
        name
    ] = description


    print()
    print(
        name
        + description[
            "signature"
        ]
    )


# ============================================================
# EXECUTION / FILL / FEE / LATENCY MODELS
# ============================================================

print()
print("=" * 80)
print("EXECUTION MODELS")
print("=" * 80)


candidate_modules = (
    "nautilus_trader.backtest.models",
    "nautilus_trader.backtest.models.fill",
    "nautilus_trader.backtest.models.fee",
    "nautilus_trader.backtest.models.latency",
    "nautilus_trader.execution",
    "nautilus_trader.backtest.config",
)


seen = set()


for module_name in candidate_modules:

    try:

        module = importlib.import_module(
            module_name
        )

    except Exception as exc:

        print()
        print(
            module_name,
            "IMPORT FAILED:",
            type(exc).__name__,
            str(exc),
        )

        continue


    for name in sorted(
        dir(
            module
        )
    ):

        if name.startswith(
            "_"
        ):

            continue


        lower = name.lower()


        if not any(
            token in lower

            for token in (
                "fillmodel",
                "fee",
                "latency",
                "marginmodel",
            )
        ):

            continue


        value = getattr(
            module,
            name
        )


        if not (
            inspect.isclass(
                value
            )
            or callable(
                value
            )
        ):

            continue


        identity = (
            getattr(
                value,
                "__module__",
                module_name,
            ),
            getattr(
                value,
                "__name__",
                name,
            ),
        )


        if identity in seen:

            continue


        seen.add(
            identity
        )


        key = (
            identity[
                0
            ]
            + ":"
            + identity[
                1
            ]
        )


        description = describe(
            value
        )


        report[
            "execution_models"
        ][
            key
        ] = description


        print()
        print(
            key
        )

        print(
            " signature:",
            description[
                "signature"
            ],
        )


# ============================================================
# IMPORTANT ENUMS
# ============================================================

print()
print("=" * 80)
print("TRADING ENUMS")
print("=" * 80)


enum_module = importlib.import_module(
    "nautilus_trader.model.enums"
)


for name in (
    "AssetClass",
    "OptionKind",
    "AccountType",
    "OmsType",
    "BookType",
    "OrderSide",
):

    value = getattr(
        enum_module,
        name,
        None,
    )


    if value is None:

        continue


    members = []


    try:

        members = [
            str(
                item
            )

            for item in value
        ]

    except Exception:

        try:

            members = [
                name

                for name in dir(
                    value
                )

                if name.isupper()
            ]

        except Exception:

            members = []


    report[
        "enums"
    ][
        name
    ] = members


    print(
        name,
        ":",
        members,
    )


# ============================================================
# VALUE OBJECTS
# ============================================================

print()
print("=" * 80)
print("VALUE OBJECTS")
print("=" * 80)


for module_name, names in (
    (
        "nautilus_trader.model.identifiers",
        (
            "InstrumentId",
            "Symbol",
            "Venue",
        ),
    ),

    (
        "nautilus_trader.model.objects",
        (
            "Price",
            "Quantity",
            "Money",
        ),
    ),

    (
        "nautilus_trader.model.currencies",
        (
            "USD",
        ),
    ),
):

    module = importlib.import_module(
        module_name
    )


    for name in names:

        value = getattr(
            module,
            name,
            None,
        )


        if value is None:

            continue


        description = describe(
            value
        )


        report[
            "objects"
        ][
            module_name
            + ":"
            + name
        ] = description


        print()
        print(
            module_name
            + ":"
            + name
        )

        print(
            " signature:",
            description[
                "signature"
            ],
        )


# ============================================================
# SAFE PROVIDER FACTORY SMOKE TESTS
# ============================================================

print()
print("=" * 80)
print("SAFE LOCAL FACTORY SMOKE TESTS")
print("=" * 80)


factory_results = {}


def try_factory(
    name,
    *args,
    **kwargs,
):

    method = getattr(
        provider,
        name,
        None,
    )


    if not callable(
        method
    ):

        return


    try:

        instrument = method(
            *args,
            **kwargs
        )


        result = {
            "success":
                True,

            "type":
                type(
                    instrument
                ).__name__,

            "id":
                str(
                    instrument.id
                ),

            "venue":
                str(
                    instrument.id.venue
                ),
        }


    except Exception as exc:

        result = {
            "success":
                False,

            "error":
                (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                ),
        }


    factory_results[
        name
    ] = result


    print()
    print(
        name,
        "=>",
        result,
    )


if hasattr(
    provider,
    "default_fx_ccy",
):

    try_factory(
        "default_fx_ccy",
        "EUR/USD",
    )


if hasattr(
    provider,
    "equity",
):

    try_factory(
        "equity",
        symbol="AAPL",
    )


# Zero-network local provider methods only.
for possible_name in (
    "futures_contract",
    "future",
    "option_contract",
    "option",
):

    method = getattr(
        provider,
        possible_name,
        None,
    )


    if not callable(
        method
    ):

        continue


    signature = safe_signature(
        method
    )


    # Do not guess required parameters.
    # Record exact signature for Phase C2 instead.
    print()
    print(
        possible_name,
        "factory detected; invocation deferred:",
        signature,
    )


report[
    "factory_smoke_tests"
] = factory_results


# ============================================================
# BACKTEST VENUE API AGAIN, FOR MODEL WIRING
# ============================================================

print()
print("=" * 80)
print("BACKTEST VENUE MODEL WIRING")
print("=" * 80)


engine_module = importlib.import_module(
    "nautilus_trader.backtest.engine"
)


BacktestEngine = getattr(
    engine_module,
    "BacktestEngine"
)


add_venue = getattr(
    BacktestEngine,
    "add_venue"
)


report[
    "add_venue"
] = describe(
    add_venue
)


print(
    "BacktestEngine.add_venue",
    report[
        "add_venue"
    ][
        "signature"
    ],
)


# ============================================================
# REPORT
# ============================================================

OUTPUT.write_text(
    json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    ),
    encoding="utf-8",
)


print()
print("=" * 80)
print("SAFETY")
print("=" * 80)

print(
    "Network request: NO"
)

print(
    "FYERS request: NO"
)

print(
    "Backtest executed: NO"
)

print(
    "Broker order: NO"
)

print(
    "TradingNode created: NO"
)

print(
    "JARVIS production source modified: NO"
)


print()
print("=" * 80)
print("PHASE C1 SUMMARY")
print("=" * 80)

print(
    "Instrument classes:",
    sorted(
        report[
            "instrument_classes"
        ]
    ),
)

print(
    "Provider helpers:",
    sorted(
        report[
            "test_instrument_provider"
        ]
    ),
)

print(
    "Execution models found:",
    len(
        report[
            "execution_models"
        ]
    ),
)

print(
    "Report:",
    OUTPUT,
)

print()
print(
    "NAUTILUS PHASE C1 API PROBE: PASS"
)
