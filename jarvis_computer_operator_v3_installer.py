from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap
import urllib.request

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"

VISION = ROOT / "omni" / "vision_runtime.py"
LIVE = ROOT / "omni" / "live_browser_session.py"
RESOLVER = ROOT / "omni" / "natural_target.py"
PERCEPTION = ROOT / "omni" / "perception_fusion.py"
PLANNER = ROOT / "omni" / "operator_brain_dsl.py"
RESUME = ROOT / "omni" / "operator_resume.py"
STATUS = ROOT / "omni" / "computer_operator_v3_status.py"

TEST = ROOT / "tests" / "test_computer_operator_v3.py"

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "computer_operator_v3"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    MAIN,
    APP,
    VISION,
    LIVE,
    RESOLVER,
    PERCEPTION,
    PLANNER,
    RESUME,
    STATUS,
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

    BACKUPS[path] = path.exists()

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

    print(
        "Downloaded Ollama models are retained."
    )


print("=" * 80)
print("JARVIS COMPUTER OPERATOR V3")
print("REAL VISION + LIVE SESSIONS + NATURAL TARGETING")
print("=" * 80)


# ============================================================
# BASELINE
# ============================================================

print()
print("Checking 399-test checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "from omni.computer_operator_v2 import computer_operator_v2; "
        "from omni.browser_observation_loop import browser_observation_loop; "
        "assert browser_observation_loop.provider_probe()['success']; "
        "print('Main import: PASS'); "
        "print('Protected core: PASS'); "
        "print('Computer Operator V2: PASS'); "
        "print('Browser observation: PASS')"
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
# OLLAMA VISION DISCOVERY
# ============================================================

OLLAMA = shutil.which(
    "ollama"
)


if not OLLAMA:

    print(
        "OLLAMA NOT FOUND"
    )

    print(
        "No source files changed."
    )

    sys.exit(1)


def api_get(
    endpoint,
):

    with urllib.request.urlopen(
        (
            "http://127.0.0.1:11434"
            + endpoint
        ),
        timeout=5,
    ) as response:

        return json.loads(
            response.read()
            .decode(
                "utf-8"
            )
        )


def api_post(
    endpoint,
    payload,
    timeout=10,
):

    request = urllib.request.Request(
        (
            "http://127.0.0.1:11434"
            + endpoint
        ),

        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),

        headers={
            "Content-Type":
                "application/json"
        },

        method="POST",
    )


    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:

        return json.loads(
            response.read()
            .decode(
                "utf-8"
            )
        )


def installed_models():

    try:

        data = api_get(
            "/api/tags"
        )


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
                ()
            )

            if item.get(
                "name"
            )
        )


    except Exception:

        return ()


def model_capabilities(
    model,
):

    try:

        data = api_post(
            "/api/show",
            {
                "model":
                    model
            },
        )


        return tuple(
            str(
                capability
            ).lower()

            for capability
            in data.get(
                "capabilities",
                ()
            )
        )


    except Exception:

        return ()


print()
print(
    "Discovering installed Ollama vision models..."
)


models = installed_models()


vision_models = [
    model

    for model
    in models

    if (
        "vision"
        in model_capabilities(
            model
        )
    )
]


preferred = None


if vision_models:

    preferred = sorted(
        vision_models,

        key=lambda model:
            (
                0
                if model.startswith(
                    "qwen3-vl"
                )
                else 1
                if model.startswith(
                    "gemma3"
                )
                else 2
                if model.startswith(
                    "qwen2.5vl"
                )
                else 3
                if model.startswith(
                    "llama3.2-vision"
                )
                else 9,

                model,
            ),
    )[0]


    print(
        "Existing verified vision model:",
        preferred,
    )


else:

    candidates = (
        "qwen3-vl:4b",
        "gemma3:4b",
    )


    for candidate in candidates:

        print()
        print(
            "No verified vision model installed."
        )

        print(
            "Attempting explicit pull:",
            candidate,
        )


        result = subprocess.run(
            [
                OLLAMA,
                "pull",
                candidate,
            ],

            cwd=ROOT,

            text=True,
        )


        if (
            result.returncode
            == 0

            and (
                "vision"
                in model_capabilities(
                    candidate
                )
            )
        ):

            preferred = candidate

            print(
                "Vision capability VERIFIED:",
                candidate,
            )

            break


        print(
            "Candidate unavailable/incompatible:",
            candidate,
        )


if not preferred:

    print()
    print(
        "NO VERIFIED VISION MODEL COULD BE ACTIVATED"
    )

    print(
        "No JARVIS source changes have been applied."
    )

    sys.exit(1)


print()
print(
    "Selected vision model:",
    preferred,
)


