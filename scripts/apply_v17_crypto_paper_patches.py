from __future__ import annotations

"""Verify/complete the V17 crypto-underlying PAPER presentation boundary.

The canonical HTTP/start-stop/status integration is now committed source and is
verified here rather than manufactured only at startup/CI.  The inherited V16
options router still receives an idempotent presentation compatibility patch so
BTC/ETH/SOL underlying PAPER exposure is visible beside Deribit research.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTTP_TARGET = ROOT / "workstation" / "v17_terminal_http.py"
ROUTER_TARGET = ROOT / "workstation" / "quant_terminal_v2_static" / "v16_workspace_router.js"

HTTP_REQUIRED = (
    "from workstation.v17_crypto_paper_lane import crypto_paper_lane",
    'results["CRYPTO_UNDERLYING"]',
    '"crypto_underlying_paper": crypto_status',
    "_crypto_lane_status()",
    '"/v17_crypto_paper_runtime.js"',
)

OLD_CAPABILITY = '''    if (["BTC", "ETH"].includes(value)) {\n      return {tier: "PUBLIC RESEARCH", kind: "research", source: "DERIBIT PUBLIC OPTIONS", detail: "Verified Deribit public option-chain research is available. V16 does not use the older separate crypto paper-intent ledger."};\n    }\n'''
NEW_CAPABILITY = '''    if (["BTC", "ETH"].includes(value)) {\n      return {tier: "OPTIONS RESEARCH + UNDERLYING AUTO PAPER", kind: "auto", source: "DERIBIT RESEARCH + CANONICAL PAPER DESK", detail: "Deribit option contracts remain research-only. BTC/ETH underlying paper entries are autonomous through the canonical Paper Desk after fresh strategy, risk and capital gates pass."};\n    }\n'''

OLD_CAPABILITY_CARD = '''<div class="v16-cap-row research"><strong>BTC / ETH · PUBLIC RESEARCH</strong><span>Verified Deribit public option chain is selectable. No separate crypto paper ledger is used in V16.</span></div>'''
NEW_CAPABILITY_CARD = '''<div class="v16-cap-row auto"><strong>BTC / ETH / SOL · UNDERLYING AUTO PAPER</strong><span>Canonical Paper Desk can autonomously open and manage verified crypto underlying PAPER positions. Deribit options remain research-only.</span></div>'''

OLD_POSITION_HEAD = '''    const positions = Array.isArray(state?.positions) ? state.positions.filter(isOptionPosition) : [];\n    const underlying = selectedUnderlying(); const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying); const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying); const host = $("v16OptionsOpenPosition");\n    if (!host) return;\n'''
NEW_POSITION_HEAD = '''    const allPositions = Array.isArray(state?.positions) ? state.positions : [];\n    const positions = allPositions.filter(isOptionPosition);\n    const underlying = selectedUnderlying(); const matching = positions.filter(item => optionUnderlyingFromPosition(item) === underlying); const other = positions.filter(item => optionUnderlyingFromPosition(item) !== underlying); const host = $("v16OptionsOpenPosition");\n    if (!host) return;\n    const cryptoUnderlying = ["BTC", "ETH", "SOL"].includes(underlying)\n      ? allPositions.find(item => String(item?.symbol || "").toUpperCase() === underlying && !isOptionPosition(item))\n      : null;\n    if (cryptoUnderlying) {\n      host.innerHTML = `<b>${esc(underlying)} UNDERLYING PAPER POSITION OPEN</b><br>${esc(cryptoUnderlying.side || "—")} · qty ${esc(cryptoUnderlying.quantity ?? "—")}<br>entry ${esc(cryptoUnderlying.entry ?? cryptoUnderlying.entry_price ?? "—")} · mark ${esc(cryptoUnderlying.mark ?? "—")}<br>SL ${esc(cryptoUnderlying.stop ?? "—")} · target ${esc(cryptoUnderlying.target ?? "—")}<div class="v16-option-provenance"><strong>CANONICAL PAPER DESK</strong> · autonomous crypto underlying; Deribit options remain research-only.</div>`;\n      return;\n    }\n'''


def verify_committed_http_integration() -> None:
    text = HTTP_TARGET.read_text(encoding="utf-8")
    missing = [marker for marker in HTTP_REQUIRED if marker not in text]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            "Committed V17 crypto HTTP integration is incomplete; refusing to manufacture "
            f"execution authority only at startup. Missing: {joined}"
        )
    print("Verified committed V17 crypto HTTP/start-stop/status integration.")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"V17 {label} patch already present.")
        return
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found; refusing a partial crypto-paper patch.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied V17 {label} patch.")


def main() -> int:
    verify_committed_http_integration()
    replace_once(ROUTER_TARGET, OLD_CAPABILITY, NEW_CAPABILITY, "crypto capability routing")
    replace_once(ROUTER_TARGET, OLD_CAPABILITY_CARD, NEW_CAPABILITY_CARD, "crypto capability card")
    replace_once(ROUTER_TARGET, OLD_POSITION_HEAD, NEW_POSITION_HEAD, "crypto underlying open-position card")
    print("V17 canonical crypto-underlying PAPER guard complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
