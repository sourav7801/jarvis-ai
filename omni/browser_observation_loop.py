from __future__ import annotations

import hashlib
import json
import tempfile


from omni.approval_queue import (
    approval_queue,
)

from omni.persistent_browser import (
    persistent_browser,
)


class BrowserObservationLoop:

    @staticmethod
    def snapshot(
        page,
    ):

        elements = page.evaluate(
            """
            () => Array.from(
                document.querySelectorAll(
                    'a,button,input,textarea,select,[role],[aria-label]'
                )
            )
            .slice(0,250)
            .map((el,index) => {
                const r = el.getBoundingClientRect();

                return {
                    index,

                    tag:
                        (
                            el.tagName
                            || ''
                        ).toLowerCase(),

                    role:
                        el.getAttribute(
                            'role'
                        ) || '',

                    text:
                        (
                            el.innerText
                            || el.value
                            || el.getAttribute(
                                'aria-label'
                            )
                            || el.getAttribute(
                                'placeholder'
                            )
                            || ''
                        )
                        .trim()
                        .slice(0,500),

                    aria_label:
                        el.getAttribute(
                            'aria-label'
                        ) || '',

                    name:
                        el.getAttribute(
                            'name'
                        ) || '',

                    id:
                        el.id || '',

                    type:
                        el.getAttribute(
                            'type'
                        ) || '',

                    disabled:
                        !!el.disabled,

                    visible:
                        !!(
                            r.width
                            && r.height
                        )
                };
            })
            """
        )


        try:

            body = (
                page.locator(
                    "body"
                )
                .inner_text()[
                    :20000
                ]
            )

        except Exception:

            body = ""


        payload = {
            "url":
                page.url,

            "title":
                page.title(),

            "text":
                body,

            "elements":
                elements,
        }


        raw = json.dumps(
            payload,

            sort_keys=True,

            ensure_ascii=False,

            default=str,
        )


        payload[
            "fingerprint"
        ] = hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()


        return payload


    @staticmethod
    def compare(
        before,
        after,
    ):

        old = {
            (
                item.get(
                    "tag",
                    ""
                ),

                item.get(
                    "role",
                    ""
                ),

                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "id",
                    ""
                ),
            )

            for item
            in before.get(
                "elements",
                ()
            )
        }


        new = {
            (
                item.get(
                    "tag",
                    ""
                ),

                item.get(
                    "role",
                    ""
                ),

                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "id",
                    ""
                ),
            )

            for item
            in after.get(
                "elements",
                ()
            )
        }


        return {
            "changed":
                before[
                    "fingerprint"
                ]
                != after[
                    "fingerprint"
                ],

            "url_changed":
                before[
                    "url"
                ]
                != after[
                    "url"
                ],

            "title_changed":
                before[
                    "title"
                ]
                != after[
                    "title"
                ],

            "elements_added":
                tuple(
                    list(
                        new
                        - old
                    )[:100]
                ),

            "elements_removed":
                tuple(
                    list(
                        old
                        - new
                    )[:100]
                ),
        }


    @staticmethod
    def binding(
        operation,
        url,
        *,
        profile="default",
        selector=None,
        value=None,
    ):

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
                operation,
        }


        display = dict(
            payload
        )


        if selector is not None:

            selector = str(
                selector
            ).strip()


            if not selector:

                raise ValueError(
                    "Selector cannot be empty."
                )


            payload[
                "selector"
            ] = selector


            display[
                "selector"
            ] = selector


        if value is not None:

            value = str(
                value
            )


            payload[
                "value_hash"
            ] = hashlib.sha256(
                value.encode(
                    "utf-8"
                )
            ).hexdigest()


            payload[
                "length"
            ] = len(
                value
            )


            display[
                "preview"
            ] = value[:80]


        return {
            "action":
                (
                    "browser_observation."
                    + operation
                ),

            "payload":
                payload,

            "display":
                display,

            "risk":
                "browser-observed-action",
        }


    @staticmethod
    def _gate(
        binding,
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
                        binding[
                            "action"
                        ],

                        binding[
                            "payload"
                        ],

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,

            binding[
                "action"
            ],

            binding[
                "payload"
            ],
        )


        return None


    def observe(
        self,
        url,
        *,
        profile="default",
        approval_id=None,
    ):

        binding = self.binding(
            "observe",
            url,
            profile=profile,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            operation="observe",
        )


    def click(
        self,
        url,
        selector,
        *,
        profile="default",
        approval_id=None,
    ):

        binding = self.binding(
            "click",
            url,
            profile=profile,
            selector=selector,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            selector=selector,
            operation="click",
        )


    def fill(
        self,
        url,
        selector,
        value,
        *,
        profile="default",
        approval_id=None,
        sensitive=False,
    ):

        selector = str(
            selector
        )


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
                        "automation blocked."
                    ),
            }


        binding = self.binding(
            "fill",
            url,
            profile=profile,
            selector=selector,
            value=value,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            selector=selector,
            value=value,
            operation="fill",
        )


    def _run(
        self,
        url,
        *,
        profile="default",
        selector=None,
        value=None,
        operation="observe",
    ):

        from playwright.sync_api import (
            sync_playwright,
        )


        profile = (
            persistent_browser
            ._profile_name(
                profile
            )
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

            with sync_playwright() as p:

                context = (
                    p.chromium
                    .launch_persistent_context(
                        user_data_dir=
                            str(
                                directory
                            ),

                        headless=
                            True,

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
                    persistent_browser
                    ._validate_url(
                        url
                    ),

                    wait_until=
                        "domcontentloaded",

                    timeout=
                        30000,
                )


                before = self.snapshot(
                    page
                )


                if operation in (
                    "click",
                    "fill",
                ):

                    locator = page.locator(
                        selector
                    )


                    count = locator.count()


                    if count != 1:

                        context.close()


                        return {
                            "success":
                                False,

                            "error":
                                (
                                    "Selector must match "
                                    "exactly one element. "
                                    "Matches: "
                                    + str(
                                        count
                                    )
                                ),

                            "before":
                                before,
                        }


                    if operation == "click":

                        locator.click(
                            timeout=15000
                        )

                    else:

                        locator.fill(
                            str(
                                value
                            ),
                            timeout=15000,
                        )


                after = self.snapshot(
                    page
                )


                result = {
                    "success":
                        True,

                    "operation":
                        operation,

                    "before":
                        before,

                    "after":
                        after,

                    "comparison":
                        self.compare(
                            before,
                            after,
                        ),

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


    def provider_probe(
        self,
    ):

        from playwright.sync_api import (
            sync_playwright,
        )


        browser = None
        context = None


        try:

            with sync_playwright() as p:

                browser = (
                    p.chromium
                    .launch(
                        headless=True,
                    )
                )


                context = (
                    browser
                    .new_context(
                        accept_downloads=False,
                    )
                )


                page = (
                    context
                    .new_page()
                )


                page.set_content(
                    (
                        '<button id="save">'
                        'Save'
                        '</button>'
                        '<input aria-label="Name">'
                    )
                )


                snapshot = self.snapshot(
                    page
                )


                result = {
                    "success":
                        True,

                    "elements":
                        len(
                            snapshot[
                                "elements"
                            ]
                        ),

                    "has_save":
                        any(
                            item.get(
                                "text",
                                "",
                            )
                            .strip()
                            .lower()
                            == "save"

                            for item
                            in snapshot[
                                "elements"
                            ]
                        ),
                }


                context.close()
                context = None

                browser.close()
                browser = None


                return result


        except Exception as exc:

            if context is not None:

                try:
                    context.close()

                except Exception:
                    pass


            if browser is not None:

                try:
                    browser.close()

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



browser_observation_loop = (
    BrowserObservationLoop()
)
