from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
)

from zoneinfo import (
    ZoneInfo,
)


def _parse_expiry(
    expiry,
    *,
    expiry_time="15:30",
    timezone_name="Asia/Kolkata",
):

    zone = ZoneInfo(
        timezone_name
    )


    if isinstance(
        expiry,
        datetime,
    ):

        result = expiry


        if result.tzinfo is None:

            result = result.replace(
                tzinfo=zone
            )


        return result


    if isinstance(
        expiry,
        date,
    ):

        expiry_date = expiry


    else:

        text = str(
            expiry
        ).strip()


        try:

            result = datetime.fromisoformat(
                text
            )


            if result.tzinfo is None:

                result = result.replace(
                    tzinfo=zone
                )


            if "T" in text:

                return result


            expiry_date = result.date()


        except Exception:

            expiry_date = date.fromisoformat(
                text
            )


    hour, minute = [
        int(
            value
        )

        for value
        in str(
            expiry_time
        ).split(
            ":",
            1,
        )
    ]


    return datetime.combine(
        expiry_date,
        time(
            hour,
            minute,
        ),
        tzinfo=zone,
    )


def expiry_state(
    expiry,
    *,
    now=None,
    expiry_time="15:30",
    timezone_name="Asia/Kolkata",
):

    zone = ZoneInfo(
        timezone_name
    )


    expiry_dt = _parse_expiry(
        expiry,
        expiry_time=expiry_time,
        timezone_name=timezone_name,
    )


    current = (
        now
        if now is not None
        else datetime.now(
            zone
        )
    )


    if current.tzinfo is None:

        current = current.replace(
            tzinfo=zone
        )


    current = current.astimezone(
        zone
    )


    expiry_dt = expiry_dt.astimezone(
        zone
    )


    seconds = (
        expiry_dt
        - current
    ).total_seconds()


    hours = (
        seconds
        / 3600.0
    )


    days = (
        seconds
        / 86400.0
    )


    if seconds < 0:

        phase = "EXPIRED"


    elif current.date() == expiry_dt.date():

        phase = "EXPIRY_DAY"


    elif days <= 3:

        phase = "NEAR_EXPIRY"


    elif days <= 7:

        phase = "SHORT_EXPIRY"


    elif days <= 30:

        phase = "MEDIUM_EXPIRY"


    else:

        phase = "FAR_EXPIRY"


    theta_urgency = max(
        0.0,
        min(
            1.0,
            (
                1.0
                - max(
                    days,
                    0.0,
                )
                / 7.0
            ),
        ),
    )


    return {
        "expiry":
            expiry_dt.isoformat(),

        "now":
            current.isoformat(),

        "seconds_to_expiry":
            seconds,

        "hours_to_expiry":
            hours,

        "days_to_expiry":
            days,

        "phase":
            phase,

        "theta_urgency_heuristic":
            theta_urgency,

        "research_only":
            True,
    }
