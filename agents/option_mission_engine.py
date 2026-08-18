# ============================================================
# JARVIS OPTION MISSION ENGINE
# V3
# ============================================================
#
# VERIFIED UNDERLYING
#        ↓
# OPTION CHAIN
#        ↓
# OPTION DECISION
#        ↓
# OPTION TRADE PLAN
#        ↓
# SAFE LOT SIZING
#        ↓
# ALL-IN RISK GATE
#        ↓
# CONFIRMATION READY / BLOCKED
#
# PAPER / RESEARCH ONLY.
# NO LIVE ORDER.
# ============================================================

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import json
import math


# ============================================================
# PATHS
# ============================================================

BASE_PATH = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
)

MISSION_FILE = (
    BASE_PATH
    / "option_mission_latest.json"
)


# ============================================================
# ENGINE
# ============================================================

class OptionMissionEngine:

    def __init__(
        self,
        max_risk_percent: float = 1.0,
        minimum_rr: float = 1.5,
        default_lot_size: int = 1,
        fee_per_lot_round_trip: float = 40.0,
        slippage_percent: float = 1.0,
    ):

        self.max_risk_percent = float(
            max_risk_percent
        )

        self.minimum_rr = float(
            minimum_rr
        )

        self.default_lot_size = max(
            1,
            int(
                default_lot_size
            ),
        )

        self.fee_per_lot_round_trip = float(
            fee_per_lot_round_trip
        )

        self.slippage_percent = float(
            slippage_percent
        )

        BASE_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # NUMBER
    # ========================================================

    @staticmethod
    def number(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            result = float(value)

            if math.isnan(result):
                return default

            if math.isinf(result):
                return default

            return result

        except Exception:

            return default

    # ========================================================
    # NORMALIZE OPTION CHAIN
    # ========================================================

    def normalize_chain(
        self,
        chain_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        rows = []

        nearest = chain_result.get(
            "nearest_strikes",
            [],
        )

        if isinstance(
            nearest,
            list,
        ):

            rows.extend(
                nearest
            )

        generic_rows = chain_result.get(
            "rows",
            [],
        )

        if (
            isinstance(
                generic_rows,
                list,
            )
            and
            not rows
        ):

            rows.extend(
                generic_rows
            )

        deduped = {}

        for row in rows:

            if not isinstance(
                row,
                dict,
            ):
                continue

            strike = self.number(
                row.get(
                    "strike"
                ),
                0.0,
            )

            if strike <= 0:
                continue

            deduped[
                strike
            ] = dict(
                row
            )

        rows = list(
            deduped.values()
        )

        rows.sort(
            key=lambda item:
                self.number(
                    item.get(
                        "strike"
                    )
                )
        )

        calls = chain_result.get(
            "calls"
        )

        puts = chain_result.get(
            "puts"
        )

        if not isinstance(
            calls,
            list,
        ):

            calls = rows

        if not isinstance(
            puts,
            list,
        ):

            puts = rows

        spot = self.number(
            chain_result.get(
                "spot"
            ),
            0.0,
        )

        atm = self.number(
            chain_result.get(
                "atm"
            ),
            0.0,
        )

        if atm <= 0:

            atm = self.number(
                chain_result.get(
                    "atm_strike"
                ),
                0.0,
            )

        if (
            atm <= 0
            and
            rows
            and
            spot > 0
        ):

            valid_strikes = [

                self.number(
                    row.get(
                        "strike"
                    )
                )

                for row
                in rows

                if self.number(
                    row.get(
                        "strike"
                    )
                ) > 0

            ]

            if valid_strikes:

                atm = min(
                    valid_strikes,
                    key=lambda strike:
                        abs(
                            strike - spot
                        ),
                )

        lot_size = self.number(
            chain_result.get(
                "lot_size"
            ),
            0.0,
        )

        return {

            "success":
                bool(
                    rows
                ),

            "spot":
                spot,

            "atm":
                atm,

            "rows":
                rows,

            "calls":
                calls,

            "puts":
                puts,

            "lot_size":
                (
                    int(
                        lot_size
                    )
                    if lot_size > 0
                    else None
                ),

            "expiry":
                chain_result.get(
                    "expiry"
                ),

            "expiry_days":
                chain_result.get(
                    "expiry_days"
                ),

            "pcr":
                chain_result.get(
                    "pcr",
                    chain_result.get(
                        "put_call_ratio"
                    ),
                ),

            "atm_iv":
                chain_result.get(
                    "atm_iv"
                ),

            "iv_skew":
                chain_result.get(
                    "iv_skew"
                ),

        }

    # ========================================================
    # LOAD OPTION CHAIN
    # ========================================================

    def load_option_chain(
        self,
        symbol: str,
        market: str,
        expiry: Optional[str] = None,
    ) -> Dict[str, Any]:

        try:

            from agents.option_chain_engine import (
                option_chain_engine,
            )

        except Exception as exc:

            return {

                "success":
                    False,

                "message":
                    (
                        "Could not import option chain engine: "
                        f"{exc}"
                    ),

            }

        # ----------------------------------------------------
        # Try get_chain()
        # ----------------------------------------------------

        if hasattr(
            option_chain_engine,
            "get_chain",
        ):

            try:

                result = (
                    option_chain_engine.get_chain(

                        symbol=symbol,

                        market=market,

                        expiry=expiry,

                    )
                )

                if isinstance(
                    result,
                    dict,
                ):

                    normalized = (
                        self.normalize_chain(
                            result
                        )
                    )

                    if normalized[
                        "success"
                    ]:

                        return normalized

            except TypeError:
                pass

            except Exception as exc:

                return {

                    "success":
                        False,

                    "message":
                        (
                            "Option chain get_chain failed: "
                            f"{exc}"
                        ),

                }

        # ----------------------------------------------------
        # Try analyze()
        # ----------------------------------------------------

        if hasattr(
            option_chain_engine,
            "analyze",
        ):

            try:

                result = (
                    option_chain_engine.analyze(
                        symbol=symbol,
                        market=market,
                    )
                )

                if isinstance(
                    result,
                    dict,
                ):

                    normalized = (
                        self.normalize_chain(
                            result
                        )
                    )

                    if normalized[
                        "success"
                    ]:

                        return normalized

            except TypeError:
                pass

            except Exception as exc:

                return {

                    "success":
                        False,

                    "message":
                        (
                            "Option chain analyze failed: "
                            f"{exc}"
                        ),

                }

        # ----------------------------------------------------
        # Try run()
        # ----------------------------------------------------

        if hasattr(
            option_chain_engine,
            "run",
        ):

            try:

                result = (
                    option_chain_engine.run(
                        symbol=symbol,
                        market=market,
                    )
                )

                if isinstance(
                    result,
                    dict,
                ):

                    normalized = (
                        self.normalize_chain(
                            result
                        )
                    )

                    if normalized[
                        "success"
                    ]:

                        return normalized

            except TypeError:
                pass

            except Exception as exc:

                return {

                    "success":
                        False,

                    "message":
                        (
                            "Option chain run failed: "
                            f"{exc}"
                        ),

                }

        return {

            "success":
                False,

            "message":
                (
                    "No compatible option-chain API "
                    "returned usable strikes."
                ),

        }

    # ========================================================
    # SELECT OPTION STRATEGY
    # ========================================================

    def select_strategy(
        self,
        spot: float,
        direction: str,
        setup_strength: float,
        chain: Dict[str, Any],
    ) -> Dict[str, Any]:

        from agents.option_decision_engine import (
            option_decision_engine,
        )

        return (
            option_decision_engine.decide(

                spot=spot,

                bias=direction,

                setup_strength=
                    setup_strength,

                chain=chain,

                expiry_days=
                    chain.get(
                        "expiry_days"
                    ),

            )
        )

    # ========================================================
    # BUILD TRADE PLAN
    # ========================================================

    def build_trade_plan(
        self,
        decision: Dict[str, Any],
        capital: float,
        lot_size: int,
    ) -> Dict[str, Any]:

        from agents.option_trade_plan_engine import (
            option_trade_plan_engine,
        )

        return (
            option_trade_plan_engine.create_plan(

                decision=decision,

                capital=capital,

                lot_size=lot_size,

            )
        )

    # ========================================================
    # EXTRACT PER-LOT BASE RISK
    # ========================================================

    def per_lot_risk(
        self,
        plan: Dict[str, Any],
    ) -> float:

        lots = int(
            self.number(
                plan.get(
                    "lots",
                    0,
                )
            )
        )

        total_planned_risk = self.number(
            plan.get(
                "planned_risk",
                0.0,
            )
        )

        if (
            lots > 0
            and
            total_planned_risk > 0
        ):

            return (
                total_planned_risk
                /
                lots
            )

        # ----------------------------------------------------
        # Fallback for a one-lot theoretical plan.
        # ----------------------------------------------------

        if plan.get(
            "entry_debit"
        ) is not None:

            entry = self.number(
                plan.get(
                    "entry_debit"
                )
            )

            stop = self.number(
                plan.get(
                    "stop_debit"
                )
            )

            if (
                entry > 0
                and
                stop > 0
                and
                entry > stop
            ):

                return (
                    entry - stop
                )

        if plan.get(
            "entry_premium"
        ) is not None:

            entry = self.number(
                plan.get(
                    "entry_premium"
                )
            )

            stop = self.number(
                plan.get(
                    "stop_premium"
                )
            )

            if (
                entry > 0
                and
                stop > 0
                and
                entry > stop
            ):

                return (
                    entry - stop
                )

        return 0.0

    # ========================================================
    # ESTIMATE COST FOR LOTS
    # ========================================================

    def estimate_cost_for_lots(
        self,
        plan: Dict[str, Any],
        lots: int,
        lot_size: int,
    ) -> Dict[str, float]:

        lots = max(
            0,
            int(lots),
        )

        lot_size = max(
            1,
            int(lot_size),
        )

        quantity = (
            lots
            *
            lot_size
        )

        base_risk_per_lot = (
            self.per_lot_risk(
                plan
            )
        )

        planned_risk = (
            base_risk_per_lot
            *
            lots
        )

        fees = (
            lots
            *
            self.fee_per_lot_round_trip
        )

        entry_value = 0.0

        if plan.get(
            "entry_debit"
        ) is not None:

            entry_value = self.number(
                plan.get(
                    "entry_debit"
                )
            )

        elif plan.get(
            "entry_premium"
        ) is not None:

            entry_value = self.number(
                plan.get(
                    "entry_premium"
                )
            )

        # Estimated round-trip premium slippage.
        slippage = (

            entry_value
            *
            self.slippage_percent
            /
            100.0
            *
            2.0
            *
            quantity

        )

        total = (
            planned_risk
            +
            fees
            +
            slippage
        )

        return {

            "lots":
                float(
                    lots
                ),

            "quantity":
                float(
                    quantity
                ),

            "risk_per_lot":
                base_risk_per_lot,

            "planned_risk":
                planned_risk,

            "fees":
                fees,

            "slippage":
                slippage,

            "total_risk":
                total,

        }

    # ========================================================
    # SAFE SIZING
    # ========================================================

    def find_safe_size(
        self,
        plan: Dict[str, Any],
        capital: float,
        lot_size: int,
    ) -> Dict[str, Any]:

        max_allowed = (

            float(capital)
            *
            self.max_risk_percent
            /
            100.0

        )

        requested_lots = int(
            self.number(
                plan.get(
                    "lots",
                    0,
                )
            )
        )

        if requested_lots <= 0:

            return {

                "approved":
                    False,

                "requested_lots":
                    0,

                "safe_lots":
                    0,

                "max_allowed_risk":
                    max_allowed,

                "reason":
                    (
                        "Trade-plan sizing returned zero lots."
                    ),

            }

        # ----------------------------------------------------
        # Calculate directly from one-lot all-in economics.
        # ----------------------------------------------------

        one_lot = (
            self.estimate_cost_for_lots(

                plan=plan,

                lots=1,

                lot_size=lot_size,

            )
        )

        one_lot_total = one_lot[
            "total_risk"
        ]

        if (
            one_lot_total <= 0
        ):

            return {

                "approved":
                    False,

                "requested_lots":
                    requested_lots,

                "safe_lots":
                    0,

                "max_allowed_risk":
                    max_allowed,

                "reason":
                    (
                        "Could not calculate positive "
                        "all-in risk for one lot."
                    ),

            }

        if (
            one_lot_total
            >
            max_allowed
        ):

            return {

                "approved":
                    False,

                "requested_lots":
                    requested_lots,

                "safe_lots":
                    0,

                "max_allowed_risk":
                    max_allowed,

                "one_lot_total_risk":
                    one_lot_total,

                "reason":
                    (
                        f"Even one lot requires "
                        f"{one_lot_total:.2f}, "
                        f"above the allowed "
                        f"{max_allowed:.2f}."
                    ),

            }

        # ----------------------------------------------------
        # Calculate maximum mathematical lots.
        # ----------------------------------------------------

        theoretical_max = int(

            max_allowed
            //
            one_lot_total

        )

        safe_lots = min(

            requested_lots,

            theoretical_max,

        )

        safe_lots = max(
            1,
            safe_lots,
        )

        # ----------------------------------------------------
        # Recheck downward in case of floating point edge
        # cases.
        # ----------------------------------------------------

        while safe_lots > 0:

            cost = (
                self.estimate_cost_for_lots(

                    plan=plan,

                    lots=safe_lots,

                    lot_size=lot_size,

                )
            )

            if (
                cost[
                    "total_risk"
                ]
                <=
                max_allowed
                + 1e-9
            ):

                break

            safe_lots -= 1

        if safe_lots <= 0:

            return {

                "approved":
                    False,

                "requested_lots":
                    requested_lots,

                "safe_lots":
                    0,

                "max_allowed_risk":
                    max_allowed,

                "reason":
                    "No safe lot size exists.",

            }

        final_cost = (
            self.estimate_cost_for_lots(

                plan=plan,

                lots=safe_lots,

                lot_size=lot_size,

            )
        )

        return {

            "approved":
                True,

            "requested_lots":
                requested_lots,

            "safe_lots":
                safe_lots,

            "max_allowed_risk":
                max_allowed,

            "risk_per_lot":
                final_cost[
                    "risk_per_lot"
                ],

            "planned_risk":
                final_cost[
                    "planned_risk"
                ],

            "fees":
                final_cost[
                    "fees"
                ],

            "slippage":
                final_cost[
                    "slippage"
                ],

            "total_risk":
                final_cost[
                    "total_risk"
                ],

            "quantity":
                int(
                    final_cost[
                        "quantity"
                    ]
                ),

        }

    # ========================================================
    # FINAL RISK GATE
    # ========================================================

    def final_risk_gate(
        self,
        plan: Dict[str, Any],
        safe_size: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not safe_size.get(
            "approved",
            False,
        ):

            return {

                "approved":
                    False,

                "planned_risk":
                    0.0,

                "fees":
                    0.0,

                "slippage":
                    0.0,

                "total_estimated_risk":
                    0.0,

                "max_allowed_risk":
                    self.number(
                        safe_size.get(
                            "max_allowed_risk"
                        )
                    ),

                "lots":
                    0,

                "quantity":
                    0,

                "reasons": [
                    safe_size.get(
                        "reason",
                        "Risk sizing failed.",
                    )
                ],

            }

        rr = self.number(

            plan.get(
                "risk_reward_target_1",
                plan.get(
                    "risk_reward_contract",
                    0.0,
                )
            )

        )

        reasons = []

        if rr < self.minimum_rr:

            reasons.append(
                (
                    f"Final option-plan R/R "
                    f"{rr:.2f} is below "
                    f"minimum "
                    f"{self.minimum_rr:.2f}."
                )
            )

        total_risk = self.number(
            safe_size.get(
                "total_risk"
            )
        )

        allowed = self.number(
            safe_size.get(
                "max_allowed_risk"
            )
        )

        if (
            total_risk
            >
            allowed
        ):

            reasons.append(
                (
                    f"All-in risk "
                    f"{total_risk:.2f} exceeds "
                    f"allowed "
                    f"{allowed:.2f}."
                )
            )

        return {

            "approved":
                not reasons,

            "planned_risk":
                self.number(
                    safe_size.get(
                        "planned_risk"
                    )
                ),

            "fees":
                self.number(
                    safe_size.get(
                        "fees"
                    )
                ),

            "slippage":
                self.number(
                    safe_size.get(
                        "slippage"
                    )
                ),

            "total_estimated_risk":
                total_risk,

            "max_allowed_risk":
                allowed,

            "risk_percent":
                (
                    total_risk
                    /
                    max(
                        allowed
                        /
                        (
                            self.max_risk_percent
                            /
                            100.0
                        ),
                        1.0,
                    )
                    *
                    100.0
                ),

            "lots":
                int(
                    safe_size.get(
                        "safe_lots",
                        0,
                    )
                ),

            "quantity":
                int(
                    safe_size.get(
                        "quantity",
                        0,
                    )
                ),

            "risk_reward":
                rr,

            "reasons":
                reasons,

        }

    # ========================================================
    # CREATE MISSION
    # ========================================================

    def create_mission(
        self,
        underlying_setup: Dict[str, Any],
        symbol: str,
        market: str = "india",
        capital: float = 1_000_000.0,
        lot_size: Optional[int] = None,
        expiry: Optional[str] = None,
    ) -> Dict[str, Any]:

        symbol = (
            str(symbol)
            .upper()
            .strip()
        )

        # ====================================================
        # UNDERLYING GATE
        # ====================================================

        if not underlying_setup:

            return self.finish_blocked(
                "No underlying setup supplied."
            )

        if not underlying_setup.get(
            "execution_ready",
            False,
        ):

            return self.finish_blocked(
                (
                    "Underlying setup has not "
                    "passed verification."
                )
            )

        direction = str(
            underlying_setup.get(
                "direction",
                "NEUTRAL",
            )
        ).upper()

        if direction not in {
            "BULLISH",
            "BEARISH",
        }:

            return self.finish_blocked(
                "Invalid underlying direction."
            )

        setup_strength = self.number(
            underlying_setup.get(
                "setup_strength",
                0.0,
            )
        )

        if setup_strength < 75.0:

            return self.finish_blocked(
                (
                    "Underlying setup strength "
                    "is below option threshold."
                )
            )

        # ====================================================
        # OPTION CHAIN
        # ====================================================

        chain = (
            self.load_option_chain(

                symbol=symbol,

                market=market,

                expiry=expiry,

            )
        )

        if not chain.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "status":
                    "CHAIN_ERROR",

                "reason":
                    chain.get(
                        "message",
                        "Option chain unavailable.",
                    ),

            }

        # ====================================================
        # LOT SIZE
        # ====================================================

        if lot_size is None:

            lot_size = chain.get(
                "lot_size"
            )

        if lot_size is None:

            lot_size = (
                self.default_lot_size
            )

        lot_size = max(
            1,
            int(
                lot_size
            ),
        )

        # ====================================================
        # OPTION DECISION
        # ====================================================

        decision = (
            self.select_strategy(

                spot=
                    chain.get(
                        "spot"
                    ),

                direction=
                    direction,

                setup_strength=
                    setup_strength,

                chain=
                    chain,

            )
        )

        if not decision.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "status":
                    "OPTION_DECISION_ERROR",

                "decision":
                    decision,

            }

        if (
            decision.get(
                "decision"
            )
            ==
            "WAIT"
        ):

            result = {

                "success":
                    True,

                "status":
                    "WAIT",

                "symbol":
                    symbol,

                "underlying":
                    underlying_setup,

                "option_chain":
                    chain,

                "decision":
                    decision,

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

            }

            self.save(
                result
            )

            return result

        # ====================================================
        # INITIAL TRADE PLAN
        # ====================================================

        plan = (
            self.build_trade_plan(

                decision=
                    decision,

                capital=
                    float(
                        capital
                    ),

                lot_size=
                    lot_size,

            )
        )

        if not plan.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "status":
                    "PLAN_ERROR",

                "decision":
                    decision,

                "reason":
                    plan.get(
                        "message",
                        "Trade plan failed.",
                    ),

            }

        if not plan.get(
            "approved",
            False,
        ):

            result = {

                "success":
                    True,

                "status":
                    "BLOCKED_PLAN",

                "symbol":
                    symbol,

                "underlying":
                    underlying_setup,

                "decision":
                    decision,

                "trade_plan":
                    plan,

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

            }

            self.save(
                result
            )

            return result

        # ====================================================
        # SAFE SIZE
        # ====================================================

        safe_size = (
            self.find_safe_size(

                plan=
                    plan,

                capital=
                    float(
                        capital
                    ),

                lot_size=
                    lot_size,

            )
        )

        # ----------------------------------------------------
        # Always make the risk object informative.
        # ----------------------------------------------------

        if not safe_size.get(
            "approved",
            False,
        ):

            risk_gate = (
                self.final_risk_gate(

                    plan=
                        plan,

                    safe_size=
                        safe_size,

                )
            )

            result = {

                "success":
                    True,

                "status":
                    "BLOCKED_RISK",

                "symbol":
                    symbol,

                "underlying":
                    underlying_setup,

                "decision":
                    decision,

                "trade_plan":
                    plan,

                "risk_gate":
                    risk_gate,

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

            }

            self.save(
                result
            )

            return result

        # ====================================================
        # APPLY SAFE SIZE
        # ====================================================

        safe_lots = int(
            safe_size[
                "safe_lots"
            ]
        )

        safe_quantity = int(
            safe_size[
                "quantity"
            ]
        )

        safe_plan = dict(
            plan
        )

        safe_plan[
            "lots"
        ] = safe_lots

        safe_plan[
            "quantity"
        ] = safe_quantity

        safe_plan[
            "planned_risk"
        ] = safe_size[
            "planned_risk"
        ]

        safe_plan[
            "fees"
        ] = safe_size[
            "fees"
        ]

        safe_plan[
            "slippage_allowance"
        ] = safe_size[
            "slippage"
        ]

        # ====================================================
        # FINAL GATE
        # ====================================================

        risk_gate = (
            self.final_risk_gate(

                plan=
                    safe_plan,

                safe_size=
                    safe_size,

            )
        )

        if not risk_gate.get(
            "approved",
            False,
        ):

            result = {

                "success":
                    True,

                "status":
                    "BLOCKED_RISK",

                "symbol":
                    symbol,

                "underlying":
                    underlying_setup,

                "decision":
                    decision,

                "trade_plan":
                    safe_plan,

                "risk_gate":
                    risk_gate,

                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

            }

            self.save(
                result
            )

            return result

        # ====================================================
        # FINAL
        # ====================================================

        final = {

            "success":
                True,

            "status":
                "CONFIRMATION_READY",

            "symbol":
                symbol,

            "market":
                market,

            "underlying":
                {

                    "direction":
                        direction,

                    "setup_strength":
                        setup_strength,

                    "quality":
                        underlying_setup.get(
                            "quality"
                        ),

                    "agreement":
                        underlying_setup.get(
                            "agreement"
                        ),

                },

            "option_decision":
                decision,

            "option_trade_plan":
                safe_plan,

            "risk_gate":
                risk_gate,

            "execution":
                {

                    "mode":
                        "PAPER",

                    "confirmation_required":
                        True,

                    "live_order":
                        False,

                },

            "timestamp":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

        }

        self.save(
            final
        )

        return final

    # ========================================================
    # BLOCK HELPER
    # ========================================================

    @staticmethod
    def finish_blocked(
        reason: str,
    ) -> Dict[str, Any]:

        return {

            "success":
                True,

            "status":
                "BLOCKED",

            "reason":
                reason,

        }

    # ========================================================
    # SAVE
    # ========================================================

    def save(
        self,
        result: Dict[str, Any],
    ):

        try:

            MISSION_FILE.write_text(

                json.dumps(
                    result,
                    indent=2,
                    default=str,
                ),

                encoding="utf-8",

            )

        except Exception as exc:

            print(
                "JARVIS OPTION MISSION DEBUG > "
                f"Save failed: {exc}"
            )

    # ========================================================
    # FORMAT
    # ========================================================

    def format_result(
        self,
        result: Dict[str, Any],
    ) -> str:

        lines = []

        lines.append(
            "JARVIS OPTION MISSION V3"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Status: "
            f"{result.get('status')}"
        )

        if result.get(
            "reason"
        ):

            lines.append(
                f"Reason: "
                f"{result.get('reason')}"
            )

        underlying = (
            result.get(
                "underlying",
                {}
            )
        )

        if underlying:

            lines.append("")

            lines.append(
                "UNDERLYING"
            )

            lines.append(
                f"Direction: "
                f"{underlying.get('direction')}"
            )

            lines.append(
                f"Setup Strength: "
                f"{underlying.get('setup_strength')}/100"
            )

            lines.append(
                f"Quality: "
                f"{underlying.get('quality')}"
            )

            lines.append(
                f"Agreement: "
                f"{underlying.get('agreement')}%"
            )

        decision = (
            result.get(
                "option_decision",
                result.get(
                    "decision"
                )
            )
        )

        if decision:

            lines.append("")

            lines.append(
                "OPTION DECISION"
            )

            lines.append(
                f"Strategy: "
                f"{decision.get('decision')}"
            )

            lines.append(
                f"Selection Score: "
                f"{self.number(decision.get('selection_score')):.2f}"
            )

            contract = decision.get(
                "contract"
            )

            if contract:

                for key, value in (
                    contract.items()
                ):

                    lines.append(
                        f"{key}: {value}"
                    )

        plan = result.get(
            "option_trade_plan",
            result.get(
                "trade_plan"
            )
        )

        if plan:

            lines.append("")

            lines.append(
                "OPTION TRADE PLAN"
            )

            if plan.get(
                "entry_debit"
            ) is not None:

                lines.append(
                    f"Entry Debit: "
                    f"{self.number(plan.get('entry_debit')):.2f}"
                )

                lines.append(
                    f"Stop Debit: "
                    f"{self.number(plan.get('stop_debit')):.2f}"
                )

                lines.append(
                    f"Target 1: "
                    f"{self.number(plan.get('target_1_debit')):.2f}"
                )

                lines.append(
                    f"Target 2: "
                    f"{self.number(plan.get('target_2_debit')):.2f}"
                )

                lines.append(
                    f"Max Profit: "
                    f"{self.number(plan.get('max_profit')):.2f}"
                )

                lines.append(
                    f"Max Loss: "
                    f"{self.number(plan.get('max_loss')):.2f}"
                )

                lines.append(
                    f"Plan R/R: "
                    f"{self.number(plan.get('risk_reward_target_1')):.2f}"
                )

            elif plan.get(
                "entry_premium"
            ) is not None:

                lines.append(
                    f"Entry Premium: "
                    f"{self.number(plan.get('entry_premium')):.2f}"
                )

                lines.append(
                    f"Stop Premium: "
                    f"{self.number(plan.get('stop_premium')):.2f}"
                )

                lines.append(
                    f"Target 1: "
                    f"{self.number(plan.get('target_1_premium')):.2f}"
                )

                lines.append(
                    f"Target 2: "
                    f"{self.number(plan.get('target_2_premium')):.2f}"
                )

                lines.append(
                    f"Plan R/R: "
                    f"{self.number(plan.get('risk_reward_target_1')):.2f}"
                )

            lines.append(
                f"Lot Size: "
                f"{plan.get('lot_size')}"
            )

            lines.append(
                f"Requested Lots: "
                f"{plan.get('lots')}"
            )

            lines.append(
                f"Quantity: "
                f"{plan.get('quantity')}"
            )

            lines.append(
                f"Planned Risk: "
                f"{self.number(plan.get('planned_risk')):.2f}"
            )

        risk = result.get(
            "risk_gate"
        )

        if risk:

            lines.append("")

            lines.append(
                "ALL-IN RISK"
            )

            lines.append(
                f"Planned Risk: "
                f"{self.number(risk.get('planned_risk')):.2f}"
            )

            lines.append(
                f"Fees: "
                f"{self.number(risk.get('fees')):.2f}"
            )

            lines.append(
                f"Slippage: "
                f"{self.number(risk.get('slippage')):.2f}"
            )

            lines.append(
                f"Total Estimated Risk: "
                f"{self.number(risk.get('total_estimated_risk')):.2f}"
            )

            lines.append(
                f"Max Allowed Risk: "
                f"{self.number(risk.get('max_allowed_risk')):.2f}"
            )

            lines.append(
                f"Risk %: "
                f"{self.number(risk.get('risk_percent')):.2f}%"
            )

            lines.append(
                f"Safe Lots: "
                f"{risk.get('lots', 0)}"
            )

            lines.append(
                f"Safe Quantity: "
                f"{risk.get('quantity', 0)}"
            )

            reasons = risk.get(
                "reasons",
                []
            )

            for reason in reasons:

                lines.append(
                    f"BLOCK: {reason}"
                )

        execution = result.get(
            "execution"
        )

        if execution:

            lines.append("")

            lines.append(
                "EXECUTION"
            )

            lines.append(
                f"Mode: "
                f"{execution.get('mode')}"
            )

            lines.append(
                f"Confirmation Required: "
                f"{execution.get('confirmation_required')}"
            )

            lines.append(
                f"Live Order: "
                f"{execution.get('live_order')}"
            )

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "Paper/research only. "
            "No live order was placed."
        )

        return "\n".join(
            lines
        )


