from __future__ import annotations

from threading import RLock
import uuid


_LOCK = RLock()
_SESSIONS: dict[str, str] = {}


def _channel(
    channel: str | None,
) -> str:

    value = str(
        channel or "default"
    ).strip().lower()

    return value or "default"


def get_session_id(
    channel: str = "default",
) -> str:
    """
    Return one stable session ID per runtime channel.

    Stable for the lifetime of the JARVIS process.
    """

    key = _channel(
        channel
    )

    with _LOCK:

        value = _SESSIONS.get(
            key
        )

        if value is None:

            value = (
                f"{key}-"
                f"{uuid.uuid4().hex}"
            )

            _SESSIONS[
                key
            ] = value

        return value


def set_session_id(
    session_id: str,
    channel: str = "default",
) -> str:

    value = str(
        session_id or ""
    ).strip()

    if not value:
        raise ValueError(
            "session_id cannot be empty"
        )

    key = _channel(
        channel
    )

    with _LOCK:
        _SESSIONS[
            key
        ] = value

    return value


def new_session(
    channel: str = "default",
) -> str:

    key = _channel(
        channel
    )

    value = (
        f"{key}-"
        f"{uuid.uuid4().hex}"
    )

    with _LOCK:
        _SESSIONS[
            key
        ] = value

    return value
