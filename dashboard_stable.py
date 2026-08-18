import tkinter as tk
from tkinter import messagebox
import threading
import time
import platform
import sys
import psutil
from datetime import datetime

# ============================================================
# JARVIS DASHBOARD
# 3D / HUD STYLE COMMAND CENTER
# ============================================================

APP_TITLE = "JARVIS AI COMMAND CENTER"
BG = "#050912"
BG2 = "#08111F"
PANEL = "#0B1422"
PANEL2 = "#0E1A2B"
CARD = "#101D30"

CYAN = "#00E5FF"
CYAN2 = "#00B8D9"
BLUE = "#1677FF"
GREEN = "#00FF9D"
RED = "#FF426D"
YELLOW = "#FFD166"
WHITE = "#F4FBFF"
TEXT = "#C7D9E8"
MUTED = "#71869C"
BORDER = "#17304A"

FONT = "Segoe UI"
MONO = "Consolas"


# ============================================================
# SAFE MAIN IMPORT
# ============================================================

try:
    import main as jarvis_main
except Exception as e:
    jarvis_main = None
    MAIN_IMPORT_ERROR = str(e)


# ============================================================
# SAFE VOICE CHECK
# ============================================================

def voice_available():
    """
    Dashboard must never assume that a variable called
    'speak' exists.

    This fixes:
        name 'speak' is not defined
    """

    if jarvis_main is None:
        return False

    return getattr(
        jarvis_main,
        "speak",
        None
    ) is not None


# ============================================================
# MAIN WINDOW
# ============================================================

root = tk.Tk()

root.title(APP_TITLE)

root.geometry("1450x850")
root.minsize(1150, 700)

root.configure(
    bg=BG
)


# ============================================================
# WINDOW ICON / STYLE
# ============================================================

try:
    root.iconname("JARVIS")
except Exception:
    pass


# ============================================================
# STATE
# ============================================================

command_running = False
start_time = time.time()

history = []


# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def percent_color(value):
    if value >= 90:
        return RED

    if value >= 70:
        return YELLOW

    return GREEN


def format_uptime(seconds):
    seconds = int(seconds)

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60

    return (
        f"{days}d "
        f"{hours:02d}h "
        f"{minutes:02d}m"
    )


# ============================================================
# ROOT GRID
# ============================================================

root.grid_rowconfigure(
    1,
    weight=1
)

root.grid_columnconfigure(
    0,
    weight=1
)


# ============================================================
# TOP BAR
# ============================================================

top = tk.Frame(
    root,
    bg=BG2,
    height=85,
)

top.grid(
    row=0,
    column=0,
    sticky="ew"
)

top.grid_propagate(False)


# Accent line

accent = tk.Frame(
    top,
    bg=CYAN,
    height=3
)

accent.pack(
    side="top",
    fill="x"
)


# Logo

logo = tk.Label(
    top,
    text="J A R V I S",
    font=(
        FONT,
        27,
        "bold"
    ),
    fg=CYAN,
    bg=BG2,
)

logo.pack(
    side="left",
    padx=(35, 20),
    pady=15
)


subtitle = tk.Label(
    top,
    text="LOCAL AI COMMAND CENTER",
    font=(
        FONT,
        10,
        "bold"
    ),
    fg=MUTED,
    bg=BG2,
)

subtitle.pack(
    side="left",
    pady=18
)


# Online indicator

status_frame = tk.Frame(
    top,
    bg=BG2
)

status_frame.pack(
    side="right",
    padx=35
)


status_dot = tk.Label(
    status_frame,
    text="●",
    font=(
        FONT,
        16,
        "bold"
    ),
    fg=GREEN,
    bg=BG2
)

status_dot.pack(
    side="left",
    padx=(0, 7)
)


status_label = tk.Label(
    status_frame,
    text="ONLINE",
    font=(
        FONT,
        11,
        "bold"
    ),
    fg=GREEN,
    bg=BG2
)

status_label.pack(
    side="left"
)


# ============================================================
# MAIN CONTENT
# ============================================================

content = tk.Frame(
    root,
    bg=BG
)

content.grid(
    row=1,
    column=0,
    sticky="nsew",
    padx=18,
    pady=15
)

content.grid_rowconfigure(
    0,
    weight=1
)

content.grid_columnconfigure(
    1,
    weight=1
)

content.grid_columnconfigure(
    2,
    weight=0
)


# ============================================================
# LEFT SYSTEM PANEL
# ============================================================

