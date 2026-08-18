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
