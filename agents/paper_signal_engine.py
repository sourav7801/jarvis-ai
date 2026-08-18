# ============================================================
# JARVIS PAPER SIGNAL ENGINE
# V1
# ============================================================
#
# Purpose:
#   Convert validated research + current market analysis into
#   a paper-trading candidate.
#
# Flow:
#
#   Market Data
#        ↓
#   Strategy Signal
#        ↓
#   Edge Validation
#        ↓
#   Risk Checks
#        ↓
#   PAPER SIGNAL
#        ↓
#   Journal
#
# IMPORTANT:
#   This module NEVER places a live order.
#
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime
import json
import uuid
import math

import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

SIGNAL_PATH = (
    BASE_PATH
    / "paper_signals.json"
)


# ============================================================
# STRATEGY REGISTRY
# ============================================================

STRATEGY_MODULES = {

    "MEAN_REVERSION":
        "agents.mean_reversion_strategy",

    "TREND_FOLLOWING":
        "agents.trend_following_strategy",

    "BREAKOUT":
        "agents.breakout_strategy",

    "MOMENTUM":
        "agents.momentum_strategy",

}


# ============================================================
# ENGINE
# ============================================================

class PaperSignalEngine:

    def __init__(
        self,
        starting_capital: float = 1_000_000.0,
        max_risk_per_trade_percent: float = 1.0,
        min_research_score: float = 70.0,
        min_confidence: float = 60.0,
    ):

        self.starting_capital = float(
            starting_capital
        )

        self.max_risk_per_trade_percent = float(
            max_risk_per_trade_percent
        )

        self.min_research_score = float(
            min_research_score
        )

        self.min_confidence = float(
            min_confidence
        )

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # SAFE NUMBER
    # ========================================================

    def number(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            value = float(value)

            if math.isnan(value):
                return default

            if math.isinf(value):
                return default

            return value

        except Exception:

            return default

    # ========================================================
    # LOAD JOURNAL
    # ========================================================

    def load_signals(
        self,
    ) -> List[
        Dict[str, Any]
    ]:

        if not SIGNAL_PATH.exists():

            return []

        try:

            raw = SIGNAL_PATH.read_text(
                encoding="utf-8"
            )

            if not raw.strip():

                return []

            data = json.loads(
                raw
            )

            if isinstance(
                data,
                list,
            ):

                return data

            return []

        except Exception as exc:

            print(
                "JARVIS PAPER SIGNAL DEBUG > "
                f"Could not load signals: {exc}"
            )

            return []

    # ========================================================
    # SAVE JOURNAL
    # ========================================================

    def save_signals(
        self,
        signals: List[
            Dict[str, Any]
        ],
    ) -> bool:

        try:

            SIGNAL_PATH.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            SIGNAL_PATH.write_text(

                json.dumps(
                    signals,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                ),

                encoding="utf-8",

            )

            return True

        except Exception as exc:

            print(
                "JARVIS PAPER SIGNAL DEBUG > "
                f"Could not save signals: {exc}"
            )

            return False

    # ========================================================
    # LOAD STRATEGY
    # ========================================================

    def load_strategy(
        self,
        strategy_name: str,
    ):

        strategy_name = (
            str(
                strategy_name
            )
            .upper()
            .strip()
        )

        module_name = (
            STRATEGY_MODULES.get(
                strategy_name
            )
        )

        if not module_name:

            raise ValueError(
                f"Strategy not registered: {strategy_name}"
            )

        import importlib

        module = (
            importlib.import_module(
                module_name
            )
        )

        candidates = [

            f"{strategy_name.lower()}_strategy",

            "mean_reversion_strategy",

            "trend_following_strategy",

            "breakout_strategy",

            "momentum_strategy",

        ]

        for name in candidates:

            if hasattr(
                module,
                name,
            ):

                value = getattr(
                    module,
                    name,
                )

                if hasattr(
                    value,
                    "signal",
                ):

                    return value

        for name in dir(module):

            if name.startswith("_"):
                continue

            try:

                value = getattr(
                    module,
                    name,
                )

            except Exception:

                continue

            if hasattr(
                value,
                "signal",
            ):

                return value

        raise ImportError(
            (
                f"Could not find strategy object "
                f"inside {module_name}."
            )
        )

    # ========================================================
    # LOAD EDGE
    # ========================================================

    def load_edge(
        self,
        strategy: str,
        symbol: str,
        market: str,
        timeframe: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        try:

            from agents.research_edge_engine import (
                research_edge_engine,
            )

            return (
                research_edge_engine.get_edge(

                    strategy=strategy,

                    symbol=symbol,

                    market=market,

                    timeframe=timeframe,

                )
            )

        except Exception as exc:

            print(
                "JARVIS PAPER SIGNAL DEBUG > "
                f"Could not load research edge: {exc}"
            )

            return None

    # ========================================================
    # LOAD AGGREGATE VALIDATION
    # ========================================================

    def load_aggregate_validation(
        self,
        strategy: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        try:

            from agents.edge_validation_engine import (
                edge_validation_engine,
            )

            loaded = (
                edge_validation_engine
                .load_matrix_file()
            )

            if not loaded.get(
                "success",
                False,
            ):

                return None

            report = (
                edge_validation_engine.validate_matrix(
                    loaded["data"]
                )
            )

            return (
                report
                .get(
                    "evaluations",
                    {}
                )
                .get(
                    str(
                        strategy
                    )
                    .upper()
                    .strip(),
                )
            )

        except Exception as exc:

            print(
                "JARVIS PAPER SIGNAL DEBUG > "
                f"Aggregate validation unavailable: {exc}"
            )

            return None

    # ========================================================
    # RISK
    # ========================================================

    def risk_check(
        self,
        entry: float,
        stop_loss: float,
        capital: float,
    ) -> Dict[str, Any]:

        entry = self.number(
            entry
        )

        stop_loss = self.number(
            stop_loss
        )

        capital = self.number(
            capital
        )

        if entry <= 0:

            return {

                "approved":
                    False,

                "reason":
                    "Invalid entry price.",

            }

        if stop_loss <= 0:

            return {

                "approved":
                    False,

                "reason":
                    "Invalid stop loss.",

            }

        risk_per_unit = abs(
            entry
            - stop_loss
        )

        max_risk_amount = (
            capital
            *
            self.max_risk_per_trade_percent
            /
            100.0
        )

        if risk_per_unit <= 0:

            return {

                "approved":
                    False,

                "reason":
                    "Zero risk distance.",

            }

        quantity = (
            max_risk_amount
            /
            risk_per_unit
        )

        quantity = max(
            0.0,
            quantity,
        )

        risk_amount = (
            quantity
            *
            risk_per_unit
        )

        return {

            "approved":
                quantity > 0,

            "quantity":
                quantity,

            "risk_per_unit":
                risk_per_unit,

            "risk_amount":
                risk_amount,

            "max_risk_amount":
                max_risk_amount,

        }

    # ========================================================
    # CREATE PAPER SIGNAL
    # ========================================================

    def create_signal(
        self,
        df: pd.DataFrame,
        strategy: str,
        symbol: str,
        market: str,
        timeframe: str,
        capital: Optional[float] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        strategy = (
            str(
                strategy
            )
            .upper()
            .strip()
        )

        symbol = (
            str(
                symbol
            )
            .upper()
            .strip()
        )

        market = (
            str(
                market
            )
            .upper()
            .strip()
        )

        timeframe = (
            str(
                timeframe
            )
            .lower()
            .strip()
        )

        account_capital = (
            self.starting_capital
            if capital is None
            else float(capital)
        )

        # ====================================================
        # CURRENT RESEARCH CELL
        # ====================================================

        edge = self.load_edge(

            strategy=strategy,

            symbol=symbol,

            market=market,

            timeframe=timeframe,

        )

        # ====================================================
        # AGGREGATE VALIDATION
        # ====================================================

        aggregate = (
            self.load_aggregate_validation(
                strategy
            )
        )

        # ====================================================
        # HARD RESEARCH GATE
        # ====================================================

        if aggregate is None:

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "No aggregate research validation "
                        "is available."
                    ),

                "research_gate":
                    False,

                "paper_signal":
                    None,

            }

        aggregate_validated = bool(
            aggregate.get(
                "validated",
                False,
            )
        )

        aggregate_score = (
            self.number(
                aggregate.get(
                    "aggregate_score",
                    0.0,
                )
            )
        )

        if not aggregate_validated:

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Strategy does not have a "
                        "robust aggregate research edge."
                    ),

                "aggregate_research_score":
                    aggregate_score,

                "research_gate":
                    False,

                "paper_signal":
                    None,

            }

        if aggregate_score < (
            self.min_research_score
        ):

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Aggregate research score is "
                        "below the paper-trading threshold."
                    ),

                "aggregate_research_score":
                    aggregate_score,

                "research_gate":
                    False,

                "paper_signal":
                    None,

            }

        # ====================================================
        # CURRENT CELL CHECK
        # ====================================================

        if edge is None:

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "No research record exists for "
                        "this exact market/timeframe."
                    ),

                "aggregate_research_score":
                    aggregate_score,

                "research_gate":
                    False,

                "paper_signal":
                    None,

            }

        cell_validated = bool(
            edge.get(
                "validated",
                False,
            )
        )

        cell_score = (
            self.number(
                edge.get(
                    "research_score",
                    0.0,
                )
            )
        )

        # ====================================================
        # WE ALLOW PAPER TRADING ONLY IF THE CURRENT CELL
        # IS ALSO AT LEAST PROMISING.
        # ====================================================

        if (
            not cell_validated
            and
            cell_score < 55.0
        ):

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Exact market/timeframe research "
                        "cell is too weak."
                    ),

                "aggregate_research_score":
                    aggregate_score,

                "cell_research_score":
                    cell_score,

                "research_gate":
                    False,

                "paper_signal":
                    None,

            }

        # ====================================================
        # STRATEGY SIGNAL
        # ====================================================

        try:

            strategy_engine = (
                self.load_strategy(
                    strategy
                )
            )

            signal = (
                strategy_engine.signal(
                    df
                )
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Strategy signal failed: "
                        f"{exc}"
                    ),

            }

        if not signal.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "action":
                    "WAIT",

                "reason":
                    signal.get(
                        "message",
                        "Strategy analysis failed.",
                    ),

            }

        action = signal.get(
            "action",
            "WAIT",
        )

        confidence = (
            self.number(
                signal.get(
                    "confidence",
                    0.0,
                )
            )
        )

        # ====================================================
        # STRATEGY WAIT
        # ====================================================

        if action not in {
            "BUY",
            "SELL",
        }:

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Current strategy conditions "
                        "do not produce a trade."
                    ),

                "aggregate_research_score":
                    aggregate_score,

                "cell_research_score":
                    cell_score,

                "signal":
                    signal,

                "research_gate":
                    True,

                "paper_signal":
                    None,

            }

        # ====================================================
        # CONFIDENCE
        # ====================================================

        if confidence < (
            self.min_confidence
        ):

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Current signal confidence is "
                        "below paper-trading threshold."
                    ),

                "confidence":
                    confidence,

                "required_confidence":
                    self.min_confidence,

                "aggregate_research_score":
                    aggregate_score,

                "cell_research_score":
                    cell_score,

                "signal":
                    signal,

                "research_gate":
                    True,

                "paper_signal":
                    None,

            }

        # ====================================================
        # PRICE / RISK
        # ====================================================

        entry = signal.get(
            "entry"
        )

        stop_loss = signal.get(
            "stop_loss"
        )

        target = signal.get(
            "target"
        )

        if (
            entry is None
            or
            stop_loss is None
            or
            target is None
        ):

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    (
                        "Signal does not have a complete "
                        "entry/stop/target structure."
                    ),

                "signal":
                    signal,

                "research_gate":
                    True,

                "paper_signal":
                    None,

            }

        entry = self.number(
            entry
        )

        stop_loss = self.number(
            stop_loss
        )

        target = self.number(
            target
        )

        risk = self.risk_check(

            entry=entry,

            stop_loss=stop_loss,

            capital=account_capital,

        )

        if not risk.get(
            "approved",
            False,
        ):

            return {

                "success":
                    True,

                "action":
                    "WAIT",

                "reason":
                    risk.get(
                        "reason",
                        "Risk rejected.",
                    ),

                "risk":
                    risk,

                "signal":
                    signal,

                "research_gate":
                    True,

                "paper_signal":
                    None,

            }

        # ====================================================
        # CREATE RECORD
        # ====================================================

        record_id = (
            "PAPER-"
            +
            datetime.now().strftime(
                "%Y%m%d%H%M%S"
            )
            +
            "-"
            +
            uuid.uuid4().hex[:8]
        )

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        record = {

            "signal_id":
                record_id,

            "status":
                "PENDING",

            "created_at":
                now,

            "updated_at":
                now,

            "strategy":
                strategy,

            "symbol":
                symbol,

            "market":
                market,

            "timeframe":
                timeframe,

            "action":
                action,

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "target":
                target,

            "risk_reward":
                signal.get(
                    "risk_reward"
                ),

            "quantity":
                risk.get(
                    "quantity"
                ),

            "risk_amount":
                risk.get(
                    "risk_amount"
                ),

            "confidence":
                confidence,

            "aggregate_research_score":
                aggregate_score,

            "cell_research_score":
                cell_score,

            "aggregate_status":
                aggregate.get(
                    "status"
                ),

            "paper_or_live":
                "PAPER",

            "reasoning":
                (
                    signal.get(
                        "bullish_evidence",
                        []
                    )
                    +
                    signal.get(
                        "bearish_evidence",
                        []
                    )
                ),

            "metadata":
                metadata or {},

        }

        # ====================================================
        # SAVE
        # ====================================================

        signals = (
            self.load_signals()
        )

        signals.append(
            record
        )

        saved = (
            self.save_signals(
                signals
            )
        )

        if not saved:

            return {

                "success":
                    False,

                "action":
                    "WAIT",

                "reason":
                    "Could not save paper signal.",

            }

        return {

            "success":
                True,

            "action":
                action,

            "reason":
                (
                    "Paper-trading candidate created."
                ),

            "record":
                record,

            "research_gate":
                True,

            "saved":
                True,

        }

    # ========================================================
    # LATEST SIGNALS
    # ========================================================

    def latest(
        self,
        limit: int = 20,
    ) -> List[
        Dict[str, Any]
    ]:

        signals = (
            self.load_signals()
        )

        return signals[
            -abs(
                int(limit)
            ):
        ]

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS PAPER SIGNAL ENGINE"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Action: "
            f"{result.get('action')}"
        )

        lines.append(
            f"Reason: "
            f"{result.get('reason')}"
        )

        if result.get(
            "aggregate_research_score"
        ) is not None:

            lines.append(
                f"Aggregate Research Score: "
                f"{result.get('aggregate_research_score')}/100"
            )

        if result.get(
            "cell_research_score"
        ) is not None:

            lines.append(
                f"Cell Research Score: "
                f"{result.get('cell_research_score')}/100"
            )

        if result.get(
            "confidence"
        ) is not None:

            lines.append(
                f"Signal Confidence: "
                f"{result.get('confidence')}%"
            )

        risk = result.get(
            "risk",
            {}
        )

        if risk:

            lines.append("")

            lines.append(
                "RISK"
            )

            lines.append(
                f"Quantity: "
                f"{risk.get('quantity')}"
            )

            lines.append(
                f"Risk Amount: "
                f"{risk.get('risk_amount')}"
            )

        record = result.get(
            "record"
        )

        if record:

            lines.append("")

            lines.append(
                "PAPER SIGNAL"
            )

            lines.append(
                f"ID: "
                f"{record.get('signal_id')}"
            )

            lines.append(
                f"Strategy: "
                f"{record.get('strategy')}"
            )

            lines.append(
                f"Symbol: "
                f"{record.get('symbol')}"
            )

            lines.append(
                f"Direction: "
                f"{record.get('action')}"
            )

            lines.append(
                f"Entry: "
                f"{record.get('entry')}"
            )

            lines.append(
                f"Stop: "
                f"{record.get('stop_loss')}"
            )

            lines.append(
                f"Target: "
                f"{record.get('target')}"
            )

            lines.append(
                f"Risk/Reward: "
                f"{record.get('risk_reward')}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Paper-trading only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

paper_signal_engine = (
    PaperSignalEngine()
)


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def create_paper_signal(
    df: pd.DataFrame,
    strategy: str,
    symbol: str,
    market: str,
    timeframe: str,
    capital: Optional[float] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
):

    return (
        paper_signal_engine.create_signal(

            df=df,

            strategy=strategy,

            symbol=symbol,

            market=market,

            timeframe=timeframe,

            capital=capital,

            metadata=metadata,

        )
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    from agents.market_data_agent import (
        get_market_data,
    )

    print(
        "=" * 60
    )

    print(
        "JARVIS PAPER SIGNAL ENGINE"
    )

    print(
        "=" * 60
    )

    market_data = get_market_data(

        "NIFTY",

        market="india",

        timeframe="1d",

        bars=500,

    )

    if not market_data.get(
        "success",
        False,
    ):

        print(
            "Market data failed:"
        )

        print(
            market_data.get(
                "message"
            )
        )

    else:

        result = create_paper_signal(

            df=market_data["data"],

            strategy="MEAN_REVERSION",

            symbol="NIFTY",

            market="INDIA",

            timeframe="1d",

            capital=1_000_000.0,

        )

        print()

        print(
            paper_signal_engine.format_result(
                result
            )
        )

    print()

    print(
        "Signal Journal:"
    )

    print(
        SIGNAL_PATH
    )

    print()

    print(
        "Paper Signal Engine loaded successfully."
    )