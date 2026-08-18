import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

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

MAX_PARALLEL_TASKS = 8

EXIT_COMMANDS = {
    "exit",
    "quit",
    "stop",
    "shutdown",
    "bye",
}


# ============================================================
# OUTPUT
# ============================================================

def say(message):
    """
    Print the JARVIS response and optionally speak it.
    """

    if message is None:
        return

    print(f"\nJARVIS > {message}")

    if speak:

        try:
            speak(str(message))

        except Exception as e:
            print(
                f"JARVIS VOICE DEBUG > {e}"
            )


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):
    """
    Normalize whitespace and convert text to lowercase.
    """

    if not text:
        return ""

    return " ".join(
        str(text).strip().lower().split()
    )


def is_exit_command(text):
    return normalize(text) in EXIT_COMMANDS


# ============================================================
# TOOL HELPERS
# ============================================================

def make_tool(tool_name, arguments=None):
    """
    Create a standard tool decision.
    """

    if arguments is None:
        arguments = {}

    return {
        "action": "tool",
        "tool": tool_name,
        "arguments": arguments,
    }


def make_tasks(tasks):
    """
    Create a standard multi-task decision.
    """

    return {
        "action": "tasks",
        "tasks": tasks,
    }


# ============================================================
# APPLICATION NAME -> TOOL
# ============================================================

APPLICATION_TO_TOOL = {
    "notepad": "open_notepad",
    "notebook": "open_notepad",
    "calculator": "open_calculator",
    "calc": "open_calculator",
}


def application_to_open_tool(name):
    """
    Convert a natural application name into a registered
    JARVIS tool.
    """

    name = normalize(name)

    return APPLICATION_TO_TOOL.get(name)


# ============================================================
# MULTI-APPLICATION DETECTION
# ============================================================

def detect_multiple_applications(text):
    """
    Detect commands such as:

        open notepad and calculator
        open calculator and notepad
        launch notepad and calculator
        start notepad and calculator
        open notepad, calculator
        can you open notepad and calculator for me

    Returns a list of tool decisions.
    """

    value = normalize(text)

    # --------------------------------------------------------
    # Only process commands that sound like opening apps.
    # --------------------------------------------------------

    open_words = [
        "open",
        "launch",
        "start",
    ]

    if not any(
        re.search(
            rf"\b{re.escape(word)}\b",
            value,
        )
        for word in open_words
    ):
        return []

    # --------------------------------------------------------
    # Determine whether this is an application-opening
    # request.
    # --------------------------------------------------------

    app_names = list(
        APPLICATION_TO_TOOL.keys()
    )

    found_apps = []

    for app_name in app_names:

        if re.search(
            rf"\b{re.escape(app_name)}\b",
            value,
            re.IGNORECASE,
        ):

            if app_name not in found_apps:
                found_apps.append(app_name)

    # --------------------------------------------------------
    # Need at least two applications.
    # --------------------------------------------------------

    if len(found_apps) < 2:
        return []

    tasks = []

    for app_name in found_apps:

        tool_name = application_to_open_tool(
            app_name
        )

        if not tool_name:
            continue

        tasks.append(
            make_tool(
                tool_name,
                {},
            )
        )

    return tasks


# ============================================================
# DETERMINISTIC ROUTER
# ============================================================

