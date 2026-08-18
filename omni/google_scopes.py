GMAIL_READ_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly"
)

GMAIL_COMPOSE_SCOPE = (
    "https://www.googleapis.com/auth/gmail.compose"
)

CALENDAR_READ_SCOPE = (
    "https://www.googleapis.com/auth/calendar.readonly"
)

CALENDAR_EVENTS_SCOPE = (
    "https://www.googleapis.com/auth/calendar.events"
)

CONTACTS_READ_SCOPE = (
    "https://www.googleapis.com/auth/contacts.readonly"
)


GOOGLE_SCOPES = (
    GMAIL_READ_SCOPE,
    GMAIL_COMPOSE_SCOPE,
    CALENDAR_READ_SCOPE,
    CALENDAR_EVENTS_SCOPE,
    CONTACTS_READ_SCOPE,
)


SERVICE_CAPABILITIES = {
    "gmail": {
        "read":
            True,

        "search":
            True,

        "draft":
            True,

        "send":
            True,

        "delete":
            False,

        "permanent_delete":
            False,
    },

    "calendar": {
        "read":
            True,

        "create_event":
            True,

        "update_event":
            True,

        "delete_event":
            True,

        "calendar_acl_write":
            False,

        "calendar_delete":
            False,
    },

    "contacts": {
        "read":
            True,

        "search":
            True,

        "create":
            False,

        "update":
            False,

        "delete":
            False,
    },
}
