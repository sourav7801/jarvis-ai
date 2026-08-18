from __future__ import annotations

import re

from omni.approval_queue import (
    approval_queue,
)


class SemanticUI:

    @staticmethod
    def available():

        try:
            import pywinauto
            return True

        except Exception:
            return False


    @staticmethod
    def _desktop():

        from pywinauto import (
            Desktop,
        )

        return Desktop(
            backend="uia"
        )


    def windows(self):

        if not self.available():

            return ()


        output = []


        try:

            windows = (
                self._desktop()
                .windows()
            )

        except Exception:

            return ()


        for window in windows:

            try:

                title = (
                    window.window_text()
                    or ""
                ).strip()


                if not title:
                    continue


                rectangle = (
                    window.rectangle()
                )


                output.append(
                    {
                        "title":
                            title,

                        "handle":
                            int(
                                window.handle
                            ),

                        "control_type":
                            str(
                                window
                                .element_info
                                .control_type
                                or ""
                            ),

                        "automation_id":
                            str(
                                window
                                .element_info
                                .automation_id
                                or ""
                            ),

                        "rect": {
                            "left":
                                int(
                                    rectangle.left
                                ),

                            "top":
                                int(
                                    rectangle.top
                                ),

                            "right":
                                int(
                                    rectangle.right
                                ),

                            "bottom":
                                int(
                                    rectangle.bottom
                                ),
                        },
                    }
                )

            except Exception:
                continue


        return tuple(
            output
        )


    def _window(
        self,
        title_contains,
    ):

        query = str(
            title_contains
        ).strip().lower()


        if not query:

            raise ValueError(
                "window title is required"
            )


        for window in (
            self._desktop()
            .windows()
        ):

            try:

                title = (
                    window.window_text()
                    or ""
                )


                if query in title.lower():

                    return window

            except Exception:
                continue


        return None


    def controls(
        self,
        window_title,
        *,
        text=None,
        control_type=None,
        automation_id=None,
        limit=100,
    ):

        window = self._window(
            window_title
        )


        if window is None:

            return ()


        limit = max(
            1,
            min(
                int(
                    limit
                ),
                500,
            ),
        )


        text_query = (
            str(
                text
            ).lower()
            if text
            else None
        )


        control_query = (
            str(
                control_type
            ).lower()
            if control_type
            else None
        )


        automation_query = (
            str(
                automation_id
            ).lower()
            if automation_id
            else None
        )


        output = []


        try:

            descendants = (
                window
                .descendants()
            )

        except Exception:

            descendants = []


        for control in descendants:

            try:

                info = (
                    control
                    .element_info
                )


                title = str(
                    control.window_text()
                    or ""
                )


                ctype = str(
                    info.control_type
                    or ""
                )


                auto_id = str(
                    info.automation_id
                    or ""
                )


                if (
                    text_query
                    and text_query
                    not in title.lower()
                ):
                    continue


                if (
                    control_query
                    and control_query
                    != ctype.lower()
                ):
                    continue


                if (
                    automation_query
                    and automation_query
                    != auto_id.lower()
                ):
                    continue


                rectangle = (
                    control.rectangle()
                )


                output.append(
                    {
                        "text":
                            title,

                        "control_type":
                            ctype,

                        "automation_id":
                            auto_id,

                        "enabled":
                            bool(
                                control.is_enabled()
                            ),

                        "visible":
                            bool(
                                control.is_visible()
                            ),

                        "rect": {
                            "left":
                                int(
                                    rectangle.left
                                ),

                            "top":
                                int(
                                    rectangle.top
                                ),

                            "right":
                                int(
                                    rectangle.right
                                ),

                            "bottom":
                                int(
                                    rectangle.bottom
                                ),
                        },
                    }
                )


                if len(
                    output
                ) >= limit:

                    break


            except Exception:
                continue


        return tuple(
            output
        )


    @staticmethod
    def _gate(
        action,
        payload,
        display,
        approval_id,
    ):

        if not approval_id:

            request = (
                approval_queue
                .request(
                    action,
                    payload,

                    display=
                        display,

                    risk=
                        "interactive-ui",
                )
            )


            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    request,
            }


        approval_queue.consume(
            approval_id,
            action,
            payload,
        )


        return None


    def _find_control(
        self,
        window_title,
        *,
        text=None,
        control_type=None,
        automation_id=None,
    ):

        window = self._window(
            window_title
        )


        if window is None:

            return (
                None,
                "Window not found."
            )


        text_query = (
            str(
                text
            ).lower()
            if text
            else None
        )


        type_query = (
            str(
                control_type
            ).lower()
            if control_type
            else None
        )


        id_query = (
            str(
                automation_id
            ).lower()
            if automation_id
            else None
        )


        try:

            descendants = (
                window
                .descendants()
            )

        except Exception as exc:

            return (
                None,
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
            )


        matches = []


        for control in descendants:

            try:

                info = (
                    control
                    .element_info
                )


                title = str(
                    control.window_text()
                    or ""
                )


                ctype = str(
                    info.control_type
                    or ""
                )


                auto_id = str(
                    info.automation_id
                    or ""
                )


                if (
                    text_query
                    and text_query
                    not in title.lower()
                ):
                    continue


                if (
                    type_query
                    and type_query
                    != ctype.lower()
                ):
                    continue


                if (
                    id_query
                    and id_query
                    != auto_id.lower()
                ):
                    continue


                matches.append(
                    control
                )


            except Exception:
                continue


        if not matches:

            return (
                None,
                "UI element not found."
            )


        if len(
            matches
        ) > 1:

            return (
                None,
                (
                    "UI selector is ambiguous: "
                    + str(
                        len(
                            matches
                        )
                    )
                    + " controls matched."
                ),
            )


        return (
            matches[0],
            None,
        )


    def click(
        self,
        window_title,
        *,
        text=None,
        control_type=None,
        automation_id=None,
        approval_id=None,
    ):

        payload = {
            "window_title":
                str(
                    window_title
                ),

            "text":
                text,

            "control_type":
                control_type,

            "automation_id":
                automation_id,
        }


        gate = self._gate(
            "semantic_ui.click",

            payload,

            payload,

            approval_id,
        )


        if gate:
            return gate


        control, error = (
            self._find_control(
                window_title,

                text=text,

                control_type=
                    control_type,

                automation_id=
                    automation_id,
            )
        )


        if control is None:

            return {
                "success":
                    False,

                "error":
                    error,
            }


        try:

            control.click_input()


            return {
                "success":
                    True,

                "window":
                    str(
                        window_title
                    ),

                "text":
                    text,

                "control_type":
                    control_type,

                "automation_id":
                    automation_id,
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            }


    def set_text(
        self,
        window_title,
        value,
        *,
        text=None,
        automation_id=None,
        approval_id=None,
        sensitive=False,
    ):

        if sensitive:

            return {
                "success":
                    False,

                "error":
                    (
                        "Sensitive/credential UI "
                        "entry is blocked."
                    ),
            }


        value = str(
            value
        )


        if len(
            value
        ) > 10000:

            raise ValueError(
                "UI text exceeds 10,000 characters."
            )


        payload = {
            "window_title":
                str(
                    window_title
                ),

            "text":
                text,

            "automation_id":
                automation_id,

            "length":
                len(
                    value
                ),

            "value_hash":
                __import__(
                    "hashlib"
                )
                .sha256(
                    value.encode(
                        "utf-8"
                    )
                )
                .hexdigest(),
        }


        gate = self._gate(
            "semantic_ui.set_text",

            payload,

            {
                "window_title":
                    str(
                        window_title
                    ),

                "target_text":
                    text,

                "automation_id":
                    automation_id,

                "preview":
                    value[:80],
            },

            approval_id,
        )


        if gate:
            return gate


        control, error = (
            self._find_control(
                window_title,

                text=text,

                control_type=
                    "Edit",

                automation_id=
                    automation_id,
            )
        )


        if control is None:

            return {
                "success":
                    False,

                "error":
                    error,
            }


        try:

            control.set_edit_text(
                value
            )


            return {
                "success":
                    True,

                "characters":
                    len(
                        value
                    ),
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            }


semantic_ui = (
    SemanticUI()
)
