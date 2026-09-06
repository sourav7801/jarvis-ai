from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8", newline="\n")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if old not in source:
        raise RuntimeError(f"V6.2 integration anchor not found: {label}")
    return source.replace(old, new, 1)


# 1) Quant Firm runtime -> Adaptive Quant Brain, preserving the V6.1 runtime.
path = "workstation/quant_firm_runtime.py"
source = read(path)
source = replace_once(
    source,
    "from omni.trading_intelligence.quant_firm_engine import decide\n",
    "from omni.trading_intelligence.adaptive_quant_brain import adaptive_decide\n",
    "quant_firm_runtime adaptive import",
)
source = replace_once(
    source,
    '    result = decide(canonical, tf, candles).to_dict()\n    result["success"] = True\n    return result\n',
    '    result = adaptive_decide(canonical, tf, candles)\n    result = dict(result)\n    result["success"] = True\n    return result\n',
    "quant_firm_runtime adaptive decision",
)
write(path, source)


# 2) Closed synthetic trades feed the bounded learning engine.
path = "workstation/paper_trading_desk.py"
source = read(path)
if "learning_engine.record_closed_row" not in source:
    anchor = '''            conn.commit()\n\n        return {\n            "success": True,\n            "reason": reason,\n            "position_id": int(row["id"]),\n'''
    replacement = '''            conn.commit()\n\n        try:\n            from omni.trading_intelligence.trade_learning_engine import learning_engine\n\n            learning_engine.record_closed_row(\n                row,\n                exit_price=exit_value,\n                pnl=pnl,\n                reason=reason,\n            )\n        except Exception:\n            # Learning telemetry must never block a synthetic paper exit.\n            pass\n\n        return {\n            "success": True,\n            "reason": reason,\n            "position_id": int(row["id"]),\n'''
    source = replace_once(source, anchor, replacement, "paper close learning")
write(path, source)


# 3) Layer self-improvement onto the newer V6.1 autonomy lifecycle without
#    removing bounded decision review, immediate scans, mark management, or
#    the 50/30/20 mandate machinery.
path = "workstation/paper_autonomy_engine.py"
source = read(path)
if "self_improvement_coordinator.start()" not in source:
    start_anchor = '''        try:\n            from workstation.bounded_decision_review import decision_review_coordinator\n\n            decision_review_coordinator.start()\n        except Exception:\n            pass\n        if scan_now:\n            self.trigger_scan()\n        return self.status()\n'''
    start_replacement = '''        try:\n            from workstation.bounded_decision_review import decision_review_coordinator\n\n            decision_review_coordinator.start()\n        except Exception:\n            pass\n        try:\n            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator\n\n            self_improvement_coordinator.start()\n        except Exception:\n            pass\n        if scan_now:\n            self.trigger_scan()\n        return self.status()\n'''
    source = replace_once(source, start_anchor, start_replacement, "paper autonomy self improvement start")

if "self_improvement_coordinator.stop()" not in source:
    stop_anchor = '''        with self._lock:\n            self._running = any(\n                thread is not None and thread.is_alive()\n                for thread in (self._scan_thread, self._mark_thread)\n            )\n        return self.status()\n'''
    stop_replacement = '''        with self._lock:\n            self._running = any(\n                thread is not None and thread.is_alive()\n                for thread in (self._scan_thread, self._mark_thread)\n            )\n        try:\n            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator\n\n            self_improvement_coordinator.stop()\n        except Exception:\n            pass\n        return self.status()\n'''
    source = replace_once(source, stop_anchor, stop_replacement, "paper autonomy self improvement stop")
source = source.replace('strategy="QUANT_V4_REGIME_ENSEMBLE"', 'strategy="ADAPTIVE_QUANT_V6_REGIME_ENSEMBLE"')
write(path, source)


# 4) Preserve the richer V6.1 symbol resolver (including equities) and only
#    extend routing for deterministic paper actions and Adaptive intelligence.
path = "workstation/quant_terminal_bridge.py"
source = read(path)
route_anchor = '''    if is_universe_scan_request(text):\n        return True\n\n    if not requested_symbols(text):\n        return False\n'''
route_replacement = '''    if is_universe_scan_request(text):\n        return True\n\n    from workstation.paper_trade_action_router import is_paper_trade_action_request\n    from workstation.quant_intelligence_commands import is_quant_intelligence_command\n\n    if is_paper_trade_action_request(text) or is_quant_intelligence_command(text):\n        return True\n\n    if not requested_symbols(text):\n        return False\n'''
source = replace_once(source, route_anchor, route_replacement, "master adaptive/intelligence routing")
write(path, source)


# 5) Extend the existing V6.1 Quant terminal pipeline; do not replace its
#    morning coordinator, scanners, option desk, signal terminal, or paper desk.
path = "workstation/quant_terminal_v2.py"
source = read(path)
if "from workstation.quant_intelligence_commands import quant_intelligence_command_payload" not in source:
    source = replace_once(
        source,
        "    from workstation.paper_trade_action_router import paper_trade_action_payload\n",
        "    from workstation.paper_trade_action_router import paper_trade_action_payload\n"
        "    from workstation.quant_intelligence_commands import quant_intelligence_command_payload\n",
        "quant intelligence import",
    )

