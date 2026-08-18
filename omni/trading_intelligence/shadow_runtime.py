from __future__ import annotations


from omni.trading_intelligence.shadow_market_bridge import (
    FyersShadowMarketBridge,
)

from omni.trading_intelligence.shadow_schema import (
    ShadowSessionConfig,
)

from omni.trading_intelligence.shadow_session import (
    ShadowTradingSession,
)


class ShadowTradingRuntime:

    MAX_SESSIONS = 20


    def __init__(
        self,
        market_bridge=None,
    ):

        self.sessions = {}

        self.market_bridge = (
            market_bridge
            or FyersShadowMarketBridge()
        )


    def create(
        self,
        symbol,
        strategy_ids,
        config=None,
    ):

        if len(
            self.sessions
        ) >= self.MAX_SESSIONS:

            raise RuntimeError(
                "Maximum shadow sessions reached."
            )


        config = (
            config
            or ShadowSessionConfig()
        )


        session = ShadowTradingSession(
            symbol,
            strategy_ids,
            config,
        )


        self.sessions[
            session.session_id
        ] = session


        return {
            "success":
                True,

            "session_id":
                session.session_id,

            "paper_only":
                True,

            "live_execution":
                False,
        }


    def get(
        self,
        session_id,
    ):

        session = self.sessions.get(
            str(
                session_id
            )
        )


        if session is None:

            raise KeyError(
                "Unknown shadow session."
            )


        return session


    def process(
        self,
        session_id,
        snapshot,
        signals,
        *,
        now=None,
    ):

        return self.get(
            session_id
        ).process(
            snapshot,
            signals,
            now=now,
        )


    def read_fyers_quote(
        self,
        symbol,
    ):

        return self.market_bridge.read_quote(
            symbol
        )


    def process_fyers(
        self,
        session_id,
        signals,
        *,
        now=None,
    ):

        session = self.get(
            session_id
        )


        snapshot = self.read_fyers_quote(
            session.symbol
        )


        return session.process(
            snapshot,
            signals,
            now=now,
        )


    def kill(
        self,
        session_id,
        reason="manual",
    ):

        return self.get(
            session_id
        ).kill(
            reason
        )


    def resume(
        self,
        session_id,
    ):

        return self.get(
            session_id
        ).resume()


    def status(
        self,
        session_id=None,
    ):

        if session_id is not None:

            return self.get(
                session_id
            ).status()


        return {
            "session_count":
                len(
                    self.sessions
                ),

            "sessions":
                tuple(
                    session.status()

                    for session
                    in self.sessions.values()
                ),

            "background_polling":
                False,

            "paper_only":
                True,

            "live_execution":
                False,
        }


shadow_trading_runtime = (
    ShadowTradingRuntime()
)
