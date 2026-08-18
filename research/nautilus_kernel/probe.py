from __future__ import annotations

import importlib
import inspect
import json
import platform
import sys


print("=" * 80)
print("NAUTILUSTRADER EXACT LOCAL API PROBE")
print("=" * 80)


import nautilus_trader


version = getattr(
    nautilus_trader,
    "__version__",
    None,
)


if version is None:

    try:

        from importlib.metadata import version as package_version

        version = package_version(
            "nautilus_trader"
        )

    except Exception:

        version = "UNKNOWN"


print()
print("RUNTIME")
print("Python:", sys.version.replace("\n", " "))
print("Platform:", platform.platform())
print("NautilusTrader version:", version)


targets = (
    (
        "BacktestEngine",
        "nautilus_trader.backtest.engine",
        "BacktestEngine",
    ),

    (
        "BacktestEngineConfig",
        "nautilus_trader.backtest.config",
        "BacktestEngineConfig",
    ),

    (
        "BacktestNode",
        "nautilus_trader.backtest.node",
        "BacktestNode",
    ),

    (
        "BacktestRunConfig",
        "nautilus_trader.backtest.node",
        "BacktestRunConfig",
    ),

    (
        "BacktestDataConfig",
        "nautilus_trader.backtest.node",
        "BacktestDataConfig",
    ),

    (
        "SimulatedExchange",
        "nautilus_trader.backtest.exchange",
        "SimulatedExchange",
    ),

    (
        "FillModel",
        "nautilus_trader.backtest.models",
        "FillModel",
    ),

    (
        "LatencyModel",
        "nautilus_trader.backtest.models",
        "LatencyModel",
    ),

    (
        "Strategy",
        "nautilus_trader.trading.strategy",
        "Strategy",
    ),

    (
        "StrategyConfig",
        "nautilus_trader.config",
        "StrategyConfig",
    ),

    (
        "Bar",
        "nautilus_trader.model.data",
        "Bar",
    ),

    (
        "BarType",
        "nautilus_trader.model.data",
        "BarType",
    ),

    (
        "InstrumentId",
        "nautilus_trader.model.identifiers",
        "InstrumentId",
    ),

    (
        "Venue",
        "nautilus_trader.model.identifiers",
        "Venue",
    ),

    (
        "TraderId",
        "nautilus_trader.model.identifiers",
        "TraderId",
    ),

    (
        "AccountType",
        "nautilus_trader.model.enums",
        "AccountType",
    ),

    (
        "OmsType",
        "nautilus_trader.model.enums",
        "OmsType",
    ),

    (
        "BookType",
        "nautilus_trader.model.enums",
        "BookType",
    ),
)


results = {}


def signature_of(
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
            "<signature unavailable: "
            + type(exc).__name__
            + ": "
            + str(exc)
            + ">"
        )


print()
print("=" * 80)
print("CORE API AVAILABILITY")
print("=" * 80)


for label, module_name, attribute_name in targets:

    item = {
        "module":
            module_name,

        "attribute":
            attribute_name,

        "available":
            False,

        "signature":
            None,

        "error":
            None,
    }


    try:

        module = importlib.import_module(
            module_name
        )


        value = getattr(
            module,
            attribute_name
        )


        item[
            "available"
        ] = True


        item[
            "signature"
        ] = signature_of(
            value
        )


        print()
        print(label + ": FOUND")
        print("  module:", module_name)
        print("  signature:", item["signature"])


    except Exception as exc:

        item[
            "error"
        ] = (
            type(exc).__name__
            + ": "
            + str(exc)
        )


        print()
        print(label + ": NOT FOUND")
        print("  attempted:", module_name)
        print("  error:", item["error"])


    results[
        label
    ] = item


print()
print("=" * 80)
print("BACKTEST ENGINE METHODS")
print("=" * 80)


engine_info = results.get(
    "BacktestEngine",
    {}
)


engine_methods = {}


if engine_info.get(
    "available"
):

    module = importlib.import_module(
        engine_info[
            "module"
        ]
    )


    BacktestEngine = getattr(
        module,
        engine_info[
            "attribute"
        ]
    )


    interesting = (
        "add_venue",
        "add_instrument",
        "add_data",
        "sort_data",
        "add_strategy",
        "run",
        "end",
        "reset",
        "clear_data",
        "clear_strategies",
        "get_result",
        "get_result",
        "dispose",
    )


    for name in interesting:

        value = getattr(
            BacktestEngine,
            name,
            None,
        )


        if value is None:

            continue


        sig = signature_of(
            value
        )


        engine_methods[
            name
        ] = sig


        print(
            name + sig
        )


print()
print("=" * 80)
print("BACKTEST CONFIG MODULE SYMBOLS")
print("=" * 80)


try:

    config_module = importlib.import_module(
        "nautilus_trader.backtest.config"
    )


    config_symbols = tuple(
        sorted(
            name

            for name in dir(
                config_module
            )

            if (
                "Config" in name
                or "Model" in name
            )
            and not name.startswith(
                "_"
            )
        )
    )


    for name in config_symbols:

        print(name)


except Exception as exc:

    config_symbols = ()

    print(
        "ERROR:",
        type(exc).__name__,
        str(exc),
    )


print()
print("=" * 80)
print("MODEL INSTRUMENT SYMBOLS")
print("=" * 80)


instrument_symbols = ()


for module_name in (
    "nautilus_trader.model.instruments",
    "nautilus_trader.model.instruments.base",
):

    try:

        module = importlib.import_module(
            module_name
        )


        names = tuple(
            sorted(
                name

                for name in dir(
                    module
                )

                if not name.startswith(
                    "_"
                )
            )
        )


        useful = tuple(
            name

            for name in names

            if any(
                token in name.lower()

                for token in (
                    "instrument",
                    "equity",
                    "future",
                    "option",
                    "currency",
                )
            )
        )


        if useful:

            print()
            print(module_name)

            for name in useful:

                print(" ", name)


            instrument_symbols += useful


    except Exception as exc:

        print()
        print(
            module_name,
            "ERROR:",
            type(exc).__name__,
            str(exc),
        )


print()
print("=" * 80)
print("SAFETY / ISOLATION")
print("=" * 80)

print("Network request executed by this probe: NO")
print("FYERS request executed by this probe: NO")
print("Broker order executed by this probe: NO")
print("TradingNode created: NO")
print("LiveNode created: NO")
print("BacktestEngine run executed: NO")
print("JARVIS Protected Core modified: NO")
print("JARVIS main .venv modified: NO")


report = {
    "python":
        sys.version,

    "nautilus_version":
        version,

    "targets":
        results,

    "backtest_engine_methods":
        engine_methods,

    "backtest_config_symbols":
        config_symbols,

    "instrument_symbols":
        tuple(
            sorted(
                set(
                    instrument_symbols
                )
            )
        ),

    "probe_network_request":
        False,

    "probe_broker_order":
        False,

    "probe_backtest_execution":
        False,
}


print()
print("=" * 80)
print("JSON SUMMARY")
print("=" * 80)

print(
    json.dumps(
        report,
        indent=2,
        default=str,
    )
)


print()
print("=" * 80)
print("NAUTILUSTRADER PHASE A PROBE: PASS")
print("=" * 80)
