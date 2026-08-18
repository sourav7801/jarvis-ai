from __future__ import annotations


from omni.connected_services_v2_status import connected_services_v2_status
from omni.connected_services_v3_gateway import connected_services_v3_gateway
from omni.core_integrity import verify_protected_core
from omni.github_connected import github_connected


class ConnectedServicesV3Status:

    def status(self):

        integrity = verify_protected_core()
        v2 = connected_services_v2_status.status()

        return {
            "protected_core": integrity.ok,
            "v2_preserved": bool(
                v2.get(
                    "recipient_intelligence"
                )
            ),
            "google_connected": bool(
                v2.get(
                    "google_connected"
                )
            ),
            "gmail_thread_intelligence": True,
            "gmail_reply_drafts": True,
            "calendar_freebusy": True,
            "slot_recommendation": True,
            "multi_person_coordination": True,
            "natural_intent_router": True,
            "approval_dashboard": True,
            "github": github_connected.status(
                verify=False
            ),
            "automatic_email_send": False,
            "automatic_calendar_write": False,
            "automatic_github_write": False,
            "github_merge": False,
            "github_force_push": False,
            "gateway": connected_services_v3_gateway.status(),
        }


connected_services_v3_status = ConnectedServicesV3Status()
