import tkinter as tk
from tkinter import ttk
import threading
import queue
import time
import datetime
import platform
import os

# ============================================================
# OPTIONAL PSUTIL
# ============================================================

try:
    import psutil
except ImportError:
    psutil = None

# ============================================================
# OPTIONAL REQUESTS
# ============================================================

try:
    import requests
except ImportError:
    requests = None

# ============================================================
# JARVIS ENGINE
# ============================================================

try:
    from main import process_command, list_tools, OLLAMA_MODEL, OLLAMA_URL
except Exception as e:
    process_command = None
    OLLAMA_MODEL = "llama3.2:3b"
    OLLAMA_URL = "http://localhost:11434/api/generate"

    def list_tools():
        return {}

    IMPORT_ERROR = str(e)
else:
    IMPORT_ERROR = None


# ============================================================
# COLORS
# ============================================================

BG = "#050b14"
PANEL = "#081522"
PANEL_2 = "#0b1b2a"

CYAN = "#00e5ff"
CYAN_2 = "#00a8c6"

BLUE = "#1677ff"
BLUE_2 = "#0d47a1"

GREEN = "#00ff9d"
RED = "#ff426d"
YELLOW = "#ffd166"

WHITE = "#f4fbff"
TEXT = "#c9e7f2"
MUTED = "#658596"

BORDER = "#12384c"


# ============================================================
# CONSTANTS
# ============================================================

APP_TITLE = "JARVIS // COMMAND CENTER"
WINDOW_WIDTH = 1500
WINDOW_HEIGHT = 900

UI_QUEUE = queue.Queue()

OLLAMA_TIMEOUT = 2

RUNNING = True


# ============================================================
# SAFE TEXT
# ============================================================

def safe_text(value):
    if value is None:
        return ""

    return str(value)


# ============================================================
# DASHBOARD
# ============================================================

