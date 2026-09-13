"""Explicit paper-book reconciliation. No broker-order clients or entry engine.

SQLite commits the immutable resolution receipt before JSON is acknowledged.
An interrupted acknowledgement remains an exposure blocker and can be retried
without another position/fill. Legacy writers use the same SQLite write lock.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from workstation import terminal_ledger_guard as guard, workspace_accounts as accounts
from workstation.terminal_data import quote_certificate

SAFETY = dict(paper_only=True, live_execution=False, automatic_broker_order=False,
              live_orders_locked=True, naked_option_selling=False)


def result(success, reason, **fields):
    return dict(success=success, reason=reason, **fields, **SAFETY)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def identity(record):
    summary = guard._legacy_position_summary(record, 0)
    immutable = {k: summary[k] for k in ("symbol", "side", "quantity", "entry_price", "opened_at")}
    source_id = guard._first_scalar(record, "id", "position_id")
    return _digest([str(guard.LEGACY_ACCOUNT.resolve()), source_id if source_id is not None else immutable])


def _read_source():
    data = json.loads(guard.LEGACY_ACCOUNT.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("positions"), list):
        raise ValueError("Unsupported legacy book schema")
    return data


def _schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS legacy_position_resolutions (
        fingerprint TEXT PRIMARY KEY, action TEXT NOT NULL, workspace TEXT NOT NULL,
        source TEXT NOT NULL, revision TEXT NOT NULL, record_json TEXT NOT NULL,
        audit_json TEXT NOT NULL, position_id INTEGER, acknowledged INTEGER NOT NULL DEFAULT 0
    )""")


