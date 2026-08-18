from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

SCHEMA = ROOT / "omni" / "operator_runtime_schema.py"
DESKTOP = ROOT / "omni" / "desktop_target_executor.py"
VERIFIER = ROOT / "omni" / "goal_verifier.py"
CODING = ROOT / "omni" / "coding_mission.py"
DASHBOARD = ROOT / "omni" / "operator_dashboard.py"
RUNTIME = ROOT / "omni" / "operator_runtime.py"

TEST = ROOT / "tests" / "test_computer_operator_v4.py"

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "computer_operator_v4"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    MAIN,
    APP,
    SCHEMA,
    DESKTOP,
    VERIFIER,
    CODING,
    DASHBOARD,
    RUNTIME,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(
    path,
):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
    )


for path in FILES:

    BACKUPS[path] = (
        path.exists()
    )

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in (
        BACKUPS.items()
    ):

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        if existed:

            shutil.copy2(
                backup,
                path,
            )

        else:

            path.unlink(
                missing_ok=True
            )

    print(
        "JARVIS source restored."
    )


print("=" * 80)
print("JARVIS COMPUTER OPERATOR V4")
print("UNIFIED AUTONOMOUS WORKFLOW RUNTIME")
print("=" * 80)


# ============================================================
# 0. VERIFY 407 CHECKPOINT
# ============================================================

print()
print("Checking 407-test checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.vision_runtime import vision_runtime; "
        "assert vision_runtime.status()['vision_ready']; "
        "from omni.live_browser_session import live_browser_sessions; "
        "from omni.natural_target import natural_target_resolver; "
        "from omni.operator_brain_dsl import _resolve_default_runner; "
        "assert callable(_resolve_default_runner()); "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V3: PASS'); "
        "print('Qwen3-VL vision: PASS'); "
        "print('Governed runner: PASS')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT
            / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(
        PROTECTED
    ),
)

print(
    "Baseline: PASS"
)


# ============================================================
# 1. UNIFIED V4 WORKFLOW SCHEMA
# ============================================================

write(
    SCHEMA,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

import json
import re


ALLOWED_ACTIONS = {

    # Desktop
    "desktop.observe",
    "desktop.natural_click",
    "desktop.natural_set_text",

    # Persistent browser
    "browser.start",
    "browser.observe",
    "browser.natural_click",
    "browser.natural_fill",
    "browser.close",

    # Vision / documents
    "vision.analyze",
    "document.read",
    "document.search",

    # Git intelligence
    "git.status",
    "git.diff",
    "git.repository_state",

    # Isolated engineering
    "coding.create_worktree",
    "coding.test_worktree",
    "coding.diff_worktree",
}


INTERACTIVE_ACTIONS = {
    "desktop.natural_click",
    "desktop.natural_set_text",

    "browser.start",
    "browser.natural_click",
    "browser.natural_fill",

    "coding.create_worktree",
    "coding.test_worktree",
}


BLOCKED_PREFIXES = (
    "shell.",
    "cmd.",
    "powershell.",
    "process.",
    "terminal.",
    "credential.",
    "password.",
    "trade.",
    "trading.",
    "broker.",
    "order.",
    "git.push",
    "git.merge",
)


SECRET_FIELDS = {
    "password",
    "passwd",
    "credential",
    "credentials",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
}


PAYLOAD_FIELDS = {

    "desktop.observe": {
        "window_title",
        "include_controls",
    },

    "desktop.natural_click": {
        "window_title",
        "target",
        "screenshot",
    },

    "desktop.natural_set_text": {
        "window_title",
        "target",
        "value",
        "sensitive",
    },

    "browser.start": {
        "url",
        "profile",
        "headless",
    },

    "browser.observe": {
        "session_id",
        "session_ref",
    },

    "browser.natural_click": {
        "session_id",
        "session_ref",
        "target",
    },

    "browser.natural_fill": {
        "session_id",
        "session_ref",
        "target",
        "value",
        "sensitive",
    },

    "browser.close": {
        "session_id",
        "session_ref",
    },

    "vision.analyze": {
        "path",
        "window_title",
        "target",
    },

    "document.read": {
        "path",
    },

    "document.search": {
        "path",
        "query",
    },

    "git.status": {
        "repo",
    },

    "git.diff": {
        "repo",
    },

    "git.repository_state": {
        "repo",
    },

    "coding.create_worktree": {
        "repo",
        "name",
    },

    "coding.test_worktree": {
        "worktree",
        "worktree_ref",
        "test_args",
    },

    "coding.diff_worktree": {
        "worktree",
        "worktree_ref",
    },
}


VERIFY_FIELDS = {
    "contains",
    "url_contains",
    "title_contains",
    "changed",
    "window_open",
    "file_exists",
    "min_elements",
}


@dataclass(frozen=True)
class RuntimeStep:

    step_id: str

    action: str

    payload: dict = field(
        default_factory=dict
    )

    verify: dict = field(
        default_factory=dict
    )

    retries: int = 0


@dataclass(frozen=True)
class RuntimePlan:

    goal: str

    steps: tuple[
        RuntimeStep,
        ...
    ]

    source: str = "operator-v4"

    schema_version: int = 1


def is_interactive(
    action,
):

    return (
        str(
            action
        )
        in INTERACTIVE_ACTIONS
    )


def _scan_secrets(
    value,
    path="payload",
):

    if isinstance(
        value,
        dict,
    ):

        for key, child in (
            value.items()
        ):

            key_lower = str(
                key
            ).lower()


            if (
                key_lower
                in SECRET_FIELDS
            ):

                raise PermissionError(
                    "Credential-bearing field "
                    "blocked: "
                    + path
                    + "."
                    + str(
                        key
                    )
                )


            _scan_secrets(
                child,
                path
                + "."
                + str(
                    key
                ),
            )


    elif isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):

        for index, child in enumerate(
            value
        ):

            _scan_secrets(
                child,
                (
                    path
                    + "["
                    + str(
                        index
                    )
                    + "]"
                ),
            )


