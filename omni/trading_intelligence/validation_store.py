from __future__ import annotations

from pathlib import Path

import json
import os
import uuid


class ValidationStore:

    def __init__(
        self,
        root=None,
    ):

        self.root = Path(
            root
            or (
                Path("data")
                / "trading"
                / "validation"
            )
        )


    def save(
        self,
        report,
    ):

        if not report.get(
            "research_only",
            False,
        ):
            raise ValueError(
                "Only research validation reports may be stored."
            )


        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )


        path = (
            self.root
            / (
                "validation_"
                + uuid.uuid4()
                .hex[:12]
                + ".json"
            )
        )


        temporary = (
            path.with_suffix(
                ".tmp"
            )
        )


        temporary.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )


        os.replace(
            temporary,
            path,
        )


        return {
            "success":
                True,

            "path":
                str(path),

            "research_only":
                True,
        }


validation_store = ValidationStore()
