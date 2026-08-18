
from __future__ import annotations

import argparse
import json

from .option_confirmation_v2 import OptionConfirmationV2
from .news_engine_v2 import NewsEngineV2
from .research_gate import ResearchGate


def main():
    p = argparse.ArgumentParser("JARVIS Trading Tools V2")
    p.add_argument("--options", choices=["NIFTY", "BANKNIFTY", "SENSEX"])
    p.add_argument("--news", action="store_true")
    p.add_argument("--research", action="store_true")
    args = p.parse_args()

    if args.options:
        result = OptionConfirmationV2().confirm(args.options)
    elif args.news:
        result = NewsEngineV2().fetch()
    elif args.research:
        result = ResearchGate().validated()
    else:
        result = {"message": "Use --options SYMBOL, --news or --research"}

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
