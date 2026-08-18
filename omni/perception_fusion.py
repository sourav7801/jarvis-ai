from __future__ import annotations

from pathlib import Path


from omni.desktop_automation import (
    desktop_automation,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.target_fusion import (
    target_fusion,
)

from omni.vision_runtime import (
    vision_runtime,
)


class PerceptionFusion:

    def analyze_existing(
        self,
        screenshot,
        *,
        window_title=None,
        target=None,
    ):

        path = Path(
            screenshot
        ).resolve()


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        controls = (
            semantic_ui.controls(
                window_title,
                limit=250,
            )

            if window_title

            else ()
        )


        vision_result = (
            vision_runtime
            .analyze(
                path
            )
        )


        vision_elements = ()


        if vision_result.get(
            "success",
            False,
        ):

            vision_elements = tuple(
                vision_result
                .get(
                    "analysis",
                    {}
                )
                .get(
                    "elements",
                    ()
                )
                or ()
            )


        resolution = None


        if target:

            resolution = (
                target_fusion
                .resolve(
                    target,

                    uia=
                        controls,

                    vision=
                        vision_elements,
                )
            )


        return {
            "success":
                bool(
                    vision_result.get(
                        "success",
                        False,
                    )
                ),

            "screenshot":
                str(
                    path
                ),

            "window_title":
                window_title,

            "uia_controls":
                controls,

            "vision":
                vision_result,

            "target_resolution":
                resolution,
        }


    def capture_and_analyze(
        self,
        screenshot_path,
        *,
        window_title=None,
        target=None,
        approval_id=None,
    ):

        capture = (
            desktop_automation
            .screen_snapshot(
                screenshot_path,

                approval_id=
                    approval_id,
            )
        )


        if not capture.get(
            "success",
            False,
        ):

            return capture


        return self.analyze_existing(
            capture[
                "path"
            ],

            window_title=
                window_title,

            target=
                target,
        )


perception_fusion = (
    PerceptionFusion()
)
