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
