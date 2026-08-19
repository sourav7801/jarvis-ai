from __future__ import annotations

import re
from typing import Any

_UNIVERSE_RE = re.compile(
    r"\b(?:scan|analy[sz]e|check|rank|find\s+setups?|find\s+trades?)\b.*\b(?:all\s+supported\s+markets|all\s+markets|entire\s+market|multi[-\s]?market|universe)\b",
    flags=re.IGNORECASE,
)


def is_universe_scan_request(text: str) -> bool:
    return bool(_UNIVERSE_RE.search(str(text or "")))


def scan_all_supported_markets(timeframe: str = "5m") -> dict[str, Any]:
    from workstation.quant_firm_runtime import scan_universe_payload

    payload = scan_universe_payload(timeframe=timeframe)
    rows = list(payload.get("results") or [])
    qualified = [
        row
        for row in rows
        if row.get("success")
        and str(row.get("side") or row.get("decision") or "").upper() not in {"", "WAIT", "FLAT"}
        and float(row.get("score") or 0.0) >= 64.0
    ]
    payload["qualified"] = qualified
    payload["qualified_count"] = len(qualified)
    payload["scanned_count"] = len(rows)
    payload["route"] = "QUANT_UNIVERSE_SCAN"
    payload["paper_only"] = True
    payload["live_execution"] = False
    return payload


def format_universe_scan(payload: dict[str, Any]) -> str:
    rows = list(payload.get("results") or [])
    qualified = list(payload.get("qualified") or [])
    lines = [
        "JARVIS QUANT UNIVERSE SCAN",
        "--------------------------------------------------",
        f"Markets scanned: {len(rows)}",
        f"Qualified setups: {len(qualified)}",
        f"Timeframe: {payload.get('timeframe') or '5m'}",
        "",
    ]
    if not qualified:
        lines.append("No setup currently clears the Quant Firm score/risk threshold.")
    else:
        lines.append("QUALIFIED PAPER CANDIDATES")
        for row in qualified[:10]:
            side = str(row.get("side") or row.get("decision") or "").upper()
            lines.append(
                f"- {row.get('symbol')}: {side} | score={float(row.get('score') or 0):.1f} | regime={row.get('regime') or 'UNKNOWN'}"
            )
    lines.extend([
        "",
        "This is a multi-market Quant scan, not a live order instruction.",
        "Live broker execution remains locked.",
    ])
    return "\n".join(lines)


def universe_command_payload(text: str) -> dict[str, Any] | None:
    if not is_universe_scan_request(text):
        return None
    payload = scan_all_supported_markets()
    payload["action"] = "quant_universe_scan"
    payload["speech"] = format_universe_scan(payload)
    return payload
