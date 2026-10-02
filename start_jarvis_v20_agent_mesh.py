from __future__ import annotations

"""Stable launcher for the JARVIS V20 multi-agent mesh service."""

import os
import runpy


if __name__ == "__main__":
    os.environ.setdefault("JARVIS_LIVE_EXECUTION", "0")
    os.environ.setdefault("JARVIS_V20_WORKSPACE_OS", "1")
    runpy.run_module("workstation.v20_agent_mesh_service", run_name="__main__")
