from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "quant_terminal_v2_static"


def test_v20_is_an_orchestration_layer_not_a_replacement_shell():
    http = (ROOT / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
    js = (STATIC / "v20_workspace_os.js").read_text(encoding="utf-8")
    assert "/v18_options_workbench.js" in http
    assert "/v19_workspace_cockpit.js" in http
    assert 'window.JARVIS_V18_OPTIONS_WORKBENCH=true' in http
    assert 'window.JARVIS_V19_WORKSPACE_OS=true' in http
    assert 'Proven V17/V18/V19 surfaces stay visible' in js
    assert "START JARVIS TRADING" in js
    assert "STOP NEW ENTRIES" in js
    assert "SCAN ALL MARKETS" in js
    assert "/api/v20/journal?limit=40" in js


def test_v20_global_control_routes_to_workspace_autopilot_and_options_agent():
    http = (ROOT / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
    assert 'parsed.path == "/api/v20/control"' in http
    assert "_autopilot_control(runtime, body)" in http
    assert "_v20_options_agent_control(action)" in http
    assert 'parsed.path == "/api/v20/journal"' in http