left = tk.Frame(
    content,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

left.grid(
    row=0,
    column=0,
    sticky="nsew",
    padx=(0, 12)
)

left.configure(
    width=285
)

left.grid_propagate(False)


tk.Label(
    left,
    text="SYSTEM CORE",
    font=(
        FONT,
        14,
        "bold"
    ),
    fg=CYAN,
    bg=PANEL
).pack(
    pady=(25, 20)
)


# ============================================================
# SYSTEM METRIC CREATOR
# ============================================================

def create_metric(parent, title):

    frame = tk.Frame(
        parent,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1
    )

    frame.pack(
        fill="x",
        padx=18,
        pady=6
    )

    title_label = tk.Label(
        frame,
        text=title,
        font=(
            FONT,
            9,
            "bold"
        ),
        fg=MUTED,
        bg=CARD
    )

    title_label.pack(
        anchor="w",
        padx=12,
        pady=(10, 2)
    )

    value_label = tk.Label(
        frame,
        text="--",
        font=(
            FONT,
            14,
            "bold"
        ),
        fg=GREEN,
        bg=CARD
    )

    value_label.pack(
        anchor="w",
        padx=12,
        pady=(0, 10)
    )

    return value_label


cpu_value = create_metric(
    left,
    "CPU"
)

ram_value = create_metric(
    left,
    "RAM"
)

disk_value = create_metric(
    left,
    "DISK"
)

python_value = create_metric(
    left,
    "PYTHON"
)

os_value = create_metric(
    left,
    "OPERATING SYSTEM"
)

ai_value = create_metric(
    left,
    "LOCAL AI"
)


# ============================================================
# MEMORY SECTION
# ============================================================

tk.Frame(
    left,
    bg=BORDER,
    height=1
).pack(
    fill="x",
    padx=18,
    pady=(20, 15)
)


tk.Label(
    left,
    text="MEMORY",
    font=(
        FONT,
        13,
        "bold"
    ),
    fg=CYAN,
    bg=PANEL
).pack(
    pady=(0, 10)
)


def left_button(
    text,
    command,
    color=CARD
):

    btn = tk.Button(
        left,
        text=text,
        command=command,
        font=(
            FONT,
            9,
            "bold"
        ),
        fg=WHITE,
        bg=color,
        activeforeground=WHITE,
        activebackground=CYAN2,
        relief="flat",
        bd=0,
        cursor="hand2",
        height=2
    )

    btn.pack(
        fill="x",
        padx=18,
        pady=5
    )

    return btn


# ============================================================
# CENTER PANEL
# ============================================================

center = tk.Frame(
    content,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1
)

center.grid(
    row=0,
    column=1,
    sticky="nsew",
    padx=(0, 12)
)

center.grid_rowconfigure(
    1,
    weight=1
)

center.grid_columnconfigure(
    0,
    weight=1
)


# ============================================================
# CENTER HEADER
# ============================================================

center_header = tk.Frame(
    center,
    bg=PANEL
)

center_header.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=20,
    pady=(20, 10)
)


tk.Label(
    center_header,
    text="COMMAND CONSOLE",
    font=(
        FONT,
        15,
        "bold"
    ),
    fg=CYAN,
    bg=PANEL
).pack(
    side="left"
)


live_label = tk.Label(
    center_header,
    text="● LIVE",
    font=(
        FONT,
        9,
        "bold"
    ),
    fg=GREEN,
    bg=PANEL
)

live_label.pack(
    side="right"
)


# ============================================================
# COMMAND CONSOLE
# ============================================================

console_frame = tk.Frame(
    center,
    bg="#03070D",
    highlightbackground="#173B59",
    highlightthickness=1
)

console_frame.grid(
    row=1,
    column=0,
    sticky="nsew",
    padx=20,
    pady=(0, 10)
)


console_frame.grid_rowconfigure(
    0,
    weight=1
)

console_frame.grid_columnconfigure(
    0,
    weight=1
)


console = tk.Text(
    console_frame,
    bg="#03070D",
    fg=WHITE,
    insertbackground=CYAN,
    selectbackground="#155B75",
    selectforeground=WHITE,
    font=(
        MONO,
        10
    ),
    relief="flat",
    bd=0,
    wrap="word",
    padx=15,
    pady=15
)

console.grid(
    row=0,
    column=0,
    sticky="nsew"
)


scrollbar = tk.Scrollbar(
    console_frame,
    command=console.yview
)

scrollbar.grid(
    row=0,
    column=1,
    sticky="ns"
)

console.configure(
    yscrollcommand=scrollbar.set
)


console.tag_configure(
    "system",
    foreground=CYAN
)

console.tag_configure(
    "user",
    foreground=WHITE
)

console.tag_configure(
    "jarvis",
    foreground=GREEN
)