# ============================================================
# GLOBAL
# ============================================================

option_mission_engine = (
    OptionMissionEngine()
)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS OPTION MISSION ENGINE V3"
    )

    print(
        "=" * 60
    )

    fake_underlying = {

        "execution_ready":
            True,

        "direction":
            "BULLISH",

        "setup_strength":
            86.0,

        "quality":
            "A",

        "agreement":
            100.0,

    }

    synthetic_chain = {

        "success":
            True,

        "spot":
            24366.0,

        "atm":
            24400.0,

        "lot_size":
            25,

        "expiry_days":
            20,

        "rows": [

            {
                "strike":
                    24200,

                "call_ltp":
                    330.0,

                "put_ltp":
                    80.0,

                "call_iv":
                    18.0,

                "put_iv":
                    19.0,

                "call_oi":
                    100000,

                "put_oi":
                    95000,

                "call_volume":
                    25000,

                "put_volume":
                    27000,

            },

            {
                "strike":
                    24400,

                "call_ltp":
                    299.4,

                "put_ltp":
                    110.0,

                "call_iv":
                    18.0,

                "put_iv":
                    19.0,

                "call_oi":
                    100000,

                "put_oi":
                    95000,

                "call_volume":
                    25000,

                "put_volume":
                    27000,

            },

            {
                "strike":
                    24600,

                "call_ltp":
                    150.0,

                "put_ltp":
                    170.0,

                "call_iv":
                    18.0,

                "put_iv":
                    19.0,

                "call_oi":
                    100000,

                "put_oi":
                    95000,

                "call_volume":
                    25000,

                "put_volume":
                    27000,

            },

        ],

    }

    original_loader = (
        option_mission_engine
        .load_option_chain
    )

    option_mission_engine.load_option_chain = (

        lambda
        symbol,
        market,
        expiry=None:

            synthetic_chain

    )

    try:

        result = (
            option_mission_engine.create_mission(

                underlying_setup=
                    fake_underlying,

                symbol=
                    "NIFTY",

                market=
                    "india",

                capital=
                    1_000_000.0,

            )
        )

    finally:

        option_mission_engine.load_option_chain = (
            original_loader
        )

    print()

    print(
        option_mission_engine.format_result(
            result
        )
    )

    print()

    print(
        f"Saved file: "
        f"{MISSION_FILE}"
    )

    print()

    print(
        "Option Mission Engine V3 loaded successfully."
    )