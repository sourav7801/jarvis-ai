from __future__ import annotations


from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.google_oauth import (
    google_oauth,
)


class ConnectedServicesV2Status:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        oauth = (
            google_oauth.status()
        )


        gateway = (
            connected_services_gateway
            .status()
        )


        return {
            "protected_core":
                integrity.ok,

            "google_connected":
                bool(
                    oauth.get(
                        "connected"
                    )
                ),

            "token_encrypted":
                bool(
                    oauth.get(
                        "token_encrypted"
                    )
                ),

            "recipient_intelligence":
                True,

            "contacts_resolution":
                True,

            "gmail_history_resolution":
                True,

            "ambiguity_blocking":
                True,

            "direct_email_resolution":
                True,

            "calendar_conflict_detection":
                True,

            "meeting_planner":
                True,

            "email_to_calendar":
                True,

            "draft_to_contact":
                True,

            "automatic_email_send":
                False,

            "automatic_calendar_write":
                False,

            "automatic_conflict_override":
                False,

            "contact_write":
                False,

            "gateway":
                gateway,
        }


connected_services_v2_status = (
    ConnectedServicesV2Status()
)
