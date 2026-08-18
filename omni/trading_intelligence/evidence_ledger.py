from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path

import json
import os
import uuid


class TradingEvidenceLedger:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "shadow"
            )
        )


        self.path = (
            self.root
            / "evidence.jsonl"
        )


    def append(
        self,
        event_type,
        payload,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        record = {
            "event_id":
                (
                    "evidence-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "event_type":
                str(
                    event_type
                ),

            "payload":
                payload,

            "research_only":
                True,

            "broker_order":
                False,
        }


        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )


        return record


    def recent(
        self,
        limit=100,
    ):

        limit = max(
            1,
            min(
                int(
                    limit
                ),
                1000,
            ),
        )


        if not self.path.exists():

            return ()


        lines = self.path.read_text(
            encoding="utf-8"
        ).splitlines()


        output = []


        for line in lines[
            -limit:
        ]:

            if not line.strip():
                continue

            output.append(
                json.loads(
                    line
                )
            )


        return tuple(
            output
        )