def validate_plan(
    plan,
):

    if not isinstance(
        plan,
        RuntimePlan,
    ):

        raise TypeError(
            "Expected RuntimePlan."
        )


    if not str(
        plan.goal
    ).strip():

        raise ValueError(
            "Workflow goal cannot be empty."
        )


    if (
        plan.schema_version
        != 1
    ):

        raise ValueError(
            "Unsupported V4 schema."
        )


    if len(
        plan.steps
    ) > 30:

        raise ValueError(
            "V4 workflow cannot exceed "
            "30 steps."
        )


    seen = set()


    for step in plan.steps:

        if not isinstance(
            step,
            RuntimeStep,
        ):

            raise TypeError(
                "Invalid RuntimeStep."
            )


        if step.step_id in seen:

            raise ValueError(
                "Duplicate workflow step ID: "
                + step.step_id
            )


        seen.add(
            step.step_id
        )


        action = str(
            step.action
        )


        if action.startswith(
            BLOCKED_PREFIXES
        ):

            raise PermissionError(
                "Blocked V4 action: "
                + action
            )


        if action not in (
            ALLOWED_ACTIONS
        ):

            raise PermissionError(
                "Unknown V4 action: "
                + action
            )


        if not isinstance(
            step.payload,
            dict,
        ):

            raise TypeError(
                "Payload must be a dict."
            )


        unexpected = (
            set(
                step.payload
            )
            - PAYLOAD_FIELDS[
                action
            ]
        )


        if unexpected:

            raise PermissionError(
                "Unexpected payload field(s) "
                "for "
                + action
                + ": "
                + ", ".join(
                    sorted(
                        unexpected
                    )
                )
            )


        if not isinstance(
            step.verify,
            dict,
        ):

            raise TypeError(
                "Verification specification "
                "must be a dict."
            )


        unknown_verify = (
            set(
                step.verify
            )
            - VERIFY_FIELDS
        )


        if unknown_verify:

            raise PermissionError(
                "Unknown verification field(s): "
                + ", ".join(
                    sorted(
                        unknown_verify
                    )
                )
            )


        _scan_secrets(
            step.payload
        )


        if not (
            0
            <= step.retries
            <= 2
        ):

            raise ValueError(
                "Retries must be 0-2."
            )


        if action in (
            "desktop.natural_set_text",
            "browser.natural_fill",
        ):

            if bool(
                step.payload.get(
                    "sensitive",
                    False,
                )
            ):

                raise PermissionError(
                    "Sensitive text automation "
                    "is blocked."
                )


            target = str(
                step.payload.get(
                    "target",
                    ""
                )
            ).lower()


            if (
                "password"
                in target

                or "passwd"
                in target

                or "credential"
                in target
            ):

                raise PermissionError(
                    "Credential/password target "
                    "is blocked."
                )


        if action.startswith(
            "browser."
        ):

            if action != "browser.start":

                if not (
                    step.payload.get(
                        "session_id"
                    )
                    or step.payload.get(
                        "session_ref"
                    )
                ):

                    raise ValueError(
                        action
                        + " requires session_id "
                        "or session_ref."
                    )


        if action.startswith(
            "coding."
        ):

            if (
                action
                != "coding.create_worktree"

                and not (
                    step.payload.get(
                        "worktree"
                    )
                    or step.payload.get(
                        "worktree_ref"
                    )
                )
            ):

                raise ValueError(
                    action
                    + " requires worktree "
                    "or worktree_ref."
                )


    return True


def from_dict(
    goal,
    data,
    *,
    source="model-proposal",
):

    if not isinstance(
        data,
        dict,
    ):

        raise TypeError(
            "V4 DSL must be a JSON object."
        )


    raw_steps = data.get(
        "steps",
        ()
    )


    if not isinstance(
        raw_steps,
        (
            list,
            tuple,
        ),
    ):

        raise TypeError(
            "steps must be an array."
        )


    steps = []


    for index, item in enumerate(
        raw_steps,
        1,
    ):

        if not isinstance(
            item,
            dict,
        ):

            raise TypeError(
                "Each workflow step "
                "must be an object."
            )


        steps.append(
            RuntimeStep(
                step_id=str(
                    item.get(
                        "step_id",
                        (
                            "step-"
                            + str(
                                index
                            )
                        ),
                    )
                ),

                action=str(
                    item[
                        "action"
                    ]
                ),

                payload=dict(
                    item.get(
                        "payload",
                        {}
                    )
                ),

                verify=dict(
                    item.get(
                        "verify",
                        {}
                    )
                ),

                retries=int(
                    item.get(
                        "retries",
                        0,
                    )
                ),
            )
        )


    plan = RuntimePlan(
        goal=str(
            goal
        ),

        steps=tuple(
            steps
        ),

        source=str(
            source
        ),

        schema_version=int(
            data.get(
                "schema_version",
                1,
            )
        ),
    )


    validate_plan(
        plan
    )


    return plan


def parse_json(
    goal,
    text,
    *,
    source="operator-agent",
):

    text = str(
        text
    ).strip()


    if text.startswith(
        "```"
    ):

        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )


    return from_dict(
        goal,

        json.loads(
            text
        ),

        source=source,
    )


def planner_prompt(
    goal,
    observations=None,
):

    observations = (
        observations
        if observations is not None
        else {}
    )


    schema = {
        "schema_version":
            1,

        "steps": [
            {
                "step_id":
                    "step-1",

                "action":
                    "desktop.observe",

                "payload":
                    {},

                "verify":
                    {},

                "retries":
                    0,
            }
        ],
    }


    return (
        "Return JSON only.\n"
        "You are proposing a bounded JARVIS "
        "Computer Operator V4 workflow.\n"
        "You do NOT authorize execution.\n"
        "Do not include credentials, passwords, "
        "tokens, arbitrary shell/process execution, "
        "Git push/merge, broker actions, or trading "
        "execution.\n"
        "Use session_ref to reference a previous "
        "browser.start step.\n"
        "Use worktree_ref to reference a previous "
        "coding.create_worktree step.\n"
        "Use verify when a deterministic success "
        "condition is available.\n\n"
        "Allowed actions:\n"
        + "\n".join(
            " - "
            + action

            for action
            in sorted(
                ALLOWED_ACTIONS
            )
        )
        + "\n\nExample schema:\n"
        + json.dumps(
            schema,
            indent=2,
        )
        + "\n\nGoal:\n"
        + str(
            goal
        )
        + "\n\nObservations:\n"
        + json.dumps(
            observations,
            ensure_ascii=False,
            default=str,
        )
    )
'''
)


# ============================================================
# 2. DESKTOP NATURAL-TARGET EXECUTION
# ============================================================

write(
    DESKTOP,
    r'''
