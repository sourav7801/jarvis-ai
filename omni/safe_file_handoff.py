from __future__ import annotations

from pathlib import Path

import hashlib
import ipaddress
import mimetypes
import os
import re
import socket
import urllib.parse
import urllib.request


from omni.approval_queue import (
    approval_queue,
)


BLOCKED_EXTENSIONS = {
    ".exe",
    ".msi",
    ".bat",
    ".cmd",
    ".ps1",
    ".dll",
    ".scr",
    ".com",
    ".sys",
    ".vbs",
    ".js",
    ".jar",
}


class SafeFileHandoff:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "downloads"
            )
        )


    @staticmethod
    def validate_url(
        url,
    ):

        value = str(
            url
        ).strip()


        parsed = urllib.parse.urlparse(
            value
        )


        if parsed.scheme not in (
            "http",
            "https",
        ):

            raise ValueError(
                "Only HTTP/HTTPS downloads "
                "are allowed."
            )


        if not parsed.hostname:

            raise ValueError(
                "Download URL requires a host."
            )


        host = parsed.hostname.lower()


        if host in (
            "localhost",
            "localhost.localdomain",
        ):

            raise PermissionError(
                "Localhost downloads are blocked."
            )


        try:

            addresses = socket.getaddrinfo(
                host,
                None,
            )


            for address in addresses:

                ip = ipaddress.ip_address(
                    address[
                        4
                    ][
                        0
                    ]
                )


                if (
                    ip.is_loopback
                    or ip.is_private
                    or ip.is_link_local
                    or ip.is_multicast
                ):

                    raise PermissionError(
                        "Private/local network "
                        "downloads are blocked."
                    )


        except socket.gaierror:

            pass


        return value


    @staticmethod
    def safe_name(
        url,
        filename=None,
    ):

        if filename:

            name = Path(
                str(
                    filename
                )
            ).name

        else:

            parsed = (
                urllib.parse
                .urlparse(
                    url
                )
            )


            name = Path(
                parsed.path
            ).name


        name = re.sub(
            r"[^A-Za-z0-9._ -]+",
            "_",
            name,
        ).strip()


        if not name:

            name = (
                "download.bin"
            )


        suffix = Path(
            name
        ).suffix.lower()


        if suffix in (
            BLOCKED_EXTENSIONS
        ):

            raise PermissionError(
                "Executable/script download "
                "types are blocked."
            )


        return name[:180]


    def binding(
        self,
        url,
        *,
        filename=None,
        max_bytes=
            50 * 1024 * 1024,
    ):

        url = self.validate_url(
            url
        )


        name = self.safe_name(
            url,
            filename,
        )


        payload = {
            "url":
                url,

            "filename":
                name,

            "max_bytes":
                int(
                    max_bytes
                ),
        }


        return {
            "action":
                "file.download",

            "payload":
                payload,

            "display": {
                "url":
                    url,

                "filename":
                    name,

                "maximum_mb":
                    round(
                        max_bytes
                        / 1024
                        / 1024,
                        1,
                    ),
            },

            "risk":
                "external-file",
        }


    def download(
        self,
        url,
        *,
        filename=None,
        approval_id=None,
        max_bytes=
            50 * 1024 * 1024,
    ):

        binding = self.binding(
            url,

            filename=
                filename,

            max_bytes=
                max_bytes,
        )


        payload = binding[
            "payload"
        ]


        if not approval_id:

            request = (
                approval_queue
                .request(
                    binding[
                        "action"
                    ],

                    payload,

                    display=
                        binding[
                            "display"
                        ],

                    risk=
                        binding[
                            "risk"
                        ],
                )
            )


            return {
                "success":
                    False,

                "requires_approval":
                    True,

                "approval":
                    request,
            }


        approval_queue.consume(
            approval_id,

            binding[
                "action"
            ],

            payload,
        )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        destination = (
            self.root
            / payload[
                "filename"
            ]
        ).resolve()


        root = self.root.resolve()


        if (
            root
            not in destination.parents
        ):

            raise PermissionError(
                "Download destination escaped "
                "the controlled folder."
            )


        request = urllib.request.Request(
            payload[
                "url"
            ],

            headers={
                "User-Agent":
                    "Jarvis/1.0",
            },
        )


        temp = destination.with_suffix(
            destination.suffix
            + ".part"
        )


        total = 0

        digest = hashlib.sha256()


        try:

            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:

                final_url = (
                    self.validate_url(
                        response.geturl()
                    )
                )


                content_length = (
                    response.headers.get(
                        "Content-Length"
                    )
                )


                if (
                    content_length

                    and int(
                        content_length
                    )
                    > payload[
                        "max_bytes"
                    ]
                ):

                    raise ValueError(
                        "Download exceeds "
                        "maximum size."
                    )


                with temp.open(
                    "wb"
                ) as handle:

                    while True:

                        chunk = response.read(
                            1024 * 256
                        )


                        if not chunk:
                            break


                        total += len(
                            chunk
                        )


                        if (
                            total
                            > payload[
                                "max_bytes"
                            ]
                        ):

                            raise ValueError(
                                "Download exceeds "
                                "maximum size."
                            )


                        digest.update(
                            chunk
                        )


                        handle.write(
                            chunk
                        )


            temp.replace(
                destination
            )


            return {
                "success":
                    True,

                "path":
                    str(
                        destination
                    ),

                "bytes":
                    total,

                "sha256":
                    digest.hexdigest(),

                "url":
                    final_url,

                "executable":
                    False,
            }


        except Exception:

            temp.unlink(
                missing_ok=True
            )

            raise


safe_file_handoff = (
    SafeFileHandoff()
)
