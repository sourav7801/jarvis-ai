import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from tools.registry import get_tool, list_tools
from tools.tool_schema import validate_tool_call
from tools.memory import remember, recall, show_memory, forget


# ============================================================
# OPTIONAL VOICE
# ============================================================

try:
    from voice import listen, speak
except Exception:
    listen = None
    speak = None


# ============================================================
# CONFIG
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

MAX_PARALLEL_TASKS = 4

EXIT_COMMANDS = {
    "exit",
    "quit",
    "stop",
    "shutdown",
    "bye",
}


# ============================================================
# SAFE VOICE
# ============================================================

def speak_safe(message):
    """
    Dashboard-safe voice function.

    If voice.py or speak() is unavailable,
    Jarvis continues working without crashing.
    """

    if not message:
        return

    if speak is None:
        return

    try:
        speak(str(message))
    except Exception as e:
        print(f"JARVIS VOICE DEBUG > {e}")


# ============================================================
# OUTPUT
# ============================================================

def say(message, voice=True):
    """
    Standard Jarvis output.

    Dashboard can use process_command() directly,
    while terminal mode uses this function.
    """

    if message is None:
        return

    print(f"\nJARVIS > {message}")

    if voice:
        speak_safe(message)


# ============================================================
# HELPERS
# ============================================================

def normalize(text):

    if text is None:
        return ""

    return " ".join(
        str(text).strip().lower().split()
    )


def is_exit_command(text):

    return normalize(text) in EXIT_COMMANDS


# ============================================================
# TOOL HELPERS
# ============================================================

def get_tool_names():

    tools = list_tools()

    if isinstance(tools, dict):
        return list(tools.keys())

    if isinstance(tools, (list, tuple, set)):
        return list(tools)

    return []


def tool_exists(name):

    return name in get_tool_names()


def make_tool_decision(tool_name, arguments=None):

    if arguments is None:
        arguments = {}

    return {
        "action": "tool",
        "tool": tool_name,
        "arguments": arguments,
    }


# ============================================================
# DETERMINISTIC ROUTER
# ============================================================

