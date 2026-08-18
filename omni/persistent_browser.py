from __future__ import annotations

from pathlib import Path

import hashlib
import re
import tempfile


from omni.approval_queue import (
    approval_queue,
)


class PersistentBrowser:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "browser_profiles"
            )
        )


    @staticmethod
    def available():

        try:
            import playwright
            return True

        except Exception:
            return False


    @staticmethod
    def _profile_name(
        profile,
    ):

        value = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            str(
                profile
            ),
        ).strip(
            "_"
        )


        if not value:

            value = "default"


        return value[:80]


    def profile_path(
        self,
        profile="default",
    ):

        return (
            self.root
            / self._profile_name(
                profile
            )
        )


    @staticmethod
    def _validate_url(
        url,
    ):

        from urllib.parse import (
            urlparse,
        )


        value = str(
            url
        ).strip()


        parsed = urlparse(
            value
        )


        if parsed.scheme not in (
            "http",
            "https",
        ):

            raise ValueError(
                "Only http/https URLs are allowed."
            )


        if not parsed.netloc:

            raise ValueError(
                "URL must contain a host."
            )


        return value


    @staticmethod
    def _gate(
        action,
        payload,
        display,
        approval_id,
    ):

        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue
                    .request(
                        action,
                        payload,

                        display=
                            display,

                        risk=
                            "browser-session",
                    ),
            }


        approval_queue.consume(
            approval_id,
            action,
            payload,
        )


        return None


    def provider_probe(
        self,
    ):

        if not self.available():

            return {
                "success":
                    False,

                "error":
                    "Playwright is unavailable.",
            }


        from playwright.sync_api import (
            sync_playwright,
        )


        try:

            with tempfile.TemporaryDirectory() as tmp:

                with sync_playwright() as p:

                    context = (
                        p.chromium
                        .launch_persistent_context(
                            user_data_dir=
                                tmp,

                            headless=
                                True,

                            accept_downloads=
                                False,
                        )
                    )


                    page = (
                        context.pages[0]
                        if context.pages
                        else context.new_page()
                    )


                    page.goto(
                        "about:blank"
                    )


                    result = {
                        "success":
                            page.url
                            == "about:blank",
                    }


                    context.close()


                    return result


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


    def inspect(
        self,
        url,
        *,
        profile="default",
        approval_id=None,
        headless=True,
        max_chars=20000,
    ):

        url = self._validate_url(
            url
        )


        profile = self._profile_name(
            profile
        )


        payload = {
            "url":
                url,

            "profile":
                profile,

            "operation":
                "inspect",
        }


        gate = self._gate(
            "persistent_browser.inspect",

            payload,

            {
                "url":
                    url,

                "profile":
                    profile,
            },

            approval_id,
        )


        if gate:
            return gate


        from playwright.sync_api import (
            sync_playwright,
        )


        directory = self.profile_path(
            profile
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        max_chars = max(
            1000,
            min(
                int(
                    max_chars
                ),
                50000,
            ),
        )


        try:

            with sync_playwright() as p:

                context = (
                    p.chromium
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
                    context.pages[0]
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


                body = (
                    page.locator(
                        "body"
                    )
                    .inner_text()[
                        :max_chars
                    ]
                )


                result = {
                    "success":
                        True,

                    "url":
                        page.url,

                    "title":
                        page.title(),

                    "text":
                        body,

                    "profile":
                        profile,

                    "persistent":
                        True,
                }


                context.close()


                return result


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


    def click(
        self,
        url,
        selector,
        *,
        profile="default",
        approval_id=None,
        headless=True,
    ):

        url = self._validate_url(
            url
        )


        selector = str(
            selector
        ).strip()


        if not selector:

            raise ValueError(
                "selector is required"
            )


        profile = self._profile_name(
            profile
        )


        payload = {
            "url":
                url,

            "selector":
                selector,

            "profile":
                profile,

            "operation":
                "click",
        }


        gate = self._gate(
            "persistent_browser.click",

            payload,

            {
                "url":
                    url,

                "selector":
                    selector,

                "profile":
                    profile,
            },

            approval_id,
        )


        if gate:
            return gate


        from playwright.sync_api import (
            sync_playwright,
        )


        directory = self.profile_path(
            profile
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        try:

            with sync_playwright() as p:

                context = (
                    p.chromium
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
                    context.pages[0]
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


                matches = (
                    page.locator(
                        selector
                    )
                )


                count = matches.count()


                if count != 1:

                    context.close()


                    return {
                        "success":
                            False,

                        "error":
                            (
                                "Selector must identify "
                                "exactly one element. "
                                "Matches: "
                                + str(
                                    count
                                )
                            ),
                    }


                matches.click(
                    timeout=15000
                )


                result = {
                    "success":
                        True,

                    "url":
                        page.url,

                    "title":
                        page.title(),

                    "profile":
                        profile,
                }


                context.close()


                return result


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


    def fill(
        self,
        url,
        selector,
        value,
        *,
        profile="default",
        approval_id=None,
        headless=True,
        sensitive=False,
    ):

        url = self._validate_url(
            url
        )


        selector = str(
            selector
        ).strip()


        if (
            sensitive

            or "password"
            in selector.lower()

            or "passwd"
            in selector.lower()
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Credential/password "
                        "automation is blocked."
                    ),
            }


        value = str(
            value
        )


        if len(
            value
        ) > 10000:

            raise ValueError(
                "Input exceeds 10,000 characters."
            )


        profile = self._profile_name(
            profile
        )


        payload = {
            "url":
                url,

            "selector":
                selector,

            "profile":
                profile,

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

            "operation":
                "fill",
        }


        gate = self._gate(
            "persistent_browser.fill",

            payload,

            {
                "url":
                    url,

                "selector":
                    selector,

                "profile":
                    profile,

                "preview":
                    value[:80],
            },

            approval_id,
        )


        if gate:
            return gate


        from playwright.sync_api import (
            sync_playwright,
        )


        directory = self.profile_path(
            profile
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        try:

            with sync_playwright() as p:

                context = (
                    p.chromium
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
                    context.pages[0]
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


                matches = (
                    page.locator(
                        selector
                    )
                )


                count = matches.count()


                if count != 1:

                    context.close()


                    return {
                        "success":
                            False,

                        "error":
                            (
                                "Selector must identify "
                                "exactly one element. "
                                "Matches: "
                                + str(
                                    count
                                )
                            ),
                    }


                matches.fill(
                    value,
                    timeout=15000,
                )


                result = {
                    "success":
                        True,

                    "url":
                        page.url,

                    "title":
                        page.title(),

                    "profile":
                        profile,
                }


                context.close()


                return result


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


persistent_browser = (
    PersistentBrowser()
)
