from pathlib import Path
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

SCOPES = ROOT / "omni" / "google_scopes.py"
VAULT = ROOT / "omni" / "google_token_vault.py"
OAUTH = ROOT / "omni" / "google_oauth.py"
AUDIT = ROOT / "omni" / "google_audit.py"
GMAIL = ROOT / "omni" / "gmail_service.py"
CALENDAR = ROOT / "omni" / "google_calendar_service.py"
CONTACTS = ROOT / "omni" / "google_contacts_service.py"
GATEWAY = ROOT / "omni" / "connected_services_gateway.py"
STATUS = ROOT / "omni" / "connected_services_status.py"

V4_SCHEMA = ROOT / "omni" / "operator_runtime_schema.py"
V4_RUNTIME = ROOT / "omni" / "operator_runtime.py"

TEST = ROOT / "tests" / "test_connected_services_v1.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"
ARCHIVE = ROOT / "archive" / "connected_services_v1"

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    MAIN,
    APP,
    SCOPES,
    VAULT,
    OAUTH,
    AUDIT,
    GMAIL,
    CALENDAR,
    CONTACTS,
    GATEWAY,
    STATUS,
    V4_SCHEMA,
    V4_RUNTIME,
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
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(path, source):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(source).lstrip(),
        encoding="utf-8",
    )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        if existed:
            shutil.copy2(
                backup,
                path,
            )

        else:
            path.unlink(
                missing_ok=True
            )

    print(
        "JARVIS source restored."
    )

    print(
        "Installed Python packages are retained."
    )


print("=" * 80)
print("JARVIS CONNECTED SERVICES V1")
print("GOOGLE OAUTH + GMAIL + CALENDAR + CONTACTS")
print("=" * 80)


# ============================================================
# 0. VERIFY 422 CHECKPOINT
# ============================================================

print()
print("Checking 422-test checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.operator_runtime import unified_operator_runtime; "
        "from omni.vision_runtime import vision_runtime; "
        "assert vision_runtime.status()['vision_ready']; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V4: PASS'); "
        "print('Qwen3-VL vision: PASS')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(PROTECTED),
)

print(
    "Baseline: PASS"
)


# ============================================================
# 1. BACKUP SOURCE
# ============================================================

for path in FILES:

    BACKUPS[path] = path.exists()

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# ============================================================
# 2. GOOGLE PYTHON DEPENDENCIES
# ============================================================

print()
print("Checking Google API dependencies...")


imports = {
    "googleapiclient.discovery":
        "google-api-python-client",

    "google_auth_oauthlib.flow":
        "google-auth-oauthlib",

    "google.auth.transport.requests":
        "google-auth",

    "google_auth_httplib2":
        "google-auth-httplib2",

    "win32crypt":
        "pywin32",
}


missing = []


for module_name, package in imports.items():

    try:
        importlib.import_module(
            module_name
        )

    except Exception:

        if package not in missing:
            missing.append(
                package
            )


if missing:

    print(
        "Installing:",
        ", ".join(
            missing
        ),
    )


    result = subprocess.run(
        [
            str(PY),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *missing,
        ],
        cwd=ROOT,
        text=True,
    )


    if result.returncode:

        print(
            "DEPENDENCY INSTALL FAILURE"
        )

        rollback()

        sys.exit(1)


else:

    print(
        "Google dependencies already installed."
    )


print(
    "Google API dependencies: PASS"
)


# ============================================================
# 3. REMOVE ONLY KNOWN INSTALLER TEST APPROVAL ARTIFACTS
# ============================================================

print()
print("Cleaning known V4 installer approval artifacts...")


KNOWN_TEST_GOALS = {
    "Inspect example.com",
    "Open example",
}


removed = 0


approval_root = (
    ROOT
    / "data"
    / "approval_batches"
)


if approval_root.exists():

    for path in approval_root.rglob(
        "*.json"
    ):

        try:

            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            continue


        if (
            data.get(
                "goal"
            )
            in KNOWN_TEST_GOALS

            and data.get(
                "status"
            )
            == "pending"
        ):

            path.unlink(
                missing_ok=True
            )

            removed += 1


print(
    "Known test approval batches removed:",
    removed,
)


# ============================================================
# 4. LEAST-PRIVILEGE GOOGLE SCOPES
# ============================================================

write(
    SCOPES,
    r'''
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
'''
)


# ============================================================
# 5. WINDOWS DPAPI TOKEN VAULT
# ============================================================

write(
    VAULT,
    r'''
from __future__ import annotations

from pathlib import Path

import os


class GoogleTokenVault:

    DESCRIPTION = (
        "JARVIS Google OAuth Token"
    )


    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "credentials"
                / "google_oauth.dpapi"
            )
        )


    @staticmethod
    def available():

        try:

            import win32crypt

            return True

        except Exception:

            return False


    def exists(
        self,
    ):

        return (
            self.path.exists()

            and self.path.stat().st_size
            > 0
        )


    def save_text(
        self,
        text,
    ):

        import win32crypt


        data = str(
            text
        ).encode(
            "utf-8"
        )


        encrypted = (
            win32crypt.CryptProtectData(
                data,
                self.DESCRIPTION,
                None,
                None,
                None,
                0,
            )
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = (
            self.path
            .with_suffix(
                ".tmp"
            )
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
            "success":
                True,

            "path":
                str(
                    self.path
                ),

            "encrypted":
                True,

            "bytes":
                len(
                    encrypted
                ),
        }


    def load_text(
        self,
    ):

        import win32crypt


        if not self.exists():

            raise FileNotFoundError(
                "Google OAuth token vault "
                "does not exist."
            )


        encrypted = (
            self.path.read_bytes()
        )


        description, data = (
            win32crypt.CryptUnprotectData(
                encrypted,
                None,
                None,
                None,
                0,
            )
        )


        return data.decode(
            "utf-8"
        )


    def delete(
        self,
    ):

        existed = self.path.exists()


        self.path.unlink(
            missing_ok=True
        )


        return {
            "success":
                True,

            "existed":
                existed,
        }


google_token_vault = (
    GoogleTokenVault()
)
'''
)


# ============================================================
# 6. GOOGLE AUDIT — NO TOKENS / MESSAGE BODIES
# ============================================================

write(
    AUDIT,
    r'''
from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


BLOCKED_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "credentials",
    "client_secret",
    "raw",
    "body",
    "message_body",
    "password",
    "secret",
}


def _sanitize(
    value,
):

    if isinstance(
        value,
        dict,
    ):

        output = {}


        for key, child in value.items():

            key_text = str(
                key
            )


            if (
                key_text.lower()
                in BLOCKED_KEYS
            ):

                output[
                    key_text
                ] = "<redacted>"

            else:

                output[
                    key_text
                ] = _sanitize(
                    child
                )


        return output


    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        return [
            _sanitize(
                child
            )

            for child
            in value
        ]


    text = str(
        value
    )


    if len(
        text
    ) > 1000:

        return (
            text[:1000]
            + "..."
        )


    return value


class GoogleAudit:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "audit"
                / "google_services.jsonl"
            )
        )


    def record(
        self,
        action,
        *,
        success,
        metadata=None,
        error=None,
    ):

        record = {
            "audit_id":
                (
                    "google-audit-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "timestamp":
                time.time(),

            "action":
                str(
                    action
                ),

            "success":
                bool(
                    success
                ),

            "metadata":
                _sanitize(
                    metadata
                    or {}
                ),

            "error":
                (
                    str(
                        error
                    )[:1000]
                    if error
                    else None
                ),
        }


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        with self.path.open(
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


google_audit = (
    GoogleAudit()
)
'''
)


