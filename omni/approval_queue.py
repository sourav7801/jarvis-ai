from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from pathlib import Path

import hashlib
import json
import time
import uuid


@dataclass(frozen=True)
class ApprovalRequest:

    approval_id: str

    action: str

    payload_hash: str

    display: dict

    risk: str

    status: str

    created_at: float

    expires_at: float

    consumed_at: float | None = None


class ApprovalQueue:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "approvals"
            )
        )


    @staticmethod
    def _signature(
        action,
        payload,
    ):

        canonical = json.dumps(
            {
                "action":
                    str(action),

                "payload":
                    payload,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(
                ",",
                ":",
            ),
        )

        return hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()


    def _path(
        self,
        approval_id,
    ):

        return (
            self.root
            / (
                str(
                    approval_id
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
                "approval_id"
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
        approval_id,
    ):

        path = self._path(
            approval_id
        )

        if not path.exists():

            raise KeyError(
                "Unknown approval request."
            )


        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )


    def request(
        self,
        action,
        payload,
        *,
        display=None,
        risk="medium",
        ttl_seconds=900,
    ):

        ttl_seconds = max(
            30,
            min(
                int(
                    ttl_seconds
                ),
                3600,
            ),
        )

        now = time.time()

        record = {
            "approval_id":
                (
                    "approval-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "action":
                str(
                    action
                ),

            "payload_hash":
                self._signature(
                    action,
                    payload,
                ),

            "display":
                dict(
                    display
                    or {}
                ),

            "risk":
                str(
                    risk
                ),

            "status":
                "pending",

            "created_at":
                now,

            "expires_at":
                now
                + ttl_seconds,

            "consumed_at":
                None,
        }

        self._save(
            record
        )

        return record


    def approve(
        self,
        approval_id,
    ):

        record = self.get(
            approval_id
        )

        if (
            record[
                "status"
            ]
            != "pending"
        ):

            raise RuntimeError(
                "Approval is not pending."
            )


        if (
            time.time()
            > float(
                record[
                    "expires_at"
                ]
            )
        ):

            record[
                "status"
            ] = "expired"

            self._save(
                record
            )

            raise RuntimeError(
                "Approval expired."
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
        approval_id,
    ):

        record = self.get(
            approval_id
        )

        if (
            record[
                "status"
            ]
            != "pending"
        ):

            raise RuntimeError(
                "Approval is not pending."
            )


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


    def consume(
        self,
        approval_id,
        action,
        payload,
    ):

        record = self.get(
            approval_id
        )


        if (
            record[
                "status"
            ]
            != "approved"
        ):

            raise PermissionError(
                "Approval is not approved."
            )


        if (
            time.time()
            > float(
                record[
                    "expires_at"
                ]
            )
        ):

            record[
                "status"
            ] = "expired"

            self._save(
                record
            )

            raise PermissionError(
                "Approval expired."
            )


        expected = (
            self._signature(
                action,
                payload,
            )
        )


        if (
            expected
            != record[
                "payload_hash"
            ]
        ):

            raise PermissionError(
                "Approval does not match "
                "this action payload."
            )


        record[
            "status"
        ] = "consumed"

        record[
            "consumed_at"
        ] = time.time()

        self._save(
            record
        )

        return True


    def pending(self):

        if not self.root.exists():
            return ()


        output = []


        for path in self.root.glob(
            "approval-*.json"
        ):

            try:

                record = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                if (
                    record.get(
                        "status"
                    )
                    == "pending"
                ):

                    output.append(
                        record
                    )

            except Exception:
                continue


        return tuple(
            sorted(
                output,

                key=lambda item:
                    item.get(
                        "created_at",
                        0,
                    ),
            )
        )


approval_queue = (
    ApprovalQueue()
)
