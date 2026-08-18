import tkinter as tk
from tkinter import ttk
import threading
import queue
import time
import math
import platform
import subprocess
import re
import os
import sys

# ============================================================
# JARVIS COMMAND CENTER
# ============================================================
#
# Features:
#   - Natural 3D dashboard
#   - Large COMMAND JARVIS button
#   - Continuous voice mode
#   - START VOICE / STOP VOICE
#   - Voice stop commands
#   - CPU / RAM / GPU monitoring
#   - Windows volume control
#   - Direct system-information answers
#   - Existing main.py backend
#   - Existing voice.py backend
#
# ============================================================


APP_TITLE = "JARVIS COMMAND CENTER"


# ============================================================
# BACKEND
# ============================================================

try:
    import main as jarvis_main
except Exception as e:
    jarvis_main = None
    print("Backend import error:", e)


try:
    from voice import listen, speak
    VOICE_AVAILABLE = True
except Exception as e:
    listen = None
    speak = None
    VOICE_AVAILABLE = False
    print("Voice import error:", e)


# ============================================================
# SYSTEM MONITOR
# ============================================================

try:
    import psutil
except Exception:
    psutil = None


# ============================================================
# VOLUME CONTROL
# ============================================================

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL

    VOLUME_AVAILABLE = True

except Exception as e:
    VOLUME_AVAILABLE = False
    print("Volume control unavailable:", e)


# ============================================================
# COLORS
# ============================================================

BG = "#07121F"
BG_TOP = "#091827"

PANEL = "#102238"
PANEL_LIGHT = "#142B43"
PANEL_SOFT = "#162F49"

WHITE = "#F5F8FC"
TEXT = "#DCE8F3"
MUTED = "#8FA7BA"

CYAN = "#56D9FF"
CYAN_DARK = "#249DCB"

BLUE = "#4C83FF"

GOLD = "#E9BB70"

GREEN = "#5CE2A0"
RED = "#FF6675"

LINE = "#203B55"

BLACK = "#040A11"


# ============================================================
# FONTS
# ============================================================

FONT = "Segoe UI"
FONT_LIGHT = "Segoe UI Light"

WINDOW_W = 1500
WINDOW_H = 930


# ============================================================
# EVENT QUEUE
# ============================================================

events = queue.Queue()


def post_event(kind, data=None):
    events.put((kind, data))


# ============================================================
# SAFE BACKEND
# ============================================================

def backend_command(text):

    if jarvis_main is None:
        return {
            "exit": False,
            "message": "JARVIS backend is unavailable."
        }

    try:

        return jarvis_main.process_command(text)

    except Exception as e:

        return {
            "exit": False,
            "message": f"Backend error: {e}"
        }


def backend_tools_count():

    try:

        if jarvis_main is not None:
            return len(jarvis_main.list_tools())

    except Exception:
        pass

    return 0


# ============================================================
# GPU INFORMATION
# ============================================================

def get_gpu_info():

    """
    Gets GPU information from Windows.

    Uses PowerShell/WMI so an additional GPU package
    is not required.
    """

    try:

        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            """
            Get-CimInstance Win32_VideoController |
            Select-Object Name, AdapterRAM |
            ConvertTo-Json -Compress
            """
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=4
        )

        output = result.stdout.strip()

        if not output:
            return {
                "name": "GPU",
                "memory": "N/A"
            }

        import json

        data = json.loads(output)

        if isinstance(data, dict):
            data = [data]

        # Ignore Microsoft Basic Display Adapter
        valid = []

        for gpu in data:

            name = str(
                gpu.get(
                    "Name",
                    "GPU"
                )
            )

            if "Microsoft Basic" not in name:
                valid.append(gpu)

        if not valid:
            valid = data

        gpu = valid[0]

        name = str(
            gpu.get(
                "Name",
                "GPU"
            )
        )

        memory_bytes = gpu.get(
            "AdapterRAM"
        )

        if memory_bytes:

            try:

                gb = (
                    float(memory_bytes)
                    / 1024
                    / 1024
                    / 1024
                )

                memory = f"{gb:.1f} GB"

            except Exception:

                memory = "N/A"

        else:

            memory = "N/A"

        return {
            "name": name,
            "memory": memory
        }

    except Exception as e:

        return {
            "name": "GPU unavailable",
            "memory": "N/A"
        }


# ============================================================
# VOLUME FUNCTIONS
# ============================================================

def get_volume_interface():

    if not VOLUME_AVAILABLE:
        return None

    try:

        devices = AudioUtilities.GetSpeakers()

        interface = devices.Activate(
            IAudioEndpointVolume._iid_,
            CLSCTX_ALL,
            None
        )

        return interface.QueryInterface(
            IAudioEndpointVolume
        )

    except Exception:

        return None


def get_volume():

    try:

        volume = get_volume_interface()

        if volume is None:
            return None

        level = volume.GetMasterVolumeLevelScalar()

        return int(
            max(
                0,
                min(
                    100,
                    level * 100
                )
            )
        )

    except Exception:

        return None


def set_volume(value):

    try:

        volume = get_volume_interface()

        if volume is None:
            return False

        value = max(
            0,
            min(
                100,
                int(value)
            )
        )

        volume.SetMasterVolumeLevelScalar(
            value / 100.0,
            None
        )

        return True

    except Exception:

        return False


