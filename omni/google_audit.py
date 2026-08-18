from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


BLOCKED_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "credentials",
    "client_secret",
    "raw",
    "body",
    "message_body",
    "password",
    "secret",
}


def _sanitize(
    value,
):

    if isinstance(
        value,
        dict,
    ):

        output = {}


        for key, child in value.items():

            key_text = str(
                key
            )


            if (
                key_text.lower()
                in BLOCKED_KEYS
            ):

                output[
                    key_text
                ] = "<redacted>"

            else:

                output[
                    key_text
                ] = _sanitize(
                    child
                )


        return output


    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return [
            _sanitize(
                child
            )

            for child
            in value
        ]


    text = str(
        value
    )


    if len(
        text
    ) > 1000:

        return (
            text[:1000]
            + "..."
        )


    return value


class GoogleAudit:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "audit"
                / "google_services.jsonl"
            )
        )


    def record(
        self,
        action,
        *,
        success,
        metadata=None,
        error=None,
    ):

        record = {
            "audit_id":
                (
                    "google-audit-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "timestamp":
                time.time(),

            "action":
                str(
                    action
                ),

            "success":
                bool(
                    success
                ),

            "metadata":
                _sanitize(
                    metadata
                    or {}
                ),

            "error":
                (
                    str(
                        error
                    )[:1000]
                    if error
                    else None
                ),
        }


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


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


        return record


google_audit = (
    GoogleAudit()
)