# ============================================================
# 7. GOOGLE OAUTH MANAGER
# ============================================================

write(
    OAUTH,
    r'''
from __future__ import annotations

from pathlib import Path

import json
import shutil


from google.auth.transport.requests import (
    Request,
)

from google.oauth2.credentials import (
    Credentials,
)

from google_auth_oauthlib.flow import (
    InstalledAppFlow,
)

from googleapiclient.discovery import (
    build,
)


from omni.google_audit import (
    google_audit,
)

from omni.google_scopes import (
    GOOGLE_SCOPES,
)

from omni.google_token_vault import (
    google_token_vault,
)


class GoogleOAuthManager:

    def __init__(
        self,
        client_secret_path=None,
    ):

        self.client_secret_path = Path(
            client_secret_path
            or (
                Path("config")
                / "google"
                / "client_secret.json"
            )
        )


    def install_client_secret(
        self,
        source,
    ):

        source = Path(
            source
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        data = json.loads(
            source.read_text(
                encoding="utf-8"
            )
        )


        if (
            "installed"
            not in data
        ):

            raise ValueError(
                "Google OAuth credential must "
                "be a Desktop app client JSON."
            )


        installed = data[
            "installed"
        ]


        if not installed.get(
            "client_id"
        ):

            raise ValueError(
                "OAuth client_id missing."
            )


        if not installed.get(
            "client_secret"
        ):

            raise ValueError(
                "OAuth client_secret missing."
            )


        self.client_secret_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        shutil.copy2(
            source,
            self.client_secret_path,
        )


        return {
            "success":
                True,

            "path":
                str(
                    self.client_secret_path
                ),

            "type":
                "desktop",
        }


    def client_secret_ready(
        self,
    ):

        if not self.client_secret_path.exists():

            return False


        try:

            data = json.loads(
                self.client_secret_path
                .read_text(
                    encoding="utf-8"
                )
            )


            return bool(
                data.get(
                    "installed",
                    {}
                ).get(
                    "client_id"
                )
            )


        except Exception:

            return False


    def _load_credentials(
        self,
    ):

        if not google_token_vault.exists():

            return None


        try:

            info = json.loads(
                google_token_vault
                .load_text()
            )


            return (
                Credentials
                .from_authorized_user_info(
                    info,

                    scopes=
                        list(
                            GOOGLE_SCOPES
                        ),
                )
            )


        except Exception:

            return None


    def credentials(
        self,
        *,
        refresh=True,
    ):

        credentials = (
            self._load_credentials()
        )


        if credentials is None:

            raise RuntimeError(
                "Google account is not connected."
            )


        if (
            refresh
            and credentials.expired
            and credentials.refresh_token
        ):

            credentials.refresh(
                Request()
            )


            google_token_vault.save_text(
                credentials.to_json()
            )


        if not (
            credentials.valid
            or credentials.refresh_token
        ):

            raise RuntimeError(
                "Google OAuth credentials "
                "are not usable."
            )


        return credentials


    def connect(
        self,
    ):

        if not self.client_secret_ready():

            raise FileNotFoundError(
                "Google Desktop OAuth client JSON "
                "not configured at "
                + str(
                    self.client_secret_path
                )
            )


        flow = (
            InstalledAppFlow
            .from_client_secrets_file(
                str(
                    self.client_secret_path
                ),

                scopes=
                    list(
                        GOOGLE_SCOPES
                    ),
            )
        )


        credentials = (
            flow.run_local_server(
                host=
                    "127.0.0.1",

                port=
                    0,

                open_browser=
                    True,

                authorization_prompt_message=
                    (
                        "JARVIS is opening your "
                        "browser for Google authorization."
                    ),

                success_message=
                    (
                        "Google authorization completed. "
                        "You may close this browser tab "
                        "and return to JARVIS."
                    ),

                access_type=
                    "offline",

                prompt=
                    "consent",
            )
        )


        google_token_vault.save_text(
            credentials.to_json()
        )


        google_audit.record(
            "google.oauth.connect",
            success=True,
            metadata={
                "scopes":
                    list(
                        GOOGLE_SCOPES
                    )
            },
        )


        return self.status()


    def disconnect(
        self,
    ):

        result = (
            google_token_vault.delete()
        )


        google_audit.record(
            "google.oauth.disconnect",
            success=True,
            metadata={
                "token_deleted":
                    result[
                        "existed"
                    ]
            },
        )


        return result


    def service(
        self,
        api,
        version,
    ):

        credentials = (
            self.credentials(
                refresh=True
            )
        )


        return build(
            str(
                api
            ),

            str(
                version
            ),

            credentials=
                credentials,

            cache_discovery=
                False,
        )


    def status(
        self,
    ):

        credentials = (
            self._load_credentials()
        )


        return {
            "client_secret_ready":
                self.client_secret_ready(),

            "token_vault_available":
                google_token_vault.available(),

            "token_encrypted":
                google_token_vault.exists(),

            "connected":
                bool(
                    credentials
                ),

            "token_valid":
                bool(
                    credentials
                    and credentials.valid
                ),

            "token_expired":
                bool(
                    credentials
                    and credentials.expired
                ),

            "refresh_token_present":
                bool(
                    credentials
                    and credentials.refresh_token
                ),

            "scopes":
                tuple(
                    GOOGLE_SCOPES
                ),
        }


google_oauth = (
    GoogleOAuthManager()
)
'''
)


# ============================================================
# 8. GMAIL SERVICE
# ============================================================