from __future__ import annotations

from pathlib import Path

import ctypes
import hashlib
import math
import time


from PIL import (
    Image,
)


from omni.approval_queue import (
    approval_queue,
)

from omni.computer_operator import (
    ComputerOperator,
)

from omni.natural_target import (
    natural_target_resolver,
)

from omni.operator_schema import (
    OperatorStep,
)

from omni.perception_fusion import (
    perception_fusion,
)

from omni.semantic_ui import (
    semantic_ui,
)


class DesktopTargetExecutor:

    VISUAL_MIN_CONFIDENCE = 0.90

    VISUAL_APPROVAL_TTL = 120


    @staticmethod
    def _screen_size(
        self=None,
    ):

        user32 = ctypes.windll.user32

        return (
            int(
                user32.GetSystemMetrics(
                    0
                )
            ),

            int(
                user32.GetSystemMetrics(
                    1
                )
            ),
        )


    @staticmethod
    def _file_sha(
        path,
    ):

        return hashlib.sha256(
            Path(
                path
            ).read_bytes()
        ).hexdigest()


    def _visual_candidate(
        self,
        screenshot,
        window_title,
        target,
    ):

        path = Path(
            screenshot
        ).resolve()


        if not path.exists():

            return {
                "success":
                    False,

                "error":
                    "Screenshot does not exist.",
            }


        result = (
            perception_fusion
            .analyze_existing(
                path,

                window_title=
                    window_title,

                target=
                    target,
            )
        )


        resolution = result.get(
            "target_resolution"
        )


        if (
            resolution is None
            or not resolution.resolved
            or resolution.best is None
        ):

            return {
                "success":
                    False,

                "error":
                    "Visual target not resolved.",
            }


        if (
            resolution.best.source
            != "vision"
        ):

            return {
                "success":
                    False,

                "error":
                    "Best fallback target was not vision.",
            }


        item = (
            resolution.best.payload
        )


        try:

            x = float(
                item[
                    "x"
                ]
            )

            y = float(
                item[
                    "y"
                ]
            )

            confidence = float(
                item.get(
                    "confidence",
                    0.0,
                )
            )

        except Exception:

            return {
                "success":
                    False,

                "error":
                    "Vision coordinates invalid.",
            }


        if (
            not math.isfinite(
                x
            )
            or not math.isfinite(
                y
            )
        ):

            return {
                "success":
                    False,

                "error":
                    "Vision coordinates non-finite.",
            }


        if (
            confidence
            < self.VISUAL_MIN_CONFIDENCE
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Vision confidence below "
                        "coordinate threshold."
                    ),
            }


        with Image.open(
            path
        ) as image:

            image_width, image_height = (
                image.size
            )


        screen_width, screen_height = (
            self._screen_size()
        )


        # Coordinate execution is only safe when
        # the screenshot corresponds to the full
        # current screen coordinate space.
        if (
            image_width
            != screen_width

            or image_height
            != screen_height
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Vision coordinate execution "
                        "requires a full-screen screenshot "
                        "matching current screen dimensions."
                    ),

                "image_size":
                    (
                        image_width,
                        image_height,
                    ),

                "screen_size":
                    (
                        screen_width,
                        screen_height,
                    ),
            }


        if not (
            0
            <= x
            < screen_width

            and 0
            <= y
            < screen_height
        ):

            return {
                "success":
                    False,

                "error":
                    "Vision coordinate out of bounds.",
            }


        prepared_at = (
            time.time()
        )


        payload = {
            "target":
                str(
                    target
                ),

            "x":
                int(
                    round(
                        x
                    )
                ),

            "y":
                int(
                    round(
                        y
                    )
                ),

            "confidence":
                confidence,

            "screenshot":
                str(
                    path
                ),

            "screenshot_sha256":
                self._file_sha(
                    path
                ),

            "prepared_at":
                prepared_at,
        }


        return {
            "success":
                True,

            "mode":
                "vision-coordinate",

            "resolution":
                resolution,

            "payload":
                payload,

            "binding": {
                "action":
                    "v4.desktop.coordinate_click",

                "payload":
                    payload,

                "display": {
                    "target":
                        str(
                            target
                        ),

                    "x":
                        payload[
                            "x"
                        ],

                    "y":
                        payload[
                            "y"
                        ],

                    "confidence":
                        confidence,

                    "warning":
                        (
                            "Vision-only coordinate "
                            "fallback"
                        ),
                },

                "risk":
                    "visual-coordinate-click",
            },
        }


    def prepare_click(
        self,
        window_title,
        target,
        *,
        screenshot=None,
    ):

        resolution = (
            natural_target_resolver
            .desktop(
                window_title,
                target,
            )
        )


        if resolution.get(
            "success",
            False,
        ):

            handle = resolution[
                "target_handle"
            ]


            step = OperatorStep(
                step_id=
                    "desktop-click",

                action=
                    "ui.click",

                payload={
                    "window_title":
                        handle[
                            "window_title"
                        ],

                    "text":
                        handle.get(
                            "text"
                        ),

                    "control_type":
                        handle.get(
                            "control_type"
                        ),

                    "automation_id":
                        handle.get(
                            "automation_id"
                        ),
                },
            )


            binding = (
                ComputerOperator
                .binding_for_step(
                    step
                )
            )


            return {
                "success":
                    True,

                "mode":
                    "uia",

                "resolution":
                    resolution,

                "handle":
                    handle,

                "binding":
                    binding,
            }


        if screenshot:

            return self._visual_candidate(
                screenshot,
                window_title,
                target,
            )


        return {
            "success":
                False,

            "error":
                (
                    "Desktop target was not "
                    "uniquely resolved."
                ),

            "resolution":
                resolution,
        }


    def prepare_set_text(
        self,
        window_title,
        target,
        value,
        *,
        sensitive=False,
    ):

        if sensitive:

            return {
                "success":
                    False,

                "error":
                    "Sensitive text entry blocked.",
            }


        target_lower = str(
            target
        ).lower()


        if (
            "password"
            in target_lower

            or "passwd"
            in target_lower

            or "credential"
            in target_lower
        ):

            return {
                "success":
                    False,

                "error":
                    "Credential target blocked.",
            }


        resolution = (
            natural_target_resolver
            .desktop(
                window_title,
                target,
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
                        "Text target was not "
                        "uniquely resolved."
                    ),

                "resolution":
                    resolution,
            }


        handle = resolution[
            "target_handle"
        ]


        step = OperatorStep(
            step_id=
                "desktop-set-text",

            action=
                "ui.set_text",

            payload={
                "window_title":
                    handle[
                        "window_title"
                    ],

                "text":
                    handle.get(
                        "text"
                    ),

                "automation_id":
                    handle.get(
                        "automation_id"
                    ),

                "value":
                    str(
                        value
                    ),

                "sensitive":
                    False,
            },
        )


        binding = (
            ComputerOperator
            .binding_for_step(
                step
            )
        )


        return {
            "success":
                True,

            "mode":
                "uia",

            "resolution":
                resolution,

            "handle":
                handle,

            "binding":
                binding,
        }


    @staticmethod
    def _coordinate_click(
        x,
        y,
    ):

        user32 = ctypes.windll.user32


        if not user32.SetCursorPos(
            int(
                x
            ),
            int(
                y
            ),
        ):

            raise RuntimeError(
                "SetCursorPos failed."
            )


        LEFT_DOWN = 0x0002
        LEFT_UP = 0x0004


        user32.mouse_event(
            LEFT_DOWN,
            0,
            0,
            0,
            0,
        )


        user32.mouse_event(
            LEFT_UP,
            0,
            0,
            0,
            0,
        )


    def execute_click(
        self,
        prepared,
        approval_id,
    ):

        if not prepared.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Prepared target is invalid.",
            }


        mode = prepared[
            "mode"
        ]


        if mode == "uia":

            handle = prepared[
                "handle"
            ]


            return semantic_ui.click(
                handle[
                    "window_title"
                ],

                text=
                    handle.get(
                        "text"
                    ),

                control_type=
                    handle.get(
                        "control_type"
                    ),

                automation_id=
                    handle.get(
                        "automation_id"
                    ),

                approval_id=
                    approval_id,
            )


        if (
            mode
            == "vision-coordinate"
        ):

            payload = prepared[
                "payload"
            ]


            if (
                time.time()
                - float(
                    payload[
                        "prepared_at"
                    ]
                )
                > self.VISUAL_APPROVAL_TTL
            ):

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Visual coordinate approval "
                            "expired; capture a new screen."
                        ),
                }


            screenshot = Path(
                payload[
                    "screenshot"
                ]
            )


            if (
                not screenshot.exists()

                or self._file_sha(
                    screenshot
                )
                != payload[
                    "screenshot_sha256"
                ]
            ):

                return {
                    "success":
                        False,

                    "error":
                        "Screenshot changed after approval.",
                }


            binding = prepared[
                "binding"
            ]


            approval_queue.consume(
                approval_id,

                binding[
                    "action"
                ],

                binding[
                    "payload"
                ],
            )


            self._coordinate_click(
                payload[
                    "x"
                ],

                payload[
                    "y"
                ],
            )


            return {
                "success":
                    True,

                "mode":
                    "vision-coordinate",

                "x":
                    payload[
                        "x"
                    ],

                "y":
                    payload[
                        "y"
                    ],
            }


        return {
            "success":
                False,

            "error":
                "Unknown desktop execution mode.",
        }


    def execute_set_text(
        self,
        prepared,
        value,
        approval_id,
    ):

        if not prepared.get(
            "success",
            False,
        ):

            return {
                "success":
                    False,

                "error":
                    "Prepared target is invalid.",
            }


        handle = prepared[
            "handle"
        ]


        return semantic_ui.set_text(
            handle[
                "window_title"
            ],

            str(
                value
            ),

            text=
                handle.get(
                    "text"
                ),

            automation_id=
                handle.get(
                    "automation_id"
                ),

            approval_id=
                approval_id,

            sensitive=
                False,
        )


