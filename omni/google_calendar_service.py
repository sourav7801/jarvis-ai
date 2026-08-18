from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import hashlib
import json


from omni.approval_queue import (
    approval_queue,
)

from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


class GoogleCalendarService:

    def service(
        self,
    ):

        return google_oauth.service(
            "calendar",
            "v3",
        )


    def calendars(
        self,
        max_results=100,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                250,
            ),
        )


        response = (
            self.service()
            .calendarList()
            .list(
                maxResults=
                    max_results,
            )
            .execute()
        )


        items = []


        for item in response.get(
            "items",
            ()
        ):

            items.append(
                {
                    "id":
                        item.get(
                            "id"
                        ),

                    "summary":
                        item.get(
                            "summary"
                        ),

                    "primary":
                        item.get(
                            "primary",
                            False,
                        ),

                    "access_role":
                        item.get(
                            "accessRole"
                        ),

                    "time_zone":
                        item.get(
                            "timeZone"
                        ),
                }
            )


        google_audit.record(
            "calendar.list",
            success=True,
            metadata={
                "results":
                    len(
                        items
                    )
            },
        )


        return {
            "success":
                True,

            "calendars":
                tuple(
                    items
                ),
        }


    def events(
        self,
        *,
        calendar_id="primary",
        time_min=None,
        time_max=None,
        max_results=20,
        query=None,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                250,
            ),
        )


        if time_min is None:

            time_min = (
                datetime.now(
                    timezone.utc
                )
                .isoformat()
            )


        arguments = {
            "calendarId":
                str(
                    calendar_id
                ),

            "timeMin":
                str(
                    time_min
                ),

            "maxResults":
                max_results,

            "singleEvents":
                True,

            "orderBy":
                "startTime",
        }


        if time_max:

            arguments[
                "timeMax"
            ] = str(
                time_max
            )


        if query:

            arguments[
                "q"
            ] = str(
                query
            )


        response = (
            self.service()
            .events()
            .list(
                **arguments
            )
            .execute()
        )


        items = []


        for event in response.get(
            "items",
            ()
        ):

            items.append(
                {
                    "id":
                        event.get(
                            "id"
                        ),

                    "summary":
                        event.get(
                            "summary"
                        ),

                    "description":
                        event.get(
                            "description"
                        ),

                    "location":
                        event.get(
                            "location"
                        ),

                    "start":
                        event.get(
                            "start"
                        ),

                    "end":
                        event.get(
                            "end"
                        ),

                    "status":
                        event.get(
                            "status"
                        ),

                    "html_link":
                        event.get(
                            "htmlLink"
                        ),

                    "attendees":
                        event.get(
                            "attendees",
                            (),
                        ),
                }
            )


        google_audit.record(
            "calendar.events",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "results":
                    len(
                        items
                    ),
            },
        )


        return {
            "success":
                True,

            "events":
                tuple(
                    items
                ),
        }


    @staticmethod
    def _event_hash(
        event,
    ):

        raw = json.dumps(
            event,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )


        return hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()


    @staticmethod
    def _display_event(
        event,
    ):

        attendees = []


        for item in event.get(
            "attendees",
            ()
        ):

            if isinstance(
                item,
                dict,
            ):

                email = item.get(
                    "email"
                )

                if email:

                    attendees.append(
                        email
                    )


        return {
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

            "location":
                event.get(
                    "location"
                ),

            "attendees":
                attendees,
        }


    def prepare_create_event(
        self,
        event,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        event = dict(
            event
        )


        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_sha256":
                self._event_hash(
                    event
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.create_event",

            "payload":
                payload,

            "display": {
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event":
                    self._display_event(
                        event
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },

            "risk":
                "calendar-write",
        }


    def create_event(
        self,
        event,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        if send_updates not in (
            "none",
            "all",
            "externalOnly",
        ):

            raise ValueError(
                "Invalid send_updates."
            )


        binding = (
            self.prepare_create_event(
                event,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
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
            .events()
            .insert(
                calendarId=
                    str(
                        calendar_id
                    ),
                body=dict(
                    event
                ),
                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.create_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    result.get(
                        "id"
                    ),

                "summary":
                    result.get(
                        "summary"
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },
        )


        return {
            "success":
                True,

            "event":
                result,
        }


    def prepare_update_event(
        self,
        event_id,
        patch,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        patch = dict(
            patch
        )


        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_id":
                str(
                    event_id
                ),

            "patch_sha256":
                self._event_hash(
                    patch
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.update_event",

            "payload":
                payload,

            "display": {
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),

                "changes":
                    self._display_event(
                        patch
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },

            "risk":
                "calendar-write",
        }


    def update_event(
        self,
        event_id,
        patch,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        binding = (
            self.prepare_update_event(
                event_id,
                patch,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
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
            .events()
            .patch(
                calendarId=
                    str(
                        calendar_id
                    ),

                eventId=
                    str(
                        event_id
                    ),

                body=dict(
                    patch
                ),

                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.update_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),
            },
        )


        return {
            "success":
                True,

            "event":
                result,
        }


    @staticmethod
    def prepare_delete_event(
        event_id,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_id":
                str(
                    event_id
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.delete_event",

            "payload":
                payload,

            "display":
                payload,

            "risk":
                "calendar-delete-event",
        }


    def delete_event(
        self,
        event_id,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        binding = (
            self.prepare_delete_event(
                event_id,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
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


        (
            self.service()
            .events()
            .delete(
                calendarId=
                    str(
                        calendar_id
                    ),

                eventId=
                    str(
                        event_id
                    ),

                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.delete_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),
            },
        )


        return {
            "success":
                True,

            "event_id":
                str(
                    event_id
                ),
        }


google_calendar_service = (
    GoogleCalendarService()
)
