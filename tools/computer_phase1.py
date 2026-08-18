from __future__ import annotations

from datetime import datetime
import os
import platform
import subprocess
import webbrowser

from tools.registry import tool


@tool(description="Get the current local date and time from the computer.", risk="read_only")
def current_time():
    now = datetime.now().astimezone()
    return {
        "success": True,
        "tool": "current_time",
        "data": {
            "iso": now.isoformat(),
            "timezone": str(now.tzinfo),
        },
        "message": now.strftime("Current date and time: %A, %d %B %Y, %I:%M:%S %p"),
    }


@tool(description="Return basic operating-system and machine information.", risk="read_only")
def system_info():
    data = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    return {
        "success": True,
        "tool": "system_info",
        "data": data,
        "message": f"{data['system']} {data['release']} ({data['machine']})",
    }


@tool(description="List files and folders inside a directory.", risk="read_only")
def list_files(path: str):
    expanded = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    if not os.path.isdir(expanded):
        return {
            "success": False,
            "tool": "list_files",
            "message": f"Directory not found: {expanded}",
            "error": "directory_not_found",
        }

    items = sorted(os.listdir(expanded))
    return {
        "success": True,
        "tool": "list_files",
        "data": {"path": expanded, "items": items},
        "message": f"Found {len(items)} items in {expanded}.",
    }


@tool(description="Open a website in the default browser.", risk="low")
def open_website(url: str):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    opened = webbrowser.open(url)
    return {
        "success": bool(opened),
        "tool": "open_website",
        "data": {"url": url},
        "message": f"Opened {url}" if opened else f"Could not open {url}",
    }


@tool(description="Open Windows Notepad.", risk="low")
def open_notepad():
    subprocess.Popen(["notepad.exe"])
    return {
        "success": True,
        "tool": "open_notepad",
        "message": "Notepad opened.",
    }


@tool(description="Open Windows Calculator.", risk="low")
def open_calculator():
    subprocess.Popen(["calc.exe"])
    return {
        "success": True,
        "tool": "open_calculator",
        "message": "Calculator opened.",
    }