def deterministic_route(text):

    value = normalize(text)

    if not value:
        return None

    # ========================================================
    # EXIT
    # ========================================================

    if is_exit_command(value):

        return {
            "action": "exit"
        }

    # ========================================================
    # MULTI-TASK COMMANDS
    #
    # Examples:
    #
    # open notepad and calculator
    # open calculator and notepad
    # can you open notepad and calculator for me
    # start calculator and notepad
    # launch notepad and calculator
    # ========================================================

    multi_match = re.match(
        r"^(?:can you\s+)?"
        r"(?:please\s+)?"
        r"(?:open|start|launch)\s+"
        r"(.+?)\s+and\s+(.+?)"
        r"(?:\s+for me)?$",
        value,
        re.IGNORECASE,
    )

    if multi_match:

        first = multi_match.group(1).strip()
        second = multi_match.group(2).strip()

        tasks = []

        # ----------------------------------------------------
        # Convert individual application names to tools
        # ----------------------------------------------------

        def application_to_tool(application):

            app = normalize(application)

            # Remove polite words
            app = re.sub(
                r"\bplease\b",
                "",
                app,
            )

            app = re.sub(
                r"\bfor me\b",
                "",
                app,
            )

            app = app.strip()

            if app in {
                "notepad",
                "notebook",
            }:
                return make_tool_decision(
                    "open_notepad"
                )

            if app in {
                "calculator",
                "calc",
            }:
                return make_tool_decision(
                    "open_calculator"
                )

            # Try normal deterministic routing
            route = deterministic_route(app)

            if route and route.get(
                "action"
            ) == "tool":
                return route

            # Try as an open command
            route = deterministic_route(
                "open " + app
            )

            if route and route.get(
                "action"
            ) == "tool":
                return route

            return None

        first_task = application_to_tool(
            first
        )

        second_task = application_to_tool(
            second
        )

        if first_task:
            tasks.append(first_task)

        if second_task:
            tasks.append(second_task)

        if len(tasks) >= 2:

            return {
                "action": "tasks",
                "tasks": tasks,
            }

    # ========================================================
    # TIME
    # ========================================================

    time_patterns = [
        "what time is it",
        "what is the time",
        "what's the time",
        "current time",
        "tell me the time",
        "time now",
        "what time it is",
        "what time is it now",
        "show current time",
        "show me the time",
    ]

    if any(
        pattern in value
        for pattern in time_patterns
    ):

        if tool_exists("current_time"):

            return make_tool_decision(
                "current_time"
            )

        # Fallback if tool doesn't exist
        return {
            "action": "chat",
            "response": (
                datetime.now().strftime(
                    "The current time is %I:%M:%S %p."
                )
            ),
        }

    # ========================================================
    # SYSTEM INFORMATION
    # ========================================================

    system_patterns = [
        "system information",
        "system info",
        "computer specs",
        "computer specification",
        "my computer specs",
        "computer details",
        "pc specs",
        "system specs",
        "show me my pc information",
        "show my pc information",
        "pc information",
        "computer information",
        "my pc information",
    ]

    if any(
        pattern in value
        for pattern in system_patterns
    ):

        if tool_exists("system_info"):

            return make_tool_decision(
                "system_info"
            )

    # ========================================================
    # OPEN NOTEPAD
    # ========================================================

    if any(
        phrase in value
        for phrase in [
            "open notepad",
            "open notebook",
            "start notepad",
            "launch notepad",
            "open the notepad",
            "start the notepad",
            "launch the notepad",
        ]
    ):

        if tool_exists("open_notepad"):

            return make_tool_decision(
                "open_notepad"
            )

    # ========================================================
    # OPEN CALCULATOR
    # ========================================================

    if any(
        phrase in value
        for phrase in [
            "open calculator",
            "open calc",
            "start calculator",
            "launch calculator",
            "open the calculator",
            "start the calculator",
            "launch the calculator",
        ]
    ):

        if tool_exists("open_calculator"):

            return make_tool_decision(
                "open_calculator"
            )

    # ========================================================
    # CLOSE NOTEPAD
    # ========================================================

    if any(
        phrase in value
        for phrase in [
            "close notepad",
            "close notebook",
            "close the notepad",
        ]
    ):

        if tool_exists(
            "close_application"
        ):

            return make_tool_decision(
                "close_application",
                {
                    "application": "notepad"
                },
            )

    # ========================================================
    # CLOSE CALCULATOR
    # ========================================================

    if any(
        phrase in value
        for phrase in [
            "close calculator",
            "close the calculator",
        ]
    ):

        if tool_exists(
            "close_application"
        ):

            return make_tool_decision(
                "close_application",
                {
                    "application": "calculator"
                },
            )

    # ========================================================
    # MEMORY SHOW
    # ========================================================

    memory_show_patterns = [
        "what do you remember about me",
        "what do you remember",
        "show my memory",
        "show memory",
        "what is in your memory",
        "what's in your memory",
    ]

    if any(
        pattern in value
        for pattern in memory_show_patterns
    ):

        return {
            "action": "memory",
            "operation": "show_memory",
        }

    # ========================================================
    # NAME RECALL
    # ========================================================

    if value in [
        "what is my name",
        "what's my name",
        "who am i",
        "do you know my name",
    ]:

        return {
            "action": "memory",
            "operation": "recall",
            "key": "name",
        }

    # ========================================================
    # NAME REMEMBER
    # ========================================================

    name_match = re.match(
        r"^(?:my name is|i am|i'm)\s+(.+)$",
        value,
        re.IGNORECASE,
    )

    if name_match:

        name = name_match.group(1).strip()

        return {
            "action": "memory",
            "operation": "remember",
            "key": "name",
            "value": name,
        }

    return None


# ============================================================
# TOOL DESCRIPTION FOR OLLAMA
# ============================================================

def build_tool_description():

    tools = list_tools()

    lines = []

    if isinstance(tools, dict):

        for name, info in tools.items():

            if isinstance(info, dict):

                description = info.get(
                    "description",
                    "No description provided.",
                )

            else:

                description = (
                    "No description provided."
                )

            lines.append(
                f"- {name}: {description}"
            )

    return "\n".join(lines)


# ============================================================
# AI ROUTER
# ============================================================

