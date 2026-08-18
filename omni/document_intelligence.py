from __future__ import annotations

from pathlib import Path

import json
import re
import zipfile
import xml.etree.ElementTree as ET


class DocumentIntelligence:

    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".py",
        ".json",
        ".csv",
        ".log",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
    }


    def read(
        self,
        path,
        *,
        max_chars=100000,
    ):

        source = Path(
            path
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        max_chars = max(
            1000,
            min(
                int(
                    max_chars
                ),
                500000,
            ),
        )


        suffix = (
            source.suffix
            .lower()
        )


        if suffix in (
            self.TEXT_EXTENSIONS
        ):

            text = source.read_text(
                encoding="utf-8",
                errors="replace",
            )


        elif suffix == ".pdf":

            text = self._read_pdf(
                source
            )


        elif suffix == ".docx":

            text = self._read_docx(
                source
            )


        else:

            raise ValueError(
                "Unsupported document type: "
                + suffix
            )


        return {
            "path":
                str(
                    source
                ),

            "type":
                suffix,

            "characters":
                len(
                    text
                ),

            "truncated":
                len(
                    text
                )
                > max_chars,

            "text":
                text[
                    :max_chars
                ],
        }


    @staticmethod
    def _read_pdf(
        path,
    ):

        reader_class = None


        try:

            from pypdf import (
                PdfReader,
            )

            reader_class = (
                PdfReader
            )

        except Exception:

            try:

                from PyPDF2 import (
                    PdfReader,
                )

                reader_class = (
                    PdfReader
                )

            except Exception as exc:

                raise RuntimeError(
                    "PDF text provider "
                    "is unavailable. Install "
                    "pypdf for local PDF reading."
                ) from exc


        reader = reader_class(
            str(
                path
            )
        )


        pages = []


        for number, page in enumerate(
            reader.pages,
            1,
        ):

            try:

                text = (
                    page.extract_text()
                    or ""
                )

            except Exception:

                text = ""


            pages.append(
                (
                    "\n"
                    "[PAGE "
                    + str(
                        number
                    )
                    + "]\n"
                    + text
                )
            )


        return "".join(
            pages
        )


    @staticmethod
    def _read_docx(
        path,
    ):

        with zipfile.ZipFile(
            path
        ) as archive:

            xml = archive.read(
                "word/document.xml"
            )


        root = ET.fromstring(
            xml
        )


        values = []


        for element in root.iter():

            if (
                element.tag.endswith(
                    "}t"
                )
                and element.text
            ):

                values.append(
                    element.text
                )


        return "\n".join(
            values
        )


    def search(
        self,
        path,
        query,
        *,
        max_matches=20,
    ):

        document = self.read(
            path
        )


        query = str(
            query
        ).strip()


        if not query:

            raise ValueError(
                "query cannot be empty"
            )


        text = document[
            "text"
        ]


        lower = text.lower()

        needle = query.lower()


        matches = []

        start = 0


        while (
            len(
                matches
            )
            < max_matches
        ):

            index = lower.find(
                needle,
                start,
            )


            if index < 0:
                break


            left = max(
                0,
                index - 150,
            )

            right = min(
                len(
                    text
                ),
                index
                + len(
                    query
                )
                + 150,
            )


            matches.append(
                text[
                    left:right
                ]
            )


            start = (
                index
                + len(
                    needle
                )
            )


        return {
            "query":
                query,

            "matches":
                tuple(
                    matches
                ),

            "count":
                len(
                    matches
                ),
        }


document_intelligence = (
    DocumentIntelligence()
)
