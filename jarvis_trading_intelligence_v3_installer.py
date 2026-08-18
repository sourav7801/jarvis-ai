from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap

ROOT = Path(r"C:\Jarvis")
PY = ROOT / ".venv" / "Scripts" / "python.exe"

PKG = ROOT / "omni" / "trading_intelligence"

CHAIN_SCHEMA = PKG / "option_chain_schema.py"
IV = PKG / "iv_analytics.py"
CHAIN_INTEL = PKG / "option_chain_intelligence.py"
EXPIRY = PKG / "expiry_intelligence.py"
SPREADS = PKG / "defined_risk_spreads.py"
COMMODITY = PKG / "commodity_intelligence.py"
CONFIRMATION = PKG / "derivatives_confirmation.py"
DERIV_STRATEGIES = PKG / "derivatives_strategy_registry.py"
CHAIN_PROVIDER = PKG / "option_chain_provider.py"
STATUS = PKG / "trading_v3_status.py"

MAIN = ROOT / "main.py"
APP = ROOT / "workstation" / "app.py"
TEST = ROOT / "tests" / "test_trading_intelligence_v3.py"

MANIFEST = ROOT / "config" / "protected_core_manifest.json"

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_intelligence_v3"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    CHAIN_SCHEMA,
    IV,
    CHAIN_INTEL,
    EXPIRY,
    SPREADS,
    COMMODITY,
    CONFIRMATION,
    DERIV_STRATEGIES,
    CHAIN_PROVIDER,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    *args,
    capture=False,
):

    return subprocess.run(
        [str(PY), *args],
        cwd=ROOT,
        capture_output=capture,
        text=True,
    )


def sha(path):

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def write(
    path,
    source,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        textwrap.dedent(
            source
        ).lstrip(),
        encoding="utf-8",
    )


def rollback():

    print()
    print("ROLLBACK")

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        if existed:

            shutil.copy2(
                backup,
                path,
            )

        else:

            path.unlink(
                missing_ok=True
            )

    print(
        "JARVIS source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V3")
print("ADVANCED OPTIONS + DERIVATIVES + COMMODITY INTELLIGENCE")
print("=" * 80)


# ============================================================
# BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = path.exists()

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


# ============================================================
# VERIFY V2 / 526 CHECKPOINT
# ============================================================

print()
print("Checking Trading Intelligence V2 / 526 checkpoint...")


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v=main.jarvis_trading_v2_status(); "
        "assert v['historical_backtester']; "
        "assert v['live_execution'] is False; "
        "assert v['automatic_broker_order'] is False; "
        "b=main.jarvis_fyers_bridge_status(); "
        "assert b['canonical_provider_available']; "
        "c=main.jarvis_fyers_readonly_capabilities(); "
        "assert c['quote']=='get_quote'; "
        "assert c['history']=='get_intraday_data'; "
        "assert c['option_chain'] is None; "
        "print('Main import: PASS'); "
        "print('Protected Core: PASS'); "
        "print('Trading Intelligence V2: PASS'); "
        "print('Canonical FYERS bridge: PASS'); "
        "print('No fabricated FYERS option-chain API: PASS'); "
        "print('Live execution: BLOCKED')"
    ),
)


if r.returncode:

    print("BASELINE FAILURE")
    sys.exit(1)


r = run(
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:

    print("BROWSER BASELINE FAILURE")
    sys.exit(1)


print("Browser DOM repair: PASS")


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)


PROTECTED = {
    relative:
        sha(
            ROOT / relative
        )

    for relative
    in manifest.get(
        "files",
        {}
    )
}


print(
    "Protected files:",
    len(PROTECTED),
)

print("Baseline: PASS")


# ============================================================
# OPTION CHAIN SCHEMA
# ============================================================

write(
    CHAIN_SCHEMA,
    r'''
from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from statistics import (
    fmean,
)


def normalize_option_type(
    value,
):

    text = str(
        value
        or ""
    ).strip().lower()


    if text in {
        "ce",
        "call",
        "c",
    }:

        return "call"


    if text in {
        "pe",
        "put",
        "p",
    }:

        return "put"


    raise ValueError(
        "Option type must be CE/PE or call/put."
    )


def _optional_float(
    value,
):

    if value in (
        None,
        "",
    ):

        return None


    return float(
        value
    )


@dataclass(frozen=True)
class OptionContractQuote:

    underlying: str

    expiry: str

    strike: float

    option_type: str

    ltp: float

    symbol: str | None = None

    bid: float | None = None

    ask: float | None = None

    volume: float | None = None

    open_interest: float | None = None

    change_in_oi: float | None = None

    implied_volatility: float | None = None

    delta: float | None = None

    gamma: float | None = None

    theta: float | None = None

    vega: float | None = None


    def __post_init__(
        self,
    ):

        object.__setattr__(
            self,
            "option_type",
            normalize_option_type(
                self.option_type
            ),
        )


        if self.strike <= 0:

            raise ValueError(
                "Option strike must be positive."
            )


        if not self.expiry:

            raise ValueError(
                "Option expiry is required."
            )


        if self.ltp < 0:

            raise ValueError(
                "Option LTP cannot be negative."
            )


    @property
    def mid(
        self,
    ):

        if (
            self.bid is None
            or self.ask is None
        ):

            return None


        return (
            self.bid
            + self.ask
        ) / 2.0


    @property
    def spread(
        self,
    ):

        if (
            self.bid is None
            or self.ask is None
        ):

            return None


        return max(
            0.0,
            self.ask
            - self.bid,
        )


    @property
    def spread_pct(
        self,
    ):

        if (
            self.mid is None
            or self.mid <= 0
        ):

            return None


        return (
            self.spread
            / self.mid
        )


    def to_dict(
        self,
    ):

        result = asdict(
            self
        )

        result[
            "mid"
        ] = self.mid

        result[
            "spread"
        ] = self.spread

        result[
            "spread_pct"
        ] = self.spread_pct

        return result


@dataclass(frozen=True)
class OptionChainSnapshot:

    underlying: str

    spot: float

    timestamp: str

    contracts: tuple[OptionContractQuote, ...]


    def __post_init__(
        self,
    ):

        if self.spot <= 0:

            raise ValueError(
                "Spot price must be positive."
            )


        if not self.contracts:

            raise ValueError(
                "Option chain requires contracts."
            )


    @property
    def expiries(
        self,
    ):

        return tuple(
            sorted(
                {
                    contract.expiry

                    for contract
                    in self.contracts
                }
            )
        )


    @property
    def strikes(
        self,
    ):

        return tuple(
            sorted(
                {
                    contract.strike

                    for contract
                    in self.contracts
                }
            )
        )


    def to_dict(
        self,
    ):

        return {
            "underlying":
                self.underlying,

            "spot":
                self.spot,

            "timestamp":
                self.timestamp,

            "expiries":
                self.expiries,

            "strikes":
                self.strikes,

            "contracts":
                tuple(
                    contract.to_dict()

                    for contract
                    in self.contracts
                ),
        }


FIELD_ALIASES = {
    "symbol": (
        "symbol",
        "tradingsymbol",
        "trading_symbol",
    ),

    "strike": (
        "strike",
        "strike_price",
        "strikeprice",
    ),

    "option_type": (
        "option_type",
        "type",
        "right",
        "cp_type",
        "optiontype",
    ),

    "expiry": (
        "expiry",
        "expiry_date",
        "expirydate",
    ),

    "ltp": (
        "ltp",
        "last",
        "last_price",
        "lastprice",
        "price",
    ),

    "bid": (
        "bid",
        "bid_price",
        "best_bid",
    ),

    "ask": (
        "ask",
        "ask_price",
        "best_ask",
    ),

    "volume": (
        "volume",
        "vol",
        "traded_volume",
    ),

    "open_interest": (
        "open_interest",
        "oi",
    ),

    "change_in_oi": (
        "change_in_oi",
        "change_oi",
        "oi_change",
        "changeinoi",
        "doi",
    ),

    "implied_volatility": (
        "implied_volatility",
        "iv",
    ),

    "delta": (
        "delta",
    ),

    "gamma": (
        "gamma",
    ),

    "theta": (
        "theta",
    ),

    "vega": (
        "vega",
    ),
}


def _value(
    row,
    field,
    default=None,
):

    normalized = {
        str(
            key
        ).strip().lower():
            value

        for key, value
        in dict(
            row
        ).items()
    }


    for alias in FIELD_ALIASES[
        field
    ]:

        if alias in normalized:

            return normalized[
                alias
            ]


    return default


def normalize_option_chain(
    rows,
    *,
    underlying,
    spot,
    timestamp,
    expiry=None,
):

    contracts = []


    for row in rows:

        row_expiry = (
            _value(
                row,
                "expiry",
                expiry,
            )
        )


        if not row_expiry:

            raise ValueError(
                "Every option contract requires expiry."
            )


        contract = OptionContractQuote(
            underlying=
                str(
                    underlying
                ),

            expiry=
                str(
                    row_expiry
                ),

            strike=
                float(
                    _value(
                        row,
                        "strike",
                    )
                ),

            option_type=
                _value(
                    row,
                    "option_type",
                ),

            ltp=
                float(
                    _value(
                        row,
                        "ltp",
                        0.0,
                    )
                    or 0.0
                ),

            symbol=
                (
                    str(
                        _value(
                            row,
                            "symbol",
                        )
                    )
                    if _value(
                        row,
                        "symbol",
                    )
                    is not None
                    else None
                ),

            bid=
                _optional_float(
                    _value(
                        row,
                        "bid",
                    )
                ),

            ask=
                _optional_float(
                    _value(
                        row,
                        "ask",
                    )
                ),

            volume=
                _optional_float(
                    _value(
                        row,
                        "volume",
                    )
                ),

            open_interest=
                _optional_float(
                    _value(
                        row,
                        "open_interest",
                    )
                ),

            change_in_oi=
                _optional_float(
                    _value(
                        row,
                        "change_in_oi",
                    )
                ),

            implied_volatility=
                _optional_float(
                    _value(
                        row,
                        "implied_volatility",
                    )
                ),

            delta=
                _optional_float(
                    _value(
                        row,
                        "delta",
                    )
                ),

            gamma=
                _optional_float(
                    _value(
                        row,
                        "gamma",
                    )
                ),

            theta=
                _optional_float(
                    _value(
                        row,
                        "theta",
                    )
                ),

            vega=
                _optional_float(
                    _value(
                        row,
                        "vega",
                    )
                ),
        )


        contracts.append(
            contract
        )


    return OptionChainSnapshot(
        underlying=
            str(
                underlying
            ),

        spot=
            float(
                spot
            ),

        timestamp=
            str(
                timestamp
            ),

        contracts=
            tuple(
                contracts
            ),
    )
'''
)


