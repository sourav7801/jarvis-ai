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
