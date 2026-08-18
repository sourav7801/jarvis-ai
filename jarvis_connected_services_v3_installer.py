from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

INTENT = ROOT / "omni" / "connected_intent_router.py"
THREADS = ROOT / "omni" / "email_thread_intelligence.py"
AVAILABILITY = ROOT / "omni" / "calendar_availability.py"
GITHUB = ROOT / "omni" / "github_connected.py"
DASHBOARD = ROOT / "omni" / "connected_approval_dashboard.py"
V3_GATEWAY = ROOT / "omni" / "connected_services_v3_gateway.py"
V3_STATUS = ROOT / "omni" / "connected_services_v3_status.py"

SCHEMA = ROOT / "omni" / "operator_runtime_schema.py"
RUNTIME = ROOT / "omni" / "operator_runtime.py"

TEST = ROOT / "tests" / "test_connected_services_v3.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"
ARCHIVE = ROOT / "archive" / "connected_services_v3"

ARCHIVE.mkdir(parents=True, exist_ok=True)

FILES = [
    MAIN,
    APP,
    INTENT,
    THREADS,
    AVAILABILITY,
    GITHUB,
    DASHBOARD,
    V3_GATEWAY,
    V3_STATUS,
    SCHEMA,
    RUNTIME,
    TEST,
]

BACKUPS = {}


def run(*args, capture=False):
    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(source).lstrip(),
        encoding="utf-8",
    )


def rollback():
    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():
        backup = ARCHIVE / path.relative_to(ROOT)

        if existed:
            shutil.copy2(backup, path)
        else:
            path.unlink(missing_ok=True)

    print("JARVIS source restored.")


print("=" * 80)
print("JARVIS CONNECTED SERVICES V3")
print("INTENT + THREADS + AVAILABILITY + GITHUB + APPROVAL DASHBOARD")
print("=" * 80)


# ============================================================
# 0. BACKUP
# ============================================================

for path in FILES:
    BACKUPS[path] = path.exists()

    if path.exists():
        destination = ARCHIVE / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


# ============================================================
# 1. VERIFY 450 CHECKPOINT
# ============================================================

print()
print("Checking Connected Services V2 / 450 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.connected_services_v2_status import connected_services_v2_status; "
        "v=connected_services_v2_status.status(); "
        "assert v['google_connected']; "
        "assert v['token_encrypted']; "
        "assert v['recipient_intelligence']; "
        "assert v['ambiguity_blocking']; "
        "from omni.operator_runtime import unified_operator_runtime; "
        "from omni.vision_runtime import vision_runtime; "
        "assert vision_runtime.status()['vision_ready']; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V4: PASS'); "
        "print('Connected Services V2: PASS'); "
        "print('Google OAuth: PASS'); "
        "print('Recipient intelligence: PASS'); "
        "print('Qwen3-VL vision: PASS')"
    ),
)


if r.returncode:
    print("BASELINE FAILURE")
    sys.exit(1)


manifest = json.loads(
    MANIFEST.read_text(encoding="utf-8")
)

PROTECTED = {
    relative: sha(ROOT / relative)
    for relative in manifest.get("files", {})
}

print("Protected files:", len(PROTECTED))
print("Baseline: PASS")


# ============================================================
# 2. NATURAL-LANGUAGE CONNECTED-SERVICE INTENT ROUTER
# ============================================================

write(
    INTENT,
    r'''
from __future__ import annotations

import re


WRITE_ACTIONS = {
    "google.gmail.reply_draft",
    "google.gmail.draft_to_contact",
    "google.gmail.send_draft",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
}


class ConnectedIntentRouter:

    def route(self, request):

        text = " ".join(
            str(request).strip().lower().split()
        )

        result = {
            "success": True,
            "request": str(request),
            "intent": "unknown",
            "action": None,
            "confidence": 0.0,
            "requires_approval": False,
            "auto_execute": False,
            "reason": "No deterministic connected-service rule matched.",
            "payload_hints": {},
        }

        if not text:
            result["success"] = False
            result["reason"] = "Request is empty."
            return result


        rules = (
            (
                (
                    "reply to this email",
                    "reply to the email",
                    "reply to this thread",
                    "draft a reply",
                    "prepare a reply",
                ),
                "email.reply",
                "google.gmail.reply_draft",
                0.93,
            ),

            (
                (
                    "email ",
                    "send an email",
                    "draft an email",
                    "write an email",
                ),
                "email.compose",
                "google.gmail.draft_to_contact",
                0.84,
            ),

            (
                (
                    "find email",
                    "search email",
                    "search gmail",
                    "find mail",
                ),
                "email.search",
                "google.gmail.search",
                0.91,
            ),

            (
                (
                    "email thread",
                    "gmail thread",
                    "read thread",
                ),
                "email.thread",
                "google.gmail.thread",
                0.90,
            ),

            (
                (
                    "free time",
                    "available slot",
                    "availability",
                    "find a time",
                    "find time for",
                    "when are we free",
                ),
                "calendar.availability",
                "google.calendar.recommend_slots",
                0.92,
            ),

            (
                (
                    "schedule a meeting",
                    "book a meeting",
                    "create a meeting",
                    "calendar meeting",
                ),
                "calendar.schedule",
                "google.calendar.schedule_meeting",
                0.91,
            ),

            (
                (
                    "resolve contact",
                    "find contact",
                    "email address for",
                    "contact details for",
                ),
                "contact.resolve",
                "google.contacts.resolve",
                0.89,
            ),

            (
                (
                    "github issues",
                    "list issues",
                    "show issues",
                ),
                "github.issues",
                "github.issues",
                0.92,
            ),

            (
                (
                    "github pull requests",
                    "list pull requests",
                    "show pull requests",
                    "show prs",
                    "list prs",
                ),
                "github.pulls",
                "github.pulls",
                0.92,
            ),

            (
                (
                    "create github issue",
                    "open github issue",
                    "create an issue",
                    "open an issue",
                ),
                "github.issue.create",
                "github.issue.create",
                0.93,
            ),

            (
                (
                    "comment on github",
                    "comment on issue",
                    "comment on pr",
                    "add github comment",
                ),
                "github.comment.create",
                "github.comment.create",
                0.92,
            ),

            (
                (
                    "create pull request",
                    "open pull request",
                    "create a pr",
                    "open a pr",
                ),
                "github.pull.create",
                "github.pull.create",
                0.94,
            ),

            (
                (
                    "github repositories",
                    "github repos",
                    "list repositories",
                    "list repos",
                ),
                "github.repos",
                "github.repos",
                0.88,
            ),
        )


        for phrases, intent, action, confidence in rules:

            if any(
                phrase in text
                for phrase in phrases
            ):

                result.update(
                    {
                        "intent": intent,
                        "action": action,
                        "confidence": confidence,
                        "requires_approval": (
                            action in WRITE_ACTIONS
                        ),
                        "auto_execute": False,
                        "reason": (
                            "Deterministic connected-service "
                            "intent rule matched."
                        ),
                    }
                )

                return result


        if re.search(
            r"\bgithub\b",
            text,
        ):
            result.update(
                {
                    "intent": "github.profile",
                    "action": "github.profile",
                    "confidence": 0.60,
                    "reason": (
                        "GitHub mentioned but no higher-confidence "
                        "operation was identified."
                    ),
                }
            )


        return result


connected_intent_router = ConnectedIntentRouter()
'''
)


