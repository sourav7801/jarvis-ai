import time

from voice import listen, speak
from main import process_command


# ============================================================
# JARVIS WAKE WORD CONFIGURATION
# ============================================================

WAKE_WORDS = [
    "jarvis",
    "hey jarvis",
    "okay jarvis",
    "ok jarvis",
]

EXIT_WORDS = [
    "exit",
    "quit",
    "shutdown",
    "shut down",
    "stop",
]


# ============================================================
# WAKE WORD CHECK
# ============================================================

def contains_wake_word(text):

    if not text:
        return False

    text = text.lower().strip()

    for word in WAKE_WORDS:

        if word in text:
            return True

    return False


# ============================================================
# REMOVE WAKE WORD
# ============================================================

def remove_wake_word(text):

    if not text:
        return ""

    result = text.strip()

    lower = result.lower()

    # Check longest phrases first.

    for word in sorted(
        WAKE_WORDS,
        key=len,
        reverse=True
    ):

        if lower.startswith(word):

            result = result[
                len(word):
            ].strip()

            break

    return result


# ============================================================
# EXIT CHECK
# ============================================================

def is_exit_command(text):

    if not text:
        return False

    command = text.lower().strip()

    return command in EXIT_WORDS


# ============================================================
# LISTEN FOR COMMAND AFTER "JARVIS"
# ============================================================

def listen_for_command():

    attempts = 0

    max_attempts = 3

    while attempts < max_attempts:

        command = listen()

        if command:

            return command

        attempts += 1

        if attempts < max_attempts:

            print()
            print(
                "JARVIS > I'm still listening..."
            )

    return None


# ============================================================
# PROCESS COMMAND
# ============================================================

def run_command(command):

    if not command:

        return

    command = command.strip()

    if not command:

        return

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    if is_exit_command(command):

        speak(
            "Shutting down wake mode."
        )

        return True

    # --------------------------------------------------------
    # SEND COMMAND TO EXISTING JARVIS ENGINE
    # --------------------------------------------------------

    try:

        process_command(
            command
        )

    except Exception as e:

        print()
        print(
            f"JARVIS > Command error: {e}"
        )

        speak(
            "I encountered an error processing that command."
        )

    return False


# ============================================================
# WAKE MODE
# ============================================================

def wake_mode():

    print()
    print("=" * 50)
    print("           JARVIS WAKE MODE")
    print("=" * 50)

    print()
    print(
        "Say 'Jarvis' to activate."
    )

    print(
        "You can say 'Jarvis, your command'."
    )

    print(
        "Say 'exit', 'stop', or 'shutdown' to stop."
    )

    print()

    speak(
        "Wake mode is active. Say Jarvis when you need me."
    )

    while True:

        # ====================================================
        # WAIT FOR WAKE WORD
        # ====================================================

        text = listen()

        if not text:

            continue

        # ====================================================
        # GLOBAL EXIT
        # ====================================================

        if is_exit_command(text):

            speak(
                "Shutting down wake mode."
            )

            break

        # ====================================================
        # IGNORE SPEECH WITHOUT WAKE WORD
        # ====================================================

        if not contains_wake_word(text):

            continue

        # ====================================================
        # REMOVE WAKE WORD
        # ====================================================

        command = remove_wake_word(
            text
        )

        # ====================================================
        # USER ONLY SAID "JARVIS"
        # ====================================================

        if not command:

            speak(
                "Yes?"
            )

            command = listen_for_command()

            if not command:

                speak(
                    "I didn't get that."
                )

                continue

        # ====================================================
        # EXECUTE COMMAND
        # ====================================================

        should_exit = run_command(
            command
        )

        if should_exit:

            break

        # ====================================================
        # SMALL PAUSE
        # ====================================================

        time.sleep(0.3)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        wake_mode()

    except KeyboardInterrupt:

        print()
        print(
            "JARVIS > Wake mode stopped."
        )

        try:

            speak(
                "Wake mode stopped."
            )

        except Exception:

            pass