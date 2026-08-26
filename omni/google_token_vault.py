from __future__ import annotations

from pathlib import Path

import os


class GoogleTokenVault:

    DPAPI_PREFIX = b"DPAPI1:"
    FERNET_PREFIX = b"FERNET1:"

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

        data = str(
            text
        ).encode(
            "utf-8"
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        provider = "WINDOWS_DPAPI"
        try:
            import win32crypt

            encrypted = self.DPAPI_PREFIX + win32crypt.CryptProtectData(
                data,
                self.DESCRIPTION,
                None,
                None,
                None,
                0,
            )
        except Exception:
            from cryptography.fernet import Fernet

            provider = "LOCAL_FERNET"
            key_path = self._fallback_key_path()
            if key_path.exists():
                key = key_path.read_bytes()
            else:
                key = Fernet.generate_key()
                key_path.write_bytes(key)
                try:
                    os.chmod(key_path, 0o600)
                except Exception:
                    pass
            encrypted = self.FERNET_PREFIX + Fernet(key).encrypt(data)


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

            "provider":
                provider,

            "bytes":
                len(
                    encrypted
                ),
        }


    def load_text(
        self,
    ):

        if not self.exists():

            raise FileNotFoundError(
                "Google OAuth token vault "
                "does not exist."
            )


        encrypted = (
            self.path.read_bytes()
        )


        if encrypted.startswith(self.FERNET_PREFIX):
            from cryptography.fernet import Fernet

            key = self._fallback_key_path().read_bytes()
            data = Fernet(key).decrypt(encrypted[len(self.FERNET_PREFIX):])
        else:
            import win32crypt

            payload = (
                encrypted[len(self.DPAPI_PREFIX):]
                if encrypted.startswith(self.DPAPI_PREFIX)
                else encrypted
            )
            _description, data = win32crypt.CryptUnprotectData(
                payload,
                None,
                None,
                None,
                0,
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

        self._fallback_key_path().unlink(
            missing_ok=True
        )


        return {
            "success":
                True,

            "existed":
                existed,
        }


    def _fallback_key_path(self):

        return self.path.with_suffix(
            self.path.suffix + ".key"
        )


google_token_vault = (
    GoogleTokenVault()
)