# ============================================================
# 3. GMAIL THREAD + REPLY-DRAFT INTELLIGENCE
# ============================================================

write(
    THREADS,
    r'''
from __future__ import annotations

from email.message import EmailMessage
from email.utils import getaddresses, parseaddr

import base64
import hashlib


from omni.approval_queue import approval_queue
from omni.gmail_service import gmail_service
from omni.google_audit import google_audit


def _dedupe(addresses):

    output = []
    seen = set()

    for address in addresses:
        name, email = parseaddr(
            str(address)
        )

        email = email.strip().lower()

        if not email or "@" not in email:
            continue

        if email in seen:
            continue

        seen.add(email)

        output.append(
            (
                name.strip(),
                email,
            )
        )

    return output


class EmailThreadIntelligence:

    def service(self):
        return gmail_service.service()


    def _profile_email(self):

        profile = (
            self.service()
            .users()
            .getProfile(userId="me")
            .execute()
        )

        return str(
            profile.get("emailAddress", "")
        ).lower()


    def thread(
        self,
        thread_id,
    ):

        raw = (
            self.service()
            .users()
            .threads()
            .get(
                userId="me",
                id=str(thread_id),
                format="full",
            )
            .execute()
        )


        messages = []

        for message in raw.get(
            "messages",
            (),
        ):
            payload = message.get(
                "payload",
                {},
            )

            headers = gmail_service._headers(
                payload
            )

            plain, html = gmail_service._parts(
                payload
            )

            messages.append(
                {
                    "id": message.get("id"),
                    "thread_id": message.get("threadId"),
                    "from": headers.get("from"),
                    "to": headers.get("to"),
                    "cc": headers.get("cc"),
                    "reply_to": headers.get("reply-to"),
                    "subject": headers.get("subject"),
                    "date": headers.get("date"),
                    "message_id": headers.get("message-id"),
                    "references": headers.get("references"),
                    "snippet": message.get("snippet", ""),
                    "text": "\n".join(plain)[:50000],
                    "html": "\n".join(html)[:50000],
                }
            )


        result = {
            "success": True,
            "id": raw.get("id"),
            "history_id": raw.get("historyId"),
            "snippet": raw.get("snippet"),
            "messages": tuple(messages),
            "message_count": len(messages),
        }


        google_audit.record(
            "gmail.thread.get",
            success=True,
            metadata={
                "thread_id": str(thread_id),
                "messages": len(messages),
            },
        )


        return result


    def _reply_context(
        self,
        thread_id,
        *,
        reply_all=False,
    ):

        thread = self.thread(
            thread_id
        )

        messages = list(
            thread.get(
                "messages",
                (),
            )
        )

        if not messages:
            raise ValueError(
                "Gmail thread contains no messages."
            )


        self_email = self._profile_email()


        selected = None

        for candidate in reversed(
            messages
        ):
            sender = parseaddr(
                str(
                    candidate.get(
                        "from",
                        "",
                    )
                )
            )[1].lower()

            if sender and sender != self_email:
                selected = candidate
                break


        if selected is None:
            selected = messages[-1]


        reply_address = (
            selected.get("reply_to")
            or selected.get("from")
            or ""
        )


        targets = _dedupe(
            [reply_address]
        )


        if not targets:
            raise ValueError(
                "Could not determine reply recipient."
            )


        to_addresses = [
            email
            for _, email in targets
            if email != self_email
        ]


        cc_addresses = []


        if reply_all:

            original = []

            original.extend(
                getaddresses(
                    [
                        str(
                            selected.get(
                                "to",
                                "",
                            )
                        )
                    ]
                )
            )

            original.extend(
                getaddresses(
                    [
                        str(
                            selected.get(
                                "cc",
                                "",
                            )
                        )
                    ]
                )
            )


            for name, email in original:
                email = email.strip().lower()

                if (
                    email
                    and email != self_email
                    and email not in to_addresses
                    and email not in cc_addresses
                ):
                    cc_addresses.append(email)


        subject = str(
            selected.get(
                "subject",
                "",
            )
            or ""
        ).strip()


        if not subject.lower().startswith(
            "re:"
        ):
            subject = (
                "Re: "
                + subject
            ).strip()


        message_id = selected.get(
            "message_id"
        )


        references = str(
            selected.get(
                "references",
                "",
            )
            or ""
        ).strip()


        if message_id:
            references = (
                references
                + " "
                + str(message_id)
            ).strip()


        return {
            "thread": thread,
            "selected_message": selected,
            "self_email": self_email,
            "to": tuple(to_addresses),
            "cc": tuple(cc_addresses),
            "subject": subject,
            "in_reply_to": message_id,
            "references": references or None,
        }


    def prepare_reply(
        self,
        thread_id,
        body,
        *,
        reply_all=False,
    ):

        context = self._reply_context(
            thread_id,
            reply_all=reply_all,
        )


        body_text = str(body)


        payload = {
            "thread_id": str(thread_id),
            "to": tuple(context["to"]),
            "cc": tuple(context["cc"]),
            "subject": context["subject"],
            "reply_all": bool(reply_all),
            "body_sha256": hashlib.sha256(
                body_text.encode("utf-8")
            ).hexdigest(),
            "body_length": len(body_text),
            "in_reply_to": context["in_reply_to"],
        }


        return {
            "success": True,
            "action": "google.gmail.reply_draft",
            "payload": payload,
            "display": {
                "thread_id": str(thread_id),
                "to": tuple(context["to"]),
                "cc": tuple(context["cc"]),
                "subject": context["subject"],
                "reply_all": bool(reply_all),
                "body_length": len(body_text),
                "body_sha256_prefix": (
                    payload["body_sha256"][:12]
                ),
            },
            "risk": "email-reply-draft",
            "context": context,
        }


    def create_reply_draft(
        self,
        thread_id,
        body,
        *,
        reply_all=False,
        approval_id=None,
    ):

        prepared = self.prepare_reply(
            thread_id,
            body,
            reply_all=reply_all,
        )


        if not approval_id:

            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        context = prepared["context"]

        message = EmailMessage()

        message["To"] = ", ".join(
            context["to"]
        )

        if context["cc"]:
            message["Cc"] = ", ".join(
                context["cc"]
            )

        message["Subject"] = context["subject"]


        if context["in_reply_to"]:
            message["In-Reply-To"] = str(
                context["in_reply_to"]
            )

        if context["references"]:
            message["References"] = str(
                context["references"]
            )


        message.set_content(
            str(body)
        )


        raw = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")


        result = (
            self.service()
            .users()
            .drafts()
            .create(
                userId="me",
                body={
                    "message": {
                        "raw": raw,
                        "threadId": str(thread_id),
                    }
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.reply_draft.create",
            success=True,
            metadata={
                "thread_id": str(thread_id),
                "draft_id": result.get("id"),
                "to": tuple(context["to"]),
                "subject": context["subject"],
            },
        )


        return {
            "success": True,
            "draft_id": result.get("id"),
            "message": result.get("message"),
            "thread_id": str(thread_id),
        }


email_thread_intelligence = EmailThreadIntelligence()
'''
)


