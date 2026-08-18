# ============================================================
# JARVIS 3D COMMAND CENTER
# Complete Dashboard
# ============================================================

import tkinter as tk
from tkinter import ttk
import threading
import time
import math
import random
import queue
import datetime
import traceback

# ------------------------------------------------------------
# OPTIONAL SYSTEM MONITOR
# ------------------------------------------------------------

try:
    import psutil
except Exception:
    psutil = None

# ------------------------------------------------------------
# JARVIS BACKEND
# ------------------------------------------------------------

try:
    from main import process_command
except Exception as e:
    process_command = None
    BACKEND_ERROR = str(e)

# ------------------------------------------------------------
# VOICE
# ------------------------------------------------------------

try:
    from voice import listen, speak
except Exception:
    listen = None
    speak = None


# ============================================================
# CONFIGURATION
# ============================================================

APP_TITLE = "JARVIS COMMAND CENTER"

BG = "#05080d"
BG2 = "#08111b"
PANEL = "#0a1521"
PANEL2 = "#0d1c2b"

CYAN = "#00e5ff"
CYAN2 = "#00a8cc"
BLUE = "#168cff"
BLUE2 = "#0a5eff"

GREEN = "#00ff9c"
RED = "#ff3355"
ORANGE = "#ffae00"
WHITE = "#f2fbff"
TEXT = "#b8d9e8"
MUTED = "#5f7f91"

GRID = "#102638"
BORDER = "#16445c"

FONT = "Segoe UI"

WINDOW_W = 1500
WINDOW_H = 900


# ============================================================
# APPLICATION
# ============================================================

