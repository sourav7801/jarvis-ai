import tempfile
import unittest

from pathlib import Path


import main


from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.connected_workflows import (
    ConnectedWorkflowIntelligence,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.operator_runtime_schema import (
    from_dict,
    is_interactive,
)

from omni.recipient_intelligence import (
    RecipientCandidate,
    RecipientResolver,
    email_address,
    valid_email,
)


class FakeContacts:

    def __init__(
        self,
        contacts,
    ):

        self.contacts = contacts


    def search(
        self,
        query,
        max_results=20,
    ):

        return {
            "success":
                True,

            "contacts":
                tuple(
                    self.contacts
                ),
        }


class FakeGmail:

    def __init__(
        self,
        messages=(),
    ):

        self.messages = tuple(
            messages
        )


    def search(
        self,
        query,
        max_results=20,
    ):

        return {
            "success":
                True,

            "messages":
                self.messages,
        }


class ConnectedServicesV2Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_email_validation(
        self,
    ):

        self.assertTrue(
            valid_email(
                "person@example.com"
            )
        )


        self.assertEqual(
            email_address(
                "Person <person@example.com>"
            ),
            "person@example.com",
        )


    def test_direct_email_resolution(
        self,
    ):

        resolver = RecipientResolver(
            contacts=
                FakeContacts(
                    ()
                ),

            gmail=
                FakeGmail(),
        )


        result = resolver.resolve(
            "person@example.com"
        )


        self.assertTrue(
            result[
                "resolved"
            ]
        )


        self.assertEqual(
            result[
                "best"
            ][
                "source"
            ],
            "direct",
        )


    def test_contact_name_resolution(
        self,
    ):

        resolver = RecipientResolver(
            contacts=
                FakeContacts(
                    (
                        {
                            "name":
                                "Rahul Kumar",

                            "emails": (
                                "rahul@example.com",
                            ),

                            "resource_name":
                                "people/1",
                        },
                    )
                ),

            gmail=
                FakeGmail(),
        )


        result = resolver.resolve(
            "Rahul Kumar",
            include_gmail_history=False,
        )


        self.assertTrue(
            result[
                "resolved"
            ]
        )


        self.assertEqual(
            result[
                "best"
            ][
                "email"
            ],
            "rahul@example.com",
        )


    def test_ambiguity_blocks(
        self,
    ):

        resolver = RecipientResolver(
            contacts=
                FakeContacts(
                    ()
                ),

            gmail=
                FakeGmail(),
        )


        candidates = (
            RecipientCandidate(
                source=
                    "contacts",

                name=
                    "Rahul Sharma",

                email=
                    "rahul1@example.com",

                score=
                    0.95,

                metadata={},
            ),

            RecipientCandidate(
                source=
                    "contacts",

                name=
                    "Rahul Sharma",

                email=
                    "rahul2@example.com",

                score=
                    0.94,

                metadata={},
            ),
        )


        result = resolver.resolve_candidates(
            "Rahul Sharma",
            candidates,
        )


        self.assertTrue(
            result[
                "ambiguous"
            ]
        )


        self.assertFalse(
            result[
                "resolved"
            ]
        )


    def test_resolve_many_deduplicates(
        self,
    ):

        resolver = RecipientResolver(
            contacts=
                FakeContacts(
                    ()
                ),

            gmail=
                FakeGmail(),
        )


        result = resolver.resolve_many(
            (
                "a@example.com",
                "a@example.com",
                "b@example.com",
            )
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertEqual(
            result[
                "emails"
            ],
            (
                "a@example.com",
                "b@example.com",
            ),
        )


    def test_timezone_required(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            ConnectedWorkflowIntelligence._datetime(
                "2026-08-20T10:00:00"
            )


    def test_timezone_accepted(
        self,
    ):

        result = (
            ConnectedWorkflowIntelligence._datetime(
                "2026-08-20T10:00:00+05:30"
            )
        )


        self.assertIsNotNone(
            result.tzinfo
        )


    def test_v4_contact_resolution_action(
        self,
    ):

        plan = from_dict(
            "Resolve Rahul",

            {
                "steps": [
                    {
                        "action":
                            "google.contacts.resolve",

                        "payload": {
                            "query":
                                "Rahul"
                        },
                    }
                ]
            },
        )


        self.assertEqual(
            plan.steps[
                0
            ].action,
            "google.contacts.resolve",
        )


    def test_v4_draft_to_contact_interactive(
        self,
    ):

        self.assertTrue(
            is_interactive(
                "google.gmail.draft_to_contact"
            )
        )


    def test_v4_schedule_interactive(
        self,
    ):

        self.assertTrue(
            is_interactive(
                "google.calendar.schedule_meeting"
            )
        )


        self.assertTrue(
            is_interactive(
                "google.calendar.schedule_from_email"
            )
        )


    def test_gateway_safety(
        self,
    ):

        status = (
            connected_services_gateway
            .status()
        )


        self.assertTrue(
            status[
                "ambiguity_blocking"
            ]
        )


        self.assertFalse(
            status[
                "automatic_send"
            ]
        )


        self.assertFalse(
            status[
                "automatic_calendar_write"
            ]
        )


        self.assertFalse(
            status[
                "automatic_conflict_override"
            ]
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main.jarvis_resolve_recipient
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_prepare_draft_to
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_check_calendar_conflicts
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_prepare_meeting
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_prepare_meeting_from_email
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_connected_services_v2_status
            )
        )


if __name__ == "__main__":

    unittest.main()
