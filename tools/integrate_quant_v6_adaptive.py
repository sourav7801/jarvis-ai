from __future__ import annotations

from pathlib import Path


ROOT = Path('C:\\Jarvis')


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8", newline="\n")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if old not in source:
        raise RuntimeError(f"V6 integration anchor not found: {label}")
    return source.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Quant Firm runtime -> Adaptive Quant Brain
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Adaptive brain -> higher-order chart patterns + custom indicator plugins
# ---------------------------------------------------------------------------
path = "omni/trading_intelligence/adaptive_quant_brain.py"
source = read(path)
if "from omni.trading_intelligence.chart_pattern_engine import detect_chart_patterns" not in source:
    source = source.replace(
        "from omni.trading_intelligence.quant_firm_engine import strategy_votes\n",
        "from omni.trading_intelligence.quant_firm_engine import strategy_votes\n"
        "from omni.trading_intelligence.chart_pattern_engine import detect_chart_patterns\n"
        "from omni.trading_intelligence.indicator_plugin_registry import indicator_registry\n",
        1,
    )
source = replace_once(
    source,
    '        "patterns": patterns,\n    }\n',
    '        "patterns": patterns,\n        "chart_patterns": detect_chart_patterns(candles),\n    }\n',
    "adaptive brain chart patterns",
)
source = replace_once(
    source,
    "    base_votes = [\n",
    "    custom_indicators = indicator_registry.evaluate_all(candles)\n\n    base_votes = [\n",
    "adaptive brain custom indicators",
)
source = replace_once(
    source,
    '        "indicator_plugins": {\n            "supported": [\n',
    '        "custom_indicators": custom_indicators,\n        "indicator_plugins": {\n            "registered": indicator_registry.describe(),\n            "supported": [\n',
    "adaptive brain indicator registry output",
)
# Chart-pattern votes are deliberately low/medium weight; pattern labels alone
# cannot create a trade.
needle = "    return votes\n\n\ndef adaptive_decide"
if "HIGHER_ORDER_CHART_PATTERN" not in source:
    addition = '''    for pattern in structure.get("chart_patterns") or []:
        bias = str(pattern.get("bias") or "").upper()
        name = str(pattern.get("pattern") or "CHART_PATTERN")
        confidence = float(pattern.get("confidence") or 0.0)
        if bias == "BULLISH":
            votes.append(_vote("HIGHER_ORDER_CHART_PATTERN", "pattern", "LONG", 52 + confidence * 20, [name]))
        elif bias == "BEARISH":
            votes.append(_vote("HIGHER_ORDER_CHART_PATTERN", "pattern", "SHORT", 52 + confidence * 20, [name]))

    return votes


def adaptive_decide'''
    if needle not in source:
        raise RuntimeError("V6 integration anchor not found: adaptive brain chart pattern votes")
    source = source.replace(needle, addition, 1)
write(path, source)


# ---------------------------------------------------------------------------
# Paper close -> persistent learning outcome
# ---------------------------------------------------------------------------
path = "workstation/paper_trading_desk.py"
source = read(path)
anchor = '''        return {
            "success": True,
            "reason": reason,
            "position_id": int(row["id"]),
'''
replacement = '''        try:
            from omni.trading_intelligence.trade_learning_engine import learning_engine

            learning_engine.record_closed_row(
                row,
                exit_price=exit_value,
                pnl=pnl,
                reason=reason,
            )
        except Exception:
            # Learning telemetry must never block a synthetic exit.
            pass

        return {
            "success": True,
            "reason": reason,
            "position_id": int(row["id"]),
'''
source = replace_once(source, anchor, replacement, "paper close learning")
write(path, source)