class JarvisDashboard:

    def __init__(self, root):

        self.root = root

        self.root.title(APP_TITLE)

        self.root.geometry(
            f"{WINDOW_W}x{WINDOW_H}"
        )

        self.root.minsize(
            1100,
            700,
        )

        self.root.configure(
            bg=BG
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.running = True

        self.voice_active = False
        self.voice_thread = None

        self.processing = False
        self.speaking = False

        self.status = "READY"

        self.event_queue = queue.Queue()

        self.command_history = []

        self.wave_phase = 0

        self.reactor_phase = 0

        self.pulse_phase = 0

        self.last_cpu = 0
        self.last_ram = 0
        self.last_disk = 0

        # ----------------------------------------------------
        # WINDOW
        # ----------------------------------------------------

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.shutdown,
        )

        # ----------------------------------------------------
        # STYLE
        # ----------------------------------------------------

        self.setup_styles()

        # ----------------------------------------------------
        # UI
        # ----------------------------------------------------

        self.build_ui()

        # ----------------------------------------------------
        # INITIAL LOG
        # ----------------------------------------------------

        self.log_event(
            "JARVIS COMMAND CENTER ONLINE",
            "system",
        )

        self.log_event(
            "Local AI backend connected.",
            "system",
        )

        self.log_event(
            self.get_tool_count_message(),
            "system",
        )

        if listen:
            self.log_event(
                "Voice interface ready.",
                "system",
            )
        else:
            self.log_event(
                "Voice interface unavailable.",
                "warning",
            )

        self.log_event(
            "Ready // awaiting command",
            "system",
        )

        # ----------------------------------------------------
        # START LOOPS
        # ----------------------------------------------------

        self.update_system_stats()

        self.animate_reactor()

        self.animate_waveform()

        self.process_events()

        # ----------------------------------------------------
        # WELCOME
        # ----------------------------------------------------

        self.set_status(
            "READY",
            GREEN,
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
            "Dark.TCombobox",
            fieldbackground=PANEL,
            background=PANEL,
            foreground=WHITE,
        )

    # ========================================================
    # TOOL COUNT
    # ========================================================

    def get_tool_count_message(self):

        try:

            from tools.registry import list_tools

            tools = list_tools()

            return (
                f"Tools detected: "
                f"{len(tools)}"
            )

        except Exception:

            return "Tools detected: --"

    # ========================================================
    # BUILD UI
    # ========================================================

    def build_ui(self):

        # ----------------------------------------------------
        # MAIN GRID
        # ----------------------------------------------------

        self.root.grid_rowconfigure(
            1,
            weight=1,
        )

        self.root.grid_columnconfigure(
            0,
            weight=1,
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        self.header = tk.Frame(
            self.root,
            bg=BG,
            height=72,
        )

        self.header.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.header.grid_propagate(
            False
        )

        self.build_header()

        # ----------------------------------------------------
        # BODY
        # ----------------------------------------------------

        self.body = tk.Frame(
            self.root,
            bg=BG,
        )

        self.body.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=14,
            pady=(0, 10),
        )

        self.body.grid_rowconfigure(
            0,
            weight=1,
        )

        self.body.grid_columnconfigure(
            0,
            minsize=260,
        )

        self.body.grid_columnconfigure(
            1,
            weight=1,
        )

        self.body.grid_columnconfigure(
            2,
            minsize=300,
        )

        self.build_left_panel()

        self.build_center_panel()

        self.build_right_panel()

        # ----------------------------------------------------
        # COMMAND BAR
        # ----------------------------------------------------

        self.build_command_bar()

    # ========================================================
    # HEADER
    # ========================================================

    def build_header(self):

        # Logo

        logo = tk.Label(
            self.header,
            text="J A R V I S",
            font=(
                FONT,
                23,
                "bold",
            ),
            fg=CYAN,
            bg=BG,
        )

        logo.pack(
            side="left",
            padx=24,
        )

        subtitle = tk.Label(
            self.header,
            text="COMMAND CENTER // LOCAL AI SYSTEM",
            font=(
                FONT,
                9,
            ),
            fg=MUTED,
            bg=BG,
        )

        subtitle.pack(
            side="left",
            pady=(7, 0),
        )

        # Status

        self.header_status_dot = tk.Label(
            self.header,
            text="●",
            font=(
                FONT,
                17,
                "bold",
            ),
            fg=GREEN,
            bg=BG,
        )

        self.header_status_dot.pack(
            side="right",
            padx=(10, 4),
        )

        self.header_status = tk.Label(
            self.header,
            text="SYSTEM ONLINE",
            font=(
                FONT,
                10,
                "bold",
            ),
            fg=GREEN,
            bg=BG,
        )

        self.header_status.pack(
            side="right",
            padx=20,
        )

    # ========================================================
    # PANEL HELPER
    # ========================================================

    def panel(
        self,
        parent,
        title,
    ):

        outer = tk.Frame(
            parent,
            bg=BORDER,
        )

        inner = tk.Frame(
            outer,
            bg=PANEL,
        )

        inner.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        title_frame = tk.Frame(
            inner,
            bg=PANEL2,
            height=36,
        )

        title_frame.pack(
            fill="x",
        )

        title_frame.pack_propagate(
            False
        )

        label = tk.Label(
            title_frame,
            text=title,
            font=(
                FONT,
                9,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL2,
            anchor="w",
        )

        label.pack(
            fill="both",
            padx=12,
        )

        return outer, inner

    # ========================================================
    # LEFT PANEL
    # ========================================================

    def build_left_panel(self):

        self.left_outer, self.left = self.panel(
            self.body,
            "SYSTEM TELEMETRY",
        )

        self.left_outer.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 8),
        )

        # ----------------------------------------------------
        # SYSTEM
        # ----------------------------------------------------

        self.add_section_title(
            self.left,
            "SYSTEM",
        )

        self.cpu_value = self.add_metric(
            self.left,
            "CPU",
        )

        self.ram_value = self.add_metric(
            self.left,
            "RAM",
        )

        self.disk_value = self.add_metric(
            self.left,
            "DISK",
        )

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        self.add_section_title(
            self.left,
            "AI CORE",
        )

        self.add_info(
            self.left,
            "BACKEND",
            "OLLAMA",
        )

        self.ai_model_label = self.add_info(
            self.left,
            "MODEL",
            "llama3.2:3b",
        )

        self.ai_status_label = self.add_info(
            self.left,
            "STATUS",
            "CONNECTED",
            GREEN,
        )

        # ----------------------------------------------------
        # VOICE
        # ----------------------------------------------------

        self.add_section_title(
            self.left,
            "VOICE INTERFACE",
        )

        self.voice_status_label = self.add_info(
            self.left,
            "STATUS",
            "READY",
            GREEN,
        )

        self.voice_state_label = self.add_info(
            self.left,
            "STATE",
            "STANDBY",
        )

        # ----------------------------------------------------
        # VOICE BUTTON
        # ----------------------------------------------------

        self.voice_button = tk.Button(
            self.left,
            text="🎤  START VOICE",
            command=self.toggle_voice,
            font=(
                FONT,
                10,
                "bold",
            ),
            fg=BG,
            bg=CYAN,
            activeforeground=BG,
            activebackground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=8,
            pady=10,
        )

        self.voice_button.pack(
            fill="x",
            padx=14,
            pady=(10, 8),
        )

        # ----------------------------------------------------
        # VOICE LEVEL
        # ----------------------------------------------------

        self.add_section_title(
            self.left,
            "AUDIO ACTIVITY",
        )

        self.voice_meter = tk.Canvas(
            self.left,
            height=75,
            bg=PANEL,
            highlightthickness=0,
        )

        self.voice_meter.pack(
            fill="x",
            padx=10,
            pady=5,
        )

    # ========================================================
    # CENTER PANEL
    # ========================================================

    def build_center_panel(self):

        self.center_outer, self.center = self.panel(
            self.body,
            "JARVIS NEURAL CORE",
        )

        self.center_outer.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=8,
        )

        # ----------------------------------------------------
        # REACTOR CANVAS
        # ----------------------------------------------------

        self.reactor = tk.Canvas(
            self.center,
            bg=BG2,
            highlightthickness=0,
        )

        self.reactor.pack(
            fill="both",
            expand=True,
        )

        self.reactor.bind(
            "<Configure>",
            lambda event: self.draw_reactor(),
        )

        # ----------------------------------------------------
        # CENTER STATUS
        # ----------------------------------------------------

        self.center_status = tk.Label(
            self.center,
            text="READY // AWAITING COMMAND",
            font=(
                FONT,
                12,
                "bold",
            ),
            fg=GREEN,
            bg=PANEL,
        )

        self.center_status.pack(
            pady=10,
        )

        # ----------------------------------------------------
        # CONVERSATION
        # ----------------------------------------------------

        self.add_section_title(
            self.center,
            "COMMAND STREAM",
        )

        stream_frame = tk.Frame(
            self.center,
            bg=BG2,
        )

        stream_frame.pack(
            fill="both",
            expand=False,
            padx=12,
            pady=(4, 12),
        )

        self.command_stream = tk.Text(
            stream_frame,
            height=8,
            bg="#04070b",
            fg=TEXT,
            insertbackground=CYAN,
            selectbackground=CYAN2,
            selectforeground=WHITE,
            font=(
                "Consolas",
                9,
            ),
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
        )

        self.command_stream.pack(
            fill="both",
            expand=True,
        )

        self.command_stream.tag_configure(
            "you",
            foreground=CYAN,
        )

        self.command_stream.tag_configure(
            "jarvis",
            foreground=GREEN,
        )

        self.command_stream.tag_configure(
            "system",
            foreground=MUTED,
        )

        self.command_stream.tag_configure(
            "warning",
            foreground=ORANGE,
        )

    # ========================================================
    # RIGHT PANEL
    # ========================================================

    def build_right_panel(self):

        self.right_outer, self.right = self.panel(
            self.body,
            "TASK MATRIX",
        )

        self.right_outer.grid(
            row=0,
            column=2,
            sticky="nsew",
            padx=(8, 0),
        )

        self.add_section_title(
            self.right,
            "CURRENT STATUS",
        )

        self.task_status = tk.Label(
            self.right,
            text="IDLE",
            font=(
                FONT,
                20,
                "bold",
            ),
            fg=GREEN,
            bg=PANEL,
        )

        self.task_status.pack(
            pady=(8, 15),
        )

        # ----------------------------------------------------
        # TASK LIST
        # ----------------------------------------------------

        self.add_section_title(
            self.right,
            "RECENT TASKS",
        )

        self.task_list = tk.Listbox(
            self.right,
            bg="#050a10",
            fg=TEXT,
            selectbackground=CYAN2,
            selectforeground=WHITE,
            font=(
                "Consolas",
                9,
            ),
            relief="flat",
            bd=0,
            highlightthickness=0,
        )

        self.task_list.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=8,
        )

        # ----------------------------------------------------
        # QUICK COMMANDS
        # ----------------------------------------------------

        self.add_section_title(
            self.right,
            "QUICK COMMANDS",
        )

        quick_commands = [
            ("OPEN NOTEPAD", "open notepad"),
            ("OPEN CALCULATOR", "open calculator"),
            ("SYSTEM INFO", "show me my PC information"),
            ("TIME", "what time is it"),
            ("JOKE", "tell me a joke"),
            ("CLOSE BOTH", "close both"),
        ]

        for title, command in quick_commands:

            button = tk.Button(
                self.right,
                text=title,
                command=lambda c=command: self.send_command(c),
                font=(
                    FONT,
                    8,
                    "bold",
                ),
                fg=TEXT,
                bg=PANEL2,
                activeforeground=WHITE,
                activebackground="#12364c",
                relief="flat",
                bd=0,
                cursor="hand2",
                pady=6,
            )

            button.pack(
                fill="x",
                padx=12,
                pady=2,
            )

    # ========================================================
    # COMMAND BAR
    # ========================================================

    def build_command_bar(self):

        bar = tk.Frame(
            self.root,
            bg="#03060a",
            height=82,
        )

        bar.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=14,
            pady=(0, 14),
        )

        bar.grid_propagate(
            False
        )

        # ----------------------------------------------------
        # LABEL
        # ----------------------------------------------------

        label = tk.Label(
            bar,
            text="YOU >",
            font=(
                "Consolas",
                11,
                "bold",
            ),
            fg=CYAN,
            bg="#03060a",
        )

        label.pack(
            side="left",
            padx=(16, 8),
        )

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        self.command_entry = tk.Entry(
            bar,
            font=(
                FONT,
                12,
            ),
            bg="#101c28",
            fg=WHITE,
            insertbackground=CYAN,
            selectbackground=CYAN2,
            selectforeground=WHITE,
            relief="flat",
            bd=0,
        )

        self.command_entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
            pady=13,
        )

        self.command_entry.bind(
            "<Return>",
            self.on_enter,
        )

        # ----------------------------------------------------
        # VOICE
        # ----------------------------------------------------

        mic_button = tk.Button(
            bar,
            text="🎤",
            command=self.toggle_voice,
            font=(
                FONT,
                15,
            ),
            fg=CYAN,
            bg="#07131d",
            activeforeground=WHITE,
            activebackground="#12364c",
            relief="flat",
            bd=0,
            cursor="hand2",
            width=4,
        )

        mic_button.pack(
            side="left",
            padx=4,
            pady=13,
        )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        send_button = tk.Button(
            bar,
            text="SEND  ➤",
            command=self.on_send,
            font=(
                FONT,
                10,
                "bold",
            ),
            fg=BG,
            bg=CYAN,
            activeforeground=BG,
            activebackground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            width=10,
        )

        send_button.pack(
            side="right",
            padx=(4, 14),
            pady=13,
        )

        self.send_button = send_button

    # ========================================================
    # UI HELPERS
    # ========================================================

    def add_section_title(
        self,
        parent,
        text,
    ):

        label = tk.Label(
            parent,
            text=text,
            font=(
                FONT,
                8,
                "bold",
            ),
            fg=MUTED,
            bg=PANEL,
            anchor="w",
        )

        label.pack(
            fill="x",
            padx=14,
            pady=(14, 5),
        )

    def add_metric(
        self,
        parent,
        name,
    ):

        frame = tk.Frame(
            parent,
            bg=PANEL,
        )

        frame.pack(
            fill="x",
            padx=14,
            pady=4,
        )

        label = tk.Label(
            frame,
            text=name,
            font=(
                FONT,
                9,
                "bold",
            ),
            fg=TEXT,
            bg=PANEL,
        )

        label.pack(
            side="left",
        )

        value = tk.Label(
            frame,
            text="--%",
            font=(
                "Consolas",
                10,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL,
        )

        value.pack(
            side="right",
        )

        return value

    def add_info(
        self,
        parent,
        name,
        value,
        color=TEXT,
    ):

        frame = tk.Frame(
            parent,
            bg=PANEL,
        )

        frame.pack(
            fill="x",
            padx=14,
            pady=3,
        )

        label = tk.Label(
            frame,
            text=name,
            font=(
                FONT,
                8,
            ),
            fg=MUTED,
            bg=PANEL,
        )

        label.pack(
            side="left",
        )

        value_label = tk.Label(
            frame,
            text=value,
            font=(
                "Consolas",
                8,
                "bold",
            ),
            fg=color,
            bg=PANEL,
        )

        value_label.pack(
            side="right",
        )

        return value_label

    # ========================================================
    # LOGGING
    # ========================================================

    def log_event(
        self,
        message,
        category="system",
    ):

        timestamp = datetime.datetime.now().strftime(
            "%H:%M:%S"
        )

        self.event_queue.put(
            (
                "log",
                timestamp,
                message,
                category,
            )
        )

    def append_log(
        self,
        timestamp,
        message,
        category,
    ):

        self.command_stream.configure(
            state="normal"
        )

        self.command_stream.insert(
            "end",
            f"[{timestamp}] ",
            "system",
        )

        tag = category

        if category not in {
            "you",
            "jarvis",
            "system",
            "warning",
        }:
            tag = "system"

        self.command_stream.insert(
            "end",
            f"{message}\n",
            tag,
        )

        self.command_stream.see(
            "end"
        )

        self.command_stream.configure(
            state="disabled"
        )

    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        status,
        color=GREEN,
    ):

        self.status = status

        self.center_status.configure(
            text=status,
            fg=color,
        )

        self.header_status.configure(
            text=status,
            fg=color,
        )

        self.header_status_dot.configure(
            fg=color
        )

        self.task_status.configure(
            text=status,
            fg=color,
        )

    # ========================================================
    # ENTER
    # ========================================================

    def on_enter(
        self,
        event=None,
    ):

        self.on_send()

        return "break"

    # ========================================================
    # SEND
    # ========================================================

    def on_send(self):

        if self.processing:

            return

        text = self.command_entry.get().strip()

        if not text:

            return

        self.command_entry.delete(
            0,
            "end",
        )

        self.send_command(
            text
        )

    # ========================================================
    # COMMAND
    # ========================================================

    def send_command(
        self,
        text,
    ):

        if not text:
            return

        if self.processing:
            return

        self.processing = True

        self.set_status(
            "THINKING...",
            CYAN,
        )

        self.voice_state_label.configure(
            text="PROCESSING",
            fg=CYAN,
        )

        self.log_event(
            f"YOU > {text}",
            "you",
        )

        self.task_list.insert(
            "end",
            f"● {text}",
        )

        if self.task_list.size() > 12:

            self.task_list.delete(
                0
            )

        self.send_button.configure(
            state="disabled",
            bg=MUTED,
        )

        thread = threading.Thread(
            target=self.command_worker,
            args=(text,),
            daemon=True,
        )

        thread.start()

    # ========================================================
    # COMMAND WORKER
    # ========================================================

    def command_worker(
        self,
        text,
    ):

        try:

            if process_command is None:

                result = {
                    "exit": False,
                    "message": (
                        "JARVIS backend unavailable: "
                        f"{BACKEND_ERROR}"
                    ),
                }

            else:

                result = process_command(
                    text
                )

            self.event_queue.put(
                (
                    "command_result",
                    text,
                    result,
                )
            )

        except Exception as e:

            self.event_queue.put(
                (
                    "error",
                    str(e),
                    traceback.format_exc(),
                )
            )

    # ========================================================
    # PROCESS EVENTS
    # ========================================================

    def process_events(self):

        try:

            while True:

                event = self.event_queue.get_nowait()

                event_type = event[0]

                if event_type == "log":

                    self.append_log(
                        event[1],
                        event[2],
                        event[3],
                    )

                elif event_type == "command_result":

                    self.handle_command_result(
                        event[1],
                        event[2],
                    )

                elif event_type == "voice_text":

                    self.handle_voice_text(
                        event[1]
                    )

                elif event_type == "voice_state":

                    self.handle_voice_state(
                        event[1]
                    )

                elif event_type == "error":

                    self.handle_error(
                        event[1],
                        event[2],
                    )

        except queue.Empty:
            pass

        if self.running:

            self.root.after(
                50,
                self.process_events,
            )

    # ========================================================
    # COMMAND RESULT
    # ========================================================

    def handle_command_result(
        self,
        text,
        result,
    ):

        self.processing = False

        self.send_button.configure(
            state="normal",
            bg=CYAN,
        )

        message = None

        if isinstance(
            result,
            dict,
        ):

            message = result.get(
                "message"
            )

        if not message:

            message = (
                "Command completed."
            )

        self.log_event(
            f"JARVIS > {message}",
            "jarvis",
        )

        self.set_status(
            "READY // AWAITING COMMAND",
            GREEN,
        )

        self.voice_state_label.configure(
            text="STANDBY",
            fg=GREEN,
        )

        # ----------------------------------------------------
        # SPEAK
        # ----------------------------------------------------

        if speak and message:

            threading.Thread(
                target=self.speak_worker,
                args=(message,),
                daemon=True,
            ).start()

    # ========================================================
    # SPEAK
    # ========================================================

    def speak_worker(
        self,
        message,
    ):

        try:

            self.event_queue.put(
                (
                    "voice_state",
                    "speaking",
                )
            )

            speak(
                str(message)
            )

        except Exception as e:

            self.event_queue.put(
                (
                    "error",
                    f"Voice output failed: {e}",
                    "",
                )
            )

        finally:

            self.event_queue.put(
                (
                    "voice_state",
                    "ready",
                )
            )

    # ========================================================
    # VOICE TOGGLE
    # ========================================================

    def toggle_voice(self):

        if listen is None:

            self.log_event(
                "Voice interface is unavailable.",
                "warning",
            )

            return

        if self.voice_active:

            self.stop_voice()

        else:

            self.start_voice()

    # ========================================================
    # START VOICE
    # ========================================================

    def start_voice(self):

        if self.voice_active:
            return

        self.voice_active = True

        self.voice_button.configure(
            text="⏹  STOP VOICE",
            bg=RED,
            fg=WHITE,
        )

        self.voice_status_label.configure(
            text="ACTIVE",
            fg=GREEN,
        )

        self.voice_state_label.configure(
            text="LISTENING",
            fg=GREEN,
        )

        self.set_status(
            "VOICE LISTENING",
            GREEN,
        )

        self.log_event(
            "Microphone active. Listening...",
            "system",
        )

        self.voice_thread = threading.Thread(
            target=self.voice_loop,
            daemon=True,
        )

        self.voice_thread.start()

    # ========================================================
    # STOP VOICE
    # ========================================================

    def stop_voice(self):

        self.voice_active = False

        self.voice_button.configure(
            text="🎤  START VOICE",
            bg=CYAN,
            fg=BG,
        )

        self.voice_status_label.configure(
            text="READY",
            fg=GREEN,
        )

        self.voice_state_label.configure(
            text="STANDBY",
            fg=TEXT,
        )

        self.set_status(
            "READY // AWAITING COMMAND",
            GREEN,
        )

        self.log_event(
            "Voice listening stopped.",
            "system",
        )

    # ========================================================
    # VOICE LOOP
    # ========================================================

    def voice_loop(self):

        while self.voice_active:

            try:

                self.event_queue.put(
                    (
                        "voice_state",
                        "listening",
                    )
                )

                text = listen()

                if not self.voice_active:
                    break

                if not text:

                    self.event_queue.put(
                        (
                            "log",
                            datetime.datetime.now().strftime(
                                "%H:%M:%S"
                            ),
                            "I didn't hear anything.",
                            "warning",
                        )
                    )

                    continue

                text = str(
                    text
                ).strip()

                if not text:
                    continue

                self.event_queue.put(
                    (
                        "voice_text",
                        text,
                    )
                )

                # --------------------------------------------
                # PROCESS VOICE COMMAND
                # --------------------------------------------

                self.event_queue.put(
                    (
                        "voice_state",
                        "understanding",
                    )
                )

                self.command_from_voice(
                    text
                )

                # Wait until command is finished

                while (
                    self.processing
                    and self.voice_active
                ):

                    time.sleep(
                        0.1
                    )

            except Exception as e:

                self.event_queue.put(
                    (
                        "error",
                        f"Voice input failed: {e}",
                        "",
                    )
                )

                time.sleep(
                    0.5
                )

    # ========================================================
    # VOICE COMMAND
    # ========================================================

    def command_from_voice(
        self,
        text,
    ):

        if not self.voice_active:
            return

        self.processing = True

        self.event_queue.put(
            (
                "voice_command",
                text,
            )
        )

        # Use same backend

        try:

            result = process_command(
                text
            )

            self.event_queue.put(
                (
                    "command_result",
                    text,
                    result,
                )
            )

        except Exception as e:

            self.event_queue.put(
                (
                    "error",
                    str(e),
                    traceback.format_exc(),
                )
            )

    # ========================================================
    # VOICE TEXT EVENT
    # ========================================================

    def handle_voice_text(
        self,
        text,
    ):

        self.log_event(
            f"YOU 🎙 > {text}",
            "you",
        )

        self.set_status(
            "UNDERSTANDING...",
            CYAN,
        )

        self.voice_state_label.configure(
            text="UNDERSTANDING",
            fg=CYAN,
        )

    # ========================================================
    # VOICE STATE
    # ========================================================

    def handle_voice_state(
        self,
        state,
    ):

        if state == "listening":

            self.set_status(
                "VOICE LISTENING",
                GREEN,
            )

            self.voice_state_label.configure(
                text="LISTENING",
                fg=GREEN,
            )

        elif state == "understanding":

            self.set_status(
                "UNDERSTANDING...",
                CYAN,
            )

            self.voice_state_label.configure(
                text="UNDERSTANDING",
                fg=CYAN,
            )

        elif state == "speaking":

            self.set_status(
                "SPEAKING...",
                BLUE,
            )

            self.voice_state_label.configure(
                text="SPEAKING",
                fg=BLUE,
            )

        elif state == "ready":

            if self.voice_active:

                self.set_status(
                    "VOICE READY",
                    GREEN,
                )

                self.voice_state_label.configure(
                    text="LISTENING",
                    fg=GREEN,
                )

            else:

                self.set_status(
                    "READY // AWAITING COMMAND",
                    GREEN,
                )

                self.voice_state_label.configure(
                    text="STANDBY",
                    fg=TEXT,
                )

    # ========================================================
    # ERROR
    # ========================================================

    def handle_error(
        self,
        message,
        details,
    ):

        self.processing = False

        self.send_button.configure(
            state="normal",
            bg=CYAN,
        )

        self.log_event(
            message,
            "warning",
        )

        self.set_status(
            "ERROR",
            RED,
        )

        self.root.after(
            1800,
            lambda: self.set_status(
                "READY // AWAITING COMMAND",
                GREEN,
            ),
        )

    # ========================================================
    # SYSTEM STATS
    # ========================================================

    def update_system_stats(self):

        try:

            if psutil:

                cpu = psutil.cpu_percent(
                    interval=None
                )

                ram = psutil.virtual_memory().percent

                disk = psutil.disk_usage(
                    "C:\\"
                ).percent

                self.last_cpu = cpu
                self.last_ram = ram
                self.last_disk = disk

                self.cpu_value.configure(
                    text=f"{cpu:.0f}%"
                )

                self.ram_value.configure(
                    text=f"{ram:.0f}%"
                )

                self.disk_value.configure(
                    text=f"{disk:.0f}%"
                )

                self.cpu_value.configure(
                    fg=self.metric_color(cpu)
                )

                self.ram_value.configure(
                    fg=self.metric_color(ram)
                )

                self.disk_value.configure(
                    fg=self.metric_color(disk)
                )

        except Exception:
            pass

        if self.running:

            self.root.after(
                1000,
                self.update_system_stats,
            )

    # ========================================================
    # METRIC COLOR
    # ========================================================

    def metric_color(
        self,
        value,
    ):

        if value >= 85:
            return RED

        if value >= 65:
            return ORANGE

        return CYAN

    # ========================================================
    # REACTOR ANIMATION
    # ========================================================

    def animate_reactor(self):

        if not self.running:
            return

        self.reactor_phase += 0.035

        self.pulse_phase += 0.06

        self.draw_reactor()

        self.root.after(
            30,
            self.animate_reactor,
        )

    # ========================================================
    # DRAW REACTOR
    # ========================================================

    def draw_reactor(self):

        canvas = self.reactor

        width = max(
            canvas.winfo_width(),
            400,
        )

        height = max(
            canvas.winfo_height(),
            300,
        )

        canvas.delete(
            "all"
        )

        cx = width / 2
        cy = height / 2 - 20

        # ----------------------------------------------------
        # BACKGROUND GRID
        # ----------------------------------------------------

        grid_size = 35

        for x in range(
            0,
            width,
            grid_size,
        ):

            canvas.create_line(
                x,
                0,
                x,
                height,
                fill="#091a28",
            )

        for y in range(
            0,
            height,
            grid_size,
        ):

            canvas.create_line(
                0,
                y,
                width,
                y,
                fill="#091a28",
            )

        # ----------------------------------------------------
        # RADAR CIRCLES
        # ----------------------------------------------------

        max_radius = min(
            width,
            height,
        ) * 0.36

        for i in range(
            6,
            0,
            -1,
        ):

            radius = max_radius * (
                i / 6
            )

            color = (
                "#0b2537"
                if i % 2
                else "#0d3044"
            )

            canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=color,
                width=1,
            )

        # ----------------------------------------------------
        # ROTATING RINGS
        # ----------------------------------------------------

        for ring in range(
            4
        ):

            radius = max_radius * (
                0.35 + ring * 0.16
            )

            angle = (
                self.reactor_phase
                * (
                    1
                    if ring % 2 == 0
                    else -1
                )
                + ring
            )

            start = (
                angle * 180 / math.pi
            )

            extent = (
                95
                if ring % 2 == 0
                else 130
            )

            canvas.create_arc(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                start=start,
                extent=extent,
                outline=CYAN,
                width=2,
            )

            canvas.create_arc(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                start=start + 180,
                extent=extent / 2,
                outline=BLUE,
                width=1,
            )

        # ----------------------------------------------------
        # OUTER MARKERS
        # ----------------------------------------------------

        for i in range(
            24
        ):

            angle = (
                i * math.pi * 2 / 24
                + self.reactor_phase
            )

            radius = max_radius * 0.92

            x1 = cx + math.cos(angle) * radius

            y1 = cy + math.sin(angle) * radius

            x2 = cx + math.cos(angle) * (
                radius + 7
            )

            y2 = cy + math.sin(angle) * (
                radius + 7
            )

            color = (
                CYAN
                if i % 3 == 0
                else "#17475d"
            )

            canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=color,
                width=2,
            )

        # ----------------------------------------------------
        # CORE GLOW
        # ----------------------------------------------------

        pulse = (
            math.sin(
                self.pulse_phase
            )
            + 1
        ) / 2

        core_radius = (
            max_radius * (
                0.20
                + pulse * 0.025
            )
        )

        for i in range(
            5,
            0,
            -1,
        ):

            radius = core_radius * (
                i / 4
            )

            color = (
                "#062a3c"
                if i > 2
                else "#07506c"
            )

            canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline="#00bddd",
                width=1,
            )

        # ----------------------------------------------------
        # CORE
        # ----------------------------------------------------

        inner = core_radius * 0.55

        canvas.create_oval(
            cx - inner,
            cy - inner,
            cx + inner,
            cy + inner,
            fill="#00b8d4",
            outline=WHITE,
            width=2,
        )

        # ----------------------------------------------------
        # CORE TEXT
        # ----------------------------------------------------

        canvas.create_text(
            cx,
            cy - 4,
            text="JARVIS",
            fill=BG,
            font=(
                FONT,
                15,
                "bold",
            ),
        )

        canvas.create_text(
            cx,
            cy + 18,
            text="AI CORE",
            fill="#073341",
            font=(
                FONT,
                7,
                "bold",
            ),
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        canvas.create_text(
            cx,
            height - 28,
            text=self.status,
            fill=CYAN,
            font=(
                "Consolas",
                9,
                "bold",
            ),
        )

        # ----------------------------------------------------
        # TELEMETRY LABELS
        # ----------------------------------------------------

        canvas.create_text(
            20,
            20,
            text="NEURAL CORE // ACTIVE",
            anchor="nw",
            fill=MUTED,
            font=(
                "Consolas",
                8,
            ),
        )

        canvas.create_text(
            width - 20,
            20,
            text=datetime.datetime.now().strftime(
                "%H:%M:%S"
            ),
            anchor="ne",
            fill=MUTED,
            font=(
                "Consolas",
                8,
            ),
        )

    # ========================================================
    # WAVEFORM
    # ========================================================

    def animate_waveform(self):

        if not self.running:
            return

        self.wave_phase += 0.2

        canvas = self.voice_meter

        canvas.delete(
            "all"
        )

        width = max(
            canvas.winfo_width(),
            150,
        )

        height = max(
            canvas.winfo_height(),
            50,
        )

        center = height / 2

        active = (
            self.voice_active
            or self.processing
            or self.speaking
        )

        for x in range(
            0,
            int(width),
            4,
        ):

            if active:

                value = (
                    math.sin(
                        self.wave_phase
                        + x * 0.08
                    )
                    * (
                        8
                        + 10
                        * math.sin(
                            self.wave_phase
                            * 0.7
                        )
                    )
                )

                value += random.uniform(
                    -3,
                    3,
                )

            else:

                value = math.sin(
                    self.wave_phase
                    + x * 0.05
                ) * 2

            y = center + value

            canvas.create_line(
                x,
                center,
                x,
                y,
                fill=(
                    CYAN
                    if active
                    else "#16465b"
                ),
                width=2,
            )

        self.root.after(
            50,
            self.animate_waveform,
        )

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self):

        self.running = False

        self.voice_active = False

        try:

            self.log_event(
                "JARVIS COMMAND CENTER OFFLINE",
                "system",
            )

        except Exception:
            pass

        self.root.after(
            100,
            self.root.destroy,
        )


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