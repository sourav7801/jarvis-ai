from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


from omni.approval_queue import (
    approval_queue,
)


class ApprovalBatchQueue:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "approval_batches"
            )
        )


    def _path(
        self,
        batch_id,
    ):

        return (
            self.root
            / (
                str(
                    batch_id
                )
                + ".json"
            )
        )


    def _save(
        self,
        record,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        path = self._path(
            record[
                "batch_id"
            ]
        )


        temp = path.with_suffix(
            ".tmp"
        )


        temp.write_text(
            json.dumps(
                record,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )


        temp.replace(
            path
        )


    def get(
        self,
        batch_id,
    ):

        path = self._path(
            batch_id
        )


        if not path.exists():

            raise KeyError(
                "Unknown approval batch."
            )


        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )


    def create(
        self,
        goal,
        bindings,
    ):

        children = []


        for binding in bindings:

            approval = (
                approval_queue
                .request(
                    binding[
                        "action"
                    ],

                    binding[
                        "payload"
                    ],

                    display=
                        binding.get(
                            "display",
                            {},
                        ),

                    risk=
                        binding.get(
                            "risk",
                            "interactive",
                        ),
                )
            )


            children.append(
                {
                    "step_id":
                        binding[
                            "step_id"
                        ],

                    "approval_id":
                        approval[
                            "approval_id"
                        ],

                    "action":
                        binding[
                            "action"
                        ],

                    "display":
                        binding.get(
                            "display",
                            {},
                        ),
                }
            )


        record = {
            "batch_id":
                (
                    "batch-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "goal":
                str(
                    goal
                ),

            "status":
                "pending",

            "children":
                children,

            "created_at":
                time.time(),
        }


        self._save(
            record
        )


        return record


    def approve(
        self,
        batch_id,
    ):

        record = self.get(
            batch_id
        )


        if (
            record[
                "status"
            ]
            != "pending"
        ):

            raise RuntimeError(
                "Approval batch is not pending."
            )


        approved = []


        for child in record[
            "children"
        ]:

            approval_queue.approve(
                child[
                    "approval_id"
                ]
            )

            approved.append(
                child[
                    "approval_id"
                ]
            )


        record[
            "status"
        ] = "approved"


        record[
            "approved_at"
        ] = time.time()


        self._save(
            record
        )


        return record


    def reject(
        self,
        batch_id,
    ):

        record = self.get(
            batch_id
        )


        if (
            record[
                "status"
            ]
            != "pending"
        ):

            raise RuntimeError(
                "Approval batch is not pending."
            )


        for child in record[
            "children"
        ]:

            try:

                approval_queue.reject(
                    child[
                        "approval_id"
                    ]
                )

            except Exception:
                pass


        record[
            "status"
        ] = "rejected"


        record[
            "rejected_at"
        ] = time.time()


        self._save(
            record
        )


        return record


    def token_for_step(
        self,
        batch_id,
        step_id,
    ):

        record = self.get(
            batch_id
        )


        if (
            record[
                "status"
            ]
            != "approved"
        ):

            return None


        for child in record[
            "children"
        ]:

            if (
                child[
                    "step_id"
                ]
                == step_id
            ):

                return child[
                    "approval_id"
                ]


        return None


approval_batches = (
    ApprovalBatchQueue()
)
