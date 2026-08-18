from __future__ import annotations

from pathlib import Path

import os


class GoogleTokenVault:

    DESCRIPTION = (
        "JARVIS Google OAuth Token"
    )


    def __init__(
        self,
        path=None,
    ):

        self.path = Path(
            path
            or (
                Path("data")
                / "credentials"
                / "google_oauth.dpapi"
            )
        )


    @staticmethod
    def available():

        try:

            import win32crypt

            return True

        except Exception:

            return False


    def exists(
        self,
    ):

        return (
            self.path.exists()

            and self.path.stat().st_size
            > 0
        )


    def save_text(
        self,
        text,
    ):

        import win32crypt


        data = str(
            text
        ).encode(
            "utf-8"
        )


        encrypted = (
            win32crypt.CryptProtectData(
                data,
                self.DESCRIPTION,
                None,
                None,
                None,
                0,
            )
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = (
            self.path
            .with_suffix(
                ".tmp"
            )
        )


        temporary.write_bytes(
            encrypted
        )


        try:

            os.chmod(
                temporary,
                0o600,
            )

        except Exception:

            pass


        temporary.replace(
            self.path
        )


        return {
            "success":
                True,

            "path":
                str(
                    self.path
                ),

            "encrypted":
                True,

            "bytes":
                len(
                    encrypted
                ),
        }


    def load_text(
        self,
    ):

        import win32crypt


        if not self.exists():

            raise FileNotFoundError(
                "Google OAuth token vault "
                "does not exist."
            )


        encrypted = (
            self.path.read_bytes()
        )


        description, data = (
            win32crypt.CryptUnprotectData(
                encrypted,
                None,
                None,
                None,
                0,
            )
        )


        return data.decode(
            "utf-8"
        )


    def delete(
        self,
    ):

        existed = self.path.exists()


        self.path.unlink(
            missing_ok=True
        )


        return {
            "success":
                True,

            "existed":
                existed,
        }


google_token_vault = (
    GoogleTokenVault()
)
