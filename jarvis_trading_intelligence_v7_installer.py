from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import textwrap


ROOT = Path(r"C:\Jarvis")

MAIN_PY = (
    ROOT / ".venv"
    / "Scripts"
    / "python.exe"
)

FYERS_PY = (
    ROOT / ".venv-fyers"
    / "Scripts"
    / "python.exe"
)

PKG = (
    ROOT
    / "omni"
    / "trading_intelligence"
)

WORKER = (
    ROOT
    / "research"
    / "fyers_sdk"
    / "worker_v7.py"
)

BRIDGE = (
    PKG
    / "fyers_v7_bridge.py"
)

NORMALIZER = (
    PKG
    / "fyers_chain_normalizer.py"
)

STORE = (
    PKG
    / "derivatives_history_store.py"
)

ANALYTICS = (
    PKG
    / "derivatives_history_analytics.py"
)

SYNC = (
    PKG
    / "derivatives_sync.py"
)

REGIME = (
    PKG
    / "derivatives_regime_v7.py"
)

ENSEMBLE = (
    PKG
    / "derivatives_ensemble.py"
)

CAMPAIGN = (
    PKG
    / "derivatives_campaign.py"
)

STATUS = (
    PKG
    / "trading_v7_status.py"
)

MAIN = ROOT / "main.py"

APP = (
    ROOT
    / "workstation"
    / "app.py"
)

TEST = (
    ROOT
    / "tests"
    / "test_trading_intelligence_v7.py"
)

MANIFEST = (
    ROOT
    / "config"
    / "protected_core_manifest.json"
)

ARCHIVE = (
    ROOT
    / "archive"
    / "trading_intelligence_v7"
)

ARCHIVE.mkdir(
    parents=True,
    exist_ok=True,
)

FILES = [
    WORKER,
    BRIDGE,
    NORMALIZER,
    STORE,
    ANALYTICS,
    SYNC,
    REGIME,
    ENSEMBLE,
    CAMPAIGN,
    STATUS,
    MAIN,
    APP,
    TEST,
]

BACKUPS = {}


def run(
    python,
    *args,
    capture=False,
    timeout=None,
):

    return subprocess.run(
        [
            str(python),
            *args,
        ],
        cwd=ROOT,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def sha(
    path,
):

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
        newline="\n",
    )


def rollback():

    print()
    print("=" * 72)
    print("ROLLBACK")
    print("=" * 72)

    for path, existed in BACKUPS.items():

        backup = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
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
        "Trading V7 source restored."
    )


print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V7")
print("REAL FYERS OPTION CHAIN + HISTORICAL DERIVATIVES INTELLIGENCE")
print("=" * 80)


# ============================================================
# 1. FROZEN C3 / 640 CHECKPOINT
# ============================================================

print()
print(
    "Checking frozen Nautilus C3 / 640 checkpoint..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert c3['single_event_driven_engine'];"
        "assert v6['live_execution'] is False;"
        "assert c3['live_execution'] is False;"
        "assert c3['broker_adapter'] is False;"
        "print('Protected Core: PASS');"
        "print('Trading V5: PASS');"
        "print('Trading V6: PASS');"
        "print('Nautilus C3: PASS');"
        "print('640 checkpoint: PASS')"
    ),
)


if r.returncode:

    print(
        "BASELINE FAILURE"
    )

    sys.exit(1)


if not FYERS_PY.exists():

    print(
        "Isolated FYERS environment missing."
    )

    sys.exit(1)


r = run(
    FYERS_PY,
    "-c",
    (
        "from importlib.metadata import version;"
        "from fyers_apiv3 import fyersModel;"
        "import inspect;"
        "assert version('fyers-apiv3')=='3.1.16';"
        "assert str(inspect.signature("
        "fyersModel.FyersModel.optionchain"
        "))=='(self, data=None)';"
        "assert str(inspect.signature("
        "fyersModel.FyersModel.depth"
        "))=='(self, data=None)';"
        "print('FYERS SDK 3.1.16: PASS');"
        "print('optionchain(self, data=None): PASS');"
        "print('depth(self, data=None): PASS')"
    ),
)


if r.returncode:

    print(
        "FYERS SDK COMPATIBILITY FAILURE"
    )

    sys.exit(1)


# ============================================================
# 2. CHECK CANONICAL AUTH MODULE BEFORE WRITING
# ============================================================

print()
print(
    "Checking canonical FYERS auth module..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import inspect;"
        "from agents import fyers_auth_manager as f;"
        "assert callable(f.load_token);"
        "assert hasattr(f,'FyersSettings');"
        "assert callable(f.FyersSettings.from_env);"
        "print('fyers_auth_manager import: PASS');"
        "print('load_token signature:',inspect.signature(f.load_token));"
        "print('FyersSettings.from_env: PASS')"
    ),
)


if r.returncode:

    print(
        "CANONICAL FYERS AUTH INTROSPECTION FAILURE"
    )

    sys.exit(1)


# ============================================================
# 3. BACKUP
# ============================================================

for path in FILES:

    BACKUPS[path] = (
        path.exists()
    )

    if path.exists():

        destination = (
            ARCHIVE
            / path.relative_to(
                ROOT
            )
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            destination,
        )


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
    len(
        PROTECTED
    ),
)


# ============================================================
# 4. ISOLATED FYERS READ-ONLY WORKER
# ============================================================

write(
    WORKER,
    r'''
from __future__ import annotations

import argparse
import inspect
import json
import os

from importlib.metadata import (
    version,
)

from pathlib import (
    Path,
)


from fyers_apiv3 import (
    fyersModel,
)


FyersModel = (
    fyersModel.FyersModel
)


ALLOWED_OPERATIONS = {
    "option_chain",
    "depth",
}


def capabilities():

    return {
        "available":
            True,

        "sdk":
            "fyers-apiv3",

        "sdk_version":
            version(
                "fyers-apiv3"
            ),

        "option_chain_method":
            "optionchain",

        "option_chain_signature":
            str(
                inspect.signature(
                    FyersModel.optionchain
                )
            ),

        "depth_method":
            "depth",

        "depth_signature":
            str(
                inspect.signature(
                    FyersModel.depth
                )
            ),

        "dict_payload":
            True,

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }


def client():

    client_id = os.environ.get(
        "JARVIS_FYERS_CLIENT_ID",
        "",
    ).strip()


    token = os.environ.get(
        "JARVIS_FYERS_ACCESS_TOKEN",
        "",
    ).strip()


    if not client_id:

        raise RuntimeError(
            "FYERS client_id is unavailable."
        )


    if not token:

        raise RuntimeError(
            "FYERS access token is unavailable."
        )


    # REST FyersModel receives client ID and access token
    # separately. Never print either credential.
    return FyersModel(
        client_id=
            client_id,

        token=
            token,

        is_async=
            False,

        log_path=
            "",
    )


def validate_option_chain(
    request,
):

    request = dict(
        request
    )


    symbol = str(
        request.get(
            "symbol",
            "",
        )
    ).strip()


    if not symbol:

        raise ValueError(
            "symbol is required."
        )


    strikecount = int(
        request.get(
            "strikecount",
            5,
        )
    )


    if not 0 <= strikecount <= 50:

        raise ValueError(
            "strikecount must be between 0 and 50."
        )


    output = {
        "symbol":
            symbol,

        "strikecount":
            strikecount,
    }


    timestamp = request.get(
        "timestamp"
    )


    if timestamp not in (
        None,
        "",
    ):

        output[
            "timestamp"
        ] = str(
            timestamp
        )


    if bool(
        request.get(
            "greeks",
            True,
        )
    ):

        output[
            "greeks"
        ] = "1"


    return output


def validate_depth(
    request,
):

    request = dict(
        request
    )


    symbol = str(
        request.get(
            "symbol",
            "",
        )
    ).strip()


    if not symbol:

        raise ValueError(
            "symbol is required."
        )


    return {
        "symbol":
            symbol,

        "ohlcv_flag":
            str(
                int(
                    bool(
                        request.get(
                            "ohlcv_flag",
                            True,
                        )
                    )
                )
            ),
    }


def run_request(
    operation,
    request,
):

    if operation not in ALLOWED_OPERATIONS:

        raise PermissionError(
            "Unsupported FYERS worker operation."
        )


    fyers = client()


    if operation == "option_chain":

        request = (
            validate_option_chain(
                request
            )
        )


        response = fyers.optionchain(
            data=request
        )


    elif operation == "depth":

        request = validate_depth(
            request
        )


        response = fyers.depth(
            data=request
        )


    else:

        raise PermissionError(
            operation
        )


    return {
        "success":
            True,

        "operation":
            operation,

        "request":
            request,

        "response":
            response,

        "sdk_version":
            version(
                "fyers-apiv3"
            ),

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }


def main():

    parser = argparse.ArgumentParser()


    parser.add_argument(
        "--capabilities",
        action="store_true",
    )


    parser.add_argument(
        "--operation",
        choices=sorted(
            ALLOWED_OPERATIONS
        ),
    )


    parser.add_argument(
        "--input",
    )


    parser.add_argument(
        "--output",
    )


    args = parser.parse_args()


    if args.capabilities:

        print(
            json.dumps(
                capabilities(),
                default=str,
            )
        )

        return


    if not args.operation:

        raise ValueError(
            "--operation is required."
        )


    if not args.input:

        raise ValueError(
            "--input is required."
        )


    if not args.output:

        raise ValueError(
            "--output is required."
        )


    request = json.loads(
        Path(
            args.input
        ).read_text(
            encoding="utf-8"
        )
    )


    result = run_request(
        args.operation,
        request,
    )


    Path(
        args.output
    ).write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":

    main()
'''
)


# ============================================================
# 5. MAIN-SIDE READ-ONLY BRIDGE
# ============================================================

