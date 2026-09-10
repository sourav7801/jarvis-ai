"""Workspace capital and session control on the existing Paper Desk ledger.

All admission calls execute inside PaperTradingDesk's BEGIN IMMEDIATE
transaction. No independent broker, balance or order authority is created.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from omni.trading_intelligence.backtest_schema import ExecutionCostConfig
from omni.trading_intelligence.cost_model import ExecutionCostModel
from workstation.paper_instrument_accounting import normalized_price_grid, quantize_quantity

WORKSPACES = ("INTRADAY", "SWING", "INVESTMENT")
DEFAULT_ALLOCATIONS = {"INTRADAY": .5, "SWING": .3, "INVESTMENT": .2}
DEFAULT_LIMITS = {
    "risk_per_trade": .01, "open_risk": .04, "daily_loss": .02,
    "concentration": .40, "max_positions": 4,
}
# Conservative paper assumptions, not a representation of a broker tariff.
# The user can replace these with the applicable segment-specific estimates.
DEFAULT_COSTS = {
    "brokerage_bps": 3., "exchange_bps": 1., "other_bps": 1.,
    "tax_bps_buy": 2., "tax_bps_sell": 15., "fixed_per_order": 20.,
    "per_contract": 0., "slippage_bps": 5., "spread_bps": 5.,
}


def number(value: Any, default: float = 0.) -> float:
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def workspace(bucket: str) -> str:
    token = str(bucket or "GENERAL").upper()
    if token.startswith("INTRADAY") or token == "GENERAL":
        return "INTRADAY"
    return token if token in WORKSPACES else "INTRADAY"


def enabled(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='terminal_workspaces'").fetchone() is not None


def is_enabled(desk) -> bool:
    with desk._lock, desk._connection() as conn:
        return enabled(conn)


def initialize(desk) -> None:
    with desk._lock, desk._connection() as conn:
        for sql in (
            "CREATE TABLE IF NOT EXISTS terminal_capital (id INTEGER PRIMARY KEY CHECK(id=1), funded_capital REAL NOT NULL)",
            "CREATE TABLE IF NOT EXISTS terminal_workspaces (workspace TEXT PRIMARY KEY, allocation REAL NOT NULL, state TEXT NOT NULL DEFAULT 'PAUSED', generation INTEGER NOT NULL DEFAULT 0, settings_json TEXT NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS terminal_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, external_id TEXT, position_id INTEGER, status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, payload_json TEXT NOT NULL)",
            "CREATE UNIQUE INDEX IF NOT EXISTS terminal_order_keys ON terminal_orders(external_id) WHERE external_id IS NOT NULL AND status='FILLED'",
            "CREATE TABLE IF NOT EXISTS terminal_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT NOT NULL, kind TEXT NOT NULL, symbol TEXT NOT NULL, body_json TEXT NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS terminal_daily (workspace TEXT NOT NULL, day TEXT NOT NULL, opening_equity REAL NOT NULL, PRIMARY KEY(workspace,day))",
            "CREATE INDEX IF NOT EXISTS terminal_position_events ON paper_events(position_id,event_type)",
        ):
            conn.execute(sql)
        conn.execute("INSERT OR IGNORE INTO terminal_capital(id,funded_capital) VALUES(1,?)", (desk.starting_equity,))
        desk.starting_equity = conn.execute("SELECT funded_capital FROM terminal_capital WHERE id=1").fetchone()[0]
        if "kind" not in {r[1] for r in conn.execute("PRAGMA table_info(terminal_orders)")}:
            conn.execute("ALTER TABLE terminal_orders ADD COLUMN kind TEXT NOT NULL DEFAULT 'ENTRY'")
        columns = {r[1] for r in conn.execute("PRAGMA table_info(terminal_workspaces)")}
        for column, kind in (("last_equity", "REAL"), ("last_equity_day", "TEXT")):
            if column not in columns:
                conn.execute(f"ALTER TABLE terminal_workspaces ADD COLUMN {column} {kind}")
        for name, allocation in DEFAULT_ALLOCATIONS.items():
            settings = {**DEFAULT_LIMITS, "costs": DEFAULT_COSTS,
                        "symbols": ["NIFTY", "BANKNIFTY", "SENSEX", "NSE:RELIANCE-EQ", "NSE:HDFCBANK-EQ"],
                        "profile": "adaptive_intraday" if name == "INTRADAY" else name.lower()}
            conn.execute("INSERT OR IGNORE INTO terminal_workspaces(workspace,allocation,settings_json,updated_at) VALUES(?,?,?,?)",
                         (name, allocation, json.dumps(settings), datetime.now(timezone.utc).isoformat()))


def session(desk, name: str) -> dict:
    with desk._lock, desk._connection() as conn:
        if not enabled(conn):
            return {}
        row = conn.execute("SELECT * FROM terminal_workspaces WHERE workspace=?", (workspace(name),)).fetchone()
        return {**dict(row), "settings": json.loads(row["settings_json"])} if row else {}


def set_session(desk, name: str, running: bool) -> dict:
    if name not in WORKSPACES:
        raise ValueError("Unknown workspace")
    with desk._lock, desk._connection() as conn:
        conn.execute("UPDATE terminal_workspaces SET state=?,generation=generation+1,updated_at=? WHERE workspace=?",
                     ("RUNNING" if running else "PAUSED", datetime.now(timezone.utc).isoformat(), name))
    return session(desk, name)


def reset_sessions(desk) -> None:
    # Restart restores positions and preferences, but never replays start intent.
    with desk._lock, desk._connection() as conn:
        conn.execute("UPDATE terminal_workspaces SET state='PAUSED',generation=generation+1")


def account_snapshot(desk, conn) -> dict:
    desk.starting_equity = conn.execute("SELECT funded_capital FROM terminal_capital WHERE id=1").fetchone()[0]
    sessions = {r["workspace"]: dict(r) for r in conn.execute("SELECT * FROM terminal_workspaces")}
    result = {}
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    for name, state in sessions.items():
        capital = desk.starting_equity * state["allocation"]
        result[name] = {"workspace": name, "allocation": state["allocation"], "starting_capital": capital,
                        "realized_pnl": 0., "unrealized_pnl": 0., "daily_pnl": 0., "committed_capital": 0.,
                        "open_risk": 0., "unbooked_entry_fees": 0., "positions": [], "settings": json.loads(state["settings_json"]),
                        "session": state["state"], "generation": state["generation"]}
    for row in conn.execute("SELECT * FROM paper_positions"):
        metadata = desk._metadata(row)
        a = result[workspace(metadata.get("portfolio_bucket"))]
        a["realized_pnl"] += number(row["realized_pnl"])
        legs = metadata.get("scale_outs") or []
        for leg in legs:
            if str(leg.get("at") or "") >= day_start:
                a["daily_pnl"] += number(leg.get("pnl"))
        if row["status"] != "OPEN":
            if str(row["closed_at"] or "") >= day_start:
                a["daily_pnl"] += number(metadata.get("final_leg_pnl") if legs else row["realized_pnl"])
            continue
        accounting = desk._accounting(metadata)
        mult = accounting["position_multiplier"]
        qty, entry = number(row["quantity"]), number(row["entry"])
        mark = number(metadata.get("last_mark"), entry)
        pnl = desk._pnl(row["side"], entry, mark, qty) * mult - accounting["entry_fees"]
        a["unrealized_pnl"] += pnl
        a["unbooked_entry_fees"] += accounting["entry_fees"]
        # Day loss includes overnight positions' change since session start
        # when available; conservative full open P&L is the fallback.
        a["daily_pnl"] += pnl if str(row["opened_at"]) >= day_start else min(pnl, 0.)
        margin_unit = number(metadata.get("capital_per_unit"), entry * mult)
        a["committed_capital"] += margin_unit * qty + accounting["entry_fees"]
        direction = 1 if row["side"] == "LONG" else -1
        risk = max(0., (entry - number(row["stop"], entry)) * direction) * qty * mult
        # Include estimated exit friction and fees in open risk.
        cost_cfg = metadata.get("execution_cost_config")
        if cost_cfg:
            cost = ExecutionCostModel(ExecutionCostConfig(**cost_cfg)).execution(number(row["stop"], entry), "sell" if direction == 1 else "buy", qty, mult)
            risk += cost["fees"] + cost["friction_cost"] + accounting["entry_fees"]
        a["open_risk"] += risk
        a["positions"].append({**dict(row), "metadata": metadata, "mark": mark, "unrealized_pnl": pnl,
                               "capital_allocated": margin_unit * qty, "capital_at_risk": risk})
    for a in result.values():
        a["equity"] = a["starting_capital"] + a["realized_pnl"] + a["unrealized_pnl"]
        # Fees are already reserved in committed capital. Reserve additional
        # adverse mark movement without charging those fees a second time.
        a["mark_loss_reserve"] = max(0., -(a["unrealized_pnl"] + a["unbooked_entry_fees"]))
        a["available_capital"] = max(0., a["starting_capital"] + a["realized_pnl"] - a["committed_capital"] - a["mark_loss_reserve"])
        prior = sessions[a["workspace"]]
        opening = a["equity"] - a["daily_pnl"]
        if prior.get("last_equity_day") and prior["last_equity_day"] < now.date().isoformat():
            # Carry forward the last persisted valuation. Do not charge an
            # overnight position's cumulative loss again each morning.
            opening = number(prior.get("last_equity"), a["equity"])
        conn.execute("INSERT OR IGNORE INTO terminal_daily(workspace,day,opening_equity) VALUES(?,?,?)", (a["workspace"], now.date().isoformat(), opening))
        baseline = conn.execute("SELECT opening_equity FROM terminal_daily WHERE workspace=? AND day=?", (a["workspace"], now.date().isoformat())).fetchone()[0]
        a["daily_pnl"] = a["equity"] - baseline
        a["daily_pnl_basis"] = "EQUITY_CHANGE_FROM_PERSISTED_DAILY_BASELINE"
        a["daily_loss_limit"] = a["starting_capital"] * a["settings"]["daily_loss"]
        conn.execute("UPDATE terminal_workspaces SET last_equity=?,last_equity_day=? WHERE workspace=?", (a["equity"], now.date().isoformat(), a["workspace"]))
    return result


def reconcile(desk, conn, *, integrity=False) -> dict:
    """Read-only cross-check of the order, event and position authorities."""
    issues = []
    if integrity and conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        issues.append("SQLITE_INTEGRITY_FAILURE")
    allocations = [r[0] for r in conn.execute("SELECT allocation FROM terminal_workspaces")]
    if len(allocations) != 3 or any(not math.isfinite(v) or v <= 0 for v in allocations) or abs(sum(allocations)-1) > 1e-9:
        issues.append("WORKSPACE_ALLOCATION_MISMATCH")
    for r in conn.execute("SELECT o.id FROM terminal_orders o LEFT JOIN paper_positions p ON p.id=o.position_id WHERE o.status='FILLED' AND (p.id IS NULL OR (o.kind='ENTRY' AND o.external_id IS NOT p.external_id))"):
        issues.append("ORDER_POSITION_MISMATCH:" + str(r[0]))
    for r in conn.execute("SELECT p.id FROM paper_positions p WHERE json_extract(p.metadata_json,'$.workspace_sizing') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM terminal_orders o WHERE o.position_id=p.id AND o.status='FILLED' AND o.kind='ENTRY')"):
        issues.append("POSITION_WITHOUT_FILLED_ORDER:" + str(r[0]))
    for r in conn.execute("SELECT p.id FROM paper_positions p WHERE NOT EXISTS (SELECT 1 FROM paper_events e WHERE e.position_id=p.id AND e.event_type='OPEN') OR (p.status='CLOSED' AND NOT EXISTS (SELECT 1 FROM paper_events e WHERE e.position_id=p.id AND e.event_type='CLOSE'))"):
        issues.append("POSITION_EVENT_MISMATCH:" + str(r[0]))
    return {"success": not issues, "issues": issues[:100], "issue_count": len(issues), "checked_at": datetime.now(timezone.utc).isoformat(), "authority": "PAPER_DESK_SQLITE"}


def configure(desk, name: str, settings: dict | None = None, allocations: dict | None = None) -> dict:
    with desk._lock, desk._connection() as conn:
        accounts = account_snapshot(desk, conn)
        if any(a["session"] == "RUNNING" for a in accounts.values()):
            raise ValueError("Pause entry sessions before changing capital or risk settings")
        if allocations is not None:
            if set(allocations) != set(WORKSPACES) or any(not math.isfinite(float(v)) or not 0 < float(v) <= 1 for v in allocations.values()) or abs(sum(float(v) for v in allocations.values()) - 1) > 1e-9:
                raise ValueError("Three finite allocations must total 1")
            # Prevent moving capital that is committed, or transferring P&L.
            if any(a["positions"] for a in accounts.values()):
                raise ValueError("Capital allocations can change only when all paper positions are flat")
            for key, value in allocations.items():
                conn.execute("UPDATE terminal_workspaces SET allocation=? WHERE workspace=?", (float(value), key))
                conn.execute("UPDATE terminal_daily SET opening_equity=opening_equity+? WHERE workspace=? AND day=?", (desk.starting_equity * (float(value) - accounts[key]["allocation"]), key, datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()))
        if settings is not None:
            if name not in WORKSPACES or set(settings) - {*DEFAULT_LIMITS, "symbols", "costs"}:
                raise ValueError("Unknown workspace setting")
            current = dict(accounts[name]["settings"])
            for key in DEFAULT_LIMITS:
                if key in settings:
                    value = float(settings[key])
                    upper = 20 if key == "max_positions" else 1
                    if not math.isfinite(value) or not 0 < value <= upper or (key == "max_positions" and value != int(value)):
                        raise ValueError("Invalid " + key)
                    current[key] = value
            if "symbols" in settings:
                symbols = settings["symbols"]
                if not isinstance(symbols, list) or not 1 <= len(symbols) <= 30 or any(not isinstance(s, str) or not s.strip() or len(s) > 80 for s in symbols):
                    raise ValueError("Choose between 1 and 30 instruments")
                from workstation.quant_terminal_v2 import normalize_symbol
                current["symbols"] = list(dict.fromkeys(normalize_symbol(s) for s in symbols))
            if "costs" in settings:
                costs = settings["costs"]
                if not isinstance(costs, dict) or set(costs) != set(DEFAULT_COSTS) or any(not math.isfinite(float(v)) or not 0 <= float(v) <= 1000 for v in costs.values()):
                    raise ValueError("Provide nonnegative finite paper cost assumptions")
                current["costs"] = {k: float(v) for k, v in costs.items()}
            conn.execute("UPDATE terminal_workspaces SET settings_json=? WHERE workspace=?", (json.dumps(current), name))
    return session(desk, name)


def plan_admission(desk, conn, request: dict) -> tuple[dict, dict]:
    """Size against current cash and risk; never promote confidence to odds."""
    name = workspace(request.get("portfolio_bucket"))
    a = account_snapshot(desk, conn)[name]
    cfg = a["settings"]
    meta = dict(request.get("metadata") or {})
    def reject(reason):
        return request, {"success": False, "reason": reason, "workspace": name, "paper_only": True, "live_execution": False}
    if a["session"] != "RUNNING":
        return reject("WORKSPACE_PAUSED")
    if not reconcile(desk, conn)["success"]:
        return reject("LEDGER_RECONCILIATION_REQUIRED")
    if meta.get("session_generation") != a["generation"]:
        return reject("SESSION_TICKET_EXPIRED")
    from workstation.terminal_data import quote_certificate
    certificate = quote_certificate(str(request.get("symbol") or ""), meta.get("entry_certificate") or {})
    if not certificate.get("eligible_for_entry"):
        return reject(certificate.get("reason") or "LIVE_ENTRY_CERTIFICATE_REQUIRED")
    if a["daily_pnl"] <= -a["daily_loss_limit"]:
        return reject("WORKSPACE_DAILY_LOSS_LIMIT")
    if len(a["positions"]) >= cfg["max_positions"]:
        return reject("WORKSPACE_POSITION_LIMIT")
    symbol = str(request.get("symbol") or "").upper()
    if any(p["symbol"] == symbol for p in a["positions"]):
        return reject("WORKSPACE_SYMBOL_ALREADY_OPEN")
    underlying = str(meta.get("underlying") or symbol).upper()
    if any(str(p["metadata"].get("underlying") or p["symbol"]).upper() == underlying for p in a["positions"]):
        return reject("WORKSPACE_UNDERLYING_ALREADY_OPEN")
    spec = request.get("instrument_spec") or {}
    if not spec.get("verified") or number(spec.get("quantity_step")) <= 0 or number(spec.get("contract_multiplier")) <= 0:
        return reject("VERIFIED_INSTRUMENT_SPEC_REQUIRED")
    if str(spec.get("instrument_type")).upper() in {"SYNTHETIC_INDEX", "INDEX"}:
        return reject("INDEX_REFERENCE_ONLY_SELECT_TRADEABLE_CONTRACT")
    side = str(request.get("side") or "").upper()
    side = {"BUY": "LONG", "SELL": "SHORT"}.get(side, side)
    if side not in {"LONG", "SHORT"}:
        return reject("INVALID_SIDE")
    kind = str(spec.get("instrument_type") or "SPOT").upper()
    if side == "SHORT" and (kind == "OPTION" or name != "INTRADAY"):
        return reject("SHORT_NOT_SUPPORTED_FOR_THIS_MANDATE")
    if str(spec.get("symbol") or "").upper() != symbol:
        return reject("INSTRUMENT_MAPPING_MISMATCH")
    live_reference = number(certificate.get("ask") if side == "LONG" else certificate.get("bid"), number(certificate.get("mark")))
    decision_entry = number(request.get("entry"))
    if decision_entry <= 0 or abs(live_reference - decision_entry) / decision_entry > .005:
        return reject("LIVE_ENTRY_DRIFT_TOO_LARGE")
    entry, stop, target = normalized_price_grid(side=side, entry=live_reference, stop=number(request.get("stop")), target=number(request.get("target")), tick_size=spec.get("tick_size"))
    if min(entry, stop, target) <= 0 or not (stop < entry < target if side == "LONG" else target < entry < stop):
        return reject("INVALID_RISK_LEVELS")
    mult = number(spec.get("contract_multiplier")) * number(request.get("valuation_multiplier"), 1)
    if mult <= 0:
        return reject("INVALID_VALUATION_MULTIPLIER")
    costs = dict(cfg["costs"])
    # A verified current bid/ask spread can only increase the conservative
    # spread assumption, never silently remove transaction costs.
    quote = meta.get("entry_certificate") or {}
    costs["spread_bps"] = max(costs["spread_bps"], number(quote.get("spread_bps")))
    model = ExecutionCostModel(ExecutionCostConfig(**costs))
    buy = side == "LONG"
    fill = model.fill(entry, "buy" if buy else "sell")["fill_price"]
    if not (stop < fill < target if buy else target < fill < stop):
        return reject("FILL_OUTSIDE_SETUP")
    stop_fill = model.fill(stop, "sell" if buy else "buy")["fill_price"]
    risk_unit = abs(fill - stop_fill) * mult
    fixed = 2 * costs["fixed_per_order"]
    fee_unit = (model.fees(fill, 1, mult, "buy" if buy else "sell")["total"] + model.fees(stop_fill, 1, mult, "sell" if buy else "buy")["total"] - fixed)
    risk_unit += fee_unit
    capital_unit = fill * mult
    if kind in {"FUTURE", "COMMODITY", "DERIVATIVE"}:
        if not spec.get("margin_verified") or number(spec.get("margin_per_unit")) <= 0:
            return reject("VERIFIED_MARGIN_REQUIRED")
        capital_unit = number(spec["margin_per_unit"]) * number(request.get("valuation_multiplier"), 1)
    entry_fee_unit = model.fees(fill, 1, mult, "buy" if buy else "sell")["total"] - costs["fixed_per_order"]
    # The existing evidence engine contributes a bounded heuristic only. Until
    # held-out calibration evidence exists, cap its risk weight at 25%.
    requested_weight = max(0., min(number(request.get("risk_multiplier"), 0.), 1.))
    # Caller-supplied calibration metadata is not independent validation.
    # Increasing this cap requires a separately verified calibration registry.
    weight = min(requested_weight, .25)
    equity = max(0., min(a["equity"], a["starting_capital"] + a["realized_pnl"]))
    risk_budget = equity * cfg["risk_per_trade"] * weight
    caps = {
        "Risk per trade including costs": max(0., risk_budget - fixed) / risk_unit,
        "Total workspace open risk": max(0., equity * cfg["open_risk"] - a["open_risk"] - fixed) / risk_unit,
        "Daily loss headroom": max(0., a["daily_loss_limit"] + min(0., a["daily_pnl"]) - a["open_risk"] - fixed) / risk_unit,
        "Available workspace capital": max(0., a["available_capital"] - costs["fixed_per_order"]) / (capital_unit + entry_fee_unit),
        "Instrument concentration": equity * cfg["concentration"] / (fill * mult),
    }
    if request.get("quantity") is not None:
        caps["Requested quantity"] = max(0., number(request["quantity"]))
    limiting = min(caps, key=caps.get)
    qty = quantize_quantity(min(caps.values()), number(spec["quantity_step"]))
    if qty <= 0:
        return reject("INSUFFICIENT_CAPITAL_OR_RISK_FOR_ONE_LOT")
    plan = {"quantity": qty, "capital_allocated": capital_unit * qty,
            "capital_at_risk": risk_unit * qty + fixed, "risk_budget": risk_budget,
            "risk_weight": weight, "confidence_status": "UNCALIBRATED_EVIDENCE_WEIGHT_NOT_WIN_PROBABILITY",
            "limiting_constraint": limiting, "quantity_caps": caps, "cost_assumptions": costs,
            "cost_status": "CONFIGURABLE_CONSERVATIVE_PAPER_ESTIMATE", "available_capital_before": a["available_capital"],
            "quantity_step": spec["quantity_step"], "contract_multiplier": spec["contract_multiplier"]}
    request = {**request, "quantity": qty, "entry": entry, "stop": stop, "target": target,
               "execution_cost_config": costs, "risk_multiplier": max(weight, .1),
               "metadata": {**meta, "workspace_sizing": plan, "capital_per_unit": capital_unit}}
    return request, {"success": True, "sizing": plan}