def ai_route(text):

    try:

        import requests

        tool_description = (
            build_tool_description()
        )

        prompt = f"""
You are JARVIS, a local Windows AI assistant.

You understand natural language.

You have two jobs:

1. Answer normal conversational questions.
2. Select tools when the user asks you to perform an action.

AVAILABLE TOOLS:

{tool_description}

============================================================
STRICT OUTPUT RULES
============================================================

Return ONLY one valid JSON object.

Never return markdown.

Never return ```.

Never write explanations outside the JSON.

Never invent a tool.

Never invent tool arguments.

IMPORTANT:
Only use arguments that are actually required by the
tool description.

If a tool requires no arguments, use:

"arguments": {{}}

============================================================
CHAT
============================================================

For jokes, explanations, greetings, general questions,
conversation, or questions you cannot perform with a tool:

{{
  "action": "chat",
  "response": "your answer"
}}

============================================================
ONE TOOL
============================================================

{{
  "action": "tool",
  "tool": "exact_tool_name",
  "arguments": {{}}
}}

============================================================
MULTIPLE TOOLS
============================================================

If the user asks for multiple independent actions:

{{
  "action": "tasks",
  "tasks": [
    {{
      "action": "tool",
      "tool": "open_notepad",
      "arguments": {{}}
    }},
    {{
      "action": "tool",
      "tool": "open_calculator",
      "arguments": {{}}
    }}
  ]
}}

============================================================
IMPORTANT EXAMPLE
============================================================

User:
open calculator and notepad

Correct:

{{
  "action": "tasks",
  "tasks": [
    {{
      "action": "tool",
      "tool": "open_calculator",
      "arguments": {{}}
    }},
    {{
      "action": "tool",
      "tool": "open_notepad",
      "arguments": {{}}
    }}
  ]
}}

Do NOT add arguments such as:

"calcMode"
"mode"
"window"
"application"

unless the actual tool description explicitly requires them.

============================================================
USER REQUEST
============================================================

{text}
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                },
            },
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

        raw = data.get(
            "response",
            "",
        )

        raw = str(raw).strip()

        print(
            "\nJARVIS AI DEBUG > Raw response:"
        )

        print(raw)

        return raw

    except Exception as e:

        print(
            f"\nJARVIS AI DEBUG > {e}"
        )

        return None


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(raw):

    if not raw:
        return None

    raw = str(raw).strip()

    # --------------------------------------------------------
    # Remove markdown fences
    # --------------------------------------------------------

    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:

        data = json.loads(raw)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    # --------------------------------------------------------
    # Extract JSON object
    # --------------------------------------------------------

    start = raw.find("{")
    end = raw.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        candidate = raw[
            start:end + 1
        ]

        try:

            data = json.loads(
                candidate
            )

            if isinstance(data, dict):
                return data

        except Exception:
            pass

    return None


# ============================================================
# SANITIZE TOOL ARGUMENTS
# ============================================================

def sanitize_tool_arguments(
    tool_name,
    arguments,
):

    if not isinstance(
        arguments,
        dict,
    ):

        return {}

    # --------------------------------------------------------
    # Never allow the AI to pass random arguments to
    # argument-less tools.
    #
    # This directly prevents:
    #
    # open_calculator + calcMode
    # ========================================================

    no_argument_tools = {
        "open_notepad",
        "open_calculator",
        "current_time",
        "system_info",
    }

    if tool_name in no_argument_tools:

        return {}

    return arguments


# ============================================================
# PARSE AI DECISION
# ============================================================

def parse_decision(raw):

    if not raw:
        return None

    if isinstance(raw, dict):

        data = raw

    else:

        data = extract_json(raw)

    if not isinstance(
        data,
        dict,
    ):

        print(
            "\nJARVIS DEBUG > "
            "AI did not return valid JSON."
        )

        return None

    action = data.get(
        "action"
    )

    tools = get_tool_names()

    # ========================================================
    # DIRECT TOOL ACTION
    # ========================================================

    if action in tools:

        arguments = sanitize_tool_arguments(
            action,
            data.get(
                "arguments",
                {},
            ),
        )

        return {
            "action": "tool",
            "tool": action,
            "arguments": arguments,
        }

    # ========================================================
    # SINGLE TOOL
    # ========================================================

    if action == "tool":

        tool_name = data.get(
            "tool"
        )

        if tool_name not in tools:

            print(
                "JARVIS DEBUG > "
                f"Unknown AI tool: "
                f"{tool_name}"
            )

            return None

        arguments = sanitize_tool_arguments(
            tool_name,
            data.get(
                "arguments",
                {},
            ),
        )

        return {
            "action": "tool",
            "tool": tool_name,
            "arguments": arguments,
        }

    # ========================================================
    # MULTIPLE TASKS
    # ========================================================

    if action in {
        "tasks",
        "multi_tool",
    }:

        raw_tasks = data.get(
            "tasks",
            data.get(
                "tools",
                [],
            ),
        )

        if not isinstance(
            raw_tasks,
            list,
        ):

            return None

        tasks = []

        for task in raw_tasks:

            if not isinstance(
                task,
                dict,
            ):

                continue

            task_action = task.get(
                "action"
            )

            # ------------------------------------------------
            # AI may return:
            #
            # {"action":"open_notepad"}
            #
            # ------------------------------------------------

            if task_action in tools:

                tool_name = task_action

                arguments = sanitize_tool_arguments(
                    tool_name,
                    task.get(
                        "arguments",
                        {},
                    ),
                )

                tasks.append({
                    "action": "tool",
                    "tool": tool_name,
                    "arguments": arguments,
                })

                continue

            # ------------------------------------------------
            # Normal:
            #
            # {"action":"tool","tool":"..."}
            # ------------------------------------------------

            if task_action != "tool":

                continue

            tool_name = task.get(
                "tool"
            )

            if tool_name not in tools:

                print(
                    "JARVIS DEBUG > "
                    f"Skipping unknown task: "
                    f"{tool_name}"
                )

                continue

            arguments = sanitize_tool_arguments(
                tool_name,
                task.get(
                    "arguments",
                    {},
                ),
            )

            tasks.append({
                "action": "tool",
                "tool": tool_name,
                "arguments": arguments,
            })

        if not tasks:

            return None

        return {
            "action": "tasks",
            "tasks": tasks,
        }

    # ========================================================
    # CHAT
    # ========================================================

    if action == "chat":

        response = data.get(
            "response",
            "",
        )

        if response is None:
            response = ""

        return {
            "action": "chat",
            "response": str(
                response
            ),
        }

    # ========================================================
    # EXIT
    # ========================================================

    if action == "exit":

        return {
            "action": "exit"
        }

    return None


# ============================================================
# MEMORY EXECUTION
# ============================================================

def execute_memory(decision):

    operation = decision.get(
        "operation"
    )

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    if operation == "remember":

        key = decision.get(
            "key"
        )

        value = decision.get(
            "value"
        )

        result = remember(
            key,
            value,
        )

        return result.get(
            "message",
            str(result),
        )

    # --------------------------------------------------------
    # RECALL
    # --------------------------------------------------------

    if operation == "recall":

        key = decision.get(
            "key"
        )

        result = recall(
            key
        )

        message = result.get(
            "message",
            str(result),
        )

        if (
            key == "name"
            and "=" in message
        ):

            value = message.split(
                "=",
                1,
            )[1].strip()

            return (
                f"Your name is "
                f"{value}."
            )

        return message

    # --------------------------------------------------------
    # SHOW MEMORY
    # --------------------------------------------------------

    if operation == "show_memory":

        result = show_memory()

        return result.get(
            "message",
            str(result),
        )

    # --------------------------------------------------------
    # FORGET
    # --------------------------------------------------------

    if operation == "forget":

        key = decision.get(
            "key"
        )

        result = forget(
            key
        )

        return result.get(
            "message",
            str(result),
        )

    return (
        "I couldn't understand "
        "that memory request."
    )


# ============================================================
# SINGLE TOOL EXECUTION
# ============================================================

def execute_tool(
    decision,
    show_header=True,
):

    tool_name = decision.get(
        "tool"
    )

    arguments = decision.get(
        "arguments",
        {},
    )

    if show_header:

        print(
            f"\nJARVIS > "
            f"Tool: {tool_name}"
        )

    tool = get_tool(
        tool_name
    )

    if not tool:

        message = (
            f"Unknown tool: "
            f"{tool_name}"
        )

        print(
            f"JARVIS DEBUG > "
            f"{message}"
        )

        return message

    # ========================================================
    # SANITIZE
    # ========================================================

    arguments = sanitize_tool_arguments(
        tool_name,
        arguments,
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    try:

        validation = validate_tool_call(
            tool_name,
            arguments,
        )

    except Exception as e:

        return (
            "Tool validation failed: "
            f"{e}"
        )

    if not validation.get(
        "valid",
        False,
    ):

        message = (
            "Tool call rejected: "
            + validation.get(
                "message",
                "Invalid arguments.",
            )
        )

        print(
            f"JARVIS DEBUG > "
            f"{message}"
        )

        return message

    # ========================================================
    # TOOL INFORMATION
    # ========================================================

    risk = tool.get(
        "risk",
        "UNKNOWN",
    )

    print(
        f"JARVIS > Risk: "
        f"{risk}"
    )

    if arguments:

        print(
            f"JARVIS > Arguments: "
            f"{arguments}"
        )

    print(
        f"JARVIS > Executing: "
        f"{tool_name}"
    )

    # ========================================================
    # EXECUTE
    # ========================================================

    try:

        function = tool.get(
            "function"
        )

        if not callable(
            function
        ):

            return (
                f"Tool {tool_name} "
                "has no callable function."
            )

        result = function(
            **arguments
        )

        if isinstance(
            result,
            dict,
        ):

            return str(
                result.get(
                    "message",
                    result,
                )
            )

        return str(
            result
        )

    except Exception as e:

        return (
            f"Tool execution "
            f"failed: {e}"
        )


# ============================================================
# MULTI-TASK EXECUTION
# ============================================================

def execute_tasks(decision):

    tasks = decision.get(
        "tasks",
        [],
    )

    if not tasks:

        return (
            "No tasks were provided."
        )

    print(
        f"\nJARVIS > "
        f"Executing {len(tasks)} "
        f"tasks in parallel."
    )

    results = {}

    worker_count = min(
        MAX_PARALLEL_TASKS,
        len(tasks),
    )

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as executor:

        future_map = {}

        for index, task in enumerate(
            tasks
        ):

            future = executor.submit(
                execute_tool,
                task,
                False,
            )

            future_map[
                future
            ] = index

        for future in as_completed(
            future_map
        ):

            index = future_map[
                future
            ]

            try:

                results[index] = (
                    future.result()
                )

            except Exception as e:

                results[index] = (
                    f"Task failed: {e}"
                )

    # ========================================================
    # KEEP ORIGINAL USER ORDER
    # ========================================================

    messages = []

    for index, task in enumerate(
        tasks
    ):

        tool_name = task.get(
            "tool",
            "unknown",
        )

        result = results.get(
            index,
            "No result.",
        )

        messages.append(
            f"{tool_name}: {result}"
        )

    print(
        "\nJARVIS > "
        "Multi-task results:"
    )

    for message in messages:

        print(
            f"  - {message}"
        )

    return "\n".join(
        messages
    )


# ============================================================
# PROCESS COMMAND
# ============================================================

def process_command(text):

    # --------------------------------------------------------
    # Empty input
    # --------------------------------------------------------

    if not text or not str(
        text
    ).strip():

        return {
            "exit": False,
            "message": None,
            "decision": None,
        }

    text = str(
        text
    ).strip()

    # ========================================================
    # GLOBAL EXIT
    # ========================================================

    if is_exit_command(
        text
    ):

        return {
            "exit": True,
            "message": "Shutting down.",
            "decision": {
                "action": "exit"
            },
        }

    # ========================================================
    # DETERMINISTIC ROUTER
    # ========================================================

    decision = deterministic_route(
        text
    )

    if decision:

        print(
            "\nJARVIS ROUTER > "
            "Deterministic"
        )

        print(
            f"JARVIS ROUTER > "
            f"{decision}"
        )

    # ========================================================
    # AI ROUTER
    # ========================================================

    else:

        print(
            "\nJARVIS ROUTER > AI"
        )

        raw = ai_route(
            text
        )

        decision = parse_decision(
            raw
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

    # ========================================================
    # FAILED ROUTING
    # ========================================================

    if not decision:

        return {
            "exit": False,
            "message": (
                "I couldn't understand "
                "that request."
            ),
            "decision": None,
        }

    # ========================================================
    # EXIT
    # ========================================================

    if decision.get(
        "action"
    ) == "exit":

        return {
            "exit": True,
            "message": "Shutting down.",
            "decision": decision,
        }

    # ========================================================
    # MEMORY
    # ========================================================

    if decision.get(
        "action"
    ) == "memory":

        message = execute_memory(
            decision
        )

        return {
            "exit": False,
            "message": message,
            "decision": decision,
        }

    # ========================================================
    # SINGLE TOOL
    # ========================================================

    if decision.get(
        "action"
    ) == "tool":

        message = execute_tool(
            decision
        )

        return {
            "exit": False,
            "message": message,
            "decision": decision,
        }

    # ========================================================
    # MULTIPLE TOOLS
    # ========================================================

    if decision.get(
        "action"
    ) == "tasks":

        message = execute_tasks(
            decision
        )

        return {
            "exit": False,
            "message": message,
            "decision": decision,
        }

    # ========================================================
    # CHAT
    # ========================================================

    if decision.get(
        "action"
    ) == "chat":

        message = decision.get(
            "response",
            "I couldn't understand "
            "that request.",
        )

        return {
            "exit": False,
            "message": message,
            "decision": decision,
        }

    return {
        "exit": False,
        "message": (
            "I couldn't understand "
            "that request."
        ),
        "decision": decision,
    }


# ============================================================
# TEXT MODE
# ============================================================

def text_mode():

    print("\n")
    print("=" * 50)
    print("              TEXT MODE")
    print("=" * 50)
    print()

    print(
        "Type 'exit' to return "
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

            print()

            return "menu"

        # ----------------------------------------------------
        # Ignore blank Enter
        # ----------------------------------------------------

        if not text:
            continue

        # ----------------------------------------------------
        # Exit
        # ----------------------------------------------------

        if is_exit_command(
            text
        ):

            print(
                "\nJARVIS > "
                "Leaving text mode."
            )

            return "menu"

        # ----------------------------------------------------
        # Process
        # ----------------------------------------------------

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
            "Voice system "
            "is unavailable."
        )

        return "menu"

    print("\n")
    print("=" * 50)
    print("              VOICE MODE")
    print("=" * 50)
    print()

    print(
        "Say 'exit', 'stop', "
        "or 'shutdown' to "
        "return to the main menu."
    )

    while True:

        try:

            text = listen()

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > "
                f"{e}"
            )

            continue

        if not text:

            continue

        text = str(
            text
        ).strip()

        if not text:

            continue

        if is_exit_command(
            text
        ):

            message = (
                "Leaving voice mode."
            )

            print(
                f"\nJARVIS > "
                f"{message}"
            )

            speak_safe(
                message
            )

            return "menu"

        result = process_command(
            text
        )

        if result.get(
            "message"
        ):

            print(
                f"\nJARVIS > "
                f"{result['message']}"
            )

            speak_safe(
                result[
                    "message"
                ]
            )

        if result.get(
            "exit"
        ):

            return "shutdown"


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

            print()

            return "shutdown"

        if mode in EXIT_COMMANDS:

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

    print("=" * 50)
    print("          JARVIS ONLINE")
    print("=" * 50)

    print(
        f"Local AI: "
        f"{OLLAMA_MODEL}"
    )

    print(
        f"Tools: "
        f"{len(get_tool_names())}"
    )

    print(
        "Router: Deterministic + AI + Memory"
    )

    print(
        "Multi-Task Execution: ENABLED"
    )

    print(
        "Parallel Tasks: ENABLED"
    )

    print(
        "Tool Arguments: ENABLED"
    )

    print(
        "Validation: ENABLED"
    )

    print(
        "Voice Output: ENABLED"
        if speak is not None
        else
        "Voice Output: OPTIONAL"
    )

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

        print(
            "\nJARVIS > "
            "Shutting down."
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()