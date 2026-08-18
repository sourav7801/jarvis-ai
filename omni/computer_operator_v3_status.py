from __future__ import annotations


from omni.approval_queue import (
    approval_queue,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.live_browser_session import (
    live_browser_sessions,
)

from omni.vision_runtime import (
    vision_runtime,
)


class ComputerOperatorV3Status:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        return {
            "protected_core":
                integrity.ok,

            "vision":
                vision_runtime.status(),

            "live_browser_sessions":
                live_browser_sessions
                .status(),

            "pending_approvals":
                approval_queue.pending(),

            "natural_targeting":
                True,

            "brain_dsl_generation":
                True,

            "brain_dsl_auto_execute":
                False,

            "automatic_replan_execution":
                False,

            "credential_automation":
                False,

            "trading_execution":
                False,
        }


computer_operator_v3_status = (
    ComputerOperatorV3Status()
)