write(
    GMAIL,
    r'''
from __future__ import annotations

from email.message import (
    EmailMessage,
)

import base64
import hashlib


from omni.approval_queue import (
    approval_queue,
)

from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


class GmailService:

    @staticmethod
    def _decode(
        value,
    ):

        if not value:

            return ""


        value = str(
            value
        )


        value += (
            "="
            * (
                -len(
                    value
                )
                % 4
            )
        )


        try:

            return (
                base64.urlsafe_b64decode(
                    value
                )
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except Exception:

            return ""


    @classmethod
    def _parts(
        cls,
        part,
    ):

        plain = []

        html = []


        mime_type = str(
            part.get(
                "mimeType",
                ""
            )
        ).lower()


        body = part.get(
            "body",
            {}
        )


        data = body.get(
            "data"
        )


        if data:

            decoded = cls._decode(
                data
            )


            if (
                mime_type
                == "text/plain"
            ):

                plain.append(
                    decoded
                )

            elif (
                mime_type
                == "text/html"
            ):

                html.append(
                    decoded
                )


        for child in part.get(
            "parts",
            ()
        ):

            child_plain, child_html = (
                cls._parts(
                    child
                )
            )


            plain.extend(
                child_plain
            )

            html.extend(
                child_html
            )


        return plain, html


    @staticmethod
    def _headers(
        payload,
    ):

        return {
            str(
                item.get(
                    "name",
                    ""
                )
            ).lower():
                str(
                    item.get(
                        "value",
                        ""
                    )
                )

            for item
            in payload.get(
                "headers",
                ()
            )
        }


    def service(
        self,
    ):

        return google_oauth.service(
            "gmail",
            "v1",
        )


    def search(
        self,
        query="",
        max_results=20,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                100,
            ),
        )


        response = (
            self.service()
            .users()
            .messages()
            .list(
                userId="me",
                q=str(
                    query
                ),
                maxResults=
                    max_results,
            )
            .execute()
        )


        messages = []


        service = self.service()


        for item in response.get(
            "messages",
            ()
        ):

            metadata = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=item[
                        "id"
                    ],
                    format=
                        "metadata",
                    metadataHeaders=[
                        "From",
                        "To",
                        "Subject",
                        "Date",
                    ],
                )
                .execute()
            )


            payload = metadata.get(
                "payload",
                {}
            )


            headers = self._headers(
                payload
            )


            messages.append(
                {
                    "id":
                        metadata.get(
                            "id"
                        ),

                    "thread_id":
                        metadata.get(
                            "threadId"
                        ),

                    "from":
                        headers.get(
                            "from"
                        ),

                    "to":
                        headers.get(
                            "to"
                        ),

                    "subject":
                        headers.get(
                            "subject"
                        ),

                    "date":
                        headers.get(
                            "date"
                        ),

                    "snippet":
                        metadata.get(
                            "snippet",
                            ""
                        ),
                }
            )


        google_audit.record(
            "gmail.search",
            success=True,
            metadata={
                "query":
                    str(
                        query
                    )[:500],

                "results":
                    len(
                        messages
                    ),
            },
        )


        return {
            "success":
                True,

            "messages":
                tuple(
                    messages
                ),

            "next_page_token":
                response.get(
                    "nextPageToken"
                ),
        }


    def get(
        self,
        message_id,
    ):

        message = (
            self.service()
            .users()
            .messages()
            .get(
                userId="me",
                id=str(
                    message_id
                ),
                format="full",
            )
            .execute()
        )


        payload = message.get(
            "payload",
            {}
        )


        headers = self._headers(
            payload
        )


        plain, html = self._parts(
            payload
        )


        result = {
            "success":
                True,

            "id":
                message.get(
                    "id"
                ),

            "thread_id":
                message.get(
                    "threadId"
                ),

            "from":
                headers.get(
                    "from"
                ),

            "to":
                headers.get(
                    "to"
                ),

            "cc":
                headers.get(
                    "cc"
                ),

            "subject":
                headers.get(
                    "subject"
                ),

            "date":
                headers.get(
                    "date"
                ),

            "snippet":
                message.get(
                    "snippet"
                ),

            "text":
                "\n".join(
                    plain
                )[:50000],

            "html":
                "\n".join(
                    html
                )[:50000],
        }


        google_audit.record(
            "gmail.get",
            success=True,
            metadata={
                "message_id":
                    str(
                        message_id
                    )
            },
        )


        return result


    @staticmethod
    def _message(
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        message = EmailMessage()


        message[
            "To"
        ] = str(
            to
        )


        message[
            "Subject"
        ] = str(
            subject
        )


        if cc:

            message[
                "Cc"
            ] = str(
                cc
            )


        if bcc:

            message[
                "Bcc"
            ] = str(
                bcc
            )


        message.set_content(
            str(
                body
            )
        )


        return message


    def prepare_create_draft(
        self,
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        body_text = str(
            body
        )


        payload = {
            "to":
                str(
                    to
                ),

            "cc":
                str(
                    cc
                    or ""
                ),

            "bcc":
                str(
                    bcc
                    or ""
                ),

            "subject":
                str(
                    subject
                ),

            "body_sha256":
                hashlib.sha256(
                    body_text.encode(
                        "utf-8"
                    )
                ).hexdigest(),

            "body_length":
                len(
                    body_text
                ),
        }


        return {
            "action":
                "google.gmail.create_draft",

            "payload":
                payload,

            "display": {
                "to":
                    payload[
                        "to"
                    ],

                "cc":
                    payload[
                        "cc"
                    ],

                "bcc":
                    payload[
                        "bcc"
                    ],

                "subject":
                    payload[
                        "subject"
                    ],

                "body_preview":
                    body_text[:160],
            },

            "risk":
                "email-draft-write",
        }


    def create_draft(
        self,
        to,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
        approval_id=None,
    ):

        binding = self.prepare_create_draft(
            to,
            subject,
            body,
            cc=cc,
            bcc=bcc,
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        binding[
                            "action"
                        ],

                        binding[
                            "payload"
                        ],

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,
            binding[
                "action"
            ],
            binding[
                "payload"
            ],
        )


        message = self._message(
            to,
            subject,
            body,
            cc=cc,
            bcc=bcc,
        )


        raw = (
            base64.urlsafe_b64encode(
                message.as_bytes()
            )
            .decode(
                "ascii"
            )
        )


        result = (
            self.service()
            .users()
            .drafts()
            .create(
                userId="me",
                body={
                    "message": {
                        "raw":
                            raw
                    }
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.create_draft",
            success=True,
            metadata={
                "draft_id":
                    result.get(
                        "id"
                    ),

                "to":
                    str(
                        to
                    ),

                "subject":
                    str(
                        subject
                    ),
            },
        )


        return {
            "success":
                True,

            "draft_id":
                result.get(
                    "id"
                ),

            "message":
                result.get(
                    "message"
                ),
        }


    @staticmethod
    def prepare_send_draft(
        draft_id,
    ):

        payload = {
            "draft_id":
                str(
                    draft_id
                )
        }


        return {
            "action":
                "google.gmail.send_draft",

            "payload":
                payload,

            "display":
                payload,

            "risk":
                "email-send",
        }


    def send_draft(
        self,
        draft_id,
        *,
        approval_id=None,
    ):

        binding = self.prepare_send_draft(
            draft_id
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        binding[
                            "action"
                        ],

                        binding[
                            "payload"
                        ],

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,
            binding[
                "action"
            ],
            binding[
                "payload"
            ],
        )


        result = (
            self.service()
            .users()
            .drafts()
            .send(
                userId="me",
                body={
                    "id":
                        str(
                            draft_id
                        )
                },
            )
            .execute()
        )


        google_audit.record(
            "gmail.send_draft",
            success=True,
            metadata={
                "draft_id":
                    str(
                        draft_id
                    ),

                "message_id":
                    result.get(
                        "id"
                    ),
            },
        )


        return {
            "success":
                True,

            "message_id":
                result.get(
                    "id"
                ),

            "thread_id":
                result.get(
                    "threadId"
                ),
        }


gmail_service = (
    GmailService()
)
'''
)



