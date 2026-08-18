from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

import hashlib
import json
from pathlib import Path
import threading
import time


TRUST = {
    "government": 0.98,
    "official_documentation": 0.96,
    "primary_research": 0.95,
    "user_provided": 0.92,
    "vendor_api": 0.90,
    "official_repository": 0.88,
    "repository": 0.82,
    "secondary": 0.70,
    "community": 0.60,
    "unknown": 0.50,
}


@dataclass(frozen=True)
class SourceEvidence:

    source_id: str
    subject: str
    uri: str
    title: str
    source_type: str
    trust_score: float
    verified: bool
    metadata: dict
    captured_at: float


def source_trust_score(
    source_type,
):

    return float(
        TRUST.get(
            str(
                source_type
                or "unknown"
            ),
            TRUST["unknown"],
        )
    )


class ProvenanceStore:

    def __init__(
        self,
        path,
    ):
        self.path = Path(path)
        self._lock = threading.RLock()


    @staticmethod
    def source_id(
        subject,
        uri,
    ):

        payload = (
            str(subject).strip().lower()
            + "\n"
            + str(uri).strip()
        )

        return (
            "source-"
            + hashlib.sha256(
                payload.encode(
                    "utf-8"
                )
            ).hexdigest()[:20]
        )


    def all(self):

        if not self.path.exists():
            return ()

        result = []

        for line in (
            self.path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        ):

            if not line.strip():
                continue

            try:
                item = json.loads(
                    line
                )

                result.append(
                    SourceEvidence(
                        source_id=
                            item["source_id"],

                        subject=
                            item["subject"],

                        uri=
                            item["uri"],

                        title=
                            item.get(
                                "title",
                                "",
                            ),

                        source_type=
                            item.get(
                                "source_type",
                                "unknown",
                            ),

                        trust_score=
                            float(
                                item.get(
                                    "trust_score",
                                    0.5,
                                )
                            ),

                        verified=
                            bool(
                                item.get(
                                    "verified",
                                    False,
                                )
                            ),

                        metadata=
                            dict(
                                item.get(
                                    "metadata",
                                    {},
                                )
                            ),

                        captured_at=
                            float(
                                item.get(
                                    "captured_at",
                                    0,
                                )
                            ),
                    )
                )

            except Exception:
                continue

        return tuple(result)


    def add(
        self,
        *,
        subject,
        uri,
        title="",
        source_type="unknown",
        verified=False,
        metadata=None,
        trust_score=None,
    ):

        subject = str(
            subject
        ).strip()

        uri = str(
            uri
        ).strip()

        if not subject:
            raise ValueError(
                "subject cannot be empty"
            )

        if not uri:
            raise ValueError(
                "source URI cannot be empty"
            )

        if trust_score is None:
            trust_score = (
                source_trust_score(
                    source_type
                )
            )

        evidence = SourceEvidence(
            source_id=
                self.source_id(
                    subject,
                    uri,
                ),

            subject=subject,

            uri=uri[:4000],

            title=
                str(title)[:1000],

            source_type=
                str(source_type),

            trust_score=max(
                0.0,
                min(
                    float(trust_score),
                    1.0,
                ),
            ),

            verified=
                bool(verified),

            metadata=
                dict(
                    metadata
                    or {}
                ),

            captured_at=
                time.time(),
        )

        records = {
            item.source_id:
                item
            for item in self.all()
        }

        records[
            evidence.source_id
        ] = evidence

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = self.path.with_suffix(
            ".tmp"
        )

        payload = "\n".join(
            json.dumps(
                asdict(item),
                ensure_ascii=False,
                default=str,
            )
            for item
            in records.values()
        )

        if payload:
            payload += "\n"

        with self._lock:

            temp.write_text(
                payload,
                encoding="utf-8",
            )

            temp.replace(
                self.path
            )

        return evidence


    def for_subject(
        self,
        subject,
    ):

        query = str(
            subject
        ).strip().lower()

        return tuple(
            item
            for item in self.all()
            if (
                item.subject
                .strip()
                .lower()
                == query
            )
        )


    def confidence(
        self,
        subject,
    ):

        evidence = (
            self.for_subject(
                subject
            )
        )

        if not evidence:
            return 0.0

        values = []

        for item in evidence:

            values.append(
                item.trust_score
                * (
                    1.0
                    if item.verified
                    else 0.75
                )
            )

        return round(
            min(
                1.0,
                sum(values)
                / len(values),
            ),
            4,
        )
