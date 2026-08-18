from __future__ import annotations

from email.message import (
    EmailMessage,
)

import base64
import hashlib


from omni.approval_queue import (
    approval_queue,
)

from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


class GmailService:

    @staticmethod
    def _decode(
        value,
    ):

        if not value:

            return ""


        value = str(
            value
        )


        value += (
            "="
            * (
                -len(
                    value
                )
                % 4
            )
        )


        try:

            return (
                base64.urlsafe_b64decode(
                    value
                )
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except Exception:

            return ""


    @classmethod
    def _parts(
        cls,
        part,
    ):

        plain = []

        html = []


        mime_type = str(
            part.get(
                "mimeType",
                ""
            )
        ).lower()


        body = part.get(
            "body",
            {}
        )


        data = body.get(
            "data"
        )


        if data:

            decoded = cls._decode(
                data
            )


            if (
                mime_type
                == "text/plain"
            ):

                plain.append(
                    decoded
                )

            elif (
                mime_type
                == "text/html"
            ):

                html.append(
                    decoded
                )


        for child in part.get(
            "parts",
            ()
        ):

            child_plain, child_html = (
                cls._parts(
                    child
                )
            )


            plain.extend(
                child_plain
            )

            html.extend(
                child_html
            )


        return plain, html


    @staticmethod
    def _headers(
        payload,
    ):

        return {
            str(
                item.get(
                    "name",
                    ""
                )
            ).lower():
                str(
                    item.get(
                        "value",
                        ""
                    )
                )

            for item
            in payload.get(
                "headers",
                ()
            )
        }


    def service(
        self,
    ):

        return google_oauth.service(
            "gmail",
            "v1",
        )


    def search(
        self,
        query="",
        max_results=20,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                100,
            ),
        )


        response = (
            self.service()
            .users()
            .messages()
            .list(
                userId="me",
                q=str(
                    query
                ),
                maxResults=
                    max_results,
            )
            .execute()
        )


        messages = []


        service = self.service()


        for item in response.get(
            "messages",
            ()
        ):

            metadata = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=item[
                        "id"
                    ],
                    format=
                        "metadata",
                    metadataHeaders=[
                        "From",
                        "To",
                        "Subject",
                        "Date",
                    ],
                )
                .execute()
            )


            payload = metadata.get(
                "payload",
                {}
            )


            headers = self._headers(
                payload
            )


            messages.append(
                {
                    "id":
                        metadata.get(
                            "id"
                        ),

                    "thread_id":
                        metadata.get(
                            "threadId"
                        ),

                    "from":
                        headers.get(
                            "from"
                        ),

                    "to":
                        headers.get(
                            "to"
                        ),

                    "subject":
                        headers.get(
                            "subject"
                        ),

                    "date":
                        headers.get(
                            "date"
                        ),

                    "snippet":
                        metadata.get(
                            "snippet",
                            ""
                        ),
                }
            )


        google_audit.record(
            "gmail.search",
            success=True,
            metadata={
                "query":
                    str(
                        query
                    )[:500],

                "results":
                    len(
                        messages
                    ),
            },
        )


        return {
            "success":
                True,

            "messages":
                tuple(
                    messages
                ),

            "next_page_token":
                response.get(
                    "nextPageToken"
                ),
        }


    def get(
        self,
        message_id,
    ):

        message = (
            self.service()
            .users()
            .messages()
            .get(
                userId="me",
                id=str(
                    message_id
                ),
                format="full",
            )
            .execute()
        )


        payload = message.get(
            "payload",
            {}
        )


        headers = self._headers(
            payload
        )


        plain, html = self._parts(
            payload
        )


        result = {
            "success":
                True,

            "id":
                message.get(
                    "id"
                ),

            "thread_id":
                message.get(
                    "threadId"
                ),

            "from":
                headers.get(
                    "from"
                ),

            "to":
                headers.get(
                    "to"
                ),

            "cc":
                headers.get(
                    "cc"
                ),

            "subject":
                headers.get(
                    "subject"
                ),

            "date":
                headers.get(
                    "date"
                ),

            "snippet":
                message.get(
                    "snippet"
                ),

            "text":
                "\n".join(
                    plain
                )[:50000],

            "html":
                "\n".join(
                    html
                )[:50000],
        }


        google_audit.record(
            "gmail.get",
            success=True,
            metadata={
                "message_id":
                    str(
                        message_id
                    )
            },
        )


        return result


    @staticmethod
    def _message(
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        message = EmailMessage()


        message[
            "To"
        ] = str(
            to
        )


        message[
            "Subject"
        ] = str(
            subject
        )


        if cc:

            message[
                "Cc"
            ] = str(
                cc
            )


        if bcc:

            message[
                "Bcc"
            ] = str(
                bcc
            )


        message.set_content(
            str(
                body
            )
        )


        return message


    def prepare_create_draft(
        self,
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        body_text = str(
            body
        )


        payload = {
            "to":
                str(
                    to
                ),

            "cc":
                str(
                    cc
                    or ""
                ),

            "bcc":
                str(
                    bcc
                    or ""
                ),

            "subject":
                str(
                    subject
                ),

            "body_sha256":
                hashlib.sha256(
                    body_text.encode(
                        "utf-8"
                    )
                ).hexdigest(),

            "body_length":
                len(
                    body_text
                ),
        }


        return {
            "action":
                "google.gmail.create_draft",

            "payload":
                payload,

            "display": {
                "to":
                    payload[
                        "to"
                    ],

                "cc":
                    payload[
                        "cc"
                    ],

                "bcc":
                    payload[
                        "bcc"
                    ],

                "subject":
                    payload[
                        "subject"
                    ],

                "body_preview":
                    body_text[:160],
            },

            "risk":
                "email-draft-write",
        }


    def create_draft(
        self,
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
        approval_id=None,
    ):

        binding = self.prepare_create_draft(
            to,
            subject,
            body,
            cc=cc,
            bcc=bcc,
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
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


        message = self._message(
            to,
            subject,
            body,
            cc=cc,
            bcc=bcc,
        )


        raw = (
            base64.urlsafe_b64encode(
                message.as_bytes()
            )
            .decode(
                "ascii"
            )
        )


        result = (
            self.service()
            .users()
            .drafts()
            .create(
                userId="me",
                body={
                    "message": {
                        "raw":
                            raw
                    }
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.create_draft",
            success=True,
            metadata={
                "draft_id":
                    result.get(
                        "id"
                    ),

                "to":
                    str(
                        to
                    ),

                "subject":
                    str(
                        subject
                    ),
            },
        )


        return {
            "success":
                True,

            "draft_id":
                result.get(
                    "id"
                ),

            "message":
                result.get(
                    "message"
                ),
        }


    @staticmethod
    def prepare_send_draft(
        draft_id,
    ):

        payload = {
            "draft_id":
                str(
                    draft_id
                )
        }


        return {
            "action":
                "google.gmail.send_draft",

            "payload":
                payload,

            "display":
                payload,

            "risk":
                "email-send",
        }


    def send_draft(
        self,
        draft_id,
        *,
        approval_id=None,
    ):

        binding = self.prepare_send_draft(
            draft_id
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
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


        result = (
            self.service()
            .users()
            .drafts()
            .send(
                userId="me",
                body={
                    "id":
                        str(
                            draft_id
                        )
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.send_draft",
            success=True,
            metadata={
                "draft_id":
                    str(
                        draft_id
                    ),

                "message_id":
                    result.get(
                        "id"
                    ),
            },
        )


        return {
            "success":
                True,

            "message_id":
                result.get(
                    "id"
                ),

            "thread_id":
                result.get(
                    "threadId"
                ),
        }


gmail_service = (
    GmailService()
)
