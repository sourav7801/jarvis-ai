from __future__ import annotations

from pathlib import Path

from omni.capability_scorecard import (
    CapabilityScorecard,
)

from omni.experience_learning import (
    ExperienceStore,
)

from omni.improvement_lab import (
    CandidatePatchLab,
)

from omni.meta_intelligence import (
    meta_intelligence,
)


class SelfImprovementLab:

    def __init__(
        self,
        project_root=None,
    ):

        if project_root is None:

            project_root = (
                Path(__file__)
                .resolve()
                .parents[1]
            )

        self.project_root = Path(
            project_root
        )

        root = (
            self.project_root
            / "data"
            / "self_improvement"
        )

        self.scorecard = (
            CapabilityScorecard(
                root
                / "capability_scorecard.json"
            )
        )

        self.experience = (
            ExperienceStore(
                root
                / "experience.jsonl"
            )
        )

        self.candidates = (
            CandidatePatchLab(
                self.project_root,

                root
                / "candidates",
            )
        )


    def record_score(
        self,
        capability,
        score,
        *,
        evidence,
        source="benchmark",
    ):

        return self.scorecard.record(
            capability,
            score,
            evidence=evidence,
            source=source,
        )


    def weaknesses(
        self,
        *,
        threshold=75,
    ):

        return (
            self.scorecard
            .weaknesses(
                threshold=threshold
            )
        )


    def improvement_hypotheses(
        self,
        *,
        threshold=75,
        target=90,
    ):

        results = []

        for weakness in (
            self.weaknesses(
                threshold=threshold
            )
        ):

            proposal = (
                meta_intelligence
                .propose_improvement(
                    weakness[
                        "capability"
                    ],

                    weakness[
                        "score"
                    ],

                    target,
                )
            )

            results.append(
                proposal
            )

        return tuple(
            results
        )


    def create_candidate(
        self,
        **kwargs,
    ):

        return (
            self.candidates
            .create_candidate(
                **kwargs
            )
        )


    def evaluate_candidate(
        self,
        candidate_id,
        *,
        test_args=None,
    ):

        return (
            self.candidates
            .evaluate(
                candidate_id,
                test_args=test_args,
            )
        )


    def promote_candidate(
        self,
        candidate_id,
        *,
        approved=False,
        post_test_args=None,
    ):

        return (
            self.candidates
            .promote(
                candidate_id,
                approved=approved,
                post_test_args=
                    post_test_args,
            )
        )


    def rollback_candidate(
        self,
        candidate_id,
    ):

        return (
            self.candidates
            .rollback(
                candidate_id
            )
        )


    def status(self):

        scores = (
            self.scorecard
            .snapshot()
        )

        experiences = (
            self.experience
            .recent(
                limit=1000
            )
        )

        return {
            "capability_scores":
                scores,

            "capability_count":
                len(scores),

            "experience_count":
                len(experiences),

            "weaknesses":
                self.weaknesses(),

            "automatic_self_modification":
                False,

            "automatic_promotion":
                False,

            "sandbox_required":
                True,

            "security_review_required":
                True,

            "approval_required":
                True,

            "automatic_rollback_on_regression":
                True,
        }


self_improvement_lab = (
    SelfImprovementLab()
)
