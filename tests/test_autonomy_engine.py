import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import main
from workstation import app

from omni.autonomy_engine import (
    AutonomousGoalEngine,
)

from omni.mission import (
    MissionStatus,
    MissionStore,
)


class Step:

    def __init__(
        self,
        agent,
        role,
        capabilities=(),
    ):

        self.agent = agent
        self.role = role
        self.capabilities = capabilities


class Delegation:

    intent = "coding"

    lead_agent = "coding"

    confidence = 0.99

    requires_approval = False

    steps = (
        Step(
            "engineering",
            "support",
        ),
        Step(
            "security",
            "support",
        ),
        Step(
            "coding",
            "lead",
        ),
    )


class MethodBrain:

    def agent_names(
        self,
    ):

        return (
            "engineering",
            "security",
            "coding",
            "quality",
            "operator",
        )

    def plan(
        self,
        goal,
    ):

        return Delegation()


class PropertyBrain:

    agent_names = (
        "engineering",
        "security",
        "coding",
        "quality",
        "operator",
    )

    def plan(
        self,
        goal,
    ):

        return Delegation()


class ApprovalDelegation(
    Delegation
):

    requires_approval = True


class ApprovalBrain(
    MethodBrain
):

    def plan(
        self,
        goal,
    ):

        return ApprovalDelegation()


class AutonomyTests(
    unittest.TestCase
):

    def make_engine(
        self,
        brain=None,
    ):

        temp = (
            tempfile.TemporaryDirectory()
        )

        self.addCleanup(
            temp.cleanup
        )

        return AutonomousGoalEngine(
            brain
            or MethodBrain(),

            max_retries=1,

            store=MissionStore(
                Path(temp.name)
            ),
        )


    def test_method_agent_names_supported(self):

        engine = self.make_engine(
            MethodBrain()
        )

        self.assertIn(
            "quality",
            engine.agent_names(),
        )


    def test_property_agent_names_supported(self):

        engine = self.make_engine(
            PropertyBrain()
        )

        self.assertIn(
            "quality",
            engine.agent_names(),
        )


    def test_dag(self):

        engine = (
            self.make_engine()
        )

        plan = engine.plan(
            "Build secure API"
        )

        lead = next(
            x
            for x in plan.tasks
            if x.role == "lead"
        )

        supports = [
            x
            for x in plan.tasks
            if x.role == "support"
        ]

        self.assertEqual(
            set(
                lead.dependencies
            ),
            {
                x.task_id
                for x in supports
            },
        )


    def test_verifier_added(self):

        engine = (
            self.make_engine()
        )

        plan = engine.plan(
            "Build API"
        )

        self.assertTrue(
            any(
                x.agent == "quality"
                and x.role
                == "verifier"
                for x in plan.tasks
            )
        )


    def test_success(self):

        engine = (
            self.make_engine()
        )

        def runner(
            agent,
            prompt,
            context,
        ):

            if agent == "coding":

                return "Final result"

            if agent == "quality":

                return "Verified"

            return (
                agent
                + " finding"
            )

        with patch(
            "omni.autonomy_engine."
            "remember_scoped",
        ):

            result = engine.execute(
                "Build API",
                runner=runner,
            )

        self.assertTrue(
            result.success
        )

        self.assertTrue(
            result.verified
        )


    def test_support_failure_survives(self):

        engine = (
            self.make_engine()
        )

        def runner(
            agent,
            prompt,
            context,
        ):

            if agent == "security":

                raise RuntimeError(
                    "offline"
                )

            if agent == "coding":

                return "Final"

            return "OK"

        with patch(
            "omni.autonomy_engine."
            "remember_scoped",
        ):

            result = engine.execute(
                "Build API",
                runner=runner,
            )

        self.assertTrue(
            result.success
        )

        self.assertTrue(
            result.errors
        )


    def test_lead_failure_recovers(self):

        engine = (
            self.make_engine()
        )

        def runner(
            agent,
            prompt,
            context,
        ):

            if agent == "coding":

                raise RuntimeError(
                    "lead failed"
                )

            if agent == "operator":

                return (
                    "Recovered result"
                )

            return "OK"

        with patch(
            "omni.autonomy_engine."
            "remember_scoped",
        ):

            result = engine.execute(
                "Build API",
                runner=runner,
            )

        self.assertTrue(
            result.success
        )

        self.assertEqual(
            result.recovery_count,
            1,
        )

        self.assertEqual(
            result.final_answer,
            "Recovered result",
        )


    def test_approval_blocks(self):

        engine = self.make_engine(
            ApprovalBrain()
        )

        calls = []

        def runner(*args):

            calls.append(
                args
            )

            return "bad"

        result = engine.execute(
            "Sensitive mission",
            runner=runner,
        )

        self.assertEqual(
            result.status,
            MissionStatus.BLOCKED,
        )

        self.assertEqual(
            calls,
            [],
        )


    def test_store(self):

        engine = (
            self.make_engine()
        )

        def runner(
            agent,
            prompt,
            context,
        ):

            return "OK"

        with patch(
            "omni.autonomy_engine."
            "remember_scoped",
        ):

            result = engine.execute(
                "Build API",
                runner=runner,
            )

        self.assertTrue(
            engine.store.exists(
                result.mission_id
            )
        )


    def test_memory(self):

        engine = (
            self.make_engine()
        )

        def runner(
            agent,
            prompt,
            context,
        ):

            return "OK"

        with patch(
            "omni.autonomy_engine."
            "remember_scoped",
        ) as remember:

            result = engine.execute(
                "Build API",
                runner=runner,
            )

        self.assertTrue(
            result.success
        )

        remember.assert_called_once()


    def test_main_entries(self):

        self.assertTrue(
            callable(
                main.jarvis_run_mission
            )
        )

        self.assertTrue(
            callable(
                main.jarvis_plan_mission
            )
        )


    def test_workstation_entries(self):

        self.assertTrue(
            callable(
                app.jarvis_mission_payload
            )
        )

        self.assertTrue(
            callable(
                app.jarvis_mission_plan_payload
            )
        )


if __name__ == "__main__":
    unittest.main()