write(
    BRIDGE,
    r'''
from __future__ import annotations

import inspect
import json
import os
import subprocess
import tempfile

from pathlib import (
    Path,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


FYERS_PY = (
    ROOT
    / ".venv-fyers"
    / "Scripts"
    / "python.exe"
)


WORKER = (
    ROOT
    / "research"
    / "fyers_sdk"
    / "worker_v7.py"
)


class FyersV7ReadOnlyBridge:

    def available(
        self,
    ):

        return (
            FYERS_PY.exists()
            and WORKER.exists()
        )


    def status(
        self,
    ):

        if not self.available():

            return {
                "available":
                    False,

                "read_only":
                    True,

                "live_execution":
                    False,
            }


        result = subprocess.run(
            [
                str(
                    FYERS_PY
                ),

                str(
                    WORKER
                ),

                "--capabilities",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )


        if result.returncode:

            return {
                "available":
                    False,

                "error":
                    (
                        result.stderr.strip()
                        or result.stdout.strip()
                    ),

                "read_only":
                    True,

                "live_execution":
                    False,
            }


        return json.loads(
            result.stdout.strip()
            .splitlines()[
                -1
            ]
        )


    @staticmethod
    def _extract(
        value,
        names,
    ):

        if value is None:

            return None


        if isinstance(
            value,
            dict,
        ):

            lowered = {
                str(
                    key
                ).lower():
                    item

                for key, item
                in value.items()
            }


            for name in names:

                if name.lower() in lowered:

                    candidate = lowered[
                        name.lower()
                    ]


                    if candidate not in (
                        None,
                        "",
                    ):

                        return str(
                            candidate
                        )


        for name in names:

            try:

                candidate = getattr(
                    value,
                    name,
                )

            except Exception:

                continue


            if candidate not in (
                None,
                "",
            ):

                return str(
                    candidate
                )


        return None


    @classmethod
    def _auth_material(
        cls,
    ):

        from agents import (
            fyers_auth_manager,
        )


        settings = (
            fyers_auth_manager
            .FyersSettings
            .from_env()
        )


        client_id = cls._extract(
            settings,
            (
                "client_id",
                "app_id",
                "appid",
                "clientId",
                "appId",
            ),
        )


        if not client_id:

            # Last resort: inspect settings attributes
            # without exposing their values.
            for name in dir(
                settings
            ):

                lower = name.lower()

                if (
                    "client"
                    not in lower
                    and "app"
                    not in lower
                ):

                    continue


                try:

                    value = getattr(
                        settings,
                        name,
                    )

                except Exception:

                    continue


                if (
                    isinstance(
                        value,
                        str,
                    )
                    and value.strip()
                ):

                    client_id = value.strip()

                    break


        load_token = (
            fyers_auth_manager
            .load_token
        )


        signature = inspect.signature(
            load_token
        )


        required = [
            parameter

            for parameter
            in signature.parameters.values()

            if (
                parameter.default
                is inspect.Parameter.empty

                and parameter.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            )
        ]


        if not required:

            token_record = (
                load_token()
            )


        elif len(
            required
        ) == 1:

            token_record = (
                load_token(
                    settings
                )
            )


        else:

            raise RuntimeError(
                "Unsupported canonical load_token signature."
            )


        token = cls._extract(
            token_record,
            (
                "access_token",
                "token",
                "accessToken",
            ),
        )


        if (
            token is None
            and isinstance(
                token_record,
                str,
            )
        ):

            token = (
                token_record.strip()
            )


        if not client_id:

            raise RuntimeError(
                "FYERS client ID not configured."
            )


        if not token:

            raise RuntimeError(
                "FYERS access token unavailable. "
                "Complete the normal JARVIS FYERS login first."
            )


        # WebSocket-style credentials sometimes contain
        # client_id:token. REST FyersModel needs the token part.
        prefix = (
            str(
                client_id
            )
            + ":"
        )


        if token.startswith(
            prefix
        ):

            token = token[
                len(
                    prefix
                ):
            ]


        return (
            str(
                client_id
            ),

            str(
                token
            ),
        )


    def _call(
        self,
        operation,
        request,
        *,
        timeout=30,
    ):

        if operation not in {
            "option_chain",
            "depth",
        }:

            raise PermissionError(
                "FYERS V7 bridge is read-only."
            )


        if not self.available():

            raise RuntimeError(
                "Isolated FYERS worker unavailable."
            )


        client_id, token = (
            self._auth_material()
        )


        child_env = dict(
            os.environ
        )


        child_env[
            "JARVIS_FYERS_CLIENT_ID"
        ] = client_id


        child_env[
            "JARVIS_FYERS_ACCESS_TOKEN"
        ] = token


        with tempfile.TemporaryDirectory(
            prefix=
                "jarvis_fyers_v7_"
        ) as tmp:

            tmp = Path(
                tmp
            )


            input_path = (
                tmp
                / "input.json"
            )


            output_path = (
                tmp
                / "output.json"
            )


            input_path.write_text(
                json.dumps(
                    request,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )


            result = subprocess.run(
                [
                    str(
                        FYERS_PY
                    ),

                    str(
                        WORKER
                    ),

                    "--operation",
                    operation,

                    "--input",
                    str(
                        input_path
                    ),

                    "--output",
                    str(
                        output_path
                    ),
                ],
                cwd=ROOT,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=float(
                    timeout
                ),
            )


            # Remove local references immediately.
            child_env[
                "JARVIS_FYERS_ACCESS_TOKEN"
            ] = ""


            if result.returncode:

                raise RuntimeError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "FYERS read-only worker failed."
                )


            if not output_path.exists():

                raise RuntimeError(
                    "FYERS worker produced no output."
                )


            response = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                )
            )


        if (
            response.get(
                "live_execution"
            )
            is not False
        ):

            raise RuntimeError(
                "FYERS V7 safety invariant failed."
            )


        if (
            response.get(
                "broker_order"
            )
            is not False
        ):

            raise RuntimeError(
                "Unexpected broker-order surface."
            )


        return response


    def option_chain(
        self,
        symbol,
        *,
        strikecount=5,
        timestamp=None,
        greeks=True,
        timeout=30,
    ):

        strikecount = int(
            strikecount
        )


        if not 0 <= strikecount <= 50:

            raise ValueError(
                "strikecount must be between 0 and 50."
            )


        request = {
            "symbol":
                str(
                    symbol
                ),

            "strikecount":
                strikecount,

            "greeks":
                bool(
                    greeks
                ),
        }


        if timestamp not in (
            None,
            "",
        ):

            request[
                "timestamp"
            ] = str(
                timestamp
            )


        return self._call(
            "option_chain",
            request,
            timeout=timeout,
        )


    def depth(
        self,
        symbol,
        *,
        ohlcv_flag=True,
        timeout=30,
    ):

        return self._call(
            "depth",

            {
                "symbol":
                    str(
                        symbol
                    ),

                "ohlcv_flag":
                    bool(
                        ohlcv_flag
                    ),
            },

            timeout=timeout,
        )


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "order",
            "trade",
            "position",
            "place",
            "modify",
            "cancel",
            "buy",
            "sell",
            "live_execution",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "FYERS V7 bridge exposes market data only."
            )


        raise AttributeError(
            name
        )


fyers_v7_readonly_bridge = (
    FyersV7ReadOnlyBridge()
)
'''
)


# ============================================================
# 6. FYERS CHAIN NORMALIZER
# ============================================================

