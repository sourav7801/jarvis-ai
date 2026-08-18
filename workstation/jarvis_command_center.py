from __future__ import annotations

import json
import queue
import threading
import tkinter as tk

from tkinter import (
    messagebox,
    scrolledtext,
    ttk,
)


from omni.jarvis_supervisor_v1 import (
    jarvis_supervisor,
)

from omni.universal_command_bridge import (
    command_bridge,
)

from omni.voice_conversation_v2 import (
    voice_conversation_v2,
)


class JarvisCommandCenter:

    def __init__(
        self,
        root,
    ):

        self.root = root

        self.events = queue.Queue()

        self.speak_answers = tk.BooleanVar(
            value=False
        )


        root.title(
            "JARVIS Command Center"
        )

        root.geometry(
            "1180x760"
        )

        root.minsize(
            900,
            600,
        )


        self._build()

        self.refresh_health()

        self._pump()


    def _build(
        self,
    ):

        top = ttk.Frame(
            self.root,
            padding=10,
        )

        top.pack(
            fill="x"
        )


        ttk.Label(
            top,
            text="JARVIS",
            font=(
                "Segoe UI",
                24,
                "bold",
            ),
        ).pack(
            side="left"
        )


        self.status_label = ttk.Label(
            top,
            text="Starting...",
        )

        self.status_label.pack(
            side="left",
            padx=20,
        )


        ttk.Button(
            top,
            text="System Health",
            command=self.refresh_health,
        ).pack(
            side="right",
            padx=5,
        )


        ttk.Button(
            top,
            text="Voice Mode",
            command=self.start_voice,
        ).pack(
            side="right",
            padx=5,
        )


        ttk.Checkbutton(
            top,
            text="Speak answers",
            variable=self.speak_answers,
        ).pack(
            side="right",
            padx=8,
        )


        body = ttk.Panedwindow(
            self.root,
            orient="horizontal",
        )

        body.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5,
        )


        chat_frame = ttk.Frame(
            body
        )

        health_frame = ttk.Frame(
            body
        )


        body.add(
            chat_frame,
            weight=3,
        )

        body.add(
            health_frame,
            weight=1,
        )


        self.chat = scrolledtext.ScrolledText(
            chat_frame,
            wrap="word",
            font=(
                "Consolas",
                11,
            ),
            state="disabled",
        )

        self.chat.pack(
            fill="both",
            expand=True,
        )


        input_frame = ttk.Frame(
            chat_frame
        )

        input_frame.pack(
            fill="x",
            pady=8,
        )


        self.input = ttk.Entry(
            input_frame,
            font=(
                "Segoe UI",
                12,
            ),
        )

        self.input.pack(
            side="left",
            fill="x",
            expand=True,
        )


        self.input.bind(
            "<Return>",
            lambda event:
                self.send(),
        )


        ttk.Button(
            input_frame,
            text="Send",
            command=self.send,
        ).pack(
            side="left",
            padx=8,
        )


        self.health = scrolledtext.ScrolledText(
            health_frame,
            wrap="word",
            font=(
                "Consolas",
                9,
            ),
            state="disabled",
        )

        self.health.pack(
            fill="both",
            expand=True,
        )


        self._append(
            "SYSTEM",
            (
                "JARVIS Command Center ready.\n"
                "Type naturally. Operator actions remain "
                "approval-gated."
            ),
        )


    def _set_text(
        self,
        widget,
        text,
    ):

        widget.configure(
            state="normal"
        )

        widget.delete(
            "1.0",
            "end",
        )

        widget.insert(
            "end",
            text,
        )

        widget.configure(
            state="disabled"
        )


    def _append(
        self,
        speaker,
        text,
    ):

        self.chat.configure(
            state="normal"
        )

        self.chat.insert(
            "end",
            "\n"
            + str(
                speaker
            )
            + " > "
            + str(
                text
            )
            + "\n"
        )

        self.chat.see(
            "end"
        )

        self.chat.configure(
            state="disabled"
        )


    def send(
        self,
    ):

        text = (
            self.input
            .get()
            .strip()
        )


        if not text:

            return


        self.input.delete(
            0,
            "end",
        )


        self._append(
            "YOU",
            text,
        )


        threading.Thread(
            target=self._execute,
            args=(text,),
            daemon=True,
        ).start()


    def _execute(
        self,
        text,
    ):

        try:

            result = (
                command_bridge
                .execute(
                    text
                )
            )


            response = (
                result.get(
                    "response"
                )
                or str(
                    result
                )
            )


            self.events.put(
                (
                    "answer",
                    response,
                )
            )


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    (
                        type(exc).__name__
                        + ": "
                        + str(exc)
                    ),
                )
            )


    def start_voice(
        self,
    ):

        self._append(
            "SYSTEM",
            "Starting existing JARVIS continuous voice mode...",
        )


        threading.Thread(
            target=self._voice_worker,
            daemon=True,
        ).start()


    def _voice_worker(
        self,
    ):

        try:

            voice_conversation_v2.run_existing_mode()


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    "Voice: "
                    + type(exc).__name__
                    + ": "
                    + str(exc),
                )
            )


    def refresh_health(
        self,
    ):

        threading.Thread(
            target=self._health_worker,
            daemon=True,
        ).start()


    def _health_worker(
        self,
    ):

        try:

            status = (
                jarvis_supervisor
                .status()
            )


            self.events.put(
                (
                    "health",
                    status,
                )
            )


        except Exception as exc:

            self.events.put(
                (
                    "error",
                    "Health: "
                    + str(
                        exc
                    ),
                )
            )


    def _pump(
        self,
    ):

        try:

            while True:

                kind, payload = (
                    self.events
                    .get_nowait()
                )


                if kind == "answer":

                    self._append(
                        "JARVIS",
                        payload,
                    )


                    if self.speak_answers.get():

                        threading.Thread(
                            target=
                                voice_conversation_v2
                                .speak,
                            args=(
                                payload,
                            ),
                            daemon=True,
                        ).start()


                elif kind == "health":

                    self._set_text(
                        self.health,
                        json.dumps(
                            payload,
                            indent=2,
                            default=str,
                        ),
                    )


                    self.status_label.configure(
                        text=(
                            "READY"
                            if payload.get(
                                "ready"
                            )
                            else "DEGRADED"
                        )
                    )


                else:

                    self._append(
                        "ERROR",
                        payload,
                    )


        except queue.Empty:

            pass


        self.root.after(
            150,
            self._pump,
        )


def main():

    root = tk.Tk()

    JarvisCommandCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":

    main()
