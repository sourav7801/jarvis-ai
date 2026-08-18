import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============================================================
# JARVIS TOOL SYSTEM
# ============================================================

from tools.registry import get_tool, list_tools
from tools.tool_schema import validate_tool_call
from tools.memory import remember, recall, show_memory, forget


# ============================================================
# OPTIONAL VOICE SYSTEM
# ============================================================

try:
    from voice import listen, speak
except Exception:
    listen = None
    speak = None


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

MAX_PARALLEL_TASKS = 4


# ============================================================
# GLOBAL EXIT COMMANDS
# ============================================================

EXIT_COMMANDS = {
    "exit",
    "quit",
    "shutdown",
    "bye",
}


# ============================================================
# MAIN MENU COMMANDS
# ============================================================

MAIN_MENU_COMMANDS = {
    "go to main menu",
    "return to main menu",
    "back to main menu",
    "exit voice mode",
    "leave voice mode",
    "go back",
    "main menu",
}


# ============================================================
# OUTPUT
# ============================================================

def say(message):
    """
    Print and speak a response once.
    """

    if message is None:
        return

    message = str(message)

    print(
        f"\nJARVIS > {message}"
    )

    if speak:

        try:

            speak(message)

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > {e}"
            )


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):

    if not text:
        return ""

    return " ".join(
        str(text)
        .strip()
        .lower()
        .split()
    )


# ============================================================
# EXIT CHECK
# ============================================================

def is_exit_command(text):

    return normalize(text) in EXIT_COMMANDS


# ============================================================
# MAIN MENU CHECK
# ============================================================

def is_main_menu_command(text):

    value = normalize(text)

    if not value:
        return False

    if value in MAIN_MENU_COMMANDS:
        return True

    # Natural variations
    phrases = [
        "go to main menu",
        "return to main menu",
        "back to main menu",
        "exit voice mode",
        "leave voice mode",
    ]

    for phrase in phrases:

        if phrase in value:
            return True

    return False


# ============================================================
# TOOL HELPERS
# ============================================================

def tool_exists(tool_name):

    return tool_name in list_tools()


def make_tool(
    tool_name,
    arguments=None,
):

    if arguments is None:
        arguments = {}

    return {
        "action": "tool",
        "tool": tool_name,
        "arguments": arguments,
    }


def make_tasks(*tasks):

    return {
        "action": "tasks",
        "tasks": list(tasks),
    }


# ============================================================
# APPLICATION RESOLVER
# ============================================================

def resolve_application(name):

    value = normalize(name)

    value = re.sub(
        r"\s+(for me|please)$",
        "",
        value,
    ).strip()

    aliases = {
        "notebook": "notepad",
        "note pad": "notepad",
        "calc": "calculator",
    }

    return aliases.get(
        value,
        value,
    )


# ============================================================
# DETERMINISTIC ROUTER
# ============================================================

