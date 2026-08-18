from __future__ import annotations

import uuid


from omni.collaboration_runtime import (
    AgentRequest,
)

from omni.operator_dsl import (
    parse_json,
    planner_prompt,
)

import importlib


def _resolve_default_runner():

    modules = (
        "omni.collaboration_service",
        "omni.collaboration_runtime",
        "omni.autonomy_engine",
        "omni.runtime",
        "main",
    )

    factory_names = (
        "build_runtime",
        "get_runtime",
        "create_runtime",
    )

    runner_names = (
        "runner",
        "governed_runner",
        "agent_runner",
    )

    errors = []


    for module_name in modules:

        try:

            module = importlib.import_module(
                module_name
            )

        except Exception as exc:

            errors.append(
                module_name
                + ": "
                + type(
                    exc
                ).__name__
                + ": "
                + str(
                    exc
                )
            )

            continue


        # ----------------------------------------
        # Runtime factory -> .runner
        # ----------------------------------------

        for factory_name in factory_names:

            factory = getattr(
                module,
                factory_name,
                None,
            )


            if not callable(
                factory
            ):

                continue


            try:

                runtime = factory()

            except TypeError:

                continue

            except Exception as exc:

                errors.append(
                    module_name
                    + "."
                    + factory_name
                    + ": "
                    + type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )

                continue


            runner = getattr(
                runtime,
                "runner",
                None,
            )


            if callable(
                runner
            ):

                return runner


            if callable(
                runtime
            ):

                return runtime


        # ----------------------------------------
        # Direct module-level runner
        # ----------------------------------------

        for runner_name in runner_names:

            runner = getattr(
                module,
                runner_name,
                None,
            )


            if callable(
                runner
            ):

                return runner


        # ----------------------------------------
        # Existing runtime/service object
        # exposing a callable .runner
        # ----------------------------------------

        for name, obj in vars(
            module
        ).items():

            if isinstance(
                obj,
                type,
            ):

                continue


            try:

                runner = getattr(
                    obj,
                    "runner",
                    None,
                )

            except Exception:

                continue


            if callable(
                runner
            ):

                return runner


    raise RuntimeError(
        "No governed JARVIS agent runner "
        "could be discovered. "
        "Checked: "
        + ", ".join(
            modules
        )
        + ". Errors: "
        + " | ".join(
            errors[-10:]
        )
    )


class BrainDSLPlanner:

    @staticmethod
    def _extract(
        result,
    ):

        if isinstance(
            result,
            str,
        ):

            return result


        if isinstance(
            result,
            dict,
        ):

            for key in (
                "response",
                "text",
                "output",
                "content",
                "message",
            ):

                value = result.get(
                    key
                )


                if (
                    isinstance(
                        value,
                        str,
                    )
                    and value.strip()
                ):

                    return value


                if isinstance(
                    value,
                    dict,
                ):

                    content = value.get(
                        "content"
                    )


                    if (
                        isinstance(
                            content,
                            str,
                        )
                        and content.strip()
                    ):

                        return content


        for key in (
            "response",
            "text",
            "output",
            "content",
            "message",
        ):

            value = getattr(
                result,
                key,
                None,
            )


            if (
                isinstance(
                    value,
                    str,
                )
                and value.strip()
            ):

                return value


            if isinstance(
                value,
                dict,
            ):

                content = value.get(
                    "content"
                )


                if (
                    isinstance(
                        content,
                        str,
                    )
                    and content.strip()
                ):

                    return content


        return str(
            result
        )


    def propose(
        self,
        goal,
        *,
        observations=None,
        runner=None,
    ):

        prompt = planner_prompt(
            goal,
            observations,
        )


        if runner is None:

            runner = (
                _resolve_default_runner()
            )


        request = AgentRequest(
            agent=
                "operator",

            text=
                prompt,

            required_capabilities=
                frozenset(),

            correlation_id=
                (
                    "operator-dsl-"
                    + uuid.uuid4()
                    .hex[:16]
                ),
        )


        result = runner(
            request
        )


        raw = (
            self._extract(
                result
            )
            .strip()
        )


        try:

            plan = parse_json(
                goal,

                raw,

                source=
                    "operator-agent-proposal",
            )


            return {
                "success":
                    True,

                "valid":
                    True,

                "plan":
                    plan,

                "raw":
                    raw[:20000],

                "auto_execute":
                    False,
            }


        except Exception as exc:

            return {
                "success":
                    False,

                "valid":
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

                "raw":
                    raw[:20000],

                "prompt":
                    prompt,

                "auto_execute":
                    False,
            }


brain_dsl_planner = (
    BrainDSLPlanner()
)