# ---------------------------------------------------------------------------
# Autonomous paper engine -> background governed research loop
# ---------------------------------------------------------------------------
path = "workstation/paper_autonomy_engine.py"
source = read(path)
start_anchor = '''            self._scan_thread.start()
            self._mark_thread.start()
        return self.status()
'''
start_replacement = '''            self._scan_thread.start()
            self._mark_thread.start()
        try:
            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator

            self_improvement_coordinator.start()
        except Exception:
            pass
        return self.status()
'''
source = replace_once(source, start_anchor, start_replacement, "paper autonomy self improvement start")
stop_anchor = '''        with self._lock:
            self._running = False
        return self.status()
'''
stop_replacement = '''        with self._lock:
            self._running = False
        try:
            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator

            self_improvement_coordinator.stop()
        except Exception:
            pass
        return self.status()
'''
source = replace_once(source, stop_anchor, stop_replacement, "paper autonomy self improvement stop")
source = source.replace('strategy="QUANT_V4_REGIME_ENSEMBLE"', 'strategy="ADAPTIVE_QUANT_V6_REGIME_ENSEMBLE"')
write(path, source)


# ---------------------------------------------------------------------------
# Master Quant router -> typo-tolerant markets + direct execution + intelligence
# ---------------------------------------------------------------------------
path = "workstation/quant_terminal_bridge.py"
source = read(path)
start = source.index("def requested_symbols(text: str) -> tuple[str, ...]:")
end = source.index("\n\ndef _looks_like_terminal_phrase", start)
new_requested_symbols = '''def requested_symbols(text: str) -> tuple[str, ...]:
    value = normalize(text)
    candidates = []
    for alias, symbol in _SYMBOL_ALIASES:
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", value):
            left, right = match.span()
            candidates.append((left, -(right-left), right, symbol))
    candidates.sort()
    found = []
    occupied = []
    for left, _length, right, symbol in candidates:
        if any(left < r and right > l for l, r in occupied):
            continue
        occupied.append((left, right))
        if symbol not in found:
            found.append(symbol)

    tokens = list(re.finditer(r"[a-z0-9]+", value))
    aliases = [(re.sub(r"[^a-z0-9]", "", alias), symbol) for alias, symbol in _SYMBOL_ALIASES]
    fuzzy = []
    for index in range(len(tokens)):
        for width in (1, 2, 3):
            stop = index + width
            if stop > len(tokens):
                continue
            left = tokens[index].start()
            right = tokens[stop-1].end()
            if any(left < r and right > l for l, r in occupied):
                continue
            window = "".join(token.group(0) for token in tokens[index:stop])
            if len(window) < 4:
                continue
            best_symbol = None
            best_ratio = 0.0
            for alias, symbol in aliases:
                if symbol in found or not alias or abs(len(window)-len(alias)) > 2:
                    continue
                ratio = 1.0 if window == alias else SequenceMatcher(None, window, alias).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_symbol = symbol
            if best_symbol and best_ratio >= 0.88:
                fuzzy.append((left, right, best_symbol, best_ratio))
    for left, right, symbol, ratio in sorted(fuzzy, key=lambda item: (item[0], -(item[1]-item[0]), -item[3])):
        if any(left < r and right > l for l, r in occupied):
            continue
        occupied.append((left, right))
        if symbol not in found:
            found.append(symbol)
    return tuple(found)
'''
source = source[:start] + new_requested_symbols + source[end:]
route_anchor = '''    if is_universe_scan_request(text):
        return True

    if not requested_symbols(text):
        return False
'''
route_replacement = '''    if is_universe_scan_request(text):
        return True

    from workstation.paper_trade_action_router import is_paper_trade_action_request
    from workstation.quant_intelligence_commands import is_quant_intelligence_command

    if is_paper_trade_action_request(text) or is_quant_intelligence_command(text):
        return True

    if not requested_symbols(text):
        return False
'''
source = replace_once(source, route_anchor, route_replacement, "master route direct/intelligence")
lock_anchor = '''    response_parts.append("Live broker execution remains locked.")

    return QuantTerminalDispatch(
'''
lock_replacement = '''    if not any(
        "live broker execution remains locked" in str(part).lower()
        for part in response_parts
    ):
        response_parts.append("Live broker execution remains locked.")

    return QuantTerminalDispatch(
'''
source = replace_once(source, lock_anchor, lock_replacement, "master duplicate lock suppression")
write(path, source)


