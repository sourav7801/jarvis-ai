
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Instrument:
    key: str
    display_name: str
    asset_class: str
    exchange: str
    provider_symbols: Dict[str, str]
    expiry_type: str = "NONE"


REGISTRY = {
    "NIFTY": Instrument(
        key="NIFTY",
        display_name="NIFTY 50",
        asset_class="INDEX",
        exchange="NSE",
        provider_symbols={
            "UPSTOX": "NSE_INDEX|Nifty 50",
            "TRADINGVIEW": "NSE:NIFTY",
        },
        expiry_type="WEEKLY_TUESDAY",
    ),
    "BANKNIFTY": Instrument(
        key="BANKNIFTY",
        display_name="BANKNIFTY",
        asset_class="INDEX",
        exchange="NSE",
        provider_symbols={
            "UPSTOX": "NSE_INDEX|Nifty Bank",
            "TRADINGVIEW": "NSE:BANKNIFTY",
        },
        expiry_type="MONTHLY_LAST_TUESDAY",
    ),
    "SENSEX": Instrument(
        key="SENSEX",
        display_name="SENSEX",
        asset_class="INDEX",
        exchange="BSE",
        provider_symbols={
            "UPSTOX": "BSE_INDEX|SENSEX",
            "TRADINGVIEW": "BSE:SENSEX",
        },
        expiry_type="VERIFY_FROM_BOD_INSTRUMENTS",
    ),
    "GOLD": Instrument(
        key="GOLD",
        display_name="GOLD",
        asset_class="COMMODITY",
        exchange="MCX",
        provider_symbols={"TRADINGVIEW": "MCX:GOLD1!"},
    ),
    "SILVER": Instrument(
        key="SILVER",
        display_name="SILVER",
        asset_class="COMMODITY",
        exchange="MCX",
        provider_symbols={"TRADINGVIEW": "MCX:SILVER1!"},
    ),
    "CRUDE_OIL": Instrument(
        key="CRUDE_OIL",
        display_name="CRUDE OIL",
        asset_class="COMMODITY",
        exchange="MCX",
        provider_symbols={"TRADINGVIEW": "MCX:CRUDEOIL1!"},
    ),
    "NATURAL_GAS": Instrument(
        key="NATURAL_GAS",
        display_name="NATURAL GAS",
        asset_class="COMMODITY",
        exchange="MCX",
        provider_symbols={"TRADINGVIEW": "MCX:NATURALGAS1!"},
    ),
    "BTC": Instrument(
        key="BTC",
        display_name="BITCOIN",
        asset_class="CRYPTO",
        exchange="CRYPTO",
        provider_symbols={"TRADINGVIEW": "BINANCE:BTCUSDT"},
    ),
}


def get_instrument(key: str) -> Instrument:
    key = key.upper().replace(" ", "_")
    return REGISTRY[key]
