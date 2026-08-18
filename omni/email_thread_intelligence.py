from __future__ import annotations

from email.message import EmailMessage
from email.utils import getaddresses, parseaddr

import base64
import hashlib


from omni.approval_queue import approval_queue
from omni.gmail_service import gmail_service
from omni.google_audit import google_audit


def _dedupe(addresses):

    output = []
    seen = set()

    for address in addresses:
        name, email = parseaddr(
            str(address)
        )

        email = email.strip().lower()

        if not email or "@" not in email:
            continue

        if email in seen:
            continue

        seen.add(email)

        output.append(
            (
                name.strip(),
                email,
            )
        )

    return output


class EmailThreadIntelligence:

    def service(self):
        return gmail_service.service()


    def _profile_email(self):

        profile = (
            self.service()
            .users()
            .getProfile(userId="me")
            .execute()
        )

        return str(
            profile.get("emailAddress", "")
        ).lower()


    def thread(
        self,
        thread_id,
    ):

        raw = (
            self.service()
            .users()
            .threads()
            .get(
                userId="me",
                id=str(thread_id),
                format="full",
            )
            .execute()
        )


        messages = []

        for message in raw.get(
            "messages",
            (),
        ):
            payload = message.get(
                "payload",
                {},
            )

            headers = gmail_service._headers(
                payload
            )

            plain, html = gmail_service._parts(
                payload
            )

            messages.append(
                {
                    "id": message.get("id"),
                    "thread_id": message.get("threadId"),
                    "from": headers.get("from"),
                    "to": headers.get("to"),
                    "cc": headers.get("cc"),
                    "reply_to": headers.get("reply-to"),
                    "subject": headers.get("subject"),
                    "date": headers.get("date"),
                    "message_id": headers.get("message-id"),
                    "references": headers.get("references"),
                    "snippet": message.get("snippet", ""),
                    "text": "\n".join(plain)[:50000],
                    "html": "\n".join(html)[:50000],
                }
            )


        result = {
            "success": True,
            "id": raw.get("id"),
            "history_id": raw.get("historyId"),
            "snippet": raw.get("snippet"),
            "messages": tuple(messages),
            "message_count": len(messages),
        }


        google_audit.record(
            "gmail.thread.get",
            success=True,
            metadata={
                "thread_id": str(thread_id),
                "messages": len(messages),
            },
        )


        return result


    def _reply_context(
        self,
        thread_id,
        *,
        reply_all=False,
    ):

        thread = self.thread(
            thread_id
        )

        messages = list(
            thread.get(
                "messages",
                (),
            )
        )

        if not messages:
            raise ValueError(
                "Gmail thread contains no messages."
            )


        self_email = self._profile_email()


        selected = None

        for candidate in reversed(
            messages
        ):
            sender = parseaddr(
                str(
                    candidate.get(
                        "from",
                        "",
                    )
                )
            )[1].lower()

            if sender and sender != self_email:
                selected = candidate
                break


        if selected is None:
            selected = messages[-1]


        reply_address = (
            selected.get("reply_to")
            or selected.get("from")
            or ""
        )


        targets = _dedupe(
            [reply_address]
        )


        if not targets:
            raise ValueError(
                "Could not determine reply recipient."
            )


        to_addresses = [
            email
            for _, email in targets
            if email != self_email
        ]


        cc_addresses = []


        if reply_all:

            original = []

            original.extend(
                getaddresses(
                    [
                        str(
                            selected.get(
                                "to",
                                "",
                            )
                        )
                    ]
                )
            )

            original.extend(
                getaddresses(
                    [
                        str(
                            selected.get(
                                "cc",
                                "",
                            )
                        )
                    ]
                )
            )


            for name, email in original:
                email = email.strip().lower()

                if (
                    email
                    and email != self_email
                    and email not in to_addresses
                    and email not in cc_addresses
                ):
                    cc_addresses.append(email)


        subject = str(
            selected.get(
                "subject",
                "",
            )
            or ""
        ).strip()


        if not subject.lower().startswith(
            "re:"
        ):
            subject = (
                "Re: "
                + subject
            ).strip()


        message_id = selected.get(
            "message_id"
        )


        references = str(
            selected.get(
                "references",
                "",
            )
            or ""
        ).strip()


        if message_id:
            references = (
                references
                + " "
                + str(message_id)
            ).strip()


        return {
            "thread": thread,
            "selected_message": selected,
            "self_email": self_email,
            "to": tuple(to_addresses),
            "cc": tuple(cc_addresses),
            "subject": subject,
            "in_reply_to": message_id,
            "references": references or None,
        }


    def prepare_reply(
        self,
        thread_id,
        body,
        *,
        reply_all=False,
    ):

        context = self._reply_context(
            thread_id,
            reply_all=reply_all,
        )


        body_text = str(body)


        payload = {
            "thread_id": str(thread_id),
            "to": tuple(context["to"]),
            "cc": tuple(context["cc"]),
            "subject": context["subject"],
            "reply_all": bool(reply_all),
            "body_sha256": hashlib.sha256(
                body_text.encode("utf-8")
            ).hexdigest(),
            "body_length": len(body_text),
            "in_reply_to": context["in_reply_to"],
        }


        return {
            "success": True,
            "action": "google.gmail.reply_draft",
            "payload": payload,
            "display": {
                "thread_id": str(thread_id),
                "to": tuple(context["to"]),
                "cc": tuple(context["cc"]),
                "subject": context["subject"],
                "reply_all": bool(reply_all),
                "body_length": len(body_text),
                "body_sha256_prefix": (
                    payload["body_sha256"][:12]
                ),
            },
            "risk": "email-reply-draft",
            "context": context,
        }


    def create_reply_draft(
        self,
        thread_id,
        body,
        *,
        reply_all=False,
        approval_id=None,
    ):

        prepared = self.prepare_reply(
            thread_id,
            body,
            reply_all=reply_all,
        )


        if not approval_id:

            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        context = prepared["context"]

        message = EmailMessage()

        message["To"] = ", ".join(
            context["to"]
        )

        if context["cc"]:
            message["Cc"] = ", ".join(
                context["cc"]
            )

        message["Subject"] = context["subject"]


        if context["in_reply_to"]:
            message["In-Reply-To"] = str(
                context["in_reply_to"]
            )

        if context["references"]:
            message["References"] = str(
                context["references"]
            )


        message.set_content(
            str(body)
        )


        raw = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")


        result = (
            self.service()
            .users()
            .drafts()
            .create(
                userId="me",
                body={
                    "message": {
                        "raw": raw,
                        "threadId": str(thread_id),
                    }
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.reply_draft.create",
            success=True,
            metadata={
                "thread_id": str(thread_id),
                "draft_id": result.get("id"),
                "to": tuple(context["to"]),
                "subject": context["subject"],
            },
        )


        return {
            "success": True,
            "draft_id": result.get("id"),
            "message": result.get("message"),
            "thread_id": str(thread_id),
        }


email_thread_intelligence = EmailThreadIntelligence()