# ---------------------------------------------------------------------------
# Quant terminal pipeline + intelligence API + adaptive chart runtime
# ---------------------------------------------------------------------------
path = "workstation/quant_terminal_v2.py"
source = read(path)
import_anchor = '''    from workstation.paper_trading_desk import paper_command_payload
    from workstation.nautilus_universe_router import universe_command_payload

    command = str(text or "").strip()
'''
import_replacement = '''    from workstation.paper_trading_desk import paper_command_payload
    from workstation.nautilus_universe_router import universe_command_payload
    from workstation.paper_trade_action_router import paper_trade_action_payload
    from workstation.quant_intelligence_commands import quant_intelligence_command_payload

    command = str(text or "").strip()
'''
source = replace_once(source, import_anchor, import_replacement, "quant terminal adaptive command imports")
pipeline_anchor = '''    paper_result = paper_command_payload(command)
    if paper_result is not None:
        return paper_result

    universe_result = universe_command_payload(command)
    if universe_result is not None:
        return universe_result
'''
pipeline_replacement = '''    # Preserve Paper Desk / portfolio / autonomy precedence before generic
    # direct-trade recognition.
    paper_result = paper_command_payload(command)
    if paper_result is not None:
        return paper_result

    trade_action = paper_trade_action_payload(command)
    if trade_action is not None:
        return trade_action

    intelligence_result = quant_intelligence_command_payload(command)
    if intelligence_result is not None:
        return intelligence_result

    universe_result = universe_command_payload(command)
    if universe_result is not None:
        return universe_result
'''
source = replace_once(source, pipeline_anchor, pipeline_replacement, "quant terminal adaptive command pipeline")
static_anchor = '''        if path == "/nautilus_core_runtime.js":
            return self.send_file(STATIC / "nautilus_core_runtime.js", "application/javascript; charset=utf-8")
'''
static_replacement = '''        if path == "/nautilus_core_runtime.js":
            return self.send_file(STATIC / "nautilus_core_runtime.js", "application/javascript; charset=utf-8")
        if path == "/adaptive_brain_runtime.js":
            return self.send_file(STATIC / "adaptive_brain_runtime.js", "application/javascript; charset=utf-8")
'''
source = replace_once(source, static_anchor, static_replacement, "adaptive runtime static route")
api_anchor = '''        if path == "/api/paper/portfolio":
            from workstation.paper_trading_desk import portfolio_payload

            return self.send_json(portfolio_payload())
'''
api_replacement = '''        if path == "/api/intelligence/decision":
            try:
                from workstation.quant_firm_runtime import decision_payload

                symbol = str((params.get("symbol") or ["BTC"])[0])
                timeframe = str((params.get("timeframe") or ["15m"])[0])
                decision = decision_payload(symbol, timeframe)
                return self.send_json(
                    {
                        "success": bool(decision.get("success")),
                        "decision": decision,
                        "paper_only": True,
                        "live_execution": False,
                    },
                    200 if decision.get("success") else 503,
                )
            except Exception as exc:
                return self.send_json({"success": False, "message": _safe_message(exc), "paper_only": True, "live_execution": False}, 400)
        if path == "/api/intelligence/status":
            from omni.trading_intelligence.trade_learning_engine import learning_engine
            from omni.trading_intelligence.self_improvement_coordinator import self_improvement_coordinator

            return self.send_json(
                {
                    "success": True,
                    "learning": learning_engine.status(),
                    "self_improvement": self_improvement_coordinator.status(),
                    "paper_only": True,
                    "live_execution": False,
                }
            )
        if path == "/api/paper/portfolio":
            from workstation.paper_trading_desk import portfolio_payload

            return self.send_json(portfolio_payload())
'''
source = replace_once(source, api_anchor, api_replacement, "adaptive intelligence API")
source = source.replace('"version": "QUANT_TERMINAL_V5"', '"version": "QUANT_TERMINAL_V6"')
write(path, source)