# ============================================================
# 4. CALENDAR FREE/BUSY + MULTI-PERSON SLOT ENGINE
# ============================================================

write(
    AVAILABILITY,
    r'''
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
'''
)


# ============================================================
# 5. LOCAL GITHUB AUTH + GOVERNED REST WORKFLOWS
# ============================================================

write(
    GITHUB,
    r'''
from __future__ import annotations

from pathlib import Path

import getpass
import hashlib
import json
import os
import time
import uuid

import requests


from omni.approval_queue import approval_queue


API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"


class GitHubTokenVault:

    DESCRIPTION = "JARVIS GitHub API Token"


    def __init__(
        self,
        path=None,
    ):
        self.path = Path(
            path
            or (
                Path("data")
                / "credentials"
                / "github_token.dpapi"
            )
        )


    @staticmethod
    def available():

        try:
            import win32crypt
            return True

        except Exception:
            return False


    def exists(self):

        return (
            self.path.exists()
            and self.path.stat().st_size > 0
        )


    def save(self, token):

        import win32crypt

        token = str(token).strip()

        if len(token) < 20:
            raise ValueError(
                "GitHub token appears invalid."
            )


        encrypted = win32crypt.CryptProtectData(
            token.encode("utf-8"),
            self.DESCRIPTION,
            None,
            None,
            None,
            0,
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = self.path.with_suffix(
            ".tmp"
        )

        temporary.write_bytes(
            encrypted
        )


        try:
            os.chmod(
                temporary,
                0o600,
            )

        except Exception:
            pass


        temporary.replace(
            self.path
        )


        return {
            "success": True,
            "encrypted": True,
            "path": str(self.path),
        }


    def load(self):

        import win32crypt

        if not self.exists():
            raise RuntimeError(
                "Local JARVIS GitHub token is not configured."
            )


        encrypted = self.path.read_bytes()

        description, data = win32crypt.CryptUnprotectData(
            encrypted,
            None,
            None,
            None,
            0,
        )

        return data.decode(
            "utf-8"
        ).strip()


    def delete(self):

        existed = self.path.exists()

        self.path.unlink(
            missing_ok=True
        )

        return {
            "success": True,
            "existed": existed,
        }


github_token_vault = GitHubTokenVault()


class GitHubConnectedService:

    def __init__(
        self,
        vault=None,
        session=None,
    ):
        self.vault = (
            vault
            or github_token_vault
        )

        self.session = (
            session
            or requests.Session()
        )

        self.audit_path = (
            Path("data")
            / "audit"
            / "github_services.jsonl"
        )


    def _audit(
        self,
        action,
        *,
        success,
        metadata=None,
        error=None,
    ):

        record = {
            "audit_id": (
                "github-audit-"
                + uuid.uuid4().hex[:16]
            ),
            "timestamp": time.time(),
            "action": str(action),
            "success": bool(success),
            "metadata": metadata or {},
            "error": (
                str(error)[:1000]
                if error
                else None
            ),
        }


        self.audit_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        with self.audit_path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


        return record


    def connect_interactive(self):

        token = getpass.getpass(
            "GitHub fine-grained token: "
        ).strip()


        result = self.vault.save(
            token
        )


        try:
            profile = self.profile()

        except Exception:
            self.vault.delete()
            raise


        return {
            "success": True,
            "encrypted": True,
            "login": profile.get(
                "login"
            ),
        }


    def disconnect(self):
        return self.vault.delete()


    def _headers(self):

        token = self.vault.load()

        return {
            "Accept": "application/vnd.github+json",
            "Authorization": (
                "Bearer "
                + token
            ),
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "JARVIS-Connected-Services",
        }


    def _request(
        self,
        method,
        path,
        *,
        params=None,
        body=None,
    ):

        url = (
            API_BASE
            + "/"
            + str(path).lstrip("/")
        )


        response = self.session.request(
            str(method).upper(),
            url,
            headers=self._headers(),
            params=params,
            json=body,
            timeout=20,
        )


        if response.status_code == 204:
            return {}


        try:
            data = response.json()

        except Exception:
            data = {
                "message": (
                    response.text[:1000]
                )
            }


        if not (
            200
            <= response.status_code
            < 300
        ):
            message = (
                data.get(
                    "message"
                )
                if isinstance(
                    data,
                    dict,
                )
                else str(data)
            )

            raise RuntimeError(
                "GitHub API "
                + str(
                    response.status_code
                )
                + ": "
                + str(message)
            )


        return data


    def status(
        self,
        *,
        verify=False,
    ):

        result = {
            "vault_available": (
                self.vault.available()
            ),
            "token_encrypted": (
                self.vault.exists()
            ),
            "connected": False,
            "login": None,
            "api_version": API_VERSION,
            "automatic_write": False,
            "merge_supported": False,
            "force_push_supported": False,
        }


        if (
            verify
            and result[
                "token_encrypted"
            ]
        ):
            try:
                profile = self.profile()

                result["connected"] = True
                result["login"] = profile.get(
                    "login"
                )

            except Exception as exc:
                result["error"] = (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                )

        else:
            result["connected"] = result[
                "token_encrypted"
            ]


        return result


    # --------------------------------------------------------
    # READS
    # --------------------------------------------------------

    def profile(self):

        result = self._request(
            "GET",
            "/user",
        )

        self._audit(
            "github.profile",
            success=True,
            metadata={
                "login": result.get(
                    "login"
                )
            },
        )

        return result


    def repos(
        self,
        *,
        per_page=30,
    ):

        return self._request(
            "GET",
            "/user/repos",
            params={
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
                "sort": "updated",
            },
        )


    def issues(
        self,
        owner,
        repo,
        *,
        state="open",
        per_page=30,
    ):

        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            params={
                "state": str(state),
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
            },
        )


    def pulls(
        self,
        owner,
        repo,
        *,
        state="open",
        per_page=30,
    ):

        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": str(state),
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
            },
        )


    # --------------------------------------------------------
    # GOVERNED WRITES
    # --------------------------------------------------------

    @staticmethod
    def _hash_text(value):

        text = str(
            value
            or ""
        )

        return {
            "sha256": hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest(),
            "length": len(text),
        }


    def prepare_create_issue(
        self,
        owner,
        repo,
        title,
        body="",
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "title": str(title),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.issue.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "title": str(title),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-write",
        }


    def create_issue(
        self,
        owner,
        repo,
        title,
        body="",
        *,
        approval_id=None,
    ):

        prepared = self.prepare_create_issue(
            owner,
            repo,
            title,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues",
            body={
                "title": str(title),
                "body": str(body),
            },
        )


        self._audit(
            "github.issue.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "number": result.get(
                    "number"
                ),
            },
        )


        return {
            "success": True,
            "issue": result,
        }


    def prepare_comment(
        self,
        owner,
        repo,
        issue_number,
        body,
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "issue_number": int(
                issue_number
            ),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.comment.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "issue_number": int(
                    issue_number
                ),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-write",
        }


    def create_comment(
        self,
        owner,
        repo,
        issue_number,
        body,
        *,
        approval_id=None,
    ):

        prepared = self.prepare_comment(
            owner,
            repo,
            issue_number,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            (
                f"/repos/{owner}/{repo}"
                f"/issues/{int(issue_number)}/comments"
            ),
            body={
                "body": str(body)
            },
        )


        self._audit(
            "github.comment.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "issue_number": int(
                    issue_number
                ),
                "comment_id": result.get(
                    "id"
                ),
            },
        )


        return {
            "success": True,
            "comment": result,
        }


    def prepare_pull(
        self,
        owner,
        repo,
        title,
        head,
        base,
        body="",
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "title": str(title),
            "head": str(head),
            "base": str(base),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.pull.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "title": str(title),
                "head": str(head),
                "base": str(base),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-pull-request-write",
        }


    def create_pull(
        self,
        owner,
        repo,
        title,
        head,
        base,
        body="",
        *,
        approval_id=None,
    ):

        prepared = self.prepare_pull(
            owner,
            repo,
            title,
            head,
            base,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            body={
                "title": str(title),
                "head": str(head),
                "base": str(base),
                "body": str(body),
            },
        )


        self._audit(
            "github.pull.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "number": result.get(
                    "number"
                ),
            },
        )


        return {
            "success": True,
            "pull": result,
        }


github_connected = GitHubConnectedService()
'''
)


