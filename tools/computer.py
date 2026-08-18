import subprocess
import time
import platform
import os
import webbrowser
from datetime import datetime


# ============================================================
# OPEN NOTEPAD
# ============================================================

def open_notepad():
    try:
        subprocess.Popen(["notepad.exe"])
        time.sleep(1)

        return {
            "success": True,
            "tool": "open_notepad",
            "message": "Notepad was opened."
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "open_notepad",
            "message": f"Could not open Notepad: {e}"
        }


# ============================================================
# OPEN CALCULATOR
# ============================================================

def open_calculator():
    try:
        subprocess.Popen(["calc.exe"])
        time.sleep(1)

        return {
            "success": True,
            "tool": "open_calculator",
            "message": "Calculator was opened."
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "open_calculator",
            "message": f"Could not open Calculator: {e}"
        }


# ============================================================
# SYSTEM INFORMATION
# ============================================================

def system_info():
    return {
        "success": True,
        "tool": "system_info",
        "message": (
            f"Operating System: {platform.system()} "
            f"{platform.release()}\n"
            f"Machine: {platform.machine()}\n"
            f"Processor: {platform.processor()}"
        )
    }


# ============================================================
# OPEN APPLICATION
# ============================================================

def open_application(application):

    allowed_apps = {
        "notepad": ["notepad.exe"],
        "calculator": ["calc.exe"],
        "paint": ["mspaint.exe"],
        "explorer": ["explorer.exe"],
    }

    application = application.lower().strip()

    if application not in allowed_apps:
        return {
            "success": False,
            "tool": "open_application",
            "message": (
                f"Application '{application}' is not allowed."
            )
        }

    try:
        subprocess.Popen(
            allowed_apps[application]
        )

        time.sleep(1)

        return {
            "success": True,
            "tool": "open_application",
            "message": f"{application} was opened."
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "open_application",
            "message": (
                f"Could not open {application}: {e}"
            )
        }


# ============================================================
# OPEN WEBSITE
# ============================================================

def open_website(url):

    url = url.strip()

    if not url.startswith(
        ("http://", "https://")
    ):
        url = "https://" + url

    try:
        webbrowser.open(url)

        return {
            "success": True,
            "tool": "open_website",
            "message": f"Opened {url}"
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "open_website",
            "message": (
                f"Could not open website: {e}"
            )
        }


# ============================================================
# OPEN FOLDER
# ============================================================

def open_folder(path):

    path = os.path.expandvars(
        os.path.expanduser(path)
    )

    if not os.path.exists(path):
        return {
            "success": False,
            "tool": "open_folder",
            "message": (
                f"Folder does not exist: {path}"
            )
        }

    if not os.path.isdir(path):
        return {
            "success": False,
            "tool": "open_folder",
            "message": (
                f"Not a folder: {path}"
            )
        }

    try:
        os.startfile(path)

        return {
            "success": True,
            "tool": "open_folder",
            "message": (
                f"Opened folder: {path}"
            )
        }

    except Exception as e:
        return {
            "success": False,
            "tool": "open_folder",
            "message": (
                f"Could not open folder: {e}"
            )
        }


# ============================================================
# CURRENT TIME
# ============================================================

def current_time():

    now = datetime.now()

    return {
        "success": True,
        "tool": "current_time",
        "message": now.strftime(
            "Current date and time: "
            "%A, %d %B %Y, %I:%M:%S %p"
        )
    }


# ============================================================
# LIST FILES
# ============================================================

def list_files(path):

    path = os.path.expandvars(
        os.path.expanduser(path)
    )

    if not os.path.exists(path):
        return {
            "success": False,
            "tool": "list_files",
            "message": (
                f"Path does not exist: {path}"
            )
        }

    if not os.path.isdir(path):
        return {
            "success": False,
            "tool": "list_files",
            "message": (
                f"Not a directory: {path}"
            )
        }

    try:

        items = os.listdir(path)

        if not items:

            message = (
                f"{path} is empty."
            )

        else:

            message = (
                f"Contents of {path}:\n"
                + "\n".join(items[:100])
            )

            if len(items) > 100:

                message += (
                    f"\n...and "
                    f"{len(items) - 100} more items."
                )

        return {
            "success": True,
            "tool": "list_files",
            "message": message
        }

    except Exception as e:

        return {
            "success": False,
            "tool": "list_files",
            "message": (
                f"Could not list files: {e}"
            )
        }


# ============================================================
# CLOSE APPLICATION
# ============================================================

def close_application(application):

    application = application.lower().strip()

    allowed_processes = {
        "notepad": "notepad.exe",
        "calculator": "CalculatorApp.exe",
        "paint": "mspaint.exe",
    }

    if application not in allowed_processes:

        return {
            "success": False,
            "tool": "close_application",
            "message": (
                f"Application '{application}' "
                "cannot be closed by this tool."
            )
        }

    process_name = allowed_processes[
        application
    ]

    try:

        result = subprocess.run(
            [
                "taskkill",
                "/IM",
                process_name,
                "/T",
                "/F"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:

            return {
                "success": True,
                "tool": "close_application",
                "message": (
                    f"{application} was closed."
                )
            }

        return {
            "success": False,
            "tool": "close_application",
            "message": (
                f"{application} was not running."
            )
        }

    except Exception as e:

        return {
            "success": False,
            "tool": "close_application",
            "message": (
                f"Could not close "
                f"{application}: {e}"
            )
        }


# ============================================================
# OPEN FILE
# ============================================================

def open_file(path):

    path = os.path.expandvars(
        os.path.expanduser(path)
    )

    if not os.path.exists(path):

        return {
            "success": False,
            "tool": "open_file",
            "message": (
                f"File does not exist: {path}"
            )
        }

    if not os.path.isfile(path):

        return {
            "success": False,
            "tool": "open_file",
            "message": (
                f"Not a file: {path}"
            )
        }

    try:

        os.startfile(path)

        return {
            "success": True,
            "tool": "open_file",
            "message": (
                f"Opened file: {path}"
            )
        }

    except Exception as e:

        return {
            "success": False,
            "tool": "open_file",
            "message": (
                f"Could not open file: {e}"
            )
        }


# ============================================================
# SEARCH FILES
# ============================================================

def search_files(path, pattern):

    path = os.path.expandvars(
        os.path.expanduser(path)
    )

    pattern = pattern.strip()

    if not os.path.exists(path):

        return {
            "success": False,
            "tool": "search_files",
            "message": (
                f"Path does not exist: {path}"
            )
        }

    if not os.path.isdir(path):

        return {
            "success": False,
            "tool": "search_files",
            "message": (
                f"Not a directory: {path}"
            )
        }

    if not pattern:

        return {
            "success": False,
            "tool": "search_files",
            "message": (
                "Search pattern cannot be empty."
            )
        }

    matches = []

    try:

        for root, dirs, files in os.walk(path):

            for filename in files:

                if pattern.lower() in filename.lower():

                    full_path = os.path.join(
                        root,
                        filename
                    )

                    matches.append(
                        full_path
                    )

                    if len(matches) >= 100:

                        break

            if len(matches) >= 100:

                break

        if not matches:

            return {
                "success": True,
                "tool": "search_files",
                "message": (
                    f"No files matching "
                    f"'{pattern}' were found "
                    f"in {path}."
                )
            }

        message = (
            f"Files matching '{pattern}':\n"
            + "\n".join(matches)
        )

        return {
            "success": True,
            "tool": "search_files",
            "message": message
        }

    except Exception as e:

        return {
            "success": False,
            "tool": "search_files",
            "message": (
                f"Could not search files: {e}"
            )
        }