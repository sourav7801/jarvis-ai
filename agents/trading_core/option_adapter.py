
from __future__ import annotations

import importlib
from typing import Any, Dict


class OptionAdapter:
    """
    Best-effort bridge to the existing option paper monitor.
    It never places a live order.
    """

    def status(self, symbol: str) -> Dict[str, Any]:
        try:
            mod = importlib.import_module("agents.option_paper_monitor")
        except Exception as exc:
            return {"available": False, "error": str(exc)}

        # Try common public entry points without assuming private internals.
        for name in ("scan_symbol", "get_symbol_setup", "analyze_symbol"):
            fn = getattr(mod, name, None)
            if callable(fn):
                try:
                    result = fn(symbol)
                    if isinstance(result, dict):
                        return {"available": True, "source": name, "result": result}
                except Exception:
                    pass

        return {
            "available": False,
            "reason": "Existing option_paper_monitor has no compatible public scan function yet.",
        }
