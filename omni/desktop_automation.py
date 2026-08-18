from __future__ import annotations

import ctypes
from ctypes import wintypes

import hashlib
import time


from omni.approval_queue import (
    approval_queue,
)


user32 = ctypes.windll.user32


SW_RESTORE = 9

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_V = 0x56


class DesktopAutomation:

    def windows(self):

        output = []


        EnumWindowsProc = (
            ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HWND,
                wintypes.LPARAM,
            )
        )


        def callback(
            hwnd,
            lparam,
        ):

            if not user32.IsWindowVisible(
                hwnd
            ):

                return True


            length = user32.GetWindowTextLengthW(
                hwnd
            )


            if length <= 0:

                return True


            buffer = ctypes.create_unicode_buffer(
                length + 1
            )


            user32.GetWindowTextW(
                hwnd,
                buffer,
                length + 1,
            )


            title = buffer.value.strip()


            if not title:

                return True


            rect = wintypes.RECT()

            user32.GetWindowRect(
                hwnd,
                ctypes.byref(
                    rect
                ),
            )


            pid = wintypes.DWORD()

            user32.GetWindowThreadProcessId(
                hwnd,
                ctypes.byref(
                    pid
                ),
            )


            output.append(
                {
                    "hwnd":
                        int(
                            hwnd
                        ),

                    "title":
                        title,

                    "pid":
                        int(
                            pid.value
                        ),

                    "rect": {
                        "left":
                            int(
                                rect.left
                            ),

                        "top":
                            int(
                                rect.top
                            ),

                        "right":
                            int(
                                rect.right
                            ),

                        "bottom":
                            int(
                                rect.bottom
                            ),
                    },
                }
            )


            return True


        user32.EnumWindows(
            EnumWindowsProc(
                callback
            ),
            0,
        )


        return tuple(
            output
        )


    def find_window(
        self,
        title_contains,
    ):

        query = str(
            title_contains
        ).strip().lower()


        if not query:

            raise ValueError(
                "window title query required"
            )


        matches = [
            window

            for window
            in self.windows()

            if query
            in window[
                "title"
            ].lower()
        ]


        return (
            matches[0]
            if matches
            else None
        )


    @staticmethod
    def _approval_or_request(
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
                        "interactive",
                )
            )


            return {
                "approved":
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


    def focus_window(
        self,
        title_contains,
        *,
        approval_id=None,
    ):

        payload = {
            "title_contains":
                str(
                    title_contains
                ),
        }


        gate = (
            self._approval_or_request(
                "desktop.focus_window",

                payload,

                {
                    "window":
                        str(
                            title_contains
                        ),
                },

                approval_id,
            )
        )


        if gate:
            return gate


        window = self.find_window(
            title_contains
        )


        if window is None:

            return {
                "success":
                    False,

                "error":
                    "Window not found.",
            }


        hwnd = wintypes.HWND(
            window[
                "hwnd"
            ]
        )


        user32.ShowWindow(
            hwnd,
            SW_RESTORE,
        )


        success = bool(
            user32.SetForegroundWindow(
                hwnd
            )
        )


        return {
            "success":
                success,

            "window":
                window,
        }


    def click(
        self,
        x,
        y,
        *,
        approval_id=None,
    ):

        x = int(x)
        y = int(y)


        payload = {
            "x": x,
            "y": y,
        }


        gate = (
            self._approval_or_request(
                "desktop.click",

                payload,

                {
                    "x": x,
                    "y": y,
                },

                approval_id,
            )
        )


        if gate:
            return gate


        if not user32.SetCursorPos(
            x,
            y,
        ):

            return {
                "success":
                    False,

                "error":
                    "Unable to move cursor.",
            }


        user32.mouse_event(
            MOUSEEVENTF_LEFTDOWN,
            0,
            0,
            0,
            0,
        )

        user32.mouse_event(
            MOUSEEVENTF_LEFTUP,
            0,
            0,
            0,
            0,
        )


        return {
            "success":
                True,

            "x":
                x,

            "y":
                y,
        }


    @staticmethod
    def _paste_clipboard(
        text,
    ):

        import tkinter


        root = tkinter.Tk()

        root.withdraw()


        previous = None

        had_previous = False


        try:

            try:

                previous = (
                    root.clipboard_get()
                )

                had_previous = True

            except Exception:
                pass


            root.clipboard_clear()

            root.clipboard_append(
                text
            )

            root.update()


            user32.keybd_event(
                VK_CONTROL,
                0,
                0,
                0,
            )

            user32.keybd_event(
                VK_V,
                0,
                0,
                0,
            )

            user32.keybd_event(
                VK_V,
                0,
                KEYEVENTF_KEYUP,
                0,
            )

            user32.keybd_event(
                VK_CONTROL,
                0,
                KEYEVENTF_KEYUP,
                0,
            )


            time.sleep(
                0.15
            )


            if had_previous:

                root.clipboard_clear()

                root.clipboard_append(
                    previous
                )

                root.update()


        finally:

            root.destroy()


    def type_text(
        self,
        text,
        *,
        approval_id=None,
        sensitive=False,
    ):

        if sensitive:

            return {
                "success":
                    False,

                "error":
                    (
                        "Credential/sensitive text "
                        "entry is blocked in V2."
                    ),
            }


        text = str(
            text
        )


        if len(text) > 10000:

            raise ValueError(
                "Text input exceeds 10,000 characters."
            )


        digest = hashlib.sha256(
            text.encode(
                "utf-8"
            )
        ).hexdigest()


        payload = {
            "text_sha256":
                digest,

            "length":
                len(
                    text
                ),
        }


        display = {
            "length":
                len(
                    text
                ),

            "preview":
                (
                    text[:80]
                    + (
                        "..."
                        if len(
                            text
                        )
                        > 80
                        else ""
                    )
                ),
        }


        gate = (
            self._approval_or_request(
                "desktop.type_text",

                payload,

                display,

                approval_id,
            )
        )


        if gate:
            return gate


        self._paste_clipboard(
            text
        )


        return {
            "success":
                True,

            "characters":
                len(
                    text
                ),
        }


    def screen_snapshot(
        self,
        path,
        *,
        approval_id=None,
    ):

        payload = {
            "path":
                str(
                    path
                ),
        }


        gate = (
            self._approval_or_request(
                "desktop.screen_capture",

                payload,

                {
                    "path":
                        str(
                            path
                        ),
                },

                approval_id,
            )
        )


        if gate:
            return gate


        from PIL import (
            ImageGrab,
        )


        image = ImageGrab.grab(
            all_screens=True
        )


        from pathlib import Path

        destination = Path(
            path
        ).resolve()


        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        image.save(
            destination
        )


        return {
            "success":
                True,

            "path":
                str(
                    destination
                ),

            "width":
                image.width,

            "height":
                image.height,

            "visible_windows":
                len(
                    self.windows()
                ),
        }


desktop_automation = (
    DesktopAutomation()
)
