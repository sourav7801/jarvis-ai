"""Explicit capability manifest for the canonical tool registry."""

from __future__ import annotations


TOOL_CAPABILITIES = {
    "open_notepad": frozenset({"process.launch"}),
    "open_calculator": frozenset({"process.launch"}),
    "system_info": frozenset({"system.read"}),
    "open_application": frozenset({"process.launch"}),
    "open_website": frozenset({"browser.launch", "network.navigate"}),
    "open_folder": frozenset({"filesystem.read", "process.launch"}),
    "current_time": frozenset({"system.read"}),
    "list_files": frozenset({"filesystem.read"}),
    "close_application": frozenset({"process.terminate"}),
    "open_file": frozenset({"filesystem.read", "process.launch"}),
    "search_files": frozenset({"filesystem.read"}),
    "remember": frozenset({"memory.write"}),
    "recall": frozenset({"memory.read"}),
    "show_memory": frozenset({"memory.read"}),
    "forget": frozenset({"memory.delete"}),
}


def capabilities_for(tool_name: str) -> frozenset[str]:
    return TOOL_CAPABILITIES.get(tool_name, frozenset())


def validate_capability_manifest(tool_names) -> list[str]:
    registered = set(tool_names)
    declared = set(TOOL_CAPABILITIES)
    errors = []
    for name in sorted(registered - declared):
        errors.append(f"Registered tool '{name}' has no capability declaration.")
    for name in sorted(declared - registered):
        errors.append(f"Capability manifest references unknown tool '{name}'.")
    for name, capabilities in TOOL_CAPABILITIES.items():
        if not capabilities:
            errors.append(f"Tool '{name}' has an empty capability declaration.")
    return errors

