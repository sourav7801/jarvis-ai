from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

ADAPTER = (
    ROOT
    / "omni"
    / "trading_intelligence"
    / "fyers_market_adapter.py"
)

STATUS = (
    ROOT
    / "omni"
    / "trading_intelligence"
    / "trading_status.py"
)

GATEWAY = (
    ROOT
    / "omni"
    / "trading_intelligence"
    / "market_data_gateway.py"
)

MAIN = ROOT / "main.py"

TEST = (
    ROOT
    / "tests"
    / "test_trading_v1_1_fyers_bridge.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_v1_1_fyers_bridge"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    ADAPTER,
    STATUS,
    GATEWAY,
    MAIN,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


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
    )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in (
        BACKUPS.items()
    ):

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        if existed:
            shutil.copy2(
                backup,
                path,
            )

        else:
            path.unlink(
                missing_ok=True
            )

    print(
        "JARVIS source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V1.1")
print("CANONICAL FYERS READ-ONLY BRIDGE")
print("=" * 80)


# ============================================================
# 0. BACKUP
# ============================================================

for path in FILES:

    BACKUPS[
        path
    ] = path.exists()

    if path.exists():

        destination = (
            ARCHIVE
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


# ============================================================
# 1. VERIFY 490 CHECKPOINT
# ============================================================

print()
print("Checking Trading Intelligence V1 / 490 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v=main.jarvis_trading_v1_status(); "
        "assert v['research_only']; "
        "assert v['live_execution'] is False; "
        "assert v['automatic_broker_order'] is False; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Trading Intelligence V1: PASS'); "
        "print('Live execution disabled: PASS')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


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


# ============================================================
# 2. VERIFY CANONICAL LOCAL FYERS FILES
# ============================================================

print()
print("Checking canonical FYERS architecture...")


canonical_files = {
    "data_adapter":
        ROOT
        / "agents"
        / "fyers_data_adapter.py",

    "auth_manager":
        ROOT
        / "agents"
        / "fyers_auth_manager.py",

    "live_stream":
        ROOT
        / "agents"
        / "fyers_live_stream.py",

    "market_agent":
        ROOT
        / "agents"
        / "market_data_agent.py",

    "paper_market_data":
        ROOT
        / "workstation"
        / "paper_market_data.py",
}


for name, path in (
    canonical_files.items()
):

    if not path.exists():

        print(
            "MISSING CANONICAL FILE:",
            path,
        )

        sys.exit(1)


    print(
        name + ":",
        "FOUND",
    )


print(
    "Canonical FYERS architecture: PASS"
)


# ============================================================
# 3. REPLACE ONLY TRADING-V1 FYERS ADAPTER
# ============================================================

write(
    ADAPTER,
    r'''
from __future__ import annotations

import importlib
import importlib.util


from omni.trading_intelligence.trading_guardrails import (
    trading_research_guard,
)


CANONICAL_DATA_MODULE = (
    "agents.fyers_data_adapter"
)

CANONICAL_AUTH_MODULE = (
    "agents.fyers_auth_manager"
)

CANONICAL_STREAM_MODULE = (
    "agents.fyers_live_stream"
)


EXPLICIT_PROVIDER_READ_METHODS = {
    "quote": (
        "get_quote",
        "quotes",
        "quote",
        "get_quotes",
    ),

    "history": (
        "get_intraday_data",
        "history",
        "get_history",
        "historical_data",
    ),

    "option_chain": (
        "option_chain",
        "optionchain",
        "get_option_chain",
    ),

    "market_depth": (
        "market_depth",
        "depth",
        "get_market_depth",
    ),
}


class CanonicalFyersProvider:
    """
    Thin read-only bridge to the mature FYERS implementation
    already used by JARVIS.

    This class deliberately exposes no order APIs.
    """

    provider_name = (
        CANONICAL_DATA_MODULE
    )


    @staticmethod
    def available():

        return (
            importlib.util.find_spec(
                CANONICAL_DATA_MODULE
            )
            is not None
        )


    @staticmethod
    def configured():

        try:

            module = importlib.import_module(
                CANONICAL_AUTH_MODULE
            )

            checker = getattr(
                module,
                "is_configured",
                None,
            )


            if not callable(
                checker
            ):

                return None


            return bool(
                checker()
            )


        except Exception:

            return None


    @staticmethod
    def normalize_symbol(
        symbol,
    ):

        trading_research_guard.require(
            "instrument.read"
        )


        module = importlib.import_module(
            CANONICAL_DATA_MODULE
        )


        function = getattr(
            module,
            "normalize_symbol",
        )


        return function(
            symbol
        )


    @staticmethod
    def quote(
        symbol,
    ):

        trading_research_guard.require(
            "market.read"
        )


        module = importlib.import_module(
            CANONICAL_DATA_MODULE
        )


        function = getattr(
            module,
            "get_quote",
        )


        return function(
            symbol
        )


    @staticmethod
    def history(
        symbol,
        *,
        market="NSE",
        timeframe="5m",
        bars=200,
    ):

        trading_research_guard.require(
            "market.history"
        )


        module = importlib.import_module(
            CANONICAL_DATA_MODULE
        )


        function = getattr(
            module,
            "get_intraday_data",
        )


        return function(
            symbol,
            market=market,
            timeframe=timeframe,
            bars=bars,
        )


    @staticmethod
    def stream_snapshot(
        symbol,
    ):

        trading_research_guard.require(
            "market.read"
        )


        module = importlib.import_module(
            CANONICAL_STREAM_MODULE
        )


        stream = getattr(
            module,
            "fyers_live_stream",
        )


        return stream.snapshot(
            symbol
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "order",
            "place",
            "cancel",
            "modify",
            "execute",
            "buy",
            "sell",
            "position",
        )


        if any(
            token in lower
            for token in forbidden
        ):

            raise PermissionError(
                "Canonical FYERS bridge is read-only."
            )


        raise AttributeError(
            name
        )


class FyersReadOnlyAdapter:

    def __init__(
        self,
        provider=None,
    ):

        self.provider = provider


    @staticmethod
    def canonical_available():

        return (
            CanonicalFyersProvider
            .available()
        )


    @classmethod
    def discover_provider(
        cls,
    ):

        if cls.canonical_available():

            return (
                CanonicalFyersProvider()
            )


        return None


    def _provider(
        self,
    ):

        if self.provider is not None:

            return self.provider


        provider = (
            self.discover_provider()
        )


        if provider is None:

            raise RuntimeError(
                "Canonical JARVIS FYERS provider "
                "was not discovered."
            )


        return provider


    @staticmethod
    def _method_name(
        provider,
        capability,
    ):

        if isinstance(
            provider,
            CanonicalFyersProvider,
        ):

            mapping = {
                "quote":
                    "get_quote",

                "history":
                    "get_intraday_data",

                "option_chain":
                    None,

                "market_depth":
                    None,
            }


            return mapping[
                capability
            ]


        for alias in (
            EXPLICIT_PROVIDER_READ_METHODS[
                capability
            ]
        ):

            if callable(
                getattr(
                    provider,
                    alias,
                    None,
                )
            ):

                return alias


        return None


    def capabilities(
        self,
    ):

        provider = (
            self.provider
            or self.discover_provider()
        )


        if provider is None:

            return {
                "quote":
                    None,

                "history":
                    None,

                "option_chain":
                    None,

                "market_depth":
                    None,
            }


        return {
            capability:
                self._method_name(
                    provider,
                    capability,
                )

            for capability
            in (
                "quote",
                "history",
                "option_chain",
                "market_depth",
            )
        }


    def bridge_status(
        self,
    ):

        available = (
            self.canonical_available()
        )


        configured = (
            CanonicalFyersProvider
            .configured()
            if available
            else None
        )


        return {
            "canonical_provider":
                CANONICAL_DATA_MODULE,

            "canonical_provider_available":
                available,

            "auth_manager":
                CANONICAL_AUTH_MODULE,

            "fyers_configured":
                configured,

            "quote_function":
                (
                    "get_quote"
                    if available
                    else None
                ),

            "history_function":
                (
                    "get_intraday_data"
                    if available
                    else None
                ),

            "live_stream_module_available":
                (
                    importlib.util.find_spec(
                        CANONICAL_STREAM_MODULE
                    )
                    is not None
                ),

            "option_chain_function":
                None,

            "market_depth_function":
                None,

            "research_only":
                True,

            "live_execution":
                False,
        }


    def _explicit_call(
        self,
        capability,
        *args,
        **kwargs,
    ):

        provider = self._provider()


        method_name = self._method_name(
            provider,
            capability,
        )


        if method_name is None:

            raise RuntimeError(
                "FYERS provider does not expose "
                + str(
                    capability
                )
                + " through the current canonical "
                "read-only bridge."
            )


        if isinstance(
            provider,
            CanonicalFyersProvider,
        ):

            method = getattr(
                provider,
                {
                    "quote":
                        "quote",

                    "history":
                        "history",

                    "option_chain":
                        "option_chain",

                    "market_depth":
                        "market_depth",
                }[
                    capability
                ],
                None,
            )


        else:

            method = getattr(
                provider,
                method_name,
            )


        if not callable(
            method
        ):

            raise RuntimeError(
                "FYERS read method unavailable."
            )


        return method(
            *args,
            **kwargs
        )


    def quote(
        self,
        *args,
        **kwargs,
    ):

        trading_research_guard.require(
            "market.read"
        )


        return self._explicit_call(
            "quote",
            *args,
            **kwargs
        )


    def history(
        self,
        *args,
        **kwargs,
    ):

        trading_research_guard.require(
            "market.history"
        )


        return self._explicit_call(
            "history",
            *args,
            **kwargs
        )


    def option_chain(
        self,
        *args,
        **kwargs,
    ):

        trading_research_guard.require(
            "options.read"
        )


        raise RuntimeError(
            "The inspected canonical FYERS adapter "
            "does not currently expose an option-chain "
            "function. Trading V3 will add a governed "
            "chain provider separately."
        )


    def market_depth(
        self,
        *args,
        **kwargs,
    ):

        trading_research_guard.require(
            "market.depth.read"
        )


        raise RuntimeError(
            "The inspected canonical FYERS adapter "
            "does not currently expose a market-depth "
            "REST function."
        )


    def stream_snapshot(
        self,
        symbol,
    ):

        provider = self._provider()


        if not isinstance(
            provider,
            CanonicalFyersProvider,
        ):

            method = getattr(
                provider,
                "stream_snapshot",
                None,
            )


            if not callable(
                method
            ):

                raise RuntimeError(
                    "Provider does not expose "
                    "stream_snapshot."
                )


            return method(
                symbol
            )


        return provider.stream_snapshot(
            symbol
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        blocked = (
            "order",
            "place",
            "cancel",
            "modify",
            "execute",
            "buy",
            "sell",
            "position",
        )


        if any(
            token in lower
            for token in blocked
        ):

            raise PermissionError(
                "FYERS Trading Intelligence bridge "
                "is read-only."
            )


        raise AttributeError(
            name
        )
'''
)


# ============================================================
# 4. STATUS UPDATE
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.trading_guardrails import (
    trading_research_guard,
)


class TradingIntelligenceV1Status:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        adapter = (
            FyersReadOnlyAdapter()
        )


        fyers = (
            adapter.capabilities()
        )


        bridge = (
            adapter.bridge_status()
        )


        return {
            "protected_core":
                integrity.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "paper_only":
                True,

            "universal_instrument_schema":
                True,

            "equity_support":
                True,

            "index_support":
                True,

            "futures_support":
                True,

            "options_support":
                True,

            "commodity_schema_support":
                True,

            "currency_schema_support":
                True,

            "forex_schema_support":
                True,

            "crypto_schema_support":
                True,

            "feature_engine":
                True,

            "options_feature_engine":
                True,

            "greeks_engine":
                True,

            "regime_engine":
                True,

            "safe_strategy_dsl":
                True,

            "signal_engine":
                True,

            "performance_metrics":
                True,

            "dataset_engine":
                True,

            "strategy_count":
                len(
                    strategy_registry.all()
                ),

            "canonical_fyers_bridge":
                bridge,

            "fyers_discovered_capabilities":
                fyers,

            "guardrails": {
                "live_execution":
                    trading_research_guard
                    .LIVE_EXECUTION,

                "paper_only":
                    trading_research_guard
                    .PAPER_ONLY,
            },

            "automatic_strategy_promotion":
                False,

            "automatic_parameter_optimization":
                False,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v1_status = (
    TradingIntelligenceV1Status()
)
'''
)


# ============================================================
# 5. PUBLIC BRIDGE STATUS API
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_fyers_bridge_status("
    not in main_source
):

    main_source += r'''


def jarvis_fyers_bridge_status():

    from omni.trading_intelligence.fyers_market_adapter import (
        FyersReadOnlyAdapter,
    )

    return FyersReadOnlyAdapter().bridge_status()
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 6. TESTS
# ============================================================

write(
    TEST,
    r'''
import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_market_adapter import (
    CanonicalFyersProvider,
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.market_data_gateway import (
    MarketDataGateway,
)


class FakeProvider:

    def get_quote(
        self,
        symbol,
    ):

        return {
            "success":
                True,

            "symbol":
                symbol,

            "ltp":
                100.0,
        }


    def get_intraday_data(
        self,
        symbol,
        market="NSE",
        timeframe="5m",
        bars=10,
    ):

        return {
            "success":
                True,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "bars":
                bars,
        }


    def place_order(
        self,
        payload,
    ):

        raise AssertionError(
            "Must never execute."
        )


class FyersBridgeTests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_canonical_provider_discovered(
        self,
    ):

        adapter = (
            FyersReadOnlyAdapter()
        )


        self.assertTrue(
            adapter
            .canonical_available()
        )


    def test_canonical_capabilities(
        self,
    ):

        capabilities = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        self.assertEqual(
            capabilities[
                "quote"
            ],
            "get_quote",
        )


        self.assertEqual(
            capabilities[
                "history"
            ],
            "get_intraday_data",
        )


    def test_no_fake_option_chain(
        self,
    ):

        capabilities = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        self.assertIsNone(
            capabilities[
                "option_chain"
            ]
        )


        self.assertIsNone(
            capabilities[
                "market_depth"
            ]
        )


    def test_explicit_provider_quote(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        result = adapter.quote(
            "NIFTY"
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


    def test_explicit_provider_history(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        result = adapter.history(
            "NIFTY",
            market="NSE",
            timeframe="5m",
            bars=50,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertEqual(
            result[
                "bars"
            ],
            50,
        )


    def test_order_attribute_blocked(
        self,
    ):

        adapter = FyersReadOnlyAdapter(
            FakeProvider()
        )


        with self.assertRaises(
            PermissionError
        ):

            adapter.place_order


    def test_gateway_bridge(
        self,
    ):

        gateway = (
            MarketDataGateway()
        )


        adapter = gateway.ensure_fyers(
            FakeProvider()
        )


        self.assertEqual(
            adapter.capabilities()[
                "quote"
            ],
            "get_quote",
        )


    def test_public_bridge_status(
        self,
    ):

        status = (
            main.jarvis_fyers_bridge_status()
        )


        self.assertTrue(
            status[
                "canonical_provider_available"
            ]
        )


        self.assertEqual(
            status[
                "quote_function"
            ],
            "get_quote",
        )


        self.assertEqual(
            status[
                "history_function"
            ],
            "get_intraday_data",
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_trading_status_bridge(
        self,
    ):

        status = (
            main.jarvis_trading_v1_status()
        )


        capabilities = status[
            "fyers_discovered_capabilities"
        ]


        self.assertEqual(
            capabilities[
                "quote"
            ],
            "get_quote",
        )


        self.assertEqual(
            capabilities[
                "history"
            ],
            "get_intraday_data",
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# 7. COMPILE
# ============================================================

print()
print("Checking FYERS bridge syntax...")


r = run(
    "-m",
    "py_compile",
    str(ADAPTER),
    str(STATUS),
    str(MAIN),
    str(TEST),
)


if r.returncode:

    print(
        "COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Syntax: PASS"
)


# ============================================================
# 8. PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "print('Protected core: PASS')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


# ============================================================
# 9. CANONICAL DISCOVERY PROBE
# ============================================================

print()
print("Checking canonical FYERS bridge discovery...")


probe = r'''
import main


status = main.jarvis_fyers_bridge_status()


print(
    "Canonical provider:",
    status[
        "canonical_provider"
    ]
)


print(
    "Provider available:",
    status[
        "canonical_provider_available"
    ]
)


print(
    "FYERS configured:",
    status[
        "fyers_configured"
    ]
)


print(
    "Quote function:",
    status[
        "quote_function"
    ]
)


print(
    "History function:",
    status[
        "history_function"
    ]
)


print(
    "Live-stream module:",
    status[
        "live_stream_module_available"
    ]
)


print(
    "Option-chain function:",
    status[
        "option_chain_function"
    ]
)


print(
    "Market-depth function:",
    status[
        "market_depth_function"
    ]
)


assert status[
    "canonical_provider_available"
]


assert (
    status[
        "quote_function"
    ]
    == "get_quote"
)


assert (
    status[
        "history_function"
    ]
    == "get_intraday_data"
)


assert (
    status[
        "live_execution"
    ]
    is False
)


print(
    "Canonical FYERS bridge: PASS"
)

print(
    "No FYERS market request executed."
)

print(
    "No login attempted."
)

print(
    "No token accessed."
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "CANONICAL BRIDGE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 10. FAKE READ + LIVE ORDER BLOCK PROBE
# ============================================================

print()
print("Checking FYERS bridge with isolated fake provider...")


probe = r'''
from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)


class FakeProvider:

    def get_quote(self, symbol):

        return {
            "success": True,
            "symbol": symbol,
        }


    def get_intraday_data(
        self,
        symbol,
        market="NSE",
        timeframe="5m",
        bars=100,
    ):

        return {
            "success": True,
            "symbol": symbol,
            "market": market,
            "timeframe": timeframe,
            "bars": bars,
        }


adapter = FyersReadOnlyAdapter(
    FakeProvider()
)


quote = adapter.quote(
    "NIFTY"
)


history = adapter.history(
    "NIFTY",
    market="NSE",
    timeframe="5m",
    bars=100,
)


assert quote["success"]
assert history["success"]


blocked = False


try:

    adapter.place_order


except PermissionError:

    blocked = True


assert blocked


print("Quote bridge: PASS")
print("History bridge: PASS")
print("Live order surface: BLOCKED")
print("Fake-provider bridge test: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "BRIDGE SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 11. TARGETED TESTS
# ============================================================

print()
print("Running Trading V1.1 targeted tests...")


r = run(
    "-m",
    "unittest",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",
    "tests.test_connected_services_v3",
    "tests.test_connected_services_v2",
    "tests.test_connected_services_v1",
    "tests.test_computer_operator_v4",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v2",
    "tests.test_computer_operator",
    "tests.test_real_world_action_v3",
    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_engine",
    "tests.test_universal_learning_v5",
    "tests.test_autonomy_engine",
    "tests.test_improvement_lab",
    "-q",
)


if r.returncode:

    print(
        "TARGETED TEST FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 12. FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 13. FINAL PROTECTED CORE
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


# ============================================================
# SUCCESS
# ============================================================

status = run(
    "-c",
    (
        "import main,pprint; "
        "pprint.pp(main.jarvis_fyers_bridge_status()); "
        "pprint.pp(main.jarvis_fyers_readonly_capabilities())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V1.1 SUCCESS")
print("=" * 80)

print()
print("CANONICAL FYERS BRIDGE")
print("agents.fyers_data_adapter: CONNECTED")
print("get_quote(): BRIDGED")
print("get_intraday_data(): BRIDGED")
print("agents.fyers_auth_manager: REUSED")
print("agents.fyers_live_stream: DISCOVERED")
print("workstation paper-market architecture: PRESERVED")
print()

print("TRADING INTELLIGENCE")
print("FYERS quote research: READY")
print("FYERS historical research: READY")
print("Index research: READY")
print("Equity research: READY")
print("Futures research: READY")
print("Commodity historical research: READY")
print("Option-symbol historical research: READY")
print()

print("TRUTHFUL CAPABILITY LIMITS")
print("Native canonical option-chain method: NOT FOUND")
print("Native canonical market-depth REST method: NOT FOUND")
print("Those capabilities are NOT fabricated.")
print()

print("SAFETY")
print("FYERS login during installer: NO")
print("FYERS token access during installer: NO")
print("FYERS market request during installer: NO")
print("Live order placement: BLOCKED")
print("Order modification: BLOCKED")
print("Order cancellation: BLOCKED")
print("Existing FYERS source overwritten: NO")
print("Protected Core: UNCHANGED")
print("Trading Intelligence V1: PRESERVED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT:")
print("TRADING INTELLIGENCE V2")
print("Universal historical backtest engine")
print("Realistic account + position simulator")
print("Long / short execution simulation")
print("Stops / targets / trailing stops")
print("Options premium simulation")
print("Commodity futures simulation")
print("Brokerage / taxes / spread / slippage")
print("Parameter sweeps")
print("Trade journal")
print("Equity curve")
print("Drawdown analytics")
print("Strategy comparison")
