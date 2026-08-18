# ============================================================
# JARVIS VOICE SYSTEM
# FINAL V2.7
# ============================================================

import speech_recognition as sr
import pyttsx3
import threading
import time


# ============================================================
# SPEECH RECOGNIZER
# ============================================================

recognizer = sr.Recognizer()

recognizer.pause_threshold = 1.8
recognizer.phrase_threshold = 0.3
recognizer.non_speaking_duration = 0.5

recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5


# ============================================================
# SPEECH ENGINE STATE
# ============================================================

_engine_lock = threading.RLock()

_engine = None

_speech_thread = None

_stop_event = threading.Event()

_speech_generation = 0


# ============================================================
# ENGINE
# ============================================================

def create_speaker():

    engine = pyttsx3.init()

    engine.setProperty(
        "rate",
        175,
    )

    engine.setProperty(
        "volume",
        1.0,
    )

    return engine


def get_engine():

    global _engine

    with _engine_lock:

        if _engine is None:

            _engine = create_speaker()

        return _engine


# ============================================================
# DESTROY ENGINE
# ============================================================

def _destroy_engine():

    global _engine

    with _engine_lock:

        if _engine is not None:

            try:

                _engine.stop()

            except Exception:
                pass

            _engine = None


# ============================================================
# VOICES
# ============================================================

def get_voices():

    try:

        engine = get_engine()

        return engine.getProperty(
            "voices"
        )

    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Could not get voices: {e}"
        )

        return []


# ============================================================
# STOP SPEAKING
# ============================================================

def stop_speaking():

    global _speech_generation

    with _engine_lock:

        _speech_generation += 1

        _stop_event.set()

        if _engine is not None:

            try:

                _engine.stop()

            except Exception as e:

                print(
                    f"JARVIS VOICE DEBUG > "
                    f"Engine stop error: {e}"
                )


# ============================================================
# ALIAS
# ============================================================

def stop():

    stop_speaking()


def cancel_speech():

    stop_speaking()


# ============================================================
# SPEECH WORKER
# ============================================================

def _speech_worker(
    text,
    generation,
):

    global _speech_thread

    try:

        # ----------------------------------------------------
        # Check whether this request was cancelled before
        # speech began.
        # ----------------------------------------------------

        with _engine_lock:

            if generation != _speech_generation:

                return

            if _stop_event.is_set():

                return

            engine = get_engine()


        # ----------------------------------------------------
        # Speak in chunks.
        #
        # Chunking makes cancellation more responsive.
        # ----------------------------------------------------

        sentences = _split_text(
            text
        )


        for sentence in sentences:

            with _engine_lock:

                if generation != _speech_generation:

                    return

                if _stop_event.is_set():

                    return

                engine = get_engine()

                engine.say(
                    sentence
                )

                try:

                    engine.runAndWait()

                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"Speech engine error: {e}"
                    )

                    return


            # Tiny cancellation checkpoint.
            time.sleep(
                0.01
            )


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Speech output error: {e}"
        )

    finally:

        with _engine_lock:

            if generation == _speech_generation:

                _stop_event.clear()

        _speech_thread = None


# ============================================================
# TEXT SPLITTER
# ============================================================

def _split_text(
    text,
):

    text = str(
        text or ""
    ).strip()


    if not text:

        return []


    # Keep sentences reasonably short so stop_speaking()
    # can interrupt between chunks.
    words = text.split()

    chunks = []

    current = []

    current_length = 0


    for word in words:

        current.append(
            word
        )

        current_length += (
            len(word)
            + 1
        )


        if (
            current_length >= 180
            and
            word.endswith(
                (
                    ".",
                    "!",
                    "?",
                    ":",
                    ";",
                )
            )
        ):

            chunks.append(
                " ".join(
                    current
                )
            )

            current = []
            current_length = 0


    if current:

        chunks.append(
            " ".join(
                current
            )
        )


    return chunks


# ============================================================
# SPEAK
# ============================================================

