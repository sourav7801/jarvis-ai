from __future__ import annotations

from pathlib import Path

import json
import shutil


from google.auth.transport.requests import (
    Request,
)

from google.oauth2.credentials import (
    Credentials,
)

from google_auth_oauthlib.flow import (
    InstalledAppFlow,
)

from googleapiclient.discovery import (
    build,
)


from omni.google_audit import (
    google_audit,
)

from omni.google_scopes import (
    GOOGLE_SCOPES,
)

from omni.google_token_vault import (
    google_token_vault,
)


class GoogleOAuthManager:

    def __init__(
        self,
        client_secret_path=None,
    ):

        self.client_secret_path = Path(
            client_secret_path
            or (
                Path("config")
                / "google"
                / "client_secret.json"
            )
        )


    def install_client_secret(
        self,
        source,
    ):

        source = Path(
            source
        ).resolve()


        if not source.exists():

            raise FileNotFoundError(
                source
            )


        data = json.loads(
            source.read_text(
                encoding="utf-8"
            )
        )


        if (
            "installed"
            not in data
        ):

            raise ValueError(
                "Google OAuth credential must "
                "be a Desktop app client JSON."
            )


        installed = data[
            "installed"
        ]


        if not installed.get(
            "client_id"
        ):

            raise ValueError(
                "OAuth client_id missing."
            )


        if not installed.get(
            "client_secret"
        ):

            raise ValueError(
                "OAuth client_secret missing."
            )


        self.client_secret_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        shutil.copy2(
            source,
            self.client_secret_path,
        )


        return {
            "success":
                True,

            "path":
                str(
                    self.client_secret_path
                ),

            "type":
                "desktop",
        }


    def client_secret_ready(
        self,
    ):

        if not self.client_secret_path.exists():

            return False


        try:

            data = json.loads(
                self.client_secret_path
                .read_text(
                    encoding="utf-8"
                )
            )


            return bool(
                data.get(
                    "installed",
                    {}
                ).get(
                    "client_id"
                )
            )


        except Exception:

            return False


    def _load_credentials(
        self,
    ):

        if not google_token_vault.exists():

            return None


        try:

            info = json.loads(
                google_token_vault
                .load_text()
            )


            return (
                Credentials
                .from_authorized_user_info(
                    info,

                    scopes=
                        list(
                            GOOGLE_SCOPES
                        ),
                )
            )


        except Exception:

            return None


    def credentials(
        self,
        *,
        refresh=True,
    ):

        credentials = (
            self._load_credentials()
        )


        if credentials is None:

            raise RuntimeError(
                "Google account is not connected."
            )


        if (
            refresh
            and credentials.expired
            and credentials.refresh_token
        ):

            credentials.refresh(
                Request()
            )


            google_token_vault.save_text(
                credentials.to_json()
            )


        if not (
            credentials.valid
            or credentials.refresh_token
        ):

            raise RuntimeError(
                "Google OAuth credentials "
                "are not usable."
            )


        return credentials


    def connect(
        self,
    ):

        if not self.client_secret_ready():

            raise FileNotFoundError(
                "Google Desktop OAuth client JSON "
                "not configured at "
                + str(
                    self.client_secret_path
                )
            )


        flow = (
            InstalledAppFlow
            .from_client_secrets_file(
                str(
                    self.client_secret_path
                ),

                scopes=
                    list(
                        GOOGLE_SCOPES
                    ),
            )
        )


        credentials = (
            flow.run_local_server(
                host=
                    "127.0.0.1",

                port=
                    0,

                open_browser=
                    True,

                authorization_prompt_message=
                    (
                        "JARVIS is opening your "
                        "browser for Google authorization."
                    ),

                success_message=
                    (
                        "Google authorization completed. "
                        "You may close this browser tab "
                        "and return to JARVIS."
                    ),

                access_type=
                    "offline",

                prompt=
                    "consent",
            )
        )


        google_token_vault.save_text(
            credentials.to_json()
        )


        google_audit.record(
            "google.oauth.connect",
            success=True,
            metadata={
                "scopes":
                    list(
                        GOOGLE_SCOPES
                    )
            },
        )


        return self.status()


    def disconnect(
        self,
    ):

        result = (
            google_token_vault.delete()
        )


        google_audit.record(
            "google.oauth.disconnect",
            success=True,
            metadata={
                "token_deleted":
                    result[
                        "existed"
                    ]
            },
        )


        return result


    def service(
        self,
        api,
        version,
    ):

        credentials = (
            self.credentials(
                refresh=True
            )
        )


        return build(
            str(
                api
            ),

            str(
                version
            ),

            credentials=
                credentials,

            cache_discovery=
                False,
        )


    def status(
        self,
    ):

        credentials = (
            self._load_credentials()
        )


        return {
            "client_secret_ready":
                self.client_secret_ready(),

            "token_vault_available":
                google_token_vault.available(),

            "token_encrypted":
                google_token_vault.exists(),

            "connected":
                bool(
                    credentials
                ),

            "token_valid":
                bool(
                    credentials
                    and credentials.valid
                ),

            "token_expired":
                bool(
                    credentials
                    and credentials.expired
                ),

            "refresh_token_present":
                bool(
                    credentials
                    and credentials.refresh_token
                ),

            "scopes":
                tuple(
                    GOOGLE_SCOPES
                ),
        }


google_oauth = (
    GoogleOAuthManager()
)
