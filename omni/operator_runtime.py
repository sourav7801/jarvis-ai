from __future__ import annotations

from dataclasses import (
    asdict,
)

from pathlib import Path

import hashlib
import json
import time
import uuid


from omni.approval_batch import (
    approval_batches,
)

from omni.browser_observation_loop import (
    browser_observation_loop,
)

from omni.coding_mission import (
    coding_mission,
)

from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.connected_services_v3_gateway import (
    connected_services_v3_gateway,
)

from omni.desktop_state import (
    desktop_state,
)

from omni.desktop_target_executor import (
    desktop_target_executor,
)

from omni.document_intelligence import (
    document_intelligence,
)

from omni.git_actions import (
    git_actions,
)

from omni.github_read import (
    github_read,
)

from omni.goal_verifier import (
    goal_verifier,
)

from omni.live_browser_session import (
    live_browser_sessions,
)

from omni.natural_target import (
    natural_target_resolver,
)

from omni.operator_brain_dsl import (
    _resolve_default_runner,
)

from omni.operator_memory import (
    operator_memory,
)

from omni.operator_runtime_schema import (
    RuntimePlan,
    from_dict,
    is_interactive,
    parse_json,
    planner_prompt,
    validate_plan,
)

from omni.persistent_browser import (
    persistent_browser,
)

from omni.perception_fusion import (
    perception_fusion,
)

from omni.collaboration_runtime import (
    AgentRequest,
)


