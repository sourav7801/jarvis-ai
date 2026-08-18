from __future__ import annotations

from urllib.parse import (
    urlparse,
)


from omni.action_engine import (
    action_engine,
)


class BrowserActions:

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
                "are allowed."
            )


        if not parsed.netloc:

            raise ValueError(
                "URL must include a host."
            )


        return value


    def open(
        self,
        url,
        *,
        approved=False,
    ):

        value = (
            self.validate_url(
                url
            )
        )


        return action_engine.execute(
            "open_website",

            {
                "url":
                    value,
            },

            approved=
                approved,
        )


browser_actions = (
    BrowserActions()
)