def deterministic_route(text):

    value = normalize(text)

    if not value:
        return None


    # ========================================================
    # MAIN MENU
    #
    # IMPORTANT:
    # This is checked BEFORE AI routing.
    # ========================================================

    if is_main_menu_command(value):

        return {
            "action": "main_menu"
        }


    # ========================================================
    # GLOBAL EXIT
    # ========================================================

    if is_exit_command(value):

        return {
            "action": "exit"
        }


    # ========================================================
    # CLOSE BOTH
    # ========================================================

    close_both_patterns = [

        "close both",
        "close them both",
        "close both applications",
        "close both apps",

        "close notepad and calculator",
        "close calculator and notepad",

        "close notepad and calc",
        "close calc and notepad",

    ]

    if any(
        pattern in value
        for pattern in close_both_patterns
    ):

        close_tool = (
            "close_application"
            if tool_exists("close_application")
            else None
        )

        if close_tool:

            return make_tasks(

                make_tool(
                    close_tool,
                    {
                        "application": "notepad"
                    }
                ),

                make_tool(
                    close_tool,
                    {
                        "application": "calculator"
                    }
                ),
            )


    # ========================================================
    # OPEN MULTIPLE APPLICATIONS
    # ========================================================

    multi_open_patterns = [

        r"^(?:open|start|launch)\s+(.+?)\s+and\s+(.+)$",

        r"^(?:can you|could you|please)\s+"
        r"(?:open|start|launch)\s+"
        r"(.+?)\s+and\s+(.+?)(?:\s+for me)?$",

    ]

    for pattern in multi_open_patterns:

        match = re.match(
            pattern,
            value,
            re.IGNORECASE,
        )

        if not match:
            continue

        first = resolve_application(
            match.group(1)
        )

        second = resolve_application(
            match.group(2)
        )

        tasks = []


        # ----------------------------------------------------
        # Open application tool
        # ----------------------------------------------------

        if tool_exists("open_application"):

            tasks.append(
                make_tool(
                    "open_application",
                    {
                        "application": first
                    }
                )
            )

            tasks.append(
                make_tool(
                    "open_application",
                    {
                        "application": second
                    }
                )
            )


        elif tool_exists("open_notepad"):

            if first == "notepad":

                tasks.append(
                    make_tool(
                        "open_notepad"
                    )
                )

            if second == "notepad":

                tasks.append(
                    make_tool(
                        "open_notepad"
                    )
                )


            if first == "calculator":

                tasks.append(
                    make_tool(
                        "open_calculator"
                    )
                )

            if second == "calculator":

                tasks.append(
                    make_tool(
                        "open_calculator"
                    )
                )


        if len(tasks) >= 2:

            return make_tasks(
                *tasks
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

    ]

    if any(
        pattern in value
        for pattern in time_patterns
    ):

        if tool_exists("current_time"):

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
        "pc information",
        "computer information",

    ]

    if any(
        pattern in value
        for pattern in system_patterns
    ):

        if tool_exists("system_info"):

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
        "launch notepad",

    ]

    if any(
        phrase in value
        for phrase in notepad_patterns
    ):

        if tool_exists("open_application"):

            return make_tool(
                "open_application",
                {
                    "application": "notepad"
                }
            )

        if tool_exists("open_notepad"):

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
        "launch calculator",

    ]

    if any(
        phrase in value
        for phrase in calculator_patterns
    ):

        if tool_exists("open_application"):

            return make_tool(
                "open_application",
                {
                    "application": "calculator"
                }
            )

        if tool_exists("open_calculator"):

            return make_tool(
                "open_calculator"
            )


    # ========================================================
    # CLOSE NOTEPAD
    # ========================================================

    close_notepad_patterns = [

        "close notepad",
        "close notebook",

    ]

    if any(
        phrase in value
        for phrase in close_notepad_patterns
    ):

        if tool_exists("close_application"):

            return make_tool(
                "close_application",
                {
                    "application": "notepad"
                }
            )


    # ========================================================
    # CLOSE CALCULATOR
    # ========================================================

    close_calculator_patterns = [

        "close calculator",
        "close calc",

    ]

    if any(
        phrase in value
        for phrase in close_calculator_patterns
    ):

        if tool_exists("close_application"):

            return make_tool(
                "close_application",
                {
                    "application": "calculator"
                }
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

    if value in {

        "what is my name",
        "what's my name",
        "who am i",
        "do you know my name",

    }:

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

        name = (
            name_match
            .group(1)
            .strip()
        )

        return {
            "action": "memory",
            "operation": "remember",
            "key": "name",
            "value": name,
        }


    # ========================================================
    # NO MATCH
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

Return ONLY valid JSON.

AVAILABLE TOOLS:

{tool_description}


IMPORTANT:

1. Never invent tool names.
2. Never invent arguments.
3. Normal conversation = chat.
4. One tool = tool.
5. Multiple independent tools = tasks.
6. Every tool call requires an arguments object.
7. Use exact tool names.
8. If application control is requested, use open_application
   or close_application only when available.
9. NEVER treat "go to main menu" as an application command.
10. NEVER treat "return to main menu" as an application command.
11. NEVER treat "back to main menu" as an application command.
12. NEVER open an application because the user said "main menu".


CHAT FORMAT:

{{
    "action": "chat",
    "response": "your answer"
}}


TOOL FORMAT:

{{
    "action": "tool",
    "tool": "tool_name",
    "arguments": {{}}
}}


TASK FORMAT:

{{
    "action": "tasks",
    "tasks": [
        {{
            "action": "tool",
            "tool": "tool_name",
            "arguments": {{}}
        }}
    ]
}}


EXIT FORMAT:

{{
    "action": "exit"
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

            timeout=60,

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
# CLEAN TOOL ARGUMENTS
# ============================================================

def clean_tool_arguments(
    tool_name,
    arguments,
):

    if not isinstance(
        arguments,
        dict,
    ):

        arguments = {}


    tool_info = list_tools().get(
        tool_name
    )


    if not tool_info:

        return {}


    accepted = set()


    schema = tool_info.get(
        "schema",
        {}
    )


    if isinstance(
        schema,
        dict,
    ):

        properties = schema.get(
            "properties",
            {}
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
        {}
    )


    if isinstance(
        argument_schema,
        dict,
    ):

        accepted.update(
            argument_schema.keys()
        )


    if not accepted:

        return arguments


    cleaned = {}


    for key, value in arguments.items():

        if key in accepted:

            cleaned[key] = value


    return cleaned


# ============================================================
# REPAIR TOOL CALL
# ============================================================

def repair_tool_call(
    tool_name,
    arguments,
):

    if not isinstance(
        arguments,
        dict,
    ):

        arguments = {}


    if tool_name == "open_application":

        application = arguments.get(
            "application"
        )

        if application:

            arguments[
                "application"
            ] = resolve_application(
                application
            )


    if tool_name == "close_application":

        application = arguments.get(
            "application"
        )

        if application:

            arguments[
                "application"
            ] = resolve_application(
                application
            )

        else:

            return None


    return arguments


# ============================================================
# NORMALIZE TOOL DECISION
# ============================================================

def normalize_tool_decision(
    tool_name,
    arguments,
):

    tools = list_tools()


    if tool_name not in tools:

        return None


    arguments = clean_tool_arguments(
        tool_name,
        arguments,
    )


    arguments = repair_tool_call(
        tool_name,
        arguments,
    )


    if arguments is None:

        return None


    return {
        "action": "tool",
        "tool": tool_name,
        "arguments": arguments,
    }


# ============================================================
# PARSE AI DECISION
# ============================================================

def parse_decision(raw):

    if not raw:

        return None


    if isinstance(
        raw,
        dict,
    ):

        data = raw

    else:

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


    tools = list_tools()


    # ========================================================
    # MAIN MENU SAFETY
    #
    # AI should never get here for main-menu commands,
    # but this is a second safety layer.
    # ========================================================

    if action == "main_menu":

        return {
            "action": "main_menu"
        }


    # ========================================================
    # DIRECT TOOL
    # ========================================================

    if action in tools:

        arguments = data.get(
            "arguments",
            {},
        )

        return normalize_tool_decision(
            action,
            arguments,
        )


    # ========================================================
    # SINGLE TOOL
    # ========================================================

    if action == "tool":

        tool_name = data.get(
            "tool"
        )


        if tool_name not in tools:

            return None


        arguments = data.get(
            "arguments",
            {},
        )


        return normalize_tool_decision(
            tool_name,
            arguments,
        )


    # ========================================================
    # TASKS
    # ========================================================

    if action == "tasks":

        raw_tasks = data.get(
            "tasks",
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


            if task_action in tools:

                normalized = (
                    normalize_tool_decision(
                        task_action,
                        task.get(
                            "arguments",
                            {},
                        ),
                    )
                )


                if normalized:

                    tasks.append(
                        normalized
                    )

                continue


            if task_action != "tool":

                continue


            tool_name = task.get(
                "tool"
            )


            if tool_name not in tools:

                continue


            normalized = (
                normalize_tool_decision(
                    tool_name,
                    task.get(
                        "arguments",
                        {},
                    ),
                )
            )


            if normalized:

                tasks.append(
                    normalized
                )


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

        return {
            "action": "chat",
            "response": str(
                data.get(
                    "response",
                    "",
                )
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
# MEMORY
# ============================================================

def execute_memory(
    decision
):

    operation = decision.get(
        "operation"
    )


    if operation == "remember":

        result = remember(
            decision.get("key"),
            decision.get("value"),
        )

        return result.get(
            "message",
            str(result),
        )


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


    if operation == "show_memory":

        result = show_memory()

        return result.get(
            "message",
            str(result),
        )


    if operation == "forget":

        result = forget(
            decision.get("key")
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
# EXECUTE ONE TOOL
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

        return (
            "Tool call rejected: "
            + validation.get(
                "message",
                "Validation failed.",
            )
        )


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
            f"Tool execution "
            f"failed: {e}"
        )


# ============================================================
# EXECUTE TASKS
# ============================================================

def execute_tasks(
    decision
):

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
                    f"Task failed: "
                    f"{e}"
                )


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
            f"{tool_name}: "
            f"{result}"
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
            "menu": False,
            "message": None,
        }


    # ========================================================
    # MAIN MENU — ALWAYS FIRST
    # ========================================================

    if is_main_menu_command(text):

        return {
            "exit": False,
            "menu": True,
            "message": (
                "Returning to the main menu."
            ),
        }


    # ========================================================
    # GLOBAL EXIT
    # ========================================================

    if is_exit_command(text):

        return {
            "exit": True,
            "menu": False,
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
    # ROUTING FAILURE
    # ========================================================

    if not decision:

        return {
            "exit": False,
            "menu": False,
            "message": (
                "I couldn't understand "
                "that request."
            ),
        }


    # ========================================================
    # MAIN MENU
    # ========================================================

    if decision.get(
        "action"
    ) == "main_menu":

        return {
            "exit": False,
            "menu": True,
            "message": (
                "Returning to the main menu."
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
            "menu": False,
            "message": "Shutting down.",
        }


    # ========================================================
    # MEMORY
    # ========================================================

    if decision.get(
        "action"
    ) == "memory":

        return {
            "exit": False,
            "menu": False,
            "message": execute_memory(
                decision
            ),
        }


    # ========================================================
    # TOOL
    # ========================================================

    if decision.get(
        "action"
    ) == "tool":

        return {
            "exit": False,
            "menu": False,
            "message": execute_tool(
                decision
            ),
        }


    # ========================================================
    # TASKS
    # ========================================================

    if decision.get(
        "action"
    ) == "tasks":

        return {
            "exit": False,
            "menu": False,
            "message": execute_tasks(
                decision
            ),
        }


    # ========================================================
    # CHAT
    # ========================================================

    if decision.get(
        "action"
    ) == "chat":

        return {
            "exit": False,
            "menu": False,
            "message": decision.get(
                "response",
                "I couldn't understand "
                "that request.",
            ),
        }


    return {
        "exit": False,
        "menu": False,
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


        if not text:

            continue


        # ====================================================
        # MAIN MENU
        # ====================================================

        if is_main_menu_command(text):

            say(
                "Returning to the main menu."
            )

            return "menu"


        # ====================================================
        # SHUTDOWN
        # ====================================================

        if is_exit_command(text):

            say(
                "Shutting down."
            )

            return "shutdown"


        # ====================================================
        # PROCESS
        # ====================================================

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
        "Say 'exit', 'stop', or 'shutdown' "
        "to return to the main menu."
    )

    print(
        "You can also say "
        "'go to main menu'."
    )

    print()


    while True:

        # ====================================================
        # LISTEN
        # ====================================================

        try:

            text = listen()

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > "
                f"{e}"
            )

            continue


        # ====================================================
        # NOTHING HEARD
        # ====================================================

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


        print(
            f"\nYOU 🎤 > {text}"
        )


        # ====================================================
        # MAIN MENU — BEFORE PROCESS_COMMAND
        #
        # THIS IS THE IMPORTANT FIX.
        # ====================================================

        if is_main_menu_command(text):

            message = (
                "Returning to the main menu."
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

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"{e}"
                    )


            return "menu"


        # ====================================================
        # SHUTDOWN — BEFORE AI
        # ====================================================

        if is_exit_command(text):

            message = (
                "Shutting down."
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

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"{e}"
                    )


            return "shutdown"


        # ====================================================
        # NORMAL COMMAND
        # ====================================================

        result = process_command(
            text
        )


        # ====================================================
        # RESPONSE
        # ====================================================

        message = result.get(
            "message"
        )


        if message:

            print(
                f"\nJARVIS > "
                f"{message}"
            )


            if speak:

                try:

                    speak(
                        message
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"{e}"
                    )


        # ====================================================
        # RETURN MENU
        # ====================================================

        if result.get(
            "menu"
        ):

            return "menu"


        # ====================================================
        # SHUTDOWN
        # ====================================================

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


        # ====================================================
        # SHUTDOWN
        # ====================================================

        if mode in {
            "exit",
            "quit",
            "shutdown",
            "bye",
        }:

            return "shutdown"


        # ====================================================
        # TEXT
        # ====================================================

        if mode == "t":

            result = text_mode()


            if result == "shutdown":

                return "shutdown"


            continue


        # ====================================================
        # VOICE
        # ====================================================

        if mode == "v":

            result = voice_mode()


            if result == "shutdown":

                return "shutdown"


            continue


        # ====================================================
        # INVALID
        # ====================================================

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
        "Router: "
        "Deterministic + AI + Memory"
    )


    print(
        "Multi-Task Execution: ENABLED"
    )


    print(
        "Parallel Tasks: ENABLED"
    )


    print(
        "AI Argument Cleanup: ENABLED"
    )


    print(
        "Tool Validation: ENABLED"
    )


    print(
        "Voice Output: "
        + (
            "ENABLED"
            if speak
            else "UNAVAILABLE"
        )
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
# PROGRAM ENTRY
# ============================================================

if __name__ == "__main__":

    main()