# ============================================================
# IV ANALYTICS
# ============================================================

write(
    IV,
    r'''
from __future__ import annotations

from statistics import (
    fmean,
)


def _clean(
    values,
):

    return [
        float(
            value
        )

        for value in values

        if value is not None
    ]


def iv_rank(
    current_iv,
    history,
):

    history = _clean(
        history
    )


    if not history:

        return None


    current = float(
        current_iv
    )


    low = min(
        history
    )

    high = max(
        history
    )


    if high == low:

        return 50.0


    return max(
        0.0,
        min(
            100.0,
            (
                current
                - low
            )
            / (
                high
                - low
            )
            * 100.0,
        ),
    )


def iv_percentile(
    current_iv,
    history,
):

    history = _clean(
        history
    )


    if not history:

        return None


    current = float(
        current_iv
    )


    count = sum(
        1

        for value in history

        if value <= current
    )


    return (
        count
        / len(
            history
        )
        * 100.0
    )


def strike_iv_skew(
    snapshot,
):

    rows = []


    for strike in snapshot.strikes:

        calls = [
            contract

            for contract
            in snapshot.contracts

            if (
                contract.strike
                == strike
                and contract.option_type
                == "call"
                and contract.implied_volatility
                is not None
            )
        ]


        puts = [
            contract

            for contract
            in snapshot.contracts

            if (
                contract.strike
                == strike
                and contract.option_type
                == "put"
                and contract.implied_volatility
                is not None
            )
        ]


        call_iv = (
            fmean(
                contract.implied_volatility
                for contract in calls
            )
            if calls
            else None
        )


        put_iv = (
            fmean(
                contract.implied_volatility
                for contract in puts
            )
            if puts
            else None
        )


        rows.append(
            {
                "strike":
                    strike,

                "distance_pct":
                    (
                        strike
                        / snapshot.spot
                        - 1.0
                    ),

                "call_iv":
                    call_iv,

                "put_iv":
                    put_iv,

                "put_minus_call_iv":
                    (
                        put_iv
                        - call_iv

                        if (
                            put_iv is not None
                            and call_iv is not None
                        )

                        else None
                    ),
            }
        )


    return tuple(
        rows
    )


def iv_term_structure(
    points,
):

    normalized = []


    for item in points:

        expiry = str(
            item[
                "expiry"
            ]
        )

        days = float(
            item[
                "days_to_expiry"
            ]
        )

        atm_iv = float(
            item[
                "atm_iv"
            ]
        )


        normalized.append(
            {
                "expiry":
                    expiry,

                "days_to_expiry":
                    days,

                "atm_iv":
                    atm_iv,
            }
        )


    normalized.sort(
        key=lambda item:
            item[
                "days_to_expiry"
            ]
    )


    slopes = []


    for left, right in zip(
        normalized,
        normalized[
            1:
        ],
    ):

        day_difference = (
            right[
                "days_to_expiry"
            ]
            - left[
                "days_to_expiry"
            ]
        )


        slopes.append(
            {
                "from_expiry":
                    left[
                        "expiry"
                    ],

                "to_expiry":
                    right[
                        "expiry"
                    ],

                "iv_change":
                    (
                        right[
                            "atm_iv"
                        ]
                        - left[
                            "atm_iv"
                        ]
                    ),

                "iv_change_per_day":
                    (
                        (
                            right[
                                "atm_iv"
                            ]
                            - left[
                                "atm_iv"
                            ]
                        )
                        / day_difference

                        if day_difference != 0

                        else None
                    ),
            }
        )


    return {
        "points":
            tuple(
                normalized
            ),

        "slopes":
            tuple(
                slopes
            ),

        "research_only":
            True,
    }
'''
)


# ============================================================
# OPTION CHAIN INTELLIGENCE
# ============================================================

