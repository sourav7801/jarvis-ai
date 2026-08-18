# ============================================================
# JARVIS MAIN CONTROLLER
# FINAL V2.7
# ============================================================

import json
import re
import threading
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    ISOLATED_AGENT_NAMES,
    MAX_PARALLEL_TASKS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
    WORKER_TIMEOUT_SECONDS,
)

from omni.runtime import audit_event
from omni.agent_registry import (
    AgentIsolation,
    AgentRegistry,
    AgentRequest,
    default_agent_specs,
)
from omni.isolated_runner import IsolatedAgentRunner, WorkerLimits
from omni.contracts import Plan
from omni.dispatch import StepDispatcher
from omni.orchestrator import DurableOrchestrator
from omni.runtime import get_audit_store
from omni.model_provider import GenerationRequest, OllamaProvider
from omni.model_router import (
    ModelRequest,
    ModelRouter,
    ModelTier,
    PrivacyLevel,
    default_profiles,
)
from omni.mission_control import MissionControl, is_mission_request
from agents.universal_operator_agent import is_operator_request


# ============================================================
# TOOLS
# ============================================================

from tools.registry import (
    get_tool,
    list_tools,
)

from tools.tool_schema import (
    validate_tool_call,
)

from tools.safety import (
    authorize_tool,
    verify_tool_postcondition,
)

from tools.capabilities import capabilities_for

from tools.memory import (
    remember,
    recall,
    show_memory,
    forget,
)
from omni.brain import brain


# ============================================================
# HEAD AGENT
# ============================================================

try:
    from agents.head_agent import head_agent
except Exception as e:
    head_agent = None
    print(
        f"JARVIS HEAD AGENT DEBUG > {e}"
    )


# ============================================================
# VOICE SYSTEM
# ============================================================

try:
    from voice import listen, speak

except Exception:
    listen = None
    speak = None


# Try to find an optional speech-stop function.
# Different voice.py versions may expose different names.

_stop_speech_function = None

try:
    from voice import stop_speaking as _stop_speech_function
except Exception:
    pass

if _stop_speech_function is None:
    try:
        from voice import stop as _stop_speech_function
    except Exception:
        pass

if _stop_speech_function is None:
    try:
        from voice import cancel_speech as _stop_speech_function
    except Exception:
        pass


# ============================================================
# CONFIGURATION
# ============================================================

# ============================================================
# COMMANDS
# ============================================================

EXIT_COMMANDS = {
    "exit",
    "quit",
    "shutdown",
    "bye",
    "stop",
}

MAIN_MENU_COMMANDS = {
    "main menu",
    "go to main menu",
    "return to main menu",
    "back to main menu",
    "exit voice mode",
    "leave voice mode",
    "go back",
}


# ============================================================
# SPEECH STATE
# ============================================================

_speech_lock = threading.Lock()

_speech_generation = 0

_speech_thread = None


def _brain_route_override(existing_route, request):
    """
    Upgrade only generic chat fallback to a JarvisBrain specialist.

    Deterministic tools, structured actions, and already-selected
    specialist routes remain authoritative.
    """
    try:
        decision = brain.decide(str(request or ""))
    except Exception:
        return existing_route

    if not isinstance(existing_route, str):
        return existing_route

    current = existing_route.strip().lower()

    if current not in {"", "chat", "conversation"}:
        return existing_route

    selected = str(decision.primary_agent or "").strip()

    if not selected or selected == "chat":
        return existing_route

    return selected

def _increment_speech_generation():
    global _speech_generation

    with _speech_lock:
        _speech_generation += 1
        return _speech_generation


def cancel_speech():
    """
    Invalidate any pending/new speech.

    If voice.py exposes a real stop function, use it.
    Otherwise we still prevent queued speech from starting.
    """

    global _speech_generation

    with _speech_lock:
        _speech_generation += 1

    if _stop_speech_function:

        try:
            _stop_speech_function()

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > "
                f"Speech stop failed: {e}"
            )


def _speak_worker(
    text,
    generation,
):
    """
    Speak only if this speech request is still current.
    """

    if not speak:
        return

    with _speech_lock:

        if generation != _speech_generation:
            return

    try:

        speak(text)

    except Exception as e:

        print(
            f"\nJARVIS VOICE DEBUG > {e}"
        )


def speak_async(text):
    """
    Start speech without blocking the input loop.

    A new speech request invalidates the previous queued
    request so JARVIS does not pile up responses.
    """

    global _speech_thread
    global _speech_generation

    if not speak:
        return

    if not text:
        return

    text = str(text).strip()

    if not text:
        return

    generation = _increment_speech_generation()

    _speech_thread = threading.Thread(
        target=_speak_worker,
        args=(
            text,
            generation,
        ),
        daemon=True,
    )

    _speech_thread.start()


def shorten_for_speech(message):

    if not message:
        return ""

    text = str(
        message
    ).strip()

    if not text:
        return ""

    lower = text.lower()

    # --------------------------------------------------------
    # Dataset reports
    # --------------------------------------------------------

    if "dataset analysis" in lower:

        has_excel = (
            "excel report:" in lower
        )

        has_html = (
            "html dashboard:" in lower
        )

        if has_excel and has_html:

            return (
                "Dataset analysis is complete. "
                "I generated the Excel report "
                "and HTML dashboard."
            )

        if has_excel:

            return (
                "Dataset analysis is complete. "
                "I generated the Excel report."
            )

        if has_html:

            return (
                "Dataset analysis is complete. "
                "I generated the HTML dashboard."
            )

        return (
            "Dataset analysis is complete."
        )

    # --------------------------------------------------------
    # Research
    # --------------------------------------------------------

    if (
        "latest headlines" in lower
        or
        "research agent" in lower
    ):

        return (
            "I found the requested research "
            "information. The full results are "
            "shown in the terminal."
        )

    # --------------------------------------------------------
    # Long responses
    # --------------------------------------------------------

    if len(text) > 500:

        parts = re.split(
            r"(?<=[.!?])\s+",
            text,
        )

        if parts:

            first = parts[0].strip()

            if (
                first
                and len(first) <= 240
            ):

                return (
                    first
                    +
                    " The full response is "
                    "shown in the terminal."
                )

        return (
            "The full response is "
            "shown in the terminal."
        )

    return text


def say(
    message,
    speak_text=None,
):

    if message is None:
        return

    message = str(message)

    print(
        f"\nJARVIS > {message}"
    )

    if not speak:
        return

    spoken = (
        speak_text
        if speak_text is not None
        else shorten_for_speech(
            message
        )
    )

    speak_async(
        spoken
    )


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):

    return " ".join(
        str(
            text or ""
        )
        .strip()
        .lower()
        .split()
    )


# ============================================================
# COMMAND CHECKS
# ============================================================

def is_exit_command(text):

    return (
        normalize(text)
        in EXIT_COMMANDS
    )


def is_main_menu_command(text):

    value = normalize(text)

    if value in MAIN_MENU_COMMANDS:
        return True

    return any(
        phrase in value
        for phrase in [
            "go to main menu",
            "return to main menu",
            "back to main menu",
            "exit voice mode",
            "leave voice mode",
        ]
    )


# ============================================================
# TOOL HELPERS
# ============================================================

def tool_exists(name):

    try:

        return name in list_tools()

    except Exception:

        return False


def resolve_application(name):

    value = normalize(name)

    aliases = {
        "notebook": "notepad",
        "note pad": "notepad",
        "calc": "calculator",
    }

    return aliases.get(
        value,
        value,
    )


def clean_tool_arguments(
    tool_name,
    arguments,
):

    if not isinstance(
        arguments,
        dict,
    ):

        arguments = {}

    try:

        tool_info = (
            list_tools().get(
                tool_name
            )
        )

    except Exception:

        return arguments

    if not tool_info:
        return {}

    accepted = set()

    schema = tool_info.get(
        "schema",
        {},
    )

    if isinstance(
        schema,
        dict,
    ):

        properties = schema.get(
            "properties",
            {},
        )

        if isinstance(
            properties,
            dict,
        ):

            accepted.update(
                properties.keys()
            )

    argument_schema = tool_info.get(
        "arguments",
        {},
    )

    if isinstance(
        argument_schema,
        dict,
    ):

        accepted.update(
            argument_schema.keys()
        )

    if accepted:

        arguments = {
            key: value

            for key, value
            in arguments.items()

            if key in accepted
        }

    if tool_name in {
        "open_application",
        "close_application",
    }:

        application = arguments.get(
            "application"
        )

        if application:

            arguments[
                "application"
            ] = resolve_application(
                application
            )

    return arguments


# ============================================================
# DATA AGENT STATUS
# ============================================================

def data_agent_has_pending_selection():

    try:

        from agents.data_agent import (
            has_pending_selection,
        )

        return bool(
            has_pending_selection()
        )

    except Exception:

        return False


# ============================================================
# WINDOWS PATH
# ============================================================

def extract_windows_path(text):

    if not text:
        return None

    match = re.search(
        r'["\']([A-Za-z]:\\[^"\']+)["\']',
        text,
        re.IGNORECASE,
    )

    if match:

        return (
            match.group(1)
            .strip()
            .rstrip(
                " .,;:)"
            )
        )

    match = re.search(
        r'([A-Za-z]:\\[^<>:"|?*\r\n]+?\.(?:csv|xlsx|xls|json|parquet))',
        text,
        re.IGNORECASE,
    )

    if match:

        return (
            match.group(1)
            .strip()
            .rstrip(
                " .,;:)"
            )
        )

    match = re.search(
        r'([A-Za-z]:\\[^\r\n]+)',
        text,
        re.IGNORECASE,
    )

    if not match:
        return None

    value = (
        match.group(1)
        .strip()
    )

    markers = [
        " and create ",
        " and make ",
        " and generate ",
        " with ",
        " then ",
        " and show ",
    ]

    lower = value.lower()

    for marker in markers:

        position = lower.find(
            marker
        )

        if position != -1:

            value = value[
                :position
            ]

            break

    return value.rstrip(
        " .,;:)"
    )


# ============================================================
# DATA REQUEST DETECTION
# ============================================================

def looks_like_data_request(text):

    value = normalize(text)

    if not value:
        return False

    phrases = [

        "analyze the dataset",
        "analyse the dataset",

        "analyze this dataset",
        "analyse this dataset",

        "analyze the data",
        "analyse the data",

        "analyze this data",
        "analyse this data",

        "analyze my data",
        "analyse my data",

        "dataset analysis",
        "data analysis",

        "analyze spreadsheet",
        "analyse spreadsheet",

        "analyze spreadsheets",
        "analyse spreadsheets",

        "create a data report",
        "make a data report",

        "create an excel report",
        "make an excel report",

        "create an excel dashboard",
        "make an excel dashboard",

        "create a dashboard",
        "make a dashboard",

        "create an html dashboard",
        "make an html dashboard",

        "build a dashboard",
        "build an html dashboard",

    ]

    if any(
        phrase in value
        for phrase in phrases
    ):

        return True

    if (
        re.search(
            r"\b(analyze|analyse)\b",
            value,
        )
        and
        extract_windows_path(
            text
        )
    ):

        return True

    if any(
        extension in value
        for extension in [
            ".csv",
            ".xlsx",
            ".xls",
            ".json",
            ".parquet",
        ]
    ):

        return any(
            word in value
            for word in [
                "analyze",
                "analyse",
                "report",
                "dashboard",
                "dataset",
                "data",
            ]
        )

    return False


