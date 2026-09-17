from __future__ import annotations

"""Wire the V17 crypto-underlying PAPER lane into one-touch control and UI.

Idempotent direct-pull patch.  Deribit option chains remain research-only;
BTC/ETH/SOL underlying paper positions use the canonical Paper Desk.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTTP_TARGET = ROOT / "workstation" / "v17_terminal_http.py"
ROUTER_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_workspace_router.js"

OLD_IMPORT = "from workstation.v17_autopilot_preferences import load_preferences, save_preferences\n"
NEW_IMPORT = OLD_IMPORT + "from workstation.v17_crypto_paper_lane import crypto_paper_lane\n"

OLD_CONTROL_TAIL = '''    success = all(item.get("success") is True for item in results.values())\n    states = {name: item.get("state") for name, item in results.items()}\n'''
NEW_CONTROL_TAIL = '''    try:\n        results["CRYPTO_UNDERLYING"] = (\n            crypto_paper_lane.start() if action == "start" else crypto_paper_lane.stop_new_entries()\n        )\n    except Exception as exc:\n        results["CRYPTO_UNDERLYING"] = {\n            "success": False,\n            "state": "PROBLEM",\n            "reason": type(exc).__name__,\n            "message": str(exc)[:300],\n            "paper_only": True,\n            "live_execution": False,\n        }\n\n    success = all(item.get("success") is True for item in results.values())\n    states = {name: item.get("state") or ("RUNNING" if item.get("running") else "PAUSED") for name, item in results.items()}\n'''

OLD_START_MESSAGE = '"V17 PAPER autopilot start requested through canonical sessions."'
NEW_START_MESSAGE = '"V17 PAPER autopilot started canonical sessions plus BTC/ETH/SOL underlying paper scanning."'

OLD_STATUS_PREF = '''            "autopilot_preferences": preferences,\n'''
NEW_STATUS_PREF = '''            "autopilot_preferences": preferences,\n            "crypto_underlying_paper": crypto_paper_lane.status(),\n'''

OLD_CAPABILITY = '''    if (["BTC", "ETH"].includes(value)) {\n      return {tier: "PUBLIC RESEARCH", kind: "research", source: "DERIBIT PUBLIC OPTIONS", detail: "Verified Deribit public option-chain research is available. V16 does not use the older separate crypto paper-intent ledger."};\n    }\n'''
NEW_CAPABILITY = '''    if (["BTC", "ETH"].includes(value)) {\n      return {tier: "OPTIONS RESEARCH + UNDERLYING AUTO PAPER", kind: "auto", source: "DERIBIT RESEARCH + CANONICAL PAPER DESK", detail: "Deribit option contracts remain research-only. BTC/ETH underlying paper entries are autonomous through the canonical Paper Desk after fresh strategy, risk and capital gates pass."};\n    }\n'''

OLD_CAPABILITY_CARD = '''<div class="v16-cap-row research"><strong>BTC / ETH · PUBLIC RESEARCH</strong><span>Verified Deribit public option chain is selectable. No separate crypto paper ledger is used in V16.</span></div>'''
NEW_CAPABILITY_CARD = '''<div class="v16-cap-row auto"><strong>BTC / ETH / SOL · UNDERLYING AUTO PAPER</strong><span>Canonical Paper Desk can autonomously open and manage verified crypto underlying PAPER positions. Deribit options remain research-only.</span></div>'''

OLD_POSITION_HEAD = '''    const positions = Array.isArray(state?.positions) ? state.positions.filter(isOptionPosition) : [];\n    const underlying = selectedUnderlying(); const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying); const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying); const host = $("v16OptionsOpenPosition");\n    if (!host) return;\n'''
NEW_POSITION_HEAD = '''    const allPositions = Array.isArray(state?.positions) ? state.positions : [];\n    const positions = allPositions.filter(isOptionPosition);\n    const underlying = selectedUnderlying(); const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying); const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying); const host = $("v16OptionsOpenPosition");\n    if (!host) return;\n    const cryptoUnderlying = ["BTC", "ETH", "SOL"].includes(underlying)\n      ? allPositions.find(item => String(item?.symbol || "").toUpperCase() === underlying && !isOptionPosition(item))\n      : null;\n    if (cryptoUnderlying) {\n      host.innerHTML = `<b>${esc(underlying)} UNDERLYING PAPER POSITION OPEN</b><br>${esc(cryptoUnderlying.side || "—")} · qty ${esc(cryptoUnderlying.quantity ?? "—")}<br>entry ${esc(cryptoUnderlying.entry ?? cryptoUnderlying.entry_price ?? "—")} · mark ${esc(cryptoUnderlying.mark ?? "—")}<br>SL ${esc(cryptoUnderlying.stop ?? "—")} · target ${esc(cryptoUnderlying.target ?? "—")}<div class="v16-option-provenance"><strong>CANONICAL PAPER DESK</strong> · autonomous crypto underlying; Deribit options remain research-only.</div>`;\n      return;\n    }\n'''


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing a partial crypto-paper patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")


def replace_all_once(path: Path, old: str, new: str, expected_minimum: int, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print(f"V17 {label} patch already present.")
        return
    count = text.count(old)
    if count < expected_minimum:
        raise SystemExit(f"Expected {label} blocks were not found; refusing a partial crypto-paper patch.")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"Applied V17 {label} patch to {count} block(s).")


def main() -> int:
    replace_once(HTTP_TARGET, OLD_IMPORT, NEW_IMPORT, "crypto lane import")
    replace_once(HTTP_TARGET, OLD_CONTROL_TAIL, NEW_CONTROL_TAIL, "one-touch crypto lane control")
    replace_once(HTTP_TARGET, OLD_START_MESSAGE, NEW_START_MESSAGE, "one-touch crypto start message")
    replace_all_once(HTTP_TARGET, OLD_STATUS_PREF, NEW_STATUS_PREF, 2, "crypto lane status exposure")
    replace_once(ROUTER_TARGET, OLD_CAPABILITY, NEW_CAPABILITY, "crypto capability routing")
    replace_once(ROUTER_TARGET, OLD_CAPABILITY_CARD, NEW_CAPABILITY_CARD, "crypto capability card")
    replace_once(ROUTER_TARGET, OLD_POSITION_HEAD, NEW_POSITION_HEAD, "crypto underlying open-position card")
    print("V17 canonical crypto-underlying PAPER patches complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
