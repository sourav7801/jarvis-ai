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


def test_v20_mounts_after_all_canonical_runtime_scripts():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    http = (ROOT / "workstation" / "v17_terminal_http.py").read_text(encoding="utf-8")
    # The index must not execute V20 before V17/V18/V19 are injected.
    assert 'src="/v20_workspace_os.js' not in html
    body_injection = http.split("body_injection = (", 1)[1].split(")", 1)[0]
    assert body_injection.index("/v19_workspace_cockpit.js") < body_injection.index("/v20_workspace_os.js")
    assert 'src="/v20_workspace_os.js?v=200108"' in body_injection


def test_v20_render_composes_workspace_specific_surfaces():
    js = (STATIC / "v20_workspace_os.js").read_text(encoding="utf-8")
    assert "root.innerHTML=header(w)+globalDeck(w)+workspaceContent" in js
    assert 'w==="OPTIONS"?optionShell()' in js
    assert "v20LoadCharts()" in js
    assert "bindOptions()" in js