# ============================================================
# HEAD AGENT
# ============================================================

def detect_department(text):

    if head_agent is None:
        return None

    try:

        department = (
            head_agent.detect_department(
                text
            )
        )
        department = _brain_route_override(department, text)

        if department:

            department = normalize(
                department
            )

            print(
                "\nJARVIS HEAD AGENT > "
                f"{department}"
            )

            return department

    except Exception as e:

        print(
            "\nJARVIS HEAD AGENT DEBUG > "
            f"{e}"
        )

    return None


# ============================================================
# DATA AGENT
# ============================================================

def run_data_agent(text):

    try:

        from agents.data_agent import (
            analyze,
        )

    except Exception as e:

        return {
            "exit": False,
            "menu": False,
            "message": (
                "The Data Agent could "
                f"not be loaded: {e}"
            ),
        }

    try:

        result = analyze(
            text
        )

        if isinstance(
            result,
            dict,
        ):

            message = (
                result.get("message")
                or
                result.get("response")
                or
                str(result)
            )

        else:

            message = str(
                result
            )

        return {
            "exit": False,
            "menu": False,
            "message": message,
        }

    except Exception as e:

        print(
            "\nJARVIS DATA AGENT DEBUG > "
            f"{type(e).__name__}: {e}"
        )

        return {
            "exit": False,
            "menu": False,
            "message": (
                "The Data Agent encountered "
                f"an error: {e}"
            ),
        }


# ============================================================
# GENERIC AGENTS
# ============================================================

_unknown_isolated_agents = ISOLATED_AGENT_NAMES - {
    spec.name for spec in default_agent_specs()
}
if _unknown_isolated_agents:
    raise RuntimeError(
        "Unknown isolated agent configuration: "
        + ", ".join(sorted(_unknown_isolated_agents))
    )

AGENT_SPECS = tuple(
    replace(spec, isolation=AgentIsolation.ISOLATED_PROCESS)
    if spec.name in ISOLATED_AGENT_NAMES
    else spec
    for spec in default_agent_specs()
)
AGENT_REGISTRY = AgentRegistry(
    AGENT_SPECS,
    isolated_runner=IsolatedAgentRunner(
        limits=WorkerLimits(timeout_seconds=WORKER_TIMEOUT_SECONDS)
    ),
)
MISSION_CONTROL = MissionControl(AGENT_REGISTRY)

# Compatibility view retained for dashboard diagnostics and older integrations.
AGENT_MAP = {
    spec.name: (
        spec.module,
        spec.entrypoint,
        spec.label,
    )
    for spec in AGENT_SPECS
}


def route_agent(
    department,
    text,
):

    department = normalize(
        department
    )

    if department not in AGENT_MAP:
        return None

    spec = AGENT_REGISTRY.get(
        department
    )

    print(
        f"\n{spec.label} > "
        "Processing request"
    )

    response = AGENT_REGISTRY.execute(
        AgentRequest(
            department,
            text,
        )
    )

    return {
        "exit": False,
        "menu": False,
        "message": response.message,
    }


# ============================================================
# DETERMINISTIC ROUTER
# ============================================================

def deterministic_route(text):

    value = normalize(text)

    if not value:
        return None

    if is_main_menu_command(value):

        return {
            "action":
                "main_menu"
        }

    if is_exit_command(value):

        return {
            "action":
                "exit"
        }

    # Data always wins over generic AI routing.
    if looks_like_data_request(text):

        return {
            "action":
                "department",
            "department":
                "data",
        }

    # Time.
    if any(
        phrase in value
        for phrase in [
            "what time is it",
            "what is the time",
            "what's the time",
            "current time",
            "tell me the time",
            "time now",
        ]
    ):

        if tool_exists(
            "current_time"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "current_time",
                "arguments":
                    {},
            }

    # System.
    if any(
        phrase in value
        for phrase in [
            "system information",
            "system info",
            "computer specs",
            "computer details",
            "pc specs",
            "system specs",
            "computer information",
        ]
    ):

        if tool_exists(
            "system_info"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "system_info",
                "arguments":
                    {},
            }

    # Notepad.
    if any(
        phrase in value
        for phrase in [
            "open notepad",
            "open notebook",
            "start notepad",
            "launch notepad",
        ]
    ):

        if tool_exists(
            "open_application"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "open_application",
                "arguments": {
                    "application":
                        "notepad"
                },
            }

        if tool_exists(
            "open_notepad"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "open_notepad",
                "arguments":
                    {},
            }

    # Calculator.
    if any(
        phrase in value
        for phrase in [
            "open calculator",
            "open calc",
            "start calculator",
            "launch calculator",
        ]
    ):

        if tool_exists(
            "open_application"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "open_application",
                "arguments": {
                    "application":
                        "calculator"
                },
            }

        if tool_exists(
            "open_calculator"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "open_calculator",
                "arguments":
                    {},
            }

    # Close Notepad.
    if any(
        phrase in value
        for phrase in [
            "close notepad",
            "close notebook",
        ]
    ):

        if tool_exists(
            "close_application"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "close_application",
                "arguments": {
                    "application":
                        "notepad"
                },
            }

    # Close Calculator.
    if any(
        phrase in value
        for phrase in [
            "close calculator",
            "close calc",
        ]
    ):

        if tool_exists(
            "close_application"
        ):

            return {
                "action":
                    "tool",
                "tool":
                    "close_application",
                "arguments": {
                    "application":
                        "calculator"
                },
            }

    # Memory.
    if any(
        phrase in value
        for phrase in [
            "show memory",
            "what do you remember",
            "show my memory",
        ]
    ):

        return {
            "action":
                "memory",
            "operation":
                "show_memory",
        }

    return None


# ============================================================
# OLLAMA
# ============================================================

def build_tool_description():

    try:

        tools = list_tools()

    except Exception:

        return ""

    lines = []

    for name, info in tools.items():

        if isinstance(
            info,
            dict,
        ):

            lines.append(
                f"- {name}: "
                f"{info.get('description', '')}"
            )

    return "\n".join(
        lines
    )