class UnifiedOperatorRuntime:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "operator_v4"
                / "missions"
            )
        )


    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _path(
        self,
        mission_id,
    ):

        return (
            self.root
            / (
                str(
                    mission_id
                )
                + ".json"
            )
        )


    def _save(
        self,
        mission,
    ):

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        mission[
            "updated_at"
        ] = time.time()


        path = self._path(
            mission[
                "mission_id"
            ]
        )


        temporary = (
            path.with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                mission,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )


        temporary.replace(
            path
        )


        return mission


    def get(
        self,
        mission_id,
    ):

        path = self._path(
            mission_id
        )


        if not path.exists():

            raise KeyError(
                "Unknown V4 mission."
            )


        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )


    # --------------------------------------------------------
    # Brain / Operator Agent planning
    # --------------------------------------------------------

    @staticmethod
    def _extract_text(
        result,
    ):

        if isinstance(
            result,
            str,
        ):

            return result


        if isinstance(
            result,
            dict,
        ):

            for key in (
                "response",
                "text",
                "output",
                "content",
                "message",
            ):

                value = result.get(
                    key
                )


                if (
                    isinstance(
                        value,
                        str,
                    )
                    and value.strip()
                ):

                    return value


                if isinstance(
                    value,
                    dict,
                ):

                    content = value.get(
                        "content"
                    )


                    if (
                        isinstance(
                            content,
                            str,
                        )
                        and content.strip()
                    ):

                        return content


        for key in (
            "response",
            "text",
            "output",
            "content",
            "message",
        ):

            value = getattr(
                result,
                key,
                None,
            )


            if (
                isinstance(
                    value,
                    str,
                )
                and value.strip()
            ):

                return value


        return str(
            result
        )


    def plan_goal(
        self,
        goal,
        *,
        observations=None,
        runner=None,
    ):

        prompt = planner_prompt(
            goal,
            observations,
        )


        if runner is None:

            runner = (
                _resolve_default_runner()
            )


        request = AgentRequest(
            agent=
                "operator",

            text=
                prompt,

            required_capabilities=
                frozenset(),

            correlation_id=
                (
                    "operator-v4-plan-"
                    + uuid.uuid4()
                    .hex[:16]
                ),
        )


        result = runner(
            request
        )


        raw = (
            self._extract_text(
                result
            )
            .strip()
        )


        try:

            plan = parse_json(
                goal,
                raw,

                source=
                    "operator-agent-v4",
            )


            return {
                "success":
                    True,

                "valid":
                    True,

                "plan":
                    plan,

                "raw":
                    raw[:30000],

                "auto_execute":
                    False,
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "valid":
                    False,

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),

                "raw":
                    raw[:30000],

                "auto_execute":
                    False,
            }


    # --------------------------------------------------------
    # Mission creation
    # --------------------------------------------------------

    def create(
        self,
        plan,
    ):

        validate_plan(
            plan
        )


        mission_id = (
            "operator-v4-"
            + uuid.uuid4()
            .hex[:16]
        )


        mission = {
            "mission_id":
                mission_id,

            "goal":
                plan.goal,

            "plan":
                {
                    "schema_version":
                        plan.schema_version,

                    "source":
                        plan.source,

                    "steps": [
                        asdict(
                            step
                        )

                        for step
                        in plan.steps
                    ],
                },

            "status":
                "ready",

            "cursor":
                0,

            "results":
                {},

            "prepared":
                {},

            "approval_batches":
                {},

            "verified_steps":
                0,

            "verification_steps":
                0,

            "verified":
                False,

            "failure":
                None,

            "replan":
                None,

            "created_at":
                time.time(),

            "updated_at":
                time.time(),
        }


        self._save(
            mission
        )


        return mission


    def create_from_dict(
        self,
        goal,
        data,
        *,
        source="structured",
    ):

        return self.create(
            from_dict(
                goal,
                data,
                source=source,
            )
        )


    # --------------------------------------------------------
    # Reference resolution
    # --------------------------------------------------------

    @staticmethod
    def _result_output(
        mission,
        step_id,
    ):

        record = (
            mission.get(
                "results",
                {}
            )
            .get(
                str(
                    step_id
                )
            )
        )


        if not isinstance(
            record,
            dict,
        ):

            return None


        return record.get(
            "output"
        )


    def _session_id(
        self,
        mission,
        payload,
    ):

        direct = payload.get(
            "session_id"
        )


        if direct:

            return str(
                direct
            )


        reference = payload.get(
            "session_ref"
        )


        output = self._result_output(
            mission,
            reference,
        )


        if not isinstance(
            output,
            dict,
        ):

            raise ValueError(
                "Browser session_ref has "
                "no completed output."
            )


        session_id = output.get(
            "session_id"
        )


        if not session_id:

            raise ValueError(
                "Referenced step did not "
                "produce session_id."
            )


        return str(
            session_id
        )


    def _worktree(
        self,
        mission,
        payload,
    ):

        direct = payload.get(
            "worktree"
        )


        if direct:

            return str(
                direct
            )


        reference = payload.get(
            "worktree_ref"
        )


        output = self._result_output(
            mission,
            reference,
        )


        if not isinstance(
            output,
            dict,
        ):

            raise ValueError(
                "worktree_ref has no "
                "completed output."
            )


        path = output.get(
            "worktree"
        )


        if not path:

            raise ValueError(
                "Referenced step did not "
                "produce worktree."
            )


        return str(
            path
        )


    # --------------------------------------------------------
    # Approval binding preparation
    # --------------------------------------------------------

    def _prepare_interactive(
        self,
        mission,
        step,
    ):

        payload = step[
            "payload"
        ]

        action = step[
            "action"
        ]


        if (
            action
            == "desktop.natural_click"
        ):

            prepared = (
                desktop_target_executor
                .prepare_click(
                    payload[
                        "window_title"
                    ],

                    payload[
                        "target"
                    ],

                    screenshot=
                        payload.get(
                            "screenshot"
                        ),
                )
            )


        elif (
            action
            == "desktop.natural_set_text"
        ):

            prepared = (
                desktop_target_executor
                .prepare_set_text(
                    payload[
                        "window_title"
                    ],

                    payload[
                        "target"
                    ],

                    payload[
                        "value"
                    ],

                    sensitive=
                        bool(
                            payload.get(
                                "sensitive",
                                False,
                            )
                        ),
                )
            )


        elif (
            action
            == "browser.start"
        ):

            url = (
                persistent_browser
                ._validate_url(
                    payload[
                        "url"
                    ]
                )
            )


            profile = (
                persistent_browser
                ._profile_name(
                    payload.get(
                        "profile",
                        "operator-v4",
                    )
                )
            )


            prepared = {
                "success":
                    True,

                "binding": {
                    "action":
                        "live_browser.session.start",

                    "payload": {
                        "url":
                            url,

                        "profile":
                            profile,

                        "operation":
                            "session.start",

                        "headless":
                            bool(
                                payload.get(
                                    "headless",
                                    True,
                                )
                            ),
                    },

                    "display": {
                        "url":
                            url,

                        "profile":
                            profile,

                        "operation":
                            "session.start",

                        "headless":
                            bool(
                                payload.get(
                                    "headless",
                                    True,
                                )
                            ),
                    },

                    "risk":
                        "browser-live-action",
                },
            }


        elif (
            action
            == "browser.natural_click"
        ):

            session_id = self._session_id(
                mission,
                payload,
            )


            resolution = (
                natural_target_resolver
                .browser(
                    session_id,

                    payload[
                        "target"
                    ],
                )
            )


            if not resolution.get(
                "success",
                False,
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Browser target was not "
                            "uniquely resolved."
                        ),

                    "resolution":
                        resolution,
                }


            target_handle = (
                resolution[
                    "target_handle"
                ]
            )


            prepared = {
                "success":
                    True,

                "session_id":
                    session_id,

                "target_handle":
                    target_handle,

                "resolution":
                    resolution,

                "binding": {
                    "action":
                        "live_browser.click",

                    "payload": {
                        "session_id":
                            session_id,

                        "operation":
                            "click",

                        "target":
                            target_handle,
                    },

                    "display": {
                        "session_id":
                            session_id,

                        "operation":
                            "click",

                        "target":
                            target_handle,
                    },

                    "risk":
                        "browser-live-action",
                },
            }


        elif (
            action
            == "browser.natural_fill"
        ):

            if bool(
                payload.get(
                    "sensitive",
                    False,
                )
            ):

                return {
                    "success":
                        False,

                    "error":
                        "Sensitive browser fill blocked.",
                }


            session_id = self._session_id(
                mission,
                payload,
            )


            resolution = (
                natural_target_resolver
                .browser(
                    session_id,

                    payload[
                        "target"
                    ],
                )
            )


            if not resolution.get(
                "success",
                False,
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Browser fill target was not "
                            "uniquely resolved."
                        ),

                    "resolution":
                        resolution,
                }


            target_handle = (
                resolution[
                    "target_handle"
                ]
            )


            value = str(
                payload[
                    "value"
                ]
            )


            prepared = {
                "success":
                    True,

                "session_id":
                    session_id,

                "target_handle":
                    target_handle,

                "resolution":
                    resolution,

                "binding": {
                    "action":
                        "live_browser.fill",

                    "payload": {
                        "session_id":
                            session_id,

                        "operation":
                            "fill",

                        "target":
                            target_handle,

                        "value_hash":
                            hashlib.sha256(
                                value.encode(
                                    "utf-8"
                                )
                            ).hexdigest(),

                        "length":
                            len(
                                value
                            ),
                    },

                    "display": {
                        "session_id":
                            session_id,

                        "operation":
                            "fill",

                        "target":
                            target_handle,

                        "preview":
                            value[:80],
                    },

                    "risk":
                        "browser-live-action",
                },
            }


        elif action in (
            "google.gmail.create_draft",
            "google.gmail.send_draft",
            "google.calendar.create_event",
            "google.calendar.update_event",
            "google.calendar.delete_event",

            "google.gmail.draft_to_contact",

            "google.calendar.schedule_meeting",
            "google.calendar.schedule_from_email",

            "google.gmail.reply_draft",

            "github.issue.create",
            "github.comment.create",
            "github.pull.create",
        ):

            prepared = (
                connected_services_v3_gateway
                .prepare(
                    action,
                    payload,
                )
            )


        elif (
            action
            == "coding.create_worktree"
        ):

            prepared = (
                coding_mission
                .prepare_create(
                    payload[
                        "repo"
                    ],

                    payload[
                        "name"
                    ],
                )
            )


        elif (
            action
            == "coding.test_worktree"
        ):

            worktree = self._worktree(
                mission,
                payload,
            )


            prepared = (
                coding_mission
                .prepare_tests(
                    worktree,

                    payload.get(
                        "test_args"
                    ),
                )
            )


            prepared[
                "worktree"
            ] = worktree


        else:

            return {
                "success":
                    False,

                "error":
                    (
                        "No interactive preparation "
                        "for "
                        + action
                    ),
            }


        return prepared


    # --------------------------------------------------------
    # Execute one prepared/noninteractive step
    # --------------------------------------------------------

    def _execute_step(
        self,
        mission,
        step,
        prepared=None,
        approval_id=None,
    ):

        action = step[
            "action"
        ]

        payload = step[
            "payload"
        ]


        if (
            action
            == "desktop.observe"
        ):

            snapshot = (
                desktop_state
                .snapshot(
                    window_title=
                        payload.get(
                            "window_title"
                        ),

                    include_controls=
                        bool(
                            payload.get(
                                "include_controls",
                                False,
                            )
                        ),
                )
            )


            return {
                "success":
                    True,

                "snapshot": {
                    "timestamp":
                        snapshot.timestamp,

                    "window_titles":
                        snapshot.window_titles,

                    "controls":
                        snapshot.controls,

                    "fingerprint":
                        snapshot.fingerprint,
                },
            }


        if (
            action
            == "desktop.natural_click"
        ):

            return (
                desktop_target_executor
                .execute_click(
                    prepared,
                    approval_id,
                )
            )


        if (
            action
            == "desktop.natural_set_text"
        ):

            return (
                desktop_target_executor
                .execute_set_text(
                    prepared,

                    payload[
                        "value"
                    ],

                    approval_id,
                )
            )


        if (
            action
            == "browser.start"
        ):

            binding = prepared[
                "binding"
            ][
                "payload"
            ]


            return (
                live_browser_sessions
                .start(
                    binding[
                        "url"
                    ],

                    profile=
                        binding[
                            "profile"
                        ],

                    approval_id=
                        approval_id,

                    headless=
                        binding[
                            "headless"
                        ],
                )
            )


        if (
            action
            == "browser.observe"
        ):

            session_id = self._session_id(
                mission,
                payload,
            )


            return (
                live_browser_sessions
                .observe(
                    session_id
                )
            )


        if (
            action
            == "browser.natural_click"
        ):

            return (
                live_browser_sessions
                .click(
                    prepared[
                        "session_id"
                    ],

                    prepared[
                        "target_handle"
                    ],

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "browser.natural_fill"
        ):

            return (
                live_browser_sessions
                .fill(
                    prepared[
                        "session_id"
                    ],

                    prepared[
                        "target_handle"
                    ],

                    payload[
                        "value"
                    ],

                    approval_id=
                        approval_id,

                    sensitive=
                        False,
                )
            )


        if (
            action
            == "browser.close"
        ):

            session_id = self._session_id(
                mission,
                payload,
            )


            return (
                live_browser_sessions
                .close(
                    session_id
                )
            )


        if (
            action
            == "vision.analyze"
        ):

            return (
                perception_fusion
                .analyze_existing(
                    payload[
                        "path"
                    ],

                    window_title=
                        payload.get(
                            "window_title"
                        ),

                    target=
                        payload.get(
                            "target"
                        ),
                )
            )


        if (
            action
            == "document.read"
        ):

            return {
                "success":
                    True,

                "document":
                    document_intelligence
                    .read(
                        payload[
                            "path"
                        ]
                    ),
            }


        if (
            action
            == "document.search"
        ):

            return {
                "success":
                    True,

                "search":
                    document_intelligence
                    .search(
                        payload[
                            "path"
                        ],

                        payload[
                            "query"
                        ],
                    ),
            }


        if (
            action
            == "git.status"
        ):

            result = git_actions.status(
                payload[
                    "repo"
                ]
            )


            return {
                "success":
                    bool(
                        result.get(
                            "success",
                            False,
                        )
                    ),

                "git":
                    result,
            }


        if (
            action
            == "git.diff"
        ):

            result = git_actions.diff(
                payload[
                    "repo"
                ]
            )


            return {
                "success":
                    bool(
                        result.get(
                            "success",
                            False,
                        )
                    ),

                "git":
                    result,
            }


        if (
            action
            == "git.repository_state"
        ):

            return {
                "success":
                    True,

                "repository":
                    github_read
                    .repository_state(
                        payload[
                            "repo"
                        ]
                    ),
            }


        if action.startswith(
            (
                "google.",
                "github.",
            )
        ):

            return (
                connected_services_v3_gateway
                .execute(
                    action,
                    payload,

                    approval_id=
                        approval_id,
                )
            )


        if (
            action
            == "coding.create_worktree"
        ):

            return (
                coding_mission
                .create(
                    payload[
                        "repo"
                    ],

                    payload[
                        "name"
                    ],

                    approval_id,
                )
            )


        if (
            action
            == "coding.test_worktree"
        ):

            return (
                coding_mission
                .run_tests(
                    prepared[
                        "worktree"
                    ],

                    prepared[
                        "test_args"
                    ],

                    approval_id,
                )
            )


        if (
            action
            == "coding.diff_worktree"
        ):

            worktree = self._worktree(
                mission,
                payload,
            )


            result = (
                coding_mission
                .diff(
                    worktree
                )
            )


            return {
                "success":
                    bool(
                        result.get(
                            "success",
                            False,
                        )
                    ),

                "git":
                    result,
            }


        return {
            "success":
                False,

            "error":
                (
                    "No unified runtime executor "
                    "for "
                    + action
                ),
        }


    # --------------------------------------------------------
    # Failure / replan proposal
    # --------------------------------------------------------

    def _failure(
        self,
        mission,
        step,
        error,
        output=None,
    ):

        observations = {
            "failed_step":
                step,

            "error":
                error,

            "output":
                output,

            "completed_results":
                mission.get(
                    "results",
                    {}
                ),
        }


        proposal = None


        try:

            proposal = self.plan_goal(
                (
                    "Revise the remaining workflow "
                    "for this original goal: "
                    + mission[
                        "goal"
                    ]
                ),

                observations=
                    observations,
            )


        except Exception as exc:

            proposal = {
                "success":
                    False,

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),

                "auto_execute":
                    False,
            }


        mission[
            "status"
        ] = "needs_replan"


        mission[
            "failure"
        ] = {
            "step_id":
                step[
                    "step_id"
                ],

            "action":
                step[
                    "action"
                ],

            "error":
                error,
        }


        mission[
            "replan"
        ] = proposal


        self._save(
            mission
        )


        operator_memory.record(
            goal=
                mission[
                    "goal"
                ],

            success=
                False,

            steps=
                len(
                    mission[
                        "plan"
                    ][
                        "steps"
                    ]
                ),

            failed_step=
                step[
                    "step_id"
                ],

            lesson=
                error,

            metadata={
                "mission_id":
                    mission[
                        "mission_id"
                    ],

                "runtime":
                    "operator-v4",
            },
        )


        return mission


    # --------------------------------------------------------
    # Advance mission until approval/failure/completion
    # --------------------------------------------------------

    def advance(
        self,
        mission_id,
    ):

        mission = self.get(
            mission_id
        )


        if mission[
            "status"
        ] in (
            "completed",
            "needs_replan",
            "failed",
        ):

            return mission


        steps = mission[
            "plan"
        ][
            "steps"
        ]


        mission[
            "status"
        ] = "running"


        while (
            mission[
                "cursor"
            ]
            < len(
                steps
            )
        ):

            index = mission[
                "cursor"
            ]


            step = steps[
                index
            ]


            step_id = step[
                "step_id"
            ]


            prepared = (
                mission[
                    "prepared"
                ].get(
                    step_id
                )
            )


            approval_id = None


            if is_interactive(
                step[
                    "action"
                ]
            ):

                batch_id = (
                    mission[
                        "approval_batches"
                    ].get(
                        step_id
                    )
                )


                if batch_id:

                    approval_id = (
                        approval_batches
                        .token_for_step(
                            batch_id,
                            step_id,
                        )
                    )


                    if not approval_id:

                        mission[
                            "status"
                        ] = "waiting_approval"


                        self._save(
                            mission
                        )


                        return mission


                else:

                    try:

                        prepared = (
                            self._prepare_interactive(
                                mission,
                                step,
                            )
                        )

                    except Exception as exc:

                        return self._failure(
                            mission,
                            step,

                            (
                                type(
                                    exc
                                ).__name__
                                + ": "
                                + str(
                                    exc
                                )
                            ),
                        )


                    if not prepared.get(
                        "success",
                        False,
                    ):

                        return self._failure(
                            mission,
                            step,

                            str(
                                prepared.get(
                                    "error",
                                    "Interactive preparation failed.",
                                )
                            ),

                            prepared,
                        )


                    mission[
                        "prepared"
                    ][
                        step_id
                    ] = prepared


                    binding = dict(
                        prepared[
                            "binding"
                        ]
                    )


                    batch = (
                        approval_batches
                        .create(
                            mission[
                                "goal"
                            ],

                            (
                                {
                                    "step_id":
                                        step_id,

                                    **binding,
                                },
                            ),
                        )
                    )


                    mission[
                        "approval_batches"
                    ][
                        step_id
                    ] = batch[
                        "batch_id"
                    ]


                    mission[
                        "status"
                    ] = "waiting_approval"


                    self._save(
                        mission
                    )


                    return mission


            attempts = 0

            success = False

            output = None

            error = None


            while (
                attempts
                <= int(
                    step.get(
                        "retries",
                        0,
                    )
                )
            ):

                attempts += 1


                try:

                    output = self._execute_step(
                        mission,
                        step,

                        prepared=
                            prepared,

                        approval_id=
                            approval_id,
                    )


                    success = (
                        bool(
                            output.get(
                                "success",
                                False,
                            )
                        )

                        if isinstance(
                            output,
                            dict,
                        )

                        else bool(
                            output
                        )
                    )


                    error = (
                        output.get(
                            "error"
                        )

                        if isinstance(
                            output,
                            dict,
                        )

                        else None
                    )


                except Exception as exc:

                    success = False

                    error = (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    )


                if success:

                    break


                # Interactive approvals are one-time.
                if is_interactive(
                    step[
                        "action"
                    ]
                ):

                    break


                if (
                    attempts
                    <= int(
                        step.get(
                            "retries",
                            0,
                        )
                    )
                ):

                    time.sleep(
                        min(
                            0.25
                            * attempts,
                            0.5,
                        )
                    )


            verification = (
                goal_verifier
                .verify(
                    step.get(
                        "verify",
                        {}
                    ),

                    output,
                )
            )


            if verification[
                "required"
            ]:

                mission[
                    "verification_steps"
                ] += 1


                if verification[
                    "passed"
                ]:

                    mission[
                        "verified_steps"
                    ] += 1


                else:

                    success = False

                    error = (
                        "Deterministic verification failed: "
                        + json.dumps(
                            verification,
                            ensure_ascii=False,
                            default=str,
                        )
                    )


            mission[
                "results"
            ][
                step_id
            ] = {
                "step_id":
                    step_id,

                "action":
                    step[
                        "action"
                    ],

                "success":
                    success,

                "attempts":
                    attempts,

                "output":
                    output,

                "verification":
                    verification,

                "error":
                    error,
            }


            self._save(
                mission
            )


            if not success:

                return self._failure(
                    mission,
                    step,

                    str(
                        error
                        or "Step execution failed."
                    ),

                    output,
                )


            mission[
                "cursor"
            ] += 1


            mission[
                "prepared"
            ].pop(
                step_id,
                None,
            )


            self._save(
                mission
            )


        mission[
            "status"
        ] = "completed"


        verification_steps = int(
            mission[
                "verification_steps"
            ]
        )


        mission[
            "verified"
        ] = bool(
            verification_steps > 0

            and mission[
                "verified_steps"
            ]
            == verification_steps
        )


        mission[
            "verification_coverage"
        ] = (
            verification_steps
            / len(
                steps
            )

            if steps

            else 0.0
        )


        self._save(
            mission
        )


        operator_memory.record(
            goal=
                mission[
                    "goal"
                ],

            success=
                True,

            steps=
                len(
                    steps
                ),

            metadata={
                "mission_id":
                    mission[
                        "mission_id"
                    ],

                "runtime":
                    "operator-v4",

                "verified":
                    mission[
                        "verified"
                    ],

                "verification_coverage":
                    mission[
                        "verification_coverage"
                    ],
            },
        )


        return mission


    # --------------------------------------------------------
    # Explicit replan application
    # --------------------------------------------------------

    def apply_replan(
        self,
        mission_id,
        revised_plan,
    ):

        mission = self.get(
            mission_id
        )


        if (
            mission[
                "status"
            ]
            != "needs_replan"
        ):

            raise RuntimeError(
                "Mission is not awaiting replan."
            )


        validate_plan(
            revised_plan
        )


        if (
            revised_plan.goal
            != mission[
                "goal"
            ]
        ):

            raise ValueError(
                "Revised plan goal must match "
                "original mission goal."
            )


        completed_steps = (
            mission[
                "cursor"
            ]
        )


        mission[
            "plan"
        ] = {
            "schema_version":
                revised_plan.schema_version,

            "source":
                revised_plan.source,

            "steps": [
                asdict(
                    step
                )

                for step
                in revised_plan.steps
            ],
        }


        mission[
            "cursor"
        ] = 0


        mission[
            "results"
        ] = {}


        mission[
            "prepared"
        ] = {}


        mission[
            "approval_batches"
        ] = {}


        mission[
            "verified_steps"
        ] = 0


        mission[
            "verification_steps"
        ] = 0


        mission[
            "verified"
        ] = False


        mission[
            "status"
        ] = "ready"


        mission[
            "failure"
        ] = None


        mission[
            "replan"
        ] = None


        mission[
            "previous_completed_steps"
        ] = completed_steps


        self._save(
            mission
        )


        # Explicit caller action applied the plan.
        # It still does not execute automatically.
        return mission


    def apply_replan_json(
        self,
        mission_id,
        proposal_text,
    ):

        mission = self.get(
            mission_id
        )


        plan = parse_json(
            mission[
                "goal"
            ],

            proposal_text,

            source=
                "explicit-v4-replan",
        )


        return self.apply_replan(
            mission_id,
            plan,
        )


unified_operator_runtime = (
    UnifiedOperatorRuntime()
)
