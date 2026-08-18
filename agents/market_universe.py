# ============================================================
# JARVIS MARKET UNIVERSE
# V1
# ============================================================
#
# Purpose:
#   Central registry and resolver for supported markets.
#
# Supports:
#   - NIFTY
#   - BANKNIFTY
#   - SENSEX
#   - Indian stock F&O
#   - Futures
#   - Options
#   - Commodities
#   - Crypto
#
# IMPORTANT:
#   This file describes instruments and market families.
#   It does NOT place orders.
#
#   Contract-specific values such as:
#       lot size
#       expiry
#       strike interval
#       margin
#
#   should come from current exchange/broker metadata
#   rather than being permanently hard-coded here.
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


# ============================================================
# INSTRUMENT TYPES
# ============================================================

ASSET_TYPES = {

    "INDEX",
    "STOCK",
    "COMMODITY",
    "CRYPTO",

}


DERIVATIVE_TYPES = {

    "OPTION",
    "FUTURE",

}


MARKETS = {

    "INDIA",
    "CRYPTO",
    "COMMODITY",

}


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class MarketInstrument:

    symbol: str

    display_name: str

    exchange: str

    market: str

    asset_type: str

    derivatives_available: bool = False

    options_available: bool = False

    futures_available: bool = False

    currency: str = "INR"

    provider_symbol: Optional[str] = None

    notes: str = ""


# ============================================================
# REGISTRY
# ============================================================

class MarketUniverse:

    def __init__(self):

        self._instruments: Dict[
            str,
            MarketInstrument,
        ] = {}

        self._load_default_universe()

    # ========================================================
    # REGISTER
    # ========================================================

    def register(
        self,
        instrument: MarketInstrument,
    ):

        key = self.normalize_symbol(
            instrument.symbol
        )

        self._instruments[
            key
        ] = instrument

    # ========================================================
    # DEFAULT UNIVERSE
    # ========================================================

    def _load_default_universe(self):

        # ----------------------------------------------------
        # NSE INDEXES
        # ----------------------------------------------------

        self.register(

            MarketInstrument(

                symbol="NIFTY",

                display_name="NIFTY 50",

                exchange="NSE",

                market="INDIA",

                asset_type="INDEX",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                provider_symbol="^NSEI",

                notes=(
                    "NSE benchmark index."
                ),

            )

        )

        self.register(

            MarketInstrument(

                symbol="BANKNIFTY",

                display_name="NIFTY BANK",

                exchange="NSE",

                market="INDIA",

                asset_type="INDEX",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                provider_symbol="^NSEBANK",

                notes=(
                    "NSE banking index."
                ),

            )

        )

        # ----------------------------------------------------
        # BSE INDEX
        # ----------------------------------------------------

        self.register(

            MarketInstrument(

                symbol="SENSEX",

                display_name="S&P BSE SENSEX",

                exchange="BSE",

                market="INDIA",

                asset_type="INDEX",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                provider_symbol="^BSESN",

                notes=(
                    "BSE benchmark index."
                ),

            )

        )

        # ----------------------------------------------------
        # GENERIC INDIAN STOCK F&O
        # ----------------------------------------------------

        self.register(

            MarketInstrument(

                symbol="STOCK_FO",

                display_name="Indian F&O Stock",

                exchange="NSE",

                market="INDIA",

                asset_type="STOCK",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                notes=(
                    "Dynamic placeholder for "
                    "currently permitted F&O stocks."
                ),

            )

        )

        # ----------------------------------------------------
        # COMMODITY
        # ----------------------------------------------------

        self.register(

            MarketInstrument(

                symbol="COMMODITY",

                display_name="Commodity Futures",

                exchange="MCX",

                market="COMMODITY",

                asset_type="COMMODITY",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                notes=(
                    "Dynamic commodity universe."
                ),

            )

        )

        # ----------------------------------------------------
        # CRYPTO
        # ----------------------------------------------------

        self.register(

            MarketInstrument(

                symbol="CRYPTO",

                display_name="Crypto Asset",

                exchange="MULTI",

                market="CRYPTO",

                asset_type="CRYPTO",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="USD",

                notes=(
                    "Dynamic crypto universe."
                ),

            )

        )

    # ========================================================
    # NORMALIZE SYMBOL
    # ========================================================

    def normalize_symbol(
        self,
        symbol: str,
    ) -> str:

        value = str(
            symbol or ""
        ).strip().upper()

        value = (
            value.replace(
                "-",
                "",
            )
            .replace(
                "_",
                "",
            )
            .replace(
                " ",
                "",
            )
        )

        aliases = {

            "NIFTY50":
                "NIFTY",

            "NIFTYINDEX":
                "NIFTY",

            "NIFTYBANK":
                "BANKNIFTY",

            "BANKNIFTYINDEX":
                "BANKNIFTY",

            "BANKNIFTY50":
                "BANKNIFTY",

            "BSESENSEX":
                "SENSEX",

            "SENSEXINDEX":
                "SENSEX",

        }

        return aliases.get(
            value,
            value,
        )

    # ========================================================
    # RESOLVE
    # ========================================================

    def resolve(
        self,
        symbol: str,
    ) -> Optional[MarketInstrument]:

        normalized = (
            self.normalize_symbol(
                symbol
            )
        )

        if normalized in self._instruments:

            return self._instruments[
                normalized
            ]

        # Unknown Indian stock.
        #
        # We deliberately classify it as a
        # generic stock rather than inventing
        # exchange/contract metadata.

        if (
            normalized
            and
            normalized.isalpha()
            and
            len(normalized) <= 20
        ):

            return MarketInstrument(

                symbol=normalized,

                display_name=normalized,

                exchange="NSE",

                market="INDIA",

                asset_type="STOCK",

                derivatives_available=True,

                options_available=True,

                futures_available=True,

                currency="INR",

                notes=(
                    "Unverified dynamic stock. "
                    "Current derivative availability "
                    "must be checked against live "
                    "exchange/broker metadata."
                ),

            )

        return None

    # ========================================================
    # LIST
    # ========================================================

    def list_indexes(
        self,
    ) -> List[MarketInstrument]:

        return [

            instrument

            for instrument
            in self._instruments.values()

            if (
                instrument.asset_type
                == "INDEX"
            )

        ]

    # ========================================================

    def list_stocks(
        self,
    ) -> List[MarketInstrument]:

        return [

            instrument

            for instrument
            in self._instruments.values()

            if (
                instrument.asset_type
                == "STOCK"
            )

        ]

    # ========================================================
    # SUPPORT CHECK
    # ========================================================

    def supports_options(
        self,
        symbol: str,
    ) -> bool:

        instrument = self.resolve(
            symbol
        )

        if instrument is None:

            return False

        return (
            instrument.options_available
        )

    # ========================================================

    def supports_futures(
        self,
        symbol: str,
    ) -> bool:

        instrument = self.resolve(
            symbol
        )

        if instrument is None:

            return False

        return (
            instrument.futures_available
        )

    # ========================================================
    # PROVIDER SYMBOL
    # ========================================================

    def provider_symbol(
        self,
        symbol: str,
    ) -> Optional[str]:

        instrument = self.resolve(
            symbol
        )

        if instrument is None:

            return None

        return (
            instrument.provider_symbol
            or
            instrument.symbol
        )

    # ========================================================
    # MARKET INFORMATION
    # ========================================================

    def describe(
        self,
        symbol: str,
    ) -> Dict:

        instrument = self.resolve(
            symbol
        )

        if instrument is None:

            return {

                "success":
                    False,

                "message":
                    (
                        f"Unknown instrument: "
                        f"{symbol}"
                    ),

            }

        return {

            "success":
                True,

            "instrument":
                asdict(
                    instrument
                ),

        }


