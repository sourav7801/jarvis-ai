from __future__ import annotations

from pathlib import Path

import time


from omni.desktop_automation import (
    desktop_automation,
)

from omni.semantic_ui import (
    semantic_ui,
)


class ScreenPerception:

    def frame(
        self,
        path,
        *,
        approval_id=None,
    ):

        result = (
            desktop_automation
            .screen_snapshot(
                path,

                approval_id=
                    approval_id,
            )
        )


        if not result.get(
            "success",
            False,
        ):

            return result


        image_path = Path(
            result[
                "path"
            ]
        )


        return {
            **result,

            "captured_at":
                time.time(),

            "semantic_windows":
                semantic_ui.windows(),

            "vision_provider_configured":
                False,
        }


    def analyze_existing(
        self,
        path,
        *,
        provider=None,
    ):

        image_path = Path(
            path
        ).resolve()


        if not image_path.exists():

            raise FileNotFoundError(
                image_path
            )


        from PIL import Image


        with Image.open(
            image_path
        ) as image:

            metadata = {
                "path":
                    str(
                        image_path
                    ),

                "width":
                    image.width,

                "height":
                    image.height,

                "mode":
                    image.mode,

                "semantic_windows":
                    semantic_ui.windows(),
            }


        if provider is None:

            return {
                **metadata,

                "vision_provider_configured":
                    False,

                "description":
                    None,
            }


        if not callable(
            provider
        ):

            raise TypeError(
                "vision provider must be callable"
            )


        description = provider(
            metadata
        )


        return {
            **metadata,

            "vision_provider_configured":
                True,

            "description":
                description,
        }


screen_perception = (
    ScreenPerception()
)
