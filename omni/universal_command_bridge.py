from __future__ import annotations

import inspect


COMMAND_CANDIDATES = (
    "execute_command",
    "handle_command",
    "process_command",
    "run_command",
    "ask_jarvis",
    "jarvis_command_answer",
)


def _text(
    result,
):

    if result is None:

        return ""


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
            "answer",
            "message",
            "output",
            "text",
            "result",
        ):

            value = result.get(
                key
            )


            if isinstance(
                value,
                str,
            ):

                return value


    for name in (
        "response",
        "answer",
        "message",
        "output",
        "text",
    ):

        value = getattr(
            result,
            name,
            None,
        )


        if isinstance(
            value,
            str,
        ):

            return value


    return str(
        result
    )


class UniversalCommandBridge:

    def discover(
        self,
    ):

        import main


        found = []


        for name in COMMAND_CANDIDATES:

            function = getattr(
                main,
                name,
                None,
            )


            if not callable(
                function
            ):

                continue


            try:

                signature = str(
                    inspect.signature(
                        function
                    )
                )

            except Exception:

                signature = "<unavailable>"


            found.append(
                {
                    "name":
                        name,

                    "signature":
                        signature,
                }
            )


        return tuple(
            found
        )


    def _native(
        self,
        text,
        context,
    ):

        import main


        for name in COMMAND_CANDIDATES:

            function = getattr(
                main,
                name,
                None,
            )


            if not callable(
                function
            ):

                continue


            try:

                parameters = tuple(
                    inspect.signature(
                        function
                    ).parameters
                )


                if "context" in parameters:

                    return function(
                        text,
                        context=context,
                    )


                return function(
                    text
                )


            except TypeError:

                continue


        return None


    def execute(
        self,
        text,
        *,
        context="master",
    ):

        import main


        text = str(
            text
        ).strip()


        if not text:

            return {
                "success":
                    False,

                "route":
                    "empty",

                "response":
                    "Please give me a command.",
            }


        native = self._native(
            text,
            context,
        )


        if native is not None:

            return {
                "success":
                    True,

                "route":
                    "native_command_handler",

                "response":
                    _text(
                        native
                    ),

                "raw":
                    native,
            }


        if (
            callable(
                getattr(
                    main,
                    "is_mission_request",
                    None,
                )
            )
            and main.is_mission_request(
                text,
                context=context,
            )
        ):

            result = (
                main
                .jarvis_run_mission(
                    text
                )
            )


            return {
                "success":
                    True,

                "route":
                    "mission",

                "response":
                    _text(
                        result
                    ),

                "raw":
                    result,
            }


        if (
            callable(
                getattr(
                    main,
                    "is_operator_request",
                    None,
                )
            )
            and main.is_operator_request(
                text
            )
        ):

            result = (
                main
                .jarvis_operator_run(
                    text
                )
            )


            return {
                "success":
                    True,

                "route":
                    "operator",

                "response":
                    _text(
                        result
                    ),

                "raw":
                    result,
            }


        memory_handler = getattr(
            main,
            "jarvis_memory_command_answer",
            None,
        )


        if callable(
            memory_handler
        ):

            try:

                memory_result = (
                    memory_handler(
                        text
                    )
                )


                if memory_result:

                    rendered = _text(
                        memory_result
                    )


                    if rendered.strip():

                        return {
                            "success":
                                True,

                            "route":
                                "memory_command",

                            "response":
                                rendered,

                            "raw":
                                memory_result,
                        }


            except Exception:

                pass


        route_agent = getattr(
            main,
            "route_agent",
            None,
        )


        if not callable(
            route_agent
        ):

            raise RuntimeError(
                "No JARVIS command route is available."
            )


        result = route_agent(
            "chat",
            text,
        )


        return {
            "success":
                True,

            "route":
                "chat",

            "response":
                _text(
                    result
                ),

            "raw":
                result,
        }


command_bridge = (
    UniversalCommandBridge()
)
