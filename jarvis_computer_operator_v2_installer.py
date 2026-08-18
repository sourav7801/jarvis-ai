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

DSL = ROOT / "omni" / "operator_dsl.py"
VISION = ROOT / "omni" / "vision_runtime.py"
FUSION = ROOT / "omni" / "target_fusion.py"
DESKTOP = ROOT / "omni" / "desktop_state.py"
BROWSER = ROOT / "omni" / "browser_observation_loop.py"
MEMORY = ROOT / "omni" / "operator_memory.py"
OPERATOR = ROOT / "omni" / "computer_operator_v2.py"

TEST = ROOT / "tests" / "test_computer_operator_v2.py"

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "computer_operator_v2"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    MAIN,
    APP,
    DSL,
    VISION,
    FUSION,
    DESKTOP,
    BROWSER,
    MEMORY,
    OPERATOR,
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


def sha(path):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(path, source):
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

    existed = path.exists()

    BACKUPS[path] = existed

    if existed:

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        backup.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            backup,
        )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

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
print("JARVIS COMPUTER OPERATOR V2")
print("DSL + DOM OBSERVATION + UI STATE + VISION FUSION")
print("=" * 80)


# ============================================================
# BASELINE
# ============================================================

print()
print("Checking 390-test architecture checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.computer_operator import computer_operator; "
        "from omni.semantic_ui import semantic_ui; "
        "from omni.persistent_browser import persistent_browser; "
        "assert semantic_ui.available(); "
        "assert persistent_browser.available(); "
        "assert persistent_browser.provider_probe()['success']; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V1: PASS'); "
        "print('Playwright Chromium: PASS'); "
        "print('Semantic UI: PASS')"
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
# SAFE OPERATOR DSL
# ============================================================

write(
    DSL,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

import json
import re


ALLOWED_ACTIONS = {
    "desktop.observe",
    "desktop.controls",

    "browser.observe",
    "browser.observe_click",
    "browser.observe_fill",

    "vision.analyze",

    "document.read",
    "document.search",

    "git.status",
    "git.diff",
    "git.repository_state",
}


INTERACTIVE_ACTIONS = {
    "browser.observe",
    "browser.observe_click",
    "browser.observe_fill",
}


BLOCKED_PREFIXES = (
    "shell.",
    "cmd.",
    "powershell.",
    "process.",
    "credential.",
    "trade.",
    "trading.",
    "broker.",
    "order.",
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


ALLOWED_PAYLOADS = {

    "desktop.observe": {
        "window_title",
        "include_controls",
    },

    "desktop.controls": {
        "window_title",
        "text",
        "control_type",
        "automation_id",
    },

    "browser.observe": {
        "url",
        "profile",
    },

    "browser.observe_click": {
        "url",
        "selector",
        "profile",
    },

    "browser.observe_fill": {
        "url",
        "selector",
        "value",
        "profile",
        "sensitive",
    },

    "vision.analyze": {
        "path",
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
}


@dataclass(frozen=True)
class DSLStep:

    step_id: str

    action: str

    payload: dict = field(
        default_factory=dict
    )

    retries: int = 0

    observe: bool = True


@dataclass(frozen=True)
class DSLPlan:

    goal: str

    steps: tuple[
        DSLStep,
        ...
    ]

    source: str = "validated-dsl"

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

        for key, child in value.items():

            if (
                str(
                    key
                ).lower()
                in SECRET_FIELDS
            ):

                raise PermissionError(
                    "Credential-bearing DSL "
                    "field blocked: "
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
        DSLPlan,
    ):

        raise TypeError(
            "Expected DSLPlan."
        )


    if not str(
        plan.goal
    ).strip():

        raise ValueError(
            "Goal cannot be empty."
        )


    if (
        plan.schema_version
        != 1
    ):

        raise ValueError(
            "Unsupported DSL schema."
        )


    if len(
        plan.steps
    ) > 20:

        raise ValueError(
            "Operator DSL cannot exceed "
            "20 steps."
        )


    seen = set()


    for step in plan.steps:

        if step.step_id in seen:

            raise ValueError(
                "Duplicate step ID: "
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
                "Blocked action: "
                + action
            )


        if action not in (
            ALLOWED_ACTIONS
        ):

            raise PermissionError(
                "Unknown action: "
                + action
            )


        if not isinstance(
            step.payload,
            dict,
        ):

            raise TypeError(
                "Payload must be a dictionary."
            )


        unexpected = (
            set(
                step.payload
            )
            - ALLOWED_PAYLOADS[
                action
            ]
        )


        if unexpected:

            raise PermissionError(
                "Unexpected payload fields "
                "for "
                + action
                + ": "
                + ", ".join(
                    sorted(
                        unexpected
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


        if (
            action
            == "browser.observe_fill"
        ):

            selector = str(
                step.payload.get(
                    "selector",
                    ""
                )
            ).lower()


            if (
                bool(
                    step.payload.get(
                        "sensitive",
                        False,
                    )
                )

                or "password"
                in selector

                or "passwd"
                in selector
            ):

                raise PermissionError(
                    "Password/credential "
                    "automation is blocked."
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
            "DSL document must be an object."
        )


    raw_steps = data.get(
        "steps",
        []
    )


    if not isinstance(
        raw_steps,
        (
            list,
            tuple,
        ),
    ):

        raise TypeError(
            "DSL steps must be an array."
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
                "DSL step must be an object."
            )


        steps.append(
            DSLStep(
                step_id=str(
                    item.get(
                        "step_id",
                        "step-"
                        + str(
                            index
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
                        {},
                    )
                ),

                retries=int(
                    item.get(
                        "retries",
                        0,
                    )
                ),

                observe=bool(
                    item.get(
                        "observe",
                        True,
                    )
                ),
            )
        )


    plan = DSLPlan(
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
    source="model-proposal",
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


    return (
        "Return JSON only.\n"
        "Propose a JARVIS computer workflow.\n"
        "You are NOT authorizing execution.\n"
        "Do not include shell commands, PowerShell, "
        "credentials, passwords, tokens, broker or "
        "trading execution.\n\n"
        "Allowed actions:\n"
        + "\n".join(
            " - "
            + action
            for action
            in sorted(
                ALLOWED_ACTIONS
            )
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
# TRUTHFUL LOCAL VISION RUNTIME
# ============================================================

write(
    VISION,
    r'''
from __future__ import annotations

from pathlib import Path

import base64
import json
import os
import shutil
import urllib.request


class VisionRuntime:

    def __init__(
        self,
        config_path=None,
        base_url=None,
    ):

        self.config_path = Path(
            config_path
            or (
                Path("config")
                / "vision_provider.json"
            )
        )

        self.base_url = (
            base_url
            or os.environ.get(
                "OLLAMA_HOST",
                "http://127.0.0.1:11434",
            )
        ).rstrip(
            "/"
        )


    def config(
        self,
    ):

        env_model = (
            os.environ.get(
                "JARVIS_VISION_MODEL"
            )
        )


        if env_model:

            return {
                "provider":
                    "ollama",

                "model":
                    env_model,

                "enabled":
                    True,
            }


        if not self.config_path.exists():

            return {
                "provider":
                    "ollama",

                "model":
                    None,

                "enabled":
                    False,
            }


        try:

            return json.loads(
                self.config_path
                .read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            return {
                "provider":
                    "ollama",

                "model":
                    None,

                "enabled":
                    False,
            }


    def models(
        self,
    ):

        try:

            with urllib.request.urlopen(
                self.base_url
                + "/api/tags",
                timeout=2,
            ) as response:

                data = json.loads(
                    response.read()
                    .decode(
                        "utf-8"
                    )
                )

        except Exception:

            return ()


        return tuple(
            str(
                item.get(
                    "name",
                    ""
                )
            ).strip()

            for item
            in data.get(
                "models",
                []
            )

            if item.get(
                "name"
            )
        )


    def status(
        self,
    ):

        config = self.config()

        installed = self.models()

        model = config.get(
            "model"
        )

        present = bool(
            model
            and model
            in installed
        )


        return {
            "provider":
                "ollama",

            "ollama_executable":
                bool(
                    shutil.which(
                        "ollama"
                    )
                ),

            "ollama_reachable":
                bool(
                    installed
                ),

            "installed_models":
                installed,

            "configured_model":
                model,

            "configured_model_present":
                present,

            "enabled":
                bool(
                    config.get(
                        "enabled",
                        False,
                    )
                ),

            "vision_ready":
                bool(
                    config.get(
                        "enabled",
                        False,
                    )
                    and present
                ),

            "automatic_model_download":
                False,
        }


    def configure(
        self,
        model,
        *,
        enabled=True,
    ):

        model = str(
            model
        ).strip()


        if model not in self.models():

            raise ValueError(
                "Vision model is not "
                "installed in Ollama."
            )


        config = {
            "provider":
                "ollama",

            "model":
                model,

            "enabled":
                bool(
                    enabled
                ),
        }


        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temp = self.config_path.with_suffix(
            ".tmp"
        )


        temp.write_text(
            json.dumps(
                config,
                indent=2,
            ),
            encoding="utf-8",
        )


        temp.replace(
            self.config_path
        )


        return config


    def analyze(
        self,
        path,
        *,
        prompt=None,
    ):

        status = self.status()


        if not status[
            "vision_ready"
        ]:

            return {
                "success":
                    False,

                "vision_available":
                    False,

                "error":
                    (
                        "No verified vision "
                        "model configured."
                    ),

                "status":
                    status,
            }


        source = Path(
            path
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        image_data = (
            base64.b64encode(
                source.read_bytes()
            ).decode(
                "ascii"
            )
        )


        body = json.dumps(
            {
                "model":
                    status[
                        "configured_model"
                    ],

                "prompt":
                    (
                        prompt
                        or (
                            "Analyze this screenshot. "
                            "Return JSON with summary, "
                            "visible_text and elements. "
                            "Each element should include "
                            "label, role, x, y and confidence."
                        )
                    ),

                "stream":
                    False,

                "format":
                    "json",

                "images": [
                    image_data
                ],
            }
        ).encode(
            "utf-8"
        )


        request = urllib.request.Request(
            self.base_url
            + "/api/generate",

            data=body,

            headers={
                "Content-Type":
                    "application/json"
            },

            method="POST",
        )


        try:

            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:

                payload = json.loads(
                    response.read()
                    .decode(
                        "utf-8"
                    )
                )


            raw = str(
                payload.get(
                    "response",
                    ""
                )
            )


            try:

                analysis = json.loads(
                    raw
                )

            except Exception:

                analysis = {
                    "summary":
                        raw[:12000],

                    "visible_text":
                        [],

                    "elements":
                        [],
                }


            return {
                "success":
                    True,

                "vision_available":
                    True,

                "model":
                    status[
                        "configured_model"
                    ],

                "analysis":
                    analysis,
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "vision_available":
                    True,

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


vision_runtime = (
    VisionRuntime()
)
'''
)


# ============================================================
# DOM + UIA + VISION TARGET FUSION
# ============================================================

write(
    FUSION,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

import re


WEIGHTS = {
    "dom": 1.00,
    "uia": 0.95,
    "vision": 0.70,
}


@dataclass(frozen=True)
class TargetCandidate:

    source: str

    label: str

    role: str

    score: float

    payload: dict


@dataclass(frozen=True)
class TargetResolution:

    target: str

    resolved: bool

    ambiguous: bool

    best: TargetCandidate | None

    candidates: tuple[
        TargetCandidate,
        ...
    ]


def _tokens(
    value,
):

    return {
        token

        for token in re.findall(
            r"[a-z0-9]+",
            str(
                value
            ).lower(),
        )

        if token
    }


def _similarity(
    target,
    label,
):

    a = _tokens(
        target
    )

    b = _tokens(
        label
    )


    if not a or not b:

        return 0.0


    score = (
        len(
            a & b
        )
        / len(
            a | b
        )
    )


    left = str(
        target
    ).strip().lower()

    right = str(
        label
    ).strip().lower()


    if left == right:

        score += 0.35

    elif left in right:

        score += 0.15


    return min(
        1.0,
        score,
    )


class TargetFusion:

    def resolve(
        self,
        target,
        *,
        dom=(),
        uia=(),
        vision=(),
        minimum_score=0.42,
    ):

        candidates = []


        for source, items in (
            (
                "dom",
                dom,
            ),
            (
                "uia",
                uia,
            ),
            (
                "vision",
                vision,
            ),
        ):

            for item in items:

                label = str(
                    item.get(
                        "text",
                        ""
                    )
                    or item.get(
                        "aria_label",
                        ""
                    )
                    or item.get(
                        "name",
                        ""
                    )
                    or item.get(
                        "label",
                        ""
                    )
                )


                role = str(
                    item.get(
                        "role",
                        ""
                    )
                    or item.get(
                        "control_type",
                        ""
                    )
                    or item.get(
                        "tag",
                        ""
                    )
                )


                confidence = (
                    float(
                        item.get(
                            "confidence",
                            1.0,
                        )
                    )
                    if source
                    == "vision"
                    else 1.0
                )


                confidence = max(
                    0.0,
                    min(
                        confidence,
                        1.0,
                    ),
                )


                score = (
                    _similarity(
                        target,
                        label,
                    )
                    * WEIGHTS[
                        source
                    ]
                    * confidence
                )


                if score > 0:

                    candidates.append(
                        TargetCandidate(
                            source=
                                source,

                            label=
                                label,

                            role=
                                role,

                            score=
                                round(
                                    score,
                                    4,
                                ),

                            payload=
                                dict(
                                    item
                                ),
                        )
                    )


        candidates.sort(
            key=lambda item:
                item.score,
            reverse=True,
        )


        if not candidates:

            return TargetResolution(
                target=str(
                    target
                ),

                resolved=False,

                ambiguous=False,

                best=None,

                candidates=(),
            )


        best = candidates[
            0
        ]


        if (
            best.score
            < minimum_score
        ):

            return TargetResolution(
                target=str(
                    target
                ),

                resolved=False,

                ambiguous=False,

                best=
                    best,

                candidates=
                    tuple(
                        candidates[:10]
                    ),
            )


        ambiguous = (
            len(
                candidates
            ) > 1

            and abs(
                candidates[
                    0
                ].score
                - candidates[
                    1
                ].score
            )
            <= 0.05
        )


        return TargetResolution(
            target=str(
                target
            ),

            resolved=
                not ambiguous,

            ambiguous=
                ambiguous,

            best=
                best,

            candidates=
                tuple(
                    candidates[:10]
                ),
        )


target_fusion = (
    TargetFusion()
)
'''
)


# ============================================================
# DESKTOP STATE
# ============================================================

write(
    DESKTOP,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

import hashlib
import json
import time


from omni.semantic_ui import (
    semantic_ui,
)


@dataclass(frozen=True)
class DesktopSnapshot:

    timestamp: float

    window_titles: tuple[
        str,
        ...
    ]

    controls: tuple[
        dict,
        ...
    ]

    fingerprint: str


class DesktopState:

    def snapshot(
        self,
        *,
        window_title=None,
        include_controls=False,
    ):

        windows = (
            semantic_ui
            .windows()
        )


        titles = tuple(
            item[
                "title"
            ]
            for item
            in windows
        )


        controls = ()


        if (
            include_controls
            and window_title
        ):

            controls = (
                semantic_ui
                .controls(
                    window_title,
                    limit=150,
                )
            )


        raw = json.dumps(
            {
                "titles":
                    titles,

                "controls":
                    controls,
            },

            sort_keys=True,

            ensure_ascii=False,

            default=str,
        )


        return DesktopSnapshot(
            timestamp=
                time.time(),

            window_titles=
                titles,

            controls=
                tuple(
                    controls
                ),

            fingerprint=
                hashlib.sha256(
                    raw.encode(
                        "utf-8"
                    )
                ).hexdigest(),
        )


    @staticmethod
    def compare(
        before,
        after,
    ):

        before_windows = set(
            before.window_titles
        )

        after_windows = set(
            after.window_titles
        )


        before_controls = {
            (
                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "control_type",
                    ""
                ),

                item.get(
                    "automation_id",
                    ""
                ),
            )

            for item
            in before.controls
        }


        after_controls = {
            (
                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "control_type",
                    ""
                ),

                item.get(
                    "automation_id",
                    ""
                ),
            )

            for item
            in after.controls
        }


        return {
            "changed":
                before.fingerprint
                != after.fingerprint,

            "windows_opened":
                tuple(
                    sorted(
                        after_windows
                        - before_windows
                    )
                ),

            "windows_closed":
                tuple(
                    sorted(
                        before_windows
                        - after_windows
                    )
                ),

            "controls_added":
                tuple(
                    sorted(
                        after_controls
                        - before_controls
                    )
                ),

            "controls_removed":
                tuple(
                    sorted(
                        before_controls
                        - after_controls
                    )
                ),
        }


desktop_state = (
    DesktopState()
)
'''
)

print()
print("PART 1 SAVED SUCCESSFULLY")
print("Now paste PART 2.")


# ============================================================
# BROWSER DOM OBSERVATION LOOP
# ============================================================

write(
    BROWSER,
    r'''
from __future__ import annotations

import hashlib
import json
import tempfile


from omni.approval_queue import (
    approval_queue,
)

from omni.persistent_browser import (
    persistent_browser,
)


class BrowserObservationLoop:

    @staticmethod
    def snapshot(
        page,
    ):

        elements = page.evaluate(
            """
            () => Array.from(
                document.querySelectorAll(
                    'a,button,input,textarea,select,[role],[aria-label]'
                )
            )
            .slice(0,250)
            .map((el,index) => {
                const r = el.getBoundingClientRect();

                return {
                    index,

                    tag:
                        (
                            el.tagName
                            || ''
                        ).toLowerCase(),

                    role:
                        el.getAttribute(
                            'role'
                        ) || '',

                    text:
                        (
                            el.innerText
                            || el.value
                            || el.getAttribute(
                                'aria-label'
                            )
                            || el.getAttribute(
                                'placeholder'
                            )
                            || ''
                        )
                        .trim()
                        .slice(0,500),

                    aria_label:
                        el.getAttribute(
                            'aria-label'
                        ) || '',

                    name:
                        el.getAttribute(
                            'name'
                        ) || '',

                    id:
                        el.id || '',

                    type:
                        el.getAttribute(
                            'type'
                        ) || '',

                    disabled:
                        !!el.disabled,

                    visible:
                        !!(
                            r.width
                            && r.height
                        )
                };
            })
            """
        )


        try:

            body = (
                page.locator(
                    "body"
                )
                .inner_text()[
                    :20000
                ]
            )

        except Exception:

            body = ""


        payload = {
            "url":
                page.url,

            "title":
                page.title(),

            "text":
                body,

            "elements":
                elements,
        }


        raw = json.dumps(
            payload,

            sort_keys=True,

            ensure_ascii=False,

            default=str,
        )


        payload[
            "fingerprint"
        ] = hashlib.sha256(
            raw.encode(
                "utf-8"
            )
        ).hexdigest()


        return payload


    @staticmethod
    def compare(
        before,
        after,
    ):

        old = {
            (
                item.get(
                    "tag",
                    ""
                ),

                item.get(
                    "role",
                    ""
                ),

                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "id",
                    ""
                ),
            )

            for item
            in before.get(
                "elements",
                ()
            )
        }


        new = {
            (
                item.get(
                    "tag",
                    ""
                ),

                item.get(
                    "role",
                    ""
                ),

                item.get(
                    "text",
                    ""
                ),

                item.get(
                    "id",
                    ""
                ),
            )

            for item
            in after.get(
                "elements",
                ()
            )
        }


        return {
            "changed":
                before[
                    "fingerprint"
                ]
                != after[
                    "fingerprint"
                ],

            "url_changed":
                before[
                    "url"
                ]
                != after[
                    "url"
                ],

            "title_changed":
                before[
                    "title"
                ]
                != after[
                    "title"
                ],

            "elements_added":
                tuple(
                    list(
                        new
                        - old
                    )[:100]
                ),

            "elements_removed":
                tuple(
                    list(
                        old
                        - new
                    )[:100]
                ),
        }


    @staticmethod
    def binding(
        operation,
        url,
        *,
        profile="default",
        selector=None,
        value=None,
    ):

        url = (
            persistent_browser
            ._validate_url(
                url
            )
        )


        profile = (
            persistent_browser
            ._profile_name(
                profile
            )
        )


        payload = {
            "url":
                url,

            "profile":
                profile,

            "operation":
                operation,
        }


        display = dict(
            payload
        )


        if selector is not None:

            selector = str(
                selector
            ).strip()


            if not selector:

                raise ValueError(
                    "Selector cannot be empty."
                )


            payload[
                "selector"
            ] = selector


            display[
                "selector"
            ] = selector


        if value is not None:

            value = str(
                value
            )


            payload[
                "value_hash"
            ] = hashlib.sha256(
                value.encode(
                    "utf-8"
                )
            ).hexdigest()


            payload[
                "length"
            ] = len(
                value
            )


            display[
                "preview"
            ] = value[:80]


        return {
            "action":
                (
                    "browser_observation."
                    + operation
                ),

            "payload":
                payload,

            "display":
                display,

            "risk":
                "browser-observed-action",
        }


    @staticmethod
    def _gate(
        binding,
        approval_id,
    ):

        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue
                    .request(
                        binding[
                            "action"
                        ],

                        binding[
                            "payload"
                        ],

                        display=
                            binding[
                                "display"
                            ],

                        risk=
                            binding[
                                "risk"
                            ],
                    ),
            }


        approval_queue.consume(
            approval_id,

            binding[
                "action"
            ],

            binding[
                "payload"
            ],
        )


        return None


    def observe(
        self,
        url,
        *,
        profile="default",
        approval_id=None,
    ):

        binding = self.binding(
            "observe",
            url,
            profile=profile,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            operation="observe",
        )


    def click(
        self,
        url,
        selector,
        *,
        profile="default",
        approval_id=None,
    ):

        binding = self.binding(
            "click",
            url,
            profile=profile,
            selector=selector,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            selector=selector,
            operation="click",
        )


    def fill(
        self,
        url,
        selector,
        value,
        *,
        profile="default",
        approval_id=None,
        sensitive=False,
    ):

        selector = str(
            selector
        )


        if (
            sensitive
            or "password"
            in selector.lower()
            or "passwd"
            in selector.lower()
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Credential/password "
                        "automation blocked."
                    ),
            }


        binding = self.binding(
            "fill",
            url,
            profile=profile,
            selector=selector,
            value=value,
        )


        gate = self._gate(
            binding,
            approval_id,
        )


        if gate:

            return gate


        return self._run(
            url,
            profile=profile,
            selector=selector,
            value=value,
            operation="fill",
        )


    def _run(
        self,
        url,
        *,
        profile="default",
        selector=None,
        value=None,
        operation="observe",
    ):

        from playwright.sync_api import (
            sync_playwright,
        )


        profile = (
            persistent_browser
            ._profile_name(
                profile
            )
        )


        directory = (
            persistent_browser
            .profile_path(
                profile
            )
        )


        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        try:

            with sync_playwright() as p:

                context = (
                    p.chromium
                    .launch_persistent_context(
                        user_data_dir=
                            str(
                                directory
                            ),

                        headless=
                            True,

                        accept_downloads=
                            False,
                    )
                )


                page = (
                    context.pages[
                        0
                    ]
                    if context.pages
                    else context.new_page()
                )


                page.goto(
                    persistent_browser
                    ._validate_url(
                        url
                    ),

                    wait_until=
                        "domcontentloaded",

                    timeout=
                        30000,
                )


                before = self.snapshot(
                    page
                )


                if operation in (
                    "click",
                    "fill",
                ):

                    locator = page.locator(
                        selector
                    )


                    count = locator.count()


                    if count != 1:

                        context.close()


                        return {
                            "success":
                                False,

                            "error":
                                (
                                    "Selector must match "
                                    "exactly one element. "
                                    "Matches: "
                                    + str(
                                        count
                                    )
                                ),

                            "before":
                                before,
                        }


                    if operation == "click":

                        locator.click(
                            timeout=15000
                        )

                    else:

                        locator.fill(
                            str(
                                value
                            ),
                            timeout=15000,
                        )


                after = self.snapshot(
                    page
                )


                result = {
                    "success":
                        True,

                    "operation":
                        operation,

                    "before":
                        before,

                    "after":
                        after,

                    "comparison":
                        self.compare(
                            before,
                            after,
                        ),

                    "profile":
                        profile,
                }


                context.close()


                return result


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


    def provider_probe(
        self,
    ):

        from playwright.sync_api import (
            sync_playwright,
        )


        try:

            with tempfile.TemporaryDirectory() as tmp:

                with sync_playwright() as p:

                    context = (
                        p.chromium
                        .launch_persistent_context(
                            user_data_dir=
                                tmp,

                            headless=True,

                            accept_downloads=False,
                        )
                    )


                    page = (
                        context.pages[
                            0
                        ]
                        if context.pages
                        else context.new_page()
                    )


                    page.set_content(
                        (
                            '<button id="save">'
                            'Save'
                            '</button>'
                            '<input aria-label="Name">'
                        )
                    )


                    snapshot = self.snapshot(
                        page
                    )


                    context.close()


                    return {
                        "success":
                            True,

                        "elements":
                            len(
                                snapshot[
                                    "elements"
                                ]
                            ),

                        "has_save":
                            any(
                                item.get(
                                    "text",
                                    ""
                                ).strip().lower()
                                == "save"

                                for item
                                in snapshot[
                                    "elements"
                                ]
                            ),
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


browser_observation_loop = (
    BrowserObservationLoop()
)
'''
)


# ============================================================
# OPERATOR MEMORY
# ============================================================

write(
    MEMORY,
    r'''
from __future__ import annotations

from pathlib import Path

import json
import time
import uuid


class OperatorMemory:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "operator"
                / "missions.jsonl"
            )
        )


    def record(
        self,
        *,
        goal,
        success,
        steps,
        failed_step=None,
        lesson=None,
        metadata=None,
        project_id=None,
    ):

        record = {
            "operator_memory_id":
                (
                    "operator-memory-"
                    + uuid.uuid4()
                    .hex[:16]
                ),

            "goal":
                str(
                    goal
                )[:4000],

            "success":
                bool(
                    success
                ),

            "steps":
                int(
                    steps
                ),

            "failed_step":
                failed_step,

            "lesson":
                str(
                    lesson
                    or ""
                )[:4000],

            "metadata":
                dict(
                    metadata
                    or {}
                ),

            "created_at":
                time.time(),
        }


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


        if (
            failed_step
            or lesson
        ):

            try:

                from omni.memory_context import (
                    remember_scoped,
                )

                from omni.memory_scope import (
                    MemoryScope,
                )


                scope = (
                    MemoryScope.PROJECT
                    if project_id
                    else MemoryScope.AGENT_FINDING
                )


                remember_scoped(
                    (
                        "JARVIS computer operator "
                        "experience\nGoal: "
                        + str(
                            goal
                        )[:2000]
                        + "\nSuccess: "
                        + str(
                            bool(
                                success
                            )
                        )
                        + "\nFailed step: "
                        + str(
                            failed_step
                            or ""
                        )
                        + "\nLesson: "
                        + str(
                            lesson
                            or ""
                        )[:2000]
                    ),

                    scope,

                    source=
                        "jarvis",

                    project_id=
                        project_id,

                    tags=(
                        "computer-operator",
                        "operator-learning",
                    ),

                    metadata={
                        "failed_step":
                            failed_step,

                        "success":
                            bool(
                                success
                            ),
                    },
                )


            except Exception:

                pass


        return record


    def recent(
        self,
        limit=20,
    ):

        if not self.path.exists():

            return ()


        output = []


        for line in (
            self.path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
        ):

            try:

                output.append(
                    json.loads(
                        line
                    )
                )

            except Exception:

                continue


        return tuple(
            output[
                -max(
                    1,
                    int(
                        limit
                    ),
                ):
            ]
        )


operator_memory = (
    OperatorMemory()
)
'''
)


# ============================================================
# COMPUTER OPERATOR V2
# ============================================================

write(
    OPERATOR,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

import time
import uuid


from omni.action_replanner import (
    action_replanner,
)

from omni.approval_batch import (
    approval_batches,
)

from omni.browser_observation_loop import (
    browser_observation_loop,
)

from omni.desktop_state import (
    desktop_state,
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

from omni.operator_dsl import (
    is_interactive,
    parse_json,
    planner_prompt,
    validate_plan,
)

from omni.operator_memory import (
    operator_memory,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.target_fusion import (
    target_fusion,
)

from omni.vision_runtime import (
    vision_runtime,
)


@dataclass(frozen=True)
class OperatorV2Result:

    operator_id: str

    goal: str

    success: bool

    completed_steps: int

    total_steps: int

    results: tuple[
        dict,
        ...
    ]

    failed_step: str | None = None

    needs_replan: bool = False

    replan: object = None


class ComputerOperatorV2:

    def planner_prompt(
        self,
        goal,
        observations=None,
    ):

        return planner_prompt(
            goal,
            observations,
        )


    def validate_proposal(
        self,
        goal,
        proposal_text,
    ):

        return parse_json(
            goal,
            proposal_text,
            source=
                "brain-or-model-proposal",
        )


    def prepare(
        self,
        plan,
    ):

        validate_plan(
            plan
        )


        bindings = []


        for step in plan.steps:

            if not is_interactive(
                step.action
            ):

                continue


            payload = step.payload


            operation = {
                "browser.observe":
                    "observe",

                "browser.observe_click":
                    "click",

                "browser.observe_fill":
                    "fill",
            }[
                step.action
            ]


            binding = (
                browser_observation_loop
                .binding(
                    operation,

                    payload[
                        "url"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    selector=
                        payload.get(
                            "selector"
                        ),

                    value=
                        payload.get(
                            "value"
                        ),
                )
            )


            bindings.append(
                {
                    "step_id":
                        step.step_id,

                    **binding,
                }
            )


        batch = (
            approval_batches
            .create(
                plan.goal,
                bindings,
            )

            if bindings

            else None
        )


        return {
            "success":
                True,

            "plan":
                plan,

            "approval_batch":
                batch,
        }


    def prepare_proposal(
        self,
        goal,
        proposal_text,
    ):

        return self.prepare(
            self.validate_proposal(
                goal,
                proposal_text,
            )
        )


    def _execute_step(
        self,
        step,
        token,
    ):

        payload = step.payload


        if (
            step.action
            == "desktop.observe"
        ):

            return {
                "success":
                    True,

                "snapshot":
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
                    ),
            }


        if (
            step.action
            == "desktop.controls"
        ):

            return {
                "success":
                    True,

                "controls":
                    semantic_ui
                    .controls(
                        payload[
                            "window_title"
                        ],

                        text=
                            payload.get(
                                "text"
                            ),

                        control_type=
                            payload.get(
                                "control_type"
                            ),

                        automation_id=
                            payload.get(
                                "automation_id"
                            ),
                    ),
            }


        if (
            step.action
            == "browser.observe"
        ):

            return (
                browser_observation_loop
                .observe(
                    payload[
                        "url"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,
                )
            )


        if (
            step.action
            == "browser.observe_click"
        ):

            return (
                browser_observation_loop
                .click(
                    payload[
                        "url"
                    ],

                    payload[
                        "selector"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,
                )
            )


        if (
            step.action
            == "browser.observe_fill"
        ):

            return (
                browser_observation_loop
                .fill(
                    payload[
                        "url"
                    ],

                    payload[
                        "selector"
                    ],

                    payload[
                        "value"
                    ],

                    profile=
                        payload.get(
                            "profile",
                            "default",
                        ),

                    approval_id=
                        token,

                    sensitive=
                        bool(
                            payload.get(
                                "sensitive",
                                False,
                            )
                        ),
                )
            )


        if (
            step.action
            == "vision.analyze"
        ):

            return (
                vision_runtime
                .analyze(
                    payload[
                        "path"
                    ]
                )
            )


        if (
            step.action
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
            step.action
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
            step.action
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
            step.action
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
            step.action
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


        return {
            "success":
                False,

            "error":
                "No executor for DSL action.",
        }


    def execute(
        self,
        plan,
        *,
        approval_batch_id=None,
        project_id=None,
    ):

        validate_plan(
            plan
        )


        operator_id = (
            "operator-v2-"
            + uuid.uuid4()
            .hex[:16]
        )


        results = []

        completed = 0


        for step in plan.steps:

            token = None


            if is_interactive(
                step.action
            ):

                token = (
                    approval_batches
                    .token_for_step(
                        approval_batch_id,
                        step.step_id,
                    )

                    if approval_batch_id

                    else None
                )


                if not token:

                    return (
                        OperatorV2Result(
                            operator_id=
                                operator_id,

                            goal=
                                plan.goal,

                            success=False,

                            completed_steps=
                                completed,

                            total_steps=
                                len(
                                    plan.steps
                                ),

                            results=
                                tuple(
                                    results
                                ),

                            failed_step=
                                step.step_id,

                            needs_replan=
                                False,

                            replan={
                                "approval_required":
                                    True
                            },
                        )
                    )


            attempts = 0

            success = False

            output = None

            error = None


            while (
                attempts
                <= step.retries
            ):

                attempts += 1


                try:

                    output = (
                        self._execute_step(
                            step,
                            token,
                        )
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


                if is_interactive(
                    step.action
                ):

                    break


                if (
                    attempts
                    <= step.retries
                ):

                    time.sleep(
                        min(
                            0.25
                            * attempts,
                            0.5,
                        )
                    )


            results.append(
                {
                    "step_id":
                        step.step_id,

                    "action":
                        step.action,

                    "success":
                        success,

                    "attempts":
                        attempts,

                    "output":
                        output,

                    "error":
                        error,
                }
            )


            if success:

                completed += 1

                continue


            failure = type(
                "OperatorFailure",
                (),
                {
                    "success":
                        False,

                    "failed_step":
                        step.step_id,

                    "steps": (
                        type(
                            "FailedStep",
                            (),
                            {
                                "success":
                                    False,

                                "step_id":
                                    step.step_id,

                                "error":
                                    error,

                                "attempts":
                                    attempts,
                            },
                        )(),
                    ),
                },
            )()


            try:

                replan = (
                    action_replanner
                    .propose(
                        plan.goal,
                        failure,
                    )
                )

            except Exception as exc:

                replan = {
                    "needs_replan":
                        True,

                    "auto_execute":
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


            operator_memory.record(
                goal=
                    plan.goal,

                success=False,

                steps=
                    len(
                        plan.steps
                    ),

                failed_step=
                    step.step_id,

                lesson=
                    error,

                metadata={
                    "operator_id":
                        operator_id,

                    "dsl_source":
                        plan.source,
                },

                project_id=
                    project_id,
            )


            return OperatorV2Result(
                operator_id=
                    operator_id,

                goal=
                    plan.goal,

                success=False,

                completed_steps=
                    completed,

                total_steps=
                    len(
                        plan.steps
                    ),

                results=
                    tuple(
                        results
                    ),

                failed_step=
                    step.step_id,

                needs_replan=
                    True,

                replan=
                    replan,
            )


        operator_memory.record(
            goal=
                plan.goal,

            success=True,

            steps=
                len(
                    plan.steps
                ),

            metadata={
                "operator_id":
                    operator_id,

                "dsl_source":
                    plan.source,
            },

            project_id=
                project_id,
        )


        return OperatorV2Result(
            operator_id=
                operator_id,

            goal=
                plan.goal,

            success=True,

            completed_steps=
                completed,

            total_steps=
                len(
                    plan.steps
                ),

            results=
                tuple(
                    results
                ),

            needs_replan=False,
        )


    def validate_replan(
        self,
        goal,
        proposal_text,
    ):

        plan = self.validate_proposal(
            goal,
            proposal_text,
        )


        return {
            "valid":
                True,

            "plan":
                plan,

            "auto_execute":
                False,

            "requires_new_approval":
                any(
                    is_interactive(
                        step.action
                    )

                    for step
                    in plan.steps
                ),
        }


    def resolve_target(
        self,
        target,
        *,
        dom=(),
        uia=(),
        screenshot=None,
    ):

        vision = ()


        if screenshot:

            result = (
                vision_runtime
                .analyze(
                    screenshot
                )
            )


            if result.get(
                "success",
                False,
            ):

                vision = tuple(
                    result.get(
                        "analysis",
                        {}
                    )
                    .get(
                        "elements",
                        ()
                    )
                    or ()
                )


        return target_fusion.resolve(
            target,

            dom=dom,

            uia=uia,

            vision=vision,
        )


computer_operator_v2 = (
    ComputerOperatorV2()
)
'''
)


# ============================================================
# MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_operator_v2_prompt("
    not in main_source
):

    main_source += r'''


def jarvis_operator_v2_prompt(
    goal,
    observations=None,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.planner_prompt(
        goal,
        observations,
    )


def jarvis_operator_v2_validate(
    goal,
    proposal_text,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.validate_proposal(
        goal,
        proposal_text,
    )


def jarvis_operator_v2_prepare(
    goal,
    proposal_text,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.prepare_proposal(
        goal,
        proposal_text,
    )


def jarvis_operator_v2_execute(
    plan,
    approval_batch_id=None,
    project_id=None,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.execute(
        plan,

        approval_batch_id=
            approval_batch_id,

        project_id=
            project_id,
    )


def jarvis_operator_v2_validate_replan(
    goal,
    proposal_text,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.validate_replan(
        goal,
        proposal_text,
    )


def jarvis_resolve_ui_target(
    target,
    dom=(),
    uia=(),
    screenshot=None,
):

    from omni.computer_operator_v2 import (
        computer_operator_v2,
    )

    return computer_operator_v2.resolve_target(
        target,

        dom=dom,

        uia=uia,

        screenshot=screenshot,
    )


def jarvis_vision_status():

    from omni.vision_runtime import (
        vision_runtime,
    )

    return vision_runtime.status()


def jarvis_configure_vision_model(
    model,
    enabled=True,
):

    from omni.vision_runtime import (
        vision_runtime,
    )

    return vision_runtime.configure(
        model,

        enabled=
            enabled,
    )


def jarvis_browser_observation_probe():

    from omni.browser_observation_loop import (
        browser_observation_loop,
    )

    return browser_observation_loop.provider_probe()


def jarvis_operator_memory(
    limit=20,
):

    from omni.operator_memory import (
        operator_memory,
    )

    return operator_memory.recent(
        limit
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# WORKSTATION API
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_computer_operator_v2_payload("
    not in app_source
):

    app_source += r'''


def jarvis_computer_operator_v2_payload():

    from omni.browser_observation_loop import (
        browser_observation_loop,
    )

    from omni.core_integrity import (
        verify_protected_core,
    )

    from omni.operator_memory import (
        operator_memory,
    )

    from omni.vision_runtime import (
        vision_runtime,
    )


    try:

        integrity = verify_protected_core()


        return {
            "success":
                True,

            "protected_core":
                integrity.ok,

            "browser_observation":
                browser_observation_loop
                .provider_probe(),

            "vision":
                vision_runtime.status(),

            "recent_operator_memory":
                operator_memory.recent(
                    10
                ),

            "model_dsl_auto_execute":
                False,

            "replan_auto_execute":
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
# TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

from pathlib import Path


import main


from omni.browser_observation_loop import (
    BrowserObservationLoop,
)

from omni.computer_operator_v2 import (
    ComputerOperatorV2,
)

from omni.core_integrity import (
    verify_protected_core,
)

from omni.desktop_state import (
    DesktopSnapshot,
    DesktopState,
)

from omni.operator_dsl import (
    from_dict,
)

from omni.target_fusion import (
    TargetFusion,
)

from omni.vision_runtime import (
    VisionRuntime,
)


class ComputerOperatorV2Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_shell_block(
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


    def test_password_block(
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
                                "browser.observe_fill",

                            "payload": {
                                "url":
                                    "https://example.com",

                                "selector":
                                    'input[type="password"]',

                                "value":
                                    "secret",
                            },
                        }
                    ]
                },
            )


    def test_dom_provider(
        self,
    ):

        result = (
            BrowserObservationLoop()
            .provider_probe()
        )

        self.assertTrue(
            result[
                "success"
            ],
            result,
        )

        self.assertTrue(
            result[
                "has_save"
            ]
        )


    def test_desktop_diff(
        self,
    ):

        before = DesktopSnapshot(
            1,
            (
                "A",
            ),
            (),
            "one",
        )

        after = DesktopSnapshot(
            2,
            (
                "A",
                "B",
            ),
            (),
            "two",
        )


        result = (
            DesktopState.compare(
                before,
                after,
            )
        )


        self.assertEqual(
            result[
                "windows_opened"
            ],
            (
                "B",
            ),
        )


    def test_fusion(
        self,
    ):

        result = (
            TargetFusion()
            .resolve(
                "Save",

                dom=(
                    {
                        "text":
                            "Save",

                        "role":
                            "button",
                    },
                ),

                vision=(
                    {
                        "label":
                            "Save",

                        "confidence":
                            0.3,
                    },
                ),
            )
        )


        self.assertTrue(
            result.resolved
        )

        self.assertEqual(
            result.best.source,
            "dom",
        )


    def test_vision_truthfulness(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            runtime = VisionRuntime(
                Path(
                    tmp
                )
                / "vision.json",

                "http://127.0.0.1:1",
            )


            self.assertFalse(
                runtime.status()[
                    "vision_ready"
                ]
            )


    def test_readonly_execution(
        self,
    ):

        operator = (
            ComputerOperatorV2()
        )


        plan = from_dict(
            "Observe desktop",

            {
                "steps": [
                    {
                        "action":
                            "desktop.observe",

                        "payload":
                            {},
                    }
                ]
            },
        )


        self.assertTrue(
            operator.execute(
                plan
            ).success
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v2_prompt
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v2_execute
            )
        )

        self.assertTrue(
            callable(
                main
                .jarvis_vision_status
            )
        )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# COMPILE
# ============================================================

print()
print("Checking V2 syntax...")


r = run(
    "-m",
    "py_compile",

    str(
        DSL
    ),

    str(
        VISION
    ),

    str(
        FUSION
    ),

    str(
        DESKTOP
    ),

    str(
        BROWSER
    ),

    str(
        MEMORY
    ),

    str(
        OPERATOR
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
# PROTECTED CORE
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
        "from omni.core_integrity "
        "import verify_protected_core; "
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
# DOM PROBE
# ============================================================

print()
print("Checking DOM observation provider...")


r = run(
    "-c",
    (
        "from omni.browser_observation_loop "
        "import browser_observation_loop; "
        "x=browser_observation_loop.provider_probe(); "
        "print(x); "
        "assert x['success']; "
        "assert x['has_save']; "
        "print('DOM observation: PASS')"
    ),
)


if r.returncode:

    print(
        "DOM PROVIDER FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# DESKTOP PROBE
# ============================================================

print()
print("Checking desktop state...")


r = run(
    "-c",
    (
        "from omni.desktop_state import desktop_state; "
        "x=desktop_state.snapshot(); "
        "print('Visible windows:',len(x.window_titles)); "
        "print('Fingerprint:',x.fingerprint[:20]); "
        "assert len(x.fingerprint)==64; "
        "print('Desktop state: PASS')"
    ),
)


if r.returncode:

    print(
        "DESKTOP STATE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# VISION STATUS
# ============================================================

print()
print("Checking vision runtime...")


r = run(
    "-c",
    (
        "from omni.vision_runtime import vision_runtime; "
        "x=vision_runtime.status(); "
        "print('Ollama:',x['ollama_executable']); "
        "print('Reachable:',x['ollama_reachable']); "
        "print('Configured:',x['configured_model']); "
        "print('Vision ready:',x['vision_ready']); "
        "print('Installed:',x['installed_models']); "
        "assert x['automatic_model_download'] is False; "
        "print('Vision truthfulness: PASS')"
    ),
)


if r.returncode:

    print(
        "VISION STATUS FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# DSL SAFETY
# ============================================================

print()
print("Checking DSL safety...")


r = run(
    "-c",
    (
        "from omni.operator_dsl import from_dict; "
        "x=from_dict('observe',"
        "{'steps':[{'action':'desktop.observe','payload':{}}]}); "
        "assert x.steps[0].action=='desktop.observe'; "
        "print('Safe DSL: PASS'); "
        "blocked=False; "
        "\ntry:\n "
        " from_dict('danger',"
        "{'steps':[{'action':'shell.exec','payload':{}}]})\n"
        "except PermissionError:\n blocked=True\n"
        "assert blocked; "
        "print('Shell DSL: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "DSL SAFETY FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# REAL OPERATOR V2
# ============================================================

print()
print("Checking Computer Operator V2...")


r = run(
    "-c",
    (
        "from omni.computer_operator_v2 "
        "import computer_operator_v2; "
        "from omni.operator_dsl import from_dict; "
        "p=from_dict('Observe desktop',"
        "{'steps':[{'action':'desktop.observe','payload':{}}]}); "
        "r=computer_operator_v2.execute(p); "
        "print('Success:',r.success); "
        "print('Completed:',r.completed_steps,'/',r.total_steps); "
        "assert r.success; "
        "print('Computer Operator V2: PASS')"
    ),
)


if r.returncode:

    print(
        "OPERATOR V2 FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# TARGETED TESTS
# ============================================================

print()
print("Running targeted tests...")


r = run(
    "-m",
    "unittest",

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
# FULL REGRESSION
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
# FINAL CORE CHECK
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


print()
print("=" * 80)
print("JARVIS COMPUTER OPERATOR V2 SUCCESS")
print("=" * 80)

print("Safe Brain/model DSL: ACTIVE")
print("DOM before/after observation: ACTIVE")
print("Semantic desktop state: ACTIVE")
print("DOM/UIA/vision fusion: ACTIVE")
print("Ollama vision adapter: ACTIVE")
print("Fake vision: BLOCKED")
print("Operator learning journal: ACTIVE")
print("Failure -> Brain replan: ACTIVE")
print("Automatic replan execution: BLOCKED")
print("Credential automation: BLOCKED")
print("Shell/PowerShell DSL: BLOCKED")
print("Trading execution DSL: BLOCKED")
print("One-time approvals: PRESERVED")
print("Approval batching: PRESERVED")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("NEXT:")
print("JARVIS COMPUTER OPERATOR V3")
print("Real vision model configuration")
print("Screenshot + DOM + UIA fusion")
print("Natural-language target resolution")
print("Live persistent task sessions")
print("Brain -> validated DSL")
print("Replan -> validate -> approve -> resume")