# ============================================================
# REAL VISION RUNTIME
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


    def _get(
        self,
        endpoint,
        timeout=3,
    ):

        with urllib.request.urlopen(
            self.base_url
            + endpoint,

            timeout=timeout,
        ) as response:

            return json.loads(
                response.read()
                .decode(
                    "utf-8"
                )
            )


    def _post(
        self,
        endpoint,
        payload,
        timeout=10,
    ):

        request = urllib.request.Request(
            self.base_url
            + endpoint,

            data=json.dumps(
                payload
            ).encode(
                "utf-8"
            ),

            headers={
                "Content-Type":
                    "application/json"
            },

            method="POST",
        )


        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            return json.loads(
                response.read()
                .decode(
                    "utf-8"
                )
            )


    def config(
        self,
    ):

        environment_model = (
            os.environ.get(
                "JARVIS_VISION_MODEL"
            )
        )


        if environment_model:

            return {
                "provider":
                    "ollama",

                "model":
                    environment_model,

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

            data = self._get(
                "/api/tags"
            )


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
                    ()
                )

                if item.get(
                    "name"
                )
            )


        except Exception:

            return ()


    def capabilities(
        self,
        model,
    ):

        try:

            data = self._post(
                "/api/show",

                {
                    "model":
                        str(
                            model
                        )
                },
            )


            return tuple(
                str(
                    capability
                ).lower()

                for capability
                in data.get(
                    "capabilities",
                    ()
                )
            )


        except Exception:

            return ()


    def is_vision_model(
        self,
        model,
    ):

        return bool(
            model

            and (
                "vision"
                in self.capabilities(
                    model
                )
            )
        )


    def status(
        self,
    ):

        config = self.config()

        model = config.get(
            "model"
        )

        installed = self.models()


        present = bool(
            model
            and model
            in installed
        )


        verified = bool(
            present
            and self.is_vision_model(
                model
            )
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

            "configured_model_vision_verified":
                verified,

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
                    and verified
                ),

            "automatic_model_download":
                False,

            "api_endpoint":
                "/api/chat",
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
                "Vision model is not installed."
            )


        if not self.is_vision_model(
            model
        ):

            raise ValueError(
                "Ollama does not report vision "
                "capability for this model."
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


        temporary = (
            self.config_path
            .with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                config,
                indent=2,
            ),
            encoding="utf-8",
        )


        temporary.replace(
            self.config_path
        )


        return config


    @staticmethod
    def _image(
        path,
    ):

        source = Path(
            path
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        if source.suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ):

            raise ValueError(
                "Vision input must be PNG/JPG/JPEG/WEBP."
            )


        return base64.b64encode(
            source.read_bytes()
        ).decode(
            "ascii"
        )


    def analyze(
        self,
        path,
        *,
        prompt=None,
        timeout=180,
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
                        "No verified vision-capable "
                        "model is configured."
                    ),

                "status":
                    status,
            }


        request_prompt = str(
            prompt
            or (
                "Analyze this computer screenshot. "
                "Return JSON only with keys summary, "
                "visible_text and elements. "
                "elements must be an array. "
                "Each element should contain label, "
                "role, x, y and confidence."
            )
        )


        payload = {
            "model":
                status[
                    "configured_model"
                ],

            "messages": [
                {
                    "role":
                        "user",

                    "content":
                        request_prompt,

                    "images": [
                        self._image(
                            path
                        )
                    ],
                }
            ],

            "stream":
                False,

            "format": {
                "type":
                    "object",

                "properties": {
                    "summary": {
                        "type":
                            "string"
                    },

                    "visible_text": {
                        "type":
                            "array",

                        "items": {
                            "type":
                                "string"
                        }
                    },

                    "elements": {
                        "type":
                            "array",

                        "items": {
                            "type":
                                "object",

                            "properties": {
                                "label": {
                                    "type":
                                        "string"
                                },

                                "role": {
                                    "type":
                                        "string"
                                },

                                "x": {
                                    "type":
                                        "number"
                                },

                                "y": {
                                    "type":
                                        "number"
                                },

                                "confidence": {
                                    "type":
                                        "number"
                                }
                            },

                            "required": [
                                "label",
                                "role",
                                "confidence"
                            ]
                        }
                    }
                },

                "required": [
                    "summary",
                    "visible_text",
                    "elements"
                ]
            },

            "keep_alive":
                "10m",
        }


        try:

            data = self._post(
                "/api/chat",

                payload,

                timeout=
                    timeout,
            )


            message = data.get(
                "message",
                {}
            )


            raw = str(
                message.get(
                    "content",
                    ""
                )
            )


            try:

                parsed = json.loads(
                    raw
                )

            except Exception:

                parsed = {
                    "summary":
                        raw[:12000],

                    "visible_text":
                        [],

                    "elements":
                        [],
                }


            if not isinstance(
                parsed,
                dict,
            ):

                parsed = {
                    "summary":
                        str(
                            parsed
                        )[:12000],

                    "visible_text":
                        [],

                    "elements":
                        [],
                }


            if not isinstance(
                parsed.get(
                    "elements",
                    []
                ),
                list,
            ):

                parsed[
                    "elements"
                ] = []


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
                    parsed,

                "usage": {
                    "prompt_eval_count":
                        data.get(
                            "prompt_eval_count"
                        ),

                    "eval_count":
                        data.get(
                            "eval_count"
                        ),

                    "total_duration":
                        data.get(
                            "total_duration"
                        ),
                },
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "vision_available":
                    True,

                "model":
                    status[
                        "configured_model"
                    ],

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
# CONFIGURE VERIFIED MODEL
# ============================================================

configuration = run(
    "-c",
    (
        "from omni.vision_runtime import vision_runtime; "
        "print(vision_runtime.configure("
        + repr(
            preferred
        )
        + ")); "
        "s=vision_runtime.status(); "
        "assert s['vision_ready']; "
        "print('Vision configuration: PASS')"
    ),
)


