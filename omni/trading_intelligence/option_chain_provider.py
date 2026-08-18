from __future__ import annotations


class ReadOnlyOptionChainProvider:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider


    def snapshot(
        self,
        *args,
        **kwargs,
    ):

        method = getattr(
            self.provider,
            "snapshot",
            None,
        )


        if not callable(
            method
        ):

            raise RuntimeError(
                "Provider does not expose snapshot()."
            )


        return method(
            *args,
            **kwargs
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
            "trade",
            "execute",
            "place",
            "cancel",
            "modify",
            "buy",
            "sell",
        )


        if any(
            token in lower

            for token in blocked
        ):

            raise PermissionError(
                "Option-chain providers are read-only."
            )


        raise AttributeError(
            name
        )


class OptionChainProviderRegistry:

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
                "Provider name required."
            )


        wrapped = (
            provider

            if isinstance(
                provider,
                ReadOnlyOptionChainProvider,
            )

            else ReadOnlyOptionChainProvider(
                provider
            )
        )


        self._providers[
            name
        ] = wrapped


        return wrapped


    def get(
        self,
        name,
    ):

        return self._providers.get(
            str(
                name
            ).strip().lower()
        )


    def status(
        self,
    ):

        return {
            "providers":
                tuple(
                    sorted(
                        self._providers
                    )
                ),

            "count":
                len(
                    self._providers
                ),

            "read_only":
                True,

            "automatic_broker_write":
                False,
        }


option_chain_providers = (
    OptionChainProviderRegistry()
)
