import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from omni.audit import AuditStore
from omni.contracts import Plan, Step, StepResult, StepStatus
from omni.orchestrator import DurableOrchestrator


class PlanValidationTests(unittest.TestCase):
    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            Plan("invalid", [Step("work", depends_on=["missing"])])

    def test_cycle_is_rejected(self):
        first = Step("first", id="first", depends_on=["second"])
        second = Step("second", id="second", depends_on=["first"])
        with self.assertRaises(ValueError):
            Plan("cycle", [first, second])


class DurableOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = AuditStore(Path(self.temporary.name) / "audit.sqlite3")

    def tearDown(self):
        self.temporary.cleanup()

    def test_dependency_order_and_persistence(self):
        calls = []
        first = Step("first", id="first")
        second = Step("second", id="second", depends_on=["first"])
        plan = Plan("ordered", [second, first])

        def execute(step):
            calls.append(step.id)
            return StepResult(True, output=step.id)

        DurableOrchestrator(self.store, execute).run(plan)

        self.assertEqual(calls, ["first", "second"])
        self.assertTrue(
            all(step.status == StepStatus.SUCCEEDED for step in plan.steps)
        )
        names = [event["name"] for event in self.store.recent_events()]
        self.assertIn("plan_started", names)
        self.assertIn("plan_finished", names)

    def test_retry_is_bounded(self):
        attempts = 0
        step = Step("flaky", max_attempts=2)

        def execute(_step):
            nonlocal attempts
            attempts += 1
            return StepResult(attempts == 2, error="temporary")

        plan = DurableOrchestrator(self.store, execute).run(
            Plan("retry", [step])
        )
        self.assertEqual(attempts, 2)
        self.assertEqual(plan.steps[0].status, StepStatus.SUCCEEDED)

    def test_failure_blocks_dependent_step(self):
        first = Step("fail", id="first")
        second = Step("never", id="second", depends_on=["first"])

        plan = DurableOrchestrator(
            self.store, lambda _step: StepResult(False, error="failure")
        ).run(Plan("blocking", [first, second]))

        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)
        self.assertEqual(plan.steps[1].status, StepStatus.BLOCKED)

    def test_interrupted_step_resumes_when_attempt_remains(self):
        step = Step("recover", id="recover", max_attempts=2)
        plan = Plan("resume", [step], id="resume-plan")
        self.store.save_plan(plan)
        step.status = StepStatus.RUNNING
        step.attempts = 1
        self.store.save_step(plan.id, step)

        resumed = DurableOrchestrator(
            self.store, lambda _step: StepResult(True, output="recovered")
        ).resume(plan.id)
        self.assertEqual(resumed.steps[0].status, StepStatus.SUCCEEDED)
        self.assertEqual(resumed.steps[0].attempts, 2)
        self.assertEqual(resumed.steps[0].output, "recovered")

    def test_interrupted_exhausted_step_fails_closed(self):
        step = Step("recover", id="recover", max_attempts=1)
        plan = Plan("resume", [step], id="exhausted-plan")
        self.store.save_plan(plan)
        step.status = StepStatus.RUNNING
        step.attempts = 1
        self.store.save_step(plan.id, step)
        executor = Mock(return_value=StepResult(True))

        resumed = DurableOrchestrator(self.store, executor).resume(plan.id)
        self.assertEqual(resumed.steps[0].status, StepStatus.FAILED)
        executor.assert_not_called()

    def test_parallelism_is_bounded(self):
        active = 0
        maximum_active = 0
        lock = threading.Lock()

        def execute(_step):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return StepResult(True)

        plan = Plan("parallel", [Step(f"step-{index}") for index in range(4)])
        DurableOrchestrator(self.store, execute, max_workers=2).run(plan)
        self.assertEqual(maximum_active, 2)

    def test_cancellation_stops_new_scheduling(self):
        started = threading.Event()
        release = threading.Event()
        first = Step("first", id="first")
        second = Step("second", id="second")
        plan = Plan("cancel", [first, second])

        def execute(_step):
            started.set()
            release.wait(timeout=2)
            return StepResult(True)

        orchestrator = DurableOrchestrator(self.store, execute, max_workers=1)
        worker = threading.Thread(target=orchestrator.run, args=(plan,))
        worker.start()
        self.assertTrue(started.wait(timeout=1))
        orchestrator.cancel(plan)
        release.set()
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertTrue(plan.cancelled)
        self.assertEqual(second.status, StepStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