desktop_target_executor = (
    DesktopTargetExecutor()
)
'''
)


# ============================================================
# 3. DETERMINISTIC GOAL VERIFICATION
# ============================================================

write(
    VERIFIER,
    r'''
from __future__ import annotations

from pathlib import Path

import json


class GoalVerifier:

    @staticmethod
    def _text(
        value,
    ):

        try:

            return json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )

        except Exception:

            return str(
                value
            )


    def verify(
        self,
        specification,
        output,
    ):

        specification = dict(
            specification
            or {}
        )


        if not specification:

            return {
                "required":
                    False,

                "passed":
                    None,

                "checks":
                    (),
            }


        checks = []


        text = self._text(
            output
        )


        if (
            "contains"
            in specification
        ):

            expected = str(
                specification[
                    "contains"
                ]
            )


            passed = (
                expected.lower()
                in text.lower()
            )


            checks.append(
                {
                    "type":
                        "contains",

                    "expected":
                        expected,

                    "passed":
                        passed,
                }
            )


        if (
            "url_contains"
            in specification
        ):

            expected = str(
                specification[
                    "url_contains"
                ]
            ).lower()


            candidate = ""


            if isinstance(
                output,
                dict,
            ):

                candidate = str(
                    output.get(
                        "url",
                        ""
                    )
                )


                after = output.get(
                    "after"
                )


                if isinstance(
                    after,
                    dict,
                ):

                    candidate = str(
                        after.get(
                            "url",
                            candidate,
                        )
                    )


                observation = output.get(
                    "observation"
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    candidate = str(
                        observation.get(
                            "url",
                            candidate,
                        )
                    )


            passed = (
                expected
                in candidate.lower()
            )


            checks.append(
                {
                    "type":
                        "url_contains",

                    "expected":
                        expected,

                    "actual":
                        candidate,

                    "passed":
                        passed,
                }
            )


        if (
            "title_contains"
            in specification
        ):

            expected = str(
                specification[
                    "title_contains"
                ]
            ).lower()


            candidate = ""


            if isinstance(
                output,
                dict,
            ):

                candidate = str(
                    output.get(
                        "title",
                        ""
                    )
                )


                after = output.get(
                    "after"
                )


                if isinstance(
                    after,
                    dict,
                ):

                    candidate = str(
                        after.get(
                            "title",
                            candidate,
                        )
                    )


                observation = output.get(
                    "observation"
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    candidate = str(
                        observation.get(
                            "title",
                            candidate,
                        )
                    )


            passed = (
                expected
                in candidate.lower()
            )


            checks.append(
                {
                    "type":
                        "title_contains",

                    "expected":
                        expected,

                    "actual":
                        candidate,

                    "passed":
                        passed,
                }
            )


        if (
            "changed"
            in specification
        ):

            expected = bool(
                specification[
                    "changed"
                ]
            )


            actual = None


            if isinstance(
                output,
                dict,
            ):

                comparison = output.get(
                    "comparison"
                )


                if isinstance(
                    comparison,
                    dict,
                ):

                    actual = bool(
                        comparison.get(
                            "changed",
                            False,
                        )
                    )


            passed = (
                actual
                is expected
            )


            checks.append(
                {
                    "type":
                        "changed",

                    "expected":
                        expected,

                    "actual":
                        actual,

                    "passed":
                        passed,
                }
            )


        if (
            "window_open"
            in specification
        ):

            expected = str(
                specification[
                    "window_open"
                ]
            ).lower()


            passed = (
                expected
                in text.lower()
            )


            checks.append(
                {
                    "type":
                        "window_open",

                    "expected":
                        expected,

                    "passed":
                        passed,
                }
            )


        if (
            "file_exists"
            in specification
        ):

            expected_path = Path(
                str(
                    specification[
                        "file_exists"
                    ]
                )
            )


            passed = (
                expected_path.exists()
            )


            checks.append(
                {
                    "type":
                        "file_exists",

                    "path":
                        str(
                            expected_path
                        ),

                    "passed":
                        passed,
                }
            )


        if (
            "min_elements"
            in specification
        ):

            minimum = int(
                specification[
                    "min_elements"
                ]
            )


            count = 0


            if isinstance(
                output,
                dict,
            ):

                observation = output.get(
                    "observation",
                    output,
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    count = len(
                        observation.get(
                            "elements",
                            ()
                        )
                        or ()
                    )


            passed = (
                count
                >= minimum
            )


            checks.append(
                {
                    "type":
                        "min_elements",

                    "expected":
                        minimum,

                    "actual":
                        count,

                    "passed":
                        passed,
                }
            )


        return {
            "required":
                True,

            "passed":
                bool(
                    checks
                )
                and all(
                    item[
                        "passed"
                    ]
                    for item
                    in checks
                ),

            "checks":
                tuple(
                    checks
                ),
        }


goal_verifier = (
    GoalVerifier()
)
'''
)

print()
print("PART 1 SAVED")
print("Now paste PART 2.")


# ============================================================
# 4. ISOLATED CODING MISSIONS
# ============================================================

write(
    CODING,
    r'''
from __future__ import annotations

from pathlib import Path


from omni.git_actions import (
    git_actions,
)

from omni.git_worktree_engine import (
    git_worktree_engine,
)


class CodingMission:

    @staticmethod
    def _validate_tests(
        test_args,
    ):

        arguments = tuple(
            str(
                item
            )
            for item
            in (
                test_args
                or (
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-q",
                )
            )
        )


        if len(
            arguments
        ) < 2:

            raise PermissionError(
                "Coding test command rejected."
            )


        if (
            arguments[
                0
            ]
            != "-m"
        ):

            raise PermissionError(
                "Only Python module test runners "
                "are allowed."
            )


        if (
            arguments[
                1
            ]
            not in (
                "unittest",
                "pytest",
            )
        ):

            raise PermissionError(
                "Only unittest/pytest are allowed."
            )


        forbidden = (
            "-c",
            "-i",
            "subprocess",
            "powershell",
            "cmd.exe",
            "shell",
        )


        lower = " ".join(
            arguments
        ).lower()


        if any(
            token
            in lower
            for token
            in forbidden
        ):

            raise PermissionError(
                "Unsafe coding test arguments."
            )


        return arguments


    def prepare_create(
        self,
        repo,
        name,
    ):

        binding = (
            git_worktree_engine
            .create_binding(
                repo,
                name,
            )
        )


        return {
            "success":
                True,

            "binding":
                binding,
        }


    def create(
        self,
        repo,
        name,
        approval_id,
    ):

        return (
            git_worktree_engine
            .create(
                repo,
                name,

                approval_id=
                    approval_id,
            )
        )


    def prepare_tests(
        self,
        worktree,
        test_args=None,
    ):

        arguments = (
            self._validate_tests(
                test_args
            )
        )


        binding = (
            git_worktree_engine
            .test_binding(
                worktree,
                arguments,
            )
        )


        return {
            "success":
                True,

            "test_args":
                arguments,

            "binding":
                binding,
        }


    def run_tests(
        self,
        worktree,
        test_args,
        approval_id,
    ):

        arguments = (
            self._validate_tests(
                test_args
            )
        )


        return (
            git_worktree_engine
            .run_tests(
                worktree,

                arguments,

                approval_id=
                    approval_id,
            )
        )


    @staticmethod
    def diff(
        worktree,
    ):

        return git_actions.diff(
            Path(
                worktree
            ).resolve()
        )


    @staticmethod
    def merge(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Automatic production merge blocked."
        )


    @staticmethod
    def push(
        *args,
        **kwargs,
    ):

        raise PermissionError(
            "Remote Git push blocked."
        )


coding_mission = (
    CodingMission()
)
'''
)


# ============================================================
# 5. APPROVAL + MISSION DASHBOARD
# ============================================================

write(
    DASHBOARD,
    r'''
from __future__ import annotations

from pathlib import Path

import json


from omni.approval_queue import (
    approval_queue,
)


class OperatorDashboard:

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


    @staticmethod
    def _records(
        directory,
    ):

        directory = Path(
            directory
        )


        if not directory.exists():

            return ()


        output = []


        for path in sorted(
            directory.glob(
                "*.json"
            )
        ):

            try:

                output.append(
                    json.loads(
                        path.read_text(
                            encoding="utf-8"
                        )
                    )
                )

            except Exception:

                continue


        return tuple(
            output
        )


    def missions(
        self,
        limit=25,
    ):

        records = list(
            self._records(
                self.root
            )
        )


        records.sort(
            key=lambda item:
                float(
                    item.get(
                        "updated_at",
                        0,
                    )
                ),
            reverse=True,
        )


        return tuple(
            records[
                :max(
                    1,
                    int(
                        limit
                    ),
                )
            ]
        )


    def approval_batches(
        self,
        limit=50,
    ):

        root = (
            Path("data")
            / "approval_batches"
        )


        records = list(
            self._records(
                root
            )
        )


        records.sort(
            key=lambda item:
                float(
                    item.get(
                        "created_at",
                        0,
                    )
                ),
            reverse=True,
        )


        return tuple(
            records[
                :max(
                    1,
                    int(
                        limit
                    ),
                )
            ]
        )


    def pending_batches(
        self,
    ):

        return tuple(
            item

            for item
            in self.approval_batches()

            if (
                item.get(
                    "status"
                )
                == "pending"
            )
        )


    def snapshot(
        self,
    ):

        missions = self.missions(
            20
        )


        return {
            "pending_action_approvals":
                approval_queue.pending(),

            "pending_batches":
                self.pending_batches(),

            "missions":
                missions,

            "running_missions":
                tuple(
                    item

                    for item
                    in missions

                    if item.get(
                        "status"
                    )
                    in (
                        "ready",
                        "running",
                        "waiting_approval",
                        "needs_replan",
                    )
                ),

            "automatic_approval":
                False,

            "automatic_remote_git_write":
                False,

            "automatic_trading":
                False,
        }


operator_dashboard = (
    OperatorDashboard()
)
'''
)


# ============================================================
# 6. UNIFIED OPERATOR RUNTIME
# ============================================================

write(
    RUNTIME,
    r'''
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
'''
)


# ============================================================
# 7. MAIN PUBLIC APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_v4_plan("
    not in main_source
):

    main_source += r'''


def jarvis_v4_plan(
    goal,
    observations=None,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.plan_goal(
        goal,
        observations=observations,
    )


def jarvis_v4_create_mission(
    goal,
    plan_data,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.create_from_dict(
        goal,
        plan_data,
    )


def jarvis_v4_start_mission(
    mission_id,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.advance(
        mission_id
    )


def jarvis_v4_resume_mission(
    mission_id,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.advance(
        mission_id
    )


def jarvis_v4_get_mission(
    mission_id,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.get(
        mission_id
    )


def jarvis_v4_apply_replan(
    mission_id,
    proposal_text,
):

    from omni.operator_runtime import (
        unified_operator_runtime,
    )

    return unified_operator_runtime.apply_replan_json(
        mission_id,
        proposal_text,
    )


def jarvis_v4_dashboard():

    from omni.operator_dashboard import (
        operator_dashboard,
    )

    return operator_dashboard.snapshot()


def jarvis_v4_prepare_desktop_click(
    window_title,
    target,
    screenshot=None,
):

    from omni.desktop_target_executor import (
        desktop_target_executor,
    )

    return desktop_target_executor.prepare_click(
        window_title,
        target,
        screenshot=screenshot,
    )


def jarvis_v4_prepare_desktop_text(
    window_title,
    target,
    value,
):

    from omni.desktop_target_executor import (
        desktop_target_executor,
    )

    return desktop_target_executor.prepare_set_text(
        window_title,
        target,
        value,
    )


def jarvis_v4_coding_diff(
    worktree,
):

    from omni.coding_mission import (
        coding_mission,
    )

    return coding_mission.diff(
        worktree
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# 8. WORKSTATION PAYLOAD
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_computer_operator_v4_payload("
    not in app_source
):

    app_source += r'''


def jarvis_computer_operator_v4_payload():

    from omni.core_integrity import (
        verify_protected_core,
    )

    from omni.operator_dashboard import (
        operator_dashboard,
    )

    from omni.vision_runtime import (
        vision_runtime,
    )


    try:

        integrity = (
            verify_protected_core()
        )


        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "vision":
                vision_runtime.status(),

            "operator":
                operator_dashboard.snapshot(),

            "unified_runtime":
                True,

            "automatic_approval":
                False,

            "automatic_replan_execution":
                False,

            "automatic_git_push":
                False,

            "trading_execution":
                False,
        }


    except Exception as exc:

        return {
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
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
    )


# ============================================================
# 9. TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

from pathlib import Path


import main


from omni.coding_mission import (
    CodingMission,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.goal_verifier import (
    GoalVerifier,
)

from omni.operator_dashboard import (
    OperatorDashboard,
)

from omni.operator_runtime import (
    UnifiedOperatorRuntime,
)

from omni.operator_runtime_schema import (
    from_dict,
)

from omni.vision_runtime import (
    vision_runtime,
)


class FakeRunner:

    def __call__(
        self,
        request,
    ):

        return {
            "response":
                (
                    '{"schema_version":1,'
                    '"steps":[{'
                    '"step_id":"observe",'
                    '"action":"desktop.observe",'
                    '"payload":{},'
                    '"verify":{}'
                    '}]}'
                )
        }


class ComputerOperatorV4Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_vision_preserved(
        self,
    ):

        self.assertTrue(
            vision_runtime.status()[
                "vision_ready"
            ]
        )


    def test_shell_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "danger",

                {
                    "steps": [
                        {
                            "action":
                                "shell.exec",

                            "payload":
                                {},
                        }
                    ]
                },
            )


    def test_trading_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "trade",

                {
                    "steps": [
                        {
                            "action":
                                "trading.execute",

                            "payload":
                                {},
                        }
                    ]
                },
            )


    def test_password_target_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            from_dict(
                "password",

                {
                    "steps": [
                        {
                            "action":
                                "browser.natural_fill",

                            "payload": {
                                "session_id":
                                    "x",

                                "target":
                                    "password field",

                                "value":
                                    "secret",
                            },
                        }
                    ]
                },
            )


    def test_brain_plan_validation(
        self,
    ):

        runtime = (
            UnifiedOperatorRuntime()
        )


        result = runtime.plan_goal(
            "Observe desktop",
            runner=FakeRunner(),
        )


        self.assertTrue(
            result[
                "valid"
            ],
            result,
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_goal_verifier(
        self,
    ):

        verifier = GoalVerifier()


        result = verifier.verify(
            {
                "title_contains":
                    "example"
            },

            {
                "observation": {
                    "title":
                        "Example Domain"
                }
            },
        )


        self.assertTrue(
            result[
                "passed"
            ]
        )


    def test_unverified_is_distinct(
        self,
    ):

        result = (
            GoalVerifier()
            .verify(
                {},
                {
                    "success":
                        True
                },
            )
        )


        self.assertFalse(
            result[
                "required"
            ]
        )


        self.assertIsNone(
            result[
                "passed"
            ]
        )


    def test_test_runner_restriction(
        self,
    ):

        mission = CodingMission()


        allowed = (
            mission._validate_tests(
                (
                    "-m",
                    "unittest",
                    "discover",
                )
            )
        )


        self.assertEqual(
            allowed[
                1
            ],
            "unittest",
        )


        with self.assertRaises(
            PermissionError
        ):

            mission._validate_tests(
                (
                    "-c",
                    "print('bad')",
                )
            )


    def test_merge_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            CodingMission.merge()


    def test_push_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            CodingMission.push()


    def test_readonly_mission_execution(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = (
                UnifiedOperatorRuntime(
                    Path(
                        tmp
                    )
                )
            )


            plan = from_dict(
                "Observe desktop",

                {
                    "steps": [
                        {
                            "step_id":
                                "observe",

                            "action":
                                "desktop.observe",

                            "payload":
                                {},

                            "verify":
                                {},
                        }
                    ]
                },
            )


            mission = runtime.create(
                plan
            )


            result = runtime.advance(
                mission[
                    "mission_id"
                ]
            )


            self.assertEqual(
                result[
                    "status"
                ],
                "completed",
            )


            self.assertFalse(
                result[
                    "verified"
                ]
            )


    def test_browser_start_pauses_for_approval(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = (
                UnifiedOperatorRuntime(
                    Path(
                        tmp
                    )
                )
            )


            plan = from_dict(
                "Open example",

                {
                    "steps": [
                        {
                            "step_id":
                                "browser",

                            "action":
                                "browser.start",

                            "payload": {
                                "url":
                                    "https://example.com",

                                "headless":
                                    True,
                            },

                            "verify":
                                {},
                        }
                    ]
                },
            )


            mission = runtime.create(
                plan
            )


            result = runtime.advance(
                mission[
                    "mission_id"
                ]
            )


            self.assertEqual(
                result[
                    "status"
                ],
                "waiting_approval",
            )


            self.assertIn(
                "browser",
                result[
                    "approval_batches"
                ],
            )


    def test_dashboard(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            dashboard = (
                OperatorDashboard(
                    Path(
                        tmp
                    )
                )
            )


            result = dashboard.snapshot()


            self.assertIn(
                "pending_batches",
                result,
            )


            self.assertFalse(
                result[
                    "automatic_trading"
                ]
            )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_v4_plan
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_create_mission
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_resume_mission
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v4_dashboard
            )
        )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# 10. COMPILE
# ============================================================

print()
print("Checking V4 syntax...")


r = run(
    "-m",
    "py_compile",

    str(
        SCHEMA
    ),

    str(
        DESKTOP
    ),

    str(
        VERIFIER
    ),

    str(
        CODING
    ),

    str(
        DASHBOARD
    ),

    str(
        RUNTIME
    ),

    str(
        MAIN
    ),

    str(
        APP
    ),
)


if r.returncode:

    print(
        "COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Syntax: PASS"
)


# ============================================================
# 11. PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT
            / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.model_router import ModelProfile; "
        "import main; "
        "print('Protected core: PASS'); "
        "print('Main import: PASS')"
    ),
)


if r.returncode:

    print(
        "CORE CHECK FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 12. UNIFIED RUNTIME PREFLIGHT
# ============================================================

print()
print("Checking unified Operator Runtime...")


probe = r'''
from omni.operator_runtime import (
    unified_operator_runtime,
)

from omni.operator_runtime_schema import (
    from_dict,
)


plan = from_dict(
    "Observe desktop",

    {
        "steps": [
            {
                "step_id":
                    "observe",

                "action":
                    "desktop.observe",

                "payload":
                    {},

                "verify":
                    {},
            }
        ]
    },
)


mission = (
    unified_operator_runtime
    .create(
        plan
    )
)


result = (
    unified_operator_runtime
    .advance(
        mission[
            "mission_id"
        ]
    )
)


print(
    "Mission:",
    result[
        "mission_id"
    ]
)


print(
    "Status:",
    result[
        "status"
    ]
)


print(
    "Verified:",
    result[
        "verified"
    ]
)


assert (
    result[
        "status"
    ]
    == "completed"
)


assert (
    result[
        "verified"
    ]
    is False
)


print(
    "Action success != goal verification: VERIFIED"
)


print(
    "Unified Operator Runtime: PASS"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "UNIFIED RUNTIME FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 13. INTERACTIVE APPROVAL PAUSE
# ============================================================

print()
print("Checking workflow approval checkpoint...")


probe = r'''
from omni.operator_runtime import (
    unified_operator_runtime,
)

from omni.operator_runtime_schema import (
    from_dict,
)


plan = from_dict(
    "Inspect example.com",

    {
        "steps": [
            {
                "step_id":
                    "browser",

                "action":
                    "browser.start",

                "payload": {
                    "url":
                        "https://example.com",

                    "headless":
                        True,
                },

                "verify": {
                    "url_contains":
                        "example.com"
                },
            }
        ]
    },
)


mission = (
    unified_operator_runtime
    .create(
        plan
    )
)


result = (
    unified_operator_runtime
    .advance(
        mission[
            "mission_id"
        ]
    )
)


print(
    "Status:",
    result[
        "status"
    ]
)


print(
    "Approval batch:",
    result[
        "approval_batches"
    ].get(
        "browser"
    )
)


assert (
    result[
        "status"
    ]
    == "waiting_approval"
)


assert result[
    "approval_batches"
].get(
    "browser"
)


print(
    "Interactive workflow paused: PASS"
)


print(
    "No browser action executed without approval."
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "APPROVAL CHECKPOINT FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 14. CODING SAFETY
# ============================================================

print()
print("Checking coding mission safety...")


probe = r'''
from omni.coding_mission import (
    coding_mission,
)


safe = (
    coding_mission
    ._validate_tests(
        (
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-q",
        )
    )
)


print(
    "Allowed test runner:",
    safe[
        1
    ]
)


assert (
    safe[
        1
    ]
    == "unittest"
)


for name in (
    "merge",
    "push",
):

    blocked = False


    try:

        getattr(
            coding_mission,
            name
        )()

    except PermissionError:

        blocked = True


    assert blocked


print(
    "Production merge: BLOCKED"
)


print(
    "Remote push: BLOCKED"
)


print(
    "Coding mission safety: PASS"
)
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print(
        "CODING SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 15. DASHBOARD
# ============================================================

print()
print("Checking approval/operator dashboard...")


r = run(
    "-c",
    (
        "from omni.operator_dashboard import operator_dashboard; "
        "x=operator_dashboard.snapshot(); "
        "print('Pending batches:',len(x['pending_batches'])); "
        "print('Missions:',len(x['missions'])); "
        "assert x['automatic_approval'] is False; "
        "assert x['automatic_remote_git_write'] is False; "
        "assert x['automatic_trading'] is False; "
        "print('Operator dashboard: PASS')"
    ),
)


if r.returncode:

    print(
        "DASHBOARD FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 16. TARGETED TESTS
# ============================================================

print()
print("Running Computer Operator V4 tests...")


r = run(
    "-m",
    "unittest",

    "tests.test_computer_operator_v4",

    "tests.test_computer_operator_v3",

    "tests.test_computer_operator_v2",

    "tests.test_computer_operator",

    "tests.test_real_world_action_v3",

    "tests.test_real_world_action_v2",

    "tests.test_real_world_action_engine",

    "tests.test_universal_learning_v5",

    "tests.test_autonomy_engine",

    "tests.test_improvement_lab",

    "-q",
)


if r.returncode:

    print(
        "TARGETED TEST FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 17. FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 18. FINAL CORE VERIFICATION
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if (
        sha(
            ROOT
            / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()

        sys.exit(1)


# ============================================================
# SUCCESS
# ============================================================

print()
print("=" * 80)
print("JARVIS COMPUTER OPERATOR V4 SUCCESS")
print("=" * 80)

print(
    "Permanent governed agents: 29"
)

print()

print("UNIFIED OPERATOR RUNTIME")
print("Single V4 workflow runtime: ACTIVE")
print("Persistent mission state: ACTIVE")
print("Maximum workflow length: 30")
print("Cross-step browser references: ACTIVE")
print("Cross-step worktree references: ACTIVE")
print("Bounded retries: ACTIVE")
print("Workflow failure capture: ACTIVE")
print()

print("BRAIN -> WORKFLOW")
print("Governed Operator Agent planner: ACTIVE")
print("V4 JSON workflow DSL: ACTIVE")
print("Deterministic action validation: ACTIVE")
print("Per-action payload validation: ACTIVE")
print("Model plan auto-execution: BLOCKED")
print()

print("DESKTOP NATURAL TARGETING")
print("Natural language -> UIA target: ACTIVE")
print("UIA click execution: ACTIVE + APPROVAL")
print("UIA text entry: ACTIVE + APPROVAL")
print("Vision fallback: ACTIVE")
print("Vision-only coordinate fallback: STRICTLY GATED")
print("Vision confidence threshold: 0.90")
print("Full-screen coordinate-space validation: ACTIVE")
print("Coordinate approval expiry: ACTIVE")
print("Screenshot hash binding: ACTIVE")
print("Ambiguous targets: BLOCKED")
print()

print("LIVE BROWSER WORKFLOWS")
print("Persistent browser sessions: ACTIVE")
print("session_ref workflow links: ACTIVE")
print("Natural-language DOM target resolution: ACTIVE")
print("DOM click: ACTIVE + APPROVAL")
print("DOM fill: ACTIVE + APPROVAL")
print("DOM observation: ACTIVE")
print("Password/sensitive fill: BLOCKED")
print("Live browser downloads: BLOCKED")
print()

print("MISSION VERIFICATION")
print("Action success tracked separately: ACTIVE")
print("Goal verification tracked separately: ACTIVE")
print("Deterministic contains verification: ACTIVE")
print("URL verification: ACTIVE")
print("Title verification: ACTIVE")
print("DOM-change verification: ACTIVE")
print("Window verification: ACTIVE")
print("File existence verification: ACTIVE")
print("Verification coverage metric: ACTIVE")
print()

print("REPLAN")
print("Failure -> new Brain workflow proposal: ACTIVE")
print("Replan DSL validation: ACTIVE")
print("Automatic replan application: BLOCKED")
print("Explicit replan application: ACTIVE")
print("Replanned interactive steps need new approval: ACTIVE")
print()

print("ISOLATED CODING MISSIONS")
print("Git worktree creation: ACTIVE + APPROVAL")
print("worktree_ref workflow links: ACTIVE")
print("unittest/pytest execution: ACTIVE + APPROVAL")
print("Arbitrary Python -c test execution: BLOCKED")
print("Worktree diff inspection: ACTIVE")
print("Automatic production merge: BLOCKED")
print("Remote Git push: BLOCKED")
print()

print("OPERATOR DASHBOARD")
print("Mission state visibility: ACTIVE")
print("Pending approval visibility: ACTIVE")
print("Approval batch visibility: ACTIVE")
print("Running mission visibility: ACTIVE")
print("Automatic approval: BLOCKED")
print()

print("REAL PERCEPTION")
print("Qwen3-VL local vision: PRESERVED")
print("DOM perception: PRESERVED")
print("Windows UIA: PRESERVED")
print("Vision/UIA fusion: PRESERVED")
print()

print("SAFETY")
print("Protected Core: UNCHANGED")
print("Credential automation: BLOCKED")
print("Arbitrary shell/PowerShell DSL: BLOCKED")
print("Remote Git push: BLOCKED")
print("Production auto-merge: BLOCKED")
print("Trading execution: BLOCKED")
print("Unbounded retry loops: BLOCKED")
print()

print("Computer Operator V3: PRESERVED")
print("Computer Operator V2: PRESERVED")
print("Computer Operator V1: PRESERVED")
print("Action Engine V1-V3: PRESERVED")
print("Universal Learning: PRESERVED")
print("Dynamic Specialists: PRESERVED")
print("Self-Improvement Lab: PRESERVED")
print("Meta Intelligence: PRESERVED")
print("Autonomy Engine: PRESERVED")
print("HybridMemory: PRESERVED")
print("Full regression: PASS")
print()

print("NEXT MAJOR PHASE:")
print("JARVIS CONNECTED SERVICES")
print()
print("Gmail OAuth + governed read/draft/send")
print("Google Calendar OAuth + read/create/update")
print("Google Contacts")
print("GitHub authenticated read workflows")
print("Operator approval dashboard UI")
print("Advanced Voice + wake word")
print()
print("THEN:")
print("Advanced Trading Intelligence")
print("NautilusTrader isolated POC")