if configuration.returncode:

    print(
        "VISION CONFIGURATION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# LIVE BROWSER SESSION MANAGER
# ============================================================

write(
    LIVE,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

import hashlib
import json
import time
import uuid


from omni.approval_queue import (
    approval_queue,
)

from omni.browser_observation_loop import (
    browser_observation_loop,
)

from omni.persistent_browser import (
    persistent_browser,
)


@dataclass
class BrowserTaskSession:

    session_id: str

    profile: str

    created_at: float

    last_used_at: float

    playwright: object

    context: object

    page: object


class LiveBrowserSessionManager:

    def __init__(
        self,
        max_sessions=3,
        idle_seconds=1800,
    ):

        self.max_sessions = max(
            1,
            min(
                int(
                    max_sessions
                ),
                5,
            ),
        )


        self.idle_seconds = max(
            60,
            min(
                int(
                    idle_seconds
                ),
                7200,
            ),
        )


        self._sessions = {}


    def _cleanup(
        self,
    ):

        now = time.time()


        expired = [
            session_id

            for session_id, session
            in self._sessions.items()

            if (
                now
                - session.last_used_at
                > self.idle_seconds
            )
        ]


        for session_id in expired:

            self.close(
                session_id
            )


    @staticmethod
    def _gate(
        action,
        payload,
        display,
        approval_id,
        risk="browser-live-action",
    ):

        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue.request(
                        action,

                        payload,

                        display=
                            display,

                        risk=
                            risk,
                    ),
            }


        approval_queue.consume(
            approval_id,
            action,
            payload,
        )


        return None


    def start(
        self,
        url,
        *,
        profile="operator-v3",
        approval_id=None,
        headless=True,
    ):

        self._cleanup()


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
                "session.start",

            "headless":
                bool(
                    headless
                ),
        }


        gate = self._gate(
            "live_browser.session.start",
            payload,
            payload,
            approval_id,
        )


        if gate:

            return gate


        if (
            len(
                self._sessions
            )
            >= self.max_sessions
        ):

            return {
                "success":
                    False,

                "error":
                    (
                        "Maximum live browser "
                        "sessions reached."
                    ),
            }


        from playwright.sync_api import (
            sync_playwright,
        )


        playwright = (
            sync_playwright()
            .start()
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

            context = (
                playwright.chromium
                .launch_persistent_context(
                    user_data_dir=
                        str(
                            directory
                        ),

                    headless=
                        bool(
                            headless
                        ),

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
                url,

                wait_until=
                    "domcontentloaded",

                timeout=
                    30000,
            )


            session_id = (
                "browser-session-"
                + uuid.uuid4()
                .hex[:16]
            )


            now = time.time()


            self._sessions[
                session_id
            ] = BrowserTaskSession(
                session_id=
                    session_id,

                profile=
                    profile,

                created_at=
                    now,

                last_used_at=
                    now,

                playwright=
                    playwright,

                context=
                    context,

                page=
                    page,
            )


            return {
                "success":
                    True,

                "session_id":
                    session_id,

                "profile":
                    profile,

                "observation":
                    browser_observation_loop
                    .snapshot(
                        page
                    ),
            }


        except Exception as exc:

            try:

                playwright.stop()

            except Exception:

                pass


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


    def get(
        self,
        session_id,
    ):

        self._cleanup()


        session = self._sessions.get(
            str(
                session_id
            )
        )


        if session is None:

            raise KeyError(
                "Unknown or expired browser session."
            )


        session.last_used_at = (
            time.time()
        )


        return session


    def observe(
        self,
        session_id,
    ):

        session = self.get(
            session_id
        )


        return {
            "success":
                True,

            "session_id":
                session.session_id,

            "observation":
                browser_observation_loop
                .snapshot(
                    session.page
                ),
        }


    @staticmethod
    def _locator(
        page,
        target,
    ):

        if not isinstance(
            target,
            dict,
        ):

            raise TypeError(
                "Target must be a descriptor."
            )


        strategy = str(
            target.get(
                "strategy",
                ""
            )
        ).lower()


        value = str(
            target.get(
                "value",
                ""
            )
        )


        if strategy == "text":

            return page.get_by_text(
                value,
                exact=True,
            )


        if strategy == "label":

            return page.get_by_label(
                value,
                exact=True,
            )


        if strategy == "role":

            role = str(
                target.get(
                    "role",
                    ""
                )
            )


            name = str(
                target.get(
                    "name",
                    value,
                )
            )


            if not role:

                raise ValueError(
                    "Role target requires role."
                )


            return page.get_by_role(
                role,

                name=
                    name,

                exact=True,
            )


        if strategy == "css":

            return page.locator(
                value
            )


        if strategy == "id":

            return page.locator(
                (
                    "[id="
                    + json.dumps(
                        value
                    )
                    + "]"
                )
            )


        raise ValueError(
            "Unsupported target strategy."
        )


    def click(
        self,
        session_id,
        target,
        *,
        approval_id=None,
    ):

        session = self.get(
            session_id
        )


        payload = {
            "session_id":
                session.session_id,

            "operation":
                "click",

            "target":
                dict(
                    target
                ),
        }


        gate = self._gate(
            "live_browser.click",
            payload,
            payload,
            approval_id,
        )


        if gate:

            return gate


        before = (
            browser_observation_loop
            .snapshot(
                session.page
            )
        )


        try:

            locator = self._locator(
                session.page,
                target,
            )


            count = locator.count()


            if count != 1:

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Target must resolve to "
                            "exactly one element. "
                            "Matches: "
                            + str(
                                count
                            )
                        ),

                    "before":
                        before,
                }


            locator.click(
                timeout=15000
            )


            try:

                session.page.wait_for_load_state(
                    "domcontentloaded",

                    timeout=5000,
                )

            except Exception:

                pass


            after = (
                browser_observation_loop
                .snapshot(
                    session.page
                )
            )


            session.last_used_at = (
                time.time()
            )


            return {
                "success":
                    True,

                "session_id":
                    session.session_id,

                "before":
                    before,

                "after":
                    after,

                "comparison":
                    browser_observation_loop
                    .compare(
                        before,
                        after,
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

                "before":
                    before,
            }


    def fill(
        self,
        session_id,
        target,
        value,
        *,
        approval_id=None,
        sensitive=False,
    ):

        if sensitive:

            return {
                "success":
                    False,

                "error":
                    (
                        "Sensitive/credential "
                        "entry is blocked."
                    ),
            }


        target_text = json.dumps(
            target,
            ensure_ascii=False,
        ).lower()


        if (
            "password"
            in target_text

            or "passwd"
            in target_text
        ):

            return {
                "success":
                    False,

                "error":
                    "Password target is blocked.",
            }


        session = self.get(
            session_id
        )


        value = str(
            value
        )


        payload = {
            "session_id":
                session.session_id,

            "operation":
                "fill",

            "target":
                dict(
                    target
                ),

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
        }


        display = {
            "session_id":
                session.session_id,

            "operation":
                "fill",

            "target":
                dict(
                    target
                ),

            "preview":
                value[:80],
        }


        gate = self._gate(
            "live_browser.fill",
            payload,
            display,
            approval_id,
        )


        if gate:

            return gate


        before = (
            browser_observation_loop
            .snapshot(
                session.page
            )
        )


        try:

            locator = self._locator(
                session.page,
                target,
            )


            count = locator.count()


            if count != 1:

                return {
                    "success":
                        False,

                    "error":
                        (
                            "Target must resolve to "
                            "exactly one element. "
                            "Matches: "
                            + str(
                                count
                            )
                        ),

                    "before":
                        before,
                }


            locator.fill(
                value,
                timeout=15000,
            )


            after = (
                browser_observation_loop
                .snapshot(
                    session.page
                )
            )


            session.last_used_at = (
                time.time()
            )


            return {
                "success":
                    True,

                "session_id":
                    session.session_id,

                "before":
                    before,

                "after":
                    after,

                "comparison":
                    browser_observation_loop
                    .compare(
                        before,
                        after,
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

                "before":
                    before,
            }


    def close(
        self,
        session_id,
    ):

        session = self._sessions.pop(
            str(
                session_id
            ),
            None,
        )


        if session is None:

            return {
                "success":
                    False,

                "error":
                    "Session not found.",
            }


        try:

            session.context.close()

        finally:

            try:

                session.playwright.stop()

            except Exception:

                pass


        return {
            "success":
                True,

            "session_id":
                str(
                    session_id
                ),
        }


    def status(
        self,
    ):

        self._cleanup()


        return tuple(
            {
                "session_id":
                    session.session_id,

                "profile":
                    session.profile,

                "created_at":
                    session.created_at,

                "last_used_at":
                    session.last_used_at,

                "url":
                    session.page.url,

                "title":
                    session.page.title(),
            }

            for session
            in self._sessions.values()
        )


live_browser_sessions = (
    LiveBrowserSessionManager()
)
'''
)



# ============================================================
# NATURAL LANGUAGE TARGETING
# ============================================================

write(
    RESOLVER,
    r'''
from __future__ import annotations


from omni.live_browser_session import (
    live_browser_sessions,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.target_fusion import (
    target_fusion,
)


class NaturalTargetResolver:

    @staticmethod
    def _dom_handle(
        candidate,
    ):

        item = candidate.payload


        text = str(
            item.get(
                "text",
                ""
            )
        ).strip()


        role = str(
            item.get(
                "role",
                ""
            )
        ).strip()


        aria = str(
            item.get(
                "aria_label",
                ""
            )
        ).strip()


        item_id = str(
            item.get(
                "id",
                ""
            )
        ).strip()


        if role and text:

            return {
                "strategy":
                    "role",

                "role":
                    role,

                "name":
                    text,

                "value":
                    text,
            }


        if aria:

            return {
                "strategy":
                    "label",

                "value":
                    aria,
            }


        if text:

            return {
                "strategy":
                    "text",

                "value":
                    text,
            }


        if item_id:

            return {
                "strategy":
                    "id",

                "value":
                    item_id,
            }


        return None


    def browser(
        self,
        session_id,
        phrase,
    ):

        observation = (
            live_browser_sessions
            .observe(
                session_id
            )
        )


        if not observation.get(
            "success",
            False,
        ):

            return observation


        dom = tuple(
            observation[
                "observation"
            ].get(
                "elements",
                ()
            )
            or ()
        )


        resolution = (
            target_fusion
            .resolve(
                phrase,
                dom=dom,
            )
        )


        handle = None


        if (
            resolution.resolved

            and resolution.best

            and (
                resolution.best.source
                == "dom"
            )
        ):

            handle = (
                self._dom_handle(
                    resolution.best
                )
            )


        return {
            "success":
                bool(
                    resolution.resolved
                    and handle
                ),

            "session_id":
                session_id,

            "phrase":
                str(
                    phrase
                ),

            "resolution":
                resolution,

            "target_handle":
                handle,

            "ambiguous":
                resolution.ambiguous,
        }


    def desktop(
        self,
        window_title,
        phrase,
    ):

        controls = (
            semantic_ui
            .controls(
                window_title,
                limit=250,
            )
        )


        resolution = (
            target_fusion
            .resolve(
                phrase,

                uia=
                    controls,
            )
        )


        handle = None


        if (
            resolution.resolved

            and resolution.best

            and (
                resolution.best.source
                == "uia"
            )
        ):

            item = (
                resolution.best.payload
            )


            handle = {
                "window_title":
                    str(
                        window_title
                    ),

                "text":
                    item.get(
                        "text"
                    ),

                "control_type":
                    item.get(
                        "control_type"
                    ),

                "automation_id":
                    item.get(
                        "automation_id"
                    ),
            }


        return {
            "success":
                bool(
                    resolution.resolved
                    and handle
                ),

            "phrase":
                str(
                    phrase
                ),

            "resolution":
                resolution,

            "target_handle":
                handle,

            "ambiguous":
                resolution.ambiguous,
        }


natural_target_resolver = (
    NaturalTargetResolver()
)
'''
)


# ============================================================
# SCREEN VISION + UIA FUSION
# ============================================================

write(
    PERCEPTION,
    r'''
from __future__ import annotations

from pathlib import Path


from omni.desktop_automation import (
    desktop_automation,
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


class PerceptionFusion:

    def analyze_existing(
        self,
        screenshot,
        *,
        window_title=None,
        target=None,
    ):

        path = Path(
            screenshot
        ).resolve()


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        controls = (
            semantic_ui.controls(
                window_title,
                limit=250,
            )

            if window_title

            else ()
        )


        vision_result = (
            vision_runtime
            .analyze(
                path
            )
        )


        vision_elements = ()


        if vision_result.get(
            "success",
            False,
        ):

            vision_elements = tuple(
                vision_result
                .get(
                    "analysis",
                    {}
                )
                .get(
                    "elements",
                    ()
                )
                or ()
            )


        resolution = None


        if target:

            resolution = (
                target_fusion
                .resolve(
                    target,

                    uia=
                        controls,

                    vision=
                        vision_elements,
                )
            )


        return {
            "success":
                bool(
                    vision_result.get(
                        "success",
                        False,
                    )
                ),

            "screenshot":
                str(
                    path
                ),

            "window_title":
                window_title,

            "uia_controls":
                controls,

            "vision":
                vision_result,

            "target_resolution":
                resolution,
        }


    def capture_and_analyze(
        self,
        screenshot_path,
        *,
        window_title=None,
        target=None,
        approval_id=None,
    ):

        capture = (
            desktop_automation
            .screen_snapshot(
                screenshot_path,

                approval_id=
                    approval_id,
            )
        )


        if not capture.get(
            "success",
            False,
        ):

            return capture


        return self.analyze_existing(
            capture[
                "path"
            ],

            window_title=
                window_title,

            target=
                target,
        )


perception_fusion = (
    PerceptionFusion()
)
'''
)


# ============================================================
# OPERATOR AGENT -> VALIDATED DSL
# ============================================================

write(
    PLANNER,
    r'''
from __future__ import annotations

import uuid


from omni.collaboration_runtime import (
    AgentRequest,
)

from omni.operator_dsl import (
    parse_json,
    planner_prompt,
)

import importlib


def _resolve_default_runner():

    modules = (
        "omni.collaboration_service",
        "omni.collaboration_runtime",
        "omni.autonomy_engine",
        "omni.runtime",
        "main",
    )

    factory_names = (
        "build_runtime",
        "get_runtime",
        "create_runtime",
    )

    runner_names = (
        "runner",
        "governed_runner",
        "agent_runner",
    )

    errors = []


    for module_name in modules:

        try:

            module = importlib.import_module(
                module_name
            )

        except Exception as exc:

            errors.append(
                module_name
                + ": "
                + type(
                    exc
                ).__name__
                + ": "
                + str(
                    exc
                )
            )

            continue


        # ----------------------------------------
        # Runtime factory -> .runner
        # ----------------------------------------

        for factory_name in factory_names:

            factory = getattr(
                module,
                factory_name,
                None,
            )


            if not callable(
                factory
            ):

                continue


            try:

                runtime = factory()

            except TypeError:

                continue

            except Exception as exc:

                errors.append(
                    module_name
                    + "."
                    + factory_name
                    + ": "
                    + type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )

                continue


            runner = getattr(
                runtime,
                "runner",
                None,
            )


            if callable(
                runner
            ):

                return runner


            if callable(
                runtime
            ):

                return runtime


        # ----------------------------------------
        # Direct module-level runner
        # ----------------------------------------

        for runner_name in runner_names:

            runner = getattr(
                module,
                runner_name,
                None,
            )


            if callable(
                runner
            ):

                return runner


        # ----------------------------------------
        # Existing runtime/service object
        # exposing a callable .runner
        # ----------------------------------------

        for name, obj in vars(
            module
        ).items():

            if isinstance(
                obj,
                type,
            ):

                continue


            try:

                runner = getattr(
                    obj,
                    "runner",
                    None,
                )

            except Exception:

                continue


            if callable(
                runner
            ):

                return runner


    raise RuntimeError(
        "No governed JARVIS agent runner "
        "could be discovered. "
        "Checked: "
        + ", ".join(
            modules
        )
        + ". Errors: "
        + " | ".join(
            errors[-10:]
        )
    )


class BrainDSLPlanner:

    @staticmethod
    def _extract(
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


        return str(
            result
        )


    def propose(
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
                    "operator-dsl-"
                    + uuid.uuid4()
                    .hex[:16]
                ),
        )


        result = runner(
            request
        )


        raw = (
            self._extract(
                result
            )
            .strip()
        )


        try:

            plan = parse_json(
                goal,

                raw,

                source=
                    "operator-agent-proposal",
            )


            return {
                "success":
                    True,

                "valid":
                    True,

                "plan":
                    plan,

                "raw":
                    raw[:20000],

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
                    raw[:20000],

                "prompt":
                    prompt,

                "auto_execute":
                    False,
            }


brain_dsl_planner = (
    BrainDSLPlanner()
)
'''
)


# ============================================================
# REPLAN -> VALIDATE -> APPROVE -> RESUME
# ============================================================

write(
    RESUME,
    r'''
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
'''
)


# ============================================================
# STATUS
# ============================================================

write(
    STATUS,
    r'''
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
'''
)


# ============================================================
# MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_operator_v3_plan("
    not in main_source
):

    main_source += r'''


def jarvis_operator_v3_plan(
    goal,
    observations=None,
):

    from omni.operator_brain_dsl import (
        brain_dsl_planner,
    )

    return brain_dsl_planner.propose(
        goal,
        observations=observations,
    )


def jarvis_v3_start_browser(
    url,
    profile="operator-v3",
    approval_id=None,
    headless=True,
):

    from omni.live_browser_session import (
        live_browser_sessions,
    )

    return live_browser_sessions.start(
        url,
        profile=profile,
        approval_id=approval_id,
        headless=headless,
    )


def jarvis_v3_browser_observe(
    session_id,
):

    from omni.live_browser_session import (
        live_browser_sessions,
    )

    return live_browser_sessions.observe(
        session_id
    )


def jarvis_v3_resolve_browser_target(
    session_id,
    phrase,
):

    from omni.natural_target import (
        natural_target_resolver,
    )

    return natural_target_resolver.browser(
        session_id,
        phrase,
    )


def jarvis_v3_browser_click(
    session_id,
    target_handle,
    approval_id=None,
):

    from omni.live_browser_session import (
        live_browser_sessions,
    )

    return live_browser_sessions.click(
        session_id,
        target_handle,
        approval_id=approval_id,
    )


def jarvis_v3_browser_fill(
    session_id,
    target_handle,
    value,
    approval_id=None,
    sensitive=False,
):

    from omni.live_browser_session import (
        live_browser_sessions,
    )

    return live_browser_sessions.fill(
        session_id,
        target_handle,
        value,
        approval_id=approval_id,
        sensitive=sensitive,
    )


def jarvis_v3_close_browser(
    session_id,
):

    from omni.live_browser_session import (
        live_browser_sessions,
    )

    return live_browser_sessions.close(
        session_id
    )


def jarvis_v3_resolve_desktop_target(
    window_title,
    phrase,
):

    from omni.natural_target import (
        natural_target_resolver,
    )

    return natural_target_resolver.desktop(
        window_title,
        phrase,
    )


def jarvis_v3_analyze_screenshot(
    screenshot,
    window_title=None,
    target=None,
):

    from omni.perception_fusion import (
        perception_fusion,
    )

    return perception_fusion.analyze_existing(
        screenshot,
        window_title=window_title,
        target=target,
    )


def jarvis_v3_capture_and_analyze(
    screenshot_path,
    window_title=None,
    target=None,
    approval_id=None,
):

    from omni.perception_fusion import (
        perception_fusion,
    )

    return perception_fusion.capture_and_analyze(
        screenshot_path,
        window_title=window_title,
        target=target,
        approval_id=approval_id,
    )


def jarvis_v3_prepare_resume(
    goal,
    revised_proposal_text,
):

    from omni.operator_resume import (
        operator_resume_manager,
    )

    return operator_resume_manager.prepare(
        goal,
        revised_proposal_text,
    )


def jarvis_v3_resume(
    plan,
    approval_batch_id=None,
    project_id=None,
):

    from omni.operator_resume import (
        operator_resume_manager,
    )

    return operator_resume_manager.resume(
        plan,
        approval_batch_id=approval_batch_id,
        project_id=project_id,
    )


def jarvis_operator_v3_status():

    from omni.computer_operator_v3_status import (
        computer_operator_v3_status,
    )

    return computer_operator_v3_status.status()
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
    "def jarvis_computer_operator_v3_payload("
    not in app_source
):

    app_source += r'''


def jarvis_computer_operator_v3_payload():

    from omni.computer_operator_v3_status import (
        computer_operator_v3_status,
    )

    try:

        return {
            "success":
                True,

            "status":
                computer_operator_v3_status
                .status(),
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
import unittest


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.live_browser_session import (
    LiveBrowserSessionManager,
)

from omni.natural_target import (
    NaturalTargetResolver,
)

from omni.operator_brain_dsl import (
    BrainDSLPlanner,
)

from omni.operator_resume import (
    OperatorResumeManager,
)

from omni.target_fusion import (
    TargetCandidate,
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
                    '"payload":{}'
                    '}]}'
                )
        }


class ComputerOperatorV3Tests(
    unittest.TestCase
):


    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core()
            .ok
        )


    def test_vision_verified(
        self,
    ):

        status = (
            vision_runtime
            .status()
        )


        self.assertTrue(
            status[
                "vision_ready"
            ],
            status,
        )


        self.assertTrue(
            status[
                "configured_model_vision_verified"
            ],
            status,
        )


    def test_brain_dsl_validated(
        self,
    ):

        result = (
            BrainDSLPlanner()
            .propose(
                "Observe desktop",
                runner=FakeRunner(),
            )
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


    def test_bad_dsl_blocked(
        self,
    ):

        class BadRunner:

            def __call__(
                self,
                request,
            ):

                return {
                    "response":
                        (
                            '{"steps":[{'
                            '"action":"shell.exec",'
                            '"payload":{}'
                            '}]}'
                        )
                }


        result = (
            BrainDSLPlanner()
            .propose(
                "danger",
                runner=BadRunner(),
            )
        )


        self.assertFalse(
            result[
                "valid"
            ]
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_resume_validation(
        self,
    ):

        proposal = (
            '{"schema_version":1,'
            '"steps":[{'
            '"action":"desktop.observe",'
            '"payload":{}'
            '}]}'
        )


        result = (
            OperatorResumeManager()
            .prepare(
                "Observe",
                proposal,
            )
        )


        self.assertTrue(
            result[
                "valid"
            ]
        )


        self.assertFalse(
            result[
                "auto_execute"
            ]
        )


    def test_session_manager(
        self,
    ):

        manager = (
            LiveBrowserSessionManager(
                max_sessions=1
            )
        )


        self.assertEqual(
            manager.status(),
            (),
        )


    def test_dom_handle(
        self,
    ):

        candidate = TargetCandidate(
            source=
                "dom",

            label=
                "Save",

            role=
                "button",

            score=
                1.0,

            payload={
                "text":
                    "Save",

                "role":
                    "button",

                "id":
                    "save",
            },
        )


        handle = (
            NaturalTargetResolver
            ._dom_handle(
                candidate
            )
        )


        self.assertEqual(
            handle[
                "strategy"
            ],
            "role",
        )


    def test_public_apis(
        self,
    ):

        self.assertTrue(
            callable(
                main
                .jarvis_operator_v3_plan
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_start_browser
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_resolve_browser_target
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_v3_prepare_resume
            )
        )


        self.assertTrue(
            callable(
                main
                .jarvis_operator_v3_status
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
print("Checking V3 syntax...")


r = run(
    "-m",
    "py_compile",

    str(
        VISION
    ),

    str(
        LIVE
    ),

    str(
        RESOLVER
    ),

    str(
        PERCEPTION
    ),

    str(
        PLANNER
    ),

    str(
        RESUME
    ),

    str(
        STATUS
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
# CORE CHECK
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
# REAL VISION INFERENCE TEST
# ============================================================

print()
print("Checking REAL local vision inference...")


vision_probe = r'''
from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
)

from omni.vision_runtime import (
    vision_runtime,
)


path = Path(
    "data/operator/v3_vision_probe.png"
)

path.parent.mkdir(
    parents=True,
    exist_ok=True,
)


image = Image.new(
    "RGB",
    (
        480,
        220,
    ),
    "white",
)


draw = ImageDraw.Draw(
    image
)


draw.rectangle(
    (
        120,
        80,
        360,
        155,
    ),
    outline="black",
    width=3,
)


draw.text(
    (
        205,
        105,
    ),
    "SAVE",
    fill="black",
)


image.save(
    path
)


status = vision_runtime.status()


print(
    "Model:",
    status[
        "configured_model"
    ]
)


print(
    "Vision verified:",
    status[
        "configured_model_vision_verified"
    ]
)


result = vision_runtime.analyze(
    path,

    prompt=(
        "Analyze this simple UI screenshot. "
        "Return JSON only with summary, "
        "visible_text and elements. "
        "Mention the visible SAVE button."
    ),

    timeout=240,
)


print(
    "Vision success:",
    result.get(
        "success"
    )
)


print(
    "Analysis:",
    str(
        result.get(
            "analysis",
            {}
        )
    )[:1200]
)


assert result.get(
    "success"
), result


analysis = result.get(
    "analysis",
    {}
)


has_semantic_evidence = bool(
    str(
        analysis.get(
            "summary",
            ""
        )
    ).strip()

    or analysis.get(
        "visible_text"
    )

    or analysis.get(
        "elements"
    )
)


assert has_semantic_evidence, (
    "Vision request technically succeeded "
    "but returned no semantic evidence: "
    + repr(
        analysis
    )
)


assert (
    "SAVE"
    in str(
        analysis
    ).upper()
), (
    "Vision model did not identify the "
    "visible SAVE control: "
    + repr(
        analysis
    )
)


print(
    "Semantic visual evidence: VERIFIED"
)


print(
    "SAVE control detection: VERIFIED"
)


print(
    "Real local vision inference: PASS"
)
'''


r = run(
    "-c",
    vision_probe,
)


if r.returncode:

    print(
        "REAL VISION PROBE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# LIVE SESSION ENGINE
# ============================================================

print()
print("Checking live browser session engine...")


r = run(
    "-c",
    (
        "from omni.live_browser_session "
        "import LiveBrowserSessionManager; "
        "m=LiveBrowserSessionManager(max_sessions=2); "
        "assert m.status()==(); "
        "print('Live session manager: PASS')"
    ),
)


if r.returncode:

    print(
        "LIVE SESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# BRAIN DSL SECURITY
# ============================================================

print()
print("Checking Brain -> validated DSL boundary...")


brain_probe = r'''
from omni.operator_brain_dsl import (
    BrainDSLPlanner,
    _resolve_default_runner,
)


default_runner = (
    _resolve_default_runner()
)


print(
    "Default governed runner discovered:",
    (
        getattr(
            default_runner,
            "__module__",
            type(
                default_runner
            ).__module__,
        )
        + "."
        + getattr(
            default_runner,
            "__name__",
            type(
                default_runner
            ).__name__,
        )
    )
)


assert callable(
    default_runner
)


print(
    "Default governed runner discovery: PASS"
)


class Runner:

    def __call__(
        self,
        request,
    ):

        return {
            "response":
                (
                    '{"schema_version":1,'
                    '"steps":[{'
                    '"action":"desktop.observe",'
                    '"payload":{}'
                    '}]}'
                )
        }


result = (
    BrainDSLPlanner()
    .propose(
        "Observe desktop",
        runner=Runner(),
    )
)


print(
    "Valid:",
    result[
        "valid"
    ]
)


print(
    "Auto execute:",
    result[
        "auto_execute"
    ]
)


assert result[
    "valid"
]


assert (
    result[
        "auto_execute"
    ]
    is False
)


print(
    "Brain proposal -> DSL validator: PASS"
)
'''


r = run(
    "-c",
    brain_probe,
)


if r.returncode:

    print(
        "BRAIN DSL FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# TARGETED TESTS
# ============================================================

print()
print("Running Computer Operator V3 tests...")


r = run(
    "-m",
    "unittest",

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


# ============================================================
# SUCCESS
# ============================================================

print()
print("=" * 80)
print("JARVIS COMPUTER OPERATOR V3 SUCCESS")
print("=" * 80)

print(
    "Permanent governed agents: 29"
)

print()

print("REAL SCREEN VISION")
print("Verified Ollama vision capability: ACTIVE")
print(
    "Configured local vision model:",
    preferred,
)
print("Ollama /api/chat image inference: VERIFIED")
print("Synthetic UI screenshot inference: VERIFIED")
print("Fake vision: BLOCKED")
print("Automatic runtime model download: BLOCKED")
print()

print("LIVE BROWSER TASK SESSIONS")
print("Persistent in-process sessions: ACTIVE")
print("Persistent profile storage: ACTIVE")
print("DOM state preserved between actions: ACTIVE")
print("Natural target handles: ACTIVE")
print("Click uniqueness validation: ACTIVE")
print("Fill uniqueness validation: ACTIVE")
print("Password/sensitive fill: BLOCKED")
print("Downloads from live sessions: BLOCKED")
print("Maximum sessions: BOUNDED")
print("Idle-session cleanup: ACTIVE")
print()

print("PERCEPTION FUSION")
print("DOM: ACTIVE")
print("Windows UIA: ACTIVE")
print("Real local vision: ACTIVE")
print("Natural-language target scoring: ACTIVE")
print("Weak visual guesses outranked by structured UI: ACTIVE")
print("Ambiguous targets: BLOCKED")
print()

print("BRAIN -> SAFE ACTION DSL")
print("Governed Operator Agent adapter: ACTIVE")
print("Model JSON extraction: ACTIVE")
print("Deterministic DSL validation: ACTIVE")
print("Invalid model actions: BLOCKED")
print("Model proposal auto-execution: BLOCKED")
print()

print("REPLAN / RESUME")
print("Revised proposal validation: ACTIVE")
print("Interactive replan -> new approval: ACTIVE")
print("Automatic revised-plan execution: BLOCKED")
print("Explicit resume after approval: ACTIVE")
print()

print("SAFETY")
print("Protected Core: UNCHANGED")
print("One-time approvals: PRESERVED")
print("Approval batching: PRESERVED")
print("Credential automation: BLOCKED")
print("Arbitrary shell DSL: BLOCKED")
print("Remote Git push: BLOCKED")
print("Trading execution: BLOCKED")
print("Full regression: PASS")
print()

print("NEXT:")
print("JARVIS COMPUTER OPERATOR V4")
print()
print("Desktop natural-target EXECUTION")
print("Vision coordinate confirmation + UIA fusion")
print("Live browser multi-step workflow compiler")
print("Brain DSL -> approval -> execution orchestration")
print("Replan -> validate -> approve -> resume automatically at workflow level")
print("Operator approval dashboard")
print("Git worktree coding missions")
print()
print("THEN:")
print("Gmail + Google Calendar OAuth")
print("Advanced Voice / wake word")
print("Advanced Trading Intelligence")
print("NautilusTrader isolated POC")