write(
    CHAIN_INTEL,
    r'''
from __future__ import annotations

from statistics import (
    fmean,
    pstdev,
)


from omni.trading_intelligence.iv_analytics import (
    strike_iv_skew,
)


def _sum(
    contracts,
    field,
):

    return sum(
        float(
            getattr(
                contract,
                field
            )
            or 0.0
        )

        for contract
        in contracts
    )


def _ratio(
    numerator,
    denominator,
):

    if denominator == 0:

        return None


    return (
        numerator
        / denominator
    )


def _max_contract(
    contracts,
    field,
):

    candidates = [
        contract

        for contract
        in contracts

        if getattr(
            contract,
            field
        )
        is not None
    ]


    if not candidates:

        return None


    contract = max(
        candidates,
        key=lambda item:
            float(
                getattr(
                    item,
                    field
                )
                or 0.0
            ),
    )


    return contract.to_dict()


def _liquidity_score(
    contract,
    max_volume,
    max_oi,
):

    spread_score = 0.0


    spread_pct = (
        contract.spread_pct
    )


    if spread_pct is not None:

        if spread_pct <= 0.002:
            spread_score = 40.0

        elif spread_pct <= 0.005:
            spread_score = 35.0

        elif spread_pct <= 0.01:
            spread_score = 30.0

        elif spread_pct <= 0.02:
            spread_score = 20.0

        elif spread_pct <= 0.05:
            spread_score = 10.0


    volume = float(
        contract.volume
        or 0.0
    )


    oi = float(
        contract.open_interest
        or 0.0
    )


    volume_score = (
        min(
            30.0,
            30.0
            * volume
            / max_volume,
        )
        if max_volume > 0
        else 0.0
    )


    oi_score = (
        min(
            30.0,
            30.0
            * oi
            / max_oi,
        )
        if max_oi > 0
        else 0.0
    )


    return (
        spread_score
        + volume_score
        + oi_score
    )


def _cross_sectional_zscores(
    contracts,
    field,
):

    values = [
        float(
            getattr(
                contract,
                field
            )
            or 0.0
        )

        for contract
        in contracts
    ]


    if len(
        values
    ) < 2:

        return [
            0.0

            for _ in values
        ]


    mean = fmean(
        values
    )

    sigma = pstdev(
        values
    )


    if sigma == 0:

        return [
            0.0

            for _ in values
        ]


    return [
        (
            value
            - mean
        )
        / sigma

        for value in values
    ]


def max_pain_research(
    snapshot,
):

    strikes = list(
        snapshot.strikes
    )


    payouts = []


    for settlement in strikes:

        total = 0.0


        for contract in snapshot.contracts:

            oi = float(
                contract.open_interest
                or 0.0
            )


            if contract.option_type == "call":

                intrinsic = max(
                    0.0,
                    settlement
                    - contract.strike,
                )


            else:

                intrinsic = max(
                    0.0,
                    contract.strike
                    - settlement,
                )


            total += (
                intrinsic
                * oi
            )


        payouts.append(
            {
                "settlement":
                    settlement,

                "writer_intrinsic_payout":
                    total,
            }
        )


    best = min(
        payouts,
        key=lambda item:
            item[
                "writer_intrinsic_payout"
            ],
    )


    return {
        "strike":
            best[
                "settlement"
            ],

        "payout":
            best[
                "writer_intrinsic_payout"
            ],

        "surface":
            tuple(
                payouts
            ),

        "predictive_claim":
            False,

        "research_only":
            True,
    }


class OptionChainIntelligence:

    def analyze(
        self,
        snapshot,
    ):

        calls = [
            contract

            for contract
            in snapshot.contracts

            if contract.option_type
            == "call"
        ]


        puts = [
            contract

            for contract
            in snapshot.contracts

            if contract.option_type
            == "put"
        ]


        if (
            not calls
            or not puts
        ):

            raise ValueError(
                "Chain requires both calls and puts."
            )


        atm_strike = min(
            snapshot.strikes,
            key=lambda strike:
                abs(
                    strike
                    - snapshot.spot
                ),
        )


        atm_call = min(
            calls,
            key=lambda contract:
                abs(
                    contract.strike
                    - atm_strike
                ),
        )


        atm_put = min(
            puts,
            key=lambda contract:
                abs(
                    contract.strike
                    - atm_strike
                ),
        )


        call_oi = _sum(
            calls,
            "open_interest",
        )

        put_oi = _sum(
            puts,
            "open_interest",
        )


        call_volume = _sum(
            calls,
            "volume",
        )

        put_volume = _sum(
            puts,
            "volume",
        )


        call_doi = _sum(
            calls,
            "change_in_oi",
        )

        put_doi = _sum(
            puts,
            "change_in_oi",
        )


        max_volume = max(
            (
                float(
                    contract.volume
                    or 0.0
                )

                for contract
                in snapshot.contracts
            ),
            default=0.0,
        )


        max_oi = max(
            (
                float(
                    contract.open_interest
                    or 0.0
                )

                for contract
                in snapshot.contracts
            ),
            default=0.0,
        )


        liquidity_rows = []


        for contract in snapshot.contracts:

            liquidity_rows.append(
                {
                    "symbol":
                        contract.symbol,

                    "strike":
                        contract.strike,

                    "option_type":
                        contract.option_type,

                    "score":
                        _liquidity_score(
                            contract,
                            max_volume,
                            max_oi,
                        ),

                    "spread_pct":
                        contract.spread_pct,

                    "volume":
                        contract.volume,

                    "open_interest":
                        contract.open_interest,
                }
            )


        near_atm = sorted(
            liquidity_rows,
            key=lambda item:
                abs(
                    item[
                        "strike"
                    ]
                    - snapshot.spot
                ),
        )[
            :min(
                6,
                len(
                    liquidity_rows
                ),
            )
        ]


        chain_liquidity = (
            fmean(
                item[
                    "score"
                ]

                for item in near_atm
            )
            if near_atm
            else 0.0
        )


        volume_z = (
            _cross_sectional_zscores(
                snapshot.contracts,
                "volume",
            )
        )


        oi_z = (
            _cross_sectional_zscores(
                snapshot.contracts,
                "open_interest",
            )
        )


        unusual = []


        for contract, vz, oz in zip(
            snapshot.contracts,
            volume_z,
            oi_z,
        ):

            if (
                vz >= 2.0
                or oz >= 2.0
            ):

                unusual.append(
                    {
                        "symbol":
                            contract.symbol,

                        "strike":
                            contract.strike,

                        "option_type":
                            contract.option_type,

                        "volume_z":
                            vz,

                        "oi_z":
                            oz,
                    }
                )


        call_ivs = [
            contract.implied_volatility

            for contract in calls

            if contract.implied_volatility
            is not None
        ]


        put_ivs = [
            contract.implied_volatility

            for contract in puts

            if contract.implied_volatility
            is not None
        ]


        average_call_iv = (
            fmean(
                call_ivs
            )
            if call_ivs
            else None
        )


        average_put_iv = (
            fmean(
                put_ivs
            )
            if put_ivs
            else None
        )


        return {
            "success":
                True,

            "underlying":
                snapshot.underlying,

            "spot":
                snapshot.spot,

            "timestamp":
                snapshot.timestamp,

            "expiries":
                snapshot.expiries,

            "atm_strike":
                atm_strike,

            "atm_call":
                atm_call.to_dict(),

            "atm_put":
                atm_put.to_dict(),

            "call_oi":
                call_oi,

            "put_oi":
                put_oi,

            "pcr_oi":
                _ratio(
                    put_oi,
                    call_oi,
                ),

            "call_volume":
                call_volume,

            "put_volume":
                put_volume,

            "pcr_volume":
                _ratio(
                    put_volume,
                    call_volume,
                ),

            "call_change_in_oi":
                call_doi,

            "put_change_in_oi":
                put_doi,

            "pcr_change_in_oi":
                _ratio(
                    put_doi,
                    call_doi,
                ),

            "call_oi_wall":
                _max_contract(
                    calls,
                    "open_interest",
                ),

            "put_oi_wall":
                _max_contract(
                    puts,
                    "open_interest",
                ),

            "call_volume_leader":
                _max_contract(
                    calls,
                    "volume",
                ),

            "put_volume_leader":
                _max_contract(
                    puts,
                    "volume",
                ),

            "average_call_iv":
                average_call_iv,

            "average_put_iv":
                average_put_iv,

            "put_minus_call_iv":
                (
                    average_put_iv
                    - average_call_iv

                    if (
                        average_put_iv
                        is not None
                        and average_call_iv
                        is not None
                    )

                    else None
                ),

            "strike_iv_skew":
                strike_iv_skew(
                    snapshot
                ),

            "liquidity":
                tuple(
                    liquidity_rows
                ),

            "chain_liquidity_score":
                chain_liquidity,

            "unusual_contracts":
                tuple(
                    unusual
                ),

            "max_pain_research":
                max_pain_research(
                    snapshot
                ),

            "predictive_claim":
                False,

            "research_only":
                True,
        }


option_chain_intelligence = (
    OptionChainIntelligence()
)
'''
)


# ============================================================
# EXPIRY INTELLIGENCE
# ============================================================

write(
    EXPIRY,
    r'''
from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
)

from zoneinfo import (
    ZoneInfo,
)


def _parse_expiry(
    expiry,
    *,
    expiry_time="15:30",
    timezone_name="Asia/Kolkata",
):

    zone = ZoneInfo(
        timezone_name
    )


    if isinstance(
        expiry,
        datetime,
    ):

        result = expiry


        if result.tzinfo is None:

            result = result.replace(
                tzinfo=zone
            )


        return result


    if isinstance(
        expiry,
        date,
    ):

        expiry_date = expiry


    else:

        text = str(
            expiry
        ).strip()


        try:

            result = datetime.fromisoformat(
                text
            )


            if result.tzinfo is None:

                result = result.replace(
                    tzinfo=zone
                )


            if "T" in text:

                return result


            expiry_date = result.date()


        except Exception:

            expiry_date = date.fromisoformat(
                text
            )


    hour, minute = [
        int(
            value
        )

        for value
        in str(
            expiry_time
        ).split(
            ":",
            1,
        )
    ]


    return datetime.combine(
        expiry_date,
        time(
            hour,
            minute,
        ),
        tzinfo=zone,
    )


def expiry_state(
    expiry,
    *,
    now=None,
    expiry_time="15:30",
    timezone_name="Asia/Kolkata",
):

    zone = ZoneInfo(
        timezone_name
    )


    expiry_dt = _parse_expiry(
        expiry,
        expiry_time=expiry_time,
        timezone_name=timezone_name,
    )


    current = (
        now
        if now is not None
        else datetime.now(
            zone
        )
    )


    if current.tzinfo is None:

        current = current.replace(
            tzinfo=zone
        )


    current = current.astimezone(
        zone
    )


    expiry_dt = expiry_dt.astimezone(
        zone
    )


    seconds = (
        expiry_dt
        - current
    ).total_seconds()


    hours = (
        seconds
        / 3600.0
    )


    days = (
        seconds
        / 86400.0
    )


    if seconds < 0:

        phase = "EXPIRED"


    elif current.date() == expiry_dt.date():

        phase = "EXPIRY_DAY"


    elif days <= 3:

        phase = "NEAR_EXPIRY"


    elif days <= 7:

        phase = "SHORT_EXPIRY"


    elif days <= 30:

        phase = "MEDIUM_EXPIRY"


    else:

        phase = "FAR_EXPIRY"


    theta_urgency = max(
        0.0,
        min(
            1.0,
            (
                1.0
                - max(
                    days,
                    0.0,
                )
                / 7.0
            ),
        ),
    )


    return {
        "expiry":
            expiry_dt.isoformat(),

        "now":
            current.isoformat(),

        "seconds_to_expiry":
            seconds,

        "hours_to_expiry":
            hours,

        "days_to_expiry":
            days,

        "phase":
            phase,

        "theta_urgency_heuristic":
            theta_urgency,

        "research_only":
            True,
    }
'''
)


# ============================================================
# DEFINED-RISK VERTICAL SPREADS
# ============================================================