# ============================================================
# 6. CONNECTED APPROVAL DASHBOARD
# ============================================================

write(
    DASHBOARD,
    r'''
from __future__ import annotations

import time


from omni.approval_queue import approval_queue


SENSITIVE_DISPLAY_KEYS = {
    "body",
    "body_preview",
    "message_body",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
}


def _sanitize(value):

    if isinstance(
        value,
        dict,
    ):
        output = {}

        for key, child in value.items():

            if str(
                key
            ).lower() in SENSITIVE_DISPLAY_KEYS:
                output[
                    str(key)
                ] = "<redacted>"

            else:
                output[
                    str(key)
                ] = _sanitize(
                    child
                )

        return output


    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _sanitize(item)
            for item in value
        ]


    return value


class ConnectedApprovalDashboard:

    def _pending_raw(self):

        value = approval_queue.pending()

        if value is None:
            return []

        if isinstance(
            value,
            dict,
        ):
            return list(
                value.values()
            )

        return list(value)


    @staticmethod
    def _service(action):

        action = str(
            action
            or ""
        )

        if action.startswith(
            "google.gmail."
        ):
            return "gmail"

        if action.startswith(
            "google.calendar."
        ):
            return "calendar"

        if action.startswith(
            "google.contacts."
        ):
            return "contacts"

        if action.startswith(
            "github."
        ):
            return "github"

        return "other"


    def pending(self):

        rows = []

        now = time.time()


        for item in self._pending_raw():

            if not isinstance(
                item,
                dict,
            ):
                continue


            action = item.get(
                "action"
            )


            if not (
                str(action).startswith(
                    "google."
                )
                or str(action).startswith(
                    "github."
                )
            ):
                continue


            expires_at = item.get(
                "expires_at"
            )


            rows.append(
                {
                    "approval_id": item.get(
                        "approval_id"
                    ),
                    "service": self._service(
                        action
                    ),
                    "action": action,
                    "risk": item.get(
                        "risk"
                    ),
                    "status": item.get(
                        "status"
                    ),
                    "created_at": item.get(
                        "created_at"
                    ),
                    "expires_at": expires_at,
                    "expired": bool(
                        expires_at
                        and float(expires_at) <= now
                    ),
                    "display": _sanitize(
                        item.get(
                            "display",
                            {},
                        )
                    ),
                }
            )


        rows.sort(
            key=lambda row:
                float(
                    row.get(
                        "created_at"
                    )
                    or 0
                ),
            reverse=True,
        )


        return {
            "success": True,
            "count": len(rows),
            "pending": tuple(rows),
            "automatic_approval": False,
        }


connected_approval_dashboard = ConnectedApprovalDashboard()
'''
)



# ============================================================
# 7. V3 WRAPPER GATEWAY
# ============================================================

