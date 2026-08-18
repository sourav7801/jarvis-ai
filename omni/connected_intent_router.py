from __future__ import annotations

import re


WRITE_ACTIONS = {
    "google.gmail.reply_draft",
    "google.gmail.draft_to_contact",
    "google.gmail.send_draft",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
}


class ConnectedIntentRouter:

    def route(self, request):

        text = " ".join(
            str(request).strip().lower().split()
        )

        result = {
            "success": True,
            "request": str(request),
            "intent": "unknown",
            "action": None,
            "confidence": 0.0,
            "requires_approval": False,
            "auto_execute": False,
            "reason": "No deterministic connected-service rule matched.",
            "payload_hints": {},
        }

        if not text:
            result["success"] = False
            result["reason"] = "Request is empty."
            return result


        rules = (
            (
                (
                    "reply to this email",
                    "reply to the email",
                    "reply to this thread",
                    "draft a reply",
                    "prepare a reply",
                ),
                "email.reply",
                "google.gmail.reply_draft",
                0.93,
            ),

            (
                (
                    "email ",
                    "send an email",
                    "draft an email",
                    "write an email",
                ),
                "email.compose",
                "google.gmail.draft_to_contact",
                0.84,
            ),

            (
                (
                    "find email",
                    "search email",
                    "search gmail",
                    "find mail",
                ),
                "email.search",
                "google.gmail.search",
                0.91,
            ),

            (
                (
                    "email thread",
                    "gmail thread",
                    "read thread",
                ),
                "email.thread",
                "google.gmail.thread",
                0.90,
            ),

            (
                (
                    "free time",
                    "available slot",
                    "availability",
                    "find a time",
                    "find time for",
                    "when are we free",
                ),
                "calendar.availability",
                "google.calendar.recommend_slots",
                0.92,
            ),

            (
                (
                    "schedule a meeting",
                    "book a meeting",
                    "create a meeting",
                    "calendar meeting",
                ),
                "calendar.schedule",
                "google.calendar.schedule_meeting",
                0.91,
            ),

            (
                (
                    "resolve contact",
                    "find contact",
                    "email address for",
                    "contact details for",
                ),
                "contact.resolve",
                "google.contacts.resolve",
                0.89,
            ),

            (
                (
                    "github issues",
                    "list issues",
                    "show issues",
                ),
                "github.issues",
                "github.issues",
                0.92,
            ),

            (
                (
                    "github pull requests",
                    "list pull requests",
                    "show pull requests",
                    "show prs",
                    "list prs",
                ),
                "github.pulls",
                "github.pulls",
                0.92,
            ),

            (
                (
                    "create github issue",
                    "open github issue",
                    "create an issue",
                    "open an issue",
                ),
                "github.issue.create",
                "github.issue.create",
                0.93,
            ),

            (
                (
                    "comment on github",
                    "comment on issue",
                    "comment on pr",
                    "add github comment",
                ),
                "github.comment.create",
                "github.comment.create",
                0.92,
            ),

            (
                (
                    "create pull request",
                    "open pull request",
                    "create a pr",
                    "open a pr",
                ),
                "github.pull.create",
                "github.pull.create",
                0.94,
            ),

            (
                (
                    "github repositories",
                    "github repos",
                    "list repositories",
                    "list repos",
                ),
                "github.repos",
                "github.repos",
                0.88,
            ),
        )


        for phrases, intent, action, confidence in rules:

            if any(
                phrase in text
                for phrase in phrases
            ):

                result.update(
                    {
                        "intent": intent,
                        "action": action,
                        "confidence": confidence,
                        "requires_approval": (
                            action in WRITE_ACTIONS
                        ),
                        "auto_execute": False,
                        "reason": (
                            "Deterministic connected-service "
                            "intent rule matched."
                        ),
                    }
                )

                return result


        if re.search(
            r"\bgithub\b",
            text,
        ):
            result.update(
                {
                    "intent": "github.profile",
                    "action": "github.profile",
                    "confidence": 0.60,
                    "reason": (
                        "GitHub mentioned but no higher-confidence "
                        "operation was identified."
                    ),
                }
            )


        return result


connected_intent_router = ConnectedIntentRouter()
