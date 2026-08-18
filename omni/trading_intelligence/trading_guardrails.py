from __future__ import annotations


ALLOWED_CAPABILITIES = {
    "market.read",
    "market.history",
    "market.depth.read",
    "options.read",
    "options.analyze",
    "instrument.read",
    "feature.compute",
    "regime.classify",
    "strategy.validate",
    "strategy.evaluate",
    "strategy.compare",
    "backtest.run",
    "simulation.run",
    "risk.analyze",
    "portfolio.analyze",
    "paper.simulate",
}


BLOCKED_CAPABILITIES = {
    "order.place",
    "order.modify",
    "order.cancel",
    "broker.order.place",
    "broker.order.modify",
    "broker.order.cancel",
    "trade.execute",
    "trade.live.execute",
    "trading.live.execute",
    "position.live.close",
    "position.live.modify",
    "broker.write",
    "live.order",
}


class TradingResearchGuard:

    LIVE_EXECUTION = False

    PAPER_ONLY = True


    def check(
        self,
        capability,
    ):

        capability = str(
            capability
        ).strip().lower()


        if (
            capability
            in BLOCKED_CAPABILITIES
            or capability.startswith(
                "broker.write."
            )
            or capability.startswith(
                "order."
            )
            or capability.startswith(
                "trade.live."
            )
            or capability.startswith(
                "trading.live."
            )
        ):

            return {
                "allowed":
                    False,

                "capability":
                    capability,

                "reason":
                    "Live trading execution is disabled.",
            }


        if capability in ALLOWED_CAPABILITIES:

            return {
                "allowed":
                    True,

                "capability":
                    capability,

                "reason":
                    "Research/read/simulation capability.",
            }


        return {
            "allowed":
                False,

            "capability":
                capability,

            "reason":
                "Capability is not explicitly allowlisted.",
        }


    def require(
        self,
        capability,
    ):

        result = self.check(
            capability
        )


        if not result[
            "allowed"
        ]:

            raise PermissionError(
                result[
                    "reason"
                ]
                + " Capability: "
                + str(
                    capability
                )
            )


        return True


trading_research_guard = (
    TradingResearchGuard()
)
