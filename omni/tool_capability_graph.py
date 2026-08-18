from __future__ import annotations


class ToolCapabilityGraph:

    def snapshot(self):

        return {
            "computer": {
                "observe": (
                    "ui.windows",
                    "ui.controls",
                    "screen.analyze",
                ),

                "act": (
                    "ui.click",
                    "ui.set_text",
                ),

                "approval_required": (
                    "ui.click",
                    "ui.set_text",
                    "screen.capture",
                ),
            },

            "browser": {
                "observe": (
                    "browser.inspect",
                ),

                "act": (
                    "browser.click",
                    "browser.fill",
                ),

                "provider":
                    "playwright",

                "persistent_sessions":
                    True,

                "credentials":
                    False,
            },

            "documents": {
                "observe": (
                    "document.read",
                    "document.search",
                ),

                "write":
                    (),
            },

            "files": {
                "external_download":
                    True,

                "executable_download":
                    False,

                "approval_required":
                    True,
            },

            "git": {
                "read": (
                    "git.status",
                    "git.diff",
                    "git.repository_state",
                ),

                "isolated_worktree":
                    True,

                "automatic_merge":
                    False,

                "automatic_push":
                    False,
            },

            "trading": {
                "research":
                    True,

                "execution":
                    False,
            },
        }


    def capabilities(self):

        return (
            "computer.observe",
            "computer.semantic_ui",
            "computer.click",
            "computer.type",
            "browser.inspect",
            "browser.click",
            "browser.fill",
            "browser.session",
            "document.read",
            "document.search",
            "file.download.safe",
            "git.inspect",
            "git.worktree",
            "workflow.observe",
            "workflow.replan.propose",
        )


tool_capability_graph = (
    ToolCapabilityGraph()
)
