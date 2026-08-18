from __future__ import annotations

from datetime import datetime, timedelta, timezone


from omni.google_calendar_service import google_calendar_service
from omni.recipient_intelligence import recipient_resolver


class CalendarAvailabilityEngine:

    MAX_CALENDARS = 50
    MAX_SLOTS = 20


    @staticmethod
    def _dt(value):

        if isinstance(
            value,
            datetime,
        ):
            result = value

        else:
            text = str(value).strip()

            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            result = datetime.fromisoformat(
                text
            )


        if result.tzinfo is None:
            raise ValueError(
                "Availability datetime must include "
                "an explicit UTC offset/timezone."
            )


        return result


    def service(self):
        return google_calendar_service.service()


    def freebusy(
        self,
        calendar_ids,
        start,
        end,
        *,
        time_zone=None,
    ):

        start_dt = self._dt(start)
        end_dt = self._dt(end)


        if end_dt <= start_dt:
            raise ValueError(
                "Availability end must be after start."
            )


        unique = []

        for item in calendar_ids:
            value = str(item).strip()

            if value and value not in unique:
                unique.append(value)


        if not unique:
            unique = ["primary"]


        if len(unique) > self.MAX_CALENDARS:
            raise ValueError(
                "Too many calendars requested."
            )


        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "items": [
                {"id": item}
                for item in unique
            ],
        }


        if time_zone:
            body["timeZone"] = str(
                time_zone
            )


        response = (
            self.service()
            .freebusy()
            .query(body=body)
            .execute()
        )


        calendars = {}
        errors = {}


        for calendar_id, data in response.get(
            "calendars",
            {},
        ).items():

            busy = tuple(
                {
                    "start": item.get("start"),
                    "end": item.get("end"),
                }
                for item in data.get(
                    "busy",
                    (),
                )
            )


            calendars[
                calendar_id
            ] = busy


            if data.get(
                "errors"
            ):
                errors[
                    calendar_id
                ] = tuple(
                    data["errors"]
                )


        return {
            "success": True,
            "time_min": response.get(
                "timeMin",
                start_dt.isoformat(),
            ),
            "time_max": response.get(
                "timeMax",
                end_dt.isoformat(),
            ),
            "calendars": calendars,
            "errors": errors,
        }


    @staticmethod
    def _overlaps(
        candidate_start,
        candidate_end,
        busy_start,
        busy_end,
    ):

        return (
            busy_start < candidate_end
            and busy_end > candidate_start
        )


    def recommend_slots(
        self,
        attendees,
        window_start,
        window_end,
        *,
        duration_minutes=30,
        step_minutes=30,
        calendar_id="primary",
        time_zone=None,
        working_hour_start=8,
        working_hour_end=20,
        strict=True,
        max_slots=10,
    ):

        start_dt = self._dt(
            window_start
        )

        end_dt = self._dt(
            window_end
        )


        if end_dt <= start_dt:
            raise ValueError(
                "Availability window is invalid."
            )


        duration_minutes = int(
            duration_minutes
        )

        step_minutes = int(
            step_minutes
        )

        max_slots = max(
            1,
            min(
                int(max_slots),
                self.MAX_SLOTS,
            ),
        )


        if duration_minutes < 5:
            raise ValueError(
                "Meeting duration must be at least 5 minutes."
            )


        if step_minutes < 5:
            raise ValueError(
                "Slot step must be at least 5 minutes."
            )


        queries = []

        if attendees is None:
            queries = []

        elif isinstance(
            attendees,
            str,
        ):
            queries = [attendees]

        else:
            queries = list(attendees)


        resolution = (
            recipient_resolver
            .resolve_many(
                queries
            )
            if queries
            else {
                "success": True,
                "emails": (),
                "resolved": (),
                "unresolved": (),
                "ambiguous": (),
            }
        )


        if not resolution.get(
            "success",
            False,
        ):
            return {
                "success": False,
                "error": (
                    "Attendee resolution failed."
                ),
                "resolution": resolution,
            }


        calendars = [
            str(calendar_id)
        ]


        for email in resolution.get(
            "emails",
            (),
        ):
            if email not in calendars:
                calendars.append(email)


        availability = self.freebusy(
            calendars,
            start_dt,
            end_dt,
            time_zone=time_zone,
        )


        if (
            strict
            and availability["errors"]
        ):
            return {
                "success": False,
                "error": (
                    "Free/busy information was unavailable "
                    "for one or more calendars."
                ),
                "resolution": resolution,
                "availability": availability,
                "slots": (),
            }


        busy_ranges = []


        for calendar_busy in availability[
            "calendars"
        ].values():

            for busy in calendar_busy:

                busy_start = self._dt(
                    busy["start"]
                )

                busy_end = self._dt(
                    busy["end"]
                )

                busy_ranges.append(
                    (
                        busy_start,
                        busy_end,
                    )
                )


        duration = timedelta(
            minutes=duration_minutes
        )

        step = timedelta(
            minutes=step_minutes
        )


        cursor = start_dt
        slots = []


        while (
            cursor + duration <= end_dt
            and len(slots) < max_slots
        ):

            candidate_end = (
                cursor
                + duration
            )


            within_hours = (
                cursor.hour
                >= int(
                    working_hour_start
                )
                and candidate_end.hour
                <= int(
                    working_hour_end
                )
            )


            conflict = any(
                self._overlaps(
                    cursor,
                    candidate_end,
                    busy_start,
                    busy_end,
                )
                for busy_start, busy_end in busy_ranges
            )


            if within_hours and not conflict:

                slots.append(
                    {
                        "start": cursor.isoformat(),
                        "end": candidate_end.isoformat(),
                        "duration_minutes": duration_minutes,
                    }
                )


            cursor += step


        return {
            "success": True,
            "resolved_attendees": resolution.get(
                "emails",
                (),
            ),
            "calendar_ids": tuple(calendars),
            "availability_errors": availability[
                "errors"
            ],
            "slots": tuple(slots),
            "duration_minutes": duration_minutes,
            "strict": bool(strict),
        }


calendar_availability = CalendarAvailabilityEngine()
