from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)

from enum import Enum

from pathlib import Path

import importlib
import inspect
import json
import time
import uuid


class ActionRisk(
    str,
    Enum,
):

    READ_ONLY = "read_only"

    LOW = "low"

    MEDIUM = "medium"

    BLOCKED = "blocked"


DEFAULT_POLICY = {

    # Pure/read-oriented tools

    "current_time":
        ActionRisk.READ_ONLY,

    "system_info":
        ActionRisk.READ_ONLY,

    "list_files":
        ActionRisk.READ_ONLY,

    "search_files":
        ActionRisk.READ_ONLY,

    "recall":
        ActionRisk.READ_ONLY,

    "show_memory":
        ActionRisk.READ_ONLY,


    # Low-impact workstation actions

    "open_notepad":
        ActionRisk.LOW,

    "open_calculator":
        ActionRisk.LOW,

    "open_application":
        ActionRisk.LOW,

    "open_folder":
        ActionRisk.LOW,

    "open_file":
        ActionRisk.LOW,


    # Explicit approval required

    "open_website":
        ActionRisk.MEDIUM,

    "close_application":
        ActionRisk.MEDIUM,

    "remember":
        ActionRisk.MEDIUM,

    "forget":
        ActionRisk.MEDIUM,
}


SENSITIVE_ARGUMENT_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
}


@dataclass(frozen=True)
class ActionResult:

    action_id: str

    tool: str

    success: bool

    risk: ActionRisk

    approved: bool

    output: object = None

    error: str | None = None

    duration_seconds: float = 0.0


class ToolBridge:
    """
    Runtime adapter for the existing JARVIS Tool Registry.

    Does not create a second registry.
    """

    def __init__(
        self,
        registry_loader=None,
    ):

        self.registry_loader = (
            registry_loader
            or self._default_registry
        )


    @staticmethod
    def _default_registry():

        from tools.registry import (
            list_tools,
        )

        return list_tools()


    def tools(self):

        result = self.registry_loader()

        if isinstance(
            result,
            dict,
        ):

            return result

        raise RuntimeError(
            "JARVIS list_tools() did not "
            "return a dictionary."
        )


    def names(self):

        return tuple(
            sorted(
                self.tools().keys()
            )
        )


    @staticmethod
    def _call(
        function,
        arguments,
    ):

        arguments = dict(
            arguments
            or {}
        )

        return function(
            **arguments
        )


    def _resolve_from_definition(
        self,
        definition,
    ):

        if callable(
            definition
        ):

            return definition


        for attribute in (
            "handler",
            "function",
            "func",
            "callable",
            "executor",
            "run",
            "execute",
        ):

            candidate = getattr(
                definition,
                attribute,
                None,
            )

            if callable(
                candidate
            ):

                return candidate


        module = getattr(
            definition,
            "module",
            None,
        )

        entrypoint = (
            getattr(
                definition,
                "entrypoint",
                None,
            )
            or getattr(
                definition,
                "function_name",
                None,
            )
        )


        if (
            isinstance(
                module,
                str,
            )

            and isinstance(
                entrypoint,
                str,
            )
        ):

            imported = (
                importlib
                .import_module(
                    module
                )
            )

            candidate = getattr(
                imported,
                entrypoint,
                None,
            )

            if callable(
                candidate
            ):

                return candidate


        if isinstance(
            definition,
            dict,
        ):

            for key in (
                "handler",
                "function",
                "func",
                "callable",
            ):

                candidate = (
                    definition.get(
                        key
                    )
                )

                if callable(
                    candidate
                ):

                    return candidate


        return None


    @staticmethod
    def _fallback_module_tool(
        name,
    ):

        # Existing tools are still authoritative:
        # fallback only searches known JARVIS tool modules.

        for module_name in (
            "tools.computer",
            "tools.memory",
            "tools.files",
        ):

            try:

                module = (
                    importlib
                    .import_module(
                        module_name
                    )
                )

            except Exception:
                continue


            candidate = getattr(
                module,
                name,
                None,
            )


            if callable(
                candidate
            ):

                return candidate


        return None


    def invoke(
        self,
        name,
        arguments=None,
    ):

        tools = self.tools()


        if name not in tools:

            raise KeyError(
                "Unknown registered tool: "
                + str(name)
            )


        function = (
            self
            ._resolve_from_definition(
                tools[
                    name
                ]
            )
        )


        if function is None:

            function = (
                self
                ._fallback_module_tool(
                    name
                )
            )


        if function is None:

            raise RuntimeError(
                "Registered tool has no "
                "resolvable callable: "
                + str(name)
            )


        return self._call(
            function,
            arguments,
        )


