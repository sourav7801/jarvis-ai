from __future__ import annotations

from dataclasses import (
    dataclass,
)

import re


WEIGHTS = {
    "dom": 1.00,
    "uia": 0.95,
    "vision": 0.70,
}


@dataclass(frozen=True)
class TargetCandidate:

    source: str

    label: str

    role: str

    score: float

    payload: dict


@dataclass(frozen=True)
class TargetResolution:

    target: str

    resolved: bool

    ambiguous: bool

    best: TargetCandidate | None

    candidates: tuple[
        TargetCandidate,
        ...
    ]


def _tokens(
    value,
):

    return {
        token

        for token in re.findall(
            r"[a-z0-9]+",
            str(
                value
            ).lower(),
        )

        if token
    }


def _similarity(
    target,
    label,
):

    a = _tokens(
        target
    )

    b = _tokens(
        label
    )


    if not a or not b:

        return 0.0


    score = (
        len(
            a & b
        )
        / len(
            a | b
        )
    )


    left = str(
        target
    ).strip().lower()

    right = str(
        label
    ).strip().lower()


    if left == right:

        score += 0.35

    elif left in right:

        score += 0.15


    return min(
        1.0,
        score,
    )


class TargetFusion:

    def resolve(
        self,
        target,
        *,
        dom=(),
        uia=(),
        vision=(),
        minimum_score=0.42,
    ):

        candidates = []


        for source, items in (
            (
                "dom",
                dom,
            ),
            (
                "uia",
                uia,
            ),
            (
                "vision",
                vision,
            ),
        ):

            for item in items:

                label = str(
                    item.get(
                        "text",
                        ""
                    )
                    or item.get(
                        "aria_label",
                        ""
                    )
                    or item.get(
                        "name",
                        ""
                    )
                    or item.get(
                        "label",
                        ""
                    )
                )


                role = str(
                    item.get(
                        "role",
                        ""
                    )
                    or item.get(
                        "control_type",
                        ""
                    )
                    or item.get(
                        "tag",
                        ""
                    )
                )


                confidence = (
                    float(
                        item.get(
                            "confidence",
                            1.0,
                        )
                    )
                    if source
                    == "vision"
                    else 1.0
                )


                confidence = max(
                    0.0,
                    min(
                        confidence,
                        1.0,
                    ),
                )


                score = (
                    _similarity(
                        target,
                        label,
                    )
                    * WEIGHTS[
                        source
                    ]
                    * confidence
                )


                if score > 0:

                    candidates.append(
                        TargetCandidate(
                            source=
                                source,

                            label=
                                label,

                            role=
                                role,

                            score=
                                round(
                                    score,
                                    4,
                                ),

                            payload=
                                dict(
                                    item
                                ),
                        )
                    )


        candidates.sort(
            key=lambda item:
                item.score,
            reverse=True,
        )


        if not candidates:

            return TargetResolution(
                target=str(
                    target
                ),

                resolved=False,

                ambiguous=False,

                best=None,

                candidates=(),
            )


        best = candidates[
            0
        ]


        if (
            best.score
            < minimum_score
        ):

            return TargetResolution(
                target=str(
                    target
                ),

                resolved=False,

                ambiguous=False,

                best=
                    best,

                candidates=
                    tuple(
                        candidates[:10]
                    ),
            )


        ambiguous = (
            len(
                candidates
            ) > 1

            and abs(
                candidates[
                    0
                ].score
                - candidates[
                    1
                ].score
            )
            <= 0.05
        )


        return TargetResolution(
            target=str(
                target
            ),

            resolved=
                not ambiguous,

            ambiguous=
                ambiguous,

            best=
                best,

            candidates=
                tuple(
                    candidates[:10]
                ),
        )


target_fusion = (
    TargetFusion()
)
