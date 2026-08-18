import unittest
from dataclasses import dataclass

from omni.collaboration_runtime import (
    GovernedAgentRunner,
)


@dataclass
class FakeResponse:
    success: bool
    result: object = None
    error: str | None = None


class FakeRegistry:

    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)

        return FakeResponse(
            success=True,
            result={
                "agent_result": "OK"
            },
        )


class FailedRegistry:

    def execute(self, request):
        return FakeResponse(
            success=False,
            error="agent failed",
        )


class CollaborationRuntimeTests(
    unittest.TestCase
):

    def test_registry_method_is_detected(self):

        runner = GovernedAgentRunner(
            FakeRegistry()
        )

        self.assertEqual(
            runner.method_name,
            "execute",
        )

    def test_execution_goes_through_registry(self):

        registry = FakeRegistry()

        runner = GovernedAgentRunner(
            registry
        )

        result = runner(
            "chat",
            "Hello Jarvis",
            {"role": "lead"},
        )

        self.assertEqual(
            len(registry.requests),
            1,
        )

        self.assertEqual(
            result,
            {"agent_result": "OK"},
        )

    def test_failed_agent_fails_closed(self):

        runner = GovernedAgentRunner(
            FailedRegistry()
        )

        with self.assertRaises(
            RuntimeError
        ):
            runner(
                "chat",
                "Hello",
                {"role": "lead"},
            )

    def test_capability_is_derived_from_registry_specs(self):

        runner = GovernedAgentRunner(
            FakeRegistry()
        )

        capability = runner._capability_for(
            "trading"
        )

        self.assertEqual(
            capability,
            "trading.research",
        )


if __name__ == "__main__":
    unittest.main()
