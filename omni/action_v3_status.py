from __future__ import annotations

import shutil


from omni.core_integrity import (
    verify_protected_core,
)

from omni.persistent_browser import (
    persistent_browser,
)

from omni.semantic_ui import (
    semantic_ui,
)

from omni.voice_adapter import (
    voice_adapter,
)


class ActionV3Status:

    def status(self):

        integrity = (
            verify_protected_core()
        )


        return {
            "protected_core":
                integrity.ok,

            "semantic_ui":
                semantic_ui.available(),

            "playwright":
                persistent_browser.available(),

            "persistent_browser_probe":
                persistent_browser
                .provider_probe(),

            "git":
                bool(
                    shutil.which(
                        "git"
                    )
                ),

            "github_cli":
                bool(
                    shutil.which(
                        "gh"
                    )
                ),

            "voice":
                voice_adapter.status(),

            "automatic_desktop_actions":
                False,

            "automatic_browser_writes":
                False,

            "credential_automation":
                False,

            "automatic_remote_git_write":
                False,

            "automatic_replan_execution":
                False,
        }


action_v3_status = (
    ActionV3Status()
)
