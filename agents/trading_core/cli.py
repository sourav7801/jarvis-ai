
from __future__ import annotations

import argparse
import json

from .instrument_registry import REGISTRY
from .news_engine import NewsEngine
from .option_confirmation import OptionConfirmation
from .paper_broker import PaperBroker
from .research_gate import ResearchGate


def main():
    p = argparse.ArgumentParser("JARVIS Trading Agent V1")
    p.add_argument("--news", action="store_true")
    p.add_argument("--options", choices=["NIFTY", "BANKNIFTY", "SENSEX"])
    p.add_argument("--research", action="store_true")
    p.add_argument("--paper", action="store_true")
    p.add_argument("--symbols", action="store_true")
    args = p.parse_args()

    if args.news:
        print(json.dumps(NewsEngine().fetch(), indent=2, default=str))
    elif args.options:
        print(json.dumps(
            OptionConfirmation().confirm(args.options, "current_week"),
            indent=2,
            default=str,
        ))
    elif args.research:
        print(json.dumps(
            ResearchGate().validated(),
            indent=2,
            default=str,
        ))
    elif args.paper:
        print(json.dumps(
            PaperBroker().snapshot(),
            indent=2,
            default=str,
        ))
    elif args.symbols:
        print(json.dumps({
            k: {
                "display_name": v.display_name,
                "asset_class": v.asset_class,
                "exchange": v.exchange,
                "upstox": v.provider_symbols.get("UPSTOX"),
                "tradingview": v.provider_symbols.get("TRADINGVIEW"),
                "expiry_type": v.expiry_type,
            }
            for k, v in REGISTRY.items()
        }, indent=2))
    else:
        print("Use --news, --options SYMBOL, --research, --paper, or --symbols")


if __name__ == "__main__":
    main()
