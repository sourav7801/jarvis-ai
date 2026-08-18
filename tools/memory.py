import json
from datetime import datetime

from config import MEMORY_FILE


def load_memory():

    if not MEMORY_FILE.exists():
        return {}

    try:

        with MEMORY_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:
        return {}


def save_memory(memory):

    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with MEMORY_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            memory,
            f,
            indent=2,
            ensure_ascii=False
        )


def remember(key, value):

    memory = load_memory()

    memory[key] = {
        "value": value,
        "updated": datetime.now().isoformat()
    }

    save_memory(memory)

    return {
        "success": True,
        "tool": "remember",
        "message": (
            f"I'll remember that "
            f"{key} = {value}"
        )
    }


def recall(key):

    memory = load_memory()

    item = memory.get(key)

    if not item:

        return {
            "success": True,
            "tool": "recall",
            "message": (
                f"I don't have anything "
                f"remembered for '{key}'."
            )
        }

    return {
        "success": True,
        "tool": "recall",
        "message": (
            f"{key} = {item['value']}"
        )
    }


def show_memory():

    memory = load_memory()

    if not memory:

        return {
            "success": True,
            "tool": "show_memory",
            "message": "My memory is currently empty."
        }

    lines = []

    for key, item in memory.items():

        lines.append(
            f"{key}: {item['value']}"
        )

    return {
        "success": True,
        "tool": "show_memory",
        "message": (
            "Stored memories:\n"
            + "\n".join(lines)
        )
    }


def forget(key):

    memory = load_memory()

    if key not in memory:

        return {
            "success": True,
            "tool": "forget",
            "message": (
                f"I don't have a memory "
                f"called '{key}'."
            )
        }

    del memory[key]

    save_memory(memory)

    return {
        "success": True,
        "tool": "forget",
        "message": (
            f"I forgot '{key}'."
        )
    }