write(
    V3_GATEWAY,
    r'''
from __future__ import annotations


from omni.calendar_availability import calendar_availability
from omni.connected_services_gateway import (
    READ_ACTIONS as V2_READ_ACTIONS,
    WRITE_ACTIONS as V2_WRITE_ACTIONS,
    connected_services_gateway,
)
from omni.email_thread_intelligence import email_thread_intelligence
from omni.github_connected import github_connected


V3_READ_ACTIONS = {
    "google.gmail.thread",
    "google.calendar.recommend_slots",

    "github.profile",
    "github.repos",
    "github.issues",
    "github.pulls",
}


V3_WRITE_ACTIONS = {
    "google.gmail.reply_draft",

    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
}


READ_ACTIONS = (
    set(V2_READ_ACTIONS)
    | V3_READ_ACTIONS
)


WRITE_ACTIONS = (
    set(V2_WRITE_ACTIONS)
    | V3_WRITE_ACTIONS
)


class ConnectedServicesV3Gateway:

    def status(self):

        return {
            "read_actions": tuple(
                sorted(
                    READ_ACTIONS
                )
            ),
            "write_actions": tuple(
                sorted(
                    WRITE_ACTIONS
                )
            ),
            "gmail_threads": True,
            "gmail_reply_drafts": True,
            "calendar_freebusy": True,
            "calendar_slot_recommendation": True,
            "multi_person_coordination": True,
            "github": github_connected.status(
                verify=False
            ),
            "automatic_email_send": False,
            "automatic_calendar_write": False,
            "automatic_github_write": False,
            "github_merge": False,
            "github_force_push": False,
        }


    def prepare(
        self,
        action,
        payload,
    ):

        payload = dict(
            payload
        )


        if action in V2_WRITE_ACTIONS:
            return connected_services_gateway.prepare(
                action,
                payload,
            )


        if action == "google.gmail.reply_draft":

            return email_thread_intelligence.prepare_reply(
                payload[
                    "thread_id"
                ],
                payload[
                    "body"
                ],
                reply_all=bool(
                    payload.get(
                        "reply_all",
                        False,
                    )
                ),
            )


        if action == "github.issue.create":

            return github_connected.prepare_create_issue(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload.get(
                    "body",
                    "",
                ),
            )


        if action == "github.comment.create":

            return github_connected.prepare_comment(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "issue_number"
                ],
                payload[
                    "body"
                ],
            )


        if action == "github.pull.create":

            return github_connected.prepare_pull(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload[
                    "head"
                ],
                payload[
                    "base"
                ],
                payload.get(
                    "body",
                    "",
                ),
            )


        return {
            "success": False,
            "error": (
                "Unsupported V3 write action: "
                + str(action)
            ),
        }


    def execute(
        self,
        action,
        payload,
        *,
        approval_id=None,
    ):

        payload = dict(
            payload
        )


        if (
            action in V2_READ_ACTIONS
            or action in V2_WRITE_ACTIONS
        ):
            return connected_services_gateway.execute(
                action,
                payload,
                approval_id=approval_id,
            )


        if action == "google.gmail.thread":

            return email_thread_intelligence.thread(
                payload[
                    "thread_id"
                ]
            )


        if action == "google.gmail.reply_draft":

            return (
                email_thread_intelligence
                .create_reply_draft(
                    payload[
                        "thread_id"
                    ],
                    payload[
                        "body"
                    ],
                    reply_all=bool(
                        payload.get(
                            "reply_all",
                            False,
                        )
                    ),
                    approval_id=approval_id,
                )
            )


        if action == "google.calendar.recommend_slots":

            return calendar_availability.recommend_slots(
                payload.get(
                    "attendees",
                    (),
                ),
                payload[
                    "window_start"
                ],
                payload[
                    "window_end"
                ],
                duration_minutes=payload.get(
                    "duration_minutes",
                    30,
                ),
                step_minutes=payload.get(
                    "step_minutes",
                    30,
                ),
                calendar_id=payload.get(
                    "calendar_id",
                    "primary",
                ),
                time_zone=payload.get(
                    "time_zone"
                ),
                working_hour_start=payload.get(
                    "working_hour_start",
                    8,
                ),
                working_hour_end=payload.get(
                    "working_hour_end",
                    20,
                ),
                strict=bool(
                    payload.get(
                        "strict",
                        True,
                    )
                ),
                max_slots=payload.get(
                    "max_slots",
                    10,
                ),
            )


        if action == "github.profile":
            return {
                "success": True,
                "profile": github_connected.profile(),
            }


        if action == "github.repos":
            return {
                "success": True,
                "repos": github_connected.repos(
                    per_page=payload.get(
                        "per_page",
                        30,
                    )
                ),
            }


        if action == "github.issues":
            return {
                "success": True,
                "issues": github_connected.issues(
                    payload[
                        "owner"
                    ],
                    payload[
                        "repo"
                    ],
                    state=payload.get(
                        "state",
                        "open",
                    ),
                    per_page=payload.get(
                        "per_page",
                        30,
                    ),
                ),
            }


        if action == "github.pulls":
            return {
                "success": True,
                "pulls": github_connected.pulls(
                    payload[
                        "owner"
                    ],
                    payload[
                        "repo"
                    ],
                    state=payload.get(
                        "state",
                        "open",
                    ),
                    per_page=payload.get(
                        "per_page",
                        30,
                    ),
                ),
            }


        if action == "github.issue.create":

            return github_connected.create_issue(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload.get(
                    "body",
                    "",
                ),
                approval_id=approval_id,
            )


        if action == "github.comment.create":

            return github_connected.create_comment(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "issue_number"
                ],
                payload[
                    "body"
                ],
                approval_id=approval_id,
            )


        if action == "github.pull.create":

            return github_connected.create_pull(
                payload[
                    "owner"
                ],
                payload[
                    "repo"
                ],
                payload[
                    "title"
                ],
                payload[
                    "head"
                ],
                payload[
                    "base"
                ],
                payload.get(
                    "body",
                    "",
                ),
                approval_id=approval_id,
            )


        return {
            "success": False,
            "error": (
                "Unknown Connected Services V3 action: "
                + str(action)
            ),
        }


connected_services_v3_gateway = ConnectedServicesV3Gateway()
'''
)


# ============================================================
# 8. STATUS
# ============================================================

write(
    V3_STATUS,
    r'''
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
'''
)


# ============================================================
# 9. PATCH OPERATOR V4 DSL
# ============================================================

print()
print("Patching Operator V4 DSL for V3 actions...")


schema_source = SCHEMA.read_text(
    encoding="utf-8"
)