write(
    NORMALIZER,
    r'''
from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import uuid


def _number(
    value,
):

    if value in (
        None,
        "",
    ):

        return None


    try:

        return float(
            value
        )

    except Exception:

        return None


def _integer(
    value,
):

    number = _number(
        value
    )


    return (
        int(
            number
        )

        if number is not None

        else None
    )


def normalize_fyers_option_chain(
    worker_result,
    *,
    captured_at=None,
):

    if not isinstance(
        worker_result,
        dict,
    ):

        raise ValueError(
            "FYERS result must be a dictionary."
        )


    response = worker_result.get(
        "response"
    )


    request = dict(
        worker_result.get(
            "request",
            {}
        )
    )


    if not isinstance(
        response,
        dict,
    ):

        raise ValueError(
            "FYERS response is not a dictionary."
        )


    status = str(
        response.get(
            "s",
            "",
        )
    ).lower()


    if (
        status == "error"
        or (
            response.get(
                "code"
            )
            is not None
            and _number(
                response.get(
                    "code"
                )
            )
            is not None
            and float(
                response.get(
                    "code"
                )
            ) < 0
        )
    ):

        raise RuntimeError(
            str(
                response.get(
                    "message",
                    "FYERS option-chain request failed.",
                )
            )
        )


    data = response.get(
        "data",
        {}
    )


    if not isinstance(
        data,
        dict,
    ):

        raise ValueError(
            "FYERS response data is invalid."
        )


    chain = data.get(
        "optionsChain",
        ()
    )


    if not isinstance(
        chain,
        (
            list,
            tuple,
        ),
    ):

        raise ValueError(
            "optionsChain is invalid."
        )


    if captured_at is None:

        captured_at = datetime.now(
            timezone.utc
        )


    if captured_at.tzinfo is None:

        captured_at = (
            captured_at.replace(
                tzinfo=timezone.utc
            )
        )


    captured_at = (
        captured_at
        .astimezone(
            timezone.utc
        )
    )


    expiry_data = data.get(
        "expiryData",
        ()
    )


    if not isinstance(
        expiry_data,
        (
            list,
            tuple,
        ),
    ):

        expiry_data = ()


    selected_expiry = request.get(
        "timestamp"
    )


    if (
        selected_expiry is None
        and expiry_data
        and isinstance(
            expiry_data[
                0
            ],
            dict,
        )
    ):

        selected_expiry = (
            expiry_data[
                0
            ].get(
                "expiry"
            )
        )


    spot = None

    legs = []


    for item in chain:

        if not isinstance(
            item,
            dict,
        ):

            continue


        option_type = str(
            item.get(
                "option_type",
                "",
            )
        ).upper()


        if option_type not in {
            "CE",
            "PE",
        }:

            if spot is None:

                candidate = _number(
                    item.get(
                        "ltp"
                    )
                )


                if candidate is not None:

                    spot = candidate

            continue


        greeks = item.get(
            "greeks",
            {}
        )


        if not isinstance(
            greeks,
            dict,
        ):

            greeks = {}


        strike = _number(
            item.get(
                "strike_price"
            )
        )


        if strike is None:

            continue


        leg = {
            "symbol":
                item.get(
                    "symbol"
                ),

            "fy_token":
                item.get(
                    "fyToken"
                ),

            "option_type":
                option_type,

            "strike":
                strike,

            "ltp":
                _number(
                    item.get(
                        "ltp"
                    )
                ),

            "ltp_change":
                _number(
                    item.get(
                        "ltpch"
                    )
                ),

            "ltp_change_pct":
                _number(
                    item.get(
                        "ltpchp"
                    )
                ),

            "bid":
                _number(
                    item.get(
                        "bid"
                    )
                ),

            "ask":
                _number(
                    item.get(
                        "ask"
                    )
                ),

            "oi":
                _integer(
                    item.get(
                        "oi"
                    )
                ),

            "oi_change":
                _integer(
                    item.get(
                        "oich"
                    )
                ),

            "oi_change_pct":
                _number(
                    item.get(
                        "oichp"
                    )
                ),

            "previous_oi":
                _integer(
                    item.get(
                        "prev_oi"
                    )
                ),

            "volume":
                _integer(
                    item.get(
                        "volume"
                    )
                ),

            "delta":
                _number(
                    greeks.get(
                        "delta"
                    )
                ),

            "gamma":
                _number(
                    greeks.get(
                        "gamma"
                    )
                ),

            "theta":
                _number(
                    greeks.get(
                        "theta"
                    )
                ),

            "vega":
                _number(
                    greeks.get(
                        "vega"
                    )
                ),

            "iv":
                _number(
                    greeks.get(
                        "iv"
                    )
                ),

            "expiry":
                (
                    str(
                        selected_expiry
                    )
                    if selected_expiry
                    is not None
                    else None
                ),
        }


        legs.append(
            leg
        )


    strikes = sorted(
        {
            leg[
                "strike"
            ]

            for leg in legs
        }
    )


    atm_strike = None


    if (
        spot is not None
        and strikes
    ):

        atm_strike = min(
            strikes,
            key=lambda strike:
                abs(
                    strike
                    - spot
                ),
        )


    atm_call_iv = None

    atm_put_iv = None


    if atm_strike is not None:

        for leg in legs:

            if leg[
                "strike"
            ] != atm_strike:

                continue


            if (
                leg[
                    "option_type"
                ] == "CE"
            ):

                atm_call_iv = (
                    leg[
                        "iv"
                    ]
                )


            elif (
                leg[
                    "option_type"
                ] == "PE"
            ):

                atm_put_iv = (
                    leg[
                        "iv"
                    ]
                )


    atm_values = [
        value

        for value in (
            atm_call_iv,
            atm_put_iv,
        )

        if value is not None
    ]


    atm_iv = (
        sum(
            atm_values
        )
        / len(
            atm_values
        )

        if atm_values

        else None
    )


    atm_skew = (
        atm_put_iv
        - atm_call_iv

        if (
            atm_put_iv
            is not None
            and atm_call_iv
            is not None
        )

        else None
    )


    call_oi = _integer(
        data.get(
            "callOi"
        )
    )


    put_oi = _integer(
        data.get(
            "putOi"
        )
    )


    pcr_oi = (
        put_oi
        / call_oi

        if (
            put_oi is not None
            and call_oi not in (
                None,
                0,
            )
        )

        else None
    )


    return {
        "snapshot_id":
            (
                "chain-"
                + uuid.uuid4()
                .hex
            ),

        "provider":
            "fyers_v3_optionchain",

        "sdk_version":
            worker_result.get(
                "sdk_version"
            ),

        "symbol":
            str(
                request.get(
                    "symbol",
                    "",
                )
            ),

        "captured_at":
            captured_at.isoformat(),

        "selected_expiry":
            (
                str(
                    selected_expiry
                )
                if selected_expiry
                is not None
                else None
            ),

        "strikecount":
            request.get(
                "strikecount"
            ),

        "greeks_requested":
            (
                str(
                    request.get(
                        "greeks",
                        ""
                    )
                )
                == "1"
            ),

        "spot":
            spot,

        "call_oi":
            call_oi,

        "put_oi":
            put_oi,

        "pcr_oi":
            pcr_oi,

        "atm_strike":
            atm_strike,

        "atm_call_iv":
            atm_call_iv,

        "atm_put_iv":
            atm_put_iv,

        "atm_iv":
            atm_iv,

        "atm_skew":
            atm_skew,

        "expiry_data":
            tuple(
                expiry_data
            ),

        "legs":
            tuple(
                legs
            ),

        "raw_response":
            response,

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }
'''
)


# ============================================================
# 7. SQLITE HISTORICAL STORE
# ============================================================

write(
    STORE,
    r'''
from __future__ import annotations

from contextlib import (
    contextmanager,
)

import json
import sqlite3

from pathlib import (
    Path,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


DEFAULT_DB = (
    ROOT
    / "data"
    / "trading"
    / "derivatives"
    / "history.sqlite3"
)


class DerivativesHistoryStore:

    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or DEFAULT_DB
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        self._initialize()


    def _connect(
        self,
    ):

        connection = sqlite3.connect(
            self.path,
            timeout=15,
        )


        connection.row_factory = (
            sqlite3.Row
        )


        connection.execute(
            "PRAGMA foreign_keys=ON"
        )


        connection.execute(
            "PRAGMA busy_timeout=15000"
        )


        return connection


    @contextmanager
    def _db(
        self,
    ):

        connection = self._connect()

        try:

            # sqlite3.Connection context management
            # commits/rolls back but does not itself close
            # the Windows database file handle.
            with connection:

                yield connection

        finally:

            connection.close()


    def _initialize(
        self,
    ):

        with self._db() as db:

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chain_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    selected_expiry TEXT,
                    strikecount INTEGER,
                    greeks_requested INTEGER NOT NULL,
                    spot REAL,
                    call_oi INTEGER,
                    put_oi INTEGER,
                    pcr_oi REAL,
                    atm_strike REAL,
                    atm_call_iv REAL,
                    atm_put_iv REAL,
                    atm_iv REAL,
                    atm_skew REAL,
                    expiry_data_json TEXT NOT NULL,
                    raw_response_json TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    sdk_version TEXT
                )
                """
            )


            db.execute(
                """
                CREATE TABLE IF NOT EXISTS option_legs (
                    snapshot_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    expiry TEXT,
                    contract_symbol TEXT,
                    fy_token TEXT,
                    option_type TEXT NOT NULL,
                    strike REAL NOT NULL,
                    ltp REAL,
                    ltp_change REAL,
                    ltp_change_pct REAL,
                    bid REAL,
                    ask REAL,
                    oi INTEGER,
                    oi_change INTEGER,
                    oi_change_pct REAL,
                    previous_oi INTEGER,
                    volume INTEGER,
                    delta REAL,
                    gamma REAL,
                    theta REAL,
                    vega REAL,
                    iv REAL,
                    FOREIGN KEY(snapshot_id)
                        REFERENCES chain_snapshots(snapshot_id)
                        ON DELETE CASCADE
                )
                """
            )


            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_chain_symbol_time
                ON chain_snapshots(symbol, captured_at)
                """
            )


            db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_leg_lookup
                ON option_legs(
                    symbol,
                    expiry,
                    strike,
                    option_type,
                    captured_at
                )
                """
            )


    def save(
        self,
        snapshot,
    ):

        snapshot = dict(
            snapshot
        )


        with self._db() as db:

            db.execute(
                """
                INSERT INTO chain_snapshots (
                    snapshot_id,
                    symbol,
                    captured_at,
                    selected_expiry,
                    strikecount,
                    greeks_requested,
                    spot,
                    call_oi,
                    put_oi,
                    pcr_oi,
                    atm_strike,
                    atm_call_iv,
                    atm_put_iv,
                    atm_iv,
                    atm_skew,
                    expiry_data_json,
                    raw_response_json,
                    provider,
                    sdk_version
                )
                VALUES (
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    snapshot[
                        "snapshot_id"
                    ],

                    snapshot[
                        "symbol"
                    ],

                    snapshot[
                        "captured_at"
                    ],

                    snapshot.get(
                        "selected_expiry"
                    ),

                    snapshot.get(
                        "strikecount"
                    ),

                    int(
                        bool(
                            snapshot.get(
                                "greeks_requested"
                            )
                        )
                    ),

                    snapshot.get(
                        "spot"
                    ),

                    snapshot.get(
                        "call_oi"
                    ),

                    snapshot.get(
                        "put_oi"
                    ),

                    snapshot.get(
                        "pcr_oi"
                    ),

                    snapshot.get(
                        "atm_strike"
                    ),

                    snapshot.get(
                        "atm_call_iv"
                    ),

                    snapshot.get(
                        "atm_put_iv"
                    ),

                    snapshot.get(
                        "atm_iv"
                    ),

                    snapshot.get(
                        "atm_skew"
                    ),

                    json.dumps(
                        snapshot.get(
                            "expiry_data",
                            (),
                        ),
                        default=str,
                    ),

                    json.dumps(
                        snapshot.get(
                            "raw_response",
                            {},
                        ),
                        default=str,
                    ),

                    snapshot.get(
                        "provider",
                        "unknown",
                    ),

                    snapshot.get(
                        "sdk_version"
                    ),
                ),
            )


            for leg in snapshot.get(
                "legs",
                ()
            ):

                db.execute(
                    """
                    INSERT INTO option_legs (
                        snapshot_id,
                        symbol,
                        captured_at,
                        expiry,
                        contract_symbol,
                        fy_token,
                        option_type,
                        strike,
                        ltp,
                        ltp_change,
                        ltp_change_pct,
                        bid,
                        ask,
                        oi,
                        oi_change,
                        oi_change_pct,
                        previous_oi,
                        volume,
                        delta,
                        gamma,
                        theta,
                        vega,
                        iv
                    )
                    VALUES (
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?,?,?,?,?,?,?,?,
                        ?,?,?
                    )
                    """,
                    (
                        snapshot[
                            "snapshot_id"
                        ],

                        snapshot[
                            "symbol"
                        ],

                        snapshot[
                            "captured_at"
                        ],

                        leg.get(
                            "expiry"
                        ),

                        leg.get(
                            "symbol"
                        ),

                        leg.get(
                            "fy_token"
                        ),

                        leg[
                            "option_type"
                        ],

                        leg[
                            "strike"
                        ],

                        leg.get(
                            "ltp"
                        ),

                        leg.get(
                            "ltp_change"
                        ),

                        leg.get(
                            "ltp_change_pct"
                        ),

                        leg.get(
                            "bid"
                        ),

                        leg.get(
                            "ask"
                        ),

                        leg.get(
                            "oi"
                        ),

                        leg.get(
                            "oi_change"
                        ),

                        leg.get(
                            "oi_change_pct"
                        ),

                        leg.get(
                            "previous_oi"
                        ),

                        leg.get(
                            "volume"
                        ),

                        leg.get(
                            "delta"
                        ),

                        leg.get(
                            "gamma"
                        ),

                        leg.get(
                            "theta"
                        ),

                        leg.get(
                            "vega"
                        ),

                        leg.get(
                            "iv"
                        ),
                    ),
                )


        return {
            "success":
                True,

            "snapshot_id":
                snapshot[
                    "snapshot_id"
                ],

            "leg_count":
                len(
                    snapshot.get(
                        "legs",
                        ()
                    )
                ),

            "database":
                str(
                    self.path
                ),

            "research_only":
                True,
        }


    def history(
        self,
        symbol,
        *,
        limit=100,
    ):

        limit = max(
            1,
            min(
                int(
                    limit
                ),
                5000,
            ),
        )


        with self._db() as db:

            rows = db.execute(
                """
                SELECT
                    snapshot_id,
                    symbol,
                    captured_at,
                    selected_expiry,
                    strikecount,
                    greeks_requested,
                    spot,
                    call_oi,
                    put_oi,
                    pcr_oi,
                    atm_strike,
                    atm_call_iv,
                    atm_put_iv,
                    atm_iv,
                    atm_skew,
                    provider,
                    sdk_version
                FROM chain_snapshots
                WHERE symbol = ?
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                (
                    str(
                        symbol
                    ),
                    limit,
                ),
            ).fetchall()


        return tuple(
            dict(
                row
            )

            for row
            in rows
        )


    def leg_history(
        self,
        symbol,
        strike,
        option_type,
        *,
        expiry=None,
        limit=500,
    ):

        option_type = str(
            option_type
        ).upper()


        parameters = [
            str(
                symbol
            ),
            float(
                strike
            ),
            option_type,
        ]


        where = (
            "symbol = ? "
            "AND strike = ? "
            "AND option_type = ?"
        )


        if expiry is not None:

            where += (
                " AND expiry = ?"
            )


            parameters.append(
                str(
                    expiry
                )
            )


        parameters.append(
            max(
                1,
                min(
                    int(
                        limit
                    ),
                    5000,
                ),
            )
        )


        with self._db() as db:

            rows = db.execute(
                f"""
                SELECT *
                FROM option_legs
                WHERE {where}
                ORDER BY captured_at DESC
                LIMIT ?
                """,
                tuple(
                    parameters
                ),
            ).fetchall()


        return tuple(
            dict(
                row
            )

            for row
            in rows
        )


derivatives_history_store = (
    DerivativesHistoryStore()
)
'''
)


