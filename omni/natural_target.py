from __future__ import annotations


from omni.live_browser_session import (
    live_browser_sessions,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.target_fusion import (
    target_fusion,
)


class NaturalTargetResolver:

    @staticmethod
    def _dom_handle(
        candidate,
    ):

        item = candidate.payload


        text = str(
            item.get(
                "text",
                ""
            )
        ).strip()


        role = str(
            item.get(
                "role",
                ""
            )
        ).strip()


        aria = str(
            item.get(
                "aria_label",
                ""
            )
        ).strip()


        item_id = str(
            item.get(
                "id",
                ""
            )
        ).strip()


        if role and text:

            return {
                "strategy":
                    "role",

                "role":
                    role,

                "name":
                    text,

                "value":
                    text,
            }


        if aria:

            return {
                "strategy":
                    "label",

                "value":
                    aria,
            }


        if text:

            return {
                "strategy":
                    "text",

                "value":
                    text,
            }


        if item_id:

            return {
                "strategy":
                    "id",

                "value":
                    item_id,
            }


        return None


    def browser(
        self,
        session_id,
        phrase,
    ):

        observation = (
            live_browser_sessions
            .observe(
                session_id
            )
        )


        if not observation.get(
            "success",
            False,
        ):

            return observation


        dom = tuple(
            observation[
                "observation"
            ].get(
                "elements",
                ()
            )
            or ()
        )


        resolution = (
            target_fusion
            .resolve(
                phrase,
                dom=dom,
            )
        )


        handle = None


        if (
            resolution.resolved

            and resolution.best

            and (
                resolution.best.source
                == "dom"
            )
        ):

            handle = (
                self._dom_handle(
                    resolution.best
                )
            )


        return {
            "success":
                bool(
                    resolution.resolved
                    and handle
                ),

            "session_id":
                session_id,

            "phrase":
                str(
                    phrase
                ),

            "resolution":
                resolution,

            "target_handle":
                handle,

            "ambiguous":
                resolution.ambiguous,
        }


    def desktop(
        self,
        window_title,
        phrase,
    ):

        controls = (
            semantic_ui
            .controls(
                window_title,
                limit=250,
            )
        )


        resolution = (
            target_fusion
            .resolve(
                phrase,

                uia=
                    controls,
            )
        )


        handle = None


        if (
            resolution.resolved

            and resolution.best

            and (
                resolution.best.source
                == "uia"
            )
        ):

            item = (
                resolution.best.payload
            )


            handle = {
                "window_title":
                    str(
                        window_title
                    ),

                "text":
                    item.get(
                        "text"
                    ),

                "control_type":
                    item.get(
                        "control_type"
                    ),

                "automation_id":
                    item.get(
                        "automation_id"
                    ),
            }


        return {
            "success":
                bool(
                    resolution.resolved
                    and handle
                ),

            "phrase":
                str(
                    phrase
                ),

            "resolution":
                resolution,

            "target_handle":
                handle,

            "ambiguous":
                resolution.ambiguous,
        }


natural_target_resolver = (
    NaturalTargetResolver()
)