def change_volume(delta):

    current = get_volume()

    if current is None:
        return None

    new_value = max(
        0,
        min(
            100,
            current + delta
        )
    )

    if set_volume(new_value):
        return new_value

    return None


def mute_volume():

    try:

        volume = get_volume_interface()

        if volume is None:
            return False

        volume.SetMute(
            1,
            None
        )

        return True

    except Exception:

        return False


def unmute_volume():

    try:

        volume = get_volume_interface()

        if volume is None:
            return False

        volume.SetMute(
            0,
            None
        )

        return True

    except Exception:

        return False


# ============================================================
# SYSTEM INFORMATION
# ============================================================

def get_system_information():

    cpu = 0
    ram_percent = 0
    ram_used = 0
    ram_total = 0

    if psutil:

        try:

            cpu = psutil.cpu_percent(
                interval=None
            )

            ram = psutil.virtual_memory()

            ram_percent = ram.percent

            ram_used = ram.used / (
                1024 ** 3
            )

            ram_total = ram.total / (
                1024 ** 3
            )

        except Exception:
            pass

    gpu = get_gpu_info()

    return {
        "os": platform.system(),
        "os_version": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu": cpu,
        "ram_percent": ram_percent,
        "ram_used": ram_used,
        "ram_total": ram_total,
        "gpu_name": gpu["name"],
        "gpu_memory": gpu["memory"]
    }


# ============================================================
# COMMAND CLASSIFICATION
# ============================================================

def is_voice_stop_command(text):

    value = text.lower().strip()

    stop_phrases = [

        "stop voice",
        "stop voice command",
        "stop listening",
        "voice stop",
        "stop listening jarvis",
        "jarvis stop listening",
        "stop microphone",
        "turn off voice",
        "disable voice"

    ]

    return any(
        phrase in value
        for phrase in stop_phrases
    )


def handle_volume_command(text):

    value = text.lower().strip()

    # --------------------------------------------------------
    # MUTE
    # --------------------------------------------------------

    if (
        "mute" in value
        and "unmute" not in value
    ):

        if mute_volume():

            return "Volume muted."

        return "I couldn't control the system volume."


    # --------------------------------------------------------
    # UNMUTE
    # --------------------------------------------------------

    if "unmute" in value:

        if unmute_volume():

            current = get_volume()

            if current is not None:
                return f"Volume unmuted. Current volume is {current}%."

            return "Volume unmuted."

        return "I couldn't control the system volume."


    # --------------------------------------------------------
    # SET VOLUME
    # --------------------------------------------------------

    match = re.search(
        r"(?:set|change)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})",
        value
    )

    if match:

        amount = int(
            match.group(1)
        )

        amount = max(
            0,
            min(
                100,
                amount
            )
        )

        if set_volume(amount):

            return f"System volume set to {amount}%."

        return "I couldn't change the system volume."


    # --------------------------------------------------------
    # LOWER VOLUME
    # --------------------------------------------------------

    lower_words = [
        "lower volume",
        "decrease volume",
        "reduce volume",
        "turn down volume",
        "volume down",
        "make volume lower",
        "make it quieter"
    ]

    if any(
        phrase in value
        for phrase in lower_words
    ):

        amount = change_volume(
            -10
        )

        if amount is not None:

            return (
                f"Volume lowered to "
                f"{amount}%."
            )

        return "I couldn't change the system volume."


    # --------------------------------------------------------
    # INCREASE VOLUME
    # --------------------------------------------------------

    louder_words = [
        "increase volume",
        "raise volume",
        "turn up volume",
        "volume up",
        "make volume louder",
        "make it louder"
    ]

    if any(
        phrase in value
        for phrase in louder_words
    ):

        amount = change_volume(
            10
        )

        if amount is not None:

            return (
                f"Volume increased to "
                f"{amount}%."
            )

        return "I couldn't change the system volume."


    # --------------------------------------------------------
    # CURRENT VOLUME
    # --------------------------------------------------------

    if (
        "current volume" in value
        or "volume level" in value
        or "what is the volume" in value
    ):

        amount = get_volume()

        if amount is not None:

            return (
                f"The current system "
                f"volume is {amount}%."
            )

    return None


def is_system_info_command(text):

    value = text.lower()

    keywords = [

        "cpu",
        "gpu",
        "graphics card",
        "ram",
        "memory reading",
        "memory usage",
        "system information",
        "system info",
        "pc information",
        "pc info",
        "computer information",
        "computer specs",
        "computer specification",
        "hardware information",
        "hardware specs"

    ]

    return any(
        keyword in value
        for keyword in keywords
    )


def format_system_information():

    info = get_system_information()

    return (
        f"CPU usage is {info['cpu']:.0f}%. "
        f"Memory usage is {info['ram_percent']:.0f}%, "
        f"using {info['ram_used']:.1f} GB "
        f"of {info['ram_total']:.1f} GB. "
        f"GPU: {info['gpu_name']}, "
        f"with approximately {info['gpu_memory']} "
        f"dedicated memory."
    )


def local_special_command(text):

    volume_result = handle_volume_command(
        text
    )

    if volume_result is not None:
        return volume_result

    if is_system_info_command(text):

        return format_system_information()

    return None


# ============================================================
# MAIN APPLICATION
# ============================================================

