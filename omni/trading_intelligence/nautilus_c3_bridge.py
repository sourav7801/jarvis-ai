from __future__ import annotations

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
    / "worker_c3.py"
)


class NautilusC3PortfolioBridge:

    MAX_STRATEGIES = 20

    MAX_TOTAL_BARS = 500000


    def available(
        self,
    ):

        return (
            NAUTILUS_PY.exists()
            and WORKER.exists()
        )


    def _validate(
        self,
        portfolio,
    ):

        portfolio = dict(
            portfolio
        )


        strategies = list(
            portfolio.get(
                "strategies",
                (),
            )
        )


        if not strategies:

            raise ValueError(
                "Portfolio strategies cannot be empty."
            )


        if len(
            strategies
        ) > self.MAX_STRATEGIES:

            raise ValueError(
                "Portfolio strategy limit exceeded."
            )


        total_bars = 0


        for slot in strategies:

            bars = tuple(
                slot.get(
                    "bars",
                    (),
                )
            )


            signals = tuple(
                slot.get(
                    "signals",
                    (),
                )
            )


            if len(
                bars
            ) != len(
                signals
            ):

                raise ValueError(
                    "Each slot requires matching bars/signals."
                )


            total_bars += len(
                bars
            )


            kind = str(
                slot.get(
                    "instrument",
                    {}
                ).get(
                    "kind",
                    "",
                )
            ).lower()


            if (
                kind == "option"
                and any(
                    str(
                        signal
                    ).upper()
                    == "SHORT"

                    for signal
                    in signals
                )
            ):

                raise PermissionError(
                    "Single-leg option short is blocked."
                )


        if total_bars > self.MAX_TOTAL_BARS:

            raise ValueError(
                "Portfolio bar limit exceeded."
            )


        return portfolio


    def run(
        self,
        portfolio,
        *,
        timeout=180,
    ):

        if not self.available():

            raise RuntimeError(
                "Nautilus C3 portfolio kernel unavailable."
            )


        payload = self._validate(
            portfolio
        )


        with tempfile.TemporaryDirectory(
            prefix=
                "jarvis_nautilus_c3_"
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
                    or "Nautilus C3 worker failed."
                )


            if not output_path.exists():

                raise RuntimeError(
                    "C3 worker produced no output."
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
                "C3 portfolio run failed."
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


    def stress_matrix(
        self,
        portfolio,
        *,
        profiles=None,
        timeout=180,
    ):

        if profiles is None:

            profiles = (
                {
                    "name":
                        "ideal",
                },

                {
                    "name":
                        "one_tick",
                },

                {
                    "name":
                        "probabilistic",

                    "random_seed":
                        42,
                },

                {
                    "name":
                        "delayed",
                },

                {
                    "name":
                        "stress",

                    "fee_mode":
                        "per_contract",

                    "commission":
                        1.0,

                    "random_seed":
                        42,
                },
            )


        rows = []


        for profile in profiles:

            payload = dict(
                portfolio
            )


            payload[
                "execution"
            ] = dict(
                profile
            )


            result = self.run(
                payload,
                timeout=timeout,
            )


            engine_pnl = result.get(
                "realized_pnl_numeric"
            )


            proxy_pnl = (
                result[
                    "drawdown_attribution"
                ][
                    "portfolio_total_proxy_pnl"
                ]
            )


            rows.append(
                {
                    "profile":
                        dict(
                            profile
                        ),

                    "fill_count":
                        result[
                            "fill_count"
                        ],

                    "engine_realized_pnl":
                        engine_pnl,

                    "signal_proxy_pnl":
                        proxy_pnl,

                    "proxy_max_drawdown":
                        result[
                            "drawdown_attribution"
                        ][
                            "max_drawdown"
                        ],

                    "live_execution":
                        False,
                }
            )


        return {
            "success":
                True,

            "rows":
                tuple(
                    rows
                ),

            "profile_count":
                len(
                    rows
                ),

            "same_portfolio":
                True,

            "automatic_profile_selection":
                False,

            "research_only":
                True,

            "live_execution":
                False,
        }


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
            "rebalance",
        )


        if any(
            token in lower

            for token
            in forbidden
        ):

            raise PermissionError(
                "C3 portfolio bridge is research-only."
            )


        raise AttributeError(
            name
        )


nautilus_c3_portfolio_bridge = (
    NautilusC3PortfolioBridge()
)
