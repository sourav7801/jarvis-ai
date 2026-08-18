from __future__ import annotations


from omni.meta_brain import (
    meta_brain,
)


class ActionReplanner:

    def __init__(
        self,
        brain=None,
    ):

        self.brain = (
            brain
            or meta_brain
        )


    @staticmethod
    def _agents(
        plan,
    ):

        value = getattr(
            plan,
            "agents",
            (),
        )


        if callable(
            value
        ):

            value = value()


        return tuple(
            value
            or ()
        )


    def propose(
        self,
        original_goal,
        observed_result,
    ):

        if bool(
            getattr(
                observed_result,
                "success",
                False,
            )
        ):

            return {
                "needs_replan":
                    False,

                "auto_execute":
                    False,
            }


        failed_step = getattr(
            observed_result,
            "failed_step",
            None,
        )


        steps = tuple(
            getattr(
                observed_result,
                "steps",
                (),
            )
            or ()
        )


        failure_details = []


        for step in steps:

            if getattr(
                step,
                "success",
                False,
            ):

                continue


            failure_details.append(
                {
                    "step_id":
                        getattr(
                            step,
                            "step_id",
                            "",
                        ),

                    "error":
                        getattr(
                            step,
                            "error",
                            "",
                        ),

                    "attempts":
                        getattr(
                            step,
                            "attempts",
                            0,
                        ),
                }
            )


        request = (
            "Recover a failed JARVIS real-world workflow.\n"
            "Original goal: "
            + str(
                original_goal
            )
            + "\nFailed step: "
            + str(
                failed_step
            )
            + "\nFailures: "
            + str(
                failure_details
            )
            + "\n"
            "Create a safer alternative plan. "
            "Do not execute actions. "
            "Preserve approval requirements."
        )


        plan = (
            self.brain
            .plan(
                request
            )
        )


        lead = getattr(
            plan,
            "lead_agent",
            None,
        )


        return {
            "needs_replan":
                True,

            "failed_step":
                failed_step,

            "lead_agent":
                lead,

            "agents":
                self._agents(
                    plan
                ),

            "requires_approval":
                bool(
                    getattr(
                        plan,
                        "requires_approval",
                        False,
                    )
                ),

            "auto_execute":
                False,

            "plan":
                plan,
        }


action_replanner = (
    ActionReplanner()
)
