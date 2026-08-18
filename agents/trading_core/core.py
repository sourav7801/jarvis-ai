
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .analysis_engine import analyze
from .candidate_engine import confirmation_state
from .context_engine import build_context
from .data_bus import DataBus
from .edge_gate import load_edge_database, find_edge
from .live_bus import LiveBus
from .option_adapter import OptionAdapter
from .paper_engine import PaperEngine
from .policy import market_policy
from .risk_engine import position_size
from .strategy_engine import build_setups
from .signal_engine import analyze_trigger_package


class TradingCore:
    """JARVIS Trading Core V4: structure-aware, still research/paper-only."""

    def __init__(self) -> None:
        self.data = DataBus()
        self.live = LiveBus()
        self.options = OptionAdapter()
        self.paper = PaperEngine()

    def analyze_multitimeframe(
        self,
        symbol: str,
        context_bars: int = 500,
        trigger_bars: int = 1000,
    ) -> dict[str, Any]:
        # Explicitly fetch both frames so V4 can inspect candle structure.
        context = self.data.get_history(symbol, "15m", context_bars)
        trigger = self.data.get_history(symbol, "5m", trigger_bars)

        base = build_context(
            self.data,
            symbol,
            context_bars=context_bars,
            trigger_bars=trigger_bars,
        )

        if not context.get("success") or not trigger.get("success"):
            return {
                **base,
                "signal_package": None,
            }

        package = analyze_trigger_package(
            context["data"],
            trigger["data"],
            base.get("context_regime") or {},
            base.get("trigger_regime") or {},
        )

        base["signal_package"] = package

        # Stricter than V2: alignment + structure/confirmation.
        aligned = base.get("tradeable", False)
        setup_score = float(package.get("score", 0))

        base["tradeable"] = bool(aligned and setup_score >= 55)
        if not aligned:
            base["reason"] = "15m context and 5m trigger are not aligned."
        elif setup_score < 55:
            base["reason"] = (
                f"Context/trigger aligned, but confirmation score is "
                f"{setup_score:.0f}/100 (<55)."
            )
        else:
            base["reason"] = "Context, trigger and structural confirmation passed."

        return base

    def paper_candidate(
        self,
        symbol: str,
        capital: float = 100000.0,
        bars: int = 1000,
    ) -> dict[str, Any]:
        mtf = self.analyze_multitimeframe(symbol, 500, bars)

        if not mtf.get("tradeable"):
            return {
                "success": True,
                "status": "WAIT",
                "paper_ready": False,
                "stage": "SIGNAL_ENGINE",
                "reason": mtf.get("reason"),
                "multitimeframe": mtf,
                "live": self.live.stream_status(),
                "execution": {"live_orders": False, "paper_orders": False},
            }

        trigger = self.data.get_history(symbol, "5m", bars)
        regime = analyze(symbol, trigger["data"])
        setups = build_setups(symbol, trigger["data"], regime)
        setup_dicts = [asdict(s) for s in setups]

        option_state = self.options.status(symbol)
        confirmation = confirmation_state(
            mtf, setup_dicts, option_state
        )

        strategy = setup_dicts[0]["strategy"] if setup_dicts else ""
        edge_db = load_edge_database()
        edge = find_edge(symbol, strategy, edge_db) if strategy else {
            "found": False,
            "eligible": False,
            "reason": "No setup.",
        }

        if not edge.get("eligible"):
            return {
                "success": True,
                "status": "WAIT_RESEARCH_EDGE",
                "paper_ready": False,
                "stage": "RESEARCH_GATE",
                "reason": edge.get("reason"),
                "setup": setup_dicts[0] if setup_dicts else None,
                "signal_package": mtf.get("signal_package"),
                "confirmation": confirmation,
                "edge": edge,
                "live": self.live.stream_status(),
                "execution": {"live_orders": False, "paper_orders": False},
            }

        setup = setups[0]
        risk = position_size(setup, capital=capital, risk_per_trade_pct=0.005)
        ready = (
            confirmation["ready"]
            and setup.status == "PAPER_CANDIDATE"
            and risk["qty"] > 0
        )

        return {
            "success": True,
            "status": "PAPER_READY" if ready else "WAIT",
            "paper_ready": ready,
            "stage": "PAPER_GATE",
            "setup": asdict(setup),
            "risk": risk,
            "signal_package": mtf.get("signal_package"),
            "confirmation": confirmation,
            "edge": edge,
            "live": self.live.stream_status(),
            "execution": {"live_orders": False, "paper_orders": False},
        }

    def scan_priority(self, bars: int = 1000) -> dict[str, Any]:
        analyses = {}
        momentum = {"NIFTY": 50.0, "BANKNIFTY": 50.0, "SENSEX": 50.0}

        for symbol in ("NIFTY", "BANKNIFTY", "SENSEX"):
            item = self.analyze_multitimeframe(symbol, 500, bars)
            analyses[symbol] = item
            trig = item.get("trigger_regime") or {}
            momentum[symbol] = float(trig.get("momentum_score", 50.0))

        policy = market_policy(
            nifty_momentum=momentum["NIFTY"],
            banknifty_momentum=momentum["BANKNIFTY"],
            sensex_momentum=momentum["SENSEX"],
        )

        preferred = policy.get("preferred_symbol", "NIFTY")
        preferred_analysis = analyses.get(preferred)

        return {
            "success": True,
            "policy": policy,
            "analyses": analyses,
            "preferred": {
                "symbol": preferred,
                "analysis": preferred_analysis,
            },
            "live": self.live.stream_status(),
            "execution": {"live_orders": False, "paper_orders": False},
        }


trading_core = TradingCore()
