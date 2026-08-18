
from __future__ import annotations

from typing import Any


def explain_wait(
    market: dict[str, Any],
    candidate_result: dict[str, Any],
    decision: dict[str, Any] | None = None,
) -> list[str]:
    """
    Produce human-readable rejection explanations for workstation/voice.
    """

    reasons = []

    diag = candidate_result.get(
        "diagnostics",
        {}
    )

    candidate = candidate_result.get(
        "candidate"
    )

    if candidate is None:
        missing = diag.get(
            "missing",
            []
        )

        reasons.extend(
            str(x)
            for x in missing
        )

        if not reasons:
            reasons.append(
                candidate_result.get(
                    "reason",
                    "No candidate generated."
                )
            )

    if decision:
        gates = decision.get(
            "gates",
            {}
        )

        if gates.get(
            "symbol_policy"
        ) is False:
            reasons.append(
                decision.get(
                    "reason",
                    "Symbol policy rejected the setup."
                )
            )

        if gates.get(
            "research"
        ) is False:
            reasons.append(
                "Research edge is not explicitly VALIDATED."
            )

        if gates.get(
            "options"
        ) is False:
            reasons.append(
                "Option confirmation is unavailable."
            )

    # Stable order and deduplication.
    out = []
    seen = set()

    for reason in reasons:
        text = str(reason).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)

    return out


def status_label(
    market: dict[str, Any],
    candidate_result: dict[str, Any],
    decision: dict[str, Any] | None,
) -> str:
    if decision and decision.get(
        "paper_candidate"
    ):
        return "PAPER_CANDIDATE"

    if candidate_result.get(
        "candidate"
    ):
        if (
            decision
            and not decision.get(
                "gates",
                {}
            ).get(
                "research",
                False,
            )
        ):
            return "CANDIDATE_WAIT_RESEARCH"

        return "CANDIDATE_WAIT_OPTION"

    return "WAIT"