# ============================================================
# GLOBAL UNIVERSE
# ============================================================

market_universe = MarketUniverse()


# ============================================================
# COMPATIBILITY HELPERS
# ============================================================

def resolve_instrument(
    symbol: str,
) -> Optional[MarketInstrument]:

    return market_universe.resolve(
        symbol
    )


def describe_market(
    symbol: str,
) -> Dict:

    return market_universe.describe(
        symbol
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "JARVIS MARKET UNIVERSE"
    )

    print(
        "=" * 60
    )

    print()

    symbols = [

        "NIFTY",
        "BANKNIFTY",
        "SENSEX",
        "RELIANCE",
        "HDFCBANK",
        "ICICIBANK",

    ]

    for symbol in symbols:

        instrument = (
            resolve_instrument(
                symbol
            )
        )

        print(
            symbol
        )

        if instrument:

            print(
                f"  Exchange: "
                f"{instrument.exchange}"
            )

            print(
                f"  Market: "
                f"{instrument.market}"
            )

            print(
                f"  Type: "
                f"{instrument.asset_type}"
            )

            print(
                f"  Options: "
                f"{instrument.options_available}"
            )

            print(
                f"  Futures: "
                f"{instrument.futures_available}"
            )

            print(
                f"  Provider: "
                f"{instrument.provider_symbol}"
            )

            print()

        else:

            print(
                "  Not resolved."
            )

    print(
        "Market Universe loaded successfully."
    )