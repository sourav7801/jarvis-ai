# ============================================================
# JARVIS TOOL SCHEMAS
# ============================================================

TOOL_SCHEMAS = {

    "open_notepad": {
        "required": [],
        "optional": [],
    },

    "open_calculator": {
        "required": [],
        "optional": [],
    },

    "system_info": {
        "required": [],
        "optional": [],
    },

    "current_time": {
        "required": [],
        "optional": [],
    },

    "show_memory": {
        "required": [],
        "optional": [],
    },

    "open_application": {
        "required": ["application"],
        "optional": [],
    },

    "open_website": {
        "required": ["url"],
        "optional": [],
    },

    "open_folder": {
        "required": ["path"],
        "optional": [],
    },

    "list_files": {
        "required": ["path"],
        "optional": [],
    },

    "close_application": {
        "required": ["application"],
        "optional": [],
    },

    "open_file": {
        "required": ["path"],
        "optional": [],
    },

    "search_files": {
        "required": ["path", "pattern"],
        "optional": [],
    },

    "remember": {
        "required": ["key", "value"],
        "optional": [],
    },

    "recall": {
        "required": ["key"],
        "optional": [],
    },

    "forget": {
        "required": ["key"],
        "optional": [],
    },
}


# ============================================================
# VALIDATE TOOL CALL
# ============================================================

def validate_tool_call(tool_name, arguments):

    if tool_name not in TOOL_SCHEMAS:

        return {
            "valid": False,
            "message": (
                f"Unknown tool: {tool_name}"
            )
        }

    if not isinstance(arguments, dict):

        return {
            "valid": False,
            "message": "Tool arguments must be an object."
        }

    schema = TOOL_SCHEMAS[tool_name]

    required = schema["required"]

    # --------------------------------------------------------
    # REQUIRED ARGUMENTS
    # --------------------------------------------------------

    for argument in required:

        if argument not in arguments:

            return {
                "valid": False,
                "message": (
                    f"Missing required argument "
                    f"'{argument}' for {tool_name}."
                )
            }

        value = arguments[argument]

        if value is None:

            return {
                "valid": False,
                "message": (
                    f"Argument '{argument}' "
                    f"cannot be null."
                )
            }

        if isinstance(value, str) and not value.strip():

            return {
                "valid": False,
                "message": (
                    f"Argument '{argument}' "
                    f"cannot be empty."
                )
            }

    # --------------------------------------------------------
    # UNEXPECTED ARGUMENTS
    # --------------------------------------------------------

    allowed = set(
        schema["required"]
        + schema["optional"]
    )

    unexpected = set(
        arguments.keys()
    ) - allowed

    if unexpected:

        return {
            "valid": False,
            "message": (
                f"Unexpected argument(s): "
                f"{', '.join(unexpected)}"
            )
        }

    # --------------------------------------------------------
    # VALID
    # --------------------------------------------------------

    return {
        "valid": True,
        "message": "Tool call is valid."
    }