"""Stable launcher for the JARVIS V20 specialist Options Agent."""
from __future__ import annotations

import runpy

if __name__ == "__main__":
    runpy.run_module("workstation.v20_options_agent_service", run_name="__main__")
