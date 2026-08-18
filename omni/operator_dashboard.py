from __future__ import annotations

from pathlib import Path

import json


from omni.approval_queue import (
    approval_queue,
)


class OperatorDashboard:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "operator_v4"
                / "missions"
            )
        )


    @staticmethod
    def _records(
        directory,
    ):

        directory = Path(
            directory
        )


        if not directory.exists():

            return ()


        output = []


        for path in sorted(
            directory.glob(
                "*.json"
            )
        ):

            try:

                output.append(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:

                continue


        return tuple(
            output
        )


    def missions(
        self,
        limit=25,
    ):

        records = list(
            self._records(
                self.root
            )
        )


        records.sort(
            key=lambda item:
                float(
                    item.get(
                        "updated_at",
                        0,
                    )
                ),
            reverse=True,
        )


        return tuple(
            records[
                :max(
                    1,
                    int(
                        limit
                    ),
                )
            ]
        )


    def approval_batches(
        self,
        limit=50,
    ):

        root = (
            Path("data")
            / "approval_batches"
        )


        records = list(
            self._records(
                root
            )
        )


        records.sort(
            key=lambda item:
                float(
                    item.get(
                        "created_at",
                        0,
                    )
                ),
            reverse=True,
        )


        return tuple(
            records[
                :max(
                    1,
                    int(
                        limit
                    ),
                )
            ]
        )


    def pending_batches(
        self,
    ):

        return tuple(
            item

            for item
            in self.approval_batches()

            if (
                item.get(
                    "status"
                )
                == "pending"
            )
        )


    def snapshot(
        self,
    ):

        missions = self.missions(
            20
        )


        return {
            "pending_action_approvals":
                approval_queue.pending(),

            "pending_batches":
                self.pending_batches(),

            "missions":
                missions,

            "running_missions":
                tuple(
                    item

                    for item
                    in missions

                    if item.get(
                        "status"
                    )
                    in (
                        "ready",
                        "running",
                        "waiting_approval",
                        "needs_replan",
                    )
                ),

            "automatic_approval":
                False,

            "automatic_remote_git_write":
                False,

            "automatic_trading":
                False,
        }


operator_dashboard = (
    OperatorDashboard()
)