def ai_route(text):

    try:

        prompt = f"""
You are JARVIS, a local Windows AI assistant.

Return ONLY valid JSON.

AVAILABLE TOOLS:

{build_tool_description()}

RULES:

1. Never invent tool names.
2. Never invent arguments.
3. Normal conversation = chat.
4. One available tool = tool.
5. Multiple independent tools = tasks.
6. Dataset requests are handled by the Data Agent.
7. Never invent a data tool.
8. Never invent a research tool.
9. Never invent a coding tool.
10. Never invent an office tool.
11. Never treat main menu as an application.

CHAT:
{{"action":"chat","response":"answer"}}

TOOL:
{{"action":"tool","tool":"tool_name","arguments":{{}}}}

TASKS:
{{"action":"tasks","tasks":[]}}

EXIT:
{{"action":"exit"}}

USER REQUEST:
{text}
"""

        router = ModelRouter(
            default_profiles(OLLAMA_MODEL)
        )

        routing = router.route(
            ModelRequest(
                task_type="tool_routing",
                minimum_tier=ModelTier.REFLEX,
                required_context_tokens=max(1, len(prompt) // 4),
                privacy=PrivacyLevel.LOCAL_ONLY,
                required_capabilities=frozenset({"tool_routing"}),
            )
        )

        if routing.profile is None:
            return None

        raw = OllamaProvider(OLLAMA_URL).generate(
            GenerationRequest(
                prompt=prompt,
                profile=routing.profile,
                timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
                json_mode=True,
            )
        ).text

        print(
            "\nJARVIS AI DEBUG > "
            "Raw response:"
        )

        print(
            raw
        )

        return raw

    except Exception as e:

        print(
            f"\nJARVIS AI DEBUG > {e}"
        )

        return None


# ============================================================
# JSON
# ============================================================

def extract_json(raw):

    if not raw:
        return None

    raw = str(
        raw
    ).strip()

    try:

        return json.loads(
            raw
        )

    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")

    if (
        start != -1
        and
        end > start
    ):

        try:

            return json.loads(
                raw[
                    start:
                    end + 1
                ]
            )

        except Exception:
            pass

    return None


def parse_decision(raw):

    data = extract_json(
        raw
    )

    if not isinstance(
        data,
        dict,
    ):

        return None

    action = data.get(
        "action"
    )

    if action in {
        "exit",
        "main_menu",
    }:

        return {
            "action":
                action
        }

    if action == "chat":

        return {
            "action":
                "chat",
            "response":
                str(
                    data.get(
                        "response",
                        "",
                    )
                ),
        }

    if action == "tool":

        tool_name = data.get(
            "tool"
        )

        if tool_name not in list_tools():
            return None

        return {
            "action":
                "tool",
            "tool":
                tool_name,
            "arguments":
                clean_tool_arguments(
                    tool_name,
                    data.get(
                        "arguments",
                        {},
                    ),
                ),
        }

    if action == "tasks":

        tasks = data.get(
            "tasks",
            [],
        )

        if not isinstance(
            tasks,
            list,
        ):

            return None

        return {
            "action":
                "tasks",
            "tasks":
                tasks,
        }

    return None


# ============================================================
# MEMORY
# ============================================================

def execute_memory(
    decision,
):

    operation = decision.get(
        "operation"
    )

    if operation == "remember":

        result = remember(
            decision.get("key"),
            decision.get("value"),
        )

    elif operation == "recall":

        result = recall(
            decision.get("key")
        )

    elif operation == "show_memory":

        result = show_memory()

    elif operation == "forget":

        result = forget(
            decision.get("key")
        )

    else:

        return (
            "I couldn't understand "
            "that memory request."
        )

    if isinstance(
        result,
        dict,
    ):

        return result.get(
            "message",
            str(result),
        )

    return str(
        result
    )


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(
    decision,
    show_header=True,
):

    tool_name = decision.get(
        "tool"
    )

    arguments = clean_tool_arguments(
        tool_name,
        decision.get(
            "arguments",
            {},
        ),
    )

    if show_header:

        print(
            f"\nJARVIS > Tool: "
            f"{tool_name}"
        )

    tool = get_tool(
        tool_name
    )

    if not tool:

        return (
            f"Unknown tool: "
            f"{tool_name}"
        )

    validation = validate_tool_call(
        tool_name,
        arguments,
    )

    if not validation.get(
        "valid",
        False,
    ):

        audit_event(
            "tool",
            str(tool_name),
            "REJECTED",
            {"reason": "schema_validation"},
        )

        return (
            "Tool call rejected: "
            +
            validation.get(
                "message",
                "Validation failed.",
            )
        )

    print(
        f"JARVIS > Risk: "
        f"{tool.get('risk', 'UNKNOWN')}"
    )

    safety = authorize_tool(
        tool_name,
        tool.get("risk", "CRITICAL"),
        capabilities_for(tool_name),
    )

    if not safety.allowed:
        audit_event(
            "tool",
            str(tool_name),
            "BLOCKED",
            {"risk": safety.risk},
        )
        return f"Tool call blocked: {safety.reason}"

    if arguments:

        print(
            f"JARVIS > Arguments: "
            f"{arguments}"
        )

    try:

        result = tool[
            "function"
        ](
            **arguments
        )

        verification = verify_tool_postcondition(
            tool_name,
            arguments,
            result,
        )

        if not verification["verified"]:
            audit_event(
                "tool",
                str(tool_name),
                "FAILED_VERIFICATION",
                {"risk": safety.risk},
            )
            return (
                "Tool execution could not be verified: "
                f"{verification['message']}"
            )

        audit_event(
            "tool",
            str(tool_name),
            "SUCCEEDED",
            {"risk": safety.risk},
        )

        return verification["message"]

    except Exception as e:

        audit_event(
            "tool",
            str(tool_name),
            "FAILED",
            {"error_type": type(e).__name__},
        )

        return (
            "Tool execution failed: "
            f"{e}"
        )


# ============================================================
# MULTI TASK
# ============================================================

def execute_tasks(
    decision,
):

    tasks = decision.get(
        "tasks",
        [],
    )

    valid_tasks = []

    for task in tasks:

        if not isinstance(
            task,
            dict,
        ):
            continue

        if task.get(
            "action"
        ) != "tool":

            continue

        tool_name = task.get(
            "tool"
        )

        if tool_name not in list_tools():
            continue

        task[
            "arguments"
        ] = clean_tool_arguments(
            tool_name,
            task.get(
                "arguments",
                {},
            ),
        )

        valid_tasks.append(
            task
        )

    if not valid_tasks:

        return (
            "No valid tasks were provided."
        )

    results = {}

    with ThreadPoolExecutor(

        max_workers=min(
            MAX_PARALLEL_TASKS,
            len(valid_tasks),
        )

    ) as executor:

        future_map = {

            executor.submit(
                execute_tool,
                task,
                False,
            ):
                index

            for index, task
            in enumerate(
                valid_tasks
            )

        }

        for future in as_completed(
            future_map
        ):

            index = future_map[
                future
            ]

            try:

                results[
                    index
                ] = future.result()

            except Exception as e:

                results[
                    index
                ] = (
                    f"Task failed: {e}"
                )

    return "\n".join(

        f"{task.get('tool')}: "
        f"{results.get(index, 'No result.')}"

        for index, task
        in enumerate(
            valid_tasks
        )
    )


def execute_plan(plan: Plan) -> Plan:
    """Execute a validated durable plan through canonical agent/tool boundaries."""
    dispatcher = StepDispatcher(
        AGENT_REGISTRY,
        lambda decision: execute_tool(decision, False),
    )
    return DurableOrchestrator(
        get_audit_store(),
        dispatcher,
        max_workers=MAX_PARALLEL_TASKS,
    ).run(plan)


# ============================================================
# PROCESS COMMAND
# ============================================================

def process_command(
    text,
):

    # Selective durable-memory capture
    jarvis_capture_salient_input(text)

    # Deterministic memory commands
    _memory_answer = jarvis_memory_command_answer(text)
    if _memory_answer is not None:
        return _memory_answer

    # Explicit autonomous mission commands
    _mission_answer = jarvis_mission_command_answer(text)
    if _mission_answer is not None:
        return _mission_answer

    if not text:

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                None,
        }

    # A new command invalidates old queued speech.
    cancel_speech()

    audit_event(
        "command",
        "received",
        "RECEIVED",
        {"character_count": len(str(text))},
    )

    # --------------------------------------------------------
    # UNIVERSAL OPERATOR / EXPLICIT MULTI-AGENT MISSION
    # --------------------------------------------------------

    if is_operator_request(text) or is_mission_request(text):
        mission = MISSION_CONTROL.create_mission(str(text))
        return {
            "exit": False,
            "menu": False,
            "action": "open_mission",
            "source": "universal_operator",
            "message": (
                f"Universal Operator completed a supervised local mission packet with "
                f"{len(mission['selected_agents'])} specialists and "
                f"{len(mission['artifacts'])} artifacts. External actions remain approval-locked."
            ),
            "mission": mission,
        }

    # --------------------------------------------------------
    # MAIN MENU
    # --------------------------------------------------------

    if is_main_menu_command(
        text
    ):

        return {
            "exit":
                False,
            "menu":
                True,
            "message":
                "Returning to the main menu.",
        }

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    if is_exit_command(
        text
    ):

        cancel_speech()

        return {
            "exit":
                True,
            "menu":
                False,
            "message":
                "Shutting down.",
        }

    # --------------------------------------------------------
    # DATA SELECTION
    # --------------------------------------------------------

    if data_agent_has_pending_selection():

        return run_data_agent(
            text
        )

    # --------------------------------------------------------
    # DATA REQUESTS FIRST
    # --------------------------------------------------------

    if looks_like_data_request(
        text
    ):

        return run_data_agent(
            text
        )

    # --------------------------------------------------------
    # DETERMINISTIC ROUTING BEFORE CATCH-ALL CHAT
    # --------------------------------------------------------

    decision = deterministic_route(
        text
    )

    # --------------------------------------------------------
    # HEAD AGENT FALLBACK
    # --------------------------------------------------------

    department = detect_department(
        text
    )

    # JARVIS Brain automatic multi-agent collaboration
    _collaboration_answer = jarvis_auto_collaboration_answer(text)
    if _collaboration_answer is not None:
        return _collaboration_answer

    audit_event(
        "router",
        "department_selected",
        "SUCCEEDED",
        {"department": department},
    )

    if not decision and department in AGENT_MAP:

        result = route_agent(
            department,
            text,
        )

        if result:

            return result

    # --------------------------------------------------------
    # DETERMINISTIC
    # --------------------------------------------------------

    if decision:

        print(
            "\nJARVIS ROUTER > "
            "Deterministic"
        )

        print(
            f"JARVIS ROUTER > "
            f"{decision}"
        )

    # --------------------------------------------------------
    # AI FALLBACK
    # --------------------------------------------------------

    if not decision:

        print(
            "\nJARVIS ROUTER > AI"
        )

        decision = parse_decision(
            ai_route(
                text
            )
        )

        if decision:

            print(
                "\nJARVIS ROUTER > "
                "AI Parsed"
            )

            print(
                f"JARVIS ROUTER > "
                f"{decision}"
            )

    if not decision:

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                (
                    "I couldn't understand "
                    "that request."
                ),
        }

    action = decision.get(
        "action"
    )

    if action == "main_menu":

        return {
            "exit":
                False,
            "menu":
                True,
            "message":
                "Returning to the main menu.",
        }

    if action == "exit":

        cancel_speech()

        return {
            "exit":
                True,
            "menu":
                False,
            "message":
                "Shutting down.",
        }

    if action == "memory":

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                execute_memory(
                    decision
                ),
        }

    if action == "tool":

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                execute_tool(
                    decision
                ),
        }

    if action == "tasks":

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                execute_tasks(
                    decision
                ),
        }

    if action == "chat":

        return {
            "exit":
                False,
            "menu":
                False,
            "message":
                decision.get(
                    "response",
                    "I couldn't understand "
                    "that request.",
                ),
        }

    return {
        "exit":
            False,
        "menu":
            False,
        "message":
            "I couldn't understand "
            "that request.",
    }


# ============================================================
# TEXT MODE
# ============================================================

def text_mode():

    print()
    print("=" * 50)
    print("              TEXT MODE")
    print("=" * 50)
    print()

    print(
        "Type 'exit' to shut down."
    )

    print(
        "Type 'main menu' to return "
        "to the main menu."
    )

    while True:

        try:

            text = input(
                "\nYOU > "
            ).strip()

        except (
            EOFError,
            KeyboardInterrupt,
        ):

            cancel_speech()
            print()
            return "menu"

        if not text:
            continue

        if is_main_menu_command(
            text
        ):

            cancel_speech()

            say(
                "Returning to the main menu.",
                "Returning to the main menu.",
            )

            return "menu"

        if is_exit_command(
            text
        ):

            cancel_speech()

            print(
                "\nJARVIS > "
                "Shutting down."
            )

            speak_async(
                "Shutting down."
            )

            return "shutdown"

        result = process_command(
            text
        )

        if result.get(
            "message"
        ):

            say(
                result[
                    "message"
                ]
            )

        if result.get(
            "menu"
        ):

            return "menu"

        if result.get(
            "exit"
        ):

            return "shutdown"


# ============================================================
# VOICE MODE
# ============================================================

def voice_mode():

    if listen is None:

        print(
            "JARVIS > "
            "Voice system unavailable."
        )

        return "menu"

    print()
    print("=" * 50)
    print("              VOICE MODE")
    print("=" * 50)
    print()

    while True:

        try:

            text = listen()

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > {e}"
            )

            continue

        if not text:

            print(
                "JARVIS > I didn't hear anything."
            )

            continue

        text = str(
            text
        ).strip()

        if not text:
            continue

        print(
            f"\nYOU 🎤 > {text}"
        )

        if is_main_menu_command(
            text
        ):

            cancel_speech()

            say(
                "Returning to the main menu.",
                "Returning to the main menu.",
            )

            return "menu"

        if is_exit_command(
            text
        ):

            cancel_speech()

            speak_async(
                "Shutting down."
            )

            return "shutdown"

        result = process_command(
            text
        )

        if result.get(
            "message"
        ):

            say(
                result[
                    "message"
                ]
            )

        if result.get(
            "menu"
        ):

            return "menu"

        if result.get(
            "exit"
        ):

            return "shutdown"


# ============================================================
# DIAGNOSTICS
# ============================================================