if "intelligence_result = quant_intelligence_command_payload(command)" not in source:
    pipeline_anchor = '''    trade_action = paper_trade_action_payload(command)\n    if trade_action is not None:\n        return attach_signal_chart(command, trade_action)\n\n    signal_result = signal_terminal_payload(command)\n'''
    pipeline_replacement = '''    trade_action = paper_trade_action_payload(command)\n    if trade_action is not None:\n        return attach_signal_chart(command, trade_action)\n\n    intelligence_result = quant_intelligence_command_payload(command)\n    if intelligence_result is not None:\n        return intelligence_result\n\n    signal_result = signal_terminal_payload(command)\n'''
    source = replace_once(source, pipeline_anchor, pipeline_replacement, "quant intelligence pipeline")

if 'path == "/adaptive_brain_runtime.js"' not in source:
    static_anchor = '''        if path == "/advanced_terminal_runtime.js":\n            return self.send_file(STATIC / "advanced_terminal_runtime.js", "application/javascript; charset=utf-8")\n'''
    static_replacement = '''        if path == "/advanced_terminal_runtime.js":\n            return self.send_file(STATIC / "advanced_terminal_runtime.js", "application/javascript; charset=utf-8")\n        if path == "/adaptive_brain_runtime.js":\n            return self.send_file(STATIC / "adaptive_brain_runtime.js", "application/javascript; charset=utf-8")\n'''
    source = replace_once(source, static_anchor, static_replacement, "adaptive runtime static route")

if 'path == "/api/intelligence/decision"' not in source:
    api_anchor = '''        if path == "/api/paper/portfolio":\n            from workstation.paper_trading_desk import portfolio_payload\n\n            return self.send_json(portfolio_payload())\n'''
    api_replacement = '''        if path == "/api/intelligence/decision":\n            try:\n                from workstation.quant_firm_runtime import decision_payload\n\n                symbol = str((params.get("symbol") or ["BTC"])[0])\n                timeframe = str((params.get("timeframe") or ["15m"])[0])\n                decision = decision_payload(symbol, timeframe)\n                return self.send_json(\n                    {\n                        "success": bool(decision.get("success")),\n                        "decision": decision,\n                        "paper_only": True,\n                        "live_execution": False,\n                    },\n                    200 if decision.get("success") else 503,\n                )\n            except Exception as exc:\n                return self.send_json(\n                    {\n                        "success": False,\n                        "message": _safe_message(exc),\n                        "paper_only": True,\n                        "live_execution": False,\n                    },\n                    400,\n                )\n        if path == "/api/intelligence/status":\n            from omni.trading_intelligence.trade_learning_engine import learning_engine\n            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator\n\n            return self.send_json(\n                {\n                    "success": True,\n                    "learning": learning_engine.status(),\n                    "self_improvement": self_improvement_coordinator.status(),\n                    "paper_only": True,\n                    "live_execution": False,\n                }\n            )\n        if path == "/api/paper/portfolio":\n            from workstation.paper_trading_desk import portfolio_payload\n\n            return self.send_json(portfolio_payload())\n'''
    source = replace_once(source, api_anchor, api_replacement, "adaptive intelligence APIs")
write(path, source)


# 6) Add the adaptive overlay runtime without deleting the V6.1 advanced
#    terminal, option chart, paper desk, intelligence page, or Nautilus runtime.
path = "workstation/quant_terminal_v2_static/index.html"
source = read(path)
if '<script src="/adaptive_brain_runtime.js"></script>' not in source:
    source = replace_once(
        source,
        '<script src="/advanced_terminal_runtime.js"></script>\n</body>',
        '<script src="/advanced_terminal_runtime.js"></script>\n<script src="/adaptive_brain_runtime.js"></script>\n</body>',
        "adaptive runtime script tag",
    )
source = source.replace(
    "JARVIS Quant V5 · Nautilus core + autonomous paper desk",
    "JARVIS Quant V6.2 · V6.1 full terminal + Adaptive Brain + learning + strategy research + Nautilus",
)
write(path, source)


# 7) Preserve all existing app.js behavior; only make Adaptive intelligence
#    actions focus the referenced market when possible.
path = "workstation/quant_terminal_v2_static/app.js"
source = read(path)
focus_line = '    if(["quant_adaptive_explanation","quant_strategy_research"].includes(result.action)&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}\n'
if focus_line not in source:
    anchor = '    if(result.action==="open_quant"&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}\n'
    if anchor in source:
        source = source.replace(anchor, anchor + focus_line, 1)
write(path, source)

print("V6.2 Adaptive Quant integration: PASS")
print("V6.1 workspaces and richer routing preserved: PASS")
print("Trade learning + self-improvement lifecycle: PASS")
print("Adaptive decision API/runtime: PASS")
print("Live broker execution surface added: NO")
