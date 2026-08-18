
from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import date

from .live_monitor import LiveMonitorV7, closed_frame
from .strategy_candidate_engine_v3 import generate_strategy_candidates
from .trade_decision_engine_v1 import TradeDecisionEngineV1
from .market_state_label import annotate
from .paper_execution_v2 import PaperExecutionV2


STATE_FILE = (
    Path.home()
    / "Documents"
    / "JARVIS_Trading"
    / "jarvis_strategy_paper_v3.json"
)


class JarvisStrategyPaperV3:
    def __init__(self, poll_seconds: int = 10):
        self.monitor = LiveMonitorV7(
            symbols=[
                "NIFTY",
                "BANKNIFTY",
                "SENSEX",
            ],
            poll_seconds=3,
            auto_start_stream=True,
        )
        self.decider = TradeDecisionEngineV1()
        self.paper = PaperExecutionV2()
        self.poll_seconds = max(5, int(poll_seconds))

    def evaluate_symbol(self, symbol: str):
        market = self.monitor.scan_symbol(symbol)
        stream = self.monitor.stream

        if stream is None:
            return {
                "market": market,
                "status": "STREAM_UNAVAILABLE",
                "candidates": [],
                "decisions": [],
                "paper_events": [],
            }

        raw15 = stream.store.get_dataframe(
            symbol,
            "15m",
        )
        raw5 = stream.store.get_dataframe(
            symbol,
            "5m",
        )

        frame15, _ = closed_frame(
            raw15,
            15,
        )
        frame5, _ = closed_frame(
            raw5,
            5,
        )

        direction15 = (
            market.get("15m", {}).get("direction")
        )
        direction5 = (
            market.get("5m", {}).get("direction")
        )
        momentum = (
            market.get("5m", {}).get("momentum")
        )

        candidate_results = generate_strategy_candidates(
            symbol=symbol,
            frame_15m=frame15,
            frame_5m=frame5,
            direction_15m=direction15,
            direction_5m=direction5,
            momentum_5m=momentum,
        )

        candidates = []
        decisions = []

        for result in candidate_results:
            candidate = result.get("candidate")
            if not candidate:
                continue

            decision = self.decider.evaluate(
                symbol=symbol,
                setup=candidate,
                momentum_score=momentum,
                as_of=date.today(),
            )

            candidates.append(candidate)
            decisions.append(decision)

        # Only simulate a paper position if a full decision gate passes.
        paper_events = []

        for decision, candidate in zip(decisions, candidates):
            if not decision.get("paper_candidate"):
                continue

            # Do not duplicate an already-open paper position of same
            # symbol+strategy+direction.
            already_open = any(
                p.status == "OPEN"
                and p.symbol == candidate["symbol"]
                and p.strategy == candidate["strategy"]
                and p.direction == candidate["direction"]
                for p in self.paper.positions
            )

            if already_open:
                continue

            result = self.paper.open_candidate(
                candidate,
                qty=1,
            )
            paper_events.append(result)

        # Manage existing paper positions with latest price.
        ltp = (
            market.get("live", {})
            .get("ltp", {})
            .get("price")
        )

        if ltp:
            paper_events.extend(
                self.paper.update_price(
                    symbol,
                    float(ltp),
                )
            )

        market_info = {}
        try:
            market_info = self.monitor.stream.store.diagnostics()
        except Exception:
            pass

        state_label = annotate(
            market,
            market_info.get(
                "market_info",
                {},
            ),
        )

        qualified = [
            d for d in decisions
            if d.get("paper_candidate")
        ]

        if qualified:
            status = "PAPER_CANDIDATE"
        elif candidates:
            status = "CANDIDATE_WAIT_GATE"
        elif state_label["market_state"]["mode"] == "HISTORICAL_BASELINE":
            status = "HISTORICAL_BASELINE_WAIT"
        else:
            status = "LIVE_WAIT"

        return {
            "market": market,
            "market_state": state_label["market_state"],
            "status": status,
            "candidates": candidates,
            "decisions": decisions,
            "paper_events": paper_events,
        }

    def run_once(self):
        results = {
            symbol: self.evaluate_symbol(symbol)
            for symbol in self.monitor.symbols
        }

        payload = {
            "results": results,
            "paper": self.paper.snapshot(),
            "execution": {
                "live_orders_placed": False,
                "paper_orders_placed": False,
            },
        }

        STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        STATE_FILE.write_text(
            json.dumps(
                payload,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        return payload

    def run_forever(self):
        print("=" * 78)
        print("JARVIS STRATEGY + PAPER ENGINE V3")
        print("=" * 78)
        print("Historical baseline labeling: ENABLED")
        print("Strategy matrix: ENABLED")
        print("R/R gate: ENABLED")
        print("BANKNIFTY expiry policy: ENABLED")
        print("Research gate: STRICT")
        print("Option gate: ENABLED")
        print("Paper simulation: ENABLED")
        print("Live orders: DISABLED")
        print()

        print(
            "Stream:",
            self.monitor.start_stream(),
        )

        while True:
            try:
                payload = self.run_once()

                for symbol, result in payload["results"].items():
                    market = result["market"]
                    print()
                    print(
                        f"{symbol} | "
                        f"STATE={result['status']} | "
                        f"SCORE={market.get('score')} | "
                        f"15m={market.get('15m', {}).get('direction')} | "
                        f"5m={market.get('5m', {}).get('direction')}"
                    )

                    if result["market_state"]["mode"] == "HISTORICAL_BASELINE":
                        print(
                            "  BASELINE: "
                            "market closed; no fresh live setup."
                        )

                    for c in result["candidates"]:
                        print(
                            "  CANDIDATE:",
                            c["strategy"],
                            c["direction"],
                            "ENTRY=", c["entry"],
                            "SL=", c["stop"],
                            "TP=", c["target"],
                            "R/R=", c["rr"],
                            "QUALITY=", c["setup_quality"],
                        )

                    for d in result["decisions"]:
                        print(
                            "  DECISION:",
                            d["decision"],
                            "|",
                            d["reason"],
                        )

                    for e in result["paper_events"]:
                        print(
                            "  PAPER EVENT:",
                            e,
                        )

                print()
                print(
                    "PAPER BOOK:",
                    payload["paper"],
                )

                time.sleep(self.poll_seconds)

            except KeyboardInterrupt:
                print(
                    "Stopping JARVIS Strategy + Paper V3."
                )
                break
            except Exception as exc:
                print(
                    "JARVIS V3 ERROR:",
                    exc,
                )
                time.sleep(self.poll_seconds)

        try:
            self.monitor.stop()
        except Exception:
            pass


if __name__ == "__main__":
    JarvisStrategyPaperV3().run_forever()