def diagnostics():

    print()
    print(
        "JARVIS DIAGNOSTICS"
    )
    print(
        "-" * 50
    )

    try:

        import requests

        ollama_online = (
            requests.get(
                "http://localhost:11434/api/tags",
                timeout=5,
            ).ok
        )

    except Exception:

        ollama_online = False

    print(
        "Ollama: "
        +
        (
            "ONLINE"
            if ollama_online
            else "OFFLINE"
        )
    )

    print(
        "Head Agent: "
        +
        (
            "ENABLED"
            if head_agent
            else "UNAVAILABLE"
        )
    )

    agents = [

        (
            "Research Agent",
            "agents.research_agent",
            "research",
        ),

        (
            "Data Agent",
            "agents.data_agent",
            "analyze",
        ),

        (
            "Coding Agent",
            "agents.coding_agent",
            "coding",
        ),

        (
            "Office Agent",
            "agents.office_agent",
            "office",
        ),

    ]

    for label, module_name, function_name in agents:

        try:

            module = __import__(
                module_name,
                fromlist=[
                    function_name
                ],
            )

            getattr(
                module,
                function_name,
            )

            enabled = True

        except Exception:

            enabled = False

        print(
            f"{label}: "
            +
            (
                "ENABLED"
                if enabled
                else "UNAVAILABLE"
            )
        )

    try:

        tools = list_tools()

    except Exception:

        tools = {}

    print(
        f"Tools loaded: "
        f"{len(tools)}"
    )

    print(
        "Available tools:"
    )

    for name in tools:

        print(
            f"  - {name}"
        )

    print(
        "Non-Blocking Voice: ENABLED"
    )

    print(
        "Speech Cancellation: "
        +
        (
            "AVAILABLE"
            if _stop_speech_function
            else "FALLBACK MODE"
        )
    )

    print(
        "-" * 50
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    while True:

        try:

            mode = input(
                "\nJARVIS MODE [T/V] > "
            ).strip().lower()

        except (
            EOFError,
            KeyboardInterrupt,
        ):

            cancel_speech()
            return "shutdown"

        if mode in {
            "exit",
            "quit",
            "shutdown",
            "bye",
        }:

            cancel_speech()
            return "shutdown"

        if mode == "t":

            result = text_mode()

            if result == "shutdown":
                return "shutdown"

            continue

        if mode == "v":

            result = voice_mode()

            if result == "shutdown":
                return "shutdown"

            continue

        print(
            "JARVIS > "
            "Please choose T or V."
        )


# ============================================================
# STARTUP
# ============================================================

def main():

    print(
        "=" * 50
    )

    print(
        "          JARVIS ONLINE"
    )

    print(
        "=" * 50
    )

    print(
        f"Local AI: "
        f"{OLLAMA_MODEL}"
    )

    try:

        tool_count = len(
            list_tools()
        )

    except Exception:

        tool_count = 0

    print(
        f"Tools: "
        f"{tool_count}"
    )

    print(
        "Router: "
        "Data-first + Head Agent + "
        "Deterministic + AI + Memory"
    )

    print(
        "Data Direct Routing: ENABLED"
    )

    print(
        "Research Direct Routing: ENABLED"
    )

    print(
        "Parallel Tasks: ENABLED"
    )

    print(
        "Tool Validation: ENABLED"
    )

    print(
        "Non-Blocking Voice: ENABLED"
    )

    print(
        "Speech Cancellation: "
        +
        (
            "ENABLED"
            if _stop_speech_function
            else "FALLBACK"
        )
    )

    print(
        "Voice Output: "
        +
        (
            "ENABLED"
            if speak
            else "UNAVAILABLE"
        )
    )

    diagnostics()

    print()

    print(
        "COMMAND MODES:"
    )

    print(
        "  T = Type command"
    )

    print(
        "  V = Voice mode"
    )

    print(
        "  EXIT = Shutdown"
    )

    result = main_menu()

    if result == "shutdown":

        cancel_speech()

        print(
            "\nJARVIS > "
            "Shutting down."
        )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    main()



def jarvis_collaborate(
    request,
    project_id=None,
    conversation_id=None,
):
    from omni.collaboration_service import collaborate

    return collaborate(
        request,
        project_id=project_id,
        conversation_id=conversation_id,
        channel="main",
    )



def jarvis_auto_collaboration_answer(request):
    """
    Automatic governed collaboration entry.

    Returns None so existing routing continues when
    collaboration is unnecessary or unavailable.
    """
    from omni.auto_collaboration import (
        auto_collaboration_answer,
    )

    return auto_collaboration_answer(request)



def jarvis_capture_salient_input(
    request,
    project_id=None,
    conversation_id=None,
):
    """
    Selectively capture durable memory.
    Never blocks command execution.
    """

    try:

        from omni.memory_context import (
            remember_salient_input,
        )

        from omni.memory_scope import (
            use_memory_context,
        )

        from omni.session_context import (
            get_session_id,
        )

        if conversation_id is None:

            conversation_id = (
                get_session_id(
                    "main"
                )
            )

        with use_memory_context(
            project_id=project_id,
            conversation_id=conversation_id,
        ):

            return remember_salient_input(
                request,
                project_id=project_id,
            )

    except Exception:
        return None


def jarvis_memory_command_answer(
    request,
    project_id=None,
    conversation_id=None,
):

    from omni.memory_commands import (
        memory_command_answer,
    )

    return memory_command_answer(
        request,
        project_id=project_id,
        conversation_id=conversation_id,
        channel="main",
    )



def jarvis_run_mission(
    goal,
    project_id=None,
    approved=False,
):
    from omni.autonomy_engine import (
        autonomy_engine,
    )

    return autonomy_engine.execute(
        goal,
        project_id=project_id,
        approved=approved,
    )


def jarvis_plan_mission(
    goal,
):
    from omni.autonomy_engine import (
        autonomy_engine,
    )

    return autonomy_engine.plan(
        goal
    )


def jarvis_mission_command_answer(
    request,
    project_id=None,
):
    from omni.mission_commands import (
        mission_command_answer,
    )

    return mission_command_answer(
        request,
        project_id=project_id,
    )



def jarvis_learn(
    subject,
    project_id=None,
):
    from omni.meta_intelligence import (
        meta_intelligence,
    )

    return meta_intelligence.learn(
        subject,
        project_id=project_id,
    )


def jarvis_knowledge_gap(
    subject,
):
    from omni.meta_intelligence import (
        meta_intelligence,
    )

    return (
        meta_intelligence
        .detect_knowledge_gap(
            subject
        )
    )


def jarvis_propose_improvement(
    capability,
    current_score,
    target_score,
):
    from omni.meta_intelligence import (
        meta_intelligence,
    )

    return (
        meta_intelligence
        .propose_improvement(
            capability,
            current_score,
            target_score,
        )
    )



def jarvis_self_improvement_status():

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .status()
    )


def jarvis_capability_score(
    capability,
    score,
    evidence,
    source="benchmark",
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .record_score(
            capability,
            score,
            evidence=evidence,
            source=source,
        )
    )


def jarvis_find_weaknesses(
    threshold=75,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .weaknesses(
            threshold=threshold
        )
    )


def jarvis_improvement_hypotheses(
    threshold=75,
    target=90,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .improvement_hypotheses(
            threshold=threshold,
            target=target,
        )
    )


def jarvis_create_candidate_patch(
    capability,
    target_file,
    candidate_source,
    rationale,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .create_candidate(
            capability=capability,
            target_file=target_file,
            candidate_source=
                candidate_source,
            rationale=rationale,
        )
    )


def jarvis_evaluate_candidate_patch(
    candidate_id,
    test_args=None,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .evaluate_candidate(
            candidate_id,
            test_args=test_args,
        )
    )


def jarvis_promote_candidate_patch(
    candidate_id,
    approved=False,
    post_test_args=None,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .promote_candidate(
            candidate_id,
            approved=approved,
            post_test_args=
                post_test_args,
        )
    )


def jarvis_rollback_candidate_patch(
    candidate_id,
):

    from omni.self_improvement_lab import (
        self_improvement_lab,
    )

    return (
        self_improvement_lab
        .rollback_candidate(
            candidate_id
        )
    )



def jarvis_verify_protected_core():

    from omni.core_integrity import (
        verify_protected_core,
    )

    return verify_protected_core()


def jarvis_universal_learn(
    subject,
    sources=(),
    project_id=None,
):

    from omni.universal_learning import (
        universal_learning,
    )

    return universal_learning.learn(
        subject,
        sources=sources,
        project_id=project_id,
    )


def jarvis_ingest_knowledge(
    subject,
    content,
    source_uri,
    source_type="user_provided",
    verified=False,
    project_id=None,
):

    from omni.universal_learning import (
        universal_learning,
    )

    return universal_learning.ingest(
        subject,
        content,
        source_uri,
        source_type=source_type,
        verified=verified,
        project_id=project_id,
    )


def jarvis_create_specialist(
    domain,
    purpose,
):

    from omni.dynamic_specialists import (
        dynamic_specialists,
    )

    return dynamic_specialists.create(
        domain,
        purpose,
    )


def jarvis_run_specialist(
    specialist_id,
    task,
):

    from omni.dynamic_specialists import (
        dynamic_specialists,
    )

    return dynamic_specialists.execute(
        specialist_id,
        task,
    )


def jarvis_score_specialist(
    specialist_id,
    score,
    success=True,
):

    from omni.dynamic_specialists import (
        dynamic_specialists,
    )

    return dynamic_specialists.evaluate(
        specialist_id,
        score,
        success,
    )


def jarvis_model_role(
    request,
    sensitive=False,
    offline=False,
):

    from omni.capability_growth import (
        model_role_router,
    )

    return model_role_router.route(
        request,
        sensitive=sensitive,
        offline=offline,
    )


def jarvis_growth_status():

    from omni.capability_growth import (
        capability_growth,
    )

    return capability_growth.status()


def jarvis_growth_actions():

    from omni.capability_growth import (
        capability_growth,
    )

    return capability_growth.next_actions()



def jarvis_action_status():

    from omni.action_engine import (
        action_engine,
    )

    return action_engine.status()


def jarvis_execute_action(
    tool,
    arguments=None,
    approved=False,
):

    from omni.action_engine import (
        action_engine,
    )

    return action_engine.execute(
        tool,
        arguments,
        approved=approved,
    )


def jarvis_run_workflow(
    steps,
):

    from omni.workflow_engine import (
        workflow_engine,
    )

    return workflow_engine.run(
        steps
    )


def jarvis_system_state():

    from omni.system_observer import (
        system_observer,
    )

    return system_observer.state()


def jarvis_capture_screen(
    path,
    approved=False,
):

    from omni.system_observer import (
        system_observer,
    )

    return system_observer.capture_screen(
        path,
        approved=approved,
    )


def jarvis_browser_open(
    url,
    approved=False,
):

    from omni.browser_actions import (
        browser_actions,
    )

    return browser_actions.open(
        url,
        approved=approved,
    )


def jarvis_git_status(
    repo,
):

    from omni.git_actions import (
        git_actions,
    )

    return git_actions.status(
        repo
    )


def jarvis_git_diff(
    repo,
):

    from omni.git_actions import (
        git_actions,
    )

    return git_actions.diff(
        repo
    )


def jarvis_read_document(
    path,
    max_chars=100000,
):

    from omni.document_intelligence import (
        document_intelligence,
    )

    return document_intelligence.read(
        path,
        max_chars=max_chars,
    )


def jarvis_search_document(
    path,
    query,
):

    from omni.document_intelligence import (
        document_intelligence,
    )

    return document_intelligence.search(
        path,
        query,
    )


def jarvis_discover_tools():

    from omni.tool_discovery import (
        tool_discovery,
    )

    return tool_discovery.inventory()



def jarvis_pending_approvals():

    from omni.approval_queue import (
        approval_queue,
    )

    return approval_queue.pending()


def jarvis_approve_action(
    approval_id,
):

    from omni.approval_queue import (
        approval_queue,
    )

    return approval_queue.approve(
        approval_id
    )


