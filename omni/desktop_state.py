from __future__ import annotations

from dataclasses import (
    dataclass,
)

import hashlib
import json
import time


from omni.semantic_ui import (
    semantic_ui,
)


@dataclass(frozen=True)
class DesktopSnapshot:

    timestamp: float

    window_titles: tuple[
        str,
        ...
    ]

    controls: tuple[
        dict,
        ...
    ]

    fingerprint: str


class DesktopState:

    def snapshot(
        self,
        *,
        window_title=None,
        include_controls=False,
    ):

        windows = (
            semantic_ui
            .windows()
        )


        titles = tuple(
            item[
                "title"
            ]
            for item
            in windows
        )


        controls = ()


        if (
            include_controls
            and window_title
        ):

            controls = (
                semantic_ui
                .controls(
                    window_title,
                    limit=150,
                )
            )


        raw = json.dumps(
            {
                "titles":
                    titles,

                "controls":
                    controls,
            },

            sort_keys=True,

            ensure_ascii=False,

            default=str,
        )


        return DesktopSnapshot(
            timestamp=
                time.time(),

            window_titles=
                titles,

            controls=
                tuple(
                    controls
                ),

            fingerprint=
                hashlib.sha256(
                    raw.encode(
                        "utf-8"
                    )
                ).hexdigest(),
        )


    @staticmethod
    def compare(
        before,
        after,
    ):

        before_windows = set(
            before.window_titles
        )

        after_windows = set(
            after.window_titles
        )


        before_controls = {
            (
                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "control_type",
                    ""
                ),

                item.get(
                    "automation_id",
                    ""
                ),
            )

            for item
            in before.controls
        }


        after_controls = {
            (
                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "control_type",
                    ""
                ),

                item.get(
                    "automation_id",
                    ""
                ),
            )

            for item
            in after.controls
        }


        return {
            "changed":
                before.fingerprint
                != after.fingerprint,

            "windows_opened":
                tuple(
                    sorted(
                        after_windows
                        - before_windows
                    )
                ),

            "windows_closed":
                tuple(
                    sorted(
                        before_windows
                        - after_windows
                    )
                ),

            "controls_added":
                tuple(
                    sorted(
                        after_controls
                        - before_controls
                    )
                ),

            "controls_removed":
                tuple(
                    sorted(
                        before_controls
                        - after_controls
                    )
                ),
        }


desktop_state = (
    DesktopState()
)