def _receipts(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='legacy_position_resolutions'").fetchone():
        return []
    return [dict(r) for r in conn.execute("SELECT * FROM legacy_position_resolutions")]


def _expiry(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
        if number > 1e12:
            number /= 1000
        return datetime.fromtimestamp(number, timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            return None


def instrument_status(symbol):
    """Exact provider lookup only; a missing listing is UNRESOLVED, not delisted."""
    try:
        if re.fullmatch(r"(NSE|BSE):[A-Z0-9._-]+(CE|PE)", symbol):
            from workstation.v16_option_paper import option_instrument_spec
            spec = option_instrument_spec(symbol)
        elif re.fullmatch(r"MCX:[A-Z0-9._-]+(CE|PE|FUT)", symbol):
            import csv
            import io
            from workstation.paper_market_data import PAPER_MARKET_DATA, MCX_SYMBOL_MASTER
            row = next((r for r in csv.reader(io.StringIO(PAPER_MARKET_DATA._master(MCX_SYMBOL_MASTER)))
                        if len(r) > 13 and r[9].strip() == symbol), None)
            if row is None:
                return dict(status="UNRESOLVED", reason="EXACT_CONTRACT_NOT_IN_PROVIDER_MASTER", spec={})
            multiplier, tick = _number(row[3]), _number(row[4])
            spec = dict(symbol=symbol,provider_symbol=symbol,instrument_type="OPTION" if symbol.endswith(("CE","PE")) else "FUTURE",
                        asset_class="OPTION" if symbol.endswith(("CE","PE")) else "COMMODITY",contract_multiplier=multiplier,
                        quantity_step=1.,tick_size=tick,expiry=row[8],source="FYERS_PUBLIC_SYMBOL_MASTER",verified=bool(multiplier and tick),
                        native_currency="INR",valuation_currency="INR")
        else:
            from workstation.paper_market_data import PAPER_MARKET_DATA
            spec = PAPER_MARKET_DATA.instrument_spec(symbol)
        if not spec.get("verified") or str(spec.get("symbol")) != symbol:
            return dict(status="UNRESOLVED", reason="EXACT_INSTRUMENT_SPEC_UNAVAILABLE", spec={})
        derivative = str(spec.get("instrument_type")).upper() in {"OPTION","FUTURE","DERIVATIVE","COMMODITY"}
        expires = _expiry(spec.get("expiry") or spec.get("expiry_epoch"))
        if derivative and expires is None:
            return dict(status="UNRESOLVED",reason="VERIFIED_EXPIRY_REQUIRED",spec=spec)
        if expires and expires <= datetime.now(timezone.utc):
            return dict(status="EXPIRED",reason="LEGACY_CONTRACT_EXPIRED",spec=spec)
        return dict(status="VALID",reason=None,spec=spec)
    except Exception as exc:
        return dict(status="UNRESOLVED",reason="INSTRUMENT_LOOKUP_UNAVAILABLE:"+type(exc).__name__,spec={})


def verified_exit(runtime, symbol):
    try:
        payload = runtime.mark_loader(symbol)
        # Re-check identity/timestamps/session, not a caller's eligibility flag.
        cert = quote_certificate(symbol, payload if isinstance(payload, dict) else {})
        if not cert.get("eligible_for_exit"):
            return result(False,cert.get("reason") or "QUOTE_UNAVAILABLE")
        return result(True,"VERIFIED_EXIT",certificate=cert)
    except Exception:
        return result(False,"QUOTE_UNAVAILABLE")


def _migration_reason(summary, spec, equivalent):
    if equivalent:
        return "CANONICAL_EXPOSURE_ALREADY_EXISTS"
    if summary["side"] not in {"LONG","SHORT"}:
        return "UNRESOLVED_POSITION_SIDE"
    if summary["side"] == "SHORT" and spec.get("instrument_type") == "OPTION":
        return "NAKED_SHORT_OPTION_BLOCKED"
    if spec.get("native_currency") != "INR" or spec.get("valuation_currency") != "INR":
        return "LEGACY_CURRENCY_BASIS_UNRESOLVED"
    qty, entry = _number(summary["quantity"]), _number(summary["entry_price"])
    if not qty or qty <= 0 or not entry or entry <= 0 or not summary["opened_at"]:
        return "LEGACY_POSITION_FIELDS_INCOMPLETE"
    step = _number(spec.get("quantity_step"))
    # PaperBroker's v2 book accounts in synthetic units, multiplier exactly 1.
    # Importing quantity=1 as a 100-unit option lot would enlarge exposure.
    if _number(spec.get("contract_multiplier")) != 1. or not step or abs(qty / step - round(qty / step)) > 1e-8:
        return "LEGACY_QUANTITY_UNIT_MISMATCH"
    if spec.get("instrument_type") in {"FUTURE","COMMODITY","DERIVATIVE","INDEX","SYNTHETIC_INDEX"}:
        return "LEGACY_MARGIN_OR_CONTRACT_REVIEW_REQUIRED"
    stop, target = _number(summary["stop"]), _number(summary["target"])
    if not stop or not target or min(stop,target) <= 0 or (stop >= target if summary["side"] == "LONG" else target >= stop):
        return "LEGACY_PROTECTION_REVIEW_REQUIRED"
    return None


def legacy_resolution_details(runtime):
    desk = runtime.desk
    if desk.db_path.resolve() != guard.TERMINAL_DB.resolve():
        return result(False,"NOT_CANONICAL_BOOK",positions=[])
    try:
        data = _read_source()
        with desk._lock, desk._connection() as conn:
            canonical = [dict(r) for r in conn.execute("SELECT id,symbol,side,quantity,entry,status FROM paper_positions WHERE status='OPEN'")]
            receipts = {r["fingerprint"]: r for r in _receipts(conn)}
        rows = []
        records = list(data["positions"])
        present = {identity(r) for r in records}
        records.extend(json.loads(r["record_json"]) for fp,r in receipts.items() if not r["acknowledged"] and fp not in present)
        for index, record in enumerate(records[:100], 1):
            summary = guard._legacy_position_summary(record,index)
            fp = identity(record); receipt = receipts.get(fp)
            equivalent = [r["id"] for r in canonical if r["symbol"] == summary["symbol"]]
            info = instrument_status(summary["symbol"])
            migrate_reason = _migration_reason(summary,info.get("spec",{}),equivalent) if info["status"] == "VALID" else info.get("reason") or info["status"]
            close = verified_exit(runtime,summary["symbol"]) if info["status"] == "VALID" else result(False,info.get("reason") or info["status"])
            pending = bool(receipt and not receipt["acknowledged"])
            rows.append({**summary,"fingerprint":fp,"revision":_digest(record),"source":str(guard.LEGACY_ACCOUNT),
                         "instrument_status":info["status"],"instrument_reason":info.get("reason"),"equivalent_position_ids":equivalent,
                         "can_migrate":not migrate_reason or bool(pending and receipt["action"] == "MIGRATE"),"migration_reason":migrate_reason,
                         "can_close":bool(close["success"]) or bool(pending and receipt["action"] == "CLOSE"),"close_reason":None if close["success"] else close["reason"],
                         "pending_action":receipt["action"] if pending else None,"resolved_workspace":receipt["workspace"] if pending else None})
        return result(True,"LEGACY_RESOLUTION_DIAGNOSTICS",positions=rows)
    except (OSError,ValueError,TypeError,KeyError):
        return result(False,"UNREADABLE_LEGACY_RECORDS",positions=[])


def _write_source(data):
    path = guard.LEGACY_ACCOUNT
    fd, temporary = tempfile.mkstemp(prefix=".legacy-resolution-",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(data,stream,indent=2,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def _acknowledge(desk, fingerprint):
    with desk._lock,desk._connection() as conn:
        receipt = next(r for r in _receipts(conn) if r["fingerprint"] == fingerprint)
        if receipt["acknowledged"]:return
        data = _read_source(); audit = json.loads(receipt["audit_json"])
        history = data.setdefault("resolved_positions",[])
        if not isinstance(history,list):raise ValueError("Invalid resolved history")
        acknowledged = any(isinstance(r,dict) and r.get("resolution",{}).get("legacy_fingerprint") == fingerprint for r in history)
        if not acknowledged:
            matches = [r for r in data["positions"] if identity(r) == fingerprint]
            if len(matches) != 1 or _digest(matches[0]) != receipt["revision"]:
                raise ValueError("Legacy record changed; acknowledgement needs review")
            original = matches[0]
            history.append(dict(position=original,resolution=audit))
            data["positions"] = [r for r in data["positions"] if r is not original]
            if receipt["action"] == "CLOSE":
                account = data["account"]
                account["cash"] = float(account["cash"]) + audit["cash_delta"]
                account["realized_pnl"] = float(account.get("realized_pnl",0)) + audit["pnl"]
            data["autopilot"] = False
            data["updated_at"] = audit["timestamp"]
            _write_source(data)
        conn.execute("UPDATE legacy_position_resolutions SET acknowledged=1 WHERE fingerprint=?",(fingerprint,))


def resolve_legacy_position(runtime, body):
    desk = runtime.desk
    action, workspace = str(body.get("action","")).upper(),str(body.get("workspace","")).upper()
    fingerprint,revision = str(body.get("fingerprint","")),str(body.get("revision",""))
    if desk.db_path.resolve() != guard.TERMINAL_DB.resolve():return result(False,"NOT_CANONICAL_BOOK")
    if action not in {"MIGRATE","CLOSE"}:return result(False,"UNSUPPORTED_RESOLUTION_ACTION")
    if workspace not in accounts.WORKSPACES:return result(False,"WORKSPACE_CHOICE_REQUIRED")
    if not re.fullmatch("[a-f0-9]{64}",fingerprint):return result(False,"INVALID_FINGERPRINT")
    try:
        with desk._lock,desk._connection() as conn:
            existing = next((r for r in _receipts(conn) if r["fingerprint"] == fingerprint),None)
        if existing:
            if existing["action"] != action or existing["workspace"] != workspace:return result(False,"RESOLUTION_CONFLICT")
            try:
                _acknowledge(desk,fingerprint)
            except (OSError,ValueError,sqlite3.Error):
                return result(False,"SOURCE_ACK_PENDING",position_id=existing["position_id"],retry_safe=True)
            return result(True,"ALREADY_RESOLVED",idempotent=True,position_id=existing["position_id"])
        data = _read_source()
        matching = [r for r in data["positions"] if identity(r) == fingerprint]
        if len(matching) != 1:return result(False,"LEGACY_RECORD_NOT_UNIQUE")
        record = matching[0]
        if _digest(record) != revision:return result(False,"LEGACY_RECORD_CHANGED")
        summary = guard._legacy_position_summary(record,0);symbol=summary["symbol"]
        info = instrument_status(symbol)
        if info["status"] != "VALID":return result(False,info.get("reason") or "LEGACY_CONTRACT_"+info["status"])
        spec = info["spec"]
        certificate = verified_exit(runtime,symbol) if action == "CLOSE" else None
        if certificate and not certificate["success"]:return certificate
        with desk._lock,desk._connection() as conn:
            _schema(conn)
            if any(r["fingerprint"] == fingerprint for r in _receipts(conn)):
                return result(False,"RESOLUTION_IN_PROGRESS_RETRY")
            current = [r for r in _read_source()["positions"] if identity(r) == fingerprint]
            if len(current) != 1 or _digest(current[0]) != revision:return result(False,"LEGACY_RECORD_CHANGED")
            if data.get("version") != 2:return result(False,"LEGACY_ECONOMICS_UNRESOLVED")
            qty,entry = _number(summary["quantity"]),_number(summary["entry_price"])
            if not qty or qty <= 0 or not entry or entry <= 0 or summary["side"] not in {"LONG","SHORT"}:return result(False,"LEGACY_POSITION_FIELDS_INCOMPLETE")
            stamp=datetime.now(timezone.utc).isoformat();position_id=None
            audit=dict(timestamp=stamp,action=action,legacy_source=str(guard.LEGACY_ACCOUNT),legacy_fingerprint=fingerprint,
                       workspace=workspace,reason="EXPLICIT_USER_LEGACY_RESOLUTION",migration_version=1,**SAFETY)
            if action == "MIGRATE":
                if _number(record.get("realized_pnl",0)) != 0:
                    return result(False,"LEGACY_REALIZED_PNL_REVIEW_REQUIRED")
                equivalent = conn.execute("SELECT id FROM paper_positions WHERE symbol=? AND status='OPEN'",(symbol,)).fetchone()
                reason = _migration_reason(summary,spec,equivalent)
                if reason:return result(False,reason)
                balances = accounts.account_snapshot(desk,conn)[workspace]
                if balances["available_capital"] < entry*qty:return result(False,"INSUFFICIENT_WORKSPACE_CAPITAL")
                meta=dict(legacy_source=str(guard.LEGACY_ACCOUNT),legacy_fingerprint=fingerprint,legacy_migrated_at=stamp,migration_version=1,
                          portfolio_bucket=workspace,instrument_spec=spec,position_multiplier=1.,valuation_multiplier=1.,
                          entry_fees=0.,legacy_fees_retained_in_source=True,initial_risk=abs(entry-float(summary["stop"])),
                          last_mark=entry,last_mark_at=None,legacy_original_summary=summary,**SAFETY)
                cursor=conn.execute("""INSERT INTO paper_positions(external_id,symbol,asset_type,side,quantity,entry,stop,target,timeframe,strategy,source,status,opened_at,realized_pnl,metadata_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",("legacy:"+fingerprint,symbol,spec.get("asset_class","SPOT"),summary["side"],qty,entry,summary["stop"],summary["target"],"","LEGACY_POSITION_IMPORT","LEGACY_RECONCILIATION","OPEN",summary["opened_at"],0.,json.dumps(meta)))
                position_id=int(cursor.lastrowid);audit["canonical_position_id"]=position_id
                desk._event(conn,position_id,"OPEN",dict(reason="BOOKKEEPING_IMPORT_NOT_MARKET_ENTRY",legacy_fingerprint=fingerprint,**SAFETY))
            else:
                cert = quote_certificate(symbol,certificate["certificate"])
                if not cert.get("eligible_for_exit"):return result(False,cert.get("reason") or "QUOTE_UNAVAILABLE")
                price = _number(cert.get("bid") if summary["side"] == "LONG" else cert.get("ask")) or _number(cert.get("mark"))
                if not price or price <= 0:return result(False,"QUOTE_UNAVAILABLE")
                if not isinstance(data.get("account"),dict) or _number(data["account"].get("cash")) is None:return result(False,"LEGACY_ACCOUNT_INVALID")
                direction=1 if summary["side"] == "LONG" else -1
                audit.update(close_price=price,quote_certificate=cert,pnl=(price-entry)*qty*direction,cash_delta=price*qty*direction,
                             exit_cost_model="EXACT_VERIFIED_MARK_RECONCILIATION_NO_ADDITIONAL_FEE")
            desk._event(conn,position_id,"LEGACY_"+action,audit)
            conn.execute("INSERT INTO legacy_position_resolutions(fingerprint,action,workspace,source,revision,record_json,audit_json,position_id) VALUES(?,?,?,?,?,?,?,?)",
                         (fingerprint,action,workspace,str(guard.LEGACY_ACCOUNT),revision,json.dumps(record),json.dumps(audit),position_id))
        # Canonical receipt is committed here. Never acknowledge before this.
        try:_acknowledge(desk,fingerprint)
        except (OSError,ValueError,sqlite3.Error):return result(False,"SOURCE_ACK_PENDING",position_id=position_id,retry_safe=True)
        return result(True,"LEGACY_"+action+"_RESOLVED",position_id=position_id,idempotent=False)
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,sqlite3.Error) as exc:
        return result(False,"LEGACY_RESOLUTION_FAILED",error_type=type(exc).__name__)