console.tag_configure(
    "error",
    foreground=RED
)

console.tag_configure(
    "muted",
    foreground=MUTED
)


# ============================================================
# LOGGING
# ============================================================

def log(message, tag="jarvis"):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    console.insert(
        "end",
        f"[{timestamp}] ",
        "muted"
    )

    console.insert(
        "end",
        str(message) + "\n",
        tag
    )

    console.see(
        "end"
    )


# ============================================================
# INPUT AREA
# ============================================================

input_outer = tk.Frame(
    center,
    bg=PANEL
)

input_outer.grid(
    row=2,
    column=0,
    sticky="ew",
    padx=20,
    pady=(0, 20)
)

input_outer.grid_columnconfigure(
    0,
    weight=1
)


# IMPORTANT:
# White text fixes the black-font problem.

command_entry = tk.Entry(
    input_outer,
    bg="#091421",
    fg=WHITE,
    insertbackground=CYAN,
    selectbackground="#14516A",
    selectforeground=WHITE,
    font=(
        FONT,
        11
    ),
    relief="flat",
    bd=0
)

command_entry.grid(
    row=0,
    column=0,
    sticky="ew",
    ipady=12,
    padx=(0, 10)
)


send_button = tk.Button(
    input_outer,
    text="SEND",
    command=lambda: send_command(),
    font=(
        FONT,
        10,
        "bold"
    ),
    fg=WHITE,
    bg="#087A9C",
    activeforeground=WHITE,
    activebackground="#00A9D1",
    relief="flat",
    bd=0,
    cursor="hand2",
    width=10
)

send_button.grid(
    row=0,
    column=1,
    ipady=8
)


# ============================================================
# RIGHT TOOLS
# ============================================================

right = tk.Frame(
    content,
    bg=PANEL,
    highlightbackground=BORDER,
    highlightthickness=1,
    width=235
)

right.grid(
    row=0,
    column=2,
    sticky="nsew"
)

right.grid_propagate(False)


tk.Label(
    right,
    text="TOOLS",
    font=(
        FONT,
        14,
        "bold"
    ),
    fg=CYAN,
    bg=PANEL
).pack(
    pady=(25, 15)
)


# ============================================================
# TOOL BUTTON
# ============================================================

def tool_button(
    title,
    command_text
):

    def run():

        command_entry.delete(
            0,
            "end"
        )

        command_entry.insert(
            0,
            command_text
        )

        send_command()

    btn = tk.Button(
        right,
        text=title,
        command=run,
        font=(
            FONT,
            9,
            "bold"
        ),
        fg=WHITE,
        bg=CARD,
        activeforeground=WHITE,
        activebackground="#135D76",
        relief="flat",
        bd=0,
        cursor="hand2",
        height=2
    )

    btn.pack(
        fill="x",
        padx=18,
        pady=5
    )

    return btn


tool_button(
    "OPEN NOTEPAD",
    "open notepad"
)

tool_button(
    "OPEN CALCULATOR",
    "open calculator"
)

tool_button(
    "SYSTEM INFORMATION",
    "show me my PC information"
)

tool_button(
    "CURRENT TIME",
    "what time is it"
)

tool_button(
    "TELL ME A JOKE",
    "tell me a joke"
)

tool_button(
    "WHAT CAN YOU DO",
    "what can you do"
)


# ============================================================
# MULTI TASK
# ============================================================

tk.Frame(
    right,
    bg=BORDER,
    height=1
).pack(
    fill="x",
    padx=18,
    pady=(18, 15)
)


tk.Label(
    right,
    text="MULTI-TASK",
    font=(
        FONT,
        12,
        "bold"
    ),
    fg=CYAN,
    bg=PANEL
).pack(
    pady=(0, 8)
)


tool_button(
    "NOTEPAD + CALCULATOR",
    "open notepad and calculator"
)

tool_button(
    "CALCULATOR + NOTEPAD",
    "open calculator and notepad"
)


# ============================================================
# DASHBOARD ACTIONS
# ============================================================

def show_memory():

    if jarvis_main is None:

        log(
            "Main module is unavailable.",
            "error"
        )

        return

    try:

        result = jarvis_main.process_command(
            "show my memory"
        )

        message = result.get(
            "message",
            "No memory result."
        )

        log(
            message
        )

    except Exception as e:

        log(
            f"Memory error: {e}",
            "error"
        )


def clear_console():

    console.delete(
        "1.0",
        "end"
    )

    log(
        "Console cleared.",
        "system"
    )


left_button(
    "SHOW MEMORY",
    show_memory
)

left_button(
    "CLEAR CHAT",
    clear_console
)


