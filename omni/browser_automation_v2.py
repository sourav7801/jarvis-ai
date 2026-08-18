from __future__ import annotations

import hashlib
import importlib.util

from urllib.parse import (
    urlparse,
)


from omni.approval_queue import (
    approval_queue,
)


class BrowserAutomation:

    @staticmethod
    def available():

        return (
            importlib.util.find_spec(
                "playwright"
            )
            is not None
        )


    @staticmethod
    def validate_url(
        url,
    ):

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
                "Only http/https URLs "
                "are permitted."
            )


        if not parsed.netloc:

            raise ValueError(
                "URL requires a host."
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
                            "external-network",
                    ),
            }


        approval_queue.consume(
            approval_id,
            action,
            payload,
        )


        return None


    def inspect(
        self,
        url,
        *,
        approval_id=None,
        max_chars=12000,
    ):

        url = self.validate_url(
            url
        )


        payload = {
            "url":
                url,

            "operation":
                "inspect",
        }


        gate = self._gate(
            "browser.inspect",

            payload,

            {
                "url":
                    url,

                "operation":
                    "navigate/read",
            },

            approval_id,
        )


        if gate:
            return gate


        if not self.available():

            return {
                "success":
                    False,

                "error":
                    "Playwright is not installed.",

                "provider":
                    "playwright",
            }


        from playwright.sync_api import (
            sync_playwright,
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

                browser = (
                    p.chromium.launch(
                        headless=True
                    )
                )

                page = browser.new_page()


                page.goto(
                    url,
                    wait_until=
                        "domcontentloaded",
                    timeout=30000,
                )


                result = {
                    "success":
                        True,

                    "url":
                        page.url,

                    "title":
                        page.title(),

                    "text":
                        page.locator(
                            "body"
                        )
                        .inner_text()[
                            :max_chars
                        ],
                }


                browser.close()


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

                "provider":
                    "playwright",
            }


    def click(
        self,
        url,
        selector,
        *,
        approval_id=None,
    ):

        url = self.validate_url(
            url
        )

        selector = str(
            selector
        ).strip()


        if not selector:

            raise ValueError(
                "selector cannot be empty"
            )


        payload = {
            "url":
                url,

            "selector":
                selector,

            "operation":
                "click",
        }


        gate = self._gate(
            "browser.click",

            payload,

            {
                "url":
                    url,

                "selector":
                    selector,
            },

            approval_id,
        )


        if gate:
            return gate


        if not self.available():

            return {
                "success":
                    False,

                "error":
                    "Playwright is not installed.",
            }


        from playwright.sync_api import (
            sync_playwright,
        )


        try:

            with sync_playwright() as p:

                browser = (
                    p.chromium.launch(
                        headless=True
                    )
                )

                page = browser.new_page()


                page.goto(
                    url,
                    wait_until=
                        "domcontentloaded",
                    timeout=30000,
                )


                page.locator(
                    selector
                ).first.click(
                    timeout=15000
                )


                result = {
                    "success":
                        True,

                    "url":
                        page.url,

                    "title":
                        page.title(),
                }


                browser.close()


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
        approval_id=None,
        sensitive=False,
    ):

        url = self.validate_url(
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
                        "Credential/password field "
                        "automation is blocked in V2."
                    ),
            }


        value = str(
            value
        )


        if len(value) > 10000:

            raise ValueError(
                "Browser input is too large."
            )


        digest = hashlib.sha256(
            value.encode(
                "utf-8"
            )
        ).hexdigest()


        payload = {
            "url":
                url,

            "selector":
                selector,

            "value_sha256":
                digest,

            "length":
                len(
                    value
                ),

            "operation":
                "fill",
        }


        gate = self._gate(
            "browser.fill",

            payload,

            {
                "url":
                    url,

                "selector":
                    selector,

                "value_preview":
                    value[:80],
            },

            approval_id,
        )


        if gate:
            return gate


        if not self.available():

            return {
                "success":
                    False,

                "error":
                    "Playwright is not installed.",
            }


        from playwright.sync_api import (
            sync_playwright,
        )


        try:

            with sync_playwright() as p:

                browser = (
                    p.chromium.launch(
                        headless=True
                    )
                )

                page = browser.new_page()


                page.goto(
                    url,
                    wait_until=
                        "domcontentloaded",
                    timeout=30000,
                )


                page.locator(
                    selector
                ).first.fill(
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
                }


                browser.close()


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


browser_automation = (
    BrowserAutomation()
)
