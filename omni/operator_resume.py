from __future__ import annotations


from omni.computer_operator_v2 import (
    computer_operator_v2,
)


class OperatorResumeManager:

    def prepare(
        self,
        goal,
        revised_proposal_text,
    ):

        validation = (
            computer_operator_v2
            .validate_replan(
                goal,
                revised_proposal_text,
            )
        )


        plan = validation[
            "plan"
        ]


        prepared = (
            computer_operator_v2
            .prepare(
                plan
            )
        )


        return {
            "success":
                True,

            "valid":
                True,

            "plan":
                plan,

            "approval_batch":
                prepared.get(
                    "approval_batch"
                ),

            "auto_execute":
                False,

            "requires_new_approval":
                validation[
                    "requires_new_approval"
                ],
        }


    def resume(
        self,
        plan,
        *,
        approval_batch_id=None,
        project_id=None,
    ):

        return (
            computer_operator_v2
            .execute(
                plan,

                approval_batch_id=
                    approval_batch_id,

                project_id=
                    project_id,
            )
        )


operator_resume_manager = (
    OperatorResumeManager()
)
