from __future__ import annotations

from pathlib import Path

import csv
import io
import subprocess
import time


class SystemObserver:

    @staticmethod
    def processes():

        result = subprocess.run(
            [
                "tasklist",
                "/FO",
                "CSV",
                "/NH",
            ],
            capture_output=True,
            text=True,
            shell=False,
        )


        if result.returncode:

            return ()


        reader = csv.reader(
            io.StringIO(
                result.stdout
            )
        )


        output = []


        for row in reader:

            if len(row) < 5:
                continue

            output.append(
                {
                    "image_name":
                        row[0],

                    "pid":
                        row[1],

                    "session_name":
                        row[2],

                    "session_number":
                        row[3],

                    "memory":
                        row[4],
                }
            )


        return tuple(
            output
        )


    def application_running(
        self,
        name,
    ):

        query = str(
            name
        ).lower()


        return any(
            query
            in process[
                "image_name"
            ].lower()

            for process
            in self.processes()
        )


    @staticmethod
    def screen_capture_available():

        try:

            from PIL import (
                ImageGrab,
            )

            return True

        except Exception:

            return False


    def capture_screen(
        self,
        path,
        *,
        approved=False,
    ):

        if not approved:

            raise PermissionError(
                "Screen capture requires "
                "explicit approval because "
                "the display may contain "
                "sensitive information."
            )


        try:

            from PIL import (
                ImageGrab,
            )

        except Exception as exc:

            raise RuntimeError(
                "Screen capture provider "
                "is unavailable."
            ) from exc


        destination = Path(
            path
        ).resolve()


        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        image = (
            ImageGrab.grab(
                all_screens=True
            )
        )


        image.save(
            destination
        )


        return {
            "success":
                True,

            "path":
                str(
                    destination
                ),

            "width":
                image.width,

            "height":
                image.height,

            "captured_at":
                time.time(),
        }


    def state(self):

        processes = (
            self.processes()
        )


        return {
            "process_count":
                len(
                    processes
                ),

            "screen_capture_available":
                self
                .screen_capture_available(),

            "sample_processes":
                processes[:20],
        }


system_observer = (
    SystemObserver()
)