def deterministic_route(text):

    value = normalize(text)

    # ========================================================
    # EXIT
    # ========================================================

    if is_exit_command(value):

        return {
            "action": "exit"
        }

    # ========================================================
    # MULTI-APPLICATION COMMANDS
    #
    # IMPORTANT:
    # This happens BEFORE individual app detection.
    # ========================================================

    multi_tasks = detect_multiple_applications(
        value
    )

    if len(multi_tasks) >= 2:

        return make_tasks(
            multi_tasks
        )

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
        "tell me current time",
    ]

    if any(
        pattern in value
        for pattern in time_patterns
    ):

        return make_tool(
            "current_time"
        )

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
        "show me computer information",
        "show computer information",
        "tell me my pc information",
        "tell me about my computer",
    ]

    if any(
        pattern in value
        for pattern in system_patterns
    ):

        return make_tool(
            "system_info"
        )

    # ========================================================
    # OPEN NOTEPAD
    # ========================================================

    notepad_patterns = [
        "open notepad",
        "open notebook",
        "start notepad",
        "start notebook",
        "launch notepad",
        "launch notebook",
    ]

    if any(
        pattern in value
        for pattern in notepad_patterns
    ):

        return make_tool(
            "open_notepad"
        )

    # ========================================================
    # OPEN CALCULATOR
    # ========================================================

    calculator_patterns = [
        "open calculator",
        "open calc",
        "start calculator",
        "start calc",
        "launch calculator",
        "launch calc",
    ]

    if any(
        pattern in value
        for pattern in calculator_patterns
    ):

        return make_tool(
            "open_calculator"
        )

    # ========================================================
    # CLOSE NOTEPAD
    # ========================================================

    close_notepad_patterns = [
        "close notepad",
        "close notebook",
        "stop notepad",
    ]

    if any(
        pattern in value
        for pattern in close_notepad_patterns
    ):

        return make_tool(
            "close_application",
            {
                "application": "notepad"
            },
        )

    # ========================================================
    # CLOSE CALCULATOR
    # ========================================================

    close_calculator_patterns = [
        "close calculator",
        "close calc",
        "stop calculator",
    ]

    if any(
        pattern in value
        for pattern in close_calculator_patterns
    ):

        return make_tool(
            "close_application",
            {
                "application": "calculator"
            },
        )

    # ========================================================
    # MEMORY - SHOW
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
    # MEMORY - NAME RECALL
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
    # MEMORY - NAME REMEMBER
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

    # ========================================================
    # NO DETERMINISTIC MATCH
    # ========================================================

    return None


# ============================================================
# TOOL DESCRIPTION
# ============================================================

def build_tool_description():

    tools = list_tools()

    lines = []

    for name, info in tools.items():

        description = info.get(
            "description",
            "No description provided.",
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

Understand the user's request and either:

1. Answer normally using "chat"
2. Use one tool using "tool"
3. Use multiple independent tools using "tasks"

AVAILABLE TOOLS:

{tool_description}

IMPORTANT RULES:

- Return ONLY valid JSON.
- Never use markdown.
- Never explain your JSON.
- Never invent a tool.
- Use exact tool names.
- Every tool requires an arguments object.
- For normal questions, jokes, explanations,
  examples, greetings and general conversation,
  use "chat".
- If several independent applications should be
  opened or several independent tasks should run,
  use "tasks".

SINGLE TOOL FORMAT:

{{
  "action": "tool",
  "tool": "tool_name",
  "arguments": {{}}
}}

MULTIPLE TASK FORMAT:

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

CHAT FORMAT:

{{
  "action": "chat",
  "response": "your answer"
}}

Examples:

User:
tell me a joke

Response:
{{
  "action": "chat",
  "response": "Why did the computer get cold? It left its Windows open."
}}

User:
open notepad

Response:
{{
  "action": "tool",
  "tool": "open_notepad",
  "arguments": {{}}
}}

User:
open notepad and calculator

Response:
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

User:
what can you do

Response:
{{
  "action": "chat",
  "response": "I can open applications, manage supported tools, provide system information, remember information, answer questions, and handle multiple independent tasks."
}}

USER REQUEST:

{text}
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()

        raw = data.get(
            "response",
            "",
        ).strip()

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
    # Remove markdown fences.
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
    )

    # --------------------------------------------------------
    # Direct JSON.
    # --------------------------------------------------------

    try:

        return json.loads(raw)

    except Exception:
        pass

    # --------------------------------------------------------
    # Search for JSON object.
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

            return json.loads(
                candidate
            )

        except Exception:
            pass

    return None


# ============================================================
# PARSE AI DECISION
# ============================================================