def speak(
    text,
):

    global _speech_thread
    global _speech_generation

    if text is None:

        return


    text = str(
        text
    ).strip()


    if not text:

        return


    print()

    print(
        f"JARVIS 🔊 > {text}"
    )


    # --------------------------------------------------------
    # Cancel old speech first.
    # --------------------------------------------------------

    stop_speaking()


    with _engine_lock:

        _speech_generation += 1

        generation = (
            _speech_generation
        )

        _stop_event.clear()


    # --------------------------------------------------------
    # Start new speech without blocking.
    # --------------------------------------------------------

    _speech_thread = (
        threading.Thread(
            target=_speech_worker,
            args=(
                text,
                generation,
            ),
            daemon=True,
        )
    )


    _speech_thread.start()


# ============================================================
# MICROPHONE CALIBRATION
# ============================================================

def prepare_microphone(
    source,
):

    try:

        print(
            "JARVIS > "
            "Calibrating microphone..."
        )


        recognizer.adjust_for_ambient_noise(
            source,
            duration=1.0,
        )


        print(
            "JARVIS > "
            "Microphone ready."
        )


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Microphone calibration error: {e}"
        )


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


            try:

                audio = recognizer.listen(

                    source,

                    timeout=8,

                    phrase_time_limit=20,

                )


            except sr.WaitTimeoutError:

                print(
                    "JARVIS > "
                    "I didn't hear anything."
                )

                return None


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Microphone error: {e}"
        )

        return None


    # ========================================================
    # GOOGLE SPEECH RECOGNITION
    # ========================================================

    try:

        print(
            "JARVIS > "
            "Understanding..."
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
            "JARVIS > "
            "I couldn't understand that."
        )

        return None


    except sr.RequestError as e:

        print(
            f"JARVIS > "
            f"Speech recognition error: {e}"
        )

        return None


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Recognition error: {e}"
        )

        return None


# ============================================================
# CONTINUOUS LISTEN
# ============================================================

def listen_with_calibration():

    try:

        with sr.Microphone() as source:

            prepare_microphone(
                source
            )


            while True:

                print()

                print(
                    "🎤 JARVIS > Listening..."
                )


                try:

                    audio = recognizer.listen(

                        source,

                        timeout=8,

                        phrase_time_limit=20,

                    )


                except sr.WaitTimeoutError:

                    print(
                        "JARVIS > "
                        "I didn't hear anything."
                    )

                    yield None

                    continue


                try:

                    print(
                        "JARVIS > "
                        "Understanding..."
                    )


                    text = (
                        recognizer
                        .recognize_google(
                            audio
                        )
                    )


                    text = text.strip()


                    if text:

                        print()

                        print(
                            f"YOU 🎤 > {text}"
                        )


                        yield text

                    else:

                        yield None


                except sr.UnknownValueError:

                    print(
                        "JARVIS > "
                        "I couldn't understand that."
                    )

                    yield None


                except sr.RequestError as e:

                    print(
                        f"JARVIS > "
                        f"Speech recognition error: {e}"
                    )

                    yield None


                except Exception as e:

                    print(
                        f"JARVIS VOICE DEBUG > "
                        f"Recognition error: {e}"
                    )

                    yield None


    except Exception as e:

        print(
            f"JARVIS VOICE DEBUG > "
            f"Microphone error: {e}"
        )

        yield None


# ============================================================
# SHUTDOWN
# ============================================================

def shutdown_voice():

    stop_speaking()

    _destroy_engine()


# ============================================================
# VOICE TEST
# ============================================================

def voice_test():

    print(
        "=" * 50
    )

    print(
        "          JARVIS VOICE TEST"
    )

    print(
        "=" * 50
    )

    print()


    speak(
        "Voice system online."
    )


    time.sleep(
        1
    )


    speak(
        "This is speech test number one."
    )


    time.sleep(
        0.5
    )


    speak(
        "This is speech test number two."
    )


    time.sleep(
        0.5
    )


    speak(
        "This is speech test number three."
    )


    time.sleep(
        1
    )


    stop_speaking()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    voice_test()