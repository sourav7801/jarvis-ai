from __future__ import annotations

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.trading_guardrails import (
    trading_research_guard,
)


class MarketDataGateway:

    def __init__(
        self,
    ):

        self._providers = {}


    def register(
        self,
        name,
        provider,
    ):

        name = str(
            name
        ).strip().lower()


        if not name:

            raise ValueError(
                "Provider name is required."
            )


        self._providers[
            name
        ] = provider


        return provider


    def get(
        self,
        name,
    ):

        return self._providers.get(
            str(
                name
            ).strip().lower()
        )


    def ensure_fyers(
        self,
        provider=None,
    ):

        adapter = (
            FyersReadOnlyAdapter(
                provider
            )
        )


        self.register(
            "fyers",
            adapter,
        )


        return adapter


    def read(
        self,
        provider,
        capability,
        *args,
        **kwargs,
    ):

        capability = str(
            capability
        ).strip().lower()


        mapping = {
            "quote": (
                "market.read",
                "quote",
            ),

            "history": (
                "market.history",
                "history",
            ),

            "option_chain": (
                "options.read",
                "option_chain",
            ),

            "market_depth": (
                "market.depth.read",
                "market_depth",
            ),
        }


        if capability not in mapping:

            raise PermissionError(
                "Market data capability not allowlisted."
            )


        guard_capability, method_name = (
            mapping[
                capability
            ]
        )


        trading_research_guard.require(
            guard_capability
        )


        adapter = self.get(
            provider
        )


        if adapter is None:

            raise KeyError(
                "Unknown market-data provider: "
                + str(
                    provider
                )
            )


        method = getattr(
            adapter,
            method_name,
        )


        return method(
            *args,
            **kwargs
        )


market_data_gateway = (
    MarketDataGateway()
)