class ActionPolicy:

    def __init__(
        self,
        policy=None,
    ):

        self.policy = dict(
            DEFAULT_POLICY
        )

        if policy:

            self.policy.update(
                policy
            )


    def classify(
        self,
        tool,
    ):

        tool = str(
            tool
        )


        # Never allow generic action execution
        # to acquire trading execution capability.

        lower = tool.lower()

        if any(
            marker in lower

            for marker in (
                "trade",
                "order",
                "buy",
                "sell",
                "position",
                "broker",
                "fyers",
            )
        ):

            if (
                "research"
                not in lower
                and "analy"
                not in lower
            ):

                return (
                    ActionRisk.BLOCKED
                )


        return self.policy.get(
            tool,
            ActionRisk.BLOCKED,
        )


    def requires_approval(
        self,
        tool,
    ):

        return (
            self.classify(
                tool
            )
            == ActionRisk.MEDIUM
        )


class ActionEngine:

    def __init__(
        self,
        *,
        bridge=None,
        policy=None,
        audit_path=None,
    ):

        self.bridge = (
            bridge
            or ToolBridge()
        )

        self.policy = (
            policy
            or ActionPolicy()
        )

        self.audit_path = Path(
            audit_path
            or (
                Path("data")
                / "audit"
                / "actions.jsonl"
            )
        )


    @staticmethod
    def _redact(
        arguments,
    ):

        clean = {}

        for key, value in dict(
            arguments
            or {}
        ).items():

            if str(
                key
            ).lower() in (
                SENSITIVE_ARGUMENT_KEYS
            ):

                clean[
                    key
                ] = "[REDACTED]"

            else:

                clean[
                    key
                ] = value

        return clean


    def _audit(
        self,
        result,
        arguments,
    ):

        self.audit_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        record = {
            **asdict(
                result
            ),

            "risk":
                result.risk.value,

            "arguments":
                self._redact(
                    arguments
                ),

            "timestamp":
                time.time(),
        }


        with self.audit_path.open(
            "a",
            encoding="utf-8",
        ) as handle:

            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )


    def execute(
        self,
        tool,
        arguments=None,
        *,
        approved=False,
    ):

        tool = str(
            tool
        )

        arguments = dict(
            arguments
            or {}
        )


        action_id = (
            "action-"
            + uuid.uuid4()
            .hex[:16]
        )


        risk = (
            self.policy
            .classify(
                tool
            )
        )


        if risk == ActionRisk.BLOCKED:

            result = ActionResult(
                action_id=
                    action_id,

                tool=
                    tool,

                success=
                    False,

                risk=
                    risk,

                approved=
                    bool(
                        approved
                    ),

                error=
                    "Action is blocked by policy.",
            )

            self._audit(
                result,
                arguments,
            )

            return result


        if (
            risk
            == ActionRisk.MEDIUM

            and not approved
        ):

            result = ActionResult(
                action_id=
                    action_id,

                tool=
                    tool,

                success=
                    False,

                risk=
                    risk,

                approved=False,

                error=
                    "Explicit approval required.",
            )

            self._audit(
                result,
                arguments,
            )

            return result


        started = (
            time.perf_counter()
        )


        try:

            output = (
                self.bridge
                .invoke(
                    tool,
                    arguments,
                )
            )


            result = ActionResult(
                action_id=
                    action_id,

                tool=
                    tool,

                success=True,

                risk=
                    risk,

                approved=
                    bool(
                        approved
                    ),

                output=
                    output,

                duration_seconds=
                    round(
                        time.perf_counter()
                        - started,
                        4,
                    ),
            )


        except Exception as exc:

            result = ActionResult(
                action_id=
                    action_id,

                tool=
                    tool,

                success=False,

                risk=
                    risk,

                approved=
                    bool(
                        approved
                    ),

                error=(
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                ),

                duration_seconds=
                    round(
                        time.perf_counter()
                        - started,
                        4,
                    ),
            )


        self._audit(
            result,
            arguments,
        )

        return result


    def status(self):

        names = (
            self.bridge
            .names()
        )

        return {
            "registered_tools":
                len(names),

            "tools":
                names,

            "policy": {
                name:
                    self.policy
                    .classify(
                        name
                    ).value

                for name in names
            },

            "unknown_tools":
                "blocked",

            "medium_actions":
                "explicit-approval",

            "audit_log":
                str(
                    self.audit_path
                ),

            "trading_execution":
                "blocked",
        }


action_engine = (
    ActionEngine()
)
