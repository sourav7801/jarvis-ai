from __future__ import annotations

import importlib.util


from omni.connected_services_gateway import (
    connected_services_gateway,
)

from omni.core_integrity import (
    verify_protected_core,
)


def _available(
    module,
):

    return (
        importlib.util.find_spec(
            module
        )
        is not None
    )


class ConnectedServicesStatus:

    def status(
        self,
    ):

        integrity = (
            verify_protected_core()
        )


        gateway = (
            connected_services_gateway
            .status()
        )


        return {
            "protected_core":
                integrity.ok,

            "dependencies": {
                "google_api_python_client":
                    _available(
                        "googleapiclient"
                    ),

                "google_auth":
                    _available(
                        "google.auth"
                    ),

                "google_auth_oauthlib":
                    _available(
                        "google_auth_oauthlib"
                    ),

                "windows_dpapi":
                    _available(
                        "win32crypt"
                    ),
            },

            **gateway,
        }


connected_services_status = (
    ConnectedServicesStatus()
)
