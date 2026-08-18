import unittest
from unittest.mock import patch


import main


from omni.connected_intent_router import ConnectedIntentRouter
from omni.connected_services_v3_gateway import connected_services_v3_gateway
from omni.core_integrity import verify_protected_core
from omni.github_connected import GitHubConnectedService
from omni.operator_runtime_schema import from_dict, is_interactive


class FakeVault:

    def available(self):
        return True

    def exists(self):
        return True

    def load(self):
        return "github_pat_fake_token_abcdefghijklmnopqrstuvwxyz"


class FakeResponse:

    def __init__(
        self,
        status_code,
        data,
    ):
        self.status_code = status_code
        self._data = data
        self.text = ""

    def json(self):
        return self._data


class FakeSession:

    def __init__(self):
        self.calls = []

    def request(
        self,
        method,
        url,
        headers=None,
        params=None,
        json=None,
        timeout=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json": json,
                "timeout": timeout,
            }
        )

        return FakeResponse(
            200,
            {
                "login": "jarvis-test"
            },
        )


class ConnectedServicesV3Tests(
    unittest.TestCase
):

    def test_core(self):
        self.assertTrue(
            verify_protected_core().ok
        )


    def test_intent_email_reply(self):

        result = ConnectedIntentRouter().route(
            "Draft a reply to this email"
        )

        self.assertEqual(
            result["action"],
            "google.gmail.reply_draft",
        )

        self.assertTrue(
            result["requires_approval"]
        )

        self.assertFalse(
            result["auto_execute"]
        )


    def test_intent_calendar_availability(self):

        result = ConnectedIntentRouter().route(
            "Find a time for our meeting"
        )

        self.assertEqual(
            result["action"],
            "google.calendar.recommend_slots",
        )

        self.assertFalse(
            result["requires_approval"]
        )


    def test_intent_github_issue_write(self):

        result = ConnectedIntentRouter().route(
            "Create GitHub issue for this bug"
        )

        self.assertEqual(
            result["action"],
            "github.issue.create",
        )

        self.assertTrue(
            result["requires_approval"]
        )


    def test_github_profile_read(self):

        session = FakeSession()

        service = GitHubConnectedService(
            vault=FakeVault(),
            session=session,
        )

        result = service.profile()

        self.assertEqual(
            result["login"],
            "jarvis-test",
        )

        self.assertEqual(
            session.calls[0]["method"],
            "GET",
        )


    def test_github_issue_binding_hides_body(self):

        service = GitHubConnectedService(
            vault=FakeVault(),
            session=FakeSession(),
        )

        result = service.prepare_create_issue(
            "owner",
            "repo",
            "Bug",
            "Sensitive body",
        )

        self.assertIn(
            "body_sha256",
            result["payload"],
        )

        self.assertNotIn(
            "body",
            result["payload"],
        )


    def test_github_comment_binding_hides_body(self):

        service = GitHubConnectedService(
            vault=FakeVault(),
            session=FakeSession(),
        )

        result = service.prepare_comment(
            "owner",
            "repo",
            5,
            "Private comment",
        )

        self.assertIn(
            "body_sha256",
            result["payload"],
        )

        self.assertNotIn(
            "body",
            result["payload"],
        )


    def test_github_pull_binding_hides_body(self):

        service = GitHubConnectedService(
            vault=FakeVault(),
            session=FakeSession(),
        )

        result = service.prepare_pull(
            "owner",
            "repo",
            "PR",
            "feature",
            "main",
            "Private PR body",
        )

        self.assertIn(
            "body_sha256",
            result["payload"],
        )

        self.assertNotIn(
            "body",
            result["payload"],
        )


    def test_gateway_safety(self):

        status = (
            connected_services_v3_gateway
            .status()
        )

        self.assertFalse(
            status[
                "automatic_email_send"
            ]
        )

        self.assertFalse(
            status[
                "automatic_calendar_write"
            ]
        )

        self.assertFalse(
            status[
                "automatic_github_write"
            ]
        )

        self.assertFalse(
            status[
                "github_merge"
            ]
        )


    def test_v4_gmail_thread_action(self):

        plan = from_dict(
            "Read thread",
            {
                "steps": [
                    {
                        "action": "google.gmail.thread",
                        "payload": {
                            "thread_id": "abc"
                        },
                    }
                ]
            },
        )

        self.assertEqual(
            plan.steps[0].action,
            "google.gmail.thread",
        )


    def test_v4_slot_recommendation_action(self):

        plan = from_dict(
            "Find slot",
            {
                "steps": [
                    {
                        "action": "google.calendar.recommend_slots",
                        "payload": {
                            "attendees": [],
                            "window_start": "2026-08-20T09:00:00+05:30",
                            "window_end": "2026-08-20T18:00:00+05:30",
                        },
                    }
                ]
            },
        )

        self.assertEqual(
            plan.steps[0].action,
            "google.calendar.recommend_slots",
        )


    def test_v4_reply_interactive(self):

        self.assertTrue(
            is_interactive(
                "google.gmail.reply_draft"
            )
        )


    def test_v4_github_issue_interactive(self):

        self.assertTrue(
            is_interactive(
                "github.issue.create"
            )
        )


    def test_v4_github_comment_interactive(self):

        self.assertTrue(
            is_interactive(
                "github.comment.create"
            )
        )


    def test_v4_github_pull_interactive(self):

        self.assertTrue(
            is_interactive(
                "github.pull.create"
            )
        )


    def test_public_apis(self):

        for name in (
            "jarvis_connected_intent",
            "jarvis_gmail_thread",
            "jarvis_prepare_reply_draft",
            "jarvis_create_reply_draft",
            "jarvis_recommend_meeting_slots",
            "jarvis_connected_approvals",
            "jarvis_github_status",
            "jarvis_github_profile",
            "jarvis_github_repos",
            "jarvis_connected_services_v3_status",
        ):
            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":
    unittest.main()
