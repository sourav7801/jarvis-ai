from __future__ import annotations

from dataclasses import (
    dataclass,
)

import hashlib
import json
import time
import uuid


from omni.approval_queue import (
    approval_queue,
)

from omni.browser_observation_loop import (
    browser_observation_loop,
)

from omni.persistent_browser import (
    persistent_browser,
)


@dataclass
class BrowserTaskSession:

    session_id: str

    profile: str

    created_at: float

    last_used_at: float

    playwright: object

    context: object

    page: object


class LiveBrowserSessionManager:

    def __init__(
        self,
        max_sessions=3,
        idle_seconds=1800,
    ):

        self.max_sessions = max(
            1,
            min(
                int(
                    max_sessions
                ),
                5,
            ),
        )


        self.idle_seconds = max(
            60,
            min(
                int(
                    idle_seconds
                ),
                7200,
            ),
        )


        self._sessions = {}


    def _cleanup(
        self,
    ):

        now = time.time()


        expired = [
            session_id

            for session_id, session
            in self._sessions.items()

            if (
                now
                - session.last_used_at
                > self.idle_seconds
            )
        ]


        for session_id in expired:

            self.close(
                session_id
            )


    @staticmethod
    def _gate(
        action,
        payload,
        display,
        approval_id,
        risk="browser-live-action",
    ):

        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        action,

                        payload,

                        display=
                            display,

                        risk=
                            risk,
                    ),
            }


        approval_queue.consume(
            approval_id,
            action,
            payload,
        )


        return None


    def start(
        self,
        url,
        *,
        profile="operator-v3",
        approval_id=None,
        headless=True,
    ):

        self._cleanup()


        url = (
            persistent_browser
            ._validate_url(
                url
            )
        )


        profile = (
            persistent_browser
            ._profile_name(
                profile
            )
        )


        payload = {
            "url":
                url,

            "profile":
                profile,

            "operation":
                "session.start",

            "headless":
                bool(
                    headless
                ),
        }


        gate = self._gate(
            "live_browser.session.start",
            payload,
            payload,
            approval_id,
        )


        if gate:

            return gate


        if (
            len(
                self._sessions
            )
            >= self.max_sessions
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Maximum live browser "
                        "sessions reached."
                    ),
            }


        from playwright.sync_api import (
            sync_playwright,
        )


        playwright = (
            sync_playwright()
            .start()
        )


        directory = (
            persistent_browser
            .profile_path(
                profile
            )
        )


        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        try:

            context = (
                playwright.chromium
                .launch_persistent_context(
                    user_data_dir=
                        str(
                            directory
                        ),

                    headless=
                        bool(
                            headless
                        ),

                    accept_downloads=
                        False,
                )
            )


            page = (
                context.pages[
                    0
                ]
                if context.pages
                else context.new_page()
            )


            page.goto(
                url,

                wait_until=
                    "domcontentloaded",

                timeout=
                    30000,
            )


            session_id = (
                "browser-session-"
                + uuid.uuid4()
                .hex[:16]
            )


            now = time.time()


            self._sessions[
                session_id
            ] = BrowserTaskSession(
                session_id=
                    session_id,

                profile=
                    profile,

                created_at=
                    now,

                last_used_at=
                    now,

                playwright=
                    playwright,

                context=
                    context,

                page=
                    page,
            )


            return {
                "success":
                    True,

                "session_id":
                    session_id,

                "profile":
                    profile,

                "observation":
                    browser_observation_loop
                    .snapshot(
                        page
                    ),
            }


        except Exception as exc:

            try:

                playwright.stop()

            except Exception:

                pass


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


    def get(
        self,
        session_id,
    ):

        self._cleanup()


        session = self._sessions.get(
            str(
                session_id
            )
        )


        if session is None:

            raise KeyError(
                "Unknown or expired browser session."
            )


        session.last_used_at = (
            time.time()
        )


        return session


    def observe(
        self,
        session_id,
    ):

        session = self.get(
            session_id
        )


        return {
            "success":
                True,

            "session_id":
                session.session_id,

            "observation":
                browser_observation_loop
                .snapshot(
                    session.page
                ),
        }


    @staticmethod
    def _locator(
        page,
        target,
    ):

        if not isinstance(
            target,
            dict,
        ):

            raise TypeError(
                "Target must be a descriptor."
            )


        strategy = str(
            target.get(
                "strategy",
                ""
            )
        ).lower()


        value = str(
            target.get(
                "value",
                ""
            )
        )


        if strategy == "text":

            return page.get_by_text(
                value,
                exact=True,
            )


        if strategy == "label":

            return page.get_by_label(
                value,
                exact=True,
            )


        if strategy == "role":

            role = str(
                target.get(
                    "role",
                    ""
                )
            )


            name = str(
                target.get(
                    "name",
                    value,
                )
            )


            if not role:

                raise ValueError(
                    "Role target requires role."
                )


            return page.get_by_role(
                role,

                name=
                    name,

                exact=True,
            )


        if strategy == "css":

            return page.locator(
                value
            )


        if strategy == "id":

            return page.locator(
                (
                    "[id="
                    + json.dumps(
                        value
                    )
                    + "]"
                )
            )


        raise ValueError(
            "Unsupported target strategy."
        )


    def click(
        self,
        session_id,
        target,
        *,
        approval_id=None,
    ):

        session = self.get(
            session_id
        )


        payload = {
            "session_id":
                session.session_id,

            "operation":
                "click",

            "target":
                dict(
                    target
                ),
        }


        gate = self._gate(
            "live_browser.click",
            payload,
            payload,
            approval_id,
        )


        if gate:

            return gate


        before = (
            browser_observation_loop
            .snapshot(
                session.page
            )
        )


        try:

            locator = self._locator(
                session.page,
                target,
            )


            count = locator.count()


            if count != 1:

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Target must resolve to "
                            "exactly one element. "
                            "Matches: "
                            + str(
                                count
                            )
                        ),

                    "before":
                        before,
                }


            locator.click(
                timeout=15000
            )


            try:

                session.page.wait_for_load_state(
                    "domcontentloaded",

                    timeout=5000,
                )

            except Exception:

                pass


            after = (
                browser_observation_loop
                .snapshot(
                    session.page
                )
            )


            session.last_used_at = (
                time.time()
            )


            return {
                "success":
                    True,

                "session_id":
                    session.session_id,

                "before":
                    before,

                "after":
                    after,

                "comparison":
                    browser_observation_loop
                    .compare(
                        before,
                        after,
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

                "before":
                    before,
            }


    def fill(
        self,
        session_id,
        target,
        value,
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
                        "Sensitive/credential "
                        "entry is blocked."
                    ),
            }


        target_text = json.dumps(
            target,
            ensure_ascii=False,
        ).lower()


        if (
            "password"
            in target_text

            or "passwd"
            in target_text
        ):

            return {
                "success":
                    False,

                "error":
                    "Password target is blocked.",
            }


        session = self.get(
            session_id
        )


        value = str(
            value
        )


        payload = {
            "session_id":
                session.session_id,

            "operation":
                "fill",

            "target":
                dict(
                    target
                ),

            "value_hash":
                hashlib.sha256(
                    value.encode(
                        "utf-8"
                    )
                ).hexdigest(),

            "length":
                len(
                    value
                ),
        }


        display = {
            "session_id":
                session.session_id,

            "operation":
                "fill",

            "target":
                dict(
                    target
                ),

            "preview":
                value[:80],
        }


        gate = self._gate(
            "live_browser.fill",
            payload,
            display,
            approval_id,
        )


        if gate:

            return gate


        before = (
            browser_observation_loop
            .snapshot(
                session.page
            )
        )


        try:

            locator = self._locator(
                session.page,
                target,
            )


            count = locator.count()


            if count != 1:

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Target must resolve to "
                            "exactly one element. "
                            "Matches: "
                            + str(
                                count
                            )
                        ),

                    "before":
                        before,
                }


            locator.fill(
                value,
                timeout=15000,
            )


            after = (
                browser_observation_loop
                .snapshot(
                    session.page
                )
            )


            session.last_used_at = (
                time.time()
            )


            return {
                "success":
                    True,

                "session_id":
                    session.session_id,

                "before":
                    before,

                "after":
                    after,

                "comparison":
                    browser_observation_loop
                    .compare(
                        before,
                        after,
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

                "before":
                    before,
            }


    def close(
        self,
        session_id,
    ):

        session = self._sessions.pop(
            str(
                session_id
            ),
            None,
        )


        if session is None:

            return {
                "success":
                    False,

                "error":
                    "Session not found.",
            }


        try:

            session.context.close()

        finally:

            try:

                session.playwright.stop()

            except Exception:

                pass


        return {
            "success":
                True,

            "session_id":
                str(
                    session_id
                ),
        }


    def status(
        self,
    ):

        self._cleanup()


        return tuple(
            {
                "session_id":
                    session.session_id,

                "profile":
                    session.profile,

                "created_at":
                    session.created_at,

                "last_used_at":
                    session.last_used_at,

                "url":
                    session.page.url,

                "title":
                    session.page.title(),
            }

            for session
            in self._sessions.values()
        )


live_browser_sessions = (
    LiveBrowserSessionManager()
)
