from __future__ import annotations

import time


from omni.approval_queue import approval_queue


SENSITIVE_DISPLAY_KEYS = {
    "body",
    "body_preview",
    "message_body",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
}


def _sanitize(value):

    if isinstance(
        value,
        dict,
    ):
        output = {}

        for key, child in value.items():

            if str(
                key
            ).lower() in SENSITIVE_DISPLAY_KEYS:
                output[
                    str(key)
                ] = "<redacted>"

            else:
                output[
                    str(key)
                ] = _sanitize(
                    child
                )

        return output


    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _sanitize(item)
            for item in value
        ]


    return value


class ConnectedApprovalDashboard:

    def _pending_raw(self):

        value = approval_queue.pending()

        if value is None:
            return []

        if isinstance(
            value,
            dict,
        ):
            return list(
                value.values()
            )

        return list(value)


    @staticmethod
    def _service(action):

        action = str(
            action
            or ""
        )

        if action.startswith(
            "google.gmail."
        ):
            return "gmail"

        if action.startswith(
            "google.calendar."
        ):
            return "calendar"

        if action.startswith(
            "google.contacts."
        ):
            return "contacts"

        if action.startswith(
            "github."
        ):
            return "github"

        return "other"


    def pending(self):

        rows = []

        now = time.time()


        for item in self._pending_raw():

            if not isinstance(
                item,
                dict,
            ):
                continue


            action = item.get(
                "action"
            )


            if not (
                str(action).startswith(
                    "google."
                )
                or str(action).startswith(
                    "github."
                )
            ):
                continue


            expires_at = item.get(
                "expires_at"
            )


            rows.append(
                {
                    "approval_id": item.get(
                        "approval_id"
                    ),
                    "service": self._service(
                        action
                    ),
                    "action": action,
                    "risk": item.get(
                        "risk"
                    ),
                    "status": item.get(
                        "status"
                    ),
                    "created_at": item.get(
                        "created_at"
                    ),
                    "expires_at": expires_at,
                    "expired": bool(
                        expires_at
                        and float(expires_at) <= now
                    ),
                    "display": _sanitize(
                        item.get(
                            "display",
                            {},
                        )
                    ),
                }
            )


        rows.sort(
            key=lambda row:
                float(
                    row.get(
                        "created_at"
                    )
                    or 0
                ),
            reverse=True,
        )


        return {
            "success": True,
            "count": len(rows),
            "pending": tuple(rows),
            "automatic_approval": False,
        }


connected_approval_dashboard = ConnectedApprovalDashboard()
