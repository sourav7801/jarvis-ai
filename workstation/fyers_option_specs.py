"""Exact option lot/tick lookup from FYERS' public daily instrument files."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
import urllib.request

from workstation.terminal_data import shared_read


@shared_read(3600.)
def _master(exchange):
    if exchange not in {"NSE", "BSE", "MCX"}:
        raise ValueError("Unsupported Indian venue")
    segment = "COM" if exchange == "MCX" else "FO"
    url = f"https://public.fyers.in/sym_details/{exchange}_{segment}.csv"
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-read-only-instruments/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError("Instrument file exceeds size limit")
    return {"url": url, "csv": data.decode("utf-8-sig"), "received_at": datetime.now(timezone.utc).isoformat()}


def parse_specs(text, contracts, source, received_at):
    wanted = {str(c.symbol).upper(): c for c in contracts if c.symbol}
    specs = {}
    now = datetime.now(timezone.utc).timestamp()
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 10:
            continue
        symbol = row[9].strip().upper()
        contract = wanted.get(symbol)
        if contract is None or not symbol.endswith(("CE", "PE")):
            continue
        try:
            lot, tick, expiry = float(row[3]), float(row[4]), float(row[8])
            if lot <= 0 or lot != int(lot) or not 0 < tick < 100 or expiry <= now:
                continue
            expiry_date = datetime.fromtimestamp(expiry, timezone.utc).date().isoformat()
            if expiry_date != str(contract.expiry)[:10]:
                continue
        except (ValueError, OverflowError):
            continue
        specs[symbol] = {"symbol": symbol, "provider_symbol": symbol, "asset_class": "OPTION", "instrument_type": "OPTION",
                         "native_currency": "INR", "valuation_currency": "INR", "quantity_step": 1.,
                         "lot_size": lot, "contract_multiplier": lot, "tick_size": tick, "expiry": expiry_date,
                         "source": source, "received_at": received_at, "verified": True,
                         "verification_reason": "EXACT_FYERS_SYMBOL_MASTER_AND_CHAIN_EXPIRY_MATCH"}
    return specs


def resolve_specs(snapshot):
    result = {}
    exchanges = {str(c.symbol).split(":")[0] for c in snapshot.contracts if ":" in str(c.symbol)}
    for exchange in sorted(exchanges & {"NSE", "BSE", "MCX"}):
        master = _master(exchange)
        result.update(parse_specs(master["csv"], snapshot.contracts, master["url"], master["received_at"]))
    return result