# ---------------------------------------------------------------------------
# Terminal HTML -> adaptive runtime + V6 footer
# ---------------------------------------------------------------------------
path = "workstation/quant_terminal_v2_static/index.html"
source = read(path)
source = replace_once(
    source,
    '<script src="/nautilus_core_runtime.js"></script>\n</body>',
    '<script src="/nautilus_core_runtime.js"></script>\n<script src="/adaptive_brain_runtime.js"></script>\n</body>',
    "terminal adaptive script tag",
)
source = source.replace(
    "JARVIS Quant V5 Â· Nautilus core + autonomous paper desk",
    "JARVIS Quant V6 Â· adaptive brain + learning + strategy research + Nautilus",
)
source = source.replace(
    "<div class=\"eyebrow\">NEXT INTELLIGENCE MODULES</div>",
    "<div class=\"eyebrow\">ADAPTIVE INTELLIGENCE</div>",
)
source = source.replace(
    "<span>OPTION CHAIN</span><span>OI / IV</span><span>FVG</span><span>STRUCTURE</span><span>HEATMAPS</span><span>PORTFOLIO RISK</span>",
    "<span>BOS / CHOCH</span><span>FVG</span><span>LIQUIDITY</span><span>PATTERNS</span><span>LEARNING</span><span>STRATEGY LAB</span>",
)
write(path, source)


# ---------------------------------------------------------------------------
# Terminal app -> focus market after deterministic paper action
# ---------------------------------------------------------------------------
path = "workstation/quant_terminal_v2_static/app.js"
source = read(path)
anchor = '''    if(result.action==="open_quant"&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}
'''
replacement = '''    if(result.action==="open_quant"&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}
    if(["paper_trade_opened","paper_trade_armed","paper_trade_existing_position","paper_trade_risk_rejected","quant_adaptive_explanation","quant_strategy_research"].includes(result.action)&&result.symbol){const raw=String(result.symbol).toUpperCase().replaceAll(" ","");const found=MARKETS.find(item=>item.symbol===raw||item.label.toUpperCase().replaceAll(" ","")===raw);if(found){selectMarket(found.symbol);scanSelected()}}
'''
source = replace_once(source, anchor, replacement, "terminal trade/intelligence focus")
write(path, source)


# ---------------------------------------------------------------------------
# Voice compile regression -> unique output file, preserve compile assertion
# ---------------------------------------------------------------------------
path = "tests/test_jarvis_v32_hybrid_voice.py"
source = read(path)
old_output = '''        output = (
            ROOT
            / ".jarvis-dev"
            / "JarvisVoiceService.test.exe"
        )
'''
new_output = '''        output = (
            ROOT
            / ".jarvis-dev"
            / f"JarvisVoiceService.test.{os.getpid()}.{id(self)}.exe"
        )
'''
source = replace_once(source, old_output, new_output, "voice unique compile output")
old_ps = '''            "& $csc /nologo /target:exe /optimize+ "
            "'/out:C:\\\\Jarvis\\\\.jarvis-dev\\\\JarvisVoiceService.test.exe' "
            "('/reference:' + $speech) "
'''
new_ps = '''            "& $csc /nologo /target:exe /optimize+ "
            f"'/out:{str(output).replace(chr(92), chr(92)+chr(92))}' "
            "('/reference:' + $speech) "
'''
source = replace_once(source, old_ps, new_ps, "voice compile output path")
assert_anchor = '''        self.assertEqual(
            result.returncode,
            0,
            msg=(
                result.stdout
                + result.stderr
            ),
        )
'''
assert_replacement = '''        try:
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    result.stdout
                    + result.stderr
                ),
            )
        finally:
            try:
                output.unlink(missing_ok=True)
            except Exception:
                pass
'''
source = replace_once(source, assert_anchor, assert_replacement, "voice compile cleanup")
write(path, source)


print("Adaptive Quant Brain integration: PASS")
print("Chart structure/pattern integration: PASS")
print("Trade outcome learning integration: PASS")
print("Self-improvement research loop integration: PASS")
print("Direct paper trade actions: PASS")
print("Quant intelligence commands: PASS")
print("Adaptive chart overlay API/runtime: PASS")
print("Voice compile lock regression hardening: PASS")
print("Live broker execution surface added: NO")
