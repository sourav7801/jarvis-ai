import speech_recognition as sr
import pyttsx3
import threading
import time


# ============================================================
# JARVIS VOICE SYSTEM
# ============================================================

recognizer = sr.Recognizer()

# Prevent multiple TTS operations from running simultaneously.
_speak_lock = threading.Lock()


# ============================================================
# SPEECH ENGINE
# ============================================================

def create_speaker():

    engine = pyttsx3.init()

    engine.setProperty(
        "rate",
        175
    )

    engine.setProperty(
        "volume",
        1.0
    )

    return engine


# ============================================================
# GET VOICES
# ============================================================

def get_voices():

    try:

        engine = create_speaker()

        voices = engine.getProperty(
            "voices"
        )

        try:
            engine.stop()
        except Exception:
            pass

        return voices

    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Could not get voices: {e}"
        )

        return []


# ============================================================
# SPEAK
# ============================================================

def speak(text):

    if text is None:
        return

    text = str(text).strip()

    if not text:
        return

    print()
    print(
        f"JARVIS 🔊 > {text}"
    )

    # Only one speech engine at a time.
    with _speak_lock:

        engine = None

        try:

            # IMPORTANT:
            # Create a NEW engine for every utterance.
            #
            # This avoids the Windows pyttsx3/SAPI
            # engine getting stuck after the first speech.

            engine = create_speaker()

            engine.say(text)

            engine.runAndWait()

            # Give SAPI a tiny amount of time to finish
            # releasing its resources.

            time.sleep(0.05)

        except Exception as e:

            print(
                f"JARVIS VOICE DEBUG > "
                f"Speech output error: {e}"
            )

        finally:

            if engine is not None:

                try:
                    engine.stop()

                except Exception:
                    pass

                del engine


# ============================================================
# LISTEN
# ============================================================

def listen():

    try:

        with sr.Microphone() as source:

            print()
            print(
                "🎤 JARVIS > Listening..."
            )

            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.4
            )

            try:

                audio = recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=15
                )

            except sr.WaitTimeoutError:

                print(
                    "JARVIS > I didn't hear anything."
                )

                return None

    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Microphone error: {e}"
        )

        return None


    # ========================================================
    # SPEECH RECOGNITION
    # ========================================================

    try:

        print(
            "JARVIS > Understanding..."
        )

        text = recognizer.recognize_google(
            audio
        )

        text = text.strip()

        if text:

            print()
            print(
                f"YOU 🎤 > {text}"
            )

        return text


    except sr.UnknownValueError:

        print(
            "JARVIS > I couldn't understand that."
        )

        return None


    except sr.RequestError as e:

        print(
            f"JARVIS > Speech recognition error: {e}"
        )

        return None


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Recognition error: {e}"
        )

        return None


# ============================================================
# DIRECT VOICE TEST
# ============================================================

def voice_test():

    print("=" * 50)
    print("          JARVIS VOICE TEST")
    print("=" * 50)

    print()

    speak(
        "Voice system online."
    )

    print()

    speak(
        "This is speech test number one."
    )

    print()

    speak(
        "This is speech test number two."
    )

    print()

    speak(
        "This is speech test number three."
    )

    print()

    text = listen()

    if text:

        speak(
            f"You said: {text}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    voice_test()