def jarvis_reject_action(
    approval_id,
):

    from omni.approval_queue import (
        approval_queue,
    )

    return approval_queue.reject(
        approval_id
    )


def jarvis_windows():

    from omni.desktop_automation import (
        desktop_automation,
    )

    return desktop_automation.windows()


def jarvis_focus_window(
    title,
    approval_id=None,
):

    from omni.desktop_automation import (
        desktop_automation,
    )

    return desktop_automation.focus_window(
        title,
        approval_id=approval_id,
    )


def jarvis_click(
    x,
    y,
    approval_id=None,
):

    from omni.desktop_automation import (
        desktop_automation,
    )

    return desktop_automation.click(
        x,
        y,
        approval_id=approval_id,
    )


def jarvis_type_text(
    text,
    approval_id=None,
    sensitive=False,
):

    from omni.desktop_automation import (
        desktop_automation,
    )

    return desktop_automation.type_text(
        text,
        approval_id=approval_id,
        sensitive=sensitive,
    )


def jarvis_screen_snapshot(
    path,
    approval_id=None,
):

    from omni.desktop_automation import (
        desktop_automation,
    )

    return desktop_automation.screen_snapshot(
        path,
        approval_id=approval_id,
    )


def jarvis_browser_inspect(
    url,
    approval_id=None,
):

    from omni.browser_automation_v2 import (
        browser_automation,
    )

    return browser_automation.inspect(
        url,
        approval_id=approval_id,
    )


def jarvis_browser_click(
    url,
    selector,
    approval_id=None,
):

    from omni.browser_automation_v2 import (
        browser_automation,
    )

    return browser_automation.click(
        url,
        selector,
        approval_id=approval_id,
    )


def jarvis_browser_fill(
    url,
    selector,
    value,
    approval_id=None,
    sensitive=False,
):

    from omni.browser_automation_v2 import (
        browser_automation,
    )

    return browser_automation.fill(
        url,
        selector,
        value,
        approval_id=approval_id,
        sensitive=sensitive,
    )


def jarvis_integration_status():

    from omni.integration_status import (
        integration_status,
    )

    return integration_status.status()


def jarvis_capability_acquisition_proposals():

    from omni.integration_status import (
        integration_status,
    )

    return (
        integration_status
        .acquisition_proposals()
    )



def jarvis_semantic_windows():

    from omni.semantic_ui import (
        semantic_ui,
    )

    return semantic_ui.windows()


def jarvis_ui_controls(
    window_title,
    text=None,
    control_type=None,
    automation_id=None,
):

    from omni.semantic_ui import (
        semantic_ui,
    )

    return semantic_ui.controls(
        window_title,

        text=text,

        control_type=
            control_type,

        automation_id=
            automation_id,
    )


def jarvis_ui_click(
    window_title,
    text=None,
    control_type=None,
    automation_id=None,
    approval_id=None,
):

    from omni.semantic_ui import (
        semantic_ui,
    )

    return semantic_ui.click(
        window_title,

        text=text,

        control_type=
            control_type,

        automation_id=
            automation_id,

        approval_id=
            approval_id,
    )


def jarvis_ui_set_text(
    window_title,
    value,
    text=None,
    automation_id=None,
    approval_id=None,
    sensitive=False,
):

    from omni.semantic_ui import (
        semantic_ui,
    )

    return semantic_ui.set_text(
        window_title,
        value,

        text=text,

        automation_id=
            automation_id,

        approval_id=
            approval_id,

        sensitive=
            sensitive,
    )


def jarvis_persistent_browser_inspect(
    url,
    profile="default",
    approval_id=None,
    headless=True,
):

    from omni.persistent_browser import (
        persistent_browser,
    )

    return persistent_browser.inspect(
        url,

        profile=profile,

        approval_id=
            approval_id,

        headless=headless,
    )


def jarvis_persistent_browser_click(
    url,
    selector,
    profile="default",
    approval_id=None,
    headless=True,
):

    from omni.persistent_browser import (
        persistent_browser,
    )

    return persistent_browser.click(
        url,
        selector,

        profile=profile,

        approval_id=
            approval_id,

        headless=headless,
    )


def jarvis_persistent_browser_fill(
    url,
    selector,
    value,
    profile="default",
    approval_id=None,
    headless=True,
    sensitive=False,
):

    from omni.persistent_browser import (
        persistent_browser,
    )

    return persistent_browser.fill(
        url,
        selector,
        value,

        profile=profile,

        approval_id=
            approval_id,

        headless=headless,

        sensitive=
            sensitive,
    )


def jarvis_analyze_screen(
    path,
):

    from omni.screen_perception import (
        screen_perception,
    )

    return (
        screen_perception
        .analyze_existing(
            path
        )
    )


def jarvis_replan_failed_action(
    original_goal,
    observed_result,
):

    from omni.action_replanner import (
        action_replanner,
    )

    return action_replanner.propose(
        original_goal,
        observed_result,
    )


def jarvis_github_state(
    repo=r"C:\Jarvis",
):

    from omni.github_read import (
        github_read,
    )

    return github_read.repository_state(
        repo
    )


def jarvis_voice_status():

    from omni.voice_adapter import (
        voice_adapter,
    )

    return voice_adapter.status()


def jarvis_listen_once(
    approval_id=None,
    timeout=5,
    phrase_time_limit=10,
):

    from omni.voice_adapter import (
        voice_adapter,
    )

    return voice_adapter.listen_once(
        approval_id=
            approval_id,

        timeout=timeout,

        phrase_time_limit=
            phrase_time_limit,
    )


def jarvis_action_v3_status():

    from omni.action_v3_status import (
        action_v3_status,
    )

    return action_v3_status.status()



def jarvis_operator_compile(
    goal,
    hints=None,
):

    from omni.computer_operator import (
        computer_operator,
    )

    return computer_operator.compile(
        goal,
        hints=hints,
    )


def jarvis_operator_prepare(
    goal,
    hints=None,
):

    from omni.computer_operator import (
        computer_operator,
    )

    return computer_operator.prepare(
        goal,
        hints=hints,
    )


def jarvis_operator_execute(
    plan,
    approval_batch_id=None,
):

    from omni.computer_operator import (
        computer_operator,
    )

    return computer_operator.execute(
        plan,

        approval_batch_id=
            approval_batch_id,
    )


def jarvis_operator_run(
    goal,
    hints=None,
    approval_batch_id=None,
):

    from omni.computer_operator import (
        computer_operator,
    )

    return computer_operator.run_goal(
        goal,

        hints=hints,

        approval_batch_id=
            approval_batch_id,
    )


def jarvis_approve_batch(
    batch_id,
):

    from omni.approval_batch import (
        approval_batches,
    )

    return approval_batches.approve(
        batch_id
    )


def jarvis_reject_batch(
    batch_id,
):

    from omni.approval_batch import (
        approval_batches,
    )

    return approval_batches.reject(
        batch_id
    )


def jarvis_download_file(
    url,
    filename=None,
    approval_id=None,
):

    from omni.safe_file_handoff import (
        safe_file_handoff,
    )

    return safe_file_handoff.download(
        url,

        filename=filename,

        approval_id=
            approval_id,
    )


def jarvis_create_worktree(
    name,
    repo=r"C:\Jarvis",
    approval_id=None,
):

    from omni.git_worktree_engine import (
        git_worktree_engine,
    )

    return git_worktree_engine.create(
        repo,
        name,

        approval_id=
            approval_id,
    )


def jarvis_test_worktree(
    worktree,
    test_args=None,
    approval_id=None,
):

    from omni.git_worktree_engine import (
        git_worktree_engine,
    )

    return git_worktree_engine.run_tests(
        worktree,

        test_args,

        approval_id=
            approval_id,
    )


def jarvis_tool_capability_graph():

    from omni.tool_capability_graph import (
        tool_capability_graph,
    )

    return (
        tool_capability_graph
        .snapshot()
    )



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



def jarvis_google_status():

    from omni.connected_services_status import (
        connected_services_status,
    )

    return connected_services_status.status()


def jarvis_google_install_client_secret(
    path,
):

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.install_client_secret(
        path
    )


def jarvis_google_connect():

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.connect()


def jarvis_google_disconnect():

    from omni.google_oauth import (
        google_oauth,
    )

    return google_oauth.disconnect()