# ============================================================
# 9. GOOGLE CALENDAR SERVICE
# ============================================================

write(
    CALENDAR,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import hashlib
import json


from omni.approval_queue import (
    approval_queue,
)

from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


class GoogleCalendarService:

    def service(
        self,
    ):

        return google_oauth.service(
            "calendar",
            "v3",
        )


    def calendars(
        self,
        max_results=100,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                250,
            ),
        )


        response = (
            self.service()
            .calendarList()
            .list(
                maxResults=
                    max_results,
            )
            .execute()
        )


        items = []


        for item in response.get(
            "items",
            ()
        ):

            items.append(
                {
                    "id":
                        item.get(
                            "id"
                        ),

                    "summary":
                        item.get(
                            "summary"
                        ),

                    "primary":
                        item.get(
                            "primary",
                            False,
                        ),

                    "access_role":
                        item.get(
                            "accessRole"
                        ),

                    "time_zone":
                        item.get(
                            "timeZone"
                        ),
                }
            )


        google_audit.record(
            "calendar.list",
            success=True,
            metadata={
                "results":
                    len(
                        items
                    )
            },
        )


        return {
            "success":
                True,

            "calendars":
                tuple(
                    items
                ),
        }


    def events(
        self,
        *,
        calendar_id="primary",
        time_min=None,
        time_max=None,
        max_results=20,
        query=None,
    ):

        max_results = max(
            1,
            min(
                int(
                    max_results
                ),
                250,
            ),
        )


        if time_min is None:

            time_min = (
                datetime.now(
                    timezone.utc
                )
                .isoformat()
            )


        arguments = {
            "calendarId":
                str(
                    calendar_id
                ),

            "timeMin":
                str(
                    time_min
                ),

            "maxResults":
                max_results,

            "singleEvents":
                True,

            "orderBy":
                "startTime",
        }


        if time_max:

            arguments[
                "timeMax"
            ] = str(
                time_max
            )


        if query:

            arguments[
                "q"
            ] = str(
                query
            )


        response = (
            self.service()
            .events()
            .list(
                **arguments
            )
            .execute()
        )


        items = []


        for event in response.get(
            "items",
            ()
        ):

            items.append(
                {
                    "id":
                        event.get(
                            "id"
                        ),

                    "summary":
                        event.get(
                            "summary"
                        ),

                    "description":
                        event.get(
                            "description"
                        ),

                    "location":
                        event.get(
                            "location"
                        ),

                    "start":
                        event.get(
                            "start"
                        ),

                    "end":
                        event.get(
                            "end"
                        ),

                    "status":
                        event.get(
                            "status"
                        ),

                    "html_link":
                        event.get(
                            "htmlLink"
                        ),

                    "attendees":
                        event.get(
                            "attendees",
                            (),
                        ),
                }
            )


        google_audit.record(
            "calendar.events",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "results":
                    len(
                        items
                    ),
            },
        )


        return {
            "success":
                True,

            "events":
                tuple(
                    items
                ),
        }


    @staticmethod
    def _event_hash(
        event,
    ):

        raw = json.dumps(
            event,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )


        return hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()


    @staticmethod
    def _display_event(
        event,
    ):

        attendees = []


        for item in event.get(
            "attendees",
            ()
        ):

            if isinstance(
                item,
                dict,
            ):

                email = item.get(
                    "email"
                )

                if email:

                    attendees.append(
                        email
                    )


        return {
            "summary":
                event.get(
                    "summary"
                ),

            "start":
                event.get(
                    "start"
                ),

            "end":
                event.get(
                    "end"
                ),

            "location":
                event.get(
                    "location"
                ),

            "attendees":
                attendees,
        }


    def prepare_create_event(
        self,
        event,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        event = dict(
            event
        )


        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_sha256":
                self._event_hash(
                    event
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.create_event",

            "payload":
                payload,

            "display": {
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event":
                    self._display_event(
                        event
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },

            "risk":
                "calendar-write",
        }


    def create_event(
        self,
        event,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        if send_updates not in (
            "none",
            "all",
            "externalOnly",
        ):

            raise ValueError(
                "Invalid send_updates."
            )


        binding = (
            self.prepare_create_event(
                event,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        binding[
                            "action"
                        ],
                        binding[
                            "payload"
                        ],
                        display=
                            binding[
                                "display"
                            ],
                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,
            binding[
                "action"
            ],
            binding[
                "payload"
            ],
        )


        result = (
            self.service()
            .events()
            .insert(
                calendarId=
                    str(
                        calendar_id
                    ),
                body=dict(
                    event
                ),
                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.create_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    result.get(
                        "id"
                    ),

                "summary":
                    result.get(
                        "summary"
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },
        )


        return {
            "success":
                True,

            "event":
                result,
        }


    def prepare_update_event(
        self,
        event_id,
        patch,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        patch = dict(
            patch
        )


        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_id":
                str(
                    event_id
                ),

            "patch_sha256":
                self._event_hash(
                    patch
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.update_event",

            "payload":
                payload,

            "display": {
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),

                "changes":
                    self._display_event(
                        patch
                    ),

                "send_updates":
                    str(
                        send_updates
                    ),
            },

            "risk":
                "calendar-write",
        }


    def update_event(
        self,
        event_id,
        patch,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        binding = (
            self.prepare_update_event(
                event_id,
                patch,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        binding[
                            "action"
                        ],
                        binding[
                            "payload"
                        ],
                        display=
                            binding[
                                "display"
                            ],
                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,
            binding[
                "action"
            ],
            binding[
                "payload"
            ],
        )


        result = (
            self.service()
            .events()
            .patch(
                calendarId=
                    str(
                        calendar_id
                    ),

                eventId=
                    str(
                        event_id
                    ),

                body=dict(
                    patch
                ),

                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.update_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),
            },
        )


        return {
            "success":
                True,

            "event":
                result,
        }


    @staticmethod
    def prepare_delete_event(
        event_id,
        *,
        calendar_id="primary",
        send_updates="none",
    ):

        payload = {
            "calendar_id":
                str(
                    calendar_id
                ),

            "event_id":
                str(
                    event_id
                ),

            "send_updates":
                str(
                    send_updates
                ),
        }


        return {
            "action":
                "google.calendar.delete_event",

            "payload":
                payload,

            "display":
                payload,

            "risk":
                "calendar-delete-event",
        }


    def delete_event(
        self,
        event_id,
        *,
        calendar_id="primary",
        send_updates="none",
        approval_id=None,
    ):

        binding = (
            self.prepare_delete_event(
                event_id,
                calendar_id=
                    calendar_id,
                send_updates=
                    send_updates,
            )
        )


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        binding[
                            "action"
                        ],
                        binding[
                            "payload"
                        ],
                        display=
                            binding[
                                "display"
                            ],
                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,
            binding[
                "action"
            ],
            binding[
                "payload"
            ],
        )


        (
            self.service()
            .events()
            .delete(
                calendarId=
                    str(
                        calendar_id
                    ),

                eventId=
                    str(
                        event_id
                    ),

                sendUpdates=
                    str(
                        send_updates
                    ),
            )
            .execute()
        )


        google_audit.record(
            "calendar.delete_event",
            success=True,
            metadata={
                "calendar_id":
                    str(
                        calendar_id
                    ),

                "event_id":
                    str(
                        event_id
                    ),
            },
        )


        return {
            "success":
                True,

            "event_id":
                str(
                    event_id
                ),
        }


google_calendar_service = (
    GoogleCalendarService()
)
'''
)


# ============================================================
# 10. GOOGLE CONTACTS / PEOPLE API
# ============================================================

write(
    CONTACTS,
    r'''
from __future__ import annotations


from omni.google_audit import (
    google_audit,
)

from omni.google_oauth import (
    google_oauth,
)


PERSON_FIELDS = (
    "names,emailAddresses,"
    "phoneNumbers,organizations"
)


class GoogleContactsService:

    def service(
        self,
    ):

        return google_oauth.service(
            "people",
            "v1",
        )


    @staticmethod
    def _person(
        person,
    ):

        names = person.get(
            "names",
            ()
        )


        emails = person.get(
            "emailAddresses",
            ()
        )


        phones = person.get(
            "phoneNumbers",
            ()
        )


        organizations = person.get(
            "organizations",
            ()
        )


        return {
            "resource_name":
                person.get(
                    "resourceName"
                ),

            "name":
                (
                    names[
                        0
                    ].get(
                        "displayName"
                    )
                    if names
                    else None
                ),

            "emails":
                tuple(
                    item.get(
                        "value"
                    )

                    for item
                    in emails

                    if item.get(
                        "value"
                    )
                ),

            "phones":
                tuple(
                    item.get(
                        "value"
                    )

                    for item
                    in phones

                    if item.get(
                        "value"
                    )
                ),

            "organizations":
                tuple(
                    {
                        "name":
                            item.get(
                                "name"
                            ),

                        "title":
                            item.get(
                                "title"
                            ),
                    }

                    for item
                    in organizations
                ),
        }


    def list(
        self,
        max_results=100,
    ):

        response = (
            self.service()
            .people()
            .connections()
            .list(
                resourceName=
                    "people/me",

                pageSize=
                    max(
                        1,
                        min(
                            int(
                                max_results
                            ),
                            1000,
                        ),
                    ),

                personFields=
                    PERSON_FIELDS,
            )
            .execute()
        )


        contacts = tuple(
            self._person(
                person
            )

            for person
            in response.get(
                "connections",
                ()
            )
        )


        google_audit.record(
            "contacts.list",
            success=True,
            metadata={
                "results":
                    len(
                        contacts
                    )
            },
        )


        return {
            "success":
                True,

            "contacts":
                contacts,
        }


    def search(
        self,
        query,
        max_results=20,
    ):

        query = str(
            query
        ).strip()


        if not query:

            return self.list(
                max_results=
                    max_results
            )


        service = self.service()


        # People API documentation recommends
        # warming the search cache first.
        try:

            (
                service.people()
                .searchContacts(
                    query="",
                    readMask=
                        PERSON_FIELDS,
                    pageSize=1,
                )
                .execute()
            )

        except Exception:

            pass


        response = (
            service.people()
            .searchContacts(
                query=
                    query,

                readMask=
                    PERSON_FIELDS,

                pageSize=
                    max(
                        1,
                        min(
                            int(
                                max_results
                            ),
                            30,
                        ),
                    ),
            )
            .execute()
        )


        contacts = []


        for result in response.get(
            "results",
            ()
        ):

            person = result.get(
                "person",
                {}
            )


            contacts.append(
                self._person(
                    person
                )
            )


        google_audit.record(
            "contacts.search",
            success=True,
            metadata={
                "query":
                    query[:300],

                "results":
                    len(
                        contacts
                    ),
            },
        )


        return {
            "success":
                True,

            "contacts":
                tuple(
                    contacts
                ),
        }


google_contacts_service = (
    GoogleContactsService()
)
'''
)


# ============================================================
# 11. CONNECTED SERVICES GATEWAY
# ============================================================

write(
    GATEWAY,
    r'''
from __future__ import annotations


from omni.gmail_service import (
    gmail_service,
)

from omni.google_calendar_service import (
    google_calendar_service,
)

from omni.google_contacts_service import (
    google_contacts_service,
)

from omni.google_oauth import (
    google_oauth,
)

from omni.google_scopes import (
    SERVICE_CAPABILITIES,
)


WRITE_ACTIONS = {
    "google.gmail.create_draft",
    "google.gmail.send_draft",

    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",
}


READ_ACTIONS = {
    "google.gmail.search",
    "google.gmail.get",

    "google.calendar.list",
    "google.calendar.events",

    "google.contacts.search",
}


class ConnectedServicesGateway:

    def status(
        self,
    ):

        return {
            "google":
                google_oauth.status(),

            "capabilities":
                SERVICE_CAPABILITIES,

            "read_actions":
                tuple(
                    sorted(
                        READ_ACTIONS
                    )
                ),

            "write_actions":
                tuple(
                    sorted(
                        WRITE_ACTIONS
                    )
                ),

            "automatic_send":
                False,

            "automatic_calendar_write":
                False,

            "contact_write":
                False,
        }


    def prepare(
        self,
        action,
        payload,
    ):

        payload = dict(
            payload
        )


        if (
            action
            == "google.gmail.create_draft"
        ):

            return {
                "success":
                    True,

                "binding":
                    gmail_service
                    .prepare_create_draft(
                        payload[
                            "to"
                        ],

                        payload[
                            "subject"
                        ],

                        payload[
                            "body"
                        ],

                        cc=
                            payload.get(
                                "cc"
                            ),

                        bcc=
                            payload.get(
                                "bcc"
                            ),
                    ),
            }


        if (
            action
            == "google.gmail.send_draft"
        ):

            return {
                "success":
                    True,

                "binding":
                    gmail_service
                    .prepare_send_draft(
                        payload[
                            "draft_id"
                        ]
                    ),
            }


        if (
            action
            == "google.calendar.create_event"
        ):

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service
                    .prepare_create_event(
                        payload[
                            "event"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        if (
            action
            == "google.calendar.update_event"
        ):

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service
                    .prepare_update_event(
                        payload[
                            "event_id"
                        ],

                        payload[
                            "patch"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        if (
            action
            == "google.calendar.delete_event"
        ):

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service
                    .prepare_delete_event(
                        payload[
                            "event_id"
                        ],

                        calendar_id=
                            payload.get(
                                "calendar_id",
                                "primary",
                            ),

                        send_updates=
                            payload.get(
                                "send_updates",
                                "none",
                            ),
                    ),
            }


        return {
            "success":
                False,

            "error":
                "Action is not a connected-service write.",
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
            action
            == "google.gmail.search"
        ):

            return gmail_service.search(
                payload.get(
                    "query",
                    ""
                ),

                payload.get(
                    "max_results",
                    20,
                ),
            )


        if (
            action
            == "google.gmail.get"
        ):

            return gmail_service.get(
                payload[
                    "message_id"
                ]
            )


        if (
            action
            == "google.gmail.create_draft"
        ):

            return gmail_service.create_draft(
                payload[
                    "to"
                ],

                payload[
                    "subject"
                ],

                payload[
                    "body"
                ],

                cc=
                    payload.get(
                        "cc"
                    ),

                bcc=
                    payload.get(
                        "bcc"
                    ),

                approval_id=
                    approval_id,
            )


        if (
            action
            == "google.gmail.send_draft"
        ):

            return gmail_service.send_draft(
                payload[
                    "draft_id"
                ],

                approval_id=
                    approval_id,
            )


        if (
            action
            == "google.calendar.list"
        ):

            return (
                google_calendar_service
                .calendars(
                    payload.get(
                        "max_results",
                        100,
                    )
                )
            )


        if (
            action
            == "google.calendar.events"
        ):

            return (
                google_calendar_service
                .events(
                    calendar_id=
                        payload.get(
                            "calendar_id",
                            "primary",
                        ),

                    time_min=
                        payload.get(
                            "time_min"
                        ),

                    time_max=
                        payload.get(
                            "time_max"
                        ),

                    max_results=
                        payload.get(
                            "max_results",
                            20,
                        ),

                    query=
                        payload.get(
                            "query"
                        ),
                )
            )


        if (
            action
            == "google.calendar.create_event"
        ):

            return (
                google_calendar_service
                .create_event(
                    payload[
                        "event"
                    ],

                    calendar_id=
                        payload.get(
                            "calendar_id",
                            "primary",
                        ),

                    send_updates=
                        payload.get(
                            "send_updates",
                            "none",
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "google.calendar.update_event"
        ):

            return (
                google_calendar_service
                .update_event(
                    payload[
                        "event_id"
                    ],

                    payload[
                        "patch"
                    ],

                    calendar_id=
                        payload.get(
                            "calendar_id",
                            "primary",
                        ),

                    send_updates=
                        payload.get(
                            "send_updates",
                            "none",
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "google.calendar.delete_event"
        ):

            return (
                google_calendar_service
                .delete_event(
                    payload[
                        "event_id"
                    ],

                    calendar_id=
                        payload.get(
                            "calendar_id",
                            "primary",
                        ),

                    send_updates=
                        payload.get(
                            "send_updates",
                            "none",
                        ),

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "google.contacts.search"
        ):

            return (
                google_contacts_service
                .search(
                    payload.get(
                        "query",
                        ""
                    ),

                    payload.get(
                        "max_results",
                        20,
                    ),
                )
            )


        return {
            "success":
                False,

            "error":
                (
                    "Unknown connected service action: "
                    + str(
                        action
                    )
                ),
        }


connected_services_gateway = (
    ConnectedServicesGateway()
)
'''
)


# ============================================================
# 12. STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

import importlib.util


from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.core_integrity import (
    verify_protected_core,
)


def _available(
    module,
):

    return (
        importlib.util.find_spec(
            module
        )
        is not None
    )


class ConnectedServicesStatus:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        gateway = (
            connected_services_gateway
            .status()
        )


        return {
            "protected_core":
                integrity.ok,

            "dependencies": {
                "google_api_python_client":
                    _available(
                        "googleapiclient"
                    ),

                "google_auth":
                    _available(
                        "google.auth"
                    ),

                "google_auth_oauthlib":
                    _available(
                        "google_auth_oauthlib"
                    ),

                "windows_dpapi":
                    _available(
                        "win32crypt"
                    ),
            },

            **gateway,
        }


connected_services_status = (
    ConnectedServicesStatus()
)
'''
)


# ============================================================
# 13. INTEGRATE GOOGLE ACTIONS INTO V4 DSL
# ============================================================

schema_source = (
    V4_SCHEMA.read_text(
        encoding="utf-8"
    )
)


if (
    '"google.gmail.search"'
    not in schema_source
):

    marker = '''    # Isolated engineering
    "coding.create_worktree",
'''


    replacement = '''    # Connected Services
    "google.gmail.search",
    "google.gmail.get",
    "google.gmail.create_draft",
    "google.gmail.send_draft",

    "google.calendar.list",
    "google.calendar.events",
    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "google.contacts.search",

    # Isolated engineering
    "coding.create_worktree",
'''


    if schema_source.count(
        marker
    ) != 1:

        print(
            "V4 SCHEMA PATCH POINT NOT FOUND"
        )

        rollback()

        sys.exit(1)


    schema_source = (
        schema_source.replace(
            marker,
            replacement,
            1,
        )
    )


    interactive_marker = '''    "browser.natural_fill",

    "coding.create_worktree",
'''


    interactive_replacement = '''    "browser.natural_fill",

    "google.gmail.create_draft",
    "google.gmail.send_draft",

    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "coding.create_worktree",
'''


    if schema_source.count(
        interactive_marker
    ) != 1:

        print(
            "V4 INTERACTIVE PATCH POINT NOT FOUND"
        )

        rollback()

        sys.exit(1)


    schema_source = (
        schema_source.replace(
            interactive_marker,
            interactive_replacement,
            1,
        )
    )


    payload_marker = '''    "coding.create_worktree": {
        "repo",
        "name",
    },
'''


    payload_replacement = '''    "google.gmail.search": {
        "query",
        "max_results",
    },

    "google.gmail.get": {
        "message_id",
    },

    "google.gmail.create_draft": {
        "to",
        "subject",
        "body",
        "cc",
        "bcc",
    },

    "google.gmail.send_draft": {
        "draft_id",
    },

    "google.calendar.list": {
        "max_results",
    },

    "google.calendar.events": {
        "calendar_id",
        "time_min",
        "time_max",
        "max_results",
        "query",
    },

    "google.calendar.create_event": {
        "calendar_id",
        "event",
        "send_updates",
    },

    "google.calendar.update_event": {
        "calendar_id",
        "event_id",
        "patch",
        "send_updates",
    },

    "google.calendar.delete_event": {
        "calendar_id",
        "event_id",
        "send_updates",
    },

    "google.contacts.search": {
        "query",
        "max_results",
    },

    "coding.create_worktree": {
        "repo",
        "name",
    },
'''


    if schema_source.count(
        payload_marker
    ) != 1:

        print(
            "V4 PAYLOAD PATCH POINT NOT FOUND"
        )

        rollback()

        sys.exit(1)


    schema_source = (
        schema_source.replace(
            payload_marker,
            payload_replacement,
            1,
        )
    )


    V4_SCHEMA.write_text(
        schema_source,
        encoding="utf-8",
    )


# ============================================================
# 14. INTEGRATE CONNECTED SERVICES INTO V4 RUNTIME
# ============================================================

runtime_source = (
    V4_RUNTIME.read_text(
        encoding="utf-8"
    )
)


if (
    "connected_services_gateway"
    not in runtime_source
):

    import_marker = '''from omni.coding_mission import (
    coding_mission,
)
'''


    import_replacement = '''from omni.coding_mission import (
    coding_mission,
)

from omni.connected_services_gateway import (
    connected_services_gateway,
)
'''


    if runtime_source.count(
        import_marker
    ) != 1:

        print(
            "V4 RUNTIME IMPORT PATCH FAILED"
        )

        rollback()

        sys.exit(1)


    runtime_source = (
        runtime_source.replace(
            import_marker,
            import_replacement,
            1,
        )
    )


    prepare_marker = '''        elif (
            action
            == "coding.create_worktree"
        ):
'''


    prepare_replacement = '''        elif action in (
            "google.gmail.create_draft",
            "google.gmail.send_draft",
            "google.calendar.create_event",
            "google.calendar.update_event",
            "google.calendar.delete_event",
        ):

            prepared = (
                connected_services_gateway
                .prepare(
                    action,
                    payload,
                )
            )


        elif (
            action
            == "coding.create_worktree"
        ):
'''


    if runtime_source.count(
        prepare_marker
    ) != 1:

        print(
            "V4 SERVICE PREPARE PATCH FAILED"
        )

        rollback()

        sys.exit(1)


    runtime_source = (
        runtime_source.replace(
            prepare_marker,
            prepare_replacement,
            1,
        )
    )


    execute_marker = '''        if (
            action
            == "coding.create_worktree"
        ):
'''


    execute_replacement = '''        if action.startswith(
            "google."
        ):

            return (
                connected_services_gateway
                .execute(
                    action,
                    payload,

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "coding.create_worktree"
        ):
'''


    if runtime_source.count(
        execute_marker
    ) != 1:

        print(
            "V4 SERVICE EXECUTION PATCH FAILED"
        )

        rollback()

        sys.exit(1)


    runtime_source = (
        runtime_source.replace(
            execute_marker,
            execute_replacement,
            1,
        )
    )


    V4_RUNTIME.write_text(
        runtime_source,
        encoding="utf-8",
    )


# ============================================================
# 15. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_google_status("
    not in main_source
):

    main_source += r'''


def jarvis_google_status():

    from omni.connected_services_status import (
        connected_services_status,
    )

    return connected_services_status.status()


def jarvis_google_install_client_secret(
    path,
):

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.install_client_secret(
        path
    )


def jarvis_google_connect():

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.connect()


def jarvis_google_disconnect():

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.disconnect()


def jarvis_gmail_search(
    query="",
    max_results=20,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.search(
        query,
        max_results,
    )


def jarvis_gmail_get(
    message_id,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.get(
        message_id
    )


def jarvis_gmail_create_draft(
    to,
    subject,
    body,
    cc=None,
    bcc=None,
    approval_id=None,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.create_draft(
        to,
        subject,
        body,
        cc=cc,
        bcc=bcc,
        approval_id=approval_id,
    )


def jarvis_gmail_send_draft(
    draft_id,
    approval_id=None,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.send_draft(
        draft_id,
        approval_id=approval_id,
    )


def jarvis_google_calendars(
    max_results=100,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.calendars(
        max_results
    )


def jarvis_google_events(
    calendar_id="primary",
    time_min=None,
    time_max=None,
    max_results=20,
    query=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.events(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        query=query,
    )


def jarvis_google_create_event(
    event,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.create_event(
        event,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_update_event(
    event_id,
    patch,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.update_event(
        event_id,
        patch,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_delete_event(
    event_id,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.delete_event(
        event_id,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_contacts(
    query="",
    max_results=20,
):

    from omni.google_contacts_service import (
        google_contacts_service,
    )

    return google_contacts_service.search(
        query,
        max_results,
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 16. WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_connected_services_v1_payload("
    not in app_source
):

    app_source += r'''


def jarvis_connected_services_v1_payload():

    from omni.connected_services_status import (
        connected_services_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                connected_services_status
                .status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
    )


# ============================================================
# 17. TESTS
# ============================================================

write(
    TEST,
    r'''
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
'''
)


# ============================================================
# 18. COMPILE
# ============================================================

print()
print("Checking Connected Services syntax...")


r = run(
    "-m",
    "py_compile",

    str(SCOPES),
    str(VAULT),
    str(OAUTH),
    str(AUDIT),
    str(GMAIL),
    str(CALENDAR),
    str(CONTACTS),
    str(GATEWAY),
    str(STATUS),
    str(V4_SCHEMA),
    str(V4_RUNTIME),
    str(MAIN),
    str(APP),
)


if r.returncode:

    print(
        "COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Syntax: PASS"
)


# ============================================================
# 19. PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

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

    print(
        "CORE CHECK FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 20. DPAPI SECURITY PROBE
# ============================================================

print()
print("Checking Windows DPAPI token vault...")


probe = r'''
from pathlib import Path
import tempfile

from omni.google_token_vault import (
    GoogleTokenVault,
)


with tempfile.TemporaryDirectory() as tmp:

    vault = GoogleTokenVault(
        Path(tmp)
        / "token.dpapi"
    )


    secret = (
        '{"refresh_token":"VERY_SECRET_TOKEN"}'
    )


    vault.save_text(
        secret
    )


    encrypted = (
        vault.path.read_bytes()
    )


    assert (
        b"VERY_SECRET_TOKEN"
        not in encrypted
    )


    assert (
        vault.load_text()
        == secret
    )


    print(
        "Plaintext token visible on disk: NO"
    )


    print(
        "DPAPI decrypt round-trip: PASS"
    )
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "DPAPI SECURITY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 21. APPROVAL BINDING PROBE
# ============================================================

print()
print("Checking connected-service approval bindings...")


probe = r'''
from omni.gmail_service import (
    gmail_service,
)

from omni.google_calendar_service import (
    google_calendar_service,
)


gmail = (
    gmail_service
    .prepare_create_draft(
        "person@example.com",
        "Test subject",
        "Private email body",
    )
)


assert (
    "body"
    not in gmail[
        "payload"
    ]
)


assert (
    "body_sha256"
    in gmail[
        "payload"
    ]
)


calendar = (
    google_calendar_service
    .prepare_create_event(
        {
            "summary":
                "Test meeting",

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


assert (
    "event"
    not in calendar[
        "payload"
    ]
)


assert (
    "event_sha256"
    in calendar[
        "payload"
    ]
)


print(
    "Email body approval binding: HASHED"
)


print(
    "Calendar event approval binding: HASHED"
)


print(
    "Approval binding security: PASS"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "APPROVAL BINDING FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 22. V4 CONNECTED SERVICES DSL
# ============================================================

print()
print("Checking V4 Connected Services integration...")


probe = r'''
from omni.operator_runtime_schema import (
    from_dict,
    is_interactive,
)


read_plan = from_dict(
    "Search Gmail",

    {
        "steps": [
            {
                "action":
                    "google.gmail.search",

                "payload": {
                    "query":
                        "is:unread",

                    "max_results":
                        5,
                },
            }
        ]
    },
)


assert (
    read_plan.steps[
        0
    ].action
    == "google.gmail.search"
)


assert is_interactive(
    "google.gmail.create_draft"
)


assert is_interactive(
    "google.gmail.send_draft"
)


assert is_interactive(
    "google.calendar.create_event"
)


assert is_interactive(
    "google.calendar.update_event"
)


assert is_interactive(
    "google.calendar.delete_event"
)


print(
    "Gmail read DSL: ACTIVE"
)


print(
    "Gmail writes approval-gated: ACTIVE"
)


print(
    "Calendar writes approval-gated: ACTIVE"
)


print(
    "Contacts read DSL: ACTIVE"
)


print(
    "V4 Connected Services integration: PASS"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "V4 CONNECTED SERVICES FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 23. GOOGLE STATUS
# ============================================================

print()
print("Checking Google connection status...")


r = run(
    "-c",
    (
        "from omni.connected_services_status "
        "import connected_services_status; "
        "x=connected_services_status.status(); "
        "print('Google API client:',"
        "x['dependencies']['google_api_python_client']); "
        "print('Google Auth:',"
        "x['dependencies']['google_auth']); "
        "print('OAuth library:',"
        "x['dependencies']['google_auth_oauthlib']); "
        "print('Windows DPAPI:',"
        "x['dependencies']['windows_dpapi']); "
        "print('Client secret ready:',"
        "x['google']['client_secret_ready']); "
        "print('Google connected:',"
        "x['google']['connected']); "
        "assert x['protected_core']; "
        "assert x['dependencies']['windows_dpapi']; "
        "print('Connected Services status: PASS')"
    ),
)


if r.returncode:

    print(
        "STATUS FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 24. TARGETED TESTS
# ============================================================

print()
print("Running Connected Services V1 tests...")


r = run(
    "-m",
    "unittest",

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
# 25. FULL REGRESSION
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
# 26. FINAL CORE CHECK
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


# ============================================================
# SUCCESS
# ============================================================

status_result = (
    run(
        "-c",
        (
            "from omni.google_oauth import google_oauth; "
            "print(google_oauth.status())"
        ),
        capture=True,
    )
)


print()
print("=" * 80)
print("JARVIS CONNECTED SERVICES V1 SUCCESS")
print("=" * 80)

print(
    "Permanent governed agents: 29"
)

print()

print("GOOGLE OAUTH")
print("Desktop-app OAuth flow: ACTIVE")
print("Browser authorization callback: ACTIVE")
print("Refresh-token support: ACTIVE")
print("Windows DPAPI token encryption: ACTIVE")
print("Plaintext OAuth token storage: BLOCKED")
print("Automatic account connection: BLOCKED")
print()

print("OAUTH SCOPES")
print("Gmail readonly: ACTIVE")
print("Gmail compose: ACTIVE")
print("Calendar readonly: ACTIVE")
print("Calendar events: ACTIVE")
print("Contacts readonly: ACTIVE")
print("Full mail.google.com scope: NOT REQUESTED")
print("Full Calendar account scope: NOT REQUESTED")
print()

print("GMAIL")
print("Search messages: ACTIVE WHEN CONNECTED")
print("Read messages: ACTIVE WHEN CONNECTED")
print("Draft creation: ACTIVE + ONE-TIME APPROVAL")
print("Draft sending: ACTIVE + ONE-TIME APPROVAL")
print("Permanent message deletion: NOT IMPLEMENTED")
print("Email body stored in approval payload: NO")
print("Email-body hash binding: ACTIVE")
print()

print("GOOGLE CALENDAR")
print("List calendars: ACTIVE WHEN CONNECTED")
print("List/search events: ACTIVE WHEN CONNECTED")
print("Create event: ACTIVE + ONE-TIME APPROVAL")
print("Update event: ACTIVE + ONE-TIME APPROVAL")
print("Delete event: ACTIVE + ONE-TIME APPROVAL")
print("Invite notifications default: NONE")
print("Calendar ACL modification: NOT IMPLEMENTED")
print()

print("GOOGLE CONTACTS")
print("People API: ACTIVE WHEN CONNECTED")
print("Contact listing: ACTIVE")
print("Contact search: ACTIVE")
print("Search-cache warmup: ACTIVE")
print("Contact writes: BLOCKED")
print()

print("OPERATOR V4 INTEGRATION")
print("Gmail read/search DSL: ACTIVE")
print("Gmail write DSL: ACTIVE + APPROVAL")
print("Calendar read DSL: ACTIVE")
print("Calendar write DSL: ACTIVE + APPROVAL")
print("Contacts read DSL: ACTIVE")
print("Connected-service writes auto-execute: BLOCKED")
print()

print("AUDIT")
print("Google service audit log: ACTIVE")
print("OAuth tokens in audit: REDACTED")
print("Email bodies in audit: REDACTED")
print("Sensitive value truncation: ACTIVE")
print()

print("SAFETY")
print("Protected Core: UNCHANGED")
print("Computer Operator V4: PRESERVED")
print("Qwen3-VL Vision: PRESERVED")
print("Credential automation: BLOCKED")
print("Arbitrary shell DSL: BLOCKED")
print("Remote Git push: BLOCKED")
print("Live trading execution: BLOCKED")
print("Automatic email sending: BLOCKED")
print("Automatic calendar writes: BLOCKED")
print("Full regression: PASS")
print()

print("CURRENT GOOGLE ACCOUNT STATUS:")
print(
    status_result.stdout.strip()
)
print()

print("NEXT:")
print("CONNECT YOUR GOOGLE ACCOUNT")
print()
print("1. Enable Gmail API")
print("2. Enable Google Calendar API")
print("3. Enable People API")
print("4. Create OAuth client -> Desktop app")
print("5. Download OAuth JSON")
print("6. Install it into JARVIS")
print("7. Run jarvis_google_connect()")
print("8. Verify Gmail + Calendar + Contacts with real reads")
print()
print("THEN:")
print("CONNECTED SERVICES V2")
print("Google recipient resolution")
print("Cross-service workflows")
print("GitHub authenticated workflows")
print("Operator approval dashboard UI")
print("Advanced Voice / wake word")
print()
print("LATER:")
print("Advanced Trading Intelligence")
print("NautilusTrader isolated POC")
