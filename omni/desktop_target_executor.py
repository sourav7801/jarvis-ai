from __future__ import annotations

from pathlib import Path

import ctypes
import hashlib
import math
import time


from PIL import (
    Image,
)


from omni.approval_queue import (
    approval_queue,
)

from omni.computer_operator import (
    ComputerOperator,
)

from omni.natural_target import (
    natural_target_resolver,
)

from omni.operator_schema import (
    OperatorStep,
)

from omni.perception_fusion import (
    perception_fusion,
)

from omni.semantic_ui import (
    semantic_ui,
)


class DesktopTargetExecutor:

    VISUAL_MIN_CONFIDENCE = 0.90

    VISUAL_APPROVAL_TTL = 120


    @staticmethod
    def _screen_size(
        self=None,
    ):

        user32 = ctypes.windll.user32

        return (
            int(
                user32.GetSystemMetrics(
                    0
                )
            ),

            int(
                user32.GetSystemMetrics(
                    1
                )
            ),
        )


    @staticmethod
    def _file_sha(
        path,
    ):

        return hashlib.sha256(
            Path(
                path
            ).read_bytes()
        ).hexdigest()


    def _visual_candidate(
        self,
        screenshot,
        window_title,
        target,
    ):

        path = Path(
            screenshot
        ).resolve()


        if not path.exists():

            return {
                "success":
                    False,

                "error":
                    "Screenshot does not exist.",
            }


        result = (
            perception_fusion
            .analyze_existing(
                path,

                window_title=
                    window_title,

                target=
                    target,
            )
        )


        resolution = result.get(
            "target_resolution"
        )


        if (
            resolution is None
            or not resolution.resolved
            or resolution.best is None
        ):

            return {
                "success":
                    False,

                "error":
                    "Visual target not resolved.",
            }


        if (
            resolution.best.source
            != "vision"
        ):

            return {
                "success":
                    False,

                "error":
                    "Best fallback target was not vision.",
            }


        item = (
            resolution.best.payload
        )


        try:

            x = float(
                item[
                    "x"
                ]
            )

            y = float(
                item[
                    "y"
                ]
            )

            confidence = float(
                item.get(
                    "confidence",
                    0.0,
                )
            )

        except Exception:

            return {
                "success":
                    False,

                "error":
                    "Vision coordinates invalid.",
            }


        if (
            not math.isfinite(
                x
            )
            or not math.isfinite(
                y
            )
        ):

            return {
                "success":
                    False,

                "error":
                    "Vision coordinates non-finite.",
            }


        if (
            confidence
            < self.VISUAL_MIN_CONFIDENCE
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Vision confidence below "
                        "coordinate threshold."
                    ),
            }


        with Image.open(
            path
        ) as image:

            image_width, image_height = (
                image.size
            )


        screen_width, screen_height = (
            self._screen_size()
        )


        # Coordinate execution is only safe when
        # the screenshot corresponds to the full
        # current screen coordinate space.
        if (
            image_width
            != screen_width

            or image_height
            != screen_height
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Vision coordinate execution "
                        "requires a full-screen screenshot "
                        "matching current screen dimensions."
                    ),

                "image_size":
                    (
                        image_width,
                        image_height,
                    ),

                "screen_size":
                    (
                        screen_width,
                        screen_height,
                    ),
            }


        if not (
            0
            <= x
            < screen_width

            and 0
            <= y
            < screen_height
        ):

            return {
                "success":
                    False,

                "error":
                    "Vision coordinate out of bounds.",
            }


        prepared_at = (
            time.time()
        )


        payload = {
            "target":
                str(
                    target
                ),

            "x":
                int(
                    round(
                        x
                    )
                ),

            "y":
                int(
                    round(
                        y
                    )
                ),

            "confidence":
                confidence,

            "screenshot":
                str(
                    path
                ),

            "screenshot_sha256":
                self._file_sha(
                    path
                ),

            "prepared_at":
                prepared_at,
        }


        return {
            "success":
                True,

            "mode":
                "vision-coordinate",

            "resolution":
                resolution,

            "payload":
                payload,

            "binding": {
                "action":
                    "v4.desktop.coordinate_click",

                "payload":
                    payload,

                "display": {
                    "target":
                        str(
                            target
                        ),

                    "x":
                        payload[
                            "x"
                        ],

                    "y":
                        payload[
                            "y"
                        ],

                    "confidence":
                        confidence,

                    "warning":
                        (
                            "Vision-only coordinate "
                            "fallback"
                        ),
                },

                "risk":
                    "visual-coordinate-click",
            },
        }


    def prepare_click(
        self,
        window_title,
        target,
        *,
        screenshot=None,
    ):

        resolution = (
            natural_target_resolver
            .desktop(
                window_title,
                target,
            )
        )


        if resolution.get(
            "success",
            False,
        ):

            handle = resolution[
                "target_handle"
            ]


            step = OperatorStep(
                step_id=
                    "desktop-click",

                action=
                    "ui.click",

                payload={
                    "window_title":
                        handle[
                            "window_title"
                        ],

                    "text":
                        handle.get(
                            "text"
                        ),

                    "control_type":
                        handle.get(
                            "control_type"
                        ),

                    "automation_id":
                        handle.get(
                            "automation_id"
                        ),
                },
            )


            binding = (
                ComputerOperator
                .binding_for_step(
                    step
                )
            )


            return {
                "success":
                    True,

                "mode":
                    "uia",

                "resolution":
                    resolution,

                "handle":
                    handle,

                "binding":
                    binding,
            }


        if screenshot:

            return self._visual_candidate(
                screenshot,
                window_title,
                target,
            )


        return {
            "success":
                False,

            "error":
                (
                    "Desktop target was not "
                    "uniquely resolved."
                ),

            "resolution":
                resolution,
        }


    def prepare_set_text(
        self,
        window_title,
        target,
        value,
        *,
        sensitive=False,
    ):

        if sensitive:

            return {
                "success":
                    False,

                "error":
                    "Sensitive text entry blocked.",
            }


        target_lower = str(
            target
        ).lower()


        if (
            "password"
            in target_lower

            or "passwd"
            in target_lower

            or "credential"
            in target_lower
        ):

            return {
                "success":
                    False,

                "error":
                    "Credential target blocked.",
            }


        resolution = (
            natural_target_resolver
            .desktop(
                window_title,
                target,
            )
        )


        if not resolution.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Text target was not "
                        "uniquely resolved."
                    ),

                "resolution":
                    resolution,
            }


        handle = resolution[
            "target_handle"
        ]


        step = OperatorStep(
            step_id=
                "desktop-set-text",

            action=
                "ui.set_text",

            payload={
                "window_title":
                    handle[
                        "window_title"
                    ],

                "text":
                    handle.get(
                        "text"
                    ),

                "automation_id":
                    handle.get(
                        "automation_id"
                    ),

                "value":
                    str(
                        value
                    ),

                "sensitive":
                    False,
            },
        )


        binding = (
            ComputerOperator
            .binding_for_step(
                step
            )
        )


        return {
            "success":
                True,

            "mode":
                "uia",

            "resolution":
                resolution,

            "handle":
                handle,

            "binding":
                binding,
        }


    @staticmethod
    def _coordinate_click(
        x,
        y,
    ):

        user32 = ctypes.windll.user32


        if not user32.SetCursorPos(
            int(
                x
            ),
            int(
                y
            ),
        ):

            raise RuntimeError(
                "SetCursorPos failed."
            )


        LEFT_DOWN = 0x0002
        LEFT_UP = 0x0004


        user32.mouse_event(
            LEFT_DOWN,
            0,
            0,
            0,
            0,
        )


        user32.mouse_event(
            LEFT_UP,
            0,
            0,
            0,
            0,
        )


    def execute_click(
        self,
        prepared,
        approval_id,
    ):

        if not prepared.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Prepared target is invalid.",
            }


        mode = prepared[
            "mode"
        ]


        if mode == "uia":

            handle = prepared[
                "handle"
            ]


            return semantic_ui.click(
                handle[
                    "window_title"
                ],

                text=
                    handle.get(
                        "text"
                    ),

                control_type=
                    handle.get(
                        "control_type"
                    ),

                automation_id=
                    handle.get(
                        "automation_id"
                    ),

                approval_id=
                    approval_id,
            )


        if (
            mode
            == "vision-coordinate"
        ):

            payload = prepared[
                "payload"
            ]


            if (
                time.time()
                - float(
                    payload[
                        "prepared_at"
                    ]
                )
                > self.VISUAL_APPROVAL_TTL
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Visual coordinate approval "
                            "expired; capture a new screen."
                        ),
                }


            screenshot = Path(
                payload[
                    "screenshot"
                ]
            )


            if (
                not screenshot.exists()

                or self._file_sha(
                    screenshot
                )
                != payload[
                    "screenshot_sha256"
                ]
            ):

                return {
                    "success":
                        False,

                    "error":
                        "Screenshot changed after approval.",
                }


            binding = prepared[
                "binding"
            ]


            approval_queue.consume(
                approval_id,

                binding[
                    "action"
                ],

                binding[
                    "payload"
                ],
            )


            self._coordinate_click(
                payload[
                    "x"
                ],

                payload[
                    "y"
                ],
            )


            return {
                "success":
                    True,

                "mode":
                    "vision-coordinate",

                "x":
                    payload[
                        "x"
                    ],

                "y":
                    payload[
                        "y"
                    ],
            }


        return {
            "success":
                False,

            "error":
                "Unknown desktop execution mode.",
        }


    def execute_set_text(
        self,
        prepared,
        value,
        approval_id,
    ):

        if not prepared.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Prepared target is invalid.",
            }


        handle = prepared[
            "handle"
        ]


        return semantic_ui.set_text(
            handle[
                "window_title"
            ],

            str(
                value
            ),

            text=
                handle.get(
                    "text"
                ),

            automation_id=
                handle.get(
                    "automation_id"
                ),

            approval_id=
                approval_id,

            sensitive=
                False,
        )


desktop_target_executor = (
    DesktopTargetExecutor()
)
