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
# APPLICATION EXIT COMMANDS
# ============================================================

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
    Display a JARVIS response and optionally speak it.
    """

    if message is None:
        return


    message = str(
        message
    )


    print(
        f"\nJARVIS > {message}"
    )


    if speak:

        try:

            speak(
                message
            )

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > {e}"
            )


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):
    """
    Normalize user input.
    """

    if not text:

        return ""


    return " ".join(
        str(text)
        .strip()
        .lower()
        .split()
    )


def is_exit_command(text):

    return (
        normalize(text)
        in EXIT_COMMANDS
    )


# ============================================================
# TOOL HELPERS
# ============================================================

def tool_exists(tool_name):

    return (
        tool_name
        in list_tools()
    )


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


def make_tasks(
    *tasks
):

    return {
        "action": "tasks",
        "tasks": list(tasks),
    }


# ============================================================
# DETERMINISTIC ROUTER
# ============================================================

def deterministic_route(text):

    value = normalize(
        text
    )


    if not value:

        return None


    # ========================================================
    # EXIT
    # ========================================================

    if is_exit_command(
        value
    ):

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

        return make_tasks(

            make_tool(
                "close_application",
                {
                    "application": "notepad"
                }
            ),

            make_tool(
                "close_application",
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


        first = match.group(
            1
        ).strip()


        second = match.group(
            2
        ).strip()


        tasks = []


        first_decision = resolve_open_application(
            first
        )


        if first_decision:

            tasks.append(
                first_decision
            )


        second_decision = resolve_open_application(
            second
        )


        if second_decision:

            tasks.append(
                second_decision
            )


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

        "launch notepad",

    ]


    if any(
        phrase in value
        for phrase in notepad_patterns
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

        "launch calculator",

    ]


    if any(
        phrase in value
        for phrase in calculator_patterns
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

    ]


    if any(
        phrase in value
        for phrase in close_notepad_patterns
    ):

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
    # NO DETERMINISTIC MATCH
    # ========================================================

    return None


# ============================================================
# RESOLVE OPEN APPLICATION
# ============================================================

def resolve_open_application(name):

    value = normalize(
        name
    )


    value = re.sub(
        r"\s+(for me|please)$",
        "",
        value,
    ).strip()


    # ========================================================
    # NOTEPAD
    # ========================================================

    if value in {
        "notepad",
        "notebook",
    }:

        return make_tool(
            "open_notepad"
        )


    # ========================================================
    # CALCULATOR
    # ========================================================

    if value in {
        "calculator",
        "calc",
    }:

        return make_tool(
            "open_calculator"
        )


    # ========================================================
    # TRY DIRECT ROUTING
    # ========================================================

    decision = deterministic_route(
        f"open {value}"
    )


    if (
        decision
        and
        decision.get(
            "action"
        ) == "tool"
    ):

        return decision


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


    return "\n".join(
        lines
    )


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

1. answer normally with chat
2. select one tool
3. select multiple tools

AVAILABLE TOOLS:

{tool_description}


IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Never return markdown.
3. Never explain the JSON.
4. Never invent tool names.
5. For normal conversation use "chat".
6. For one tool use "tool".
7. For multiple independent tools use "tasks".
8. Every tool call must contain an "arguments" object.
9. Use EXACTLY the tool names listed above.
10. NEVER invent arguments.
11. Only use arguments required by the tool.
12. If a tool requires an application name, provide it.
13. Do not use Windows application UI parameters unless they are explicitly listed in AVAILABLE TOOLS.
14. For "close both" prefer:
    - close_application application=notepad
    - close_application application=calculator
15. If the user asks what you can do, use "chat".
16. Do not interpret normal conversational phrases as application shutdown.
17. Only return "exit" when the user clearly asks JARVIS to shut down.


SINGLE TOOL FORMAT:

{{
  "action": "tool",
  "tool": "tool_name",
  "arguments": {{}}
}}


MULTIPLE TOOL FORMAT:

{{
  "action": "tasks",
  "tasks": [
    {{
      "action": "tool",
      "tool": "tool_name",
      "arguments": {{}}
    }},
    {{
      "action": "tool",
      "tool": "tool_name",
      "arguments": {{}}
    }}
  ]
}}


CHAT FORMAT:

{{
  "action": "chat",
  "response": "your answer here"
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
# JSON EXTRACTION
# ============================================================

def extract_json(raw):

    if not raw:

        return None


    raw = str(
        raw
    ).strip()


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
    )


    # --------------------------------------------------------
    # Entire response
    # --------------------------------------------------------

    try:

        return json.loads(
            raw
        )

    except Exception:

        pass


    # --------------------------------------------------------
    # Find JSON object
    # --------------------------------------------------------

    start = raw.find(
        "{"
    )


    end = raw.rfind(
        "}"
    )


    if (
        start != -1
        and
        end != -1
        and
        end > start
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
# CLEAN AI ARGUMENTS
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

    removed = []


    for key, value in arguments.items():

        if key in accepted:

            cleaned[key] = value

        else:

            removed.append(
                key
            )


    if removed:

        print(
            f"\nJARVIS AI DEBUG > "
            f"Ignoring unsupported argument(s) "
            f"for {tool_name}: {removed}"
        )


    return cleaned


# ============================================================
# REPAIR AI TOOL CALL
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


    # --------------------------------------------------------
    # CLOSE APPLICATION
    # --------------------------------------------------------

    if tool_name == "close_application":

        if not arguments.get(
            "application"
        ):

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


    repaired = repair_tool_call(
        tool_name,
        arguments,
    )


    if repaired is None:

        return None


    return {
        "action": "tool",
        "tool": tool_name,
        "arguments": repaired,
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


        return normalize_tool_decision(
            tool_name,
            arguments,
        )


    # ========================================================
    # MULTIPLE TASKS
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


            # ------------------------------------------------
            # Direct tool action
            # ------------------------------------------------

            if task_action in tools:

                tool_name = task_action


                arguments = task.get(
                    "arguments",
                    {},
                )


                normalized = (
                    normalize_tool_decision(
                        tool_name,
                        arguments,
                    )
                )


                if normalized:

                    tasks.append(
                        normalized
                    )


                continue


            # ------------------------------------------------
            # Normal tool action
            # ------------------------------------------------

            if task_action != "tool":

                continue


            tool_name = task.get(
                "tool"
            )


            if tool_name not in tools:

                continue


            arguments = task.get(
                "arguments",
                {},
            )


            normalized = (
                normalize_tool_decision(
                    tool_name,
                    arguments,
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

        response = data.get(
            "response",
            "",
        )


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

def execute_memory(
    decision
):

    operation = decision.get(
        "operation"
    )


    # ========================================================
    # REMEMBER
    # ========================================================

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


    # ========================================================
    # RECALL
    # ========================================================

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


    # ========================================================
    # SHOW MEMORY
    # ========================================================

    if operation == "show_memory":

        result = show_memory()


        return result.get(
            "message",
            str(result),
        )


    # ========================================================
    # FORGET
    # ========================================================

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


    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    if show_header:

        print(
            f"\nJARVIS > "
            f"Tool: {tool_name}"
        )


    # --------------------------------------------------------
    # Get tool
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
    # Validation
    # --------------------------------------------------------

    validation = validate_tool_call(
        tool_name,
        arguments,
    )


    if not validation.get(
        "valid",
        False,
    ):

        message = (
            "Tool call rejected: "
            + validation.get(
                "message",
                "Validation failed.",
            )
        )


        print(
            f"JARVIS DEBUG > "
            f"{message}"
        )


        return message


    # --------------------------------------------------------
    # Tool information
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
    # Execute
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
            f"Tool execution "
            f"failed: {e}"
        )


# ============================================================
# MULTI-TASK EXECUTION
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
            "message": None,
        }


    # ========================================================
    # GLOBAL EXIT
    # ========================================================

    if is_exit_command(
        text
    ):

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
    # ROUTING FAILURE
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
            "I couldn't understand "
            "that request.",
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
        # Empty input
        # ----------------------------------------------------

        if not text:

            continue


        # ----------------------------------------------------
        # Exit text mode
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
            "Voice system is unavailable."
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

    print(
        "Natural phrases such as "
        "'nothing just exit the voice mode' "
        "are supported."
    )

    print()


    # ========================================================
    # VOICE LOOP
    # ========================================================

    while True:

        # ----------------------------------------------------
        # LISTEN
        # ----------------------------------------------------

        try:

            text = listen()

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > {e}"
            )

            continue


        # ----------------------------------------------------
        # NOTHING HEARD
        # ----------------------------------------------------

        if not text:

            print(
                "JARVIS > "
                "I didn't hear anything."
            )

            continue


        # ----------------------------------------------------
        # CLEAN
        # ----------------------------------------------------

        text = str(
            text
        ).strip()


        if not text:

            continue


        # ----------------------------------------------------
        # DISPLAY USER SPEECH
        # ----------------------------------------------------

        print(
            f"\nYOU 🎤 > {text}"
        )


        # ====================================================
        # VOICE MODE CONTROL
        #
        # VERY IMPORTANT:
        #
        # This happens BEFORE process_command().
        #
        # Therefore:
        #
        # "nothing just exit the voice mode"
        #
        # will return to the main menu instead of allowing
        # the AI router to shut down the application.
        # ====================================================

        normalized = normalize(
            text
        )


        # ----------------------------------------------------
        # Exact voice-mode commands
        # ----------------------------------------------------

        voice_exit_commands = {

            "exit",
            "quit",
            "stop",
            "shutdown",
            "bye",

            "go to main menu",
            "return to main menu",
            "back to main menu",

            "exit voice mode",
            "leave voice mode",
            "stop voice mode",

            "exit the voice mode",
            "leave the voice mode",
            "stop the voice mode",

            "go back",

        }


        if normalized in voice_exit_commands:

            message = (
                "Returning to the main menu."
            )


            print(
                f"\nJARVIS > {message}"
            )


            if speak:

                try:

                    speak(
                        message
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > {e}"
                    )


            return "menu"


        # ----------------------------------------------------
        # Natural exit phrases
        # ----------------------------------------------------

        natural_exit_phrases = [

            "exit voice mode",

            "leave voice mode",

            "stop voice mode",

            "shutdown voice mode",

            "exit the voice mode",

            "leave the voice mode",

            "stop the voice mode",

            "shutdown the voice mode",

            "exit this voice mode",

            "leave this voice mode",

            "stop this voice mode",

            "go to main menu",

            "return to main menu",

            "back to main menu",

            "go back to main menu",

        ]


        should_return_to_menu = False


        for phrase in natural_exit_phrases:

            if phrase in normalized:

                should_return_to_menu = True

                break


        if should_return_to_menu:

            message = (
                "Returning to the main menu."
            )


            print(
                f"\nJARVIS > {message}"
            )


            if speak:

                try:

                    speak(
                        message
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > {e}"
                    )


            return "menu"


        # ----------------------------------------------------
        # Short natural exit commands
        #
        # Examples:
        #
        # "please exit"
        # "ok exit"
        # "jarvis exit"
        # "please stop"
        # ----------------------------------------------------

        exit_words = {

            "exit",
            "quit",
            "stop",
            "shutdown",

        }


        words = normalized.split()


        short_exit = False


        if len(words) <= 5:

            for word in words:

                if word in exit_words:

                    short_exit = True

                    break


        if short_exit:

            message = (
                "Returning to the main menu."
            )


            print(
                f"\nJARVIS > {message}"
            )


            if speak:

                try:

                    speak(
                        message
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > {e}"
                    )


            return "menu"


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
                f"\nJARVIS > {message}"
            )


            if speak:

                try:

                    speak(
                        message
                    )

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > {e}"
                    )


        # ====================================================
        # APPLICATION SHUTDOWN
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

        if mode in EXIT_COMMANDS:

            return "shutdown"


        # ====================================================
        # TEXT MODE
        # ====================================================

        if mode == "t":

            result = text_mode()


            if result == "shutdown":

                return "shutdown"


            continue


        # ====================================================
        # VOICE MODE
        # ====================================================

        if mode == "v":

            result = voice_mode()


            if result == "shutdown":

                return "shutdown"


            # -----------------------------------------------
            # "menu" simply returns here and asks T/V again
            # -----------------------------------------------

            if result == "menu":

                continue


            continue


        # ====================================================
        # INVALID MODE
        # ====================================================

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


    print()


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