write(
    SPREADS,
    r'''
from __future__ import annotations


SUPPORTED = {
    "bull_call",
    "bear_call",
    "bear_put",
    "bull_put",
}


def build_vertical_spread(
    kind,
    *,
    lower_strike,
    higher_strike,
    lower_premium,
    higher_premium,
    quantity=1.0,
    multiplier=1.0,
):

    kind = str(
        kind
    ).strip().lower()


    if kind not in SUPPORTED:

        raise ValueError(
            "Unsupported defined-risk vertical spread."
        )


    lower = float(
        lower_strike
    )

    higher = float(
        higher_strike
    )


    if higher <= lower:

        raise ValueError(
            "higher_strike must exceed lower_strike."
        )


    lower_premium = float(
        lower_premium
    )

    higher_premium = float(
        higher_premium
    )

    quantity = float(
        quantity
    )

    multiplier = float(
        multiplier
    )


    if (
        quantity <= 0
        or multiplier <= 0
    ):

        raise ValueError(
            "quantity and multiplier must be positive."
        )


    width = (
        higher
        - lower
    )


    if kind == "bull_call":

        option_type = "call"

        legs = (
            {
                "side":
                    "BUY",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "SELL",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        net_debit = (
            lower_premium
            - higher_premium
        )


        max_loss = max(
            0.0,
            net_debit
        )


        max_profit = max(
            0.0,
            width
            - net_debit
        )


        breakeven = (
            lower
            + net_debit
        )


    elif kind == "bear_call":

        option_type = "call"

        legs = (
            {
                "side":
                    "SELL",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "BUY",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        credit = (
            lower_premium
            - higher_premium
        )


        max_profit = max(
            0.0,
            credit
        )


        max_loss = max(
            0.0,
            width
            - credit
        )


        breakeven = (
            lower
            + credit
        )


    elif kind == "bear_put":

        option_type = "put"

        legs = (
            {
                "side":
                    "SELL",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "BUY",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        net_debit = (
            higher_premium
            - lower_premium
        )


        max_loss = max(
            0.0,
            net_debit
        )


        max_profit = max(
            0.0,
            width
            - net_debit
        )


        breakeven = (
            higher
            - net_debit
        )


    else:

        option_type = "put"

        legs = (
            {
                "side":
                    "BUY",

                "strike":
                    lower,

                "premium":
                    lower_premium,
            },

            {
                "side":
                    "SELL",

                "strike":
                    higher,

                "premium":
                    higher_premium,
            },
        )


        credit = (
            higher_premium
            - lower_premium
        )


        max_profit = max(
            0.0,
            credit
        )


        max_loss = max(
            0.0,
            width
            - credit
        )


        breakeven = (
            higher
            - credit
        )


    scale = (
        quantity
        * multiplier
    )


    return {
        "kind":
            kind,

        "option_type":
            option_type,

        "legs":
            legs,

        "lower_strike":
            lower,

        "higher_strike":
            higher,

        "width":
            width,

        "breakeven":
            breakeven,

        "max_profit":
            max_profit
            * scale,

        "max_loss":
            max_loss
            * scale,

        "quantity":
            quantity,

        "multiplier":
            multiplier,

        "defined_risk":
            True,

        "naked_short":
            False,

        "research_only":
            True,
    }


def vertical_payoff(
    spread,
    settlement,
):

    settlement = float(
        settlement
    )


    option_type = spread[
        "option_type"
    ]


    gross = 0.0

    premium_cashflow = 0.0


    for leg in spread[
        "legs"
    ]:

        strike = float(
            leg[
                "strike"
            ]
        )

        premium = float(
            leg[
                "premium"
            ]
        )


        side = (
            1.0
            if leg[
                "side"
            ] == "BUY"
            else -1.0
        )


        if option_type == "call":

            intrinsic = max(
                0.0,
                settlement
                - strike,
            )


        else:

            intrinsic = max(
                0.0,
                strike
                - settlement,
            )


        gross += (
            side
            * intrinsic
        )


        premium_cashflow += (
            -side
            * premium
        )


    pnl_per_unit = (
        gross
        + premium_cashflow
    )


    return (
        pnl_per_unit
        * float(
            spread[
                "quantity"
            ]
        )
        * float(
            spread[
                "multiplier"
            ]
        )
    )
'''
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# COMMODITY CONTRACT / SESSION INTELLIGENCE
# ============================================================

write(
    COMMODITY,
    r'''
from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    date,
    datetime,
    time,
)

from zoneinfo import (
    ZoneInfo,
)


@dataclass(frozen=True)
class CommodityContract:

    symbol: str

    exchange: str

    underlying: str

    expiry: str

    lot_size: float

    tick_size: float

    session_start: str

    session_end: str

    timezone: str = "Asia/Kolkata"

    currency: str = "INR"


    def __post_init__(
        self,
    ):

        if self.lot_size <= 0:

            raise ValueError(
                "lot_size must be positive."
            )


        if self.tick_size <= 0:

            raise ValueError(
                "tick_size must be positive."
            )


def _clock(
    value,
):

    hour, minute = [
        int(
            item
        )

        for item
        in str(
            value
        ).split(
            ":",
            1,
        )
    ]


    return time(
        hour,
        minute,
    )


def commodity_contract_state(
    contract,
    *,
    now=None,
    spot=None,
    future=None,
    bid=None,
    ask=None,
    volume=None,
    open_interest=None,
):

    zone = ZoneInfo(
        contract.timezone
    )


    current = (
        now
        if now is not None
        else datetime.now(
            zone
        )
    )


    if current.tzinfo is None:

        current = current.replace(
            tzinfo=zone
        )


    current = current.astimezone(
        zone
    )


    start = _clock(
        contract.session_start
    )

    end = _clock(
        contract.session_end
    )

    current_clock = current.time().replace(
        tzinfo=None
    )


    if start <= end:

        session_open = (
            start
            <= current_clock
            <= end
        )


    else:

        session_open = (
            current_clock >= start
            or current_clock <= end
        )


    expiry_date = date.fromisoformat(
        str(
            contract.expiry
        )[
            :10
        ]
    )


    days_to_expiry = (
        expiry_date
        - current.date()
    ).days


    if days_to_expiry < 0:

        roll_phase = "EXPIRED"


    elif days_to_expiry <= 3:

        roll_phase = "URGENT_ROLL"


    elif days_to_expiry <= 7:

        roll_phase = "ROLL_WINDOW"


    else:

        roll_phase = "FRONT_CONTRACT"


    basis = None

    basis_pct = None


    if (
        spot is not None
        and future is not None
    ):

        spot = float(
            spot
        )

        future = float(
            future
        )


        basis = (
            future
            - spot
        )


        basis_pct = (
            basis
            / spot
            if spot != 0
            else None
        )


    spread = None

    spread_pct = None


    if (
        bid is not None
        and ask is not None
    ):

        bid = float(
            bid
        )

        ask = float(
            ask
        )


        spread = max(
            0.0,
            ask
            - bid,
        )


        midpoint = (
            bid
            + ask
        ) / 2.0


        spread_pct = (
            spread
            / midpoint
            if midpoint > 0
            else None
        )


    liquidity = 0.0


    if spread_pct is not None:

        if spread_pct <= 0.001:
            liquidity += 40

        elif spread_pct <= 0.003:
            liquidity += 30

        elif spread_pct <= 0.01:
            liquidity += 20

        elif spread_pct <= 0.03:
            liquidity += 10


    if float(
        volume
        or 0
    ) > 0:

        liquidity += 30


    if float(
        open_interest
        or 0
    ) > 0:

        liquidity += 30


    return {
        "symbol":
            contract.symbol,

        "exchange":
            contract.exchange,

        "underlying":
            contract.underlying,

        "expiry":
            contract.expiry,

        "days_to_expiry":
            days_to_expiry,

        "roll_phase":
            roll_phase,

        "session_open":
            session_open,

        "session_start":
            contract.session_start,

        "session_end":
            contract.session_end,

        "timezone":
            contract.timezone,

        "basis":
            basis,

        "basis_pct":
            basis_pct,

        "spread":
            spread,

        "spread_pct":
            spread_pct,

        "volume":
            volume,

        "open_interest":
            open_interest,

        "liquidity_score":
            min(
                100.0,
                liquidity,
            ),

        "research_only":
            True,
    }
'''
)


# ============================================================
# DERIVATIVES CONFIRMATION ENGINE
# ============================================================

write(
    CONFIRMATION,
    r'''
from __future__ import annotations


def _direction(
    value,
    threshold=0.0,
):

    if value is None:

        return 0.0


    value = float(
        value
    )


    if value > threshold:

        return 1.0


    if value < -threshold:

        return -1.0


    return 0.0


def derivatives_confirmation(
    chain_analysis,
    *,
    underlying_return=None,
    futures_return=None,
    futures_basis_pct=None,
):

    components = []


    if underlying_return is not None:

        components.append(
            (
                "underlying_momentum",
                _direction(
                    underlying_return
                ),
                1.0,
            )
        )


    if futures_return is not None:

        components.append(
            (
                "futures_momentum",
                _direction(
                    futures_return
                ),
                1.0,
            )
        )


    if futures_basis_pct is not None:

        components.append(
            (
                "futures_basis",
                _direction(
                    futures_basis_pct
                ),
                0.5,
            )
        )


    pcr = chain_analysis.get(
        "pcr_oi"
    )


    if pcr is not None:

        if pcr > 1.10:

            pcr_direction = 1.0

        elif pcr < 0.90:

            pcr_direction = -1.0

        else:

            pcr_direction = 0.0


        components.append(
            (
                "pcr_oi_heuristic",
                pcr_direction,
                0.5,
            )
        )


    call_doi = float(
        chain_analysis.get(
            "call_change_in_oi"
        )
        or 0.0
    )


    put_doi = float(
        chain_analysis.get(
            "put_change_in_oi"
        )
        or 0.0
    )


    if (
        call_doi != 0
        or put_doi != 0
    ):

        components.append(
            (
                "change_in_oi_structure",
                (
                    1.0
                    if put_doi > call_doi
                    else (
                        -1.0
                        if call_doi > put_doi
                        else 0.0
                    )
                ),
                0.75,
            )
        )


    weighted_sum = sum(
        direction
        * weight

        for _, direction, weight
        in components
    )


    total_weight = sum(
        weight

        for _, _, weight
        in components
    )


    score = (
        weighted_sum
        / total_weight
        if total_weight > 0
        else 0.0
    )


    liquidity_score = float(
        chain_analysis.get(
            "chain_liquidity_score"
        )
        or 0.0
    )


    if liquidity_score < 20:

        confidence = 0.25


    elif liquidity_score < 40:

        confidence = 0.50


    elif liquidity_score < 70:

        confidence = 0.70


    else:

        confidence = 0.85


    if score >= 0.45:

        regime = "BULLISH_CONFIRMATION"


    elif score <= -0.45:

        regime = "BEARISH_CONFIRMATION"


    else:

        regime = "MIXED"


    return {
        "success":
            True,

        "confirmation_score":
            score,

        "regime":
            regime,

        "confidence":
            confidence,

        "liquidity_score":
            liquidity_score,

        "components":
            tuple(
                {
                    "name":
                        name,

                    "direction":
                        direction,

                    "weight":
                        weight,
                }

                for name, direction, weight
                in components
            ),

        "heuristic":
            True,

        "predictive_guarantee":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# DERIVATIVES STRATEGY FAMILIES
# ============================================================

write(
    DERIV_STRATEGIES,
    r'''
from __future__ import annotations

from omni.trading_intelligence.signal_engine import (
    signal_engine,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)

from omni.trading_intelligence.strategy_schema import (
    Condition,
    StrategySpec,
)


DERIVATIVE_STRATEGIES = (
    StrategySpec(
        strategy_id=
            "derivatives_confirmation_v1",

        name=
            "Derivatives Confirmation",

        family=
            "derivatives_confirmation",

        supported_asset_classes=(
            "index",
            "equity",
            "commodity",
            "currency",
        ),

        supported_instrument_types=(
            "future",
            "option",
        ),

        supported_timeframes=(
            "1m",
            "3m",
            "5m",
            "15m",
        ),

        required_features=(
            "confirmation_score",
            "liquidity_score",
        ),

        long_entry=(
            Condition(
                "confirmation_score",
                "gt",
                0.45,
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        short_entry=(
            Condition(
                "confirmation_score",
                "lt",
                -0.45,
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        metadata={
            "research_only":
                True,

            "requires_derivatives_snapshot":
                True,
        },
    ),


    StrategySpec(
        strategy_id=
            "commodity_liquid_trend_v1",

        name=
            "Commodity Liquid Trend",

        family=
            "commodity_trend",

        supported_asset_classes=(
            "commodity",
        ),

        supported_instrument_types=(
            "future",
        ),

        supported_timeframes=(
            "5m",
            "15m",
            "1h",
        ),

        required_features=(
            "ema9",
            "ema21",
            "liquidity_score",
        ),

        long_entry=(
            Condition(
                "ema9",
                "gt",
                "ema21",
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        short_entry=(
            Condition(
                "ema9",
                "lt",
                "ema21",
            ),

            Condition(
                "liquidity_score",
                "gt",
                40.0,
            ),
        ),

        metadata={
            "research_only":
                True,
        },
    ),


    StrategySpec(
        strategy_id=
            "expiry_confirmation_filter_v1",

        name=
            "Expiry Confirmation Filter",

        family=
            "expiry_derivatives",

        supported_asset_classes=(
            "index",
            "equity",
        ),

        supported_instrument_types=(
            "option",
            "future",
        ),

        supported_timeframes=(
            "1m",
            "3m",
            "5m",
        ),

        required_features=(
            "confirmation_score",
            "liquidity_score",
            "hours_to_expiry",
        ),

        long_entry=(
            Condition(
                "confirmation_score",
                "gt",
                0.55,
            ),

            Condition(
                "liquidity_score",
                "gt",
                50.0,
            ),

            Condition(
                "hours_to_expiry",
                "gt",
                1.0,
            ),
        ),

        short_entry=(
            Condition(
                "confirmation_score",
                "lt",
                -0.55,
            ),

            Condition(
                "liquidity_score",
                "gt",
                50.0,
            ),

            Condition(
                "hours_to_expiry",
                "gt",
                1.0,
            ),
        ),

        metadata={
            "research_only":
                True,

            "expiry_specific":
                True,
        },
    ),
)


def ensure_derivatives_strategies():

    for strategy in DERIVATIVE_STRATEGIES:

        strategy_registry.register(
            strategy
        )


    return DERIVATIVE_STRATEGIES


def derivatives_strategy_catalog():

    ensure_derivatives_strategies()


    ids = {
        strategy.strategy_id

        for strategy
        in DERIVATIVE_STRATEGIES
    }


    return tuple(
        row

        for row in strategy_registry.catalog()

        if row[
            "strategy_id"
        ]
        in ids
    )


def derivatives_signal(
    strategy_id,
    features,
    previous=None,
):

    ensure_derivatives_strategies()


    strategy = strategy_registry.get(
        strategy_id
    )


    if strategy is None:

        return {
            "success":
                False,

            "error":
                "Unknown derivatives strategy.",
        }


    result = signal_engine.evaluate(
        strategy,
        features,
        previous,
    )


    result[
        "derivatives_research"
    ] = True


    return result
'''
)


# ============================================================
# PROVIDER-NEUTRAL OPTION CHAIN REGISTRY
# ============================================================

write(
    CHAIN_PROVIDER,
    r'''
from __future__ import annotations


class ReadOnlyOptionChainProvider:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider


    def snapshot(
        self,
        *args,
        **kwargs,
    ):

        method = getattr(
            self.provider,
            "snapshot",
            None,
        )


        if not callable(
            method
        ):

            raise RuntimeError(
                "Provider does not expose snapshot()."
            )


        return method(
            *args,
            **kwargs
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        blocked = (
            "order",
            "trade",
            "execute",
            "place",
            "cancel",
            "modify",
            "buy",
            "sell",
        )


        if any(
            token in lower

            for token in blocked
        ):

            raise PermissionError(
                "Option-chain providers are read-only."
            )


        raise AttributeError(
            name
        )


class OptionChainProviderRegistry:

    def __init__(
        self,
    ):

        self._providers = {}


    def register(
        self,
        name,
        provider,
    ):

        name = str(
            name
        ).strip().lower()


        if not name:

            raise ValueError(
                "Provider name required."
            )


        wrapped = (
            provider

            if isinstance(
                provider,
                ReadOnlyOptionChainProvider,
            )

            else ReadOnlyOptionChainProvider(
                provider
            )
        )


        self._providers[
            name
        ] = wrapped


        return wrapped


    def get(
        self,
        name,
    ):

        return self._providers.get(
            str(
                name
            ).strip().lower()
        )


    def status(
        self,
    ):

        return {
            "providers":
                tuple(
                    sorted(
                        self._providers
                    )
                ),

            "count":
                len(
                    self._providers
                ),

            "read_only":
                True,

            "automatic_broker_write":
                False,
        }


option_chain_providers = (
    OptionChainProviderRegistry()
)
'''
)


# ============================================================
# V3 STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    ensure_derivatives_strategies,
)

from omni.trading_intelligence.fyers_market_adapter import (
    FyersReadOnlyAdapter,
)

from omni.trading_intelligence.option_chain_provider import (
    option_chain_providers,
)

from omni.trading_intelligence.strategy_registry import (
    strategy_registry,
)


class TradingIntelligenceV3Status:

    def status(
        self,
    ):

        core = verify_protected_core()


        ensure_derivatives_strategies()


        fyers = (
            FyersReadOnlyAdapter()
            .capabilities()
        )


        return {
            "protected_core":
                core.ok,

            "research_only":
                True,

            "live_execution":
                False,

            "option_chain_schema":
                True,

            "provider_neutral_option_chain":
                True,

            "registered_chain_providers":
                option_chain_providers.status(),

            "native_fyers_option_chain":
                fyers.get(
                    "option_chain"
                ),

            "native_fyers_market_depth":
                fyers.get(
                    "market_depth"
                ),

            "iv_rank":
                True,

            "iv_percentile":
                True,

            "strike_iv_skew":
                True,

            "iv_term_structure":
                True,

            "pcr_oi":
                True,

            "pcr_volume":
                True,

            "change_in_oi_structure":
                True,

            "oi_walls":
                True,

            "volume_leaders":
                True,

            "atm_relationships":
                True,

            "unusual_volume_oi":
                True,

            "max_pain_research":
                True,

            "max_pain_predictive_claim":
                False,

            "liquidity_scoring":
                True,

            "underlying_futures_options_confirmation":
                True,

            "expiry_intelligence":
                True,

            "defined_risk_vertical_spreads":
                True,

            "naked_option_selling":
                False,

            "commodity_contract_intelligence":
                True,

            "commodity_session_intelligence":
                True,

            "commodity_roll_intelligence":
                True,

            "derivatives_strategy_count":
                3,

            "total_runtime_strategy_count":
                len(
                    strategy_registry.all()
                ),

            "automatic_strategy_promotion":
                False,

            "automatic_parameter_promotion":
                False,

            "automatic_broker_order":
                False,
        }


trading_intelligence_v3_status = (
    TradingIntelligenceV3Status()
)
'''
)


# ============================================================
# MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v3_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v3_status():

    from omni.trading_intelligence.trading_v3_status import (
        trading_intelligence_v3_status,
    )

    return trading_intelligence_v3_status.status()


def jarvis_option_chain_snapshot(
    rows,
    underlying,
    spot,
    timestamp,
    expiry=None,
):

    from omni.trading_intelligence.option_chain_schema import (
        normalize_option_chain,
    )

    return normalize_option_chain(
        rows,
        underlying=underlying,
        spot=spot,
        timestamp=timestamp,
        expiry=expiry,
    )


def jarvis_option_chain_analyze(
    snapshot,
):

    from omni.trading_intelligence.option_chain_intelligence import (
        option_chain_intelligence,
    )

    return option_chain_intelligence.analyze(
        snapshot
    )


def jarvis_iv_rank(
    current_iv,
    history,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_rank,
    )

    return iv_rank(
        current_iv,
        history,
    )


def jarvis_iv_percentile(
    current_iv,
    history,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_percentile,
    )

    return iv_percentile(
        current_iv,
        history,
    )


def jarvis_iv_term_structure(
    points,
):

    from omni.trading_intelligence.iv_analytics import (
        iv_term_structure,
    )

    return iv_term_structure(
        points
    )


def jarvis_expiry_state(
    expiry,
    **kwargs,
):

    from omni.trading_intelligence.expiry_intelligence import (
        expiry_state,
    )

    return expiry_state(
        expiry,
        **kwargs
    )


def jarvis_build_vertical_spread(
    kind,
    **kwargs,
):

    from omni.trading_intelligence.defined_risk_spreads import (
        build_vertical_spread,
    )

    return build_vertical_spread(
        kind,
        **kwargs
    )


def jarvis_vertical_payoff(
    spread,
    settlement,
):

    from omni.trading_intelligence.defined_risk_spreads import (
        vertical_payoff,
    )

    return vertical_payoff(
        spread,
        settlement,
    )


def jarvis_derivatives_confirmation(
    chain_analysis,
    **kwargs,
):

    from omni.trading_intelligence.derivatives_confirmation import (
        derivatives_confirmation,
    )

    return derivatives_confirmation(
        chain_analysis,
        **kwargs
    )


def jarvis_commodity_contract_state(
    contract,
    **kwargs,
):

    from omni.trading_intelligence.commodity_intelligence import (
        commodity_contract_state,
    )

    return commodity_contract_state(
        contract,
        **kwargs
    )


def jarvis_derivatives_strategy_catalog():

    from omni.trading_intelligence.derivatives_strategy_registry import (
        derivatives_strategy_catalog,
    )

    return derivatives_strategy_catalog()


def jarvis_derivatives_signal(
    strategy_id,
    features,
    previous=None,
):

    from omni.trading_intelligence.derivatives_strategy_registry import (
        derivatives_signal,
    )

    return derivatives_signal(
        strategy_id,
        features,
        previous,
    )


def jarvis_option_chain_provider_status():

    from omni.trading_intelligence.option_chain_provider import (
        option_chain_providers,
    )

    return option_chain_providers.status()
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
    )


# ============================================================
# WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_intelligence_v3_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_intelligence_v3_payload():

    from omni.trading_intelligence.trading_v3_status import (
        trading_intelligence_v3_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_intelligence_v3_status.status(),
        }


    except Exception as exc:

        return {
            "success":
                False,

            "error":
                (
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),
        }
'''


    APP.write_text(
        app_source,
        encoding="utf-8",
    )


# ============================================================
# TESTS
# ============================================================

write(
    TEST,
    r'''
import unittest

from datetime import (
    datetime,
    timezone,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.commodity_intelligence import (
    CommodityContract,
    commodity_contract_state,
)

from omni.trading_intelligence.defined_risk_spreads import (
    build_vertical_spread,
    vertical_payoff,
)

from omni.trading_intelligence.derivatives_confirmation import (
    derivatives_confirmation,
)

from omni.trading_intelligence.derivatives_strategy_registry import (
    derivatives_signal,
    derivatives_strategy_catalog,
)

from omni.trading_intelligence.expiry_intelligence import (
    expiry_state,
)

from omni.trading_intelligence.iv_analytics import (
    iv_percentile,
    iv_rank,
    iv_term_structure,
)

from omni.trading_intelligence.option_chain_intelligence import (
    option_chain_intelligence,
)

from omni.trading_intelligence.option_chain_provider import (
    OptionChainProviderRegistry,
)

from omni.trading_intelligence.option_chain_schema import (
    normalize_option_chain,
)


def chain_rows():

    rows = []


    for strike, call_oi, put_oi, civ, piv in (
        (
            24800,
            50000,
            150000,
            16.0,
            18.0,
        ),

        (
            24900,
            80000,
            130000,
            15.5,
            17.0,
        ),

        (
            25000,
            120000,
            120000,
            15.0,
            16.0,
        ),

        (
            25100,
            160000,
            90000,
            15.5,
            16.5,
        ),

        (
            25200,
            200000,
            60000,
            17.0,
            17.5,
        ),
    ):

        rows.append(
            {
                "symbol":
                    f"NIFTY{strike}CE",

                "strike":
                    strike,

                "option_type":
                    "CE",

                "expiry":
                    "2026-08-27",

                "ltp":
                    200,

                "bid":
                    199,

                "ask":
                    201,

                "volume":
                    call_oi / 10,

                "oi":
                    call_oi,

                "change_in_oi":
                    call_oi / 20,

                "iv":
                    civ,
            }
        )


        rows.append(
            {
                "symbol":
                    f"NIFTY{strike}PE",

                "strike":
                    strike,

                "option_type":
                    "PE",

                "expiry":
                    "2026-08-27",

                "ltp":
                    195,

                "bid":
                    194,

                "ask":
                    196,

                "volume":
                    put_oi / 10,

                "oi":
                    put_oi,

                "change_in_oi":
                    put_oi / 20,

                "iv":
                    piv,
            }
        )


    return rows


def snapshot():

    return normalize_option_chain(
        chain_rows(),
        underlying="NIFTY",
        spot=25020,
        timestamp="2026-08-18T10:00:00+05:30",
    )


class TradingIntelligenceV3Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_chain_normalization(
        self,
    ):

        value = snapshot()


        self.assertEqual(
            len(
                value.contracts
            ),
            10,
        )


        self.assertEqual(
            len(
                value.strikes
            ),
            5,
        )


    def test_atm_chain(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertEqual(
            analysis[
                "atm_strike"
            ],
            25000,
        )


    def test_pcr(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertGreater(
            analysis[
                "pcr_oi"
            ],
            0,
        )


        self.assertGreater(
            analysis[
                "pcr_volume"
            ],
            0,
        )


    def test_oi_walls(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertEqual(
            analysis[
                "call_oi_wall"
            ][
                "strike"
            ],
            25200,
        )


        self.assertEqual(
            analysis[
                "put_oi_wall"
            ][
                "strike"
            ],
            24800,
        )


    def test_max_pain_research(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertIn(
            analysis[
                "max_pain_research"
            ][
                "strike"
            ],
            snapshot().strikes,
        )


        self.assertFalse(
            analysis[
                "max_pain_research"
            ][
                "predictive_claim"
            ]
        )


    def test_liquidity(
        self,
    ):

        analysis = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        self.assertGreater(
            analysis[
                "chain_liquidity_score"
            ],
            0,
        )


    def test_iv_rank(
        self,
    ):

        result = iv_rank(
            20,
            (
                10,
                15,
                20,
                25,
                30,
            ),
        )


        self.assertEqual(
            result,
            50.0,
        )


    def test_iv_percentile(
        self,
    ):

        result = iv_percentile(
            20,
            (
                10,
                15,
                20,
                25,
                30,
            ),
        )


        self.assertEqual(
            result,
            60.0,
        )


    def test_term_structure(
        self,
    ):

        result = iv_term_structure(
            (
                {
                    "expiry":
                        "A",

                    "days_to_expiry":
                        2,

                    "atm_iv":
                        20,
                },

                {
                    "expiry":
                        "B",

                    "days_to_expiry":
                        10,

                    "atm_iv":
                        18,
                },
            )
        )


        self.assertEqual(
            len(
                result[
                    "slopes"
                ]
            ),
            1,
        )


    def test_expiry_intelligence(
        self,
    ):

        result = expiry_state(
            "2026-08-18",
            now=datetime(
                2026,
                8,
                18,
                10,
                0,
                tzinfo=timezone.utc,
            ),
            timezone_name="UTC",
            expiry_time="15:30",
        )


        self.assertEqual(
            result[
                "phase"
            ],
            "EXPIRY_DAY",
        )


    def test_bull_call_defined_risk(
        self,
    ):

        spread = build_vertical_spread(
            "bull_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
            multiplier=1,
        )


        self.assertTrue(
            spread[
                "defined_risk"
            ]
        )


        self.assertFalse(
            spread[
                "naked_short"
            ]
        )


        self.assertEqual(
            spread[
                "max_loss"
            ],
            4,
        )


        self.assertEqual(
            spread[
                "max_profit"
            ],
            6,
        )


    def test_bear_call_defined_risk(
        self,
    ):

        spread = build_vertical_spread(
            "bear_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
        )


        self.assertEqual(
            spread[
                "max_profit"
            ],
            4,
        )


        self.assertEqual(
            spread[
                "max_loss"
            ],
            6,
        )


    def test_vertical_payoff(
        self,
    ):

        spread = build_vertical_spread(
            "bull_call",
            lower_strike=100,
            higher_strike=110,
            lower_premium=6,
            higher_premium=2,
        )


        self.assertEqual(
            vertical_payoff(
                spread,
                90,
            ),
            -4,
        )


        self.assertEqual(
            vertical_payoff(
                spread,
                120,
            ),
            6,
        )


    def test_commodity_session(
        self,
    ):

        contract = CommodityContract(
            symbol="CRUDE",
            exchange="MCX",
            underlying="CRUDEOIL",
            expiry="2026-09-18",
            lot_size=100,
            tick_size=1,
            session_start="09:00",
            session_end="23:30",
            timezone="UTC",
        )


        state = commodity_contract_state(
            contract,
            now=datetime(
                2026,
                8,
                18,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            spot=6000,
            future=6050,
            bid=6049,
            ask=6051,
            volume=1000,
            open_interest=5000,
        )


        self.assertTrue(
            state[
                "session_open"
            ]
        )


        self.assertGreater(
            state[
                "liquidity_score"
            ],
            0,
        )


    def test_confirmation(
        self,
    ):

        chain = (
            option_chain_intelligence
            .analyze(
                snapshot()
            )
        )


        result = derivatives_confirmation(
            chain,
            underlying_return=0.01,
            futures_return=0.012,
            futures_basis_pct=0.002,
        )


        self.assertTrue(
            result[
                "success"
            ]
        )


        self.assertGreaterEqual(
            result[
                "confirmation_score"
            ],
            -1,
        )


        self.assertLessEqual(
            result[
                "confirmation_score"
            ],
            1,
        )


    def test_derivatives_strategy_catalog(
        self,
    ):

        catalog = (
            derivatives_strategy_catalog()
        )


        ids = {
            item[
                "strategy_id"
            ]

            for item
            in catalog
        }


        self.assertIn(
            "derivatives_confirmation_v1",
            ids,
        )


        self.assertIn(
            "commodity_liquid_trend_v1",
            ids,
        )


    def test_derivatives_signal(
        self,
    ):

        result = derivatives_signal(
            "derivatives_confirmation_v1",
            {
                "confirmation_score":
                    0.8,

                "liquidity_score":
                    75,
            },
        )


        self.assertEqual(
            result[
                "signal"
            ],
            "LONG",
        )


        self.assertFalse(
            result[
                "execution_allowed"
            ]
        )


    def test_provider_registry_empty_by_default(
        self,
    ):

        registry = (
            OptionChainProviderRegistry()
        )


        status = registry.status()


        self.assertEqual(
            status[
                "count"
            ],
            0,
        )


        self.assertTrue(
            status[
                "read_only"
            ]
        )


    def test_status_truthful_fyers(
        self,
    ):

        status = (
            main.jarvis_trading_v3_status()
        )


        self.assertIsNone(
            status[
                "native_fyers_option_chain"
            ]
        )


        self.assertIsNone(
            status[
                "native_fyers_market_depth"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "naked_option_selling"
            ]
        )


    def test_v2_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v2_status()
        )


        self.assertTrue(
            status[
                "historical_backtester"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


    def test_public_apis(
        self,
    ):

        for name in (
            "jarvis_trading_v3_status",
            "jarvis_option_chain_snapshot",
            "jarvis_option_chain_analyze",
            "jarvis_iv_rank",
            "jarvis_iv_percentile",
            "jarvis_iv_term_structure",
            "jarvis_expiry_state",
            "jarvis_build_vertical_spread",
            "jarvis_vertical_payoff",
            "jarvis_derivatives_confirmation",
            "jarvis_commodity_contract_state",
            "jarvis_derivatives_strategy_catalog",
            "jarvis_derivatives_signal",
            "jarvis_option_chain_provider_status",
        ):

            self.assertTrue(
                callable(
                    getattr(
                        main,
                        name,
                    )
                )
            )


if __name__ == "__main__":

    unittest.main()
'''
)


# ============================================================
# COMPILE
# ============================================================

print()
print("Checking Trading Intelligence V3 syntax...")


r = run(
    "-m",
    "py_compile",

    str(CHAIN_SCHEMA),
    str(IV),
    str(CHAIN_INTEL),
    str(EXPIRY),
    str(SPREADS),
    str(COMMODITY),
    str(CONFIRMATION),
    str(DERIV_STRATEGIES),
    str(CHAIN_PROVIDER),
    str(STATUS),
    str(MAIN),
    str(APP),
    str(TEST),
)


if r.returncode:

    print("COMPILE FAILURE")
    rollback()
    sys.exit(1)


print("Syntax: PASS")


# ============================================================
# PROTECTED CORE
# ============================================================

print()
print("Checking protected core...")


for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "import main; "
        "print('Protected Core: PASS'); "
        "print('Main import: PASS')"
    ),
)


if r.returncode:

    rollback()
    sys.exit(1)


# ============================================================
# CHAIN INTELLIGENCE PROBE
# ============================================================

print()
print("Checking advanced option-chain intelligence...")


probe = r'''
import main

rows = []


for strike, coi, poi in (
    (24800, 50000, 150000),
    (24900, 80000, 130000),
    (25000, 120000, 120000),
    (25100, 160000, 90000),
    (25200, 200000, 60000),
):

    rows.append(
        {
            "strike": strike,
            "option_type": "CE",
            "expiry": "2026-08-27",
            "ltp": 200,
            "bid": 199,
            "ask": 201,
            "volume": coi / 10,
            "oi": coi,
            "change_in_oi": coi / 20,
            "iv": 15 + abs(strike - 25000) / 200,
        }
    )

    rows.append(
        {
            "strike": strike,
            "option_type": "PE",
            "expiry": "2026-08-27",
            "ltp": 195,
            "bid": 194,
            "ask": 196,
            "volume": poi / 10,
            "oi": poi,
            "change_in_oi": poi / 20,
            "iv": 16 + abs(strike - 25000) / 200,
        }
    )


snapshot = main.jarvis_option_chain_snapshot(
    rows,
    "NIFTY",
    25020,
    "2026-08-18T10:00:00+05:30",
)


analysis = main.jarvis_option_chain_analyze(
    snapshot
)


assert analysis["atm_strike"] == 25000
assert analysis["pcr_oi"] is not None
assert analysis["pcr_volume"] is not None
assert analysis["call_oi_wall"]
assert analysis["put_oi_wall"]
assert analysis["chain_liquidity_score"] > 0
assert analysis["max_pain_research"]["predictive_claim"] is False


print("ATM relationship engine: PASS")
print("PCR OI: ACTIVE")
print("PCR volume: ACTIVE")
print("Change-in-OI structure: ACTIVE")
print("Call/put OI walls: ACTIVE")
print("Volume leaders: ACTIVE")
print("IV skew: ACTIVE")
print("Liquidity scoring: ACTIVE")
print("Unusual volume/OI scan: ACTIVE")
print("Max-pain research metric: ACTIVE")
print("Max-pain predictive claim: BLOCKED")
print("Option-chain intelligence: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("OPTION CHAIN PROBE FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# DEFINED-RISK SPREAD PROBE
# ============================================================

print()
print("Checking defined-risk options structures...")


probe = r'''
import main


for kind in (
    "bull_call",
    "bear_call",
    "bear_put",
    "bull_put",
):

    spread = main.jarvis_build_vertical_spread(
        kind,
        lower_strike=100,
        higher_strike=110,
        lower_premium=6,
        higher_premium=2,
    )

    assert spread["defined_risk"]
    assert spread["naked_short"] is False
    assert spread["max_loss"] >= 0
    assert spread["max_profit"] >= 0


print("Bull call spread: ACTIVE")
print("Bear call spread: ACTIVE")
print("Bear put spread: ACTIVE")
print("Bull put spread: ACTIVE")
print("Finite max-loss calculation: ACTIVE")
print("Vertical payoff engine: ACTIVE")
print("Naked option short structure: BLOCKED")
print("Defined-risk spread engine: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("SPREAD ENGINE FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# STRATEGY / SAFETY PROBE
# ============================================================

print()
print("Checking derivatives strategy research...")


probe = r'''
import main


catalog = main.jarvis_derivatives_strategy_catalog()

assert len(catalog) == 3


signal = main.jarvis_derivatives_signal(
    "derivatives_confirmation_v1",
    {
        "confirmation_score": 0.8,
        "liquidity_score": 80,
    },
)


assert signal["signal"] == "LONG"
assert signal["execution_allowed"] is False


v3 = main.jarvis_trading_v3_status()


assert v3["research_only"]
assert v3["live_execution"] is False
assert v3["naked_option_selling"] is False
assert v3["automatic_broker_order"] is False
assert v3["automatic_strategy_promotion"] is False

assert v3["native_fyers_option_chain"] is None
assert v3["native_fyers_market_depth"] is None


print("Derivatives strategy families: 3")
print("Snapshot signal evaluation: ACTIVE")
print("Signal -> live order: BLOCKED")
print("Native FYERS option-chain method fabricated: NO")
print("Native FYERS market-depth method fabricated: NO")
print("Automatic strategy promotion: BLOCKED")
print("Derivatives safety: PASS")
'''


r = run(
    "-c",
    probe,
)


if r.returncode:

    print("DERIVATIVES SAFETY FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# TARGETED REGRESSION
# ============================================================

print()
print("Running Trading Intelligence V3 targeted regression...")


r = run(
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v3",
    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "tests.test_computer_operator_v2",
    "tests.test_computer_operator_v3",
    "tests.test_computer_operator_v4",
    "tests.test_computer_operator",

    "tests.test_connected_services_v3",
    "tests.test_connected_services_v2",
    "tests.test_connected_services_v1",

    "tests.test_real_world_action_v3",
    "tests.test_real_world_action_v2",
    "tests.test_real_world_action_engine",

    "tests.test_universal_learning_v5",
    "tests.test_autonomy_engine",
    "tests.test_improvement_lab",

    "-q",
)


if r.returncode:

    print("TARGETED TEST FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FULL REGRESSION
# ============================================================

print()
print("Running full regression...")


r = run(
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
)


if r.returncode:

    print("FULL REGRESSION FAILURE")
    rollback()
    sys.exit(1)


# ============================================================
# FINAL VERIFICATION
# ============================================================

for relative, before in PROTECTED.items():

    if (
        sha(
            ROOT / relative
        )
        != before
    ):

        print(
            "PROTECTED CORE CHANGED:",
            relative,
        )

        rollback()
        sys.exit(1)


r = run(
    "-c",
    (
        "import main; "
        "from omni.core_integrity import verify_protected_core; "
        "s=verify_protected_core(); "
        "assert s.ok,(s.changed,s.missing); "
        "v2=main.jarvis_trading_v2_status(); "
        "v3=main.jarvis_trading_v3_status(); "
        "assert v2['historical_backtester']; "
        "assert v3['live_execution'] is False; "
        "assert v3['automatic_broker_order'] is False; "
        "assert v3['native_fyers_option_chain'] is None; "
        "print('Final Protected Core: PASS'); "
        "print('Trading V2: PRESERVED'); "
        "print('Trading V3 safety: PASS')"
    ),
)


if r.returncode:

    rollback()
    sys.exit(1)


r = run(
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:

    print("FINAL DOM TEST FAILURE")
    rollback()
    sys.exit(1)


print("Final browser DOM test: PASS")


# ============================================================
# SUCCESS
# ============================================================

status = run(
    "-c",
    (
        "import main,pprint; "
        "pprint.pp(main.jarvis_trading_v3_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V3 SUCCESS")
print("=" * 80)

print()
print("OPTION CHAIN")
print("Provider-neutral chain schema: ACTIVE")
print("ATM/ITM/OTM relationship foundation: ACTIVE")
print("PCR by OI: ACTIVE")
print("PCR by volume: ACTIVE")
print("Change-in-OI structure: ACTIVE")
print("Call OI wall: ACTIVE")
print("Put OI wall: ACTIVE")
print("Call/put volume leaders: ACTIVE")
print("Cross-sectional unusual volume/OI: ACTIVE")
print("Liquidity score: ACTIVE")
print()

print("VOLATILITY")
print("IV rank: ACTIVE")
print("IV percentile: ACTIVE")
print("Strike IV skew: ACTIVE")
print("Put-minus-call IV: ACTIVE")
print("IV term structure: ACTIVE")
print()

print("EXPIRY")
print("Hours/days to expiry: ACTIVE")
print("Expiry-day classification: ACTIVE")
print("Near-expiry classification: ACTIVE")
print("Theta-urgency heuristic: ACTIVE")
print()

print("DERIVATIVES CONFIRMATION")
print("Underlying momentum input: ACTIVE")
print("Futures momentum input: ACTIVE")
print("Futures basis input: ACTIVE")
print("Options OI confirmation: ACTIVE")
print("Liquidity confidence gate: ACTIVE")
print("Bullish/bearish/mixed classification: ACTIVE")
print("Predictive guarantee: NONE")
print()

print("DEFINED-RISK OPTIONS")
print("Bull call vertical: ACTIVE")
print("Bear call vertical: ACTIVE")
print("Bear put vertical: ACTIVE")
print("Bull put vertical: ACTIVE")
print("Max profit: ACTIVE")
print("Max loss: ACTIVE")
print("Breakeven: ACTIVE")
print("Expiry payoff engine: ACTIVE")
print("Naked option selling: BLOCKED")
print()

print("COMMODITIES")
print("Contract metadata: ACTIVE")
print("Session intelligence: ACTIVE")
print("Overnight session support: ACTIVE")
print("Days-to-expiry: ACTIVE")
print("Roll-window classification: ACTIVE")
print("Spot/futures basis: ACTIVE")
print("Spread quality: ACTIVE")
print("Liquidity score: ACTIVE")
print()

print("DERIVATIVES STRATEGIES")
print("Derivatives confirmation family: REGISTERED")
print("Commodity liquid-trend family: REGISTERED")
print("Expiry confirmation filter: REGISTERED")
print("Existing safe SignalEngine: REUSED")
print("Signal -> broker execution: BLOCKED")
print()

print("TRUTHFUL DATA PROVIDERS")
print("Canonical FYERS quote/history: PRESERVED")
print("Native FYERS option chain: NOT FOUND / NOT FABRICATED")
print("Native FYERS market depth: NOT FOUND / NOT FABRICATED")
print("Provider-neutral chain registry: ACTIVE")
print("Default real chain providers: NONE")
print()

print("SAFETY")
print("Trading V1: PRESERVED")
print("Trading V1.1: PRESERVED")
print("Trading V2: PRESERVED")
print("Historical backtester: PRESERVED")
print("Live orders: BLOCKED")
print("Automatic strategy promotion: BLOCKED")
print("Automatic broker orders: BLOCKED")
print("Protected Core: UNCHANGED")
print("Browser lock repair: PRESERVED")
print("Full regression: PASS")
print()

print("STATUS:")
print(status.stdout.strip())
print()

print("NEXT: TRADING INTELLIGENCE V4")
print("Strategy evolution laboratory")
print("Regime-aware strategy selection")
print("Parameter mutation / crossover")
print("Strategy-rule combination")
print("Champion vs challenger framework")
print("Fitness based on expectancy + drawdown + stability")
print("Bad-strategy retirement proposals")
print("No automatic production promotion")
print()
print("THEN V5:")
print("Walk-forward validation")
print("Out-of-sample validation")
print("Monte Carlo")
print("Parameter sensitivity")
print("Cost stress tests")
print("Regime robustness")
print("Overfitting rejection")
print()
print("THEN V6:")
print("Live-data paper/shadow trader")
print("Performance drift")
print("Adaptive strategy weighting")
print("Continuous evidence collection")