if (
    '"google.gmail.thread"'
    not in schema_source
):

    needle = (
        '    "google.calendar.schedule_from_email",\n'
    )


    count = schema_source.count(
        needle
    )


    if count != 2:
        print(
            "Unexpected V2 DSL marker count:",
            count,
        )
        rollback()
        sys.exit(1)


    allowed_extra = '''    "google.gmail.thread",
    "google.gmail.reply_draft",
    "google.calendar.recommend_slots",

    "github.profile",
    "github.repos",
    "github.issues",
    "github.pulls",
    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
'''


    interactive_extra = '''    "google.gmail.reply_draft",

    "github.issue.create",
    "github.comment.create",
    "github.pull.create",
'''


    parts = schema_source.split(
        needle
    )


    schema_source = (
        parts[0]
        + needle
        + allowed_extra
        + parts[1]
        + needle
        + interactive_extra
        + parts[2]
    )


    payload_marker = '''    "coding.create_worktree": {
'''


    if schema_source.count(
        payload_marker
    ) != 1:
        print(
            "Operator payload patch point not unique."
        )
        rollback()
        sys.exit(1)


    payload_extra = '''    "google.gmail.thread": {
        "thread_id",
    },

    "google.gmail.reply_draft": {
        "thread_id",
        "body",
        "reply_all",
    },

    "google.calendar.recommend_slots": {
        "attendees",
        "window_start",
        "window_end",
        "duration_minutes",
        "step_minutes",
        "calendar_id",
        "time_zone",
        "working_hour_start",
        "working_hour_end",
        "strict",
        "max_slots",
    },

    "github.profile": {
    },

    "github.repos": {
        "per_page",
    },

    "github.issues": {
        "owner",
        "repo",
        "state",
        "per_page",
    },

    "github.pulls": {
        "owner",
        "repo",
        "state",
        "per_page",
    },

    "github.issue.create": {
        "owner",
        "repo",
        "title",
        "body",
    },

    "github.comment.create": {
        "owner",
        "repo",
        "issue_number",
        "body",
    },

    "github.pull.create": {
        "owner",
        "repo",
        "title",
        "head",
        "base",
        "body",
    },

'''


    schema_source = schema_source.replace(
        payload_marker,
        payload_extra
        + payload_marker,
        1,
    )


    SCHEMA.write_text(
        schema_source,
        encoding="utf-8",
    )


print(
    "Operator V4 DSL patch: PASS"
)


# ============================================================
# 10. PATCH OPERATOR V4 RUNTIME TO V3 GATEWAY
# ============================================================

print()
print("Patching Operator V4 connected-service gateway...")


runtime_source = RUNTIME.read_text(
    encoding="utf-8"
)


if (
    "connected_services_v3_gateway"
    not in runtime_source
):

    import_marker = '''from omni.connected_services_gateway import (
    connected_services_gateway,
)
'''


    if runtime_source.count(
        import_marker
    ) != 1:
        print(
            "Runtime V2 gateway import not found uniquely."
        )
        rollback()
        sys.exit(1)


    runtime_source = runtime_source.replace(
        import_marker,
        import_marker
        + '''
from omni.connected_services_v3_gateway import (
    connected_services_v3_gateway,
)
''',
        1,
    )


    tuple_marker = '''            "google.calendar.schedule_from_email",
        ):
'''


    if runtime_source.count(
        tuple_marker
    ) != 1:
        print(
            "Runtime interactive tuple patch point failed."
        )
        rollback()
        sys.exit(1)


    runtime_source = runtime_source.replace(
        tuple_marker,
        '''            "google.calendar.schedule_from_email",

            "google.gmail.reply_draft",

            "github.issue.create",
            "github.comment.create",
            "github.pull.create",
        ):
''',
        1,
    )


    old_prepare = '''            prepared = (
                connected_services_gateway
                .prepare(
'''


    if runtime_source.count(
        old_prepare
    ) != 1:
        print(
            "Runtime prepare gateway patch point failed."
        )
        rollback()
        sys.exit(1)


    runtime_source = runtime_source.replace(
        old_prepare,
        '''            prepared = (
                connected_services_v3_gateway
                .prepare(
''',
        1,
    )


    old_execute = '''        if action.startswith(
            "google."
        ):

            return (
                connected_services_gateway
                .execute(
'''


    if runtime_source.count(
        old_execute
    ) != 1:
        print(
            "Runtime execution gateway patch point failed."
        )
        rollback()
        sys.exit(1)


    runtime_source = runtime_source.replace(
        old_execute,
        '''        if action.startswith(
            (
                "google.",
                "github.",
            )
        ):

            return (
                connected_services_v3_gateway
                .execute(
''',
        1,
    )


    RUNTIME.write_text(
        runtime_source,
        encoding="utf-8",
    )


print(
    "Operator V4 runtime gateway patch: PASS"
)


# ============================================================
# 11. MAIN PUBLIC APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_connected_intent("
    not in main_source
):

    main_source += r'''


def jarvis_connected_intent(
    request,
):
    from omni.connected_intent_router import connected_intent_router
    return connected_intent_router.route(request)


def jarvis_gmail_thread(
    thread_id,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.thread(thread_id)


def jarvis_prepare_reply_draft(
    thread_id,
    body,
    reply_all=False,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.prepare_reply(
        thread_id,
        body,
        reply_all=reply_all,
    )


def jarvis_create_reply_draft(
    thread_id,
    body,
    reply_all=False,
    approval_id=None,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.create_reply_draft(
        thread_id,
        body,
        reply_all=reply_all,
        approval_id=approval_id,
    )


def jarvis_recommend_meeting_slots(
    attendees,
    window_start,
    window_end,
    duration_minutes=30,
    step_minutes=30,
    calendar_id="primary",
    time_zone=None,
    working_hour_start=8,
    working_hour_end=20,
    strict=True,
    max_slots=10,
):
    from omni.calendar_availability import calendar_availability
    return calendar_availability.recommend_slots(
        attendees,
        window_start,
        window_end,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        calendar_id=calendar_id,
        time_zone=time_zone,
        working_hour_start=working_hour_start,
        working_hour_end=working_hour_end,
        strict=strict,
        max_slots=max_slots,
    )


def jarvis_connected_approvals():
    from omni.connected_approval_dashboard import connected_approval_dashboard
    return connected_approval_dashboard.pending()


def jarvis_github_connect():
    from omni.github_connected import github_connected
    return github_connected.connect_interactive()


def jarvis_github_disconnect():
    from omni.github_connected import github_connected
    return github_connected.disconnect()


def jarvis_github_status(
    verify=False,
):
    from omni.github_connected import github_connected
    return github_connected.status(
        verify=verify
    )


def jarvis_github_profile():
    from omni.github_connected import github_connected
    return github_connected.profile()


def jarvis_github_repos(
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.repos(
        per_page=per_page
    )


def jarvis_github_issues(
    owner,
    repo,
    state="open",
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.issues(
        owner,
        repo,
        state=state,
        per_page=per_page,
    )


def jarvis_github_pulls(
    owner,
    repo,
    state="open",
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.pulls(
        owner,
        repo,
        state=state,
        per_page=per_page,
    )


def jarvis_github_create_issue(
    owner,
    repo,
    title,
    body="",
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_issue(
        owner,
        repo,
        title,
        body,
        approval_id=approval_id,
    )


def jarvis_github_comment(
    owner,
    repo,
    issue_number,
    body,
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_comment(
        owner,
        repo,
        issue_number,
        body,
        approval_id=approval_id,
    )


def jarvis_github_create_pull(
    owner,
    repo,
    title,
    head,
    base,
    body="",
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_pull(
        owner,
        repo,
        title,
        head,
        base,
        body,
        approval_id=approval_id,
    )


def jarvis_connected_services_v3_status():
    from omni.connected_services_v3_status import connected_services_v3_status
    return connected_services_v3_status.status()
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 12. WORKSTATION STATUS PAYLOAD
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_connected_services_v3_payload("
    not in app_source
):

    app_source += r'''