def jarvis_gmail_search(
    query="",
    max_results=20,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.search(
        query,
        max_results,
    )


def jarvis_gmail_get(
    message_id,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.get(
        message_id
    )


def jarvis_gmail_create_draft(
    to,
    subject,
    body,
    cc=None,
    bcc=None,
    approval_id=None,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.create_draft(
        to,
        subject,
        body,
        cc=cc,
        bcc=bcc,
        approval_id=approval_id,
    )


def jarvis_gmail_send_draft(
    draft_id,
    approval_id=None,
):

    from omni.gmail_service import (
        gmail_service,
    )

    return gmail_service.send_draft(
        draft_id,
        approval_id=approval_id,
    )


def jarvis_google_calendars(
    max_results=100,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.calendars(
        max_results
    )


def jarvis_google_events(
    calendar_id="primary",
    time_min=None,
    time_max=None,
    max_results=20,
    query=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.events(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        query=query,
    )


def jarvis_google_create_event(
    event,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.create_event(
        event,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_update_event(
    event_id,
    patch,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.update_event(
        event_id,
        patch,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_delete_event(
    event_id,
    calendar_id="primary",
    send_updates="none",
    approval_id=None,
):

    from omni.google_calendar_service import (
        google_calendar_service,
    )

    return google_calendar_service.delete_event(
        event_id,
        calendar_id=calendar_id,
        send_updates=send_updates,
        approval_id=approval_id,
    )


def jarvis_google_contacts(
    query="",
    max_results=20,
):

    from omni.google_contacts_service import (
        google_contacts_service,
    )

    return google_contacts_service.search(
        query,
        max_results,
    )



def jarvis_resolve_recipient(
    query,
    max_results=20,
    include_gmail_history=True,
):

    from omni.recipient_intelligence import (
        recipient_resolver,
    )

    return recipient_resolver.resolve(
        query,
        max_results=max_results,
        include_gmail_history=include_gmail_history,
    )


def jarvis_resolve_recipients(
    queries,
    include_gmail_history=True,
):

    from omni.recipient_intelligence import (
        recipient_resolver,
    )

    return recipient_resolver.resolve_many(
        queries,
        include_gmail_history=include_gmail_history,
    )


def jarvis_prepare_draft_to(
    recipients,
    subject,
    body,
    cc=None,
    bcc=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_draft(
        recipients,
        subject,
        body,
        cc=cc,
        bcc=bcc,
    )


def jarvis_draft_to(
    recipients,
    subject,
    body,
    cc=None,
    bcc=None,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.create_draft(
        recipients,
        subject,
        body,
        cc=cc,
        bcc=bcc,
        approval_id=approval_id,
    )


def jarvis_check_calendar_conflicts(
    start,
    end,
    calendar_id="primary",
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.check_conflicts(
        start,
        end,
        calendar_id=calendar_id,
    )


def jarvis_prepare_meeting(
    title,
    attendees,
    start,
    end,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_meeting(
        title,
        attendees,
        start,
        end,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
    )


def jarvis_schedule_meeting(
    title,
    attendees,
    start,
    end,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.schedule_meeting(
        title,
        attendees,
        start,
        end,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
        approval_id=approval_id,
    )


def jarvis_prepare_meeting_from_email(
    message_id,
    title,
    start,
    end,
    attendees=None,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.prepare_meeting_from_email(
        message_id,
        title,
        start,
        end,
        attendees=attendees,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
    )


def jarvis_schedule_meeting_from_email(
    message_id,
    title,
    start,
    end,
    attendees=None,
    description=None,
    location=None,
    calendar_id="primary",
    send_updates="none",
    time_zone=None,
    allow_conflicts=False,
    approval_id=None,
):

    from omni.connected_workflows import (
        connected_workflows,
    )

    return connected_workflows.schedule_meeting_from_email(
        message_id,
        title,
        start,
        end,
        attendees=attendees,
        description=description,
        location=location,
        calendar_id=calendar_id,
        send_updates=send_updates,
        time_zone=time_zone,
        allow_conflicts=allow_conflicts,
        approval_id=approval_id,
    )


def jarvis_connected_services_v2_status():

    from omni.connected_services_v2_status import (
        connected_services_v2_status,
    )

    return connected_services_v2_status.status()



def jarvis_connected_intent(
    request,
):
    from omni.connected_intent_router import connected_intent_router
    return connected_intent_router.route(request)


def jarvis_gmail_thread(
    thread_id,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.thread(thread_id)


def jarvis_prepare_reply_draft(
    thread_id,
    body,
    reply_all=False,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.prepare_reply(
        thread_id,
        body,
        reply_all=reply_all,
    )


def jarvis_create_reply_draft(
    thread_id,
    body,
    reply_all=False,
    approval_id=None,
):
    from omni.email_thread_intelligence import email_thread_intelligence
    return email_thread_intelligence.create_reply_draft(
        thread_id,
        body,
        reply_all=reply_all,
        approval_id=approval_id,
    )


def jarvis_recommend_meeting_slots(
    attendees,
    window_start,
    window_end,
    duration_minutes=30,
    step_minutes=30,
    calendar_id="primary",
    time_zone=None,
    working_hour_start=8,
    working_hour_end=20,
    strict=True,
    max_slots=10,
):
    from omni.calendar_availability import calendar_availability
    return calendar_availability.recommend_slots(
        attendees,
        window_start,
        window_end,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        calendar_id=calendar_id,
        time_zone=time_zone,
        working_hour_start=working_hour_start,
        working_hour_end=working_hour_end,
        strict=strict,
        max_slots=max_slots,
    )


def jarvis_connected_approvals():
    from omni.connected_approval_dashboard import connected_approval_dashboard
    return connected_approval_dashboard.pending()


def jarvis_github_connect():
    from omni.github_connected import github_connected
    return github_connected.connect_interactive()


def jarvis_github_disconnect():
    from omni.github_connected import github_connected
    return github_connected.disconnect()


def jarvis_github_status(
    verify=False,
):
    from omni.github_connected import github_connected
    return github_connected.status(
        verify=verify
    )


def jarvis_github_profile():
    from omni.github_connected import github_connected
    return github_connected.profile()


def jarvis_github_repos(
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.repos(
        per_page=per_page
    )


def jarvis_github_issues(
    owner,
    repo,
    state="open",
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.issues(
        owner,
        repo,
        state=state,
        per_page=per_page,
    )


def jarvis_github_pulls(
    owner,
    repo,
    state="open",
    per_page=30,
):
    from omni.github_connected import github_connected
    return github_connected.pulls(
        owner,
        repo,
        state=state,
        per_page=per_page,
    )


def jarvis_github_create_issue(
    owner,
    repo,
    title,
    body="",
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_issue(
        owner,
        repo,
        title,
        body,
        approval_id=approval_id,
    )


def jarvis_github_comment(
    owner,
    repo,
    issue_number,
    body,
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_comment(
        owner,
        repo,
        issue_number,
        body,
        approval_id=approval_id,
    )


def jarvis_github_create_pull(
    owner,
    repo,
    title,
    head,
    base,
    body="",
    approval_id=None,
):
    from omni.github_connected import github_connected
    return github_connected.create_pull(
        owner,
        repo,
        title,
        head,
        base,
        body,
        approval_id=approval_id,
    )


def jarvis_connected_services_v3_status():
    from omni.connected_services_v3_status import connected_services_v3_status
    return connected_services_v3_status.status()



def jarvis_trading_v1_status():

    from omni.trading_intelligence.trading_status import (
        trading_intelligence_v1_status,
    )

    return trading_intelligence_v1_status.status()


def jarvis_trading_register_instrument(
    instrument,
):

    from omni.trading_intelligence.instrument_master import (
        instrument_master,
    )

    return (
        instrument_master
        .register(
            instrument
        )
        .to_dict()
    )


def jarvis_trading_find_instruments(
    query="",
    exchange=None,
    asset_class=None,
    instrument_type=None,
    underlying=None,
):

    from omni.trading_intelligence.instrument_master import (
        instrument_master,
    )

    return tuple(
        instrument.to_dict()

        for instrument
        in instrument_master.search(
            query,
            exchange=exchange,
            asset_class=asset_class,
            instrument_type=instrument_type,
            underlying=underlying,
        )
    )


def jarvis_trading_features(
    bars,
):

    from omni.trading_intelligence.feature_engine import (
        feature_engine,
    )

    return feature_engine.snapshot(
        bars
    )


def jarvis_trading_option_features(
    **kwargs,
):

    from omni.trading_intelligence.options_features import (
        option_feature_snapshot,
    )

    return option_feature_snapshot(
        **kwargs
    )


def jarvis_trading_regime(
    bars,
    **kwargs,
):

    from omni.trading_intelligence.regime_engine import (
        market_regime_engine,
    )

    return market_regime_engine.classify(
        bars,
        **kwargs
    )


def jarvis_trading_strategy_catalog():

    from omni.trading_intelligence.strategy_registry import (
        strategy_registry,
    )

    return strategy_registry.catalog()


def jarvis_trading_signal(
    strategy_id,
    current,
    previous=None,
):

    from omni.trading_intelligence.signal_engine import (
        signal_engine,
    )

    from omni.trading_intelligence.strategy_registry import (
        strategy_registry,
    )


    strategy = strategy_registry.get(
        strategy_id
    )


    if strategy is None:

        return {
            "success":
                False,

            "error":
                "Unknown strategy.",
        }


    return signal_engine.evaluate(
        strategy,
        current,
        previous,
    )


def jarvis_trading_metrics(
    trades,
):

    from omni.trading_intelligence.trading_metrics import (
        evaluate_trades,
    )

    return evaluate_trades(
        trades
    )


def jarvis_trading_guard(
    capability,
):

    from omni.trading_intelligence.trading_guardrails import (
        trading_research_guard,
    )

    return trading_research_guard.check(
        capability
    )


def jarvis_fyers_readonly_capabilities():

    from omni.trading_intelligence.fyers_market_adapter import (
        FyersReadOnlyAdapter,
    )

    return FyersReadOnlyAdapter().capabilities()



def jarvis_fyers_bridge_status():

    from omni.trading_intelligence.fyers_market_adapter import (
        FyersReadOnlyAdapter,
    )

    return FyersReadOnlyAdapter().bridge_status()



def jarvis_trading_v2_status():

    from omni.trading_intelligence.trading_v2_status import (
        trading_intelligence_v2_status,
    )

    return trading_intelligence_v2_status.status()


def jarvis_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        BacktestConfig,
    )

    return BacktestConfig(
        **kwargs
    )


def jarvis_option_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        option_premium_config,
    )

    return option_premium_config(
        **kwargs
    )


def jarvis_commodity_backtest_config(
    **kwargs,
):

    from omni.trading_intelligence.backtest_schema import (
        commodity_future_config,
    )

    return commodity_future_config(
        **kwargs
    )


def jarvis_backtest(
    bars,
    strategy_id,
    config,
):

    from omni.trading_intelligence.historical_backtester import (
        historical_backtester,
    )

    return historical_backtester.run(
        bars,
        strategy_id,
        config,
    )


def jarvis_backtest_fyers(
    symbol,
    strategy_id,
    config,
    market="NSE",
    timeframe="5m",
    bars=500,
):

    from omni.trading_intelligence.historical_backtester import (
        historical_backtester,
    )

    return historical_backtester.run_fyers(
        symbol,
        strategy_id,
        config,
        market=market,
        timeframe=timeframe,
        bars=bars,
    )


def jarvis_normalize_market_history(
    payload,
    symbol=None,
):

    from omni.trading_intelligence.history_normalizer import (
        normalize_history_payload,
    )

    return normalize_history_payload(
        payload,
        symbol=symbol,
    )


def jarvis_resample_bars(
    bars,
    timeframe_minutes,
    base_timeframe_minutes=1,
    closed_only=True,
):

    from omni.trading_intelligence.multi_timeframe import (
        resample_bars,
    )

    return resample_bars(
        bars,
        timeframe_minutes,
        base_timeframe_minutes=base_timeframe_minutes,
        closed_only=closed_only,
    )


def jarvis_parameter_sweep(
    bars,
    strategy_id,
    base_config,
    grid,
    objective="net_pnl",
):

    from omni.trading_intelligence.parameter_sweep import (
        parameter_sweep_engine,
    )

    return parameter_sweep_engine.run(
        bars,
        strategy_id,
        base_config,
        grid,
        objective=objective,
    )


def jarvis_compare_strategies(
    bars,
    strategy_ids,
    config,
    objective="net_pnl",
):

    from omni.trading_intelligence.strategy_compare import (
        strategy_comparator,
    )

    return strategy_comparator.compare(
        bars,
        strategy_ids,
        config,
        objective=objective,
    )


def jarvis_save_backtest(
    result,
    name=None,
):

    from omni.trading_intelligence.trade_journal import (
        trade_journal,
    )

    return trade_journal.save(
        result,
        name=name,
    )



def jarvis_trading_v3_status():

    from omni.trading_intelligence.trading_v3_status import (
        trading_intelligence_v3_status,
    )

    return trading_intelligence_v3_status.status()


def jarvis_option_chain_snapshot(
    rows,
    underlying,
    spot,
    timestamp,
    expiry=None,
):

    from omni.trading_intelligence.option_chain_schema import (
        normalize_option_chain,
    )

    return normalize_option_chain(
        rows,
        underlying=underlying,
        spot=spot,
        timestamp=timestamp,
        expiry=expiry,
    )


def jarvis_option_chain_analyze(
    snapshot,
):

    from omni.trading_intelligence.option_chain_intelligence import (
        option_chain_intelligence,
    )

    return option_chain_intelligence.analyze(
        snapshot
    )


def jarvis_iv_rank(
    current_iv,
    history,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_rank,
    )

    return iv_rank(
        current_iv,
        history,
    )


def jarvis_iv_percentile(
    current_iv,
    history,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_percentile,
    )

    return iv_percentile(
        current_iv,
        history,
    )


def jarvis_iv_term_structure(
    points,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_term_structure,
    )

    return iv_term_structure(
        points
    )


def jarvis_expiry_state(
    expiry,
    **kwargs,
):

    from omni.trading_intelligence.expiry_intelligence import (
        expiry_state,
    )

    return expiry_state(
        expiry,
        **kwargs
    )


def jarvis_build_vertical_spread(
    kind,
    **kwargs,
):

    from omni.trading_intelligence.defined_risk_spreads import (
        build_vertical_spread,
    )

    return build_vertical_spread(
        kind,
        **kwargs
    )


def jarvis_vertical_payoff(
    spread,
    settlement,
):

    from omni.trading_intelligence.defined_risk_spreads import (
        vertical_payoff,
    )

    return vertical_payoff(
        spread,
        settlement,
    )


def jarvis_derivatives_confirmation(
    chain_analysis,
    **kwargs,
):

    from omni.trading_intelligence.derivatives_confirmation import (
        derivatives_confirmation,
    )

    return derivatives_confirmation(
        chain_analysis,
        **kwargs
    )


def jarvis_commodity_contract_state(
    contract,
    **kwargs,
):

    from omni.trading_intelligence.commodity_intelligence import (
        commodity_contract_state,
    )

    return commodity_contract_state(
        contract,
        **kwargs
    )


def jarvis_derivatives_strategy_catalog():

    from omni.trading_intelligence.derivatives_strategy_registry import (
        derivatives_strategy_catalog,
    )

    return derivatives_strategy_catalog()


def jarvis_derivatives_signal(
    strategy_id,
    features,
    previous=None,
):

    from omni.trading_intelligence.derivatives_strategy_registry import (
        derivatives_signal,
    )

    return derivatives_signal(
        strategy_id,
        features,
        previous,
    )


def jarvis_option_chain_provider_status():

    from omni.trading_intelligence.option_chain_provider import (
        option_chain_providers,
    )

    return option_chain_providers.status()



def jarvis_trading_v4_status():

    from omni.trading_intelligence.trading_v4_status import (
        trading_intelligence_v4_status,
    )

    return trading_intelligence_v4_status.status()


def jarvis_strategy_mutate(
    strategy_id,
    count=5,
    random_seed=1,
    generation=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.mutate(
        strategy_id,
        count=count,
        random_seed=random_seed,
        generation=generation,
    )


def jarvis_strategy_crossover(
    left_strategy_id,
    right_strategy_id,
    generation=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.crossover(
        left_strategy_id,
        right_strategy_id,
        generation=generation,
    )


def jarvis_evaluate_strategy_candidate(
    genome,
    regime_datasets,
    base_config,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.evaluate(
        genome,
        regime_datasets,
        base_config,
    )


def jarvis_evolve_strategy(
    strategy_id,
    regime_datasets,
    base_config,
    candidate_count=8,
    random_seed=1,
):

    from omni.trading_intelligence.strategy_evolution_lab import (
        strategy_evolution_lab,
    )

    return strategy_evolution_lab.evolve(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=candidate_count,
        random_seed=random_seed,
    )


def jarvis_compare_champion_challenger(
    champion,
    challenger,
    minimum_margin=2.0,
):

    from omni.trading_intelligence.champion_challenger import (
        champion_challenger,
    )

    return champion_challenger.compare(
        champion,
        challenger,
        minimum_margin=minimum_margin,
    )


def jarvis_strategy_retirement_proposal(
    evaluation,
    retire_below=-20.0,
    degrade_below=0.0,
):

    from omni.trading_intelligence.strategy_retirement import (
        strategy_retirement_engine,
    )

    return strategy_retirement_engine.evaluate(
        evaluation,
        retire_below=retire_below,
        degrade_below=degrade_below,
    )


def jarvis_save_evolution_artifact(
    artifact,
):

    from omni.trading_intelligence.evolution_store import (
        evolution_store,
    )

    return evolution_store.save(
        artifact
    )



def jarvis_trading_v5_status():

    from omni.trading_intelligence.trading_v5_status import (
        trading_intelligence_v5_status,
    )

    return trading_intelligence_v5_status.status()


def jarvis_trading_validate_candidate(
    candidate,
    bars,
    base_config,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    from omni.trading_intelligence.strategy_validation_lab import (
        strategy_validation_lab,
    )

    return strategy_validation_lab.validate(
        candidate,
        bars,
        base_config,
        regime_datasets=regime_datasets,
        monte_carlo_iterations=monte_carlo_iterations,
        random_seed=random_seed,
    )


def jarvis_walk_forward(
    bars,
    strategy,
    config,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    from omni.trading_intelligence.walk_forward import (
        walk_forward_validator,
    )

    return walk_forward_validator.run(
        bars,
        strategy,
        config,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
    )


def jarvis_monte_carlo_trades(
    trades,
    initial_capital,
    iterations=1000,
    random_seed=1,
    bootstrap=True,
):

    from omni.trading_intelligence.monte_carlo import (
        monte_carlo_trade_simulator,
    )

    return monte_carlo_trade_simulator.run(
        trades,
        initial_capital=initial_capital,
        iterations=iterations,
        random_seed=random_seed,
        bootstrap=bootstrap,
    )


def jarvis_parameter_sensitivity(
    bars,
    strategy,
    config,
    fields=(
        "stop_loss_pct",
        "target_pct",
        "max_bars_in_trade",
    ),
):

    from omni.trading_intelligence.parameter_sensitivity import (
        parameter_sensitivity_analyzer,
    )

    return parameter_sensitivity_analyzer.run(
        bars,
        strategy,
        config,
        fields=fields,
    )


def jarvis_cost_stress(
    bars,
    strategy,
    config,
):

    from omni.trading_intelligence.cost_stress import (
        cost_stress_tester,
    )

    return cost_stress_tester.run(
        bars,
        strategy,
        config,
    )


def jarvis_save_validation_report(
    report,
):

    from omni.trading_intelligence.validation_store import (
        validation_store,
    )

    return validation_store.save(
        report
    )



def jarvis_trading_v6_status():

    from omni.trading_intelligence.trading_v6_status import (
        trading_intelligence_v6_status,
    )

    return trading_intelligence_v6_status.status()


def jarvis_shadow_config(
    **kwargs,
):

    from omni.trading_intelligence.shadow_schema import (
        ShadowSessionConfig,
    )

    return ShadowSessionConfig(
        **kwargs
    )


def jarvis_shadow_quote_snapshot(
    symbol,
    timestamp,
    ltp,
    bid=None,
    ask=None,
    source="manual",
):

    from omni.trading_intelligence.shadow_schema import (
        QuoteSnapshot,
    )

    return QuoteSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        ltp=ltp,
        bid=bid,
        ask=ask,
        source=source,
    )


def jarvis_shadow_create_session(
    symbol,
    strategy_ids,
    config=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.create(
        symbol,
        strategy_ids,
        config,
    )


def jarvis_shadow_process(
    session_id,
    snapshot,
    signals,
    now=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.process(
        session_id,
        snapshot,
        signals,
        now=now,
    )


def jarvis_shadow_fyers_quote(
    symbol,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.read_fyers_quote(
        symbol
    )


def jarvis_shadow_process_fyers(
    session_id,
    signals,
    now=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.process_fyers(
        session_id,
        signals,
        now=now,
    )


def jarvis_shadow_status(
    session_id=None,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.status(
        session_id
    )


def jarvis_shadow_kill(
    session_id,
    reason="manual",
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.kill(
        session_id,
        reason,
    )


def jarvis_shadow_resume(
    session_id,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return shadow_trading_runtime.resume(
        session_id
    )


def jarvis_shadow_summary(
    session_id,
):

    from omni.trading_intelligence.shadow_runtime import (
        shadow_trading_runtime,
    )

    return (
        shadow_trading_runtime
        .get(
            session_id
        )
        .summary()
    )


def jarvis_shadow_drift(
    baseline_metrics,
    recent_metrics,
):

    from omni.trading_intelligence.performance_drift import (
        performance_drift_detector,
    )

    return performance_drift_detector.compare(
        baseline_metrics,
        recent_metrics,
    )


def jarvis_shadow_weights(
    evidence,
):

    from omni.trading_intelligence.strategy_weighting import (
        research_strategy_weighting,
    )

    return research_strategy_weighting.calculate(
        evidence
    )


def jarvis_shadow_champion_compare(
    champion_metrics,
    challenger_metrics,
    margin=2.0,
):

    from omni.trading_intelligence.shadow_champion import (
        shadow_champion_challenger,
    )

    return shadow_champion_challenger.compare(
        champion_metrics,
        challenger_metrics,
        margin=margin,
    )



def jarvis_nautilus_status():

    from omni.trading_intelligence.nautilus_status import (
        nautilus_kernel_status,
    )

    return nautilus_kernel_status()


def jarvis_nautilus_backtest(
    bars,
    signals,
    initial_capital=100000.0,
    quantity=1000,
    timeout=120,
):

    from omni.trading_intelligence.nautilus_bridge import (
        nautilus_research_bridge,
    )

    return nautilus_research_bridge.backtest(
        bars,
        signals,
        initial_capital=initial_capital,
        quantity=quantity,
        timeout=timeout,
    )



def jarvis_nautilus_c2_status():

    from omni.trading_intelligence.nautilus_c2_status import (
        nautilus_c2_status,
    )

    return nautilus_c2_status()


def jarvis_nautilus_universal_backtest(
    bars,
    signals,
    instrument,
    execution=None,
    initial_capital=100000.0,
    quantity=1,
    leverage=1,
    timeout=120,
):

    from omni.trading_intelligence.nautilus_c2_bridge import (
        nautilus_c2_bridge,
    )

    return nautilus_c2_bridge.backtest(
        bars,
        signals,
        instrument=instrument,
        execution=execution,
        initial_capital=initial_capital,
        quantity=quantity,
        leverage=leverage,
        timeout=timeout,
    )


def jarvis_reconcile_backtests(
    native_result,
    nautilus_result,
):

    from omni.trading_intelligence.nautilus_reconciliation import (
        reconcile_native_nautilus,
    )

    return reconcile_native_nautilus(
        native_result,
        nautilus_result,
    )


def jarvis_nautilus_v5_gate(
    v5_report,
    nautilus_result,
):

    from omni.trading_intelligence.nautilus_validation_adapter import (
        nautilus_v5_validation_gate,
    )

    return nautilus_v5_validation_gate(
        v5_report,
        nautilus_result,
    )


def jarvis_nautilus_portfolio_research(
    results,
):

    from omni.trading_intelligence.nautilus_portfolio_research import (
        nautilus_portfolio_research,
    )

    return nautilus_portfolio_research(
        results
    )



def jarvis_nautilus_c3_status():

    from omni.trading_intelligence.nautilus_c3_status import (
        nautilus_c3_status,
    )

    return nautilus_c3_status()


def jarvis_nautilus_portfolio_backtest(
    portfolio,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_bridge import (
        nautilus_c3_portfolio_bridge,
    )

    return nautilus_c3_portfolio_bridge.run(
        portfolio,
        timeout=timeout,
    )


def jarvis_nautilus_execution_stress(
    portfolio,
    profiles=None,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_bridge import (
        nautilus_c3_portfolio_bridge,
    )

    return nautilus_c3_portfolio_bridge.stress_matrix(
        portfolio,
        profiles=profiles,
        timeout=timeout,
    )


def jarvis_nautilus_portfolio_walk_forward(
    portfolio,
    train_size,
    validation_size,
    test_size,
    step=None,
    timeout=180,
):

    from omni.trading_intelligence.nautilus_c3_campaign import (
        nautilus_c3_walk_forward,
    )

    return nautilus_c3_walk_forward.run(
        portfolio,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
        timeout=timeout,
    )


def jarvis_nautilus_c3_v5_gate(
    v5_report,
    c3_campaign,
):

    from omni.trading_intelligence.nautilus_c3_campaign import (
        nautilus_c3_v5_gate,
    )

    return nautilus_c3_v5_gate(
        v5_report,
        c3_campaign,
    )



def jarvis_trading_v7_status():

    from omni.trading_intelligence.trading_v7_status import (
        trading_v7_status,
    )

    return trading_v7_status()


def jarvis_fyers_option_chain(
    symbol,
    strikecount=5,
    timestamp=None,
    greeks=True,
    persist=True,
    timeout=30,
):

    from omni.trading_intelligence.fyers_v7_bridge import (
        fyers_v7_readonly_bridge,
    )

    from omni.trading_intelligence.fyers_chain_normalizer import (
        normalize_fyers_option_chain,
    )

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )


    raw = fyers_v7_readonly_bridge.option_chain(
        symbol,
        strikecount=strikecount,
        timestamp=timestamp,
        greeks=greeks,
        timeout=timeout,
    )


    snapshot = normalize_fyers_option_chain(
        raw
    )


    saved = None


    if persist:

        saved = (
            derivatives_history_store
            .save(
                snapshot
            )
        )


    return {
        "success":
            True,

        "snapshot":
            snapshot,

        "persisted":
            bool(
                persist
            ),

        "save_result":
            saved,

        "read_only":
            True,

        "live_execution":
            False,
    }


def jarvis_fyers_market_depth(
    symbol,
    ohlcv_flag=True,
    timeout=30,
):

    from omni.trading_intelligence.fyers_v7_bridge import (
        fyers_v7_readonly_bridge,
    )


    return fyers_v7_readonly_bridge.depth(
        symbol,
        ohlcv_flag=ohlcv_flag,
        timeout=timeout,
    )


def jarvis_derivatives_history(
    symbol,
    limit=100,
):

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )

    return derivatives_history_store.history(
        symbol,
        limit=limit,
    )


def jarvis_derivatives_leg_history(
    symbol,
    strike,
    option_type,
    expiry=None,
    limit=500,
):

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )

    return derivatives_history_store.leg_history(
        symbol,
        strike,
        option_type,
        expiry=expiry,
        limit=limit,
    )


def jarvis_derivatives_history_analytics(
    symbol,
    lookback=252,
):

    from omni.trading_intelligence.derivatives_history_analytics import (
        derivatives_history_analytics,
    )

    return derivatives_history_analytics.analyze(
        symbol,
        lookback=lookback,
    )


def jarvis_sync_derivatives(
    underlying_bars,
    futures_bars,
    chain_snapshots,
    max_chain_age_seconds=300,
):

    from omni.trading_intelligence.derivatives_sync import (
        synchronize_derivatives,
    )

    return synchronize_derivatives(
        underlying_bars,
        futures_bars,
        chain_snapshots,
        max_chain_age_seconds=max_chain_age_seconds,
    )


def jarvis_derivatives_regime(
    features,
):

    from omni.trading_intelligence.derivatives_regime_v7 import (
        derivatives_regime,
    )

    return derivatives_regime(
        features
    )


def jarvis_derivatives_ensemble(
    signals,
    weights=None,
    threshold=0.25,
):

    from omni.trading_intelligence.derivatives_ensemble import (
        derivatives_ensemble,
    )

    return derivatives_ensemble(
        signals,
        weights=weights,
        threshold=threshold,
    )


def jarvis_derivatives_campaign(
    candidates,
):

    from omni.trading_intelligence.derivatives_campaign import (
        derivatives_research_campaign,
    )

    return derivatives_research_campaign.run(
        candidates
    )



def jarvis_trading_v8_status():

    from omni.trading_intelligence.trading_v8_status import (
        trading_v8_status,
    )

    return trading_v8_status()


def jarvis_derivatives_capture_plan(
    plan_id,
    symbol,
    strikecount=5,
    greeks=True,
    expiry_mode="nearest",
    expiry_timestamps=(),
    interval_minutes=5,
    session_start="09:15",
    session_end="15:30",
    timezone="Asia/Kolkata",
    enabled=True,
    max_captures_per_run=1,
):

    from omni.trading_intelligence.derivatives_capture_plans import (
        build_capture_plan,
    )

    return build_capture_plan(
        plan_id,
        symbol,
        strikecount=strikecount,
        greeks=greeks,
        expiry_mode=expiry_mode,
        expiry_timestamps=expiry_timestamps,
        interval_minutes=interval_minutes,
        session_start=session_start,
        session_end=session_end,
        timezone=timezone,
        enabled=enabled,
        max_captures_per_run=max_captures_per_run,
    )


def jarvis_save_derivatives_capture_plan(
    plan,
):

    from omni.trading_intelligence.derivatives_capture_plans import (
        capture_plan_store,
    )

    return capture_plan_store.save(
        plan
    )


def jarvis_list_derivatives_capture_plans():

    from omni.trading_intelligence.derivatives_capture_plans import (
        capture_plan_store,
    )

    return capture_plan_store.list()


def jarvis_run_derivatives_collector(
    now=None,
    dry_run=False,
    timeout=30,
    max_plans=10,
):

    from omni.trading_intelligence.derivatives_session_collector import (
        derivatives_session_collector,
    )

    return derivatives_session_collector.collect_due(
        now=now,
        dry_run=dry_run,
        timeout=timeout,
        max_plans=max_plans,
    )


def jarvis_build_derivatives_feature_dataset(
    symbol,
    limit=1000,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.build(
        symbol,
        limit=limit,
    )


def jarvis_build_synchronized_derivatives_dataset(
    symbol,
    underlying_bars,
    futures_bars,
    limit=1000,
    max_chain_age_seconds=300,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.synchronized(
        symbol,
        underlying_bars,
        futures_bars,
        limit=limit,
        max_chain_age_seconds=max_chain_age_seconds,
    )


def jarvis_build_derivatives_regime_datasets(
    bars,
    feature_rows,
):

    from omni.trading_intelligence.derivatives_feature_dataset import (
        derivatives_feature_dataset_builder,
    )

    return derivatives_feature_dataset_builder.regime_datasets(
        bars,
        feature_rows,
    )


def jarvis_v4_evolve_derivatives(
    strategy_id,
    regime_datasets,
    base_config,
    candidate_count=8,
    random_seed=1,
):

    from omni.trading_intelligence.derivatives_v4_adapter import (
        evolve_derivatives_strategy,
    )

    return evolve_derivatives_strategy(
        strategy_id,
        regime_datasets,
        base_config,
        candidate_count=candidate_count,
        random_seed=random_seed,
    )


def jarvis_v5_validate_derivatives(
    candidate,
    bars,
    base_config,
    regime_datasets=None,
    monte_carlo_iterations=500,
    random_seed=1,
):

    from omni.trading_intelligence.derivatives_v5_adapter import (
        validate_derivatives_candidate,
    )

    return validate_derivatives_candidate(
        candidate,
        bars,
        base_config,
        regime_datasets=regime_datasets,
        monte_carlo_iterations=monte_carlo_iterations,
        random_seed=random_seed,
    )


def jarvis_v5_walk_forward_derivatives(
    bars,
    strategy,
    config,
    train_size,
    validation_size,
    test_size,
    step=None,
):

    from omni.trading_intelligence.derivatives_v5_adapter import (
        walk_forward_derivatives,
    )

    return walk_forward_derivatives(
        bars,
        strategy,
        config,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
    )


def jarvis_nautilus_validate_derivatives_portfolio(
    portfolio,
    v5_report=None,
    train_size=None,
    validation_size=None,
    test_size=None,
    step=None,
    timeout=180,
):

    from omni.trading_intelligence.derivatives_nautilus_adapter import (
        validate_derivatives_portfolio,
    )

    return validate_derivatives_portfolio(
        portfolio,
        v5_report=v5_report,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step=step,
        timeout=timeout,
    )


def jarvis_cross_asset_regime_graph(
    symbols,
    feature="atm_iv",
    lookback=252,
    min_overlap=3,
    max_gap_seconds=900,
    edge_threshold=0.40,
):

    from omni.trading_intelligence.cross_asset_regime_graph import (
        cross_asset_regime_graph,
    )

    return cross_asset_regime_graph.build(
        symbols,
        feature=feature,
        lookback=lookback,
        min_overlap=min_overlap,
        max_gap_seconds=max_gap_seconds,
        edge_threshold=edge_threshold,
    )


def jarvis_research_portfolio_optimize(
    candidates,
    correlation_graph=None,
    temperature=10.0,
):

    from omni.trading_intelligence.research_portfolio_optimizer import (
        research_portfolio_optimizer,
    )

    return research_portfolio_optimizer.optimize(
        candidates,
        correlation_graph=correlation_graph,
        temperature=temperature,
    )



def jarvis_operator_v5_status():

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.status()


def jarvis_operator_v5_snapshot(
    mission_id,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.snapshot(
        mission_id
    )


def jarvis_operator_v5_resume(
    mission_id,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.resume(
        mission_id
    )


def jarvis_operator_v5_apply_replan(
    mission_id,
    proposal_text,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return operator_v5_reliability.apply_replan(
        mission_id,
        proposal_text,
    )


def jarvis_operator_v5_evidence(
    limit=50,
):

    from omni.operator_v5_reliability import (
        operator_v5_reliability,
    )

    return (
        operator_v5_reliability
        .ledger
        .recent(
            limit
        )
    )


def jarvis_command(
    text,
    context="master",
):

    from omni.universal_command_bridge import (
        command_bridge,
    )

    return command_bridge.execute(
        text,
        context=context,
    )


def jarvis_voice_v2_status():

    from omni.voice_conversation_v2 import (
        voice_conversation_v2,
    )

    return voice_conversation_v2.status()


def jarvis_system_status():

    from omni.jarvis_supervisor_v1 import (
        jarvis_supervisor,
    )

    return jarvis_supervisor.status()
