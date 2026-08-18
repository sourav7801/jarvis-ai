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
