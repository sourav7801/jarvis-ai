# ============================================================
# JARVIS TRADING AGENT
# V1
# ============================================================

from __future__ import annotations
import re

from typing import Any, Dict

from agents.market_data_agent import (
    get_market_data,
)

from agents.technical_engine import (
    technical_engine,
)

from agents.pattern_engine import (
    pattern_engine,
)

from agents.signal_engine import (
    signal_engine,
)

from agents.risk_engine import (
    risk_engine,
)




def extract_timeframe(
    request: str,
    default: str = "1d",
) -> str:

    text = (
        str(
            request
            or ""
        )
        .lower()
        .strip()
    )


    compact = re.search(
        r"(?<![a-z0-9])"
        r"(1m|3m|5m|15m|30m|1h|2h|4h|1d)"
        r"(?![a-z0-9])",
        text,
    )


    if compact:
        return compact.group(1)


    human = re.search(
        r"(?<!\d)"
        r"(1|3|5|15|30|60|120|240)"
        r"\s*"
        r"(minute|minutes|min|mins|hour|hours|hr|hrs)",
        text,
    )


    if not human:
        return default


    amount = int(
        human.group(1)
    )

    unit = human.group(2)


    if unit.startswith(
        (
            "hour",
            "hr",
        )
    ):
        return {
            1:
                "1h",

            2:
                "2h",

            4:
                "4h",
        }.get(
            amount,
            default,
        )


    return {
        1:
            "1m",

        3:
            "3m",

        5:
            "5m",

        15:
            "15m",

        30:
            "30m",

        60:
            "1h",

        120:
            "2h",

        240:
            "4h",
    }.get(
        amount,
        default,
    )


