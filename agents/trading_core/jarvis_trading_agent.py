
from __future__ import annotations

import json
import time
from pathlib import Path

from .live_monitor import LiveMonitorV7
from .option_confirmation import OptionConfirmation
from .paper_broker import PaperBroker
from .news_engine import NewsEngine
from .workstation_bridge import WorkstationBridge


class JarvisTradingAgentV1:
    """
    Unified, research/paper-only orchestration.

    It does not place orders.
    """

    def __init__(self, poll_seconds: int = 5):
        self.monitor = LiveMonitorV7(
            symbols=["NIFTY", "BANKNIFTY", "SENSEX"],
            poll_seconds=poll_seconds,
            auto_start_stream=True,
        )
        self.options = OptionConfirmation()
        self.paper = PaperBroker()
        self.news = NewsEngine()
        self.bridge = WorkstationBridge()
        self.running = False

    def run_once(self):
        trading = {}

        for symbol in self.monitor.symbols:
            state = self.monitor.scan_symbol(symbol)

            # Options confirmation only when a deterministic candidate exists.
            if state.get("setup") is not None:
                try:
                    state["options_confirmation"] = self.options.confirm(
                        symbol,
                        "current_week",
                    )
                except Exception as exc:
                    state["options_confirmation"] = {
                        "available": False,
                        "reason": str(exc),
                    }
            else:
                state["options_confirmation"] = {
                    "available": False,
                    "confirmed": False,
                    "reason": "No setup to confirm.",
                }

            # Update any existing paper positions from live LTP.
            ltp = (
                state.get("live", {})
                .get("ltp", {})
                .get("price")
            )
            if ltp:
                state["paper_closures"] = self.paper.update(
                    symbol,
                    float(ltp),
                )

            trading[symbol] = state

        # Top current market-news ranking.
        news = self.news.fetch(limit_per_feed=5)

        paper = self.paper.snapshot()

        self.bridge.write_state(
            trading,
            paper,
            news,
        )

        return {
            "trading": trading,
            "paper": paper,
            "news": news,
        }

    def run_forever(self):
        startup = self.monitor.start_stream()
        print(
            "JARVIS TRADING AGENT V1 > "
            f"Stream startup: {startup}"
        )

        self.running = True

        print("=" * 72)
        print("JARVIS TRADING AGENT V1")
        print("=" * 72)
        print("SENSEX LIVE FEED: ENABLED")
        print("OPTIONS CONFIRMATION: ENABLED")
        print("RESEARCH EDGE GATE: STRICT")
        print("PAPER EXECUTION: SIMULATION ONLY")
        print("NEWS ENGINE: ENABLED")
        print("WORKSTATION BRIDGE: ENABLED")
        print("VOICE EVENT BRIDGE: SEPARATE PROCESS")
        print("LIVE ORDERS: DISABLED")
        print()

        while self.running:
            try:
                state = self.run_once()

                for symbol, item in state["trading"].items():
                    print(
                        f"{symbol} | "
                        f"Status={item.get('status')} | "
                        f"Score={item.get('score')} | "
                        f"LTP={item.get('live', {}).get('ltp', {}).get('price')} | "
                        f"15m={item.get('15m', {}).get('direction')} | "
                        f"5m={item.get('5m', {}).get('direction')}"
                    )

                print(
                    "News items:",
                    len(state["news"]),
                    "| Paper open:",
                    len(state["paper"]["open"]),
                )

                time.sleep(5)

            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as exc:
                print("JARVIS TRADING AGENT > ERROR:", exc)
                time.sleep(5)

        try:
            self.monitor.stop()
        except Exception:
            pass


if __name__ == "__main__":
    JarvisTradingAgentV1().run_forever()
