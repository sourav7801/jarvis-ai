from __future__ import annotations

from omni.action_engine import (
    action_engine,
)


class ToolDiscovery:

    def inventory(self):

        return (
            action_engine
            .status()
        )


    def executable_without_approval(
        self,
    ):

        status = self.inventory()

        return tuple(
            name

            for name, risk
            in status[
                "policy"
            ].items()

            if risk in (
                "read_only",
                "low",
            )
        )


    def approval_required(
        self,
    ):

        status = self.inventory()

        return tuple(
            name

            for name, risk
            in status[
                "policy"
            ].items()

            if risk
            == "medium"
        )


    def blocked(
        self,
    ):

        status = self.inventory()

        return tuple(
            name

            for name, risk
            in status[
                "policy"
            ].items()

            if risk
            == "blocked"
        )


tool_discovery = (
    ToolDiscovery()
)