def jarvis_connected_services_v3_payload():

    from omni.connected_services_v3_status import connected_services_v3_status
    from omni.connected_approval_dashboard import connected_approval_dashboard

    try:
        return {
            "success": True,
            "status": connected_services_v3_status.status(),
            "approvals": connected_approval_dashboard.pending(),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": (
                type(exc).__name__
                + ": "
                + str(exc)
            ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
    )


# ============================================================
# 13. TESTS
# ============================================================

write(
    TEST,
    r'''
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
'''
)


# ============================================================
# 14. COMPILE ALL GENERATED SOURCE
# ============================================================

print()
print("Checking Connected Services V3 syntax...")


r = run(
    "-m",
    "py_compile",
    str(INTENT),
    str(THREADS),
    str(AVAILABILITY),
    str(GITHUB),
    str(DASHBOARD),
    str(V3_GATEWAY),
    str(V3_STATUS),
    str(SCHEMA),
    str(RUNTIME),
    str(MAIN),
    str(APP),
    str(TEST),
)


if r.returncode:
    print("COMPILE FAILURE")
    rollback()
    sys.exit(1)


print("Syntax: PASS")


# ============================================================
# 15. PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if sha(ROOT / relative) != before:
        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )
        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "import main; "
        "print('Protected core: PASS'); "
        "print('Main import: PASS')"
    ),
)