def parse_decision(raw):

    if not raw:
        return None

    # --------------------------------------------------------
    # Already a dictionary.
    # --------------------------------------------------------

    if isinstance(raw, dict):

        data = raw

    else:

        data = extract_json(raw)

    if not isinstance(data, dict):

        print(
            "\nJARVIS DEBUG > "
            "AI did not return valid JSON."
        )

        return None

    action = data.get(
        "action"
    )

    tools = list_tools()

    # ========================================================
    # DIRECT TOOL NAME
    # ========================================================

    if action in tools:

        return {
            "action": "tool",
            "tool": action,
            "arguments": data.get(
                "arguments",
                {},
            ),
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
                f"JARVIS DEBUG > "
                f"Unknown AI tool: "
                f"{tool_name}"
            )

            return None

        arguments = data.get(
            "arguments",
            {},
        )

        if not isinstance(
            arguments,
            dict,
        ):

            arguments = {}

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
        "multi_task",
    }:

        raw_tasks = data.get(
            "tasks",
            [],
        )

        # Compatibility with another possible AI format.
        if not raw_tasks:

            raw_tasks = data.get(
                "tools",
                [],
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

            # --------------------------------------------
            # Direct tool name.
            # --------------------------------------------

            if task_action in tools:

                tool_name = task_action

            # --------------------------------------------
            # Standard tool format.
            # --------------------------------------------

            elif task_action == "tool":

                tool_name = task.get(
                    "tool"
                )

            else:

                continue

            if tool_name not in tools:
                continue

            arguments = task.get(
                "arguments",
                {},
            )

            if not isinstance(
                arguments,
                dict,
            ):

                arguments = {}

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

        if not response:

            response = (
                "I'm ready. "
                "What would you like me to do?"
            )

        return {
            "action": "chat",
            "response": response,
        }

    # ========================================================
    # EXIT
    # ========================================================

    if action == "exit":

        return {
            "action": "exit"
        }

    # ========================================================
    # UNKNOWN ACTION
    # ========================================================

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

    if not isinstance(
        arguments,
        dict,
    ):

        arguments = {}

    if show_header:

        print(
            f"\nJARVIS > "
            f"Tool: {tool_name}"
        )

    # --------------------------------------------------------
    # Find tool.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Validate.
    # --------------------------------------------------------

    try:

        validation = validate_tool_call(
            tool_name,
            arguments,
        )

    except Exception as e:

        return (
            f"Tool validation failed: "
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

    # --------------------------------------------------------
    # Tool information.
    # --------------------------------------------------------

    print(
        f"JARVIS > Risk: "
        f"{tool.get('risk', 'UNKNOWN')}"
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

    # --------------------------------------------------------
    # Execute.
    # --------------------------------------------------------

    try:

        result = tool[
            "function"
        ](
            **arguments
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

    except Exception as e:

        return (
            f"Tool execution failed: "
            f"{e}"
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

    # --------------------------------------------------------
    # Limit number of tasks.
    # --------------------------------------------------------

    tasks = tasks[
        :MAX_PARALLEL_TASKS
    ]

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

    # --------------------------------------------------------
    # Execute concurrently.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Display results in original order.
    # --------------------------------------------------------

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

    if not text or not text.strip():

        return {
            "exit": False,
            "message": None,
        }

    # ========================================================
    # GLOBAL EXIT
    # ========================================================

    if is_exit_command(text):

        return {
            "exit": True,
            "message": "Shutting down.",
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
    # ROUTING FAILED
    # ========================================================

    if not decision:

        return {
            "exit": False,
            "message": (
                "I couldn't understand "
                "that request."
            ),
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
        }

    # ========================================================
    # MULTIPLE TASKS
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
        }

    # ========================================================
    # CHAT
    # ========================================================

    if decision.get(
        "action"
    ) == "chat":

        message = decision.get(
            "response",
            "",
        )

        if not message:

            message = (
                "I'm ready. "
                "What would you like me to do?"
            )

        return {
            "exit": False,
            "message": message,
        }

    # ========================================================
    # FALLBACK
    # ========================================================

    return {
        "exit": False,
        "message": (
            "I couldn't understand "
            "that request."
        ),
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
        # Ignore blank Enter presses.
        # ----------------------------------------------------

        if not text:
            continue

        # ----------------------------------------------------
        # Exit text mode.
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
        # Process.
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

            print(
                "JARVIS > "
                "I didn't hear anything."
            )

            continue

        text = str(
            text
        ).strip()

        if not text:
            continue

        # ----------------------------------------------------
        # Exit voice mode.
        # ----------------------------------------------------

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

            if speak:

                try:
                    speak(
                        message
                    )

                except Exception:
                    pass

            return "menu"

        # ----------------------------------------------------
        # Process.
        # ----------------------------------------------------

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

            if speak:

                try:

                    speak(
                        result[
                            "message"
                        ]
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"{e}"
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

        # ----------------------------------------------------
        # Shutdown.
        # ----------------------------------------------------

        if mode in EXIT_COMMANDS:

            return "shutdown"

        # ----------------------------------------------------
        # Text mode.
        # ----------------------------------------------------

        if mode == "t":

            result = text_mode()

            if result == "shutdown":

                return "shutdown"

            continue

        # ----------------------------------------------------
        # Voice mode.
        # ----------------------------------------------------

        if mode == "v":

            result = voice_mode()

            if result == "shutdown":

                return "shutdown"

            continue

        # ----------------------------------------------------
        # Invalid.
        # ----------------------------------------------------

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
        f"{len(list_tools())}"
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