class TradingAgent:

    def __init__(self):

        self.name = "trading"

    # ========================================================
    # SYMBOL EXTRACTION
    # ========================================================

    def extract_symbol(
        self,
        request: str,
    ) -> str:

        text = str(
            request or ""
        ).strip()

        words = text.upper().split()

        ignored = {

            "ANALYZE",
            "ANALYSE",
            "TRADE",
            "TRADING",
            "BUY",
            "SELL",
            "SHOW",
            "ME",
            "THE",
            "MARKET",
            "CHART",
            "STOCK",
            "SHARE",
            "PRICE",
            "TODAY",
            "TODAYS",
            "TODAY'S",
            "PLEASE",
            "NIFTY",
            "BANKNIFTY",

        }

        # Explicit index names.
        lowered = text.lower()

        if "banknifty" in lowered:
            return "BANKNIFTY"

        if "bank nifty" in lowered:
            return "BANKNIFTY"

        if "nifty 50" in lowered:
            return "NIFTY"

        if "nifty" in lowered:
            return "NIFTY"

        for word in words:

            clean = (
                word
                .strip(
                    ".,!?;:'\"()[]{}"
                )
            )

            if not clean:
                continue

            if clean in ignored:
                continue

            if (
                1
                <= len(clean)
                <= 12
                and
                any(
                    character.isalpha()
                    for character
                    in clean
                )
            ):

                return clean

        return "NIFTY"

    # ========================================================
    # FORMAT PRICE
    # ========================================================

    def _fmt(
        self,
        value,
    ):

        if value is None:
            return "N/A"

        try:
            return f"{float(value):,.2f}"
        except Exception:
            return str(value)

    # ========================================================
    # ANALYZE SYMBOL
    # ========================================================

    def analyze(
        self,
        symbol: str,
        market: str = "india",
        timeframe: str = "1d",
        bars: int = 500,
        account_equity: float = 1_000_000.0,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # MARKET DATA
        # ----------------------------------------------------

        market_result = get_market_data(
            symbol=symbol,
            market=market,
            timeframe=timeframe,
            bars=bars,
        )

        if not market_result.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "stage":
                    "market_data",

                "message":
                    market_result.get(
                        "message",
                        "Market data unavailable.",
                    ),

            }

        data = market_result.get(
            "data"
        )

        if data is None or data.empty:

            return {

                "success":
                    False,

                "stage":
                    "market_data",

                "message":
                    "Market data is empty.",

            }

        # ----------------------------------------------------
        # TECHNICAL ANALYSIS
        # ----------------------------------------------------

        technical = (
            technical_engine.analyze(
                data
            )
        )

        if not technical.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "stage":
                    "technical",

                "message":
                    technical.get(
                        "message",
                        "Technical analysis failed.",
                    ),

            }

        # ----------------------------------------------------
        # PATTERN ANALYSIS
        # ----------------------------------------------------

        patterns = (
            pattern_engine.analyze(
                data
            )
        )

        if not patterns.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "stage":
                    "patterns",

                "message":
                    patterns.get(
                        "message",
                        "Pattern analysis failed.",
                    ),

            }

        # ----------------------------------------------------
        # SIGNAL
        # ----------------------------------------------------

        signal = (
            signal_engine.generate_signal(
                technical,
                patterns,
            )
        )

        if not signal.get(
            "success",
            False,
        ):

            return {

                "success":
                    False,

                "stage":
                    "signal",

                "message":
                    signal.get(
                        "message",
                        "Signal generation failed.",
                    ),

            }

        # ----------------------------------------------------
        # RISK
        # ----------------------------------------------------

        action = signal.get(
            "action"
        )

        entry = signal.get(
            "entry"
        )

        stop_loss = signal.get(
            "stop_loss"
        )

        target = signal.get(
            "target"
        )

        risk = None

        if action in {
            "BUY",
            "SELL",
        } and entry and stop_loss and target:

            risk = (
                risk_engine.evaluate_trade(
                    account_equity=account_equity,
                    entry_price=entry,
                    stop_price=stop_loss,
                    target_price=target,
                )
            )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

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
                len(data),

            "source":
                market_result.get(
                    "source"
                ),

            "price":
                signal.get(
                    "price"
                ),

            "technical":
                technical,

            "patterns":
                patterns,

            "signal":
                signal,

            "risk":
                risk,

        }

    # ========================================================
    # FORMAT ANALYSIS
    # ========================================================

    def format_analysis(
        self,
        result: Dict[str, Any],
    ) -> str:

        if not result.get(
            "success",
            False,
        ):

            return (
                "TRADING ANALYSIS FAILED\n"
                "--------------------------------------------------\n"
                +
                str(
                    result.get(
                        "message",
                        "Unknown error.",
                    )
                )
            )

        technical = result[
            "technical"
        ]

        patterns = result[
            "patterns"
        ]

        signal = result[
            "signal"
        ]

        risk = result.get(
            "risk"
        )

        lines = []

        lines.append(
            "JARVIS TRADING ANALYSIS"
        )

        lines.append(
            "--------------------------------------------------"
        )

        lines.append(
            f"Symbol: {result['symbol']}"
        )

        lines.append(
            f"Market: {result['market']}"
        )

        lines.append(
            f"Timeframe: {result['timeframe']}"
        )

        lines.append(
            f"Data Source: {result['source']}"
        )

        lines.append(
            f"Bars: {result['bars']:,}"
        )

        lines.append("")

        lines.append(
            "MARKET STATE"
        )

        lines.append(
            f"Price: "
            f"{self._fmt(result['price'])}"
        )

        lines.append(
            f"Trend: "
            f"{technical.get('trend', 'N/A')}"
        )

        lines.append(
            f"Momentum: "
            f"{technical.get('momentum', 'N/A')}"
        )

        lines.append(
            f"RSI: "
            f"{self._fmt(technical.get('rsi'))}"
        )

        lines.append(
            f"ADX: "
            f"{self._fmt(technical.get('adx'))}"
        )

        lines.append("")

        lines.append(
            "MARKET STRUCTURE"
        )

        lines.append(
            f"Bias: "
            f"{patterns.get('bias', 'N/A')}"
        )

        breakout = patterns.get(
            "breakout",
            {},
        )

        lines.append(
            f"Breakout: "
            f"{breakout.get('signal', 'NONE')}"
        )

        lines.append("")

        lines.append(
            "SIGNAL"
        )

        lines.append(
            f"Decision: "
            f"{signal.get('action', 'WAIT')}"
        )

        lines.append(
            f"Confidence Score: "
            f"{signal.get('confidence', 0)}%"
        )

        lines.append(
            f"Bullish Score: "
            f"{signal.get('bullish_score', 0)}"
        )

        lines.append(
            f"Bearish Score: "
            f"{signal.get('bearish_score', 0)}"
        )

        lines.append(
            f"Entry: "
            f"{self._fmt(signal.get('entry'))}"
        )

        lines.append(
            f"Stop Loss: "
            f"{self._fmt(signal.get('stop_loss'))}"
        )

        lines.append(
            f"Target: "
            f"{self._fmt(signal.get('target'))}"
        )

        lines.append(
            f"Risk/Reward: "
            f"{self._fmt(signal.get('risk_reward'))}"
        )

        # ----------------------------------------------------
        # Risk decision
        # ----------------------------------------------------

        if risk is not None:

            lines.append("")

            lines.append(
                "RISK ENGINE"
            )

            lines.append(
                "Decision: "
                +
                (
                    "APPROVED"
                    if risk.approved
                    else "REJECTED"
                )
            )

            lines.append(
                f"Reason: "
                f"{risk.reason}"
            )

            lines.append(
                f"Risk Amount: "
                f"{self._fmt(risk.risk_amount)}"
            )

            lines.append(
                f"Position Size: "
                f"{self._fmt(risk.position_size)}"
            )

        # ----------------------------------------------------
        # Evidence
        # ----------------------------------------------------

        evidence = signal.get(
            "evidence",
            [],
        )

        if evidence:

            lines.append("")

            lines.append(
                "SIGNAL EVIDENCE"
            )

            for item in evidence[:15]:

                lines.append(
                    f"- {item}"
                )

        # ----------------------------------------------------
        # Warning
        # ----------------------------------------------------

        lines.append("")

        lines.append(
            "IMPORTANT: "
            "This is an analytical candidate signal. "
            "No live trade was placed."
        )

        return "\n".join(
            lines
        )

    # ========================================================
    # NATURAL LANGUAGE REQUEST
    # ========================================================

    def trade(
        self,
        request: str,
    ) -> Dict[str, Any]:

        symbol = (
            self.extract_symbol(
                request
            )
        )

        timeframe = extract_timeframe(
            request
        )


        result = self.analyze(
            symbol=symbol,
            market="india",
            timeframe=timeframe,
        )

        if not result.get(
            "success",
            False,
        ):

            return result

        return {

            "success":
                True,

            "message":
                self.format_analysis(
                    result
                ),

            "analysis":
                result,

        }


# ============================================================
# GLOBAL AGENT
# ============================================================

trading_agent = TradingAgent()


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def trading(
    request: str,
):

    return trading_agent.trade(
        request
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS TRADING AGENT"
    )

    print(
        "=" * 60
    )

    result = trading(
        "analyze NIFTY"
    )

    print()

    print(
        result.get(
            "message",
            result,
        )
    )