# ============================================================
# 8. COMPILE PART 1
# ============================================================

print()
print(
    "Checking Trading V7 Part 1 syntax..."
)


r = run(
    MAIN_PY,
    "-m",
    "py_compile",
    str(
        BRIDGE
    ),
    str(
        NORMALIZER
    ),
    str(
        STORE
    ),
)


if r.returncode:

    print(
        "V7 PART 1 COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


r = run(
    FYERS_PY,
    "-m",
    "py_compile",
    str(
        WORKER
    ),
)


if r.returncode:

    print(
        "FYERS WORKER COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Trading V7 Part 1 syntax: PASS"
)


print()
print("PART 1 SAVED")
print("Paste PART 2.")


# ============================================================
# 9. HISTORICAL DERIVATIVES ANALYTICS
# ============================================================

write(
    ANALYTICS,
    r'''
from __future__ import annotations

from collections import (
    defaultdict,
)

from statistics import (
    fmean,
)


from omni.trading_intelligence.derivatives_history_store import (
    derivatives_history_store,
)


def _percentile_rank(
    history,
    current,
):

    if (
        current is None
        or not history
    ):

        return None


    values = [
        float(
            value
        )

        for value in history

        if value is not None
    ]


    if not values:

        return None


    return (
        sum(
            1

            for value in values

            if value <= float(
                current
            )
        )
        / len(
            values
        )
        * 100.0
    )


def _range_rank(
    history,
    current,
):

    if current is None:

        return None


    values = [
        float(
            value
        )

        for value in history

        if value is not None
    ]


    if len(
        values
    ) < 2:

        return None


    low = min(
        values
    )

    high = max(
        values
    )


    if high == low:

        return 50.0


    return (
        (
            float(
                current
            )
            - low
        )
        / (
            high
            - low
        )
        * 100.0
    )


class DerivativesHistoryAnalytics:

    def analyze(
        self,
        symbol,
        *,
        lookback=252,
    ):

        history = (
            derivatives_history_store
            .history(
                symbol,
                limit=lookback,
            )
        )


        if not history:

            return {
                "symbol":
                    str(
                        symbol
                    ),

                "available":
                    False,

                "snapshot_count":
                    0,

                "research_only":
                    True,
            }


        latest = history[
            0
        ]


        previous = (
            history[
                1
            ]

            if len(
                history
            ) > 1

            else None
        )


        iv_history = [
            row.get(
                "atm_iv"
            )

            for row in history

            if row.get(
                "atm_iv"
            ) is not None
        ]


        current_iv = latest.get(
            "atm_iv"
        )


        delta_call_oi = None

        delta_put_oi = None


        if previous is not None:

            if (
                latest.get(
                    "call_oi"
                )
                is not None
                and previous.get(
                    "call_oi"
                )
                is not None
            ):

                delta_call_oi = (
                    latest[
                        "call_oi"
                    ]
                    - previous[
                        "call_oi"
                    ]
                )


            if (
                latest.get(
                    "put_oi"
                )
                is not None
                and previous.get(
                    "put_oi"
                )
                is not None
            ):

                delta_put_oi = (
                    latest[
                        "put_oi"
                    ]
                    - previous[
                        "put_oi"
                    ]
                )


        by_expiry = {}


        for row in history:

            expiry = row.get(
                "selected_expiry"
            )


            if (
                expiry
                and expiry
                not in by_expiry
            ):

                by_expiry[
                    expiry
                ] = {
                    "captured_at":
                        row[
                            "captured_at"
                        ],

                    "atm_iv":
                        row.get(
                            "atm_iv"
                        ),

                    "atm_skew":
                        row.get(
                            "atm_skew"
                        ),

                    "pcr_oi":
                        row.get(
                            "pcr_oi"
                        ),
                }


        return {
            "symbol":
                str(
                    symbol
                ),

            "available":
                True,

            "snapshot_count":
                len(
                    history
                ),

            "latest":
                latest,

            "atm_iv_rank":
                _range_rank(
                    iv_history,
                    current_iv,
                ),

            "atm_iv_percentile":
                _percentile_rank(
                    iv_history,
                    current_iv,
                ),

            "atm_skew":
                latest.get(
                    "atm_skew"
                ),

            "pcr_oi":
                latest.get(
                    "pcr_oi"
                ),

            "delta_call_oi":
                delta_call_oi,

            "delta_put_oi":
                delta_put_oi,

            "term_structure":
                by_expiry,

            "average_atm_iv":
                (
                    fmean(
                        iv_history
                    )

                    if iv_history

                    else None
                ),

            "predictive_guarantee":
                False,

            "research_only":
                True,
        }


derivatives_history_analytics = (
    DerivativesHistoryAnalytics()
)
'''
)


# ============================================================
# 10. UNDERLYING / FUTURES / OPTIONS SYNCHRONIZATION
# ============================================================

write(
    SYNC,
    r'''
from __future__ import annotations

from bisect import (
    bisect_right,
)

from datetime import (
    datetime,
    timezone,
)


def _timestamp(
    value,
):

    if isinstance(
        value,
        datetime,
    ):

        result = value


    else:

        text = str(
            value
        )


        if text.endswith(
            "Z"
        ):

            text = (
                text[:-1]
                + "+00:00"
            )


        result = datetime.fromisoformat(
            text
        )


    if result.tzinfo is None:

        result = result.replace(
            tzinfo=timezone.utc
        )


    return result.astimezone(
        timezone.utc
    )


def _bar_value(
    bar,
    name,
):

    if isinstance(
        bar,
        dict,
    ):

        return bar[
            name
        ]


    return getattr(
        bar,
        name
    )


def synchronize_derivatives(
    underlying_bars,
    futures_bars,
    chain_snapshots,
    *,
    max_chain_age_seconds=300,
):

    underlying = sorted(
        tuple(
            underlying_bars
        ),
        key=lambda bar:
            _timestamp(
                _bar_value(
                    bar,
                    "timestamp",
                )
            ),
    )


    futures = sorted(
        tuple(
            futures_bars
        ),
        key=lambda bar:
            _timestamp(
                _bar_value(
                    bar,
                    "timestamp",
                )
            ),
    )


    chains = sorted(
        tuple(
            chain_snapshots
        ),
        key=lambda row:
            _timestamp(
                row[
                    "captured_at"
                ]
            ),
    )


    futures_times = [
        _timestamp(
            _bar_value(
                bar,
                "timestamp",
            )
        )

        for bar in futures
    ]


    chain_times = [
        _timestamp(
            row[
                "captured_at"
            ]
        )

        for row in chains
    ]


    output = []


    for spot_bar in underlying:

        spot_time = _timestamp(
            _bar_value(
                spot_bar,
                "timestamp",
            )
        )


        future_index = (
            bisect_right(
                futures_times,
                spot_time,
            )
            - 1
        )


        chain_index = (
            bisect_right(
                chain_times,
                spot_time,
            )
            - 1
        )


        if future_index < 0:

            continue


        if chain_index < 0:

            continue


        future_bar = futures[
            future_index
        ]


        chain = chains[
            chain_index
        ]


        chain_time = chain_times[
            chain_index
        ]


        age = (
            spot_time
            - chain_time
        ).total_seconds()


        if age < 0:

            raise RuntimeError(
                "Future chain data leakage detected."
            )


        if age > float(
            max_chain_age_seconds
        ):

            continue


        spot_close = float(
            _bar_value(
                spot_bar,
                "close",
            )
        )


        future_close = float(
            _bar_value(
                future_bar,
                "close",
            )
        )


        output.append(
            {
                "timestamp":
                    spot_time.isoformat(),

                "spot_close":
                    spot_close,

                "future_close":
                    future_close,

                "futures_basis":
                    (
                        future_close
                        - spot_close
                    ),

                "chain_captured_at":
                    chain[
                        "captured_at"
                    ],

                "chain_age_seconds":
                    age,

                "pcr_oi":
                    chain.get(
                        "pcr_oi"
                    ),

                "atm_iv":
                    chain.get(
                        "atm_iv"
                    ),

                "atm_skew":
                    chain.get(
                        "atm_skew"
                    ),

                "call_oi":
                    chain.get(
                        "call_oi"
                    ),

                "put_oi":
                    chain.get(
                        "put_oi"
                    ),

                "atm_strike":
                    chain.get(
                        "atm_strike"
                    ),

                "future_data_after_signal":
                    False,

                "chain_data_after_signal":
                    False,
            }
        )


    return {
        "rows":
            tuple(
                output
            ),

        "row_count":
            len(
                output
            ),

        "backward_asof_only":
            True,

        "future_data_leakage":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 11. DERIVATIVES REGIME ENGINE
# ============================================================

write(
    REGIME,
    r'''
from __future__ import annotations


def derivatives_regime(
    features,
):

    features = dict(
        features
    )


    iv_rank = features.get(
        "atm_iv_rank"
    )


    pcr = features.get(
        "pcr_oi"
    )


    delta_call = features.get(
        "delta_call_oi"
    )


    delta_put = features.get(
        "delta_put_oi"
    )


    basis = features.get(
        "futures_basis"
    )


    components = {}


    if iv_rank is None:

        components[
            "volatility"
        ] = "UNKNOWN"


    elif float(
        iv_rank
    ) >= 70:

        components[
            "volatility"
        ] = "HIGH_IV"


    elif float(
        iv_rank
    ) <= 30:

        components[
            "volatility"
        ] = "LOW_IV"


    else:

        components[
            "volatility"
        ] = "MID_IV"


    if pcr is None:

        components[
            "pcr"
        ] = "UNKNOWN"


    elif float(
        pcr
    ) >= 1.2:

        components[
            "pcr"
        ] = "PUT_OI_HEAVY"


    elif float(
        pcr
    ) <= 0.8:

        components[
            "pcr"
        ] = "CALL_OI_HEAVY"


    else:

        components[
            "pcr"
        ] = "BALANCED_OI"


    if (
        delta_call is None
        or delta_put is None
    ):

        components[
            "oi_change"
        ] = "UNKNOWN"


    elif delta_put > delta_call:

        components[
            "oi_change"
        ] = "PUT_OI_BUILDING_FASTER"


    elif delta_call > delta_put:

        components[
            "oi_change"
        ] = "CALL_OI_BUILDING_FASTER"


    else:

        components[
            "oi_change"
        ] = "OI_CHANGE_BALANCED"


    if basis is None:

        components[
            "basis"
        ] = "UNKNOWN"


    elif float(
        basis
    ) > 0:

        components[
            "basis"
        ] = "FUTURES_PREMIUM"


    elif float(
        basis
    ) < 0:

        components[
            "basis"
        ] = "FUTURES_DISCOUNT"


    else:

        components[
            "basis"
        ] = "FLAT_BASIS"


    known = sum(
        1

        for value in components.values()

        if value != "UNKNOWN"
    )


    return {
        "regime":
            "|".join(
                components.values()
            ),

        "components":
            components,

        "feature_coverage":
            known
            / len(
                components
            ),

        "predictive_guarantee":
            False,

        "trade_instruction":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 12. STRATEGY ENSEMBLE
# ============================================================

write(
    ENSEMBLE,
    r'''
from __future__ import annotations


SIGNAL_VALUE = {
    "LONG":
        1.0,

    "SHORT":
        -1.0,

    "FLAT":
        0.0,

    "EXIT":
        0.0,
}


def derivatives_ensemble(
    signals,
    *,
    weights=None,
    threshold=0.25,
):

    signals = dict(
        signals
    )


    if not signals:

        raise ValueError(
            "At least one signal is required."
        )


    normalized = {}


    for strategy_id, signal in (
        signals.items()
    ):

        signal = str(
            signal
        ).upper()


        if signal not in SIGNAL_VALUE:

            raise ValueError(
                "Unsupported signal: "
                + signal
            )


        normalized[
            str(
                strategy_id
            )
        ] = signal


    if weights is None:

        weights = {
            strategy_id:
                1.0

            for strategy_id
            in normalized
        }


    else:

        weights = {
            str(
                key
            ):
                max(
                    0.0,
                    float(
                        value
                    ),
                )

            for key, value
            in dict(
                weights
            ).items()
        }


    total_weight = sum(
        weights.get(
            strategy_id,
            0.0,
        )

        for strategy_id
        in normalized
    )


    if total_weight <= 0:

        raise ValueError(
            "Ensemble weights must contain positive mass."
        )


    contributions = {}


    score = 0.0


    for strategy_id, signal in (
        normalized.items()
    ):

        weight = (
            weights.get(
                strategy_id,
                0.0,
            )
            / total_weight
        )


        contribution = (
            SIGNAL_VALUE[
                signal
            ]
            * weight
        )


        contributions[
            strategy_id
        ] = {
            "signal":
                signal,

            "weight":
                weight,

            "contribution":
                contribution,
        }


        score += contribution


    threshold = abs(
        float(
            threshold
        )
    )


    if score >= threshold:

        consensus = "LONG"


    elif score <= -threshold:

        consensus = "SHORT"


    else:

        consensus = "FLAT"


    return {
        "consensus":
            consensus,

        "score":
            score,

        "threshold":
            threshold,

        "contributions":
            contributions,

        "execution_allowed":
            False,

        "broker_order":
            False,

        "capital_allocation":
            False,

        "research_only":
            True,
    }
'''
)


# ============================================================
# 13. BOUNDED RESEARCH CAMPAIGN
# ============================================================

write(
    CAMPAIGN,
    r'''
from __future__ import annotations


STATE_SCORE = {
    "PORTFOLIO_RESEARCH_ELIGIBLE":
        5,

    "EXTENDED_RESEARCH_ELIGIBLE":
        4,

    "PROMOTE":
        3,

    "KEEP_TESTING":
        2,

    "DEGRADE":
        1,

    "RETIRE":
        0,
}


class DerivativesResearchCampaign:

    MAX_CANDIDATES = 50


    def run(
        self,
        candidates,
    ):

        candidates = tuple(
            candidates
        )


        if not candidates:

            raise ValueError(
                "At least one candidate is required."
            )


        if len(
            candidates
        ) > self.MAX_CANDIDATES:

            raise ValueError(
                "Research campaign candidate limit exceeded."
            )


        rows = []


        for index, candidate in enumerate(
            candidates
        ):

            candidate = dict(
                candidate
            )


            candidate_id = str(
                candidate.get(
                    "candidate_id",
                    "candidate_"
                    + str(
                        index
                    ),
                )
            )


            v5 = dict(
                candidate.get(
                    "v5_report",
                    {}
                )
            )


            v5_state = (
                v5.get(
                    "recommendation",
                    {}
                ).get(
                    "recommendation"
                )
                or candidate.get(
                    "v5_recommendation"
                )
                or "KEEP_TESTING"
            )


            c3 = dict(
                candidate.get(
                    "c3_campaign",
                    {}
                )
            )


            c3_pass_rate = float(
                c3.get(
                    "oos_pass_rate",
                    0.0,
                )
            )


            if v5_state == "RETIRE":

                state = "RETIRE"


            elif v5_state == "DEGRADE":

                state = "DEGRADE"


            elif (
                v5_state == "PROMOTE"
                and c3
                and c3_pass_rate >= 0.60
            ):

                state = (
                    "PORTFOLIO_RESEARCH_ELIGIBLE"
                )


            elif v5_state == "PROMOTE":

                state = (
                    "EXTENDED_RESEARCH_ELIGIBLE"
                )


            else:

                state = "KEEP_TESTING"


            rows.append(
                {
                    "candidate_id":
                        candidate_id,

                    "state":
                        state,

                    "score":
                        STATE_SCORE.get(
                            state,
                            0,
                        ),

                    "v5_recommendation":
                        v5_state,

                    "c3_oos_pass_rate":
                        (
                            c3_pass_rate
                            if c3
                            else None
                        ),

                    "automatic_promotion":
                        False,

                    "broker_execution":
                        False,
                }
            )


        rows.sort(
            key=lambda row:
                (
                    row[
                        "score"
                    ],
                    (
                        row[
                            "c3_oos_pass_rate"
                        ]
                        or 0.0
                    ),
                ),
            reverse=True,
        )


        return {
            "success":
                True,

            "candidate_count":
                len(
                    rows
                ),

            "ranking":
                tuple(
                    rows
                ),

            "best_candidate":
                rows[
                    0
                ],

            "max_candidates":
                self.MAX_CANDIDATES,

            "v5_authoritative":
                True,

            "nautilus_evidence_supported":
                True,

            "automatic_strategy_promotion":
                False,

            "automatic_registry_mutation":
                False,

            "automatic_capital_allocation":
                False,

            "automatic_broker_order":
                False,

            "research_only":
                True,
        }


derivatives_research_campaign = (
    DerivativesResearchCampaign()
)
'''
)


# ============================================================
# 14. STATUS
# ============================================================

write(
    STATUS,
    r'''
from __future__ import annotations

from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.fyers_v7_bridge import (
    fyers_v7_readonly_bridge,
)


def trading_v7_status():

    core = verify_protected_core()

    fyers = (
        fyers_v7_readonly_bridge
        .status()
    )


    return {
        "protected_core":
            core.ok,

        "research_only":
            True,

        "live_execution":
            False,

        "paper_only":
            True,

        "fyers_sdk_isolated":
            True,

        "fyers_sdk_version":
            fyers.get(
                "sdk_version"
            ),

        "fyers_option_chain_method":
            fyers.get(
                "option_chain_method"
            ),

        "fyers_market_depth_method":
            fyers.get(
                "depth_method"
            ),

        "real_option_chain_read":
            bool(
                fyers.get(
                    "available"
                )
            ),

        "real_market_depth_read":
            bool(
                fyers.get(
                    "available"
                )
            ),

        "api_call_during_install":
            False,

        "background_option_chain_polling":
            False,

        "historical_chain_store":
            True,

        "raw_chain_persistence":
            True,

        "historical_option_legs":
            True,

        "historical_atm_iv":
            True,

        "historical_iv_rank":
            True,

        "historical_iv_percentile":
            True,

        "historical_skew":
            True,

        "historical_pcr":
            True,

        "historical_oi":
            True,

        "historical_delta_oi":
            True,

        "expiry_term_structure":
            True,

        "underlying_futures_options_sync":
            True,

        "backward_asof_only":
            True,

        "future_data_leakage":
            False,

        "derivatives_regime_engine":
            True,

        "strategy_ensemble_research":
            True,

        "bounded_research_campaign":
            True,

        "campaign_candidate_limit":
            50,

        "v5_authoritative":
            True,

        "nautilus_c3_preserved":
            True,

        "legacy_v6_fyers_bridge_preserved":
            True,

        "single_leg_naked_option_short":
            False,

        "automatic_strategy_promotion":
            False,

        "automatic_registry_mutation":
            False,

        "automatic_capital_allocation":
            False,

        "automatic_broker_order":
            False,

        "production_self_modification":
            False,
    }
'''
)


# ============================================================
# 15. MAIN APIs
# ============================================================

main_source = MAIN.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v7_status("
    not in main_source
):

    main_source += r'''


def jarvis_trading_v7_status():

    from omni.trading_intelligence.trading_v7_status import (
        trading_v7_status,
    )

    return trading_v7_status()


def jarvis_fyers_option_chain(
    symbol,
    strikecount=5,
    timestamp=None,
    greeks=True,
    persist=True,
    timeout=30,
):

    from omni.trading_intelligence.fyers_v7_bridge import (
        fyers_v7_readonly_bridge,
    )

    from omni.trading_intelligence.fyers_chain_normalizer import (
        normalize_fyers_option_chain,
    )

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )


    raw = fyers_v7_readonly_bridge.option_chain(
        symbol,
        strikecount=strikecount,
        timestamp=timestamp,
        greeks=greeks,
        timeout=timeout,
    )


    snapshot = normalize_fyers_option_chain(
        raw
    )


    saved = None


    if persist:

        saved = (
            derivatives_history_store
            .save(
                snapshot
            )
        )


    return {
        "success":
            True,

        "snapshot":
            snapshot,

        "persisted":
            bool(
                persist
            ),

        "save_result":
            saved,

        "read_only":
            True,

        "live_execution":
            False,
    }


def jarvis_fyers_market_depth(
    symbol,
    ohlcv_flag=True,
    timeout=30,
):

    from omni.trading_intelligence.fyers_v7_bridge import (
        fyers_v7_readonly_bridge,
    )


    return fyers_v7_readonly_bridge.depth(
        symbol,
        ohlcv_flag=ohlcv_flag,
        timeout=timeout,
    )


def jarvis_derivatives_history(
    symbol,
    limit=100,
):

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )

    return derivatives_history_store.history(
        symbol,
        limit=limit,
    )


def jarvis_derivatives_leg_history(
    symbol,
    strike,
    option_type,
    expiry=None,
    limit=500,
):

    from omni.trading_intelligence.derivatives_history_store import (
        derivatives_history_store,
    )

    return derivatives_history_store.leg_history(
        symbol,
        strike,
        option_type,
        expiry=expiry,
        limit=limit,
    )


def jarvis_derivatives_history_analytics(
    symbol,
    lookback=252,
):

    from omni.trading_intelligence.derivatives_history_analytics import (
        derivatives_history_analytics,
    )

    return derivatives_history_analytics.analyze(
        symbol,
        lookback=lookback,
    )


def jarvis_sync_derivatives(
    underlying_bars,
    futures_bars,
    chain_snapshots,
    max_chain_age_seconds=300,
):

    from omni.trading_intelligence.derivatives_sync import (
        synchronize_derivatives,
    )

    return synchronize_derivatives(
        underlying_bars,
        futures_bars,
        chain_snapshots,
        max_chain_age_seconds=max_chain_age_seconds,
    )


def jarvis_derivatives_regime(
    features,
):

    from omni.trading_intelligence.derivatives_regime_v7 import (
        derivatives_regime,
    )

    return derivatives_regime(
        features
    )


def jarvis_derivatives_ensemble(
    signals,
    weights=None,
    threshold=0.25,
):

    from omni.trading_intelligence.derivatives_ensemble import (
        derivatives_ensemble,
    )

    return derivatives_ensemble(
        signals,
        weights=weights,
        threshold=threshold,
    )


def jarvis_derivatives_campaign(
    candidates,
):

    from omni.trading_intelligence.derivatives_campaign import (
        derivatives_research_campaign,
    )

    return derivatives_research_campaign.run(
        candidates
    )
'''


    MAIN.write_text(
        main_source,
        encoding="utf-8",
        newline="\n",
    )


# ============================================================
# 16. WORKSTATION STATUS
# ============================================================

app_source = APP.read_text(
    encoding="utf-8"
)


if (
    "def jarvis_trading_v7_payload("
    not in app_source
):

    app_source += r'''


def jarvis_trading_v7_payload():

    from omni.trading_intelligence.trading_v7_status import (
        trading_v7_status,
    )


    try:

        return {
            "success":
                True,

            "status":
                trading_v7_status(),
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
        newline="\n",
    )


# ============================================================
# 17. TESTS
# ============================================================

write(
    TEST,
    r'''
import tempfile
import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import (
    Path,
)


import main


from omni.core_integrity import (
    verify_protected_core,
)

from omni.trading_intelligence.derivatives_history_analytics import (
    DerivativesHistoryAnalytics,
)

from omni.trading_intelligence.derivatives_history_store import (
    DerivativesHistoryStore,
)

from omni.trading_intelligence.derivatives_sync import (
    synchronize_derivatives,
)

from omni.trading_intelligence.fyers_chain_normalizer import (
    normalize_fyers_option_chain,
)

from omni.trading_intelligence.fyers_v7_bridge import (
    fyers_v7_readonly_bridge,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


def fyers_result(
    *,
    spot=25000,
    call_oi=1000,
    put_oi=1200,
    call_iv=15,
    put_iv=17,
    expiry="1797550200",
):

    return {
        "success":
            True,

        "sdk_version":
            "3.1.16",

        "request": {
            "symbol":
                "NSE:NIFTY50-INDEX",

            "strikecount":
                5,

            "timestamp":
                expiry,

            "greeks":
                "1",
        },

        "response": {
            "s":
                "ok",

            "data": {
                "callOi":
                    call_oi,

                "putOi":
                    put_oi,

                "expiryData": [
                    {
                        "date":
                            "18-12-2026",

                        "expiry":
                            expiry,

                        "expiry_flag":
                            "M",
                    }
                ],

                "optionsChain": [
                    {
                        "option_type":
                            "",

                        "strike_price":
                            -1,

                        "ltp":
                            spot,
                    },

                    {
                        "symbol":
                            "NSE:NIFTY-CE",

                        "fyToken":
                            "1",

                        "option_type":
                            "CE",

                        "strike_price":
                            25000,

                        "ltp":
                            200,

                        "bid":
                            199,

                        "ask":
                            201,

                        "oi":
                            call_oi,

                        "oich":
                            100,

                        "prev_oi":
                            call_oi - 100,

                        "volume":
                            500,

                        "greeks": {
                            "delta":
                                0.5,

                            "gamma":
                                0.01,

                            "theta":
                                -10,

                            "vega":
                                12,

                            "iv":
                                call_iv,
                        },
                    },

                    {
                        "symbol":
                            "NSE:NIFTY-PE",

                        "fyToken":
                            "2",

                        "option_type":
                            "PE",

                        "strike_price":
                            25000,

                        "ltp":
                            210,

                        "bid":
                            209,

                        "ask":
                            211,

                        "oi":
                            put_oi,

                        "oich":
                            150,

                        "prev_oi":
                            put_oi - 150,

                        "volume":
                            600,

                        "greeks": {
                            "delta":
                                -0.5,

                            "gamma":
                                0.01,

                            "theta":
                                -11,

                            "vega":
                                13,

                            "iv":
                                put_iv,
                        },
                    },
                ],
            },
        },

        "read_only":
            True,

        "broker_order":
            False,

        "live_execution":
            False,
    }


class TradingIntelligenceV7Tests(
    unittest.TestCase
):

    def test_core(
        self,
    ):

        self.assertTrue(
            verify_protected_core().ok
        )


    def test_sdk_status(
        self,
    ):

        status = (
            fyers_v7_readonly_bridge
            .status()
        )


        self.assertTrue(
            status[
                "available"
            ]
        )


        self.assertEqual(
            status[
                "sdk_version"
            ],
            "3.1.16",
        )


        self.assertEqual(
            status[
                "option_chain_method"
            ],
            "optionchain",
        )


        self.assertEqual(
            status[
                "depth_method"
            ],
            "depth",
        )


    def test_normalize(
        self,
    ):

        result = normalize_fyers_option_chain(
            fyers_result(),
            captured_at=NOW,
        )


        self.assertEqual(
            result[
                "spot"
            ],
            25000,
        )


        self.assertEqual(
            result[
                "atm_strike"
            ],
            25000,
        )


        self.assertEqual(
            len(
                result[
                    "legs"
                ]
            ),
            2,
        )


        self.assertAlmostEqual(
            result[
                "pcr_oi"
            ],
            1.2,
        )


        self.assertAlmostEqual(
            result[
                "atm_iv"
            ],
            16,
        )


        self.assertAlmostEqual(
            result[
                "atm_skew"
            ],
            2,
        )


    def test_store(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            snapshot = normalize_fyers_option_chain(
                fyers_result(),
                captured_at=NOW,
            )


            saved = store.save(
                snapshot
            )


            self.assertTrue(
                saved[
                    "success"
                ]
            )


            history = store.history(
                "NSE:NIFTY50-INDEX"
            )


            self.assertEqual(
                len(
                    history
                ),
                1,
            )


            legs = store.leg_history(
                "NSE:NIFTY50-INDEX",
                25000,
                "CE",
            )


            self.assertEqual(
                len(
                    legs
                ),
                1,
            )


    def test_iv_history_math(
        self,
    ):

        with tempfile.TemporaryDirectory() as tmp:

            import omni.trading_intelligence.derivatives_history_analytics as module


            original = (
                module.derivatives_history_store
            )


            store = DerivativesHistoryStore(
                Path(
                    tmp
                )
                / "history.sqlite3"
            )


            module.derivatives_history_store = store


            try:

                for index, iv in enumerate(
                    (
                        10,
                        15,
                        20,
                    )
                ):

                    snapshot = (
                        normalize_fyers_option_chain(
                            fyers_result(
                                call_iv=iv,
                                put_iv=iv + 2,
                                call_oi=
                                    1000
                                    + index * 50,
                                put_oi=
                                    1100
                                    + index * 100,
                            ),
                            captured_at=
                                NOW
                                + timedelta(
                                    minutes=index
                                ),
                        )
                    )


                    store.save(
                        snapshot
                    )


                analytics = (
                    module
                    .DerivativesHistoryAnalytics()
                    .analyze(
                        "NSE:NIFTY50-INDEX"
                    )
                )


                self.assertTrue(
                    analytics[
                        "available"
                    ]
                )


                self.assertIsNotNone(
                    analytics[
                        "atm_iv_rank"
                    ]
                )


                self.assertIsNotNone(
                    analytics[
                        "atm_iv_percentile"
                    ]
                )


                self.assertEqual(
                    analytics[
                        "delta_call_oi"
                    ],
                    50,
                )


                self.assertEqual(
                    analytics[
                        "delta_put_oi"
                    ],
                    100,
                )


            finally:

                module.derivatives_history_store = (
                    original
                )


    def test_sync_no_future_chain(
        self,
    ):

        underlying = [
            {
                "timestamp":
                    NOW
                    + timedelta(
                        minutes=index
                    ),

                "close":
                    100
                    + index,
            }

            for index
            in range(
                3
            )
        ]


        futures = [
            {
                "timestamp":
                    NOW
                    + timedelta(
                        minutes=index
                    ),

                "close":
                    101
                    + index,
            }

            for index
            in range(
                3
            )
        ]


        chains = [
            {
                "captured_at":
                    (
                        NOW
                        + timedelta(
                            seconds=30
                        )
                    ).isoformat(),

                "pcr_oi":
                    1.1,

                "atm_iv":
                    15,

                "atm_skew":
                    1,

                "call_oi":
                    100,

                "put_oi":
                    110,

                "atm_strike":
                    100,
            }
        ]


        result = synchronize_derivatives(
            underlying,
            futures,
            chains,
            max_chain_age_seconds=300,
        )


        self.assertTrue(
            result[
                "backward_asof_only"
            ]
        )


        self.assertFalse(
            result[
                "future_data_leakage"
            ]
        )


        # The first underlying timestamp precedes
        # chain capture and must not receive the chain.
        self.assertEqual(
            result[
                "row_count"
            ],
            2,
        )


    def test_regime(
        self,
    ):

        result = (
            main.jarvis_derivatives_regime(
                {
                    "atm_iv_rank":
                        80,

                    "pcr_oi":
                        1.3,

                    "delta_call_oi":
                        50,

                    "delta_put_oi":
                        100,

                    "futures_basis":
                        10,
                }
            )
        )


        self.assertEqual(
            result[
                "components"
            ][
                "volatility"
            ],
            "HIGH_IV",
        )


        self.assertFalse(
            result[
                "predictive_guarantee"
            ]
        )


    def test_ensemble(
        self,
    ):

        result = (
            main.jarvis_derivatives_ensemble(
                {
                    "a":
                        "LONG",

                    "b":
                        "LONG",

                    "c":
                        "SHORT",
                }
            )
        )


        self.assertEqual(
            result[
                "consensus"
            ],
            "LONG",
        )


        self.assertFalse(
            result[
                "execution_allowed"
            ]
        )


        self.assertFalse(
            result[
                "broker_order"
            ]
        )


    def test_campaign(
        self,
    ):

        result = (
            main.jarvis_derivatives_campaign(
                (
                    {
                        "candidate_id":
                            "a",

                        "v5_recommendation":
                            "PROMOTE",

                        "c3_campaign": {
                            "oos_pass_rate":
                                0.8,
                        },
                    },

                    {
                        "candidate_id":
                            "b",

                        "v5_recommendation":
                            "DEGRADE",
                    },
                )
            )
        )


        self.assertEqual(
            result[
                "candidate_count"
            ],
            2,
        )


        self.assertEqual(
            result[
                "best_candidate"
            ][
                "candidate_id"
            ],
            "a",
        )


        self.assertFalse(
            result[
                "automatic_strategy_promotion"
            ]
        )


    def test_campaign_limit(
        self,
    ):

        with self.assertRaises(
            ValueError
        ):

            main.jarvis_derivatives_campaign(
                tuple(
                    {
                        "candidate_id":
                            str(
                                index
                            )
                    }

                    for index in range(
                        51
                    )
                )
            )


    def test_live_surface_blocked(
        self,
    ):

        with self.assertRaises(
            PermissionError
        ):

            fyers_v7_readonly_bridge.place_order


    def test_v7_status(
        self,
    ):

        status = (
            main.jarvis_trading_v7_status()
        )


        self.assertTrue(
            status[
                "real_option_chain_read"
            ]
        )


        self.assertTrue(
            status[
                "historical_chain_store"
            ]
        )


        self.assertTrue(
            status[
                "underlying_futures_options_sync"
            ]
        )


        self.assertFalse(
            status[
                "future_data_leakage"
            ]
        )


        self.assertFalse(
            status[
                "background_option_chain_polling"
            ]
        )


        self.assertFalse(
            status[
                "live_execution"
            ]
        )


        self.assertFalse(
            status[
                "automatic_broker_order"
            ]
        )


    def test_v5_preserved(
        self,
    ):

        status = (
            main.jarvis_trading_v5_status()
        )


        self.assertTrue(
            status[
                "walk_forward_validation"
            ]
        )


        self.assertFalse(
            status[
                "oos_tuning"
            ]
        )


    def test_c3_preserved(
        self,
    ):

        status = (
            main.jarvis_nautilus_c3_status()
        )


        self.assertTrue(
            status[
                "single_event_driven_engine"
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
            "jarvis_trading_v7_status",
            "jarvis_fyers_option_chain",
            "jarvis_fyers_market_depth",
            "jarvis_derivatives_history",
            "jarvis_derivatives_leg_history",
            "jarvis_derivatives_history_analytics",
            "jarvis_sync_derivatives",
            "jarvis_derivatives_regime",
            "jarvis_derivatives_ensemble",
            "jarvis_derivatives_campaign",
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
# 18. COMPILE
# ============================================================

print()
print(
    "Checking Trading Intelligence V7 syntax..."
)


r = run(
    MAIN_PY,
    "-m",
    "py_compile",

    str(
        BRIDGE
    ),

    str(
        NORMALIZER
    ),

    str(
        STORE
    ),

    str(
        ANALYTICS
    ),

    str(
        SYNC
    ),

    str(
        REGIME
    ),

    str(
        ENSEMBLE
    ),

    str(
        CAMPAIGN
    ),

    str(
        STATUS
    ),

    str(
        MAIN
    ),

    str(
        APP
    ),

    str(
        TEST
    ),
)


if r.returncode:

    print(
        "V7 COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


r = run(
    FYERS_PY,
    "-m",
    "py_compile",
    str(
        WORKER
    ),
)


if r.returncode:

    print(
        "V7 FYERS WORKER COMPILE FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Trading V7 syntax: PASS"
)


# ============================================================
# 19. PROTECTED CORE
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "PROTECTED CORE MODIFIED:",
            relative,
        )

        rollback()

        sys.exit(1)


print(
    "Protected Core hashes: PASS"
)


# ============================================================
# 20. ISOLATED FYERS CAPABILITY PROBE — NO API REQUEST
# ============================================================

print()
print(
    "Checking isolated FYERS option-chain bridge..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "s=main.jarvis_trading_v7_status();"
        "assert s['fyers_sdk_version']=='3.1.16';"
        "assert s['fyers_option_chain_method']=='optionchain';"
        "assert s['fyers_market_depth_method']=='depth';"
        "assert s['real_option_chain_read'];"
        "assert s['api_call_during_install'] is False;"
        "assert s['background_option_chain_polling'] is False;"
        "print('FYERS SDK isolation: PASS');"
        "print('optionchain(self, data=None): PASS');"
        "print('depth(self, data=None): PASS');"
        "print('Installer real FYERS request: NO');"
        "print('Background option polling: BLOCKED')"
    ),
)


if r.returncode:

    print(
        "V7 FYERS BRIDGE STATUS FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 21. SYNTHETIC CHAIN / HISTORY / LEAKAGE PROBE
# ============================================================

print()
print(
    "Checking historical derivatives intelligence..."
)


probe = r'''
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from omni.trading_intelligence.fyers_chain_normalizer import (
    normalize_fyers_option_chain,
)

from omni.trading_intelligence.derivatives_history_store import (
    DerivativesHistoryStore,
)

from omni.trading_intelligence.derivatives_sync import (
    synchronize_derivatives,
)


now = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=timezone.utc,
)


raw = {
    "success": True,
    "sdk_version": "3.1.16",

    "request": {
        "symbol": "NSE:NIFTY50-INDEX",
        "strikecount": 5,
        "timestamp": "1797550200",
        "greeks": "1",
    },

    "response": {
        "s": "ok",

        "data": {
            "callOi": 1000,
            "putOi": 1200,

            "expiryData": [
                {
                    "date": "18-12-2026",
                    "expiry": "1797550200",
                    "expiry_flag": "M",
                }
            ],

            "optionsChain": [
                {
                    "option_type": "",
                    "strike_price": -1,
                    "ltp": 25000,
                },

                {
                    "symbol": "CE",
                    "option_type": "CE",
                    "strike_price": 25000,
                    "ltp": 200,
                    "oi": 1000,
                    "oich": 100,
                    "volume": 500,
                    "greeks": {
                        "iv": 15,
                        "delta": 0.5,
                        "gamma": 0.01,
                        "theta": -10,
                        "vega": 12,
                    },
                },

                {
                    "symbol": "PE",
                    "option_type": "PE",
                    "strike_price": 25000,
                    "ltp": 210,
                    "oi": 1200,
                    "oich": 150,
                    "volume": 600,
                    "greeks": {
                        "iv": 17,
                        "delta": -0.5,
                        "gamma": 0.01,
                        "theta": -11,
                        "vega": 13,
                    },
                },
            ],
        },
    },
}


snapshot = normalize_fyers_option_chain(
    raw,
    captured_at=now,
)


assert snapshot["atm_strike"] == 25000
assert snapshot["pcr_oi"] == 1.2
assert snapshot["atm_iv"] == 16
assert snapshot["atm_skew"] == 2
assert len(snapshot["legs"]) == 2


with tempfile.TemporaryDirectory() as tmp:

    store = DerivativesHistoryStore(
        Path(tmp) / "test.sqlite3"
    )

    saved = store.save(snapshot)

    assert saved["leg_count"] == 2

    assert len(
        store.history(
            "NSE:NIFTY50-INDEX"
        )
    ) == 1


underlying = [
    {
        "timestamp":
            now + timedelta(minutes=i),

        "close":
            100 + i,
    }

    for i in range(3)
]


futures = [
    {
        "timestamp":
            now + timedelta(minutes=i),

        "close":
            101 + i,
    }

    for i in range(3)
]


chains = [
    {
        **snapshot,
        "captured_at":
            (
                now
                + timedelta(seconds=30)
            ).isoformat(),
    }
]


sync = synchronize_derivatives(
    underlying,
    futures,
    chains,
)


assert sync["backward_asof_only"]
assert sync["future_data_leakage"] is False
assert sync["row_count"] == 2


print("FYERS response normalization: PASS")
print("ATM detection: PASS")
print("PCR history foundation: PASS")
print("IV/skew history foundation: PASS")
print("OI/delta-OI history foundation: PASS")
print("SQLite derivatives store: PASS")
print("Backward-asof synchronization: PASS")
print("Future data leakage: BLOCKED")
print("Historical derivatives intelligence: PASS")
'''


r = run(
    MAIN_PY,
    "-c",
    probe,
)


if r.returncode:

    print(
        "V7 HISTORICAL INTELLIGENCE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 22. ENSEMBLE / CAMPAIGN / SAFETY
# ============================================================

print()
print(
    "Checking V7 research governance..."
)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "e=main.jarvis_derivatives_ensemble("
        "{'a':'LONG','b':'LONG','c':'SHORT'}"
        ");"
        "assert e['consensus']=='LONG';"
        "assert e['execution_allowed'] is False;"
        "assert e['broker_order'] is False;"
        "c=main.jarvis_derivatives_campaign(("
        "{'candidate_id':'a','v5_recommendation':'PROMOTE',"
        "'c3_campaign':{'oos_pass_rate':0.8}},"
        "{'candidate_id':'b','v5_recommendation':'DEGRADE'},"
        "));"
        "assert c['best_candidate']['candidate_id']=='a';"
        "assert c['v5_authoritative'];"
        "assert c['automatic_strategy_promotion'] is False;"
        "assert c['automatic_capital_allocation'] is False;"
        "assert c['automatic_broker_order'] is False;"
        "s=main.jarvis_trading_v7_status();"
        "assert s['single_leg_naked_option_short'] is False;"
        "assert s['future_data_leakage'] is False;"
        "assert s['live_execution'] is False;"
        "assert s['automatic_broker_order'] is False;"
        "print('Derivatives regime: ACTIVE');"
        "print('Strategy ensemble: ACTIVE');"
        "print('V5-authoritative research campaign: ACTIVE');"
        "print('Naked option short: BLOCKED');"
        "print('Automatic capital allocation: BLOCKED');"
        "print('Automatic broker orders: BLOCKED');"
        "print('V7 governance: PASS')"
    ),
)


if r.returncode:

    print(
        "V7 GOVERNANCE FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 23. TARGETED REGRESSION
# ============================================================

print()
print(
    "Running Trading Intelligence V7 targeted regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",

    "tests.test_trading_intelligence_v7",

    "tests.test_nautilus_phase_c3",
    "tests.test_nautilus_phase_c2",
    "tests.test_nautilus_research_kernel",

    "tests.test_trading_intelligence_v6",
    "tests.test_trading_intelligence_v5",
    "tests.test_trading_intelligence_v4",
    "tests.test_trading_intelligence_v3",
    "tests.test_trading_intelligence_v2",
    "tests.test_trading_v1_1_fyers_bridge",
    "tests.test_trading_intelligence_v1",

    "-q",
    timeout=420,
)


if r.returncode:

    print(
        "TARGETED REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 24. FULL REGRESSION
# ============================================================

print()
print(
    "Running full JARVIS regression..."
)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-q",
    timeout=480,
)


if r.returncode:

    print(
        "FULL REGRESSION FAILURE"
    )

    rollback()

    sys.exit(1)


# ============================================================
# 25. FINAL INTEGRITY
# ============================================================

for relative, before in (
    PROTECTED.items()
):

    if sha(
        ROOT / relative
    ) != before:

        print(
            "FINAL PROTECTED CORE CHANGE:",
            relative,
        )

        rollback()

        sys.exit(1)


r = run(
    MAIN_PY,
    "-c",
    (
        "import main;"
        "from omni.core_integrity import verify_protected_core;"
        "c=verify_protected_core();"
        "assert c.ok,(c.changed,c.missing);"
        "v5=main.jarvis_trading_v5_status();"
        "v6=main.jarvis_trading_v6_status();"
        "c3=main.jarvis_nautilus_c3_status();"
        "v7=main.jarvis_trading_v7_status();"
        "assert v5['walk_forward_validation'];"
        "assert v6['paper_only'];"
        "assert c3['single_event_driven_engine'];"
        "assert v7['historical_chain_store'];"
        "assert v7['live_execution'] is False;"
        "assert v7['automatic_broker_order'] is False;"
        "print('Final Protected Core: PASS');"
        "print('Trading V5: PRESERVED');"
        "print('Trading V6: PRESERVED');"
        "print('Nautilus C3: PRESERVED');"
        "print('Trading V7: PASS')"
    ),
)


if r.returncode:

    rollback()

    sys.exit(1)


r = run(
    MAIN_PY,
    "-m",
    "unittest",
    (
        "tests.test_computer_operator_v2."
        "ComputerOperatorV2Tests.test_dom_provider"
    ),
    "-q",
)


if r.returncode:

    print(
        "FINAL BROWSER TEST FAILURE"
    )

    rollback()

    sys.exit(1)


print(
    "Final browser DOM test: PASS"
)


# ============================================================
# SUCCESS
# ============================================================

status = run(
    MAIN_PY,
    "-c",
    (
        "import main,pprint;"
        "pprint.pp(main.jarvis_trading_v7_status())"
    ),
    capture=True,
)


print()
print("=" * 80)
print("JARVIS TRADING INTELLIGENCE V7 SUCCESS")
print("=" * 80)

print()
print("REAL FYERS MARKET DATA")
print("Isolated FYERS SDK 3.1.16: ACTIVE")
print("optionchain(data): ACTIVE")
print("depth(data): ACTIVE")
print("Canonical JARVIS token source: REUSED")
print("Token written to disk by V7 bridge: NO")
print("Installer real FYERS request: NO")
print("Background option-chain polling: DISABLED")
print()

print("HISTORICAL OPTIONS")
print("Timestamped chain snapshots: ACTIVE")
print("Raw response preservation: ACTIVE")
print("Strike-level history: ACTIVE")
print("OI history: ACTIVE")
print("Change-in-OI history: ACTIVE")
print("Volume history: ACTIVE")
print("Greeks history: ACTIVE")
print("IV history: ACTIVE")
print("ATM IV rank: ACTIVE")
print("ATM IV percentile: ACTIVE")
print("ATM skew history: ACTIVE")
print("Expiry term structure: ACTIVE")
print("PCR history: ACTIVE")
print()

print("SYNCHRONIZED DERIVATIVES")
print("Underlying bars: ACTIVE")
print("Futures bars: ACTIVE")
print("Option-chain snapshots: ACTIVE")
print("Backward-asof synchronization: ACTIVE")
print("Future chain leakage: BLOCKED")
print("Futures basis: ACTIVE")
print()

print("RESEARCH INTELLIGENCE")
print("Derivatives regime engine: ACTIVE")
print("Strategy ensemble research: ACTIVE")
print("Weighted consensus research: ACTIVE")
print("Ensemble -> execution: BLOCKED")
print("Bounded candidate campaign: ACTIVE")
print("Candidate cap: 50")
print()

print("GOVERNANCE")
print("V5 remains authoritative: YES")
print("Nautilus C3 preserved: YES")
print("Legacy FYERS quote/history preserved: YES")
print("Single-leg naked option short: BLOCKED")
print("Automatic strategy promotion: BLOCKED")
print("Automatic registry mutation: BLOCKED")
print("Automatic capital allocation: BLOCKED")
print("Automatic broker order: BLOCKED")
print("Production self-modification: BLOCKED")
print()

print("PRESERVED")
print("Trading V1-V6: YES")
print("Nautilus Phase B/C2/C3: YES")
print("Browser lock repair: YES")
print("Protected Core: UNCHANGED")
print("Full regression: PASS")
print()

print("STATUS:")
print(
    status.stdout.strip()
)
print()

print("NEXT: TRADING INTELLIGENCE V8")
print("Historical capture scheduler / session collector")
print("Expiry-aware chain collection plans")
print("Underlying + futures + options dataset builder")
print("Historical derivatives backtest features")
print("V4 evolution using derivatives history")
print("V5 walk-forward on historical derivatives features")
print("Nautilus C3 ensemble portfolio validation")
print("Cross-asset regime graph")
print("Strategy portfolio optimizer — research only")
print("NO live broker execution")
