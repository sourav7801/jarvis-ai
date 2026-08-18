import json
import tempfile
import unittest

from pathlib import Path


import main


from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.gmail_service import (
    GmailService,
)

from omni.google_calendar_service import (
    GoogleCalendarService,
)

from omni.google_oauth import (
    GoogleOAuthManager,
)

from omni.google_scopes import (
    GOOGLE_SCOPES,
)

from omni.google_token_vault import (
    GoogleTokenVault,
)

from omni.operator_runtime_schema import (
    from_dict,
)


class ConnectedServicesV1Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_dpapi_available(
        self,
    ):

        self.assertTrue(
            GoogleTokenVault.available()
        )


    def test_scope_count(
        self,
    ):

        self.assertEqual(
            len(
                GOOGLE_SCOPES
            ),
            5,
        )


    def test_no_full_gmail_scope(
        self,
    ):

        self.assertNotIn(
            "https://mail.google.com/",
            GOOGLE_SCOPES,
        )


    def test_no_full_calendar_scope(
        self,
    ):

        self.assertNotIn(
            "https://www.googleapis.com/auth/calendar",
            GOOGLE_SCOPES,
        )


    def test_vault_round_trip(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            vault = GoogleTokenVault(
                Path(
                    tmp
                )
                / "token.dpapi"
            )


            vault.save_text(
                '{"hello":"world"}'
            )


            self.assertEqual(
                vault.load_text(),
                '{"hello":"world"}',
            )


    def test_desktop_client_validation(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            manager = GoogleOAuthManager(
                Path(
                    tmp
                )
                / "configured.json"
            )


            source = (
                Path(
                    tmp
                )
                / "source.json"
            )


            source.write_text(
                json.dumps(
                    {
                        "web": {
                            "client_id":
                                "bad"
                        }
                    }
                ),
                encoding="utf-8",
            )


            with self.assertRaises(
                ValueError
            ):

                manager.install_client_secret(
                    source
                )


    def test_gmail_binding_hashes_body(
        self,
    ):

        binding = (
            GmailService()
            .prepare_create_draft(
                "person@example.com",
                "Subject",
                "Secret body text",
            )
        )


        self.assertIn(
            "body_sha256",
            binding[
                "payload"
            ],
        )


        self.assertNotIn(
            "body",
            binding[
                "payload"
            ],
        )


    def test_gmail_send_binding(
        self,
    ):

        binding = (
            GmailService
            .prepare_send_draft(
                "draft-123"
            )
        )


        self.assertEqual(
            binding[
                "action"
            ],
            "google.gmail.send_draft",
        )


    def test_calendar_binding_hash(
        self,
    ):

        binding = (
            GoogleCalendarService()
            .prepare_create_event(
                {
                    "summary":
                        "Meeting",

                    "start": {
                        "dateTime":
                            "2026-08-19T10:00:00+05:30"
                    },

                    "end": {
                        "dateTime":
                            "2026-08-19T11:00:00+05:30"
                    },
                }
            )
        )


        self.assertIn(
            "event_sha256",
            binding[
                "payload"
            ],
        )


        self.assertNotIn(
            "event",
            binding[
                "payload"
            ],
        )


    def test_gateway_write_not_automatic(
        self,
    ):

        status = (
            connected_services_gateway
            .status()
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


    def test_v4_google_read_action(
        self,
    ):

        plan = from_dict(
            "Search email",

            {
                "steps": [
                    {
                        "action":
                            "google.gmail.search",

                        "payload": {
                            "query":
                                "from:test@example.com",

                            "max_results":
                                5,
                        },
                    }
                ]
            },
        )


        self.assertEqual(
            plan.steps[
                0
            ].action,
            "google.gmail.search",
        )


    def test_v4_gmail_write_interactive(
        self,
    ):

        from omni.operator_runtime_schema import (
            is_interactive,
        )


        self.assertTrue(
            is_interactive(
                "google.gmail.send_draft"
            )
        )


    def test_v4_calendar_write_interactive(
        self,
    ):

        from omni.operator_runtime_schema import (
            is_interactive,
        )


        self.assertTrue(
            is_interactive(
                "google.calendar.create_event"
            )
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main.jarvis_google_status
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_google_connect
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_gmail_search
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_google_events
            )
        )


        self.assertTrue(
            callable(
                main.jarvis_google_contacts
            )
        )


if __name__ == "__main__":

    unittest.main()
