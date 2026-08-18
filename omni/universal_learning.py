from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from pathlib import Path

import hashlib
import json
import time
import uuid


from omni.knowledge_graph import (
    KnowledgeGraph,
)

from omni.meta_intelligence import (
    meta_intelligence,
)


SOURCE_TRUST = {
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
class Evidence:

    evidence_id: str

    subject: str

    uri: str

    source_type: str

    trust: float

    verified: bool

    captured_at: float

    metadata: dict


@dataclass(frozen=True)
class LearningArtifact:

    artifact_id: str

    subject: str

    summary: str

    confidence: float

    comprehension: float

    verified: bool

    mission_id: str | None

    evidence_ids: tuple[str, ...]

    status: str

    created_at: float


class ProvenanceStore:

    def __init__(
        self,
        path,
    ):

        self.path = Path(
            path
        )


    @staticmethod
    def _id(
        subject,
        uri,
    ):

        raw = (
            str(subject)
            .strip()
            .lower()
            + "\n"
            + str(uri)
            .strip()
        )

        return (
            "evidence-"
            + hashlib.sha256(
                raw.encode(
                    "utf-8"
                )
            ).hexdigest()[:20]
        )


    def _read(self):

        if not self.path.exists():
            return {}

        result = {}

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

                data = json.loads(
                    line
                )

                item = Evidence(
                    evidence_id=
                        data[
                            "evidence_id"
                        ],

                    subject=
                        data[
                            "subject"
                        ],

                    uri=
                        data[
                            "uri"
                        ],

                    source_type=
                        data[
                            "source_type"
                        ],

                    trust=
                        float(
                            data[
                                "trust"
                            ]
                        ),

                    verified=
                        bool(
                            data[
                                "verified"
                            ]
                        ),

                    captured_at=
                        float(
                            data[
                                "captured_at"
                            ]
                        ),

                    metadata=
                        dict(
                            data.get(
                                "metadata",
                                {},
                            )
                        ),
                )

                result[
                    item.evidence_id
                ] = item

            except Exception:
                continue

        return result


    def add(
        self,
        subject,
        uri,
        *,
        source_type="unknown",
        verified=False,
        metadata=None,
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

        source_type = str(
            source_type
            or "unknown"
        )

        item = Evidence(
            evidence_id=
                self._id(
                    subject,
                    uri,
                ),

            subject=
                subject,

            uri=
                uri[:4000],

            source_type=
                source_type,

            trust=
                SOURCE_TRUST.get(
                    source_type,
                    SOURCE_TRUST[
                        "unknown"
                    ],
                ),

            verified=
                bool(verified),

            captured_at=
                time.time(),

            metadata=
                dict(
                    metadata
                    or {}
                ),
        )


        records = self._read()

        records[
            item.evidence_id
        ] = item


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = self.path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            "".join(
                json.dumps(
                    asdict(record),
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"

                for record
                in records.values()
            ),
            encoding="utf-8",
        )

        temp.replace(
            self.path
        )

        return item


    def for_subject(
        self,
        subject,
    ):

        query = str(
            subject
        ).strip().lower()

        return tuple(
            item

            for item
            in self._read().values()

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

        evidence = self.for_subject(
            subject
        )

        if not evidence:
            return 0.0


        values = [
            item.trust
            * (
                1.0
                if item.verified
                else 0.75
            )

            for item
            in evidence
        ]


        diversity = len(
            {
                item.source_type
                for item
                in evidence
            }
        )

        diversity_bonus = min(
            0.08,
            max(
                0,
                diversity - 1
            )
            * 0.02,
        )


        return round(
            min(
                1.0,

                (
                    sum(values)
                    / len(values)
                )
                + diversity_bonus,
            ),
            4,
        )


class UniversalLearningEngine:

    def __init__(
        self,
        root=None,
        *,
        meta_engine=None,
        graph=None,
        provenance=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "learning"
            )
        )

        self.meta = (
            meta_engine
            or meta_intelligence
        )

        self.graph = (
            graph
            or KnowledgeGraph(
                Path("data")
                / "knowledge"
                / "world_model.json"
            )
        )

        self.provenance = (
            provenance
            or ProvenanceStore(
                self.root
                / "provenance.jsonl"
            )
        )


    @staticmethod
    def comprehension_score(
        summary,
        confidence,
        evidence_count,
        verified,
    ):

        # This measures evidence/completeness quality.
        # It does NOT claim objective truth.

        summary_component = min(
            25.0,

            len(
                str(
                    summary
                    or ""
                )
            )
            / 1800
            * 25.0,
        )

        source_component = (
            float(
                confidence
            )
            * 40.0
        )

        evidence_component = min(
            20.0,

            int(
                evidence_count
            )
            * 5.0,
        )

        verification_component = (
            15.0
            if verified
            else 0.0
        )


        return round(
            min(
                100.0,

                summary_component
                + source_component
                + evidence_component
                + verification_component,
            ),
            2,
        )


    def _artifact_path(
        self,
        artifact_id,
    ):

        return (
            self.root
            / "artifacts"
            / (
                artifact_id
                + ".json"
            )
        )


    def _save(
        self,
        artifact,
    ):

        path = self._artifact_path(
            artifact.artifact_id
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                asdict(
                    artifact
                ),
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temp.replace(
            path
        )


    def _world_model(
        self,
        artifact,
    ):

        topic = (
            "topic:"
            + artifact.subject
            .lower()
            .replace(
                " ",
                "-"
            )[:100]
        )


        self.graph.upsert_node(
            topic,

            kind=
                "learned_topic",

            label=
                artifact.subject,

            attributes={
                "artifact_id":
                    artifact.artifact_id,

                "confidence":
                    artifact.confidence,

                "comprehension":
                    artifact.comprehension,

                "verified":
                    artifact.verified,

                "learning_status":
                    artifact.status,
            },
        )


        for evidence_id in (
            artifact.evidence_ids
        ):

            self.graph.upsert_node(
                evidence_id,

                kind="evidence",

                label=
                    evidence_id,
            )

            self.graph.link(
                topic,
                "supported_by",
                evidence_id,
            )


    def _remember(
        self,
        artifact,
        project_id=None,
    ):

        if (
            artifact.comprehension
            < 60
        ):
            return


        try:

            from omni.memory_context import (
                remember_scoped,
            )

            from omni.memory_scope import (
                MemoryScope,
            )


            scope = (
                MemoryScope.PROJECT
                if project_id
                else MemoryScope.AGENT_FINDING
            )


            remember_scoped(
                (
                    "Learned knowledge\n"
                    "Subject: "
                    + artifact.subject
                    + "\nConfidence: "
                    + str(
                        artifact.confidence
                    )
                    + "\nComprehension: "
                    + str(
                        artifact.comprehension
                    )
                    + "\n"
                    + artifact.summary[
                        :6500
                    ]
                ),

                scope,

                source="jarvis",

                project_id=
                    project_id,

                tags=(
                    "universal-learning",
                    "knowledge",
                ),

                metadata={
                    "artifact_id":
                        artifact.artifact_id,

                    "confidence":
                        artifact.confidence,

                    "comprehension":
                        artifact.comprehension,
                },
            )

        except Exception:
            pass


    def ingest(
        self,
        subject,
        content,
        source_uri,
        *,
        source_type=
            "user_provided",
        verified=False,
        project_id=None,
    ):

        subject = str(
            subject
        ).strip()

        content = str(
            content
        ).strip()


        if not subject:
            raise ValueError(
                "subject cannot be empty"
            )

        if not content:
            raise ValueError(
                "content cannot be empty"
            )


        evidence = (
            self.provenance.add(
                subject,
                source_uri,

                source_type=
                    source_type,

                verified=
                    verified,
            )
        )


        confidence = (
            self.provenance
            .confidence(
                subject
            )
        )


        comprehension = (
            self.comprehension_score(
                content,

                confidence,

                len(
                    self.provenance
                    .for_subject(
                        subject
                    )
                ),

                verified,
            )
        )


        artifact = LearningArtifact(
            artifact_id=(
                "learn-"
                + uuid.uuid4()
                .hex[:16]
            ),

            subject=
                subject,

            summary=
                content[:20000],

            confidence=
                confidence,

            comprehension=
                comprehension,

            verified=
                bool(verified),

            mission_id=
                None,

            evidence_ids=(
                evidence.evidence_id,
            ),

            status=(
                "mastered"
                if (
                    verified
                    and comprehension
                    >= 80
                )
                else (
                    "learned"
                    if comprehension
                    >= 60
                    else "partial"
                )
            ),

            created_at=
                time.time(),
        )


        self._save(
            artifact
        )

        self._world_model(
            artifact
        )

        self._remember(
            artifact,
            project_id,
        )

        return artifact


    def learn(
        self,
        subject,
        *,
        sources=(),
        runner=None,
        project_id=None,
    ):

        subject = str(
            subject
        ).strip()

        if not subject:
            raise ValueError(
                "subject cannot be empty"
            )


        evidence_ids = []


        for source in sources:

            if not isinstance(
                source,
                dict,
            ):
                continue


            uri = str(
                source.get(
                    "uri",
                    "",
                )
            ).strip()


            if not uri:
                continue


            evidence = (
                self.provenance.add(
                    subject,
                    uri,

                    source_type=
                        source.get(
                            "source_type",
                            "unknown",
                        ),

                    verified=
                        bool(
                            source.get(
                                "verified",
                                False,
                            )
                        ),

                    metadata=
                        source.get(
                            "metadata",
                            {},
                        ),
                )
            )


            evidence_ids.append(
                evidence.evidence_id
            )


        mission = (
            self.meta.learn(
                subject,

                runner=
                    runner,

                project_id=
                    project_id,
            )
        )


        summary = str(
            getattr(
                mission,
                "final_answer",
                "",
            )
            or ""
        )


        verified = bool(
            getattr(
                mission,
                "verified",
                False,
            )
        )


        confidence = (
            self.provenance
            .confidence(
                subject
            )
        )


        comprehension = (
            self.comprehension_score(
                summary,

                confidence,

                len(
                    self.provenance
                    .for_subject(
                        subject
                    )
                ),

                verified,
            )
        )


        artifact = LearningArtifact(
            artifact_id=(
                "learn-"
                + uuid.uuid4()
                .hex[:16]
            ),

            subject=
                subject,

            summary=
                summary[:20000],

            confidence=
                confidence,

            comprehension=
                comprehension,

            verified=
                verified,

            mission_id=
                getattr(
                    mission,
                    "mission_id",
                    None,
                ),

            evidence_ids=
                tuple(
                    evidence_ids
                ),

            status=(
                "mastered"
                if (
                    verified
                    and comprehension
                    >= 80
                )
                else (
                    "learned"
                    if comprehension
                    >= 60
                    else "partial"
                )
            ),

            created_at=
                time.time(),
        )


        self._save(
            artifact
        )

        self._world_model(
            artifact
        )

        self._remember(
            artifact,
            project_id,
        )


        return artifact


    def artifacts(self):

        folder = (
            self.root
            / "artifacts"
        )

        if not folder.exists():
            return ()


        output = []

        for path in folder.glob(
            "*.json"
        ):

            try:

                output.append(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:
                continue


        return tuple(
            output
        )


universal_learning = (
    UniversalLearningEngine()
)
