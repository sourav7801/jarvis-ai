from __future__ import annotations

import importlib.util
import shutil


class IntegrationStatus:

    @staticmethod
    def module(
        name,
    ):

        try:

            return (
                importlib.util
                .find_spec(
                    name
                )
                is not None
            )

        except Exception:

            return False


    def status(self):

        playwright = (
            self.module(
                "playwright"
            )
        )

        pywinauto = (
            self.module(
                "pywinauto"
            )
        )

        speech_recognition = (
            self.module(
                "speech_recognition"
            )
        )

        pyttsx3 = (
            self.module(
                "pyttsx3"
            )
        )

        google_api = (
            self.module(
                "googleapiclient"
            )
        )


        return {
            "playwright": {
                "installed":
                    playwright,

                "browser_binary_required":
                    True,

                "automatic_install":
                    False,
            },

            "desktop": {
                "win32_ctypes":
                    True,

                "pywinauto_optional":
                    pywinauto,
            },

            "screen_capture": {
                "pillow":
                    self.module(
                        "PIL"
                    ),
            },

            "github": {
                "git":
                    bool(
                        shutil.which(
                            "git"
                        )
                    ),

                "gh_cli":
                    bool(
                        shutil.which(
                            "gh"
                        )
                    ),

                "remote_write":
                    False,
            },

            "gmail": {
                "google_api_library":
                    google_api,

                "credentials_configured":
                    False,

                "write_enabled":
                    False,
            },

            "google_calendar": {
                "google_api_library":
                    google_api,

                "credentials_configured":
                    False,

                "write_enabled":
                    False,
            },

            "voice": {
                "speech_recognition":
                    speech_recognition,

                "text_to_speech":
                    pyttsx3,

                "microphone_auto_capture":
                    False,
            },

            "plugin_acquisition": {
                "automatic_install":
                    False,

                "proposal_only":
                    True,
            },
        }


    def acquisition_proposals(
        self,
    ):

        status = self.status()

        proposals = []


        if not status[
            "playwright"
        ][
            "installed"
        ]:

            proposals.append(
                {
                    "capability":
                        "browser_automation",

                    "package":
                        "playwright",

                    "follow_up":
                        (
                            "playwright install chromium"
                        ),

                    "automatic":
                        False,
                }
            )


        if not status[
            "desktop"
        ][
            "pywinauto_optional"
        ]:

            proposals.append(
                {
                    "capability":
                        "semantic_windows_ui",

                    "package":
                        "pywinauto",

                    "automatic":
                        False,
                }
            )


        if not status[
            "voice"
        ][
            "speech_recognition"
        ]:

            proposals.append(
                {
                    "capability":
                        "speech_recognition",

                    "package":
                        "SpeechRecognition",

                    "automatic":
                        False,
                }
            )


        return tuple(
            proposals
        )


integration_status = (
    IntegrationStatus()
)
