from __future__ import annotations


from omni.calendar_availability import calendar_availability
from omni.connected_services_gateway import (
    READ_ACTIONS as V2_READ_ACTIONS,
    WRITE_ACTIONS as V2_WRITE_ACTIONS,
    connected_services_gateway,
)
from omni.email_thread_intelligence import email_thread_intelligence
from omni.github_connected import github_connected


V3_READ_ACTIONS = {
    "google.gmail.thread",
    "google.calendar.recommend_slots",

    "github.profile",
    "github.repos",
    "github.issues",
    "github.pulls",
}


V3_WRITE_ACTIONS = {
    "google.gmail.reply_draft",

    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
}


READ_ACTIONS = (
    set(V2_READ_ACTIONS)
    | V3_READ_ACTIONS
)


WRITE_ACTIONS = (
    set(V2_WRITE_ACTIONS)
    | V3_WRITE_ACTIONS
)


class ConnectedServicesV3Gateway:

    def status(self):

        return {
            "read_actions": tuple(
                sorted(
                    READ_ACTIONS
                )
            ),
            "write_actions": tuple(
                sorted(
                    WRITE_ACTIONS
                )
            ),
            "gmail_threads": True,
            "gmail_reply_drafts": True,
            "calendar_freebusy": True,
            "calendar_slot_recommendation": True,
            "multi_person_coordination": True,
            "github": github_connected.status(
                verify=False
            ),
            "automatic_email_send": False,
            "automatic_calendar_write": False,
            "automatic_github_write": False,
            "github_merge": False,
            "github_force_push": False,
        }


    def prepare(
        self,
        action,
        payload,
    ):

        payload = dict(
            payload
        )


        if action in V2_WRITE_ACTIONS:
            return connected_services_gateway.prepare(
                action,
                payload,
            )


        if action == "google.gmail.reply_draft":

            return email_thread_intelligence.prepare_reply(
                payload[
                    "thread_id"
                ],
                payload[
                    "body"
                ],
                reply_all=bool(
                    payload.get(
                        "reply_all",
                        False,
                    )
                ),
            )


        if action == "github.issue.create":

            return github_connected.prepare_create_issue(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload.get(
                    "body",
                    "",
                ),
            )


        if action == "github.comment.create":

            return github_connected.prepare_comment(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "issue_number"
                ],
                payload[
                    "body"
                ],
            )


        if action == "github.pull.create":

            return github_connected.prepare_pull(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload[
                    "head"
                ],
                payload[
                    "base"
                ],
                payload.get(
                    "body",
                    "",
                ),
            )


        return {
            "success": False,
            "error": (
                "Unsupported V3 write action: "
                + str(action)
            ),
        }


    def execute(
        self,
        action,
        payload,
        *,
        approval_id=None,
    ):

        payload = dict(
            payload
        )


        if (
            action in V2_READ_ACTIONS
            or action in V2_WRITE_ACTIONS
        ):
            return connected_services_gateway.execute(
                action,
                payload,
                approval_id=approval_id,
            )


        if action == "google.gmail.thread":

            return email_thread_intelligence.thread(
                payload[
                    "thread_id"
                ]
            )


        if action == "google.gmail.reply_draft":

            return (
                email_thread_intelligence
                .create_reply_draft(
                    payload[
                        "thread_id"
                    ],
                    payload[
                        "body"
                    ],
                    reply_all=bool(
                        payload.get(
                            "reply_all",
                            False,
                        )
                    ),
                    approval_id=approval_id,
                )
            )


        if action == "google.calendar.recommend_slots":

            return calendar_availability.recommend_slots(
                payload.get(
                    "attendees",
                    (),
                ),
                payload[
                    "window_start"
                ],
                payload[
                    "window_end"
                ],
                duration_minutes=payload.get(
                    "duration_minutes",
                    30,
                ),
                step_minutes=payload.get(
                    "step_minutes",
                    30,
                ),
                calendar_id=payload.get(
                    "calendar_id",
                    "primary",
                ),
                time_zone=payload.get(
                    "time_zone"
                ),
                working_hour_start=payload.get(
                    "working_hour_start",
                    8,
                ),
                working_hour_end=payload.get(
                    "working_hour_end",
                    20,
                ),
                strict=bool(
                    payload.get(
                        "strict",
                        True,
                    )
                ),
                max_slots=payload.get(
                    "max_slots",
                    10,
                ),
            )


        if action == "github.profile":
            return {
                "success": True,
                "profile": github_connected.profile(),
            }


        if action == "github.repos":
            return {
                "success": True,
                "repos": github_connected.repos(
                    per_page=payload.get(
                        "per_page",
                        30,
                    )
                ),
            }


        if action == "github.issues":
            return {
                "success": True,
                "issues": github_connected.issues(
                    payload[
                        "owner"
                    ],
                    payload[
                        "repo"
                    ],
                    state=payload.get(
                        "state",
                        "open",
                    ),
                    per_page=payload.get(
                        "per_page",
                        30,
                    ),
                ),
            }


        if action == "github.pulls":
            return {
                "success": True,
                "pulls": github_connected.pulls(
                    payload[
                        "owner"
                    ],
                    payload[
                        "repo"
                    ],
                    state=payload.get(
                        "state",
                        "open",
                    ),
                    per_page=payload.get(
                        "per_page",
                        30,
                    ),
                ),
            }


        if action == "github.issue.create":

            return github_connected.create_issue(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload.get(
                    "body",
                    "",
                ),
                approval_id=approval_id,
            )


        if action == "github.comment.create":

            return github_connected.create_comment(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "issue_number"
                ],
                payload[
                    "body"
                ],
                approval_id=approval_id,
            )


        if action == "github.pull.create":

            return github_connected.create_pull(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload[
                    "head"
                ],
                payload[
                    "base"
                ],
                payload.get(
                    "body",
                    "",
                ),
                approval_id=approval_id,
            )


        return {
            "success": False,
            "error": (
                "Unknown Connected Services V3 action: "
                + str(action)
            ),
        }


connected_services_v3_gateway = ConnectedServicesV3Gateway()
