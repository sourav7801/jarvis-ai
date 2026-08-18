from __future__ import annotations

from datetime import (
    datetime,
)

from pathlib import (
    Path,
)

import json
import subprocess
import tempfile


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


NAUTILUS_PY = (
    ROOT
    / ".venv-nautilus"
    / "Scripts"
    / "python.exe"
)


WORKER = (
    ROOT
    / "research"
    / "nautilus_kernel"
    / "worker_c2.py"
)


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


class NautilusC2Bridge:

    MAX_BARS = 200000


    def available(
        self,
    ):

        return (
            NAUTILUS_PY.exists()
            and WORKER.exists()
        )


    def capabilities(
        self,
    ):

        if not self.available():

            return {
                "available":
                    False,

                "paper_only":
                    True,

                "live_execution":
                    False,

                "broker_adapter":
                    False,
            }


        result = subprocess.run(
            [
                str(
                    NAUTILUS_PY
                ),

                str(
                    WORKER
                ),

                "--capabilities-json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )


        if result.returncode:

            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or "Nautilus C2 capability probe failed."
            )


        return json.loads(
            result.stdout.strip()
            .splitlines()[
                -1
            ]
        )


    @staticmethod
    def _bar(
        bar,
    ):

        if isinstance(
            bar,
            dict,
        ):

            getter = bar.get


        else:

            getter = lambda name: getattr(
                bar,
                name
            )


        timestamp = getter(
            "timestamp"
        )


        if isinstance(
            timestamp,
            datetime,
        ):

            timestamp = (
                timestamp.isoformat()
            )


        return {
            "timestamp":
                str(
                    timestamp
                ),

            "open":
                float(
                    getter(
                        "open"
                    )
                ),

            "high":
                float(
                    getter(
                        "high"
                    )
                ),

            "low":
                float(
                    getter(
                        "low"
                    )
                ),

            "close":
                float(
                    getter(
                        "close"
                    )
                ),
        }


    def backtest(
        self,
        bars,
        signals,
        *,
        instrument,
        execution=None,
        initial_capital=100000.0,
        quantity=1,
        leverage=1,
        timeout=120,
    ):

        if not self.available():

            raise RuntimeError(
                "Nautilus C2 kernel unavailable."
            )


        bars = tuple(
            bars
        )


        signals = tuple(
            str(
                signal
            ).strip().upper()

            for signal
            in signals
        )


        if not bars:

            raise ValueError(
                "bars cannot be empty."
            )


        if len(
            bars
        ) > self.MAX_BARS:

            raise ValueError(
                "Nautilus job exceeds maximum bar count."
            )


        if len(
            bars
        ) != len(
            signals
        ):

            raise ValueError(
                "bars/signals length mismatch."
            )


        invalid = {
            signal

            for signal in signals

            if signal
            not in ALLOWED_SIGNALS
        }


        if invalid:

            raise ValueError(
                "Unsupported signals: "
                + repr(
                    sorted(
                        invalid
                    )
                )
            )


        instrument = dict(
            instrument
        )


        kind = str(
            instrument.get(
                "kind",
                ""
            )
        ).strip().lower()


        if (
            kind == "option"
            and "SHORT" in signals
        ):

            raise PermissionError(
                "Single-leg option short simulation is blocked."
            )


        payload = {
            "bars":
                [
                    self._bar(
                        bar
                    )

                    for bar
                    in bars
                ],

            "signals":
                list(
                    signals
                ),

            "instrument":
                instrument,

            "execution":
                dict(
                    execution
                    or {
                        "name":
                            "ideal"
                    }
                ),

            "initial_capital":
                float(
                    initial_capital
                ),

            "quantity":
                float(
                    quantity
                ),

            "leverage":
                float(
                    leverage
                ),

            "research_only":
                True,

            "live_execution":
                False,

            "broker_adapter":
                False,
        }


        with tempfile.TemporaryDirectory(
            prefix=
                "jarvis_nautilus_c2_"
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
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )


            result = subprocess.run(
                [
                    str(
                        NAUTILUS_PY
                    ),

                    str(
                        WORKER
                    ),

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
                capture_output=True,
                text=True,
                timeout=float(
                    timeout
                ),
            )


            if result.returncode:

                raise RuntimeError(
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "Nautilus C2 worker failed."
                )


            if not output_path.exists():

                raise RuntimeError(
                    "Nautilus worker returned no output."
                )


            output = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                )
            )


        if not output.get(
            "success"
        ):

            raise RuntimeError(
                "Nautilus C2 result unsuccessful."
            )


        if (
            output.get(
                "live_execution"
            )
            is not False
        ):

            raise RuntimeError(
                "Live-execution invariant failed."
            )


        if (
            output.get(
                "broker_adapter"
            )
            is not False
        ):

            raise RuntimeError(
                "Broker-adapter invariant failed."
            )


        return output


    def __getattr__(
        self,
        name,
    ):

        lower = str(
            name
        ).lower()


        forbidden = (
            "live",
            "broker",
            "place_order",
            "modify_order",
            "cancel_order",
            "execution_client",
            "trading_node",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "Nautilus C2 bridge is research-only."
            )


        raise AttributeError(
            name
        )


nautilus_c2_bridge = (
    NautilusC2Bridge()
)
