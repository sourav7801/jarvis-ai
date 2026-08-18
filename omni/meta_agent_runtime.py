from __future__ import annotations

import json


GUIDANCE = {

    "learning":
        "Detect knowledge gaps, determine what must "
        "be learned, synthesize specialist evidence, "
        "separate fact from assumption and produce "
        "reusable verified knowledge.",

    "knowledge":
        "Convert evidence into concepts, entities, "
        "relationships, confidence and reusable "
        "structured knowledge.",

    "skill_builder":
        "Convert repeatable procedures into candidate "
        "skill specifications with inputs, outputs, "
        "constraints, tests and failure conditions.",

    "experiment":
        "Design controlled experiments using a "
        "baseline, candidate, metrics, success "
        "threshold and rollback condition.",

    "evaluator":
        "Benchmark capability objectively using "
        "explicit evidence and measurable metrics.",

    "critic":
        "Independently challenge plans and results "
        "for unsupported assumptions, omissions, "
        "contradictions and risks.",

    "meta_improvement":
        "Find measurable JARVIS weaknesses and "
        "propose improvements. Never modify production "
        "code directly. Require sandbox evaluation, "
        "approval and rollback capability.",
}


def _extract_text(args, kwargs):

    for key in (
        "text",
        "request",
        "prompt",
        "message",
        "task",
    ):
        value = kwargs.get(key)

        if isinstance(value, str):
            return value

    for value in args:

        if isinstance(value, str):
            return value

        candidate = getattr(
            value,
            "text",
            None,
        )

        if isinstance(candidate, str):
            return candidate

    return ""


def _context(text):

    begin = "[JARVIS MISSION CONTEXT]"
    end = "[END JARVIS MISSION CONTEXT]"

    if begin not in text or end not in text:
        return {}

    raw = (
        text.split(begin, 1)[1]
        .split(end, 1)[0]
        .strip()
    )

    try:
        return json.loads(raw)
    except Exception:
        return {}


def run_meta(role, *args, **kwargs):

    text = _extract_text(
        args,
        kwargs,
    )

    context = _context(
        text
    )

    findings = context.get(
        "dependency_outputs",
        {},
    )

    if not isinstance(findings, dict):
        findings = {}

    return json.dumps(
        {
            "agent": role,

            "status": "complete",

            "guidance":
                GUIDANCE.get(
                    role,
                    "Analyze carefully.",
                ),

            "mission_goal":
                context.get(
                    "goal",
                    context.get(
                        "mission_goal",
                        "",
                    ),
                ),

            "specialist_findings_received":
                len(findings),

            "specialist_findings":
                findings,

            "safety": {
                "direct_self_modification":
                    False,

                "automatic_production_promotion":
                    False,

                "approval_required_for_promotion":
                    True,
            },
        },
        ensure_ascii=False,
        default=str,
    )
