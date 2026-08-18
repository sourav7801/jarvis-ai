import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace


import main


from omni.agent_registry import (
    default_agent_specs,
)

from omni.capability_growth import (
    model_role_router,
    SkillExtractor,
)

from omni.core_integrity import (
    verify_protected_core,
    rebaseline_protected_core,
)

from omni.dynamic_specialists import (
    DynamicSpecialistFactory,
)

from omni.knowledge_graph import (
    KnowledgeGraph,
)

from omni.universal_learning import (
    ProvenanceStore,
    UniversalLearningEngine,
)


class FakeMeta:

    def learn(
        self,
        subject,
        runner=None,
        project_id=None,
    ):

        return SimpleNamespace(
            success=True,

            verified=True,

            mission_id=
                "learning-mission",

            final_answer=
                "A" * 3000,
        )


class UniversalLearningV5Tests(
    unittest.TestCase
):


    def test_core_integrity(self):

        status = (
            verify_protected_core()
        )

        self.assertTrue(
            status.ok
        )

        self.assertGreaterEqual(
            status.checked,
            5,
        )


    def test_rebaseline_requires_approval(self):

        with self.assertRaises(
            PermissionError
        ):

            rebaseline_protected_core(
                approved=False,
                reason="test",
            )


    def test_existing_model_router_contract(self):

        from omni.model_router import (
            ModelProfile,
        )

        self.assertIsNotNone(
            ModelProfile
        )


    def test_permanent_agents_stay_29(self):

        self.assertEqual(
            len(
                default_agent_specs()
            ),
            29,
        )


    def test_provenance_confidence(self):

        with tempfile.TemporaryDirectory() as tmp:

            store = ProvenanceStore(
                Path(tmp)
                / "sources.jsonl"
            )

            store.add(
                "AI",
                "official-doc",

                source_type=
                    "official_documentation",

                verified=True,
            )

            store.add(
                "AI",
                "research-paper",

                source_type=
                    "primary_research",

                verified=True,
            )


            self.assertGreater(
                store.confidence(
                    "AI"
                ),
                0.90,
            )


    def test_learning_artifact(self):

        with tempfile.TemporaryDirectory() as tmp:

            root = Path(tmp)


            engine = UniversalLearningEngine(
                root=
                    root
                    / "learning",

                meta_engine=
                    FakeMeta(),

                graph=
                    KnowledgeGraph(
                        root
                        / "graph.json"
                    ),

                provenance=
                    ProvenanceStore(
                        root
                        / "sources.jsonl"
                    ),
            )


            artifact = engine.learn(
                "Distributed Systems",

                sources=(
                    {
                        "uri":
                            "official-doc",

                        "source_type":
                            "official_documentation",

                        "verified":
                            True,
                    },

                    {
                        "uri":
                            "research-paper",

                        "source_type":
                            "primary_research",

                        "verified":
                            True,
                    },
                ),
            )


            self.assertTrue(
                artifact.verified
            )

            self.assertGreater(
                artifact.comprehension,
                75,
            )


    def test_specialist_governance(self):

        with tempfile.TemporaryDirectory() as tmp:

            factory = (
                DynamicSpecialistFactory(
                    Path(tmp)
                )
            )


            profile = factory.create(
                "Robotics",
                "Robot systems expert",
            )


            calls = []


            def runner(
                agent,
                prompt,
                context,
            ):

                calls.append(
                    agent
                )

                return "OK"


            factory.execute(
                profile[
                    "specialist_id"
                ],

                "Analyze motor control",

                runner,
            )


            self.assertEqual(
                calls,
                ["research"],
            )


    def test_good_specialist_promotion_recommendation(self):

        with tempfile.TemporaryDirectory() as tmp:

            factory = (
                DynamicSpecialistFactory(
                    Path(tmp)
                )
            )


            profile = factory.create(
                "Kubernetes",
                "Kubernetes expert",
            )


            sid = profile[
                "specialist_id"
            ]


            for score in (
                90,
                92,
                95,
            ):

                profile = factory.evaluate(
                    sid,
                    score,
                    True,
                )


            self.assertTrue(
                profile[
                    "promotion_eligible"
                ]
            )


    def test_bad_specialist_retires(self):

        with tempfile.TemporaryDirectory() as tmp:

            factory = (
                DynamicSpecialistFactory(
                    Path(tmp)
                )
            )


            profile = factory.create(
                "Weak domain",
                "Test specialist",
            )


            sid = profile[
                "specialist_id"
            ]


            for _ in range(3):

                profile = factory.evaluate(
                    sid,
                    20,
                    False,
                )


            self.assertEqual(
                profile[
                    "status"
                ],
                "retired",
            )


    def test_model_role_router(self):

        self.assertEqual(
            model_role_router.route(
                "Debug Python application"
            ).role,
            "coding",
        )


        self.assertEqual(
            model_role_router.route(
                "Research latest information"
            ).role,
            "research",
        )


        self.assertEqual(
            model_role_router.route(
                "Analyze architecture"
            ).role,
            "reasoning",
        )


        self.assertEqual(
            model_role_router.route(
                "Private file",
                sensitive=True,
            ).role,
            "local_private",
        )


    def test_skill_proposal(self):

        with tempfile.TemporaryDirectory() as tmp:

            extractor = SkillExtractor(
                Path(tmp)
            )


            mission = SimpleNamespace(
                success=True,

                verified=True,

                mission_id=
                    "mission-1",

                goal=
                    "Secure Python service",

                plan=SimpleNamespace(
                    tasks=(
                        SimpleNamespace(
                            agent="security",
                            role="support",
                            objective="Find risks",
                        ),

                        SimpleNamespace(
                            agent="coding",
                            role="lead",
                            objective="Fix risks",
                        ),
                    )
                ),
            )


            proposal = (
                extractor
                .extract_from_mission(
                    mission,
                    95,
                )
            )


            self.assertIsNotNone(
                proposal
            )

            self.assertFalse(
                proposal[
                    "automatic_promotion"
                ]
            )


    def test_public_api(self):

        self.assertTrue(
            callable(
                main
                .jarvis_verify_protected_core
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_universal_learn
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_create_specialist
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_model_role
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_growth_status
            )
        )


if __name__ == "__main__":
    unittest.main()
