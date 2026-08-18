from __future__ import annotations

from pathlib import (
    Path,
)

import csv
import json
import os
import re
import uuid


class TradeJournal:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "backtests"
            )
        )


    @staticmethod
    def _name(
        value,
    ):

        value = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            str(
                value
            ),
        ).strip(
            "_"
        )


        return (
            value[:80]
            or "backtest"
        )


    def save(
        self,
        result,
        *,
        name=None,
    ):

        if not result.get(
            "research_only"
        ):

            raise ValueError(
                "Journal only accepts research results."
            )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        base = self._name(
            name
            or result.get(
                "strategy_id",
                "backtest",
            )
        )


        run_id = (
            uuid.uuid4()
            .hex[:12]
        )


        json_path = (
            self.root
            / (
                base
                + "_"
                + run_id
                + ".json"
            )
        )


        csv_path = (
            self.root
            / (
                base
                + "_"
                + run_id
                + "_trades.csv"
            )
        )


        temporary = (
            json_path
            .with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        os.replace(
            temporary,
            json_path,
        )


        trades = list(
            result.get(
                "trades",
                ()
            )
        )


        if trades:

            fields = sorted(
                {
                    key

                    for trade in trades

                    for key in trade
                }
            )


            with csv_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:

                writer = csv.DictWriter(
                    handle,
                    fieldnames=fields,
                )

                writer.writeheader()

                writer.writerows(
                    trades
                )


        return {
            "success":
                True,

            "json":
                str(
                    json_path
                ),

            "trades_csv":
                (
                    str(
                        csv_path
                    )
                    if trades
                    else None
                ),

            "research_only":
                True,
        }


trade_journal = (
    TradeJournal()
)
