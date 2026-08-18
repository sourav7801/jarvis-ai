
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .option_confirmation_v2 import OptionConfirmationV2
from .research_gate import ResearchGate


BANKNIFTY_MOMENTUM_THRESHOLD = 65.0


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d",
        ).date()
    except Exception:
        return None


def is_previous_weekday(trading_date: date, expiry_date: date) -> bool:
    """
    Baseline previous-trading-day approximation.

    We deliberately use weekdays here; a later market-calendar layer can
    replace this with NSE/BSE holiday-aware previous-session logic.
    """
    d = expiry_date - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return trading_date == d


def banknifty_window(
    trading_date: date,
    expiry_date: date | None,
) -> dict[str, Any]:
    if expiry_date is None:
        return {
            "eligible": False,
            "phase": "UNKNOWN",
            "reason": "No concrete BANKNIFTY expiry was discovered.",
        }

    if trading_date == expiry_date:
        return {
            "eligible": True,
            "phase": "EXPIRY_DAY",
            "reason": "BANKNIFTY is on its discovered monthly expiry date.",
        }

    if is_previous_weekday(trading_date, expiry_date):
        return {
            "eligible": True,
            "phase": "PRE_EXPIRY",
            "reason": "BANKNIFTY is on the previous trading day to monthly expiry.",
        }

    return {
        "eligible": False,
        "phase": "NORMAL",
        "reason": (
            f"BANKNIFTY monthly-expiry window not active. "
            f"Expiry={expiry_date.isoformat()}."
        ),
    }


class TradeDecisionEngineV1:
    """
    Turns the existing 15m/5m setup into a gated decision.

    Gates:
      1. setup must exist
      2. symbol policy
      3. research must explicitly be VALIDATED
      4. option chain must be available
      5. BANKNIFTY requires expiry/pre-expiry + strong momentum

    No broker orders are placed.
    """

    def __init__(
        self,
        research: ResearchGate | None = None,
        options: OptionConfirmationV2 | None = None,
    ):
        self.research = research or ResearchGate()
        self.options = options or OptionConfirmationV2()

    def option_confirmation(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        try:
            return self.options.confirm(symbol)
        except Exception as exc:
            return {
                "available": False,
                "confirmed": False,
                "reason": str(exc),
            }

    def evaluate(
        self,
        symbol: str,
        setup: dict[str, Any] | None,
        momentum_score: float | None,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        symbol = symbol.upper()
        trading_date = as_of or date.today()

        base = {
            "symbol": symbol,
            "decision": "WAIT",
            "eligible": False,
            "paper_candidate": False,
            "reason": "",
            "gates": {},
        }

        if not setup:
            base["reason"] = "No strategy setup exists."
            base["gates"]["setup"] = False
            return base

        base["gates"]["setup"] = True

        # ----------------------------------------------------
        # Symbol policy
        # ----------------------------------------------------
        if symbol == "BANKNIFTY":
            opt_probe = self.option_confirmation(symbol)
            expiry = parse_iso_date(
                opt_probe.get("expiry")
            )

            window = banknifty_window(
                trading_date,
                expiry,
            )

            base["banknifty_policy"] = {
                **window,
                "expiry": expiry,
                "momentum_score": momentum_score,
                "momentum_threshold": BANKNIFTY_MOMENTUM_THRESHOLD,
            }

            if not window["eligible"]:
                base["reason"] = window["reason"]
                base["gates"]["symbol_policy"] = False
                return base

            if (
                momentum_score is None
                or float(momentum_score)
                < BANKNIFTY_MOMENTUM_THRESHOLD
            ) and (
                momentum_score is None
                or float(momentum_score)
                > (100.0 - BANKNIFTY_MOMENTUM_THRESHOLD)
            ):
                base["reason"] = (
                    "BANKNIFTY is in the expiry window, "
                    "but momentum is not strong enough."
                )
                base["gates"]["symbol_policy"] = False
                return base

            base["gates"]["symbol_policy"] = True
            option = opt_probe

        else:
            base["gates"]["symbol_policy"] = True
            option = self.option_confirmation(symbol)

        # ----------------------------------------------------
        # Research gate
        # ----------------------------------------------------
        strategy = str(
            setup.get(
                "strategy",
                ""
            )
        )

        research_result = self.research.authorize(
            symbol,
            strategy,
        )

        base["research"] = research_result

        if not research_result.get(
            "eligible"
        ):
            base["reason"] = (
                "Research edge is not explicitly VALIDATED "
                f"for {symbol}/{strategy}."
            )
            base["gates"]["research"] = False
            return base

        base["gates"]["research"] = True

        # ----------------------------------------------------
        # Option chain gate
        # ----------------------------------------------------
        base["options"] = option

        if not option.get(
            "available"
        ):

            base["reason"] = (
                "Option confirmation is unavailable."
            )

            base["gates"]["options"] = False

            return base

        base["gates"]["options"] = True

        # ----------------------------------------------------
        # Final decision
        # ----------------------------------------------------
        base["eligible"] = True
        base["paper_candidate"] = True
        base["decision"] = "PAPER_CANDIDATE"
        base["reason"] = (
            "Setup passed symbol policy, explicit research validation, "
            "and option-chain availability. "
            "No order was placed."
        )

        return base
