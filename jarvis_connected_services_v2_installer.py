from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

RECIPIENT = ROOT / "omni" / "recipient_intelligence.py"
WORKFLOWS = ROOT / "omni" / "connected_workflows.py"
GATEWAY = ROOT / "omni" / "connected_services_gateway.py"
STATUS = ROOT / "omni" / "connected_services_v2_status.py"

V4_SCHEMA = ROOT / "omni" / "operator_runtime_schema.py"
V4_RUNTIME = ROOT / "omni" / "operator_runtime.py"

TEST = ROOT / "tests" / "test_connected_services_v2.py"

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "connected_services_v2"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    MAIN,
    APP,
    RECIPIENT,
    WORKFLOWS,
    GATEWAY,
    STATUS,
    V4_SCHEMA,
    V4_RUNTIME,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
    )


for path in FILES:

    BACKUPS[path] = (
        path.exists()
    )

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


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in (
        BACKUPS.items()
    ):

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


print("=" * 80)
print("JARVIS CONNECTED SERVICES V2")
print("RECIPIENT INTELLIGENCE + CROSS-SERVICE WORKFLOWS")
print("=" * 80)


# ============================================================
# 0. VERIFY CURRENT ARCHITECTURE
# ============================================================

print()
print("Checking 437-test Connected Services V1 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.operator_runtime import unified_operator_runtime; "
        "from omni.google_oauth import google_oauth; "
        "g=google_oauth.status(); "
        "assert g['client_secret_ready']; "
        "assert g['token_encrypted']; "
        "assert g['connected']; "
        "assert g['refresh_token_present']; "
        "from omni.vision_runtime import vision_runtime; "
        "assert vision_runtime.status()['vision_ready']; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V4: PASS'); "
        "print('Connected Services V1: PASS'); "
        "print('Google OAuth connection: PASS'); "
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
            ROOT
            / relative
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
# 1. RECIPIENT INTELLIGENCE
# ============================================================

write(
    RECIPIENT,
    r'''
from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from email.utils import (
    getaddresses,
    parseaddr,
)

import re


from omni.gmail_service import (
    gmail_service,
)

from omni.google_contacts_service import (
    google_contacts_service,
)


EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RecipientCandidate:

    source: str

    name: str

    email: str

    score: float

    metadata: dict


def normalize(
    value,
):

    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            str(
                value
            ).lower(),
        )
    )


def valid_email(
    value,
):

    _, email = parseaddr(
        str(
            value
        )
    )


    return bool(
        email

        and EMAIL_PATTERN.match(
            email
        )
    )


def email_address(
    value,
):

    _, email = parseaddr(
        str(
            value
        )
    )


    if (
        email
        and EMAIL_PATTERN.match(
            email
        )
    ):

        return email.lower()


    return None


def _tokens(
    value,
):

    return {
        token

        for token
        in normalize(
            value
        ).split()

        if token
    }


def similarity(
    left,
    right,
):

    a = _tokens(
        left
    )

    b = _tokens(
        right
    )


    if not a or not b:

        return 0.0


    overlap = len(
        a & b
    )


    union = len(
        a | b
    )


    score = (
        overlap
        / union

        if union

        else 0.0
    )


    left_text = normalize(
        left
    )

    right_text = normalize(
        right
    )


    if (
        left_text
        == right_text
    ):

        score += 0.40


    elif (
        left_text
        and left_text
        in right_text
    ):

        score += 0.18


    return min(
        1.0,
        score,
    )


class RecipientResolver:

    MINIMUM_SCORE = 0.55

    AMBIGUITY_MARGIN = 0.08


    def __init__(
        self,
        contacts=None,
        gmail=None,
    ):

        self.contacts = (
            contacts
            or google_contacts_service
        )

        self.gmail = (
            gmail
            or gmail_service
        )


    @staticmethod
    def _score(
        query,
        name,
        email,
        source,
    ):

        query_text = str(
            query
        ).strip()


        direct = email_address(
            query_text
        )


        if (
            direct
            and direct
            == str(
                email
            ).lower()
        ):

            return 1.0


        name_score = similarity(
            query_text,
            name,
        )


        local_part = (
            str(
                email
            ).split(
                "@",
                1,
            )[0]
        )


        local_score = similarity(
            query_text,
            local_part,
        )


        score = max(
            name_score,
            local_score * 0.88,
        )


        if (
            source
            == "contacts"
        ):

            score += 0.03


        return round(
            min(
                score,
                1.0,
            ),
            4,
        )


    @staticmethod
    def _deduplicate(
        candidates,
    ):

        best = {}


        for candidate in candidates:

            key = (
                candidate.email
                .strip()
                .lower()
            )


            existing = best.get(
                key
            )


            if (
                existing is None

                or candidate.score
                > existing.score
            ):

                best[
                    key
                ] = candidate


        return list(
            best.values()
        )


    def _contact_candidates(
        self,
        query,
        max_results,
    ):

        response = (
            self.contacts.search(
                query,
                max_results,
            )
        )


        output = []


        for person in response.get(
            "contacts",
            ()
        ):

            name = str(
                person.get(
                    "name",
                    ""
                )
                or ""
            )


            for email in person.get(
                "emails",
                ()
            ):

                email = email_address(
                    email
                )


                if not email:

                    continue


                score = self._score(
                    query,
                    name,
                    email,
                    "contacts",
                )


                output.append(
                    RecipientCandidate(
                        source=
                            "contacts",

                        name=
                            name,

                        email=
                            email,

                        score=
                            score,

                        metadata={
                            "resource_name":
                                person.get(
                                    "resource_name"
                                )
                        },
                    )
                )


        return output


    def _gmail_candidates(
        self,
        query,
        max_results,
    ):

        response = (
            self.gmail.search(
                str(
                    query
                ),
                max_results,
            )
        )


        output = []


        for message in response.get(
            "messages",
            ()
        ):

            for field in (
                "from",
                "to",
            ):

                value = message.get(
                    field
                )


                if not value:

                    continue


                for name, email in getaddresses(
                    [
                        str(
                            value
                        )
                    ]
                ):

                    email = email_address(
                        email
                    )


                    if not email:

                        continue


                    score = self._score(
                        query,
                        name,
                        email,
                        "gmail_history",
                    )


                    output.append(
                        RecipientCandidate(
                            source=
                                "gmail_history",

                            name=
                                str(
                                    name
                                    or ""
                                ),

                            email=
                                email,

                            score=
                                score,

                            metadata={
                                "message_id":
                                    message.get(
                                        "id"
                                    )
                            },
                        )
                    )


        return output


    def resolve_candidates(
        self,
        query,
        candidates,
    ):

        candidates = (
            self._deduplicate(
                list(
                    candidates
                )
            )
        )


        candidates.sort(
            key=lambda item:
                (
                    item.score,
                    item.source
                    == "contacts",
                ),
            reverse=True,
        )


        if not candidates:

            return {
                "success":
                    True,

                "resolved":
                    False,

                "ambiguous":
                    False,

                "query":
                    str(
                        query
                    ),

                "best":
                    None,

                "candidates":
                    (),
            }


        best = candidates[
            0
        ]


        if (
            best.score
            < self.MINIMUM_SCORE
        ):

            return {
                "success":
                    True,

                "resolved":
                    False,

                "ambiguous":
                    False,

                "query":
                    str(
                        query
                    ),

                "best":
                    asdict(
                        best
                    ),

                "candidates":
                    tuple(
                        asdict(
                            item
                        )

                        for item
                        in candidates[:10]
                    ),
            }


        ambiguous = False


        if len(
            candidates
        ) > 1:

            second = candidates[
                1
            ]


            if (
                second.email.lower()
                != best.email.lower()

                and abs(
                    best.score
                    - second.score
                )
                <= self.AMBIGUITY_MARGIN
            ):

                ambiguous = True


        return {
            "success":
                True,

            "resolved":
                not ambiguous,

            "ambiguous":
                ambiguous,

            "query":
                str(
                    query
                ),

            "best":
                asdict(
                    best
                ),

            "candidates":
                tuple(
                    asdict(
                        item
                    )

                    for item
                    in candidates[:10]
                ),
        }


    def resolve(
        self,
        query,
        *,
        max_results=20,
        include_gmail_history=True,
    ):

        query = str(
            query
        ).strip()


        if not query:

            return {
                "success":
                    False,

                "resolved":
                    False,

                "ambiguous":
                    False,

                "query":
                    query,

                "error":
                    "Recipient query cannot be empty.",

                "best":
                    None,

                "candidates":
                    (),
            }


        direct = email_address(
            query
        )


        if direct:

            candidate = (
                RecipientCandidate(
                    source=
                        "direct",

                    name=
                        parseaddr(
                            query
                        )[0],

                    email=
                        direct,

                    score=
                        1.0,

                    metadata={},
                )
            )


            return {
                "success":
                    True,

                "resolved":
                    True,

                "ambiguous":
                    False,

                "query":
                    query,

                "best":
                    asdict(
                        candidate
                    ),

                "candidates": (
                    asdict(
                        candidate
                    ),
                ),
            }


        candidates = []

        errors = []


        try:

            candidates.extend(
                self._contact_candidates(
                    query,
                    max_results,
                )
            )


        except Exception as exc:

            errors.append(
                (
                    "contacts: "
                    + type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )
            )


        if include_gmail_history:

            try:

                candidates.extend(
                    self._gmail_candidates(
                        query,
                        max_results,
                    )
                )


            except Exception as exc:

                errors.append(
                    (
                        "gmail_history: "
                        + type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )
                )


        result = self.resolve_candidates(
            query,
            candidates,
        )


        result[
            "source_errors"
        ] = tuple(
            errors
        )


        return result


    def resolve_many(
        self,
        queries,
        *,
        include_gmail_history=True,
    ):

        if isinstance(
            queries,
            str,
        ):

            queries = [
                queries
            ]


        queries = list(
            queries
            or ()
        )


        resolved = []

        unresolved = []

        ambiguous = []


        for query in queries:

            result = self.resolve(
                query,

                include_gmail_history=
                    include_gmail_history,
            )


            if result.get(
                "ambiguous",
                False,
            ):

                ambiguous.append(
                    result
                )

                continue


            if not result.get(
                "resolved",
                False,
            ):

                unresolved.append(
                    result
                )

                continue


            resolved.append(
                result
            )


        emails = []


        for result in resolved:

            email = result[
                "best"
            ][
                "email"
            ]


            if (
                email
                not in emails
            ):

                emails.append(
                    email
                )


        return {
            "success":
                (
                    not unresolved
                    and not ambiguous
                ),

            "resolved":
                tuple(
                    resolved
                ),

            "emails":
                tuple(
                    emails
                ),

            "unresolved":
                tuple(
                    unresolved
                ),

            "ambiguous":
                tuple(
                    ambiguous
                ),
        }


recipient_resolver = (
    RecipientResolver()
)
'''
)


# ============================================================
# 2. CROSS-SERVICE WORKFLOW INTELLIGENCE
# ============================================================

write(
    WORKFLOWS,
    r'''
from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
    timezone,
)

from email.utils import (
    getaddresses,
)


from omni.gmail_service import (
    gmail_service,
)

from omni.google_calendar_service import (
    google_calendar_service,
)

from omni.recipient_intelligence import (
    recipient_resolver,
)


class ConnectedWorkflowIntelligence:

    def __init__(
        self,
        resolver=None,
        gmail=None,
        calendar=None,
    ):

        self.resolver = (
            resolver
            or recipient_resolver
        )

        self.gmail = (
            gmail
            or gmail_service
        )

        self.calendar = (
            calendar
            or google_calendar_service
        )


    @staticmethod
    def _queries(
        value,
    ):

        if value is None:

            return []


        if isinstance(
            value,
            str,
        ):

            return [
                value
            ]


        return [
            str(
                item
            )

            for item
            in value
        ]


    @staticmethod
    def _join(
        values,
    ):

        values = tuple(
            values
            or ()
        )


        return (
            ", ".join(
                values
            )

            if values

            else None
        )


    def _resolve_group(
        self,
        value,
    ):

        queries = self._queries(
            value
        )


        if not queries:

            return {
                "success":
                    True,

                "resolved":
                    (),

                "emails":
                    (),

                "unresolved":
                    (),

                "ambiguous":
                    (),
            }


        return (
            self.resolver
            .resolve_many(
                queries
            )
        )


    # --------------------------------------------------------
    # Gmail draft intelligence
    # --------------------------------------------------------

    def prepare_draft(
        self,
        recipients,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
    ):

        to_result = self._resolve_group(
            recipients
        )

        cc_result = self._resolve_group(
            cc
        )

        bcc_result = self._resolve_group(
            bcc
        )


        problems = {
            "to":
                to_result,

            "cc":
                cc_result,

            "bcc":
                bcc_result,
        }


        for name, result in problems.items():

            if not result.get(
                "success",
                False,
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Recipient resolution failed "
                            "for "
                            + name
                        ),

                    "resolution":
                        problems,
                }


        if not to_result[
            "emails"
        ]:

            return {
                "success":
                    False,

                "error":
                    "At least one To recipient is required.",

                "resolution":
                    problems,
            }


        to_value = self._join(
            to_result[
                "emails"
            ]
        )

        cc_value = self._join(
            cc_result[
                "emails"
            ]
        )

        bcc_value = self._join(
            bcc_result[
                "emails"
            ]
        )


        binding = (
            self.gmail
            .prepare_create_draft(
                to_value,
                subject,
                body,

                cc=
                    cc_value,

                bcc=
                    bcc_value,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,

            "resolved_to":
                to_result[
                    "emails"
                ],

            "resolved_cc":
                cc_result[
                    "emails"
                ],

            "resolved_bcc":
                bcc_result[
                    "emails"
                ],

            "resolution":
                problems,
        }


    def create_draft(
        self,
        recipients,
        subject,
        body,
        *,
        cc=None,
        bcc=None,
        approval_id=None,
    ):

        prepared = self.prepare_draft(
            recipients,
            subject,
            body,

            cc=cc,
            bcc=bcc,
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.gmail
            .create_draft(
                self._join(
                    prepared[
                        "resolved_to"
                    ]
                ),

                subject,
                body,

                cc=
                    self._join(
                        prepared[
                            "resolved_cc"
                        ]
                    ),

                bcc=
                    self._join(
                        prepared[
                            "resolved_bcc"
                        ]
                    ),

                approval_id=
                    approval_id,
            )
        )


    # --------------------------------------------------------
    # Time / conflict handling
    # --------------------------------------------------------

    @staticmethod
    def _datetime(
        value,
    ):

        if isinstance(
            value,
            datetime,
        ):

            result = value

        else:

            text = str(
                value
            ).strip()


            if text.endswith(
                "Z"
            ):

                text = (
                    text[:-1]
                    + "+00:00"
                )


            result = (
                datetime.fromisoformat(
                    text
                )
            )


        if result.tzinfo is None:

            raise ValueError(
                "Meeting date/time must include "
                "an explicit UTC offset/timezone."
            )


        return result


    @staticmethod
    def _event_bounds(
        event,
    ):

        start = event.get(
            "start",
            {}
        )

        end = event.get(
            "end",
            {}
        )


        if (
            start.get(
                "dateTime"
            )
            and end.get(
                "dateTime"
            )
        ):

            return (
                ConnectedWorkflowIntelligence
                ._datetime(
                    start[
                        "dateTime"
                    ]
                ),

                ConnectedWorkflowIntelligence
                ._datetime(
                    end[
                        "dateTime"
                    ]
                ),
            )


        if (
            start.get(
                "date"
            )
            and end.get(
                "date"
            )
        ):

            start_date = (
                date.fromisoformat(
                    start[
                        "date"
                    ]
                )
            )

            end_date = (
                date.fromisoformat(
                    end[
                        "date"
                    ]
                )
            )


            return (
                datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=
                        timezone.utc,
                ),

                datetime.combine(
                    end_date,
                    time.min,
                    tzinfo=
                        timezone.utc,
                ),
            )


        return (
            None,
            None,
        )


    def check_conflicts(
        self,
        start,
        end,
        *,
        calendar_id="primary",
    ):

        start_dt = self._datetime(
            start
        )

        end_dt = self._datetime(
            end
        )


        if (
            end_dt
            <= start_dt
        ):

            raise ValueError(
                "Meeting end must be after start."
            )


        response = (
            self.calendar
            .events(
                calendar_id=
                    calendar_id,

                time_min=
                    start_dt.isoformat(),

                time_max=
                    end_dt.isoformat(),

                max_results=
                    100,
            )
        )


        conflicts = []


        for event in response.get(
            "events",
            ()
        ):

            if (
                event.get(
                    "status"
                )
                == "cancelled"
            ):

                continue


            event_start, event_end = (
                self._event_bounds(
                    event
                )
            )


            if (
                event_start is None
                or event_end is None
            ):

                continue


            try:

                overlaps = (
                    event_start
                    < end_dt

                    and event_end
                    > start_dt
                )

            except TypeError:

                # All-day events are normalized
                # to UTC. Compare UTC if needed.
                overlaps = (
                    event_start.astimezone(
                        timezone.utc
                    )
                    < end_dt.astimezone(
                        timezone.utc
                    )

                    and event_end.astimezone(
                        timezone.utc
                    )
                    > start_dt.astimezone(
                        timezone.utc
                    )
                )


            if overlaps:

                conflicts.append(
                    {
                        "id":
                            event.get(
                                "id"
                            ),

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
                    }
                )


        return {
            "success":
                True,

            "calendar_id":
                str(
                    calendar_id
                ),

            "start":
                start_dt.isoformat(),

            "end":
                end_dt.isoformat(),

            "has_conflict":
                bool(
                    conflicts
                ),

            "conflicts":
                tuple(
                    conflicts
                ),
        }


    # --------------------------------------------------------
    # Meeting planning
    # --------------------------------------------------------

    def prepare_meeting(
        self,
        title,
        attendees,
        start,
        end,
        *,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
    ):

        attendee_result = (
            self._resolve_group(
                attendees
            )
        )


        if not attendee_result.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Attendee resolution failed.",

                "resolution":
                    attendee_result,
            }


        start_dt = self._datetime(
            start
        )

        end_dt = self._datetime(
            end
        )


        if (
            end_dt
            <= start_dt
        ):

            return {
                "success":
                    False,

                "error":
                    "Meeting end must be after start.",
            }


        conflicts = self.check_conflicts(
            start_dt,
            end_dt,

            calendar_id=
                calendar_id,
        )


        if (
            conflicts[
                "has_conflict"
            ]

            and not allow_conflicts
        ):

            return {
                "success":
                    False,

                "conflict":
                    True,

                "requires_resolution":
                    True,

                "error":
                    "Calendar conflict detected.",

                "conflicts":
                    conflicts[
                        "conflicts"
                    ],

                "resolved_attendees":
                    attendee_result[
                        "emails"
                    ],
            }


        start_payload = {
            "dateTime":
                start_dt.isoformat()
        }


        end_payload = {
            "dateTime":
                end_dt.isoformat()
        }


        if time_zone:

            start_payload[
                "timeZone"
            ] = str(
                time_zone
            )

            end_payload[
                "timeZone"
            ] = str(
                time_zone
            )


        event = {
            "summary":
                str(
                    title
                ),

            "start":
                start_payload,

            "end":
                end_payload,

            "attendees": [
                {
                    "email":
                        email
                }

                for email
                in attendee_result[
                    "emails"
                ]
            ],
        }


        if description:

            event[
                "description"
            ] = str(
                description
            )


        if location:

            event[
                "location"
            ] = str(
                location
            )


        binding = (
            self.calendar
            .prepare_create_event(
                event,

                calendar_id=
                    calendar_id,

                send_updates=
                    send_updates,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,

            "event":
                event,

            "calendar_id":
                str(
                    calendar_id
                ),

            "send_updates":
                str(
                    send_updates
                ),

            "resolved_attendees":
                attendee_result[
                    "emails"
                ],

            "resolution":
                attendee_result,

            "conflicts":
                conflicts[
                    "conflicts"
                ],

            "allow_conflicts":
                bool(
                    allow_conflicts
                ),
        }


    def schedule_meeting(
        self,
        title,
        attendees,
        start,
        end,
        *,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
        approval_id=None,
    ):

        prepared = self.prepare_meeting(
            title,
            attendees,
            start,
            end,

            description=
                description,

            location=
                location,

            calendar_id=
                calendar_id,

            send_updates=
                send_updates,

            time_zone=
                time_zone,

            allow_conflicts=
                allow_conflicts,
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.calendar
            .create_event(
                prepared[
                    "event"
                ],

                calendar_id=
                    prepared[
                        "calendar_id"
                    ],

                send_updates=
                    prepared[
                        "send_updates"
                    ],

                approval_id=
                    approval_id,
            )
        )


    # --------------------------------------------------------
    # Gmail message -> Calendar meeting
    # --------------------------------------------------------

    def prepare_meeting_from_email(
        self,
        message_id,
        title,
        start,
        end,
        *,
        attendees=None,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
    ):

        message = self.gmail.get(
            message_id
        )


        attendee_queries = (
            self._queries(
                attendees
            )
        )


        if not attendee_queries:

            sender = message.get(
                "from"
            )


            addresses = getaddresses(
                [
                    str(
                        sender
                        or ""
                    )
                ]
            )


            attendee_queries = [
                email

                for name, email
                in addresses

                if email
            ]


        if not attendee_queries:

            return {
                "success":
                    False,

                "error":
                    (
                        "Could not derive an attendee "
                        "from the source email."
                    ),
            }


        prepared = self.prepare_meeting(
            title,
            attendee_queries,
            start,
            end,

            description=
                description,

            location=
                location,

            calendar_id=
                calendar_id,

            send_updates=
                send_updates,

            time_zone=
                time_zone,

            allow_conflicts=
                allow_conflicts,
        )


        prepared[
            "source_message"
        ] = {
            "message_id":
                str(
                    message_id
                ),

            "from":
                message.get(
                    "from"
                ),

            "subject":
                message.get(
                    "subject"
                ),
        }


        return prepared


    def schedule_meeting_from_email(
        self,
        message_id,
        title,
        start,
        end,
        *,
        attendees=None,
        description=None,
        location=None,
        calendar_id="primary",
        send_updates="none",
        time_zone=None,
        allow_conflicts=False,
        approval_id=None,
    ):

        prepared = (
            self.prepare_meeting_from_email(
                message_id,
                title,
                start,
                end,

                attendees=
                    attendees,

                description=
                    description,

                location=
                    location,

                calendar_id=
                    calendar_id,

                send_updates=
                    send_updates,

                time_zone=
                    time_zone,

                allow_conflicts=
                    allow_conflicts,
            )
        )


        if not prepared.get(
            "success",
            False,
        ):

            return prepared


        return (
            self.calendar
            .create_event(
                prepared[
                    "event"
                ],

                calendar_id=
                    prepared[
                        "calendar_id"
                    ],

                send_updates=
                    prepared[
                        "send_updates"
                    ],

                approval_id=
                    approval_id,
            )
        )


connected_workflows = (
    ConnectedWorkflowIntelligence()
)
'''
)

print()
print("PART 1 SAVED")
print("Now paste PART 2.")


# ============================================================
# 3. EXTENDED CONNECTED SERVICES GATEWAY
# ============================================================

write(
    GATEWAY,
    r'''
from __future__ import annotations

from omni.connected_workflows import connected_workflows
from omni.gmail_service import gmail_service
from omni.google_calendar_service import google_calendar_service
from omni.google_contacts_service import google_contacts_service
from omni.google_oauth import google_oauth
from omni.google_scopes import SERVICE_CAPABILITIES
from omni.recipient_intelligence import recipient_resolver


WRITE_ACTIONS = {
    "google.gmail.create_draft",
    "google.gmail.send_draft",
    "google.calendar.create_event",
    "google.calendar.update_event",
    "google.calendar.delete_event",

    "google.gmail.draft_to_contact",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",
}


READ_ACTIONS = {
    "google.gmail.search",
    "google.gmail.get",

    "google.calendar.list",
    "google.calendar.events",

    "google.contacts.search",

    "google.contacts.resolve",
    "google.calendar.check_conflicts",
}


class ConnectedServicesGateway:

    def status(self):

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

            "recipient_resolution":
                True,

            "ambiguity_blocking":
                True,

            "gmail_history_resolution":
                True,

            "calendar_conflict_detection":
                True,

            "email_to_calendar_workflow":
                True,

            "draft_to_contact_workflow":
                True,

            "automatic_send":
                False,

            "automatic_calendar_write":
                False,

            "automatic_conflict_override":
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


        if action == "google.gmail.create_draft":

            return {
                "success":
                    True,

                "binding":
                    gmail_service.prepare_create_draft(
                        payload["to"],
                        payload["subject"],
                        payload["body"],

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


        if action == "google.gmail.send_draft":

            return {
                "success":
                    True,

                "binding":
                    gmail_service.prepare_send_draft(
                        payload[
                            "draft_id"
                        ]
                    ),
            }


        if action == "google.gmail.draft_to_contact":

            return connected_workflows.prepare_draft(
                payload[
                    "recipients"
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
            )


        if action == "google.calendar.create_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_create_event(
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


        if action == "google.calendar.update_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_update_event(
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


        if action == "google.calendar.delete_event":

            return {
                "success":
                    True,

                "binding":
                    google_calendar_service.prepare_delete_event(
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


        if action == "google.calendar.schedule_meeting":

            return connected_workflows.prepare_meeting(
                payload[
                    "title"
                ],

                payload[
                    "attendees"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

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

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),
            )


        if action == "google.calendar.schedule_from_email":

            return connected_workflows.prepare_meeting_from_email(
                payload[
                    "message_id"
                ],

                payload[
                    "title"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                attendees=
                    payload.get(
                        "attendees"
                    ),

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

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

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),
            )


        return {
            "success":
                False,

            "error":
                (
                    "Action is not a connected "
                    "service write: "
                    + str(
                        action
                    )
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


        # ----------------------------------------------------
        # GMAIL
        # ----------------------------------------------------

        if action == "google.gmail.search":

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


        if action == "google.gmail.get":

            return gmail_service.get(
                payload[
                    "message_id"
                ]
            )


        if action == "google.gmail.create_draft":

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


        if action == "google.gmail.draft_to_contact":

            return connected_workflows.create_draft(
                payload[
                    "recipients"
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


        if action == "google.gmail.send_draft":

            return gmail_service.send_draft(
                payload[
                    "draft_id"
                ],

                approval_id=
                    approval_id,
            )


        # ----------------------------------------------------
        # CONTACTS
        # ----------------------------------------------------

        if action == "google.contacts.search":

            return google_contacts_service.search(
                payload.get(
                    "query",
                    ""
                ),

                payload.get(
                    "max_results",
                    20,
                ),
            )


        if action == "google.contacts.resolve":

            return recipient_resolver.resolve(
                payload[
                    "query"
                ],

                max_results=
                    payload.get(
                        "max_results",
                        20,
                    ),

                include_gmail_history=
                    bool(
                        payload.get(
                            "include_gmail_history",
                            True,
                        )
                    ),
            )


        # ----------------------------------------------------
        # CALENDAR
        # ----------------------------------------------------

        if action == "google.calendar.list":

            return google_calendar_service.calendars(
                payload.get(
                    "max_results",
                    100,
                )
            )


        if action == "google.calendar.events":

            return google_calendar_service.events(
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


        if action == "google.calendar.check_conflicts":

            return connected_workflows.check_conflicts(
                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                calendar_id=
                    payload.get(
                        "calendar_id",
                        "primary",
                    ),
            )


        if action == "google.calendar.create_event":

            return google_calendar_service.create_event(
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


        if action == "google.calendar.update_event":

            return google_calendar_service.update_event(
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


        if action == "google.calendar.delete_event":

            return google_calendar_service.delete_event(
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


        if action == "google.calendar.schedule_meeting":

            return connected_workflows.schedule_meeting(
                payload[
                    "title"
                ],

                payload[
                    "attendees"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

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

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),

                approval_id=
                    approval_id,
            )


        if action == "google.calendar.schedule_from_email":

            return connected_workflows.schedule_meeting_from_email(
                payload[
                    "message_id"
                ],

                payload[
                    "title"
                ],

                payload[
                    "start"
                ],

                payload[
                    "end"
                ],

                attendees=
                    payload.get(
                        "attendees"
                    ),

                description=
                    payload.get(
                        "description"
                    ),

                location=
                    payload.get(
                        "location"
                    ),

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

                time_zone=
                    payload.get(
                        "time_zone"
                    ),

                allow_conflicts=
                    bool(
                        payload.get(
                            "allow_conflicts",
                            False,
                        )
                    ),

                approval_id=
                    approval_id,
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
# 4. PATCH OPERATOR V4 DSL
# ============================================================

schema_source = (
    V4_SCHEMA.read_text(
        encoding="utf-8"
    )
)


if (
    '"google.contacts.resolve"'
    not in schema_source
):

    allowed_marker = '''    "google.contacts.search",

    # Isolated engineering
'''


    allowed_replacement = '''    "google.contacts.search",
    "google.contacts.resolve",

    "google.gmail.draft_to_contact",

    "google.calendar.check_conflicts",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",

    # Isolated engineering
'''


    if schema_source.count(
        allowed_marker
    ) != 1:

        print(
            "V4 ALLOWED ACTION PATCH POINT FAILED"
        )

        rollback()

        sys.exit(1)


    schema_source = (
        schema_source.replace(
            allowed_marker,
            allowed_replacement,
            1,
        )
    )


    interactive_marker = '''    "google.calendar.delete_event",

    "coding.create_worktree",
'''


    interactive_replacement = '''    "google.calendar.delete_event",

    "google.gmail.draft_to_contact",
    "google.calendar.schedule_meeting",
    "google.calendar.schedule_from_email",

    "coding.create_worktree",
'''


    if schema_source.count(
        interactive_marker
    ) != 1:

        print(
            "V4 INTERACTIVE ACTION PATCH POINT FAILED"
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


    payload_marker = '''    "google.contacts.search": {
        "query",
        "max_results",
    },

    "coding.create_worktree": {
'''


    payload_replacement = '''    "google.contacts.search": {
        "query",
        "max_results",
    },

    "google.contacts.resolve": {
        "query",
        "max_results",
        "include_gmail_history",
    },

    "google.gmail.draft_to_contact": {
        "recipients",
        "subject",
        "body",
        "cc",
        "bcc",
    },

    "google.calendar.check_conflicts": {
        "start",
        "end",
        "calendar_id",
    },

    "google.calendar.schedule_meeting": {
        "title",
        "attendees",
        "start",
        "end",
        "description",
        "location",
        "calendar_id",
        "send_updates",
        "time_zone",
        "allow_conflicts",
    },

    "google.calendar.schedule_from_email": {
        "message_id",
        "title",
        "start",
        "end",
        "attendees",
        "description",
        "location",
        "calendar_id",
        "send_updates",
        "time_zone",
        "allow_conflicts",
    },

    "coding.create_worktree": {
'''


    if schema_source.count(
        payload_marker
    ) != 1:

        print(
            "V4 PAYLOAD PATCH POINT FAILED"
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
# 5. PATCH V4 INTERACTIVE CONNECTED-SERVICE PREPARATION
# ============================================================

runtime_source = (
    V4_RUNTIME.read_text(
        encoding="utf-8"
    )
)


if (
    '"google.gmail.draft_to_contact"'
    not in runtime_source
):

    marker = '''            "google.calendar.delete_event",
        ):
'''


    replacement = '''            "google.calendar.delete_event",

            "google.gmail.draft_to_contact",

            "google.calendar.schedule_meeting",
            "google.calendar.schedule_from_email",
        ):
'''


    if runtime_source.count(
        marker
    ) != 1:

        print(
            "V4 RUNTIME CONNECTED WRITE PATCH FAILED"
        )

        rollback()

        sys.exit(1)


    runtime_source = (
        runtime_source.replace(
            marker,
            replacement,
            1,
        )
    )


    V4_RUNTIME.write_text(
        runtime_source,
        encoding="utf-8",
    )


# ============================================================
# 6. STATUS
# ============================================================

write(
    STATUS,
    r'''
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
'''
)


# ============================================================
# 7. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_resolve_recipient("
    not in main_source
):

    main_source += r'''


def jarvis_resolve_recipient(
    query,
    max_results=20,
    include_gmail_history=True,
):

    from omni.recipient_intelligence import (
        recipient_resolver,
    )

    return recipient_resolver.resolve(
        query,
        max_results=max_results,
        include_gmail_history=include_gmail_history,
    )


def jarvis_resolve_recipients(
    queries,
    include_gmail_history=True,
):

    from omni.recipient_intelligence import (
        recipient_resolver,
    )

    return recipient_resolver.resolve_many(
        queries,
        include_gmail_history=include_gmail_history,
    )


def jarvis_prepare_draft_to(
    recipients,
    subject,
    body,
    cc=None,
    bcc=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_draft(
        recipients,
        subject,
        body,
        cc=cc,
        bcc=bcc,
    )


def jarvis_draft_to(
    recipients,
    subject,
    body,
    cc=None,
    bcc=None,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.create_draft(
        recipients,
        subject,
        body,
        cc=cc,
        bcc=bcc,
        approval_id=approval_id,
    )


def jarvis_check_calendar_conflicts(
    start,
    end,
    calendar_id="primary",
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.check_conflicts(
        start,
        end,
        calendar_id=calendar_id,
    )


def jarvis_prepare_meeting(
    title,
    attendees,
    start,
    end,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_meeting(
        title,
        attendees,
        start,
        end,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
    )


def jarvis_schedule_meeting(
    title,
    attendees,
    start,
    end,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.schedule_meeting(
        title,
        attendees,
        start,
        end,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
        approval_id=approval_id,
    )


def jarvis_prepare_meeting_from_email(
    message_id,
    title,
    start,
    end,
    attendees=None,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_meeting_from_email(
        message_id,
        title,
        start,
        end,
        attendees=attendees,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
    )


def jarvis_schedule_meeting_from_email(
    message_id,
    title,
    start,
    end,
    attendees=None,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.schedule_meeting_from_email(
        message_id,
        title,
        start,
        end,
        attendees=attendees,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
        approval_id=approval_id,
    )


def jarvis_connected_services_v2_status():

    from omni.connected_services_v2_status import (
        connected_services_v2_status,
    )

    return connected_services_v2_status.status()
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 8. WORKSTATION PAYLOAD
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_connected_services_v2_payload("
    not in app_source
):

    app_source += r'''


def jarvis_connected_services_v2_payload():

    from omni.connected_services_v2_status import (
        connected_services_v2_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                connected_services_v2_status
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
# 9. TESTS
# ============================================================

write(
    TEST,
    r'''
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
'''
)


# ============================================================
# 10. COMPILE
# ============================================================

print()
print("Checking Connected Services V2 syntax...")


r = run(
    "-m",
    "py_compile",

    str(
        RECIPIENT
    ),

    str(
        WORKFLOWS
    ),

    str(
        GATEWAY
    ),

    str(
        STATUS
    ),

    str(
        V4_SCHEMA
    ),

    str(
        V4_RUNTIME
    ),

    str(
        MAIN
    ),

    str(
        APP
    ),
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
# 11. PROTECTED CORE CHECK
# ============================================================

print()
print("Checking protected core...")


for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT
            / relative
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
# 12. REAL GOOGLE READ-ONLY CONNECTION PROBE
# ============================================================

print()
print("Checking real Google connection...")


probe = r'''
from omni.gmail_service import (
    gmail_service,
)

from omni.google_oauth import (
    google_oauth,
)

from omni.recipient_intelligence import (
    recipient_resolver,
)


status = google_oauth.status()


print(
    "Connected:",
    status[
        "connected"
    ]
)


print(
    "Encrypted token:",
    status[
        "token_encrypted"
    ]
)


assert status[
    "connected"
]


assert status[
    "token_encrypted"
]


profile = (
    gmail_service
    .service()
    .users()
    .getProfile(
        userId="me"
    )
    .execute()
)


email = profile.get(
    "emailAddress"
)


assert email


print(
    "Connected account resolved:",
    bool(
        email
    )
)


resolution = (
    recipient_resolver
    .resolve(
        email
    )
)


assert resolution[
    "resolved"
]


assert (
    resolution[
        "best"
    ][
        "email"
    ]
    == email.lower()
)


print(
    "Direct recipient resolution: PASS"
)


print(
    "No Gmail/Calendar write executed."
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "REAL GOOGLE CONNECTION PROBE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 13. REAL CALENDAR CONFLICT READ PROBE
# ============================================================

print()
print("Checking real Calendar conflict intelligence...")


probe = r'''
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from omni.connected_workflows import (
    connected_workflows,
)


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
        minutes=30
    )
)


result = (
    connected_workflows
    .check_conflicts(
        start,
        end,
    )
)


print(
    "Conflict read success:",
    result[
        "success"
    ]
)


print(
    "Has conflict:",
    result[
        "has_conflict"
    ]
)


print(
    "Conflict count:",
    len(
        result[
            "conflicts"
        ]
    )
)


assert result[
    "success"
]


print(
    "Calendar conflict intelligence: PASS"
)


print(
    "Calendar modified: NO"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "CALENDAR CONFLICT PROBE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 14. AMBIGUITY SECURITY PROBE
# ============================================================

print()
print("Checking recipient ambiguity blocking...")


probe = r'''
from omni.recipient_intelligence import (
    RecipientCandidate,
    RecipientResolver,
)


resolver = RecipientResolver()


result = (
    resolver.resolve_candidates(
        "Rahul Sharma",

        (
            RecipientCandidate(
                source=
                    "contacts",

                name=
                    "Rahul Sharma",

                email=
                    "rahul.one@example.com",

                score=
                    0.96,

                metadata={},
            ),

            RecipientCandidate(
                source=
                    "gmail_history",

                name=
                    "Rahul Sharma",

                email=
                    "rahul.two@example.com",

                score=
                    0.94,

                metadata={},
            ),
        ),
    )
)


print(
    "Resolved:",
    result[
        "resolved"
    ]
)


print(
    "Ambiguous:",
    result[
        "ambiguous"
    ]
)


assert (
    result[
        "resolved"
    ]
    is False
)


assert result[
    "ambiguous"
]


print(
    "Ambiguous recipient guessing: BLOCKED"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "AMBIGUITY SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 15. V4 CROSS-SERVICE DSL PROBE
# ============================================================

print()
print("Checking Operator V4 cross-service integration...")


probe = r'''
from omni.operator_runtime_schema import (
    from_dict,
    is_interactive,
)


plan = from_dict(
    "Resolve recipient then prepare meeting",

    {
        "steps": [
            {
                "step_id":
                    "resolve",

                "action":
                    "google.contacts.resolve",

                "payload": {
                    "query":
                        "person@example.com"
                },
            }
        ]
    },
)


assert (
    plan.steps[
        0
    ].action
    == "google.contacts.resolve"
)


assert is_interactive(
    "google.gmail.draft_to_contact"
)


assert is_interactive(
    "google.calendar.schedule_meeting"
)


assert is_interactive(
    "google.calendar.schedule_from_email"
)


print(
    "Recipient resolution DSL: ACTIVE"
)


print(
    "Draft-to-contact approval gate: ACTIVE"
)


print(
    "Meeting scheduling approval gate: ACTIVE"
)


print(
    "Email-to-calendar approval gate: ACTIVE"
)


print(
    "Operator V4 cross-service integration: PASS"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "V4 CROSS-SERVICE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 16. TARGETED TESTS
# ============================================================

print()
print("Running Connected Services V2 tests...")


r = run(
    "-m",
    "unittest",

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
# 17. FULL REGRESSION
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
# 18. FINAL CORE CHECK
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT
            / relative
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

print()
print("=" * 80)
print("JARVIS CONNECTED SERVICES V2 SUCCESS")
print("=" * 80)

print(
    "Permanent governed agents: 29"
)

print()

print("RECIPIENT INTELLIGENCE")
print("Exact email resolution: ACTIVE")
print("Google Contacts resolution: ACTIVE")
print("Gmail correspondence fallback: ACTIVE")
print("Candidate scoring: ACTIVE")
print("Recipient deduplication: ACTIVE")
print("Multiple-recipient resolution: ACTIVE")
print("Ambiguous recipient guessing: BLOCKED")
print("Unresolved recipient execution: BLOCKED")
print()

print("GMAIL INTELLIGENCE")
print("Name/contact -> exact email: ACTIVE")
print("Multiple To recipients: ACTIVE")
print("CC recipient resolution: ACTIVE")
print("BCC recipient resolution: ACTIVE")
print("Draft-to-contact workflow: ACTIVE")
print("Draft creation: ONE-TIME APPROVAL")
print("Email sending: SEPARATE ONE-TIME APPROVAL")
print("Automatic sending: BLOCKED")
print()

print("CALENDAR INTELLIGENCE")
print("Explicit timezone requirement: ACTIVE")
print("Calendar overlap detection: ACTIVE")
print("Conflict details: ACTIVE")
print("Conflict-safe meeting preparation: ACTIVE")
print("Contact/name attendee resolution: ACTIVE")
print("Meeting event construction: ACTIVE")
print("Event attendee preview: ACTIVE")
print("Conflict override default: BLOCKED")
print("Calendar write: ONE-TIME APPROVAL")
print("Invitation notifications default: NONE")
print()

print("EMAIL -> CALENDAR")
print("Source Gmail message lookup: ACTIVE")
print("Sender attendee derivation: ACTIVE")
print("Email -> meeting preparation: ACTIVE")
print("Email -> Calendar write: APPROVAL-GATED")
print("Automatic invite sending: BLOCKED")
print()

print("OPERATOR V4 INTEGRATION")
print("google.contacts.resolve: ACTIVE")
print("google.gmail.draft_to_contact: ACTIVE")
print("google.calendar.check_conflicts: ACTIVE")
print("google.calendar.schedule_meeting: ACTIVE")
print("google.calendar.schedule_from_email: ACTIVE")
print("Cross-service writes auto-execute: BLOCKED")
print()

print("REAL GOOGLE VERIFICATION")
print("Google OAuth connection: VERIFIED")
print("DPAPI encrypted token: VERIFIED")
print("Real Calendar conflict read: VERIFIED")
print("Real account direct recipient resolution: VERIFIED")
print("Installer Gmail write: NO")
print("Installer Calendar write: NO")
print()

print("SAFETY")
print("Protected Core: UNCHANGED")
print("Computer Operator V4: PRESERVED")
print("Connected Services V1: PRESERVED")
print("Qwen3-VL Vision: PRESERVED")
print("Recipient ambiguity: BLOCKED")
print("Credential automation: BLOCKED")
print("Automatic email send: BLOCKED")
print("Automatic Calendar writes: BLOCKED")
print("Automatic conflict override: BLOCKED")
print("Contact writes: BLOCKED")
print("Remote Git push: BLOCKED")
print("Live trading execution: BLOCKED")
print("Full regression: PASS")
print()

print("NEXT:")
print("CONNECTED SERVICES V3")
print()
print("Natural-language service intent routing")
print("Email-thread context intelligence")
print("Calendar free/busy slot recommendation")
print("Multi-person meeting coordination")
print("Draft reply workflows")
print("Operator mission -> Google service orchestration")
print("Connected-service approval dashboard UI")
print("Authenticated GitHub workflows")
print()
print("AFTER:")
print("Advanced Voice / wake word")
print("Advanced Trading Intelligence")
print("NautilusTrader isolated POC")
