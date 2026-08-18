from __future__ import annotations

from datetime import (
    datetime,
)

from pathlib import (
    Path,
)

import importlib.util
import json
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]

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
    / "worker.py"
)


ALLOWED_SIGNALS = {
    "LONG",
    "SHORT",
    "EXIT",
    "FLAT",
}


class NautilusResearchBridge:

    MAX_BARS = 200000


    def available(
        self,
    ):

        return (
            NAUTILUS_PY.exists()
            and WORKER.exists()
        )


    def status(
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

                "--version-json",
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

                "paper_only":
                    True,

                "live_execution":
                    False,

                "broker_adapter":
                    False,
            }


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

            source = bar

            getter = source.get


        else:

            getter = lambda key: getattr(
                bar,
                key
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
        initial_capital=100000.0,
        quantity=1000,
        timeout=120,
    ):

        if not self.available():

            raise RuntimeError(
                "Nautilus research kernel unavailable."
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
                "bars and signals must have equal length."
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

            "initial_capital":
                float(
                    initial_capital
                ),

            "quantity":
                float(
                    quantity
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
                "jarvis_nautilus_"
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
                    "Nautilus worker failed: "
                    + (
                        result.stderr.strip()
                        or result.stdout.strip()
                    )
                )


            if not output_path.exists():

                raise RuntimeError(
                    "Nautilus worker produced no output."
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
                "Nautilus backtest unsuccessful."
            )


        if (
            output.get(
                "live_execution"
            )
            is not False
        ):

            raise RuntimeError(
                "Nautilus safety invariant failed."
            )


        if (
            output.get(
                "broker_adapter"
            )
            is not False
        ):

            raise RuntimeError(
                "Unexpected broker adapter surface."
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
            "trading_node",
            "execution_client",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "Nautilus bridge is research/backtest only."
            )


        raise AttributeError(
            name
        )


nautilus_research_bridge = (
    NautilusResearchBridge()
)
