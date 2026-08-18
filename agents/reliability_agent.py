from __future__ import annotations

from omni.reliability_supervisor import reliability_supervisor


def reliability(request: str):
    text = " ".join(str(request or "").lower().split())
    if any(phrase in text for phrase in ("repair yourself", "self heal", "self-heal", "fix yourself", "repair system")):
        return reliability_supervisor.diagnose_and_repair()
    if any(phrase in text for phrase in ("improve yourself", "make yourself better", "improvement plan", "reliability plan")):
        return reliability_supervisor.improvement_plan()
    return reliability_supervisor.diagnose()