class JarvisDashboard:

    def __init__(self, root):

        self.root = root

        self.root.title(
            APP_TITLE
        )

        self.root.geometry(
            f"{WINDOW_W}x{WINDOW_H}"
        )

        self.root.minsize(
            1150,
            760
        )

        self.root.configure(
            bg=BG
        )

        self.running = True

        self.voice_enabled = (
            VOICE_AVAILABLE
        )

        # Continuous voice mode
        self.voice_mode = False

        # One current listen operation
        self.listening = False

        self.thinking = False
        self.speaking = False

        self.animation_phase = 0
        self.command_hover = False

        self.last_gpu = {
            "name": "Detecting...",
            "memory": "..."
        }

        self.setup_styles()

        self.build_ui()

        # ----------------------------------------------------
        # Startup log
        # ----------------------------------------------------

        self.write_log(
            "JARVIS COMMAND CENTER ONLINE",
            "system"
        )

        self.write_log(
            "Local AI backend connected."
            if jarvis_main
            else "Local AI backend unavailable.",
            "system"
        )

        self.write_log(
            f"Tools detected: {backend_tools_count()}",
            "system"
        )

        if self.voice_enabled:

            self.write_log(
                "Voice interface ready.",
                "system"
            )

        else:

            self.write_log(
                "Voice interface unavailable.",
                "warning"
            )

        if VOLUME_AVAILABLE:

            self.write_log(
                "System volume control ready.",
                "system"
            )

        else:

            self.write_log(
                "System volume control unavailable.",
                "warning"
            )

        self.write_log(
            "Ready // awaiting command",
            "system"
        )

        self.process_events()
        self.animate()
        self.update_system_stats()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )


    # ========================================================
    # STYLES
    # ========================================================

    def setup_styles(self):

        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )
        except Exception:
            pass

        style.configure(
            "TButton",
            font=(
                FONT,
                10
            ),
            padding=8
        )


    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        self.root.grid_rowconfigure(
            0,
            weight=0
        )

        self.root.grid_rowconfigure(
            1,
            weight=1
        )

        self.root.grid_rowconfigure(
            2,
            weight=0
        )

        self.root.grid_columnconfigure(
            0,
            weight=1
        )

        # Header
        self.header = tk.Frame(
            self.root,
            bg=BG_TOP,
            height=78
        )

        self.header.grid(
            row=0,
            column=0,
            sticky="ew"
        )

        self.header.grid_propagate(
            False
        )

        self.build_header()

        # Main
        self.main = tk.Frame(
            self.root,
            bg=BG
        )

        self.main.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=22,
            pady=(8, 15)
        )

        self.main.grid_columnconfigure(
            0,
            weight=3
        )

        self.main.grid_columnconfigure(
            1,
            weight=2
        )

        self.main.grid_rowconfigure(
            0,
            weight=1
        )

        self.build_left_area()

        self.build_right_area()

        self.build_command_bar()


    # ========================================================
    # HEADER
    # ========================================================

    def build_header(self):

        left = tk.Frame(
            self.header,
            bg=BG_TOP
        )

        left.pack(
            side="left",
            padx=28
        )

        tk.Label(
            left,
            text="JARVIS",
            bg=BG_TOP,
            fg=WHITE,
            font=(
                FONT_LIGHT,
                27
            )
        ).pack(
            side="left"
        )

        tk.Label(
            left,
            text="  COMMAND CENTER",
            bg=BG_TOP,
            fg=CYAN,
            font=(
                FONT,
                10,
                "bold"
            )
        ).pack(
            side="left",
            pady=(11, 0)
        )

        # Right
        right = tk.Frame(
            self.header,
            bg=BG_TOP
        )

        right.pack(
            side="right",
            padx=28
        )

        self.status_dot = tk.Canvas(
            right,
            width=14,
            height=14,
            bg=BG_TOP,
            highlightthickness=0
        )

        self.status_dot.pack(
            side="left",
            padx=(0, 8)
        )

        self.status_circle = (
            self.status_dot.create_oval(
                2,
                2,
                12,
                12,
                fill=GREEN,
                outline=""
            )
        )

        self.header_status = tk.Label(
            right,
            text="SYSTEM READY",
            bg=BG_TOP,
            fg=GREEN,
            font=(
                FONT,
                10,
                "bold"
            )
        )

        self.header_status.pack(
            side="left"
        )


    # ========================================================
    # LEFT AREA
    # ========================================================

    def build_left_area(self):

        self.left = tk.Frame(
            self.main,
            bg=BG
        )

        self.left.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 12)
        )

        self.left.grid_rowconfigure(
            0,
            weight=1
        )

        self.left.grid_rowconfigure(
            1,
            weight=0
        )

        self.left.grid_columnconfigure(
            0,
            weight=1
        )

        # Core card
        self.core_card = tk.Frame(
            self.left,
            bg=PANEL
        )

        self.core_card.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        self.core_canvas = tk.Canvas(
            self.core_card,
            bg=PANEL,
            highlightthickness=0
        )

        self.core_canvas.pack(
            fill="both",
            expand=True
        )

        self.core_canvas.bind(
            "<Configure>",
            lambda e: self.draw_core()
        )

        # Command area
        self.command_area = tk.Frame(
            self.left,
            bg=BG,
            height=155
        )

        self.command_area.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(14, 0)
        )

        self.command_area.grid_propagate(
            False
        )

        self.build_big_command_button()


    # ========================================================
    # CORE
    # ========================================================

    def draw_core(self):

        c = self.core_canvas

        c.delete("all")

        width = max(
            c.winfo_width(),
            500
        )

        height = max(
            c.winfo_height(),
            400
        )

        cx = width / 2
        cy = height / 2 - 20

        base = min(
            width,
            height
        )

        # Ambient circles
        for i in range(18, 0, -1):

            radius = base * (
                0.27 + i * 0.014
            )

            amount = (
                (18 - i)
                / 18
                * 0.18
            )

            color = self.mix_color(
                PANEL,
                CYAN,
                amount
            )

            c.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline=""
            )

        # Outer rings
        for offset in range(5):

            radius = base * (
                0.27
                + offset * 0.022
            )

            c.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=(
                    CYAN
                    if offset == 0
                    else "#24536D"
                ),
                width=(
                    2
                    if offset == 0
                    else 1
                )
            )

        # Orb
        radius = base * 0.215

        for i in range(35, 0, -1):

            r = radius * (
                i / 35
            )

            color = self.mix_color(
                "#061321",
                CYAN,
                1 - i / 35
            )

            c.create_oval(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                fill=color,
                outline=""
            )

        # Central energy
        core_r = radius * 0.34

        c.create_oval(
            cx - core_r,
            cy - core_r,
            cx + core_r,
            cy + core_r,
            fill="#E8FBFF",
            outline=""
        )

        c.create_oval(
            cx - core_r * .65,
            cy - core_r * .65,
            cx + core_r * .65,
            cy + core_r * .65,
            fill="#72E2FF",
            outline=""
        )

        # Orbiting particles
        for n in range(5):

            angle = (
                self.animation_phase
                + n * 1.256
            )

            orbit = radius * 1.38

            x = (
                cx
                + math.cos(angle)
                * orbit
            )

            y = (
                cy
                + math.sin(angle)
                * orbit
            )

            pulse = (
                math.sin(
                    self.animation_phase * 4
                    + n
                ) + 1
            )

            dot_r = 3 + pulse * 1.5

            c.create_oval(
                x - dot_r,
                y - dot_r,
                x + dot_r,
                y + dot_r,
                fill=CYAN,
                outline=""
            )

        # Status
        if self.listening:

            state = "LISTENING"
            color = CYAN

        elif self.thinking:

            state = "THINKING"
            color = GOLD

        elif self.speaking:

            state = "SPEAKING"
            color = GREEN

        elif self.voice_mode:

            state = "VOICE MODE"
            color = CYAN

        else:

            state = "READY"
            color = WHITE

        c.create_text(
            cx,
            cy + radius + 55,
            text=state,
            fill=color,
            font=(
                FONT,
                14,
                "bold"
            )
        )

        c.create_text(
            cx,
            cy + radius + 82,
            text="JARVIS NEURAL CORE",
            fill=MUTED,
            font=(
                FONT,
                9
            )
        )


    # ========================================================
    # BIG COMMAND BUTTON
    # ========================================================

    def build_big_command_button(self):

        self.command_button = tk.Canvas(
            self.command_area,
            bg=BG,
            height=125,
            highlightthickness=0
        )

        self.command_button.pack(
            fill="both",
            expand=True
        )

        self.command_button.bind(
            "<Button-1>",
            self.command_button_clicked
        )

        self.command_button.bind(
            "<Enter>",
            lambda e:
            self.command_button_hover(True)
        )

        self.command_button.bind(
            "<Leave>",
            lambda e:
            self.command_button_hover(False)
        )

        self.draw_command_button()


    def draw_command_button(self):

        c = self.command_button

        c.delete("all")

        width = max(
            c.winfo_width(),
            400
        )

        height = max(
            c.winfo_height(),
            120
        )

        cx = width / 2
        cy = height / 2

        button_w = min(
            430,
            width - 40
        )

        button_h = 78

        x1 = cx - button_w / 2
        y1 = cy - button_h / 2
        x2 = cx + button_w / 2
        y2 = cy + button_h / 2

        if self.listening:

            fill = "#18516B"
            outline = CYAN
            title = "●  LISTENING"

            subtitle = (
                "Speak your command..."
            )

        elif self.voice_mode:

            fill = "#15364E"
            outline = CYAN
            title = "🎙  VOICE MODE ACTIVE"

            subtitle = (
                "Continuous listening enabled"
            )

        else:

            fill = (
                "#1A3A56"
                if self.command_hover
                else "#142B43"
            )

            outline = (
                CYAN
                if self.command_hover
                else "#31536F"
            )

            title = "🎙  COMMAND JARVIS"

            subtitle = (
                "Tap to speak"
            )

        # Depth
        c.create_rectangle(
            x1 + 6,
            y1 + 8,
            x2 + 6,
            y2 + 8,
            fill=BLACK,
            outline=""
        )

        # Main
        c.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=fill,
            outline=outline,
            width=2
        )

        c.create_text(
            cx,
            cy - 9,
            text=title,
            fill=WHITE,
            font=(
                FONT,
                15,
                "bold"
            )
        )

        c.create_text(
            cx,
            cy + 20,
            text=subtitle,
            fill=(
                CYAN
                if self.listening
                else MUTED
            ),
            font=(
                FONT,
                9
            )
        )


    def command_button_hover(self, value):

        self.command_hover = value

        self.draw_command_button()


    def command_button_clicked(self, event=None):

        if not self.voice_enabled:

            self.write_log(
                "Voice interface is unavailable.",
                "warning"
            )

            return

        if not self.voice_mode:

            self.start_continuous_voice()

        elif not self.listening:

            self.start_listen_cycle()


    # ========================================================
    # RIGHT AREA
    # ========================================================

    def build_right_area(self):

        self.right = tk.Frame(
            self.main,
            bg=BG
        )

        self.right.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(12, 0)
        )

        self.right.grid_rowconfigure(
            1,
            weight=1
        )

        self.right.grid_columnconfigure(
            0,
            weight=1
        )

        self.build_status_cards()

        self.build_activity()

        self.build_quick_actions()


    # ========================================================
    # STATUS CARDS
    # ========================================================

    def build_status_cards(self):

        container = tk.Frame(
            self.right,
            bg=BG
        )

        container.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 12)
        )

        for i in range(5):

            container.grid_columnconfigure(
                i,
                weight=1
            )

        self.ai_card = self.create_info_card(
            container,
            0,
            "LOCAL AI",
            "LLAMA 3.2",
            CYAN
        )

        self.tool_card = self.create_info_card(
            container,
            1,
            "TOOLS",
            str(backend_tools_count()),
            GOLD
        )

        self.cpu_card = self.create_info_card(
            container,
            2,
            "CPU",
            "0%",
            GREEN
        )

        self.ram_card = self.create_info_card(
            container,
            3,
            "MEMORY",
            "0%",
            BLUE
        )

        self.gpu_card = self.create_info_card(
            container,
            4,
            "GPU",
            "Detecting...",
            CYAN
        )


    def create_info_card(
        self,
        parent,
        column,
        title,
        value,
        color
    ):

        frame = tk.Frame(
            parent,
            bg=PANEL,
            height=82
        )

        frame.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=3
        )

        frame.grid_propagate(
            False
        )

        tk.Frame(
            frame,
            bg=color,
            width=3
        ).pack(
            side="left",
            fill="y"
        )

        inner = tk.Frame(
            frame,
            bg=PANEL
        )

        inner.pack(
            fill="both",
            expand=True,
            padx=10
        )

        tk.Label(
            inner,
            text=title,
            bg=PANEL,
            fg=MUTED,
            font=(
                FONT,
                8,
                "bold"
            )
        ).pack(
            anchor="w",
            pady=(9, 1)
        )

        value_label = tk.Label(
            inner,
            text=value,
            bg=PANEL,
            fg=WHITE,
            font=(
                FONT,
                10,
                "bold"
            ),
            anchor="w"
        )

        value_label.pack(
            anchor="w",
            fill="x"
        )

        return value_label


    # ========================================================
    # ACTIVITY
    # ========================================================

    def build_activity(self):

        outer = tk.Frame(
            self.right,
            bg=PANEL
        )

        outer.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        title_row = tk.Frame(
            outer,
            bg=PANEL,
            height=48
        )

        title_row.pack(
            fill="x"
        )

        title_row.pack_propagate(
            False
        )

        tk.Label(
            title_row,
            text="LIVE ACTIVITY",
            bg=PANEL,
            fg=WHITE,
            font=(
                FONT,
                10,
                "bold"
            )
        ).pack(
            side="left",
            padx=16
        )

        self.live_indicator = tk.Label(
            title_row,
            text="● LIVE",
            bg=PANEL,
            fg=GREEN,
            font=(
                FONT,
                8,
                "bold"
            )
        )

        self.live_indicator.pack(
            side="right",
            padx=16
        )

        tk.Frame(
            outer,
            bg=LINE,
            height=1
        ).pack(
            fill="x"
        )

        self.activity = tk.Text(
            outer,
            bg="#0B192A",
            fg=TEXT,
            insertbackground=WHITE,
            selectbackground="#34769D",
            selectforeground=WHITE,
            relief="flat",
            borderwidth=0,
            font=(
                FONT,
                10
            ),
            wrap="word",
            padx=16,
            pady=12
        )

        self.activity.pack(
            fill="both",
            expand=True
        )

        self.activity.tag_configure(
            "time",
            foreground="#5F7D94"
        )

        self.activity.tag_configure(
            "jarvis",
            foreground=CYAN
        )

        self.activity.tag_configure(
            "you",
            foreground=GOLD
        )

        self.activity.tag_configure(
            "system",
            foreground=GREEN
        )

        self.activity.tag_configure(
            "warning",
            foreground=RED
        )

        self.activity.configure(
            state="disabled"
        )


    # ========================================================
    # QUICK ACTIONS
    # ========================================================

    def build_quick_actions(self):

        frame = tk.Frame(
            self.right,
            bg=BG,
            height=92
        )

        frame.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(12, 0)
        )

        frame.grid_propagate(
            False
        )

        buttons = [

            (
                "NOTEPAD",
                "open notepad"
            ),

            (
                "CALCULATOR",
                "open calculator"
            ),

            (
                "PC STATUS",
                "show me my cpu gpu and memory"
            ),

        ]

        for i, (label, command) in enumerate(buttons):

            frame.grid_columnconfigure(
                i,
                weight=1
            )

            button = tk.Button(
                frame,
                text=label,
                command=lambda c=command:
                self.submit_command(c),
                bg=PANEL_LIGHT,
                fg=TEXT,
                activebackground="#1D4666",
                activeforeground=WHITE,
                relief="flat",
                bd=0,
                font=(
                    FONT,
                    9,
                    "bold"
                ),
                cursor="hand2"
            )

            button.grid(
                row=0,
                column=i,
                sticky="ew",
                padx=4,
                pady=5
            )


    # ========================================================
    # COMMAND BAR
    # ========================================================

    def build_command_bar(self):

        self.bottom = tk.Frame(
            self.root,
            bg="#091522",
            height=88
        )

        self.bottom.grid(
            row=2,
            column=0,
            sticky="ew"
        )

        self.bottom.grid_propagate(
            False
        )

        self.bottom.grid_columnconfigure(
            2,
            weight=1
        )

        # ----------------------------------------------------
        # START VOICE
        # ----------------------------------------------------

        self.start_voice_button = tk.Button(
            self.bottom,
            text="🎙  START VOICE",
            command=self.start_continuous_voice,
            bg="#174E66",
            fg=WHITE,
            activebackground="#246E8E",
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            font=(
                FONT,
                9,
                "bold"
            ),
            cursor="hand2"
        )

        self.start_voice_button.grid(
            row=0,
            column=0,
            padx=(20, 5),
            pady=14,
            ipadx=8,
            ipady=8
        )

        # ----------------------------------------------------
        # STOP VOICE
        # ----------------------------------------------------

        self.stop_voice_button = tk.Button(
            self.bottom,
            text="■  STOP VOICE",
            command=self.stop_continuous_voice,
            bg="#48202A",
            fg="#FFB6BD",
            activebackground="#6A2936",
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            font=(
                FONT,
                9,
                "bold"
            ),
            cursor="hand2"
        )

        self.stop_voice_button.grid(
            row=0,
            column=1,
            padx=5,
            pady=14,
            ipadx=8,
            ipady=8
        )

        # ----------------------------------------------------
        # INPUT
        # ----------------------------------------------------

        self.entry = tk.Entry(
            self.bottom,
            bg="#142B40",
            fg=WHITE,
            insertbackground=WHITE,
            selectbackground="#34769D",
            selectforeground=WHITE,
            relief="flat",
            bd=0,
            font=(
                FONT,
                12
            )
        )

        self.entry.grid(
            row=0,
            column=2,
            sticky="ew",
            padx=8,
            pady=14,
            ipady=13
        )

        self.placeholder = (
            "Ask JARVIS anything..."
        )

        self.entry.insert(
            0,
            self.placeholder
        )

        self.entry.config(
            fg="#7D98AC"
        )

        self.entry.bind(
            "<FocusIn>",
            self.entry_focus_in
        )

        self.entry.bind(
            "<FocusOut>",
            self.entry_focus_out
        )

        self.entry.bind(
            "<Return>",
            lambda e:
            self.submit_text()
        )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        self.send_button = tk.Button(
            self.bottom,
            text="SEND  ➜",
            command=self.submit_text,
            bg=CYAN_DARK,
            fg=WHITE,
            activebackground=CYAN,
            activeforeground="#06111C",
            relief="flat",
            bd=0,
            font=(
                FONT,
                10,
                "bold"
            ),
            cursor="hand2",
            width=12
        )

        self.send_button.grid(
            row=0,
            column=3,
            padx=(5, 20),
            pady=14,
            ipady=10
        )


    # ========================================================
    # ENTRY
    # ========================================================

    def entry_focus_in(self, event=None):

        if self.entry.get() == self.placeholder:

            self.entry.delete(
                0,
                tk.END
            )

            self.entry.config(
                fg=WHITE
            )


    def entry_focus_out(self, event=None):

        if not self.entry.get().strip():

            self.entry.insert(
                0,
                self.placeholder
            )

            self.entry.config(
                fg="#7D98AC"
            )


    def submit_text(self):

        text = self.entry.get().strip()

        if not text:
            return

        if text == self.placeholder:
            return

        self.entry.delete(
            0,
            tk.END
        )

        self.submit_command(
            text
        )


    # ========================================================
    # COMMAND
    # ========================================================

    def submit_command(self, text):

        text = str(
            text
        ).strip()

        if not text:
            return

        self.write_log(
            f"YOU  > {text}",
            "you"
        )

        self.set_thinking(
            True
        )

        threading.Thread(
            target=self.command_worker,
            args=(text,),
            daemon=True
        ).start()


    def command_worker(self, text):

        try:

            # Local dashboard commands first
            special = local_special_command(
                text
            )

            if special is not None:

                post_event(
                    "command_result",
                    special
                )

                return

            # Existing JARVIS backend
            result = backend_command(
                text
            )

            if isinstance(
                result,
                dict
            ):

                message = result.get(
                    "message",
                    ""
                )

            else:

                message = str(
                    result
                )

            post_event(
                "command_result",
                message
            )

        except Exception as e:

            post_event(
                "command_result",
                f"Command error: {e}"
            )


    # ========================================================
    # CONTINUOUS VOICE
    # ========================================================

    def start_continuous_voice(self):

        if not self.voice_enabled:

            self.write_log(
                "Voice interface is unavailable.",
                "warning"
            )

            return

        if self.voice_mode:

            self.write_log(
                "Continuous voice mode is already active.",
                "warning"
            )

            return

        self.voice_mode = True

        self.set_status(
            "VOICE ACTIVE",
            CYAN
        )

        self.write_log(
            "Continuous voice mode started.",
            "system"
        )

        self.start_voice_button.config(
            bg="#246E8E"
        )

        self.draw_core()
        self.draw_command_button()

        self.start_listen_cycle()


    def stop_continuous_voice(self):

        if not self.voice_mode:

            self.write_log(
                "Voice mode is already stopped.",
                "warning"
            )

            return

        self.voice_mode = False

        self.listening = False

        self.set_status(
            "SYSTEM READY",
            GREEN
        )

        self.write_log(
            "Voice listening stopped.",
            "system"
        )

        self.start_voice_button.config(
            bg="#174E66"
        )

        self.draw_core()
        self.draw_command_button()


    def start_listen_cycle(self):

        if not self.running:
            return

        if not self.voice_mode:
            return

        if self.listening:
            return

        if self.thinking:
            return

        self.listening = True

        self.set_status(
            "LISTENING",
            CYAN
        )

        self.write_log(
            "Microphone active. Listening...",
            "jarvis"
        )

        self.draw_core()
        self.draw_command_button()

        threading.Thread(
            target=self.voice_worker,
            daemon=True
        ).start()


    def voice_worker(self):

        try:

            if listen is None:

                post_event(
                    "voice_error",
                    "Voice listener is unavailable."
                )

                return

            text = listen()

            if text:

                post_event(
                    "voice_result",
                    str(text).strip()
                )

            else:

                post_event(
                    "voice_empty",
                    None
                )

        except Exception as e:

            post_event(
                "voice_error",
                str(e)
            )


    # ========================================================
    # VOICE COMMAND PROCESSING
    # ========================================================

    def process_voice_command(self, text):

        # Stop command is handled locally
        if is_voice_stop_command(text):

            self.stop_continuous_voice()

            self.write_log(
                "Voice mode stopped by voice command.",
                "system"
            )

            return

        self.set_thinking(
            True
        )

        try:

            # System controls first
            special = local_special_command(
                text
            )

            if special is not None:

                post_event(
                    "voice_command_result",
                    special
                )

                return

            # Existing backend
            result = backend_command(
                text
            )

            if isinstance(
                result,
                dict
            ):

                message = result.get(
                    "message",
                    ""
                )

            else:

                message = str(
                    result
                )

            post_event(
                "voice_command_result",
                message
            )

        except Exception as e:

            post_event(
                "voice_command_result",
                f"Command error: {e}"
            )


    # ========================================================
    # STATE
    # ========================================================

    def set_thinking(self, value):

        self.thinking = value

        if value:

            self.set_status(
                "THINKING",
                GOLD
            )

        else:

            if self.voice_mode:

                self.set_status(
                    "VOICE ACTIVE",
                    CYAN
                )

            else:

                self.set_status(
                    "SYSTEM READY",
                    GREEN
                )

        self.draw_core()


    def set_status(
        self,
        text,
        color
    ):

        try:

            self.header_status.config(
                text=text,
                fg=color
            )

            self.status_dot.itemconfig(
                self.status_circle,
                fill=color
            )

        except Exception:
            pass


    # ========================================================
    # EVENTS
    # ========================================================

    def process_events(self):

        try:

            while True:

                kind, data = events.get_nowait()

                # --------------------------------------------
                # NORMAL COMMAND
                # --------------------------------------------

                if kind == "command_result":

                    self.set_thinking(
                        False
                    )

                    self.write_log(
                        f"JARVIS > {data}",
                        "jarvis"
                    )

                    self.safe_speak(
                        data
                    )

                # --------------------------------------------
                # VOICE RESULT
                # --------------------------------------------

                elif kind == "voice_result":

                    self.listening = False

                    self.set_status(
                        "THINKING",
                        GOLD
                    )

                    self.draw_core()
                    self.draw_command_button()

                    # IMPORTANT:
                    # Only ONE YOU entry.
                    self.write_log(
                        f"YOU 🎙 > {data}",
                        "you"
                    )

                    threading.Thread(
                        target=self.process_voice_command,
                        args=(data,),
                        daemon=True
                    ).start()

                # --------------------------------------------
                # EMPTY VOICE
                # --------------------------------------------

                elif kind == "voice_empty":

                    self.listening = False

                    if self.voice_mode:

                        self.set_status(
                            "VOICE ACTIVE",
                            CYAN
                        )

                    else:

                        self.set_status(
                            "SYSTEM READY",
                            GREEN
                        )

                    self.write_log(
                        "I didn't hear anything.",
                        "warning"
                    )

                    self.draw_core()
                    self.draw_command_button()

                    if self.voice_mode:

                        self.root.after(
                            250,
                            self.start_listen_cycle
                        )

                # --------------------------------------------
                # VOICE ERROR
                # --------------------------------------------

                elif kind == "voice_error":

                    self.listening = False
                    self.thinking = False

                    self.set_status(
                        "VOICE ERROR",
                        RED
                    )

                    self.write_log(
                        f"Voice error: {data}",
                        "warning"
                    )

                    self.draw_core()
                    self.draw_command_button()

                    if self.voice_mode:

                        self.root.after(
                            1000,
                            self.start_listen_cycle
                        )

                # --------------------------------------------
                # VOICE RESULT
                # --------------------------------------------

                elif kind == "voice_command_result":

                    self.set_thinking(
                        False
                    )

                    self.write_log(
                        f"JARVIS > {data}",
                        "jarvis"
                    )

                    self.safe_speak(
                        data
                    )

                # --------------------------------------------
                # SPEAKING
                # --------------------------------------------

                elif kind == "speaking":

                    self.speaking = True

                    self.set_status(
                        "SPEAKING",
                        GREEN
                    )

                    self.draw_core()

                # --------------------------------------------
                # SPEAKING DONE
                # --------------------------------------------

                elif kind == "speaking_done":

                    self.speaking = False

                    if self.voice_mode:

                        self.set_status(
                            "VOICE ACTIVE",
                            CYAN
                        )

                    else:

                        self.set_status(
                            "SYSTEM READY",
                            GREEN
                        )

                    self.draw_core()

                    # Continue listening AFTER speech
                    if self.voice_mode:

                        self.root.after(
                            350,
                            self.start_listen_cycle
                        )

        except queue.Empty:
            pass

        if self.running:

            self.root.after(
                50,
                self.process_events
            )


    # ========================================================
    # SPEECH
    # ========================================================

    def safe_speak(self, message):

        if not message:
            return

        if speak is None:
            return

        def worker():

            post_event(
                "speaking",
                None
            )

            try:

                speak(
                    str(message)
                )

            except Exception as e:

                post_event(
                    "voice_error",
                    str(e)
                )

            finally:

                post_event(
                    "speaking_done",
                    None
                )

        threading.Thread(
            target=worker,
            daemon=True
        ).start()


    # ========================================================
    # LOG
    # ========================================================

    def write_log(
        self,
        message,
        tag="system"
    ):

        timestamp = time.strftime(
            "%H:%M:%S"
        )

        try:

            self.activity.config(
                state="normal"
            )

            self.activity.insert(
                tk.END,
                f"[{timestamp}] ",
                "time"
            )

            self.activity.insert(
                tk.END,
                message + "\n",
                tag
            )

            self.activity.see(
                tk.END
            )

            self.activity.config(
                state="disabled"
            )

        except Exception:
            pass


    # ========================================================
    # SYSTEM STATS
    # ========================================================

    def update_system_stats(self):

        if not self.running:
            return

        try:

            if psutil:

                cpu = psutil.cpu_percent(
                    interval=None
                )

                ram = psutil.virtual_memory()

                self.cpu_card.config(
                    text=f"{cpu:.0f}%"
                )

                self.ram_card.config(
                    text=(
                        f"{ram.percent:.0f}%  "
                        f"({ram.used / 1024**3:.1f} GB)"
                    )
                )

            # GPU
            gpu = get_gpu_info()

            self.last_gpu = gpu

            gpu_name = gpu["name"]

            # Keep card readable
            if len(gpu_name) > 18:

                gpu_name = (
                    gpu_name[:17]
                    + "…"
                )

            self.gpu_card.config(
                text=(
                    f"{gpu_name}  "
                    f"{gpu['memory']}"
                )
            )

            # Window title
            if psutil:

                self.root.title(
                    f"{APP_TITLE}  |  "
                    f"CPU {cpu:.0f}%  |  "
                    f"RAM {ram.percent:.0f}%"
                )

        except Exception:
            pass

        self.root.after(
            1500,
            self.update_system_stats
        )


    # ========================================================
    # ANIMATION
    # ========================================================

    def animate(self):

        if not self.running:
            return

        self.animation_phase += 0.025

        try:

            self.draw_core()
            self.draw_command_button()

        except Exception:
            pass

        self.root.after(
            35,
            self.animate
        )


    # ========================================================
    # COLOR MIX
    # ========================================================

    @staticmethod
    def mix_color(
        color1,
        color2,
        amount
    ):

        amount = max(
            0,
            min(
                1,
                amount
            )
        )

        try:

            c1 = color1.lstrip("#")
            c2 = color2.lstrip("#")

            r1 = int(
                c1[0:2],
                16
            )

            g1 = int(
                c1[2:4],
                16
            )

            b1 = int(
                c1[4:6],
                16
            )

            r2 = int(
                c2[0:2],
                16
            )

            g2 = int(
                c2[2:4],
                16
            )

            b2 = int(
                c2[4:6],
                16
            )

            r = int(
                r1
                + (r2 - r1)
                * amount
            )

            g = int(
                g1
                + (g2 - g1)
                * amount
            )

            b = int(
                b1
                + (b2 - b1)
                * amount
            )

            return (
                f"#{r:02x}"
                f"{g:02x}"
                f"{b:02x}"
            )

        except Exception:

            return color1


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.running = False
        self.voice_mode = False
        self.listening = False

        try:

            self.root.destroy()

        except Exception:
            pass


# ============================================================
# START
# ============================================================

def main():

    root = tk.Tk()

    app = JarvisDashboard(
        root
    )

    root.mainloop()


if __name__ == "__main__":

    main()