class JarvisDashboard:

    def __init__(self, root):

        self.root = root

        self.root.title(APP_TITLE)

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            1100,
            700,
        )

        self.root.configure(
            bg=BG
        )

        # ----------------------------------------------------
        # WINDOW
        # ----------------------------------------------------

        try:
            self.root.state("zoomed")
        except Exception:
            pass

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.command_running = False

        self.command_count = 0

        self.start_time = time.time()

        self.message_count = 0

        self.last_command = "System initialized."

        self.current_status = "READY"

        # ----------------------------------------------------
        # FONTS
        # ----------------------------------------------------

        self.font_title = (
            "Segoe UI",
            24,
            "bold",
        )

        self.font_header = (
            "Segoe UI",
            11,
            "bold",
        )

        self.font_normal = (
            "Segoe UI",
            10,
        )

        self.font_small = (
            "Segoe UI",
            9,
        )

        self.font_console = (
            "Consolas",
            10,
        )

        # ----------------------------------------------------
        # BUILD UI
        # ----------------------------------------------------

        self.build_style()

        self.build_header()

        self.build_main_area()

        self.build_command_bar()

        self.build_status_bar()

        # ----------------------------------------------------
        # EVENTS
        # ----------------------------------------------------

        self.root.bind(
            "<Return>",
            self.handle_enter,
        )

        self.root.bind(
            "<Control-l>",
            self.clear_console,
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.shutdown,
        )

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        self.write_system(
            "JARVIS COMMAND CENTER ONLINE"
        )

        self.write_system(
            f"Local AI: {OLLAMA_MODEL}"
        )

        self.write_system(
            f"Tools detected: {len(list_tools())}"
        )

        if IMPORT_ERROR:

            self.write_system(
                "WARNING: main.py import problem"
            )

            self.write_system(
                IMPORT_ERROR
            )

        # ----------------------------------------------------
        # BACKGROUND MONITORS
        # ----------------------------------------------------

        self.update_clock()

        self.update_system_stats()

        self.update_ollama_status()

        self.process_ui_queue()


    # ========================================================
    # STYLE
    # ========================================================

    def build_style(self):

        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )
        except Exception:
            pass

        style.configure(
            "TScrollbar",
            background=PANEL,
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=CYAN,
        )


    # ========================================================
    # HEADER
    # ========================================================

    def build_header(self):

        header = tk.Frame(
            self.root,
            bg=BG,
            height=90,
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(15, 5),
        )

        header.pack_propagate(
            False
        )

        # ----------------------------------------------------
        # LEFT
        # ----------------------------------------------------

        left = tk.Frame(
            header,
            bg=BG,
        )

        left.pack(
            side="left",
            fill="y",
        )

        title = tk.Label(
            left,
            text="JARVIS",
            font=(
                "Segoe UI",
                28,
                "bold",
            ),
            fg=CYAN,
            bg=BG,
        )

        title.pack(
            anchor="w"
        )

        subtitle = tk.Label(
            left,
            text="AI COMMAND CENTER // LOCAL INTELLIGENCE SYSTEM",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg=MUTED,
            bg=BG,
        )

        subtitle.pack(
            anchor="w"
        )

        # ----------------------------------------------------
        # RIGHT STATUS
        # ----------------------------------------------------

        right = tk.Frame(
            header,
            bg=BG,
        )

        right.pack(
            side="right",
            fill="y",
        )

        self.online_dot = tk.Label(
            right,
            text="●",
            font=(
                "Segoe UI",
                18,
            ),
            fg=GREEN,
            bg=BG,
        )

        self.online_dot.pack(
            side="left",
            padx=(0, 8),
        )

        self.online_label = tk.Label(
            right,
            text="SYSTEM ONLINE",
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
            fg=GREEN,
            bg=BG,
        )

        self.online_label.pack(
            side="left"
        )


    # ========================================================
    # MAIN AREA
    # ========================================================

    def build_main_area(self):

        main = tk.Frame(
            self.root,
            bg=BG,
        )

        main.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=8,
        )

        # ----------------------------------------------------
        # LEFT PANEL
        # ----------------------------------------------------

        left = tk.Frame(
            main,
            bg=BG,
            width=270,
        )

        left.pack(
            side="left",
            fill="y",
            padx=(0, 10),
        )

        left.pack_propagate(
            False
        )

        self.build_system_panel(
            left
        )

        self.build_ai_panel(
            left
        )

        # ----------------------------------------------------
        # CENTER
        # ----------------------------------------------------

        center = tk.Frame(
            main,
            bg=BG,
        )

        center.pack(
            side="left",
            fill="both",
            expand=True,
        )

        self.build_core_panel(
            center
        )

        self.build_console_panel(
            center
        )

        # ----------------------------------------------------
        # RIGHT
        # ----------------------------------------------------

        right = tk.Frame(
            main,
            bg=BG,
            width=300,
        )

        right.pack(
            side="right",
            fill="y",
            padx=(10, 0),
        )

        right.pack_propagate(
            False
        )

        self.build_task_panel(
            right
        )

        self.build_info_panel(
            right
        )


    # ========================================================
    # SYSTEM PANEL
    # ========================================================

    def build_system_panel(self, parent):

        panel = self.panel(
            parent,
            "SYSTEM TELEMETRY",
        )

        panel.pack(
            fill="x",
            pady=(0, 10),
        )

        self.cpu_value = self.metric(
            panel,
            "CPU",
            CYAN,
        )

        self.ram_value = self.metric(
            panel,
            "MEMORY",
            GREEN,
        )

        self.disk_value = self.metric(
            panel,
            "DISK",
            YELLOW,
        )

        self.system_value = self.metric(
            panel,
            "OS",
            WHITE,
        )


    # ========================================================
    # AI PANEL
    # ========================================================

    def build_ai_panel(self, parent):

        panel = self.panel(
            parent,
            "AI CORE",
        )

        panel.pack(
            fill="x",
            pady=(0, 10),
        )

        self.ai_dot = tk.Label(
            panel,
            text="●",
            font=(
                "Segoe UI",
                26,
            ),
            fg=GREEN,
            bg=PANEL,
        )

        self.ai_dot.pack(
            pady=(8, 0)
        )

        self.ai_status = tk.Label(
            panel,
            text="OLLAMA CHECKING",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg=TEXT,
            bg=PANEL,
        )

        self.ai_status.pack(
            pady=(0, 10)
        )

        self.model_label = tk.Label(
            panel,
            text=f"MODEL\n{OLLAMA_MODEL}",
            font=(
                "Consolas",
                9,
            ),
            fg=CYAN,
            bg=PANEL,
            justify="center",
        )

        self.model_label.pack(
            pady=(0, 12)
        )


    # ========================================================
    # CORE PANEL
    # ========================================================

    def build_core_panel(self, parent):

        panel = tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        panel.pack(
            fill="x",
            pady=(0, 10),
        )

        # ----------------------------------------------------
        # CORE CANVAS
        # ----------------------------------------------------

        self.core_canvas = tk.Canvas(
            panel,
            height=210,
            bg=PANEL,
            highlightthickness=0,
        )

        self.core_canvas.pack(
            fill="x"
        )

        self.core_angle = 0

        self.draw_core()

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.core_status = tk.Label(
            panel,
            text="READY // AWAITING COMMAND",
            font=(
                "Consolas",
                11,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL,
        )

        self.core_status.pack(
            pady=(0, 12)
        )


    # ========================================================
    # DRAW 3D CORE
    # ========================================================

    def draw_core(self):

        canvas = self.core_canvas

        canvas.delete(
            "core"
        )

        width = max(
            canvas.winfo_width(),
            600,
        )

        height = 210

        cx = width // 2
        cy = 100

        # ----------------------------------------------------
        # GLOW RINGS
        # ----------------------------------------------------

        rings = [
            (90, "#082b3d"),
            (75, "#093e55"),
            (60, "#07516d"),
            (45, "#007b9f"),
        ]

        for radius, color in rings:

            canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=color,
                width=2,
                tags="core",
            )

        # ----------------------------------------------------
        # ROTATING ORBIT
        # ----------------------------------------------------

        import math

        for i in range(3):

            angle = (
                self.core_angle
                + i * 120
            )

            radians = math.radians(
                angle
            )

            x = cx + (
                math.cos(radians)
                * 75
            )

            y = cy + (
                math.sin(radians)
                * 28
            )

            canvas.create_oval(
                x - 6,
                y - 6,
                x + 6,
                y + 6,
                fill=CYAN,
                outline="",
                tags="core",
            )

        # ----------------------------------------------------
        # CORE
        # ----------------------------------------------------

        canvas.create_oval(
            cx - 32,
            cy - 32,
            cx + 32,
            cy + 32,
            fill="#063b52",
            outline=CYAN,
            width=2,
            tags="core",
        )

        canvas.create_oval(
            cx - 20,
            cy - 20,
            cx + 20,
            cy + 20,
            fill="#087c9d",
            outline="#67efff",
            width=2,
            tags="core",
        )

        canvas.create_oval(
            cx - 8,
            cy - 8,
            cx + 8,
            cy + 8,
            fill=WHITE,
            outline="",
            tags="core",
        )

        # ----------------------------------------------------
        # LABEL
        # ----------------------------------------------------

        canvas.create_text(
            cx,
            165,
            text="J A R V I S",
            font=(
                "Consolas",
                12,
                "bold",
            ),
            fill=CYAN,
            tags="core",
        )

        self.core_angle += 4

        self.root.after(
            50,
            self.draw_core,
        )


    # ========================================================
    # CONSOLE
    # ========================================================

    def build_console_panel(self, parent):

        panel = self.panel(
            parent,
            "COMMAND / CONVERSATION",
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        console_frame = tk.Frame(
            panel,
            bg=PANEL,
        )

        console_frame.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8,
        )

        self.console = tk.Text(
            console_frame,
            bg="#03080e",
            fg=TEXT,
            insertbackground=CYAN,
            selectbackground="#144b66",
            selectforeground=WHITE,
            font=self.font_console,
            relief="flat",
            borderwidth=0,
            wrap="word",
            padx=12,
            pady=12,
            state="disabled",
        )

        scrollbar = ttk.Scrollbar(
            console_frame,
            orient="vertical",
            command=self.console.yview,
        )

        self.console.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.console.pack(
            side="left",
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # TAGS
        # ----------------------------------------------------

        self.console.tag_configure(
            "system",
            foreground=MUTED,
        )

        self.console.tag_configure(
            "you",
            foreground=CYAN,
            font=(
                "Consolas",
                10,
                "bold",
            ),
        )

        self.console.tag_configure(
            "jarvis",
            foreground=WHITE,
        )

        self.console.tag_configure(
            "tool",
            foreground=GREEN,
        )

        self.console.tag_configure(
            "error",
            foreground=RED,
        )

        self.console.tag_configure(
            "time",
            foreground="#52788a",
        )


    # ========================================================
    # TASK PANEL
    # ========================================================

    def build_task_panel(self, parent):

        panel = self.panel(
            parent,
            "TASK MATRIX",
        )

        panel.pack(
            fill="both",
            expand=True,
            pady=(0, 10),
        )

        self.task_container = tk.Frame(
            panel,
            bg=PANEL,
        )

        self.task_container.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8,
        )

        self.task_empty = tk.Label(
            self.task_container,
            text=(
                "NO ACTIVE TASKS\n\n"
                "JARVIS IS READY"
            ),
            font=(
                "Consolas",
                9,
            ),
            fg=MUTED,
            bg=PANEL,
            justify="center",
        )

        self.task_empty.pack(
            expand=True
        )


    # ========================================================
    # INFO PANEL
    # ========================================================

    def build_info_panel(self, parent):

        panel = self.panel(
            parent,
            "SESSION",
        )

        panel.pack(
            fill="x",
        )

        self.clock_label = tk.Label(
            panel,
            text="--:--:--",
            font=(
                "Consolas",
                16,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL,
        )

        self.clock_label.pack(
            pady=(8, 2)
        )

        self.date_label = tk.Label(
            panel,
            text="",
            font=self.font_small,
            fg=MUTED,
            bg=PANEL,
        )

        self.date_label.pack(
            pady=(0, 8)
        )

        self.commands_label = tk.Label(
            panel,
            text="COMMANDS: 0",
            font=self.font_small,
            fg=TEXT,
            bg=PANEL,
        )

        self.commands_label.pack(
            pady=2
        )

        self.tools_label = tk.Label(
            panel,
            text=f"TOOLS: {len(list_tools())}",
            font=self.font_small,
            fg=TEXT,
            bg=PANEL,
        )

        self.tools_label.pack(
            pady=(2, 10)
        )


    # ========================================================
    # COMMAND BAR
    # ========================================================

    def build_command_bar(self):

        outer = tk.Frame(
            self.root,
            bg=BG,
        )

        outer.pack(
            fill="x",
            padx=18,
            pady=(8, 5),
        )

        # ----------------------------------------------------
        # INPUT PANEL
        # ----------------------------------------------------

        input_panel = tk.Frame(
            outer,
            bg=PANEL_2,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        input_panel.pack(
            fill="x",
        )

        # ----------------------------------------------------
        # PROMPT
        # ----------------------------------------------------

        prompt = tk.Label(
            input_panel,
            text="YOU >",
            font=(
                "Consolas",
                11,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL_2,
        )

        prompt.pack(
            side="left",
            padx=(15, 8),
        )

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        self.command_entry = tk.Entry(
            input_panel,
            bg="#0d1f2e",
            fg=WHITE,
            insertbackground=CYAN,
            selectbackground="#1a5c7a",
            selectforeground=WHITE,
            font=(
                "Segoe UI",
                12,
            ),
            relief="flat",
            borderwidth=0,
        )

        self.command_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=12,
            padx=5,
        )

        self.command_entry.focus_set()

        self.command_entry.bind(
            "<Return>",
            self.handle_enter,
        )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        self.send_button = tk.Button(
            input_panel,
            text="SEND  ➤",
            command=self.send_command,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            fg="#001018",
            bg=CYAN,
            activeforeground="#001018",
            activebackground="#70f4ff",
            relief="flat",
            cursor="hand2",
            padx=20,
            pady=10,
            borderwidth=0,
        )

        self.send_button.pack(
            side="right",
            padx=8,
            pady=6,
        )

        # ----------------------------------------------------
        # CLEAR
        # ----------------------------------------------------

        clear_button = tk.Button(
            input_panel,
            text="CLEAR",
            command=self.clear_console,
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg=TEXT,
            bg="#102635",
            activeforeground=WHITE,
            activebackground="#173b50",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=10,
            borderwidth=0,
        )

        clear_button.pack(
            side="right",
            padx=(0, 4),
            pady=6,
        )


    # ========================================================
    # STATUS BAR
    # ========================================================

    def build_status_bar(self):

        bar = tk.Frame(
            self.root,
            bg="#02070c",
            height=28,
        )

        bar.pack(
            fill="x",
            padx=18,
            pady=(0, 10),
        )

        bar.pack_propagate(
            False
        )

        self.status_label = tk.Label(
            bar,
            text="● READY",
            font=(
                "Consolas",
                9,
                "bold",
            ),
            fg=GREEN,
            bg="#02070c",
            anchor="w",
        )

        self.status_label.pack(
            side="left",
            padx=8,
        )

        self.connection_label = tk.Label(
            bar,
            text="LOCAL ENGINE",
            font=(
                "Consolas",
                9,
            ),
            fg=MUTED,
            bg="#02070c",
            anchor="e",
        )

        self.connection_label.pack(
            side="right",
            padx=8,
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
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        header = tk.Label(
            outer,
            text=f"  {title}",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
            fg=CYAN,
            bg=PANEL,
            anchor="w",
        )

        header.pack(
            fill="x",
            padx=8,
            pady=(8, 5),
        )

        return outer


    # ========================================================
    # METRIC
    # ========================================================

    def metric(
        self,
        parent,
        name,
        color,
    ):

        row = tk.Frame(
            parent,
            bg=PANEL,
        )

        row.pack(
            fill="x",
            padx=12,
            pady=5,
        )

        label = tk.Label(
            row,
            text=name,
            font=self.font_small,
            fg=MUTED,
            bg=PANEL,
        )

        label.pack(
            side="left"
        )

        value = tk.Label(
            row,
            text="--",
            font=(
                "Consolas",
                9,
                "bold",
            ),
            fg=color,
            bg=PANEL,
        )

        value.pack(
            side="right"
        )

        return value


    # ========================================================
    # CONSOLE WRITE
    # ========================================================

    def write_console(
        self,
        message,
        tag="jarvis",
    ):

        message = safe_text(
            message
        )

        if not message:
            return

        timestamp = datetime.datetime.now().strftime(
            "%H:%M:%S"
        )

        self.console.configure(
            state="normal"
        )

        self.console.insert(
            "end",
            f"[{timestamp}] ",
            "time",
        )

        self.console.insert(
            "end",
            message + "\n",
            tag,
        )

        self.console.see(
            "end"
        )

        self.console.configure(
            state="disabled"
        )

        self.message_count += 1


    # ========================================================
    # SYSTEM MESSAGE
    # ========================================================

    def write_system(
        self,
        message,
    ):

        self.write_console(
            message,
            "system",
        )


    # ========================================================
    # USER MESSAGE
    # ========================================================

    def write_user(
        self,
        message,
    ):

        self.write_console(
            "YOU > " + message,
            "you",
        )


    # ========================================================
    # JARVIS MESSAGE
    # ========================================================

    def write_jarvis(
        self,
        message,
    ):

        self.write_console(
            "JARVIS > " + message,
            "jarvis",
        )


    # ========================================================
    # TOOL MESSAGE
    # ========================================================

    def write_tool(
        self,
        message,
    ):

        self.write_console(
            message,
            "tool",
        )


    # ========================================================
    # ERROR
    # ========================================================

    def write_error(
        self,
        message,
    ):

        self.write_console(
            message,
            "error",
        )


    # ========================================================
    # SEND COMMAND
    # ========================================================

    def handle_enter(
        self,
        event=None,
    ):

        self.send_command()

        return "break"


    def send_command(self):

        # ----------------------------------------------------
        # DO NOT SEND WHITESPACE
        # ----------------------------------------------------

        text = self.command_entry.get().strip()

        if not text:
            return

        # ----------------------------------------------------
        # DON'T STACK COMMANDS
        # ----------------------------------------------------

        if self.command_running:

            self.write_error(
                "JARVIS > A command is already running. Please wait."
            )

            return

        # ----------------------------------------------------
        # CLEAR INPUT IMMEDIATELY
        # ----------------------------------------------------

        self.command_entry.delete(
            0,
            "end",
        )

        self.command_count += 1

        self.commands_label.config(
            text=f"COMMANDS: {self.command_count}"
        )

        self.last_command = text

        self.write_user(
            text
        )

        self.set_status(
            "PROCESSING",
            YELLOW,
        )

        self.core_status.config(
            text="PROCESSING // JARVIS THINKING"
        )

        self.command_running = True

        self.send_button.config(
            state="disabled",
            text="RUNNING...",
        )

        self.clear_tasks()

        # ----------------------------------------------------
        # RUN ENGINE IN BACKGROUND
        # ----------------------------------------------------

        thread = threading.Thread(
            target=self.run_command,
            args=(text,),
            daemon=True,
        )

        thread.start()


    # ========================================================
    # RUN COMMAND
    # ========================================================

    def run_command(
        self,
        text,
    ):

        if process_command is None:

            self.ui_put(
                (
                    "error",
                    "JARVIS ENGINE COULD NOT BE LOADED.\n"
                    + safe_text(IMPORT_ERROR),
                )
            )

            self.ui_put(
                (
                    "complete",
                    None,
                )
            )

            return

        try:

            result = process_command(
                text
            )

            self.ui_put(
                (
                    "result",
                    result,
                )
            )

        except Exception as e:

            self.ui_put(
                (
                    "error",
                    f"ENGINE ERROR: {e}",
                )
            )

        finally:

            self.ui_put(
                (
                    "complete",
                    None,
                )
            )


    # ========================================================
    # UI QUEUE
    # ========================================================

    def ui_put(
        self,
        item,
    ):

        UI_QUEUE.put(
            item
        )


    def process_ui_queue(self):

        try:

            while True:

                kind, data = UI_QUEUE.get_nowait()

                if kind == "result":

                    self.handle_result(
                        data
                    )

                elif kind == "error":

                    self.write_error(
                        data
                    )

                    self.set_status(
                        "ERROR",
                        RED,
                    )

                elif kind == "complete":

                    self.command_running = False

                    self.send_button.config(
                        state="normal",
                        text="SEND  ➤",
                    )

                    self.set_status(
                        "READY",
                        GREEN,
                    )

                    self.core_status.config(
                        text="READY // AWAITING COMMAND"
                    )

        except queue.Empty:
            pass

        self.root.after(
            50,
            self.process_ui_queue,
        )


    # ========================================================
    # RESULT
    # ========================================================

    def handle_result(
        self,
        result,
    ):

        if not isinstance(
            result,
            dict,
        ):

            self.write_jarvis(
                safe_text(result)
            )

            return

        message = result.get(
            "message"
        )

        if not message:
            return

        # ----------------------------------------------------
        # MULTI TASK
        # ----------------------------------------------------

        if "\n" in message:

            lines = [
                x.strip()
                for x in message.splitlines()
                if x.strip()
            ]

            self.write_jarvis(
                "MULTI-TASK EXECUTION COMPLETE"
            )

            for line in lines:

                self.write_tool(
                    "  ● " + line
                )

            self.show_completed_tasks(
                lines
            )

        else:

            self.write_jarvis(
                message
            )

            self.show_completed_tasks(
                [message]
            )


    # ========================================================
    # TASK DISPLAY
    # ========================================================

    def clear_tasks(self):

        for child in self.task_container.winfo_children():

            child.destroy()

        self.task_empty = tk.Label(
            self.task_container,
            text=(
                "EXECUTING COMMAND...\n\n"
                "WAITING FOR ENGINE"
            ),
            font=(
                "Consolas",
                9,
            ),
            fg=YELLOW,
            bg=PANEL,
            justify="center",
        )

        self.task_empty.pack(
            expand=True
        )


    def show_completed_tasks(
        self,
        lines,
    ):

        for child in self.task_container.winfo_children():

            child.destroy()

        title = tk.Label(
            self.task_container,
            text="EXECUTION COMPLETE",
            font=(
                "Consolas",
                9,
                "bold",
            ),
            fg=GREEN,
            bg=PANEL,
        )

        title.pack(
            pady=(5, 12)
        )

        for line in lines:

            card = tk.Frame(
                self.task_container,
                bg="#0d2534",
                highlightbackground="#16445b",
                highlightthickness=1,
            )

            card.pack(
                fill="x",
                padx=4,
                pady=4,
            )

            dot = tk.Label(
                card,
                text="●",
                font=(
                    "Segoe UI",
                    12,
                ),
                fg=GREEN,
                bg="#0d2534",
            )

            dot.pack(
                side="left",
                padx=8,
            )

            label = tk.Label(
                card,
                text=line,
                font=(
                    "Segoe UI",
                    9,
                ),
                fg=TEXT,
                bg="#0d2534",
                anchor="w",
                justify="left",
                wraplength=220,
            )

            label.pack(
                side="left",
                fill="x",
                expand=True,
                pady=8,
                padx=(0, 8),
            )


    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        status,
        color,
    ):

        self.current_status = status

        self.status_label.config(
            text=f"● {status}",
            fg=color,
        )


    # ========================================================
    # CLOCK
    # ========================================================

    def update_clock(self):

        now = datetime.datetime.now()

        self.clock_label.config(
            text=now.strftime(
                "%H:%M:%S"
            )
        )

        self.date_label.config(
            text=now.strftime(
                "%A // %d %B %Y"
            )
        )

        self.root.after(
            1000,
            self.update_clock,
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
                    os.path.abspath(
                        os.sep
                    )
                ).percent

                self.cpu_value.config(
                    text=f"{cpu:.0f}%"
                )

                self.ram_value.config(
                    text=f"{ram:.0f}%"
                )

                self.disk_value.config(
                    text=f"{disk:.0f}%"
                )

            else:

                self.cpu_value.config(
                    text="N/A"
                )

                self.ram_value.config(
                    text="N/A"
                )

                self.disk_value.config(
                    text="N/A"
                )

            self.system_value.config(
                text=platform.system()
                + " "
                + platform.release()
            )

        except Exception:

            pass

        self.root.after(
            1500,
            self.update_system_stats,
        )


    # ========================================================
    # OLLAMA STATUS
    # ========================================================

    def update_ollama_status(self):

        thread = threading.Thread(
            target=self.check_ollama,
            daemon=True,
        )

        thread.start()

        self.root.after(
            5000,
            self.update_ollama_status,
        )


    def check_ollama(self):

        if requests is None:

            self.ui_put(
                (
                    "ollama",
                    False,
                )
            )

            return

        try:

            # Ollama root endpoint

            base_url = OLLAMA_URL.split(
                "/api/"
            )[0]

            response = requests.get(
                base_url,
                timeout=OLLAMA_TIMEOUT,
            )

            online = (
                response.status_code == 200
            )

            self.ui_put(
                (
                    "ollama",
                    online,
                )
            )

        except Exception:

            self.ui_put(
                (
                    "ollama",
                    False,
                )
            )

        # ----------------------------------------------------
        # OLLAMA UI UPDATE
        # ----------------------------------------------------

        # handled immediately below by queue


    # ========================================================
    # OVERRIDE QUEUE HANDLER SUPPORT
    # ========================================================


    # ========================================================
    # CLEAR CONSOLE
    # ========================================================

    def clear_console(
        self,
        event=None,
    ):

        self.console.configure(
            state="normal"
        )

        self.console.delete(
            "1.0",
            "end"
        )

        self.console.configure(
            state="disabled"
        )

        self.write_system(
            "CONSOLE CLEARED"
        )

        return "break"


    # ========================================================
    # SHUTDOWN
    # ========================================================

    def shutdown(self):

        global RUNNING

        RUNNING = False

        self.root.destroy()


# ============================================================
# PATCH QUEUE HANDLER FOR OLLAMA
# ============================================================

_original_process_ui_queue = JarvisDashboard.process_ui_queue


def enhanced_process_ui_queue(self):

    try:

        while True:

            kind, data = UI_QUEUE.get_nowait()

            if kind == "ollama":

                if data:

                    self.ai_dot.config(
                        fg=GREEN
                    )

                    self.ai_status.config(
                        text="OLLAMA ONLINE",
                        fg=GREEN,
                    )

                    self.connection_label.config(
                        text="OLLAMA // ONLINE",
                        fg=GREEN,
                    )

                else:

                    self.ai_dot.config(
                        fg=RED
                    )

                    self.ai_status.config(
                        text="OLLAMA OFFLINE",
                        fg=RED,
                    )

                    self.connection_label.config(
                        text="OLLAMA // OFFLINE",
                        fg=RED,
                    )

                continue

            if kind == "result":

                self.handle_result(
                    data
                )

                continue

            if kind == "error":

                self.write_error(
                    data
                )

                self.set_status(
                    "ERROR",
                    RED,
                )

                continue

            if kind == "complete":

                self.command_running = False

                self.send_button.config(
                    state="normal",
                    text="SEND  ➤",
                )

                self.set_status(
                    "READY",
                    GREEN,
                )

                self.core_status.config(
                    text="READY // AWAITING COMMAND"
                )

                continue

    except queue.Empty:

        pass

    self.root.after(
        50,
        self.process_ui_queue,
    )


JarvisDashboard.process_ui_queue = enhanced_process_ui_queue


# ============================================================
# START
# ============================================================

def main():

    root = tk.Tk()

    app = JarvisDashboard(
        root
    )

    root.mainloop()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()