# ============================================================
# INITIAL SYSTEM VALUES
# ============================================================

os_value.config(
    text=platform.system()
)

python_value.config(
    text=platform.python_version()
)

ai_value.config(
    text=getattr(
        jarvis_main,
        "OLLAMA_MODEL",
        "OLLAMA"
    ).upper()
)


# ============================================================
# COMMAND EXECUTION
# ============================================================

def send_command():

    global command_running

    if command_running:

        log(
            "A command is already running.",
            "muted"
        )

        return

    text = command_entry.get().strip()

    if not text:

        return

    command_entry.delete(
        0,
        "end"
    )

    log(
        f"YOU > {text}",
        "user"
    )

    command_running = True

    send_button.config(
        state="disabled",
        text="RUNNING..."
    )

    threading.Thread(
        target=execute_command_thread,
        args=(text,),
        daemon=True
    ).start()


def execute_command_thread(text):

    global command_running

    try:

        if jarvis_main is None:

            raise RuntimeError(
                "Could not import main.py"
            )

        result = jarvis_main.process_command(
            text
        )

        message = result.get(
            "message"
        )

        should_exit = result.get(
            "exit",
            False
        )

        root.after(
            0,
            lambda: command_finished(
                message,
                should_exit
            )
        )

    except Exception as e:

        root.after(
            0,
            lambda: command_finished(
                f"Command error: {e}",
                False,
                True
            )
        )


def command_finished(
    message,
    should_exit=False,
    error=False
):

    global command_running

    command_running = False

    send_button.config(
        state="normal",
        text="SEND"
    )

    if message:

        log(
            f"JARVIS > {message}",
            "error" if error else "jarvis"
        )

    if should_exit:

        log(
            "Dashboard command requested shutdown.",
            "system"
        )


# ============================================================
# ENTER KEY
# ============================================================

command_entry.bind(
    "<Return>",
    lambda event: send_command()
)


# ============================================================
# SYSTEM MONITOR
# ============================================================

def update_system():

    try:

        cpu = psutil.cpu_percent(
            interval=None
        )

        ram = psutil.virtual_memory()

        disk = psutil.disk_usage(
            "C:\\"
        )

        cpu_value.config(
            text=f"{cpu:.0f}%",
            fg=percent_color(cpu)
        )

        ram_value.config(
            text=f"{ram.percent:.0f}%",
            fg=percent_color(
                ram.percent
            )
        )

        disk_value.config(
            text=f"{disk.percent:.0f}%",
            fg=percent_color(
                disk.percent
            )
        )

        uptime = time.time() - psutil.boot_time()

        status_label.config(
            text="ONLINE",
            fg=GREEN
        )

        status_dot.config(
            fg=GREEN
        )

    except Exception as e:

        status_label.config(
            text="MONITOR ERROR",
            fg=RED
        )

        status_dot.config(
            fg=RED
        )

    root.after(
        1500,
        update_system
    )


# ============================================================
# LIVE CLOCK
# ============================================================

def update_clock():

    now = datetime.now().strftime(
        "%A  %d %B %Y  |  %H:%M:%S"
    )

    live_label.config(
        text=f"● LIVE  {now}",
        fg=GREEN
    )

    root.after(
        1000,
        update_clock
    )


# ============================================================
# 3D HUD ANIMATION
# ============================================================

pulse_state = True


def pulse_hud():

    global pulse_state

    pulse_state = not pulse_state

    if pulse_state:

        accent.config(
            bg=CYAN
        )

        live_label.config(
            fg=GREEN
        )

    else:

        accent.config(
            bg="#007D99"
        )

        live_label.config(
            fg="#00B87A"
        )

    root.after(
        900,
        pulse_hud
    )


# ============================================================
# STARTUP LOG
# ============================================================

log(
    "JARVIS dashboard initialized.",
    "system"
)

log(
    "Local AI interface ready.",
    "system"
)

log(
    "Multi-task execution available.",
    "system"
)

log(
    "Parallel task execution available.",
    "system"
)

if jarvis_main is None:

    log(
        f"main.py import failed: {MAIN_IMPORT_ERROR}",
        "error"
    )


# ============================================================
# START MONITORS
# ============================================================

update_system()

update_clock()

pulse_hud()


# ============================================================
# FOCUS INPUT
# ============================================================

root.after(
    300,
    lambda: command_entry.focus_set()
)


# ============================================================
# CLOSE
# ============================================================

def on_close():

    global command_running

    if command_running:

        answer = messagebox.askyesno(
            "JARVIS",
            "A command is still running.\n\nClose dashboard?"
        )

        if not answer:

            return

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# START
# ============================================================

root.mainloop()