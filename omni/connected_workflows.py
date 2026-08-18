from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
    timezone,
)

from email.utils import (
    getaddresses,
)


from omni.gmail_service import (
    gmail_service,
)

from omni.google_calendar_service import (
    google_calendar_service,
)

from omni.recipient_intelligence import (
    recipient_resolver,
)


class ConnectedWorkflowIntelligence:

    def __init__(
        self,
        resolver=None,
        gmail=None,
        calendar=None,
    ):

        self.resolver = (
            resolver
            or recipient_resolver
        )

        self.gmail = (
            gmail
            or gmail_service
        )

        self.calendar = (
            calendar
            or google_calendar_service
        )


    @staticmethod
    def _queries(
        value,
    ):

        if value is None:

            return []


        if isinstance(
            value,
            str,
        ):

            return [
                value
            ]


        return [
            str(
                item
            )

            for item
            in value
        ]


    @staticmethod
    def _join(
        values,
    ):

        values = tuple(
            values
            or ()
        )


        return (
            ", ".join(
                values
            )

            if values

            else None
        )


    def _resolve_group(
        self,
        value,
    ):

        queries = self._queries(
            value
        )


        if not queries:

            return {
                "success":
                    True,

                "resolved":
                    (),

                "emails":
                    (),

                "unresolved":
                    (),

                "ambiguous":
                    (),
            }


        return (
            self.resolver
            .resolve_many(
                queries
            )
        )


    # --------------------------------------------------------
    # Gmail draft intelligence
    # --------------------------------------------------------

    def prepare_draft(
        self,
        recipients,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        to_result = self._resolve_group(
            recipients
        )

        cc_result = self._resolve_group(
            cc
        )

        bcc_result = self._resolve_group(
            bcc
        )


        problems = {
            "to":
                to_result,

            "cc":
                cc_result,

            "bcc":
                bcc_result,
        }


        for name, result in problems.items():

            if not result.get(
                "success",
                False,
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Recipient resolution failed "
                            "for "
                            + name
                        ),

                    "resolution":
                        problems,
                }


        if not to_result[
            "emails"
        ]:

            return {
                "success":
                    False,

                "error":
                    "At least one To recipient is required.",

                "resolution":
                    problems,
            }


        to_value = self._join(
            to_result[
                "emails"
            ]
        )

        cc_value = self._join(
            cc_result[
                "emails"
            ]
        )

        bcc_value = self._join(
            bcc_result[
                "emails"
            ]
        )


        binding = (
            self.gmail
            .prepare_create_draft(
                to_value,
                subject,
                body,

                cc=
                    cc_value,

                bcc=
                    bcc_value,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,

            "resolved_to":
                to_result[
                    "emails"
                ],

            "resolved_cc":
                cc_result[
                    "emails"
                ],

            "resolved_bcc":
                bcc_result[
                    "emails"
                ],

            "resolution":
                problems,
        }


    def create_draft(
        self,
        recipients,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
        approval_id=None,
    ):

        prepared = self.prepare_draft(
            recipients,
            subject,
            body,

            cc=cc,
            bcc=bcc,
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.gmail
            .create_draft(
                self._join(
                    prepared[
                        "resolved_to"
                    ]
                ),

                subject,
                body,

                cc=
                    self._join(
                        prepared[
                            "resolved_cc"
                        ]
                    ),

                bcc=
                    self._join(
                        prepared[
                            "resolved_bcc"
                        ]
                    ),

                approval_id=
                    approval_id,
            )
        )


    # --------------------------------------------------------
    # Time / conflict handling
    # --------------------------------------------------------

    @staticmethod
    def _datetime(
        value,
    ):

        if isinstance(
            value,
            datetime,
        ):

            result = value

        else:

            text = str(
                value
            ).strip()


            if text.endswith(
                "Z"
            ):

                text = (
                    text[:-1]
                    + "+00:00"
                )


            result = (
                datetime.fromisoformat(
                    text
                )
            )


        if result.tzinfo is None:

            raise ValueError(
                "Meeting date/time must include "
                "an explicit UTC offset/timezone."
            )


        return result


    @staticmethod
    def _event_bounds(
        event,
    ):

        start = event.get(
            "start",
            {}
        )

        end = event.get(
            "end",
            {}
        )


        if (
            start.get(
                "dateTime"
            )
            and end.get(
                "dateTime"
            )
        ):

            return (
                ConnectedWorkflowIntelligence
                ._datetime(
                    start[
                        "dateTime"
                    ]
                ),

                ConnectedWorkflowIntelligence
                ._datetime(
                    end[
                        "dateTime"
                    ]
                ),
            )


        if (
            start.get(
                "date"
            )
            and end.get(
                "date"
            )
        ):

            start_date = (
                date.fromisoformat(
                    start[
                        "date"
                    ]
                )
            )

            end_date = (
                date.fromisoformat(
                    end[
                        "date"
                    ]
                )
            )


            return (
                datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=
                        timezone.utc,
                ),

                datetime.combine(
                    end_date,
                    time.min,
                    tzinfo=
                        timezone.utc,
                ),
            )


        return (
            None,
            None,
        )


    def check_conflicts(
        self,
        start,
        end,
        *,
        calendar_id="primary",
    ):

        start_dt = self._datetime(
            start
        )

        end_dt = self._datetime(
            end
        )


        if (
            end_dt
            <= start_dt
        ):

            raise ValueError(
                "Meeting end must be after start."
            )


        response = (
            self.calendar
            .events(
                calendar_id=
                    calendar_id,

                time_min=
                    start_dt.isoformat(),

                time_max=
                    end_dt.isoformat(),

                max_results=
                    100,
            )
        )


        conflicts = []


        for event in response.get(
            "events",
            ()
        ):

            if (
                event.get(
                    "status"
                )
                == "cancelled"
            ):

                continue


            event_start, event_end = (
                self._event_bounds(
                    event
                )
            )


            if (
                event_start is None
                or event_end is None
            ):

                continue


            try:

                overlaps = (
                    event_start
                    < end_dt

                    and event_end
                    > start_dt
                )

            except TypeError:

                # All-day events are normalized
                # to UTC. Compare UTC if needed.
                overlaps = (
                    event_start.astimezone(
                        timezone.utc
                    )
                    < end_dt.astimezone(
                        timezone.utc
                    )

                    and event_end.astimezone(
                        timezone.utc
                    )
                    > start_dt.astimezone(
                        timezone.utc
                    )
                )


            if overlaps:

                conflicts.append(
                    {
                        "id":
                            event.get(
                                "id"
                            ),

                        "summary":
                            event.get(
                                "summary"
                            ),

                        "start":
                            event.get(
                                "start"
                            ),

                        "end":
                            event.get(
                                "end"
                            ),
                    }
                )


        return {
            "success":
                True,

            "calendar_id":
                str(
                    calendar_id
                ),

            "start":
                start_dt.isoformat(),

            "end":
                end_dt.isoformat(),

            "has_conflict":
                bool(
                    conflicts
                ),

            "conflicts":
                tuple(
                    conflicts
                ),
        }


    # --------------------------------------------------------
    # Meeting planning
    # --------------------------------------------------------

    def prepare_meeting(
        self,
        title,
        attendees,
        start,
        end,
        *,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
    ):

        attendee_result = (
            self._resolve_group(
                attendees
            )
        )


        if not attendee_result.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Attendee resolution failed.",

                "resolution":
                    attendee_result,
            }


        start_dt = self._datetime(
            start
        )

        end_dt = self._datetime(
            end
        )


        if (
            end_dt
            <= start_dt
        ):

            return {
                "success":
                    False,

                "error":
                    "Meeting end must be after start.",
            }


        conflicts = self.check_conflicts(
            start_dt,
            end_dt,

            calendar_id=
                calendar_id,
        )


        if (
            conflicts[
                "has_conflict"
            ]

            and not allow_conflicts
        ):

            return {
                "success":
                    False,

                "conflict":
                    True,

                "requires_resolution":
                    True,

                "error":
                    "Calendar conflict detected.",

                "conflicts":
                    conflicts[
                        "conflicts"
                    ],

                "resolved_attendees":
                    attendee_result[
                        "emails"
                    ],
            }


        start_payload = {
            "dateTime":
                start_dt.isoformat()
        }


        end_payload = {
            "dateTime":
                end_dt.isoformat()
        }


        if time_zone:

            start_payload[
                "timeZone"
            ] = str(
                time_zone
            )

            end_payload[
                "timeZone"
            ] = str(
                time_zone
            )


        event = {
            "summary":
                str(
                    title
                ),

            "start":
                start_payload,

            "end":
                end_payload,

            "attendees": [
                {
                    "email":
                        email
                }

                for email
                in attendee_result[
                    "emails"
                ]
            ],
        }


        if description:

            event[
                "description"
            ] = str(
                description
            )


        if location:

            event[
                "location"
            ] = str(
                location
            )


        binding = (
            self.calendar
            .prepare_create_event(
                event,

                calendar_id=
                    calendar_id,

                send_updates=
                    send_updates,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,

            "event":
                event,

            "calendar_id":
                str(
                    calendar_id
                ),

            "send_updates":
                str(
                    send_updates
                ),

            "resolved_attendees":
                attendee_result[
                    "emails"
                ],

            "resolution":
                attendee_result,

            "conflicts":
                conflicts[
                    "conflicts"
                ],

            "allow_conflicts":
                bool(
                    allow_conflicts
                ),
        }


    def schedule_meeting(
        self,
        title,
        attendees,
        start,
        end,
        *,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
        approval_id=None,
    ):

        prepared = self.prepare_meeting(
            title,
            attendees,
            start,
            end,

            description=
                description,

            location=
                location,

            calendar_id=
                calendar_id,

            send_updates=
                send_updates,

            time_zone=
                time_zone,

            allow_conflicts=
                allow_conflicts,
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.calendar
            .create_event(
                prepared[
                    "event"
                ],

                calendar_id=
                    prepared[
                        "calendar_id"
                    ],

                send_updates=
                    prepared[
                        "send_updates"
                    ],

                approval_id=
                    approval_id,
            )
        )


    # --------------------------------------------------------
    # Gmail message -> Calendar meeting
    # --------------------------------------------------------

    def prepare_meeting_from_email(
        self,
        message_id,
        title,
        start,
        end,
        *,
        attendees=None,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
    ):

        message = self.gmail.get(
            message_id
        )


        attendee_queries = (
            self._queries(
                attendees
            )
        )


        if not attendee_queries:

            sender = message.get(
                "from"
            )


            addresses = getaddresses(
                [
                    str(
                        sender
                        or ""
                    )
                ]
            )


            attendee_queries = [
                email

                for name, email
                in addresses

                if email
            ]


        if not attendee_queries:

            return {
                "success":
                    False,

                "error":
                    (
                        "Could not derive an attendee "
                        "from the source email."
                    ),
            }


        prepared = self.prepare_meeting(
            title,
            attendee_queries,
            start,
            end,

            description=
                description,

            location=
                location,

            calendar_id=
                calendar_id,

            send_updates=
                send_updates,

            time_zone=
                time_zone,

            allow_conflicts=
                allow_conflicts,
        )


        prepared[
            "source_message"
        ] = {
            "message_id":
                str(
                    message_id
                ),

            "from":
                message.get(
                    "from"
                ),

            "subject":
                message.get(
                    "subject"
                ),
        }


        return prepared


    def schedule_meeting_from_email(
        self,
        message_id,
        title,
        start,
        end,
        *,
        attendees=None,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
        approval_id=None,
    ):

        prepared = (
            self.prepare_meeting_from_email(
                message_id,
                title,
                start,
                end,

                attendees=
                    attendees,

                description=
                    description,

                location=
                    location,

                calendar_id=
                    calendar_id,

                send_updates=
                    send_updates,

                time_zone=
                    time_zone,

                allow_conflicts=
                    allow_conflicts,
            )
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.calendar
            .create_event(
                prepared[
                    "event"
                ],

                calendar_id=
                    prepared[
                        "calendar_id"
                    ],

                send_updates=
                    prepared[
                        "send_updates"
                    ],

                approval_id=
                    approval_id,
            )
        )


connected_workflows = (
    ConnectedWorkflowIntelligence()
)
