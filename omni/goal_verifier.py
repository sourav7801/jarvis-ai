from __future__ import annotations

from pathlib import Path

import json


class GoalVerifier:

    @staticmethod
    def _text(
        value,
    ):

        try:

            return json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )

        except Exception:

            return str(
                value
            )


    def verify(
        self,
        specification,
        output,
    ):

        specification = dict(
            specification
            or {}
        )


        if not specification:

            return {
                "required":
                    False,

                "passed":
                    None,

                "checks":
                    (),
            }


        checks = []


        text = self._text(
            output
        )


        if (
            "contains"
            in specification
        ):

            expected = str(
                specification[
                    "contains"
                ]
            )


            passed = (
                expected.lower()
                in text.lower()
            )


            checks.append(
                {
                    "type":
                        "contains",

                    "expected":
                        expected,

                    "passed":
                        passed,
                }
            )


        if (
            "url_contains"
            in specification
        ):

            expected = str(
                specification[
                    "url_contains"
                ]
            ).lower()


            candidate = ""


            if isinstance(
                output,
                dict,
            ):

                candidate = str(
                    output.get(
                        "url",
                        ""
                    )
                )


                after = output.get(
                    "after"
                )


                if isinstance(
                    after,
                    dict,
                ):

                    candidate = str(
                        after.get(
                            "url",
                            candidate,
                        )
                    )


                observation = output.get(
                    "observation"
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    candidate = str(
                        observation.get(
                            "url",
                            candidate,
                        )
                    )


            passed = (
                expected
                in candidate.lower()
            )


            checks.append(
                {
                    "type":
                        "url_contains",

                    "expected":
                        expected,

                    "actual":
                        candidate,

                    "passed":
                        passed,
                }
            )


        if (
            "title_contains"
            in specification
        ):

            expected = str(
                specification[
                    "title_contains"
                ]
            ).lower()


            candidate = ""


            if isinstance(
                output,
                dict,
            ):

                candidate = str(
                    output.get(
                        "title",
                        ""
                    )
                )


                after = output.get(
                    "after"
                )


                if isinstance(
                    after,
                    dict,
                ):

                    candidate = str(
                        after.get(
                            "title",
                            candidate,
                        )
                    )


                observation = output.get(
                    "observation"
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    candidate = str(
                        observation.get(
                            "title",
                            candidate,
                        )
                    )


            passed = (
                expected
                in candidate.lower()
            )


            checks.append(
                {
                    "type":
                        "title_contains",

                    "expected":
                        expected,

                    "actual":
                        candidate,

                    "passed":
                        passed,
                }
            )


        if (
            "changed"
            in specification
        ):

            expected = bool(
                specification[
                    "changed"
                ]
            )


            actual = None


            if isinstance(
                output,
                dict,
            ):

                comparison = output.get(
                    "comparison"
                )


                if isinstance(
                    comparison,
                    dict,
                ):

                    actual = bool(
                        comparison.get(
                            "changed",
                            False,
                        )
                    )


            passed = (
                actual
                is expected
            )


            checks.append(
                {
                    "type":
                        "changed",

                    "expected":
                        expected,

                    "actual":
                        actual,

                    "passed":
                        passed,
                }
            )


        if (
            "window_open"
            in specification
        ):

            expected = str(
                specification[
                    "window_open"
                ]
            ).lower()


            passed = (
                expected
                in text.lower()
            )


            checks.append(
                {
                    "type":
                        "window_open",

                    "expected":
                        expected,

                    "passed":
                        passed,
                }
            )


        if (
            "file_exists"
            in specification
        ):

            expected_path = Path(
                str(
                    specification[
                        "file_exists"
                    ]
                )
            )


            passed = (
                expected_path.exists()
            )


            checks.append(
                {
                    "type":
                        "file_exists",

                    "path":
                        str(
                            expected_path
                        ),

                    "passed":
                        passed,
                }
            )


        if (
            "min_elements"
            in specification
        ):

            minimum = int(
                specification[
                    "min_elements"
                ]
            )


            count = 0


            if isinstance(
                output,
                dict,
            ):

                observation = output.get(
                    "observation",
                    output,
                )


                if isinstance(
                    observation,
                    dict,
                ):

                    count = len(
                        observation.get(
                            "elements",
                            ()
                        )
                        or ()
                    )


            passed = (
                count
                >= minimum
            )


            checks.append(
                {
                    "type":
                        "min_elements",

                    "expected":
                        minimum,

                    "actual":
                        count,

                    "passed":
                        passed,
                }
            )


        return {
            "required":
                True,

            "passed":
                bool(
                    checks
                )
                and all(
                    item[
                        "passed"
                    ]
                    for item
                    in checks
                ),

            "checks":
                tuple(
                    checks
                ),
        }


goal_verifier = (
    GoalVerifier()
)
