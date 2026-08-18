"""Dependency-aware durable orchestrator with bounded worker scheduling."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
import threading

from .audit import AuditStore
from .contracts import Plan, Step, StepResult, StepStatus


Executor = Callable[[Step], StepResult]


class DurableOrchestrator:
    def __init__(
        self,
        store: AuditStore,
        executor: Executor,
        max_workers: int = 1,
    ):
        if max_workers < 1 or max_workers > 32:
            raise ValueError("max_workers must be between 1 and 32.")
        self.store = store
        self.executor = executor
        self.max_workers = max_workers
        self._tokens: dict[str, threading.Event] = {}
        self._lock = threading.RLock()

    def cancel(self, plan: Plan) -> None:
        with self._lock:
            plan.cancelled = True
            token = self._tokens.get(plan.id)
            if token:
                token.set()
            for step in plan.steps:
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.CANCELLED
        self.store.save_plan(plan)
        self.store.record_event(
            "orchestrator", "plan_cancelled", "CANCELLED", {}, plan.id
        )

    def resume(self, plan_id: str) -> Plan:
        plan = self.store.load_plan(plan_id)
        if plan is None:
            raise KeyError(f"Unknown plan '{plan_id}'.")
        if plan.cancelled:
            return plan

        recovered = 0
        for step in plan.steps:
            if step.status == StepStatus.RUNNING:
                if step.attempts < step.max_attempts:
                    step.status = StepStatus.PENDING
                    step.error = "Recovered after interrupted execution."
                else:
                    step.status = StepStatus.FAILED
                    step.error = "Interrupted after exhausting maximum attempts."
                self.store.save_step(plan.id, step)
                recovered += 1
        self.store.record_event(
            "orchestrator",
            "plan_recovered",
            "RECOVERED",
            {"recovered_steps": recovered},
            plan.id,
        )
        return self.run(plan, resumed=True)

    def run(self, plan: Plan, resumed: bool = False) -> Plan:
        plan.validate()
        token = threading.Event()
        with self._lock:
            self._tokens[plan.id] = token
        self.store.save_plan(plan)
        self.store.record_event(
            "orchestrator",
            "plan_resumed" if resumed else "plan_started",
            "RUNNING",
            {"max_workers": self.max_workers},
            plan.id,
        )

        try:
            while not plan.cancelled and not token.is_set():
                progress = False
                by_id = {step.id: step for step in plan.steps}
                ready: list[Step] = []

                for step in plan.steps:
                    if step.status != StepStatus.PENDING:
                        continue
                    dependencies = [by_id[item] for item in step.depends_on]
                    if any(
                        item.status
                        in {StepStatus.FAILED, StepStatus.BLOCKED, StepStatus.CANCELLED}
                        for item in dependencies
                    ):
                        step.status = StepStatus.BLOCKED
                        self.store.save_step(plan.id, step)
                        progress = True
                        continue
                    if all(
                        item.status == StepStatus.SUCCEEDED for item in dependencies
                    ):
                        ready.append(step)

                if ready:
                    progress = True
                    batch = ready[: self.max_workers]
                    with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                        futures = [
                            pool.submit(self._run_step, plan, step, token)
                            for step in batch
                        ]
                        wait(futures)

                if not progress:
                    break
        finally:
            with self._lock:
                self._tokens.pop(plan.id, None)

        if plan.cancelled:
            final_status = "CANCELLED"
        elif all(step.status == StepStatus.SUCCEEDED for step in plan.steps):
            final_status = "SUCCEEDED"
        elif any(step.status == StepStatus.FAILED for step in plan.steps):
            final_status = "FAILED"
        else:
            final_status = "BLOCKED"

        self.store.save_plan(plan)
        self.store.record_event(
            "orchestrator", "plan_finished", final_status, {}, plan.id
        )
        return plan

    def _run_step(
        self, plan: Plan, step: Step, token: threading.Event
    ) -> None:
        result = StepResult(False, error="Step did not execute.")
        while step.attempts < step.max_attempts and not token.is_set():
            step.status = StepStatus.RUNNING
            step.attempts += 1
            self.store.save_step(plan.id, step)
            try:
                result = self.executor(step)
            except Exception as error:
                result = StepResult(False, error=f"{type(error).__name__}: {error}")

            if result.success:
                step.output = result.output
                step.error = None
                step.status = StepStatus.SUCCEEDED
                self.store.save_step(plan.id, step)
                return

            if step.attempts < step.max_attempts:
                step.error = result.error
                step.status = StepStatus.PENDING
                self.store.save_step(plan.id, step)

        if token.is_set() or plan.cancelled:
            step.error = "Cancelled cooperatively."
            step.status = StepStatus.CANCELLED
        else:
            step.error = result.error
            step.status = StepStatus.FAILED
        self.store.save_step(plan.id, step)