if r.returncode:
    print("CORE CHECK FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# 16. REAL GMAIL THREAD READ — NO WRITE
# ============================================================

print()
print("Checking real Gmail thread intelligence...")


gmail_probe = r'''
import main

search = main.jarvis_gmail_search(
    "newer_than:30d",
    1,
)

assert search["success"]

messages = search.get(
    "messages",
    (),
)

if not messages:
    print("Recent Gmail messages: 0")
    print("Thread live probe: SKIPPED - mailbox query returned none")

else:
    thread_id = messages[0].get(
        "thread_id"
    )

    assert thread_id

    thread = main.jarvis_gmail_thread(
        thread_id
    )

    assert thread["success"]
    assert thread["message_count"] >= 1

    print(
        "Thread message count:",
        thread["message_count"],
    )

    print(
        "Gmail thread real read: PASS"
    )

print(
    "Gmail draft created: NO"
)

print(
    "Email sent: NO"
)
'''


r = run(
    "-c",
    gmail_probe,
)


if r.returncode:
    print(
        "GMAIL THREAD PROBE FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 17. REAL FREE/BUSY READ — PRIMARY CALENDAR ONLY
# ============================================================

print()
print("Checking real Calendar free/busy intelligence...")


calendar_probe = r'''
from datetime import datetime, timedelta, timezone

import main


start = (
    datetime.now(
        timezone.utc
    )
    + timedelta(
        days=7
    )
)

end = (
    start
    + timedelta(
        hours=6
    )
)


result = main.jarvis_recommend_meeting_slots(
    [],
    start.isoformat(),
    end.isoformat(),
    duration_minutes=30,
    step_minutes=30,
    calendar_id="primary",
    working_hour_start=0,
    working_hour_end=23,
    strict=True,
    max_slots=5,
)


assert result["success"], result


print(
    "Recommended slot count:",
    len(
        result.get(
            "slots",
            (),
        )
    ),
)

print(
    "Calendar free/busy real read: PASS"
)

print(
    "Calendar modified: NO"
)
'''


r = run(
    "-c",
    calendar_probe,
)


if r.returncode:
    print(
        "CALENDAR FREE/BUSY PROBE FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 18. INTENT SAFETY
# ============================================================

print()
print("Checking natural-language connected-service router...")


intent_probe = r'''
import main


tests = (
    (
        "Draft a reply to this email",
        "google.gmail.reply_draft",
        True,
    ),

    (
        "Find a time for our meeting",
        "google.calendar.recommend_slots",
        False,
    ),

    (
        "Create GitHub issue for this bug",
        "github.issue.create",
        True,
    ),
)


for text, action, approval in tests:

    result = main.jarvis_connected_intent(
        text
    )

    assert result["action"] == action, result
    assert result["requires_approval"] == approval, result
    assert result["auto_execute"] is False, result


print(
    "Natural-language routing: PASS"
)

print(
    "Intent auto-execution: BLOCKED"
)
'''


r = run(
    "-c",
    intent_probe,
)


if r.returncode:
    print(
        "INTENT ROUTER FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 19. APPROVAL DASHBOARD
# ============================================================

print()
print("Checking connected approval dashboard...")


r = run(
    "-c",
    (
        "import main; "
        "x=main.jarvis_connected_approvals(); "
        "assert x['success']; "
        "assert x['automatic_approval'] is False; "
        "print('Connected pending approvals:',x['count']); "
        "print('Automatic approval: BLOCKED'); "
        "print('Approval dashboard backend: PASS')"
    ),
)


if r.returncode:
    print(
        "APPROVAL DASHBOARD FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 20. LOCAL GITHUB STATUS
# ============================================================

print()
print("Checking local JARVIS GitHub credential layer...")


r = run(
    "-c",
    (
        "import main; "
        "x=main.jarvis_github_status(False); "
        "print('DPAPI vault available:',x['vault_available']); "
        "print('Local GitHub token encrypted:',x['token_encrypted']); "
        "print('Local GitHub connected:',x['connected']); "
        "print('GitHub API version:',x['api_version']); "
        "assert x['vault_available']; "
        "assert x['automatic_write'] is False; "
        "assert x['merge_supported'] is False; "
        "assert x['force_push_supported'] is False; "
        "print('Local GitHub safety layer: PASS')"
    ),
)


if r.returncode:
    print(
        "GITHUB STATUS FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 21. OPERATOR V4 DSL
# ============================================================

print()
print("Checking Operator V4 V3-service integration...")


operator_probe = r'''
from omni.operator_runtime_schema import (
    from_dict,
    is_interactive,
)


plan = from_dict(
    "Connected service V3 test",
    {
        "steps": [
            {
                "action": "google.gmail.thread",
                "payload": {
                    "thread_id": "abc"
                },
            },

            {
                "action": "google.calendar.recommend_slots",
                "payload": {
                    "attendees": [],
                    "window_start": "2026-08-20T09:00:00+05:30",
                    "window_end": "2026-08-20T12:00:00+05:30",
                },
            },

            {
                "action": "github.repos",
                "payload": {
                    "per_page": 5
                },
            },
        ]
    },
)


assert len(plan.steps) == 3

assert is_interactive(
    "google.gmail.reply_draft"
)

assert is_interactive(
    "github.issue.create"
)

assert is_interactive(
    "github.comment.create"
)

assert is_interactive(
    "github.pull.create"
)


print(
    "Gmail thread DSL: ACTIVE"
)

print(
    "Calendar availability DSL: ACTIVE"
)

print(
    "GitHub read DSL: ACTIVE"
)

print(
    "Gmail reply write gate: ACTIVE"
)

print(
    "GitHub write gates: ACTIVE"
)

print(
    "Operator V4 V3 integration: PASS"
)
'''


r = run(
    "-c",
    operator_probe,
)


if r.returncode:
    print(
        "OPERATOR V4 V3 INTEGRATION FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 22. TARGETED TESTS
# ============================================================

print()
print("Running Connected Services V3 targeted tests...")


r = run(
    "-m",
    "unittest",

    "tests.test_connected_services_v3",
    "tests.test_connected_services_v2",
    "tests.test_connected_services_v1",

    "tests.test_computer_operator_v4",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v2",
    "tests.test_computer_operator",

    "tests.test_real_world_action_v3",
    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_engine",

    "tests.test_universal_learning_v5",
    "tests.test_autonomy_engine",
    "tests.test_improvement_lab",

    "-q",
)


if r.returncode:
    print(
        "TARGETED TEST FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 23. FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:
    print(
        "FULL REGRESSION FAILURE"
    )
    rollback()
    sys.exit(1)


# ============================================================
# 24. FINAL CORE VERIFICATION
# ============================================================

for relative, before in PROTECTED.items():

    if sha(ROOT / relative) != before:
        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )
        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "print('Final Protected Core: PASS')"
    ),
)


if r.returncode:
    rollback()
    sys.exit(1)


# ============================================================
# SUCCESS
# ============================================================

github_status = run(
    "-c",
    (
        "import main; "
        "print(main.jarvis_github_status(False))"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS CONNECTED SERVICES V3 SUCCESS")
print("=" * 80)

print("Permanent governed agents: 29")
print()

print("NATURAL-LANGUAGE SERVICE INTELLIGENCE")
print("Connected-service intent classification: ACTIVE")
print("Gmail intent routing: ACTIVE")
print("Calendar intent routing: ACTIVE")
print("Contacts intent routing: ACTIVE")
print("GitHub intent routing: ACTIVE")
print("Model-free deterministic safety layer: ACTIVE")
print("Intent auto-execution: BLOCKED")
print()

print("GMAIL THREAD INTELLIGENCE")
print("Thread retrieval: ACTIVE")
print("Thread message context: ACTIVE")
print("Latest external sender detection: ACTIVE")
print("Reply recipient derivation: ACTIVE")
print("Reply-all derivation: ACTIVE")
print("In-Reply-To / References support: ACTIVE")
print("Reply draft creation: ONE-TIME APPROVAL")
print("Reply draft sending: SEPARATE APPROVAL")
print("Automatic email send: BLOCKED")
print()

print("CALENDAR AVAILABILITY")
print("Free/busy API integration: ACTIVE")
print("Primary-calendar availability: VERIFIED")
print("Multi-calendar free/busy: ACTIVE")
print("Contact -> attendee calendar mapping: ACTIVE")
print("Multi-person slot recommendation: ACTIVE")
print("Strict unavailable-calendar handling: ACTIVE")
print("Explicit timezone requirement: ACTIVE")
print("Automatic Calendar write: BLOCKED")
print()

print("CONNECTED APPROVAL DASHBOARD")
print("Pending Gmail approvals: VISIBLE")
print("Pending Calendar approvals: VISIBLE")
print("Pending GitHub approvals: VISIBLE")
print("Sensitive body previews: REDACTED")
print("Automatic approval: BLOCKED")
print()

print("LOCAL JARVIS GITHUB")
print("DPAPI credential vault: ACTIVE")
print("Fine-grained token interactive setup: ACTIVE")
print("Authenticated profile read: ACTIVE WHEN CONNECTED")
print("Repository reads: ACTIVE WHEN CONNECTED")
print("Issue reads: ACTIVE WHEN CONNECTED")
print("Pull-request reads: ACTIVE WHEN CONNECTED")
print("Issue creation: APPROVAL-GATED")
print("Issue/PR comments: APPROVAL-GATED")
print("Pull-request creation: APPROVAL-GATED")
print("Automatic GitHub write: BLOCKED")
print("GitHub merge: NOT IMPLEMENTED")
print("Force push: NOT IMPLEMENTED")
print()

print("OPERATOR V4")
print("Gmail thread action: ACTIVE")
print("Gmail reply-draft action: ACTIVE + APPROVAL")
print("Calendar slot recommendation: ACTIVE")
print("GitHub read actions: ACTIVE")
print("GitHub write actions: ACTIVE + APPROVAL")
print("Connected-services V3 gateway: ACTIVE")
print()

print("REAL SERVICE VERIFICATION")
print("Google OAuth: PRESERVED")
print("Gmail thread read: VERIFIED")
print("Calendar free/busy read: VERIFIED")
print("Installer email write: NO")
print("Installer Calendar write: NO")
print("Installer GitHub write: NO")
print()

print("SAFETY")
print("Protected Core: UNCHANGED")
print("Computer Operator V4: PRESERVED")
print("Connected Services V1: PRESERVED")
print("Connected Services V2: PRESERVED")
print("Qwen3-VL Vision: PRESERVED")
print("Recipient ambiguity blocking: PRESERVED")
print("Live trading execution: BLOCKED")
print("Remote Git auto-write: BLOCKED")
print("Automatic Gmail send: BLOCKED")
print("Automatic Calendar write: BLOCKED")
print("Automatic GitHub write: BLOCKED")
print("Full regression: PASS")
print()

print("LOCAL GITHUB STATUS:")
print(
    github_status.stdout.strip()
)
print()

print("NEXT AFTER THIS PASSES:")
print("1. Connect local JARVIS GitHub using hidden interactive PAT input")
print("2. Verify profile/repository/issue/PR reads")
print("3. Test one-time GitHub approval binding WITHOUT creating content")
print("4. Connected Services V4: richer mission orchestration")
print("5. Advanced Voice / wake word")
print("6. Advanced Trading Intelligence")
print("7. NautilusTrader isolated simulation/backtest kernel")
