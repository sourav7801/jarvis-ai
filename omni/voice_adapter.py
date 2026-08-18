from __future__ import annotations

import importlib.util


from omni.approval_queue import (
    approval_queue,
)


class VoiceAdapter:

    @staticmethod
    def status():

        speech = (
            importlib.util
            .find_spec(
                "speech_recognition"
            )
            is not None
        )


        pyaudio = (
            importlib.util
            .find_spec(
                "pyaudio"
            )
            is not None
        )


        pyttsx3 = (
            importlib.util
            .find_spec(
                "pyttsx3"
            )
            is not None
        )


        return {
            "speech_recognition":
                speech,

            "microphone_provider":
                pyaudio,

            "text_to_speech":
                pyttsx3,

            "continuous_microphone":
                False,

            "wake_word":
                False,

            "one_shot_capture":
                speech
                and pyaudio,
        }


    def listen_once(
        self,
        *,
        approval_id=None,
        timeout=5,
        phrase_time_limit=10,
    ):

        payload = {
            "operation":
                "microphone.listen_once",

            "timeout":
                int(
                    timeout
                ),

            "phrase_time_limit":
                int(
                    phrase_time_limit
                ),
        }


        if not approval_id:

            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    approval_queue
                    .request(
                        "voice.listen_once",

                        payload,

                        display={
                            "microphone":
                                "one-shot capture",

                            "timeout":
                                int(
                                    timeout
                                ),

                            "phrase_time_limit":
                                int(
                                    phrase_time_limit
                                ),
                        },

                        risk=
                            "microphone",
                    ),
            }


        approval_queue.consume(
            approval_id,
            "voice.listen_once",
            payload,
        )


        status = self.status()


        if not status[
            "one_shot_capture"
        ]:

            return {
                "success":
                    False,

                "error":
                    (
                        "SpeechRecognition/PyAudio "
                        "microphone provider is unavailable."
                    ),
            }


        import speech_recognition as sr


        recognizer = (
            sr.Recognizer()
        )


        try:

            with sr.Microphone() as source:

                audio = (
                    recognizer.listen(
                        source,

                        timeout=max(
                            1,
                            min(
                                int(
                                    timeout
                                ),
                                30,
                            ),
                        ),

                        phrase_time_limit=max(
                            1,
                            min(
                                int(
                                    phrase_time_limit
                                ),
                                60,
                            ),
                        ),
                    )
                )


            text = (
                recognizer
                .recognize_google(
                    audio
                )
            )


            return {
                "success":
                    True,

                "text":
                    text,
            }


        except Exception as exc:

            return {
                "success":
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


voice_adapter = (
    VoiceAdapter()
)
