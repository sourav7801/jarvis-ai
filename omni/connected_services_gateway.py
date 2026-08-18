from __future__ import annotations

from omni.connected_workflows import connected_workflows
from omni.gmail_service import gmail_service
from omni.google_calendar_service import google_calendar_service
from omni.google_contacts_service import google_contacts_service
from omni.google_oauth import google_oauth
from omni.google_scopes import SERVICE_CAPABILITIES
from omni.recipient_intelligence import recipient_resolver


WRITE_ACTIONS = {
    "google.gmail.create_draft",
    "google.gmail.send_draft",
    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "google.gmail.draft_to_contact",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
}


READ_ACTIONS = {
    "google.gmail.search",
    "google.gmail.get",

    "google.calendar.list",
    "google.calendar.events",

    "google.contacts.search",

    "google.contacts.resolve",
    "google.calendar.check_conflicts",
}


class ConnectedServicesGateway:

    def status(self):

        return {
            "google":
                google_oauth.status(),

            "capabilities":
                SERVICE_CAPABILITIES,

            "read_actions":
                tuple(
                    sorted(
                        READ_ACTIONS
                    )
                ),

            "write_actions":
                tuple(
                    sorted(
                        WRITE_ACTIONS
                    )
                ),

            "recipient_resolution":
                True,

            "ambiguity_blocking":
                True,

            "gmail_history_resolution":
                True,

            "calendar_conflict_detection":
                True,

            "email_to_calendar_workflow":
                True,

            "draft_to_contact_workflow":
                True,

            "automatic_send":
                False,

            "automatic_calendar_write":
                False,

            "automatic_conflict_override":
                False,

            "contact_write":
                False,
        }


    def prepare(
        self,
        action,
        payload,
    ):

        payload = dict(
            payload
        )


        if action == "google.gmail.create_draft":

            return {
                "success":
                    True,

                "binding":
                    gmail_service.prepare_create_draft(
                        payload["to"],
                        payload["subject"],
                        payload["body"],

                        cc=
                            payload.get(
                                "cc"
                            ),

                        bcc=
                            payload.get(
                                "bcc"
                            ),
                    ),
            }


        if action == "google.gmail.send_draft":

            return {
                "success":
                    True,

                "binding":
                    gmail_service.prepare_send_draft(
                        payload[
                            "draft_id"
                        ]
                    ),
            }


        if action == "google.gmail.draft_to_contact":

            return connected_workflows.prepare_draft(
                payload[
                    "recipients"
                ],

                payload[
                    "subject"
                ],

                payload[
                    "body"
                ],

                cc=
                    payload.get(
                        "cc"
                    ),

                bcc=
                    payload.get(
                        "bcc"
                    ),
            )


        if action == "google.calendar.create_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_create_event(
                        payload[
                            "event"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        if action == "google.calendar.update_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_update_event(
                        payload[
                            "event_id"
                        ],

                        payload[
                            "patch"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        if action == "google.calendar.delete_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_delete_event(
                        payload[
                            "event_id"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        if action == "google.calendar.schedule_meeting":

            return connected_workflows.prepare_meeting(
                payload[
                    "title"
                ],

                payload[
                    "attendees"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),
            )


        if action == "google.calendar.schedule_from_email":

            return connected_workflows.prepare_meeting_from_email(
                payload[
                    "message_id"
                ],

                payload[
                    "title"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                attendees=
                    payload.get(
                        "attendees"
                    ),

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),
            )


        return {
            "success":
                False,

            "error":
                (
                    "Action is not a connected "
                    "service write: "
                    + str(
                        action
                    )
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


        # ----------------------------------------------------
        # GMAIL
        # ----------------------------------------------------

        if action == "google.gmail.search":

            return gmail_service.search(
                payload.get(
                    "query",
                    ""
                ),

                payload.get(
                    "max_results",
                    20,
                ),
            )


        if action == "google.gmail.get":

            return gmail_service.get(
                payload[
                    "message_id"
                ]
            )


        if action == "google.gmail.create_draft":

            return gmail_service.create_draft(
                payload[
                    "to"
                ],

                payload[
                    "subject"
                ],

                payload[
                    "body"
                ],

                cc=
                    payload.get(
                        "cc"
                    ),

                bcc=
                    payload.get(
                        "bcc"
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.gmail.draft_to_contact":

            return connected_workflows.create_draft(
                payload[
                    "recipients"
                ],

                payload[
                    "subject"
                ],

                payload[
                    "body"
                ],

                cc=
                    payload.get(
                        "cc"
                    ),

                bcc=
                    payload.get(
                        "bcc"
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.gmail.send_draft":

            return gmail_service.send_draft(
                payload[
                    "draft_id"
                ],

                approval_id=
                    approval_id,
            )


        # ----------------------------------------------------
        # CONTACTS
        # ----------------------------------------------------

        if action == "google.contacts.search":

            return google_contacts_service.search(
                payload.get(
                    "query",
                    ""
                ),

                payload.get(
                    "max_results",
                    20,
                ),
            )


        if action == "google.contacts.resolve":

            return recipient_resolver.resolve(
                payload[
                    "query"
                ],

                max_results=
                    payload.get(
                        "max_results",
                        20,
                    ),

                include_gmail_history=
                    bool(
                        payload.get(
                            "include_gmail_history",
                            True,
                        )
                    ),
            )


        # ----------------------------------------------------
        # CALENDAR
        # ----------------------------------------------------

        if action == "google.calendar.list":

            return google_calendar_service.calendars(
                payload.get(
                    "max_results",
                    100,
                )
            )


        if action == "google.calendar.events":

            return google_calendar_service.events(
                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                time_min=
                    payload.get(
                        "time_min"
                    ),

                time_max=
                    payload.get(
                        "time_max"
                    ),

                max_results=
                    payload.get(
                        "max_results",
                        20,
                    ),

                query=
                    payload.get(
                        "query"
                    ),
            )


        if action == "google.calendar.check_conflicts":

            return connected_workflows.check_conflicts(
                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),
            )


        if action == "google.calendar.create_event":

            return google_calendar_service.create_event(
                payload[
                    "event"
                ],

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.calendar.update_event":

            return google_calendar_service.update_event(
                payload[
                    "event_id"
                ],

                payload[
                    "patch"
                ],

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.calendar.delete_event":

            return google_calendar_service.delete_event(
                payload[
                    "event_id"
                ],

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.calendar.schedule_meeting":

            return connected_workflows.schedule_meeting(
                payload[
                    "title"
                ],

                payload[
                    "attendees"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.calendar.schedule_from_email":

            return connected_workflows.schedule_meeting_from_email(
                payload[
                    "message_id"
                ],

                payload[
                    "title"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                attendees=
                    payload.get(
                        "attendees"
                    ),

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),

                send_updates=
                    payload.get(
                        "send_updates",
                        "none",
                    ),

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),

                approval_id=
                    approval_id,
            )


        return {
            "success":
                False,

            "error":
                (
                    "Unknown connected service action: "
                    + str(
                        action
                    )
                ),
        }


connected_services_gateway = (
    ConnectedServicesGateway()
)
