from __future__ import annotations

import importlib.util
import threading


class VoiceConversationV2:

    def __init__(
        self,
    ):

        self._speech_lock = (
            threading.Lock()
        )


    @staticmethod
    def _available(
        package,
    ):

        return (
            importlib.util.find_spec(
                package
            )
            is not None
        )


    def status(
        self,
    ):

        import main


        try:

            existing = (
                main
                .jarvis_voice_status()
            )

        except Exception as exc:

            existing = {
                "available":
                    False,

                "error":
                    (
                        type(
                            exc
                        ).__name__
                        + ": "
                        + str(
                            exc
                        )
                    ),
            }


        return {
            "version":
                "2.0",

            "existing_voice":
                existing,

            "speech_recognition":
                self._available(
                    "speech_recognition"
                ),

            "pyttsx3":
                self._available(
                    "pyttsx3"
                ),

            "pyaudio":
                self._available(
                    "pyaudio"
                ),

            "continuous_existing_voice_mode":
                callable(
                    getattr(
                        main,
                        "voice_mode",
                        None,
                    )
                ),

            "cancel_speech":
                callable(
                    getattr(
                        main,
                        "cancel_speech",
                        None,
                    )
                ),

            "command_bridge":
                True,
        }


    def speak(
        self,
        text,
    ):

        if not self._available(
            "pyttsx3"
        ):

            return {
                "success":
                    False,

                "reason":
                    "pyttsx3 unavailable",
            }


        import pyttsx3


        with self._speech_lock:

            engine = pyttsx3.init()


            try:

                engine.say(
                    str(
                        text
                    )
                )

                engine.runAndWait()


            finally:

                try:

                    engine.stop()

                except Exception:

                    pass


        return {
            "success":
                True,
        }


    def run_existing_mode(
        self,
    ):

        import main


        function = getattr(
            main,
            "voice_mode",
            None,
        )


        if not callable(
            function
        ):

            raise RuntimeError(
                "Existing JARVIS voice_mode is unavailable."
            )


        return function()


    def cancel(
        self,
    ):

        import main


        function = getattr(
            main,
            "cancel_speech",
            None,
        )


        if callable(
            function
        ):

            return function()


        return None


voice_conversation_v2 = (
    VoiceConversationV2()
)
