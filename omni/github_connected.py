from __future__ import annotations

from pathlib import Path

import getpass
import hashlib
import json
import os
import time
import uuid

import requests


from omni.approval_queue import approval_queue


API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"


class GitHubTokenVault:

    DESCRIPTION = "JARVIS GitHub API Token"


    def __init__(
        self,
        path=None,
    ):
        self.path = Path(
            path
            or (
                Path("data")
                / "credentials"
                / "github_token.dpapi"
            )
        )


    @staticmethod
    def available():

        try:
            import win32crypt
            return True

        except Exception:
            return False


    def exists(self):

        return (
            self.path.exists()
            and self.path.stat().st_size > 0
        )


    def save(self, token):

        import win32crypt

        token = str(token).strip()

        if len(token) < 20:
            raise ValueError(
                "GitHub token appears invalid."
            )


        encrypted = win32crypt.CryptProtectData(
            token.encode("utf-8"),
            self.DESCRIPTION,
            None,
            None,
            None,
            0,
        )


        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        temporary = self.path.with_suffix(
            ".tmp"
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
            "success": True,
            "encrypted": True,
            "path": str(self.path),
        }


    def load(self):

        import win32crypt

        if not self.exists():
            raise RuntimeError(
                "Local JARVIS GitHub token is not configured."
            )


        encrypted = self.path.read_bytes()

        description, data = win32crypt.CryptUnprotectData(
            encrypted,
            None,
            None,
            None,
            0,
        )

        return data.decode(
            "utf-8"
        ).strip()


    def delete(self):

        existed = self.path.exists()

        self.path.unlink(
            missing_ok=True
        )

        return {
            "success": True,
            "existed": existed,
        }


github_token_vault = GitHubTokenVault()


class GitHubConnectedService:

    def __init__(
        self,
        vault=None,
        session=None,
    ):
        self.vault = (
            vault
            or github_token_vault
        )

        self.session = (
            session
            or requests.Session()
        )

        self.audit_path = (
            Path("data")
            / "audit"
            / "github_services.jsonl"
        )


    def _audit(
        self,
        action,
        *,
        success,
        metadata=None,
        error=None,
    ):

        record = {
            "audit_id": (
                "github-audit-"
                + uuid.uuid4().hex[:16]
            ),
            "timestamp": time.time(),
            "action": str(action),
            "success": bool(success),
            "metadata": metadata or {},
            "error": (
                str(error)[:1000]
                if error
                else None
            ),
        }


        self.audit_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


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


        return record


    def connect_interactive(self):

        token = getpass.getpass(
            "GitHub fine-grained token: "
        ).strip()


        result = self.vault.save(
            token
        )


        try:
            profile = self.profile()

        except Exception:
            self.vault.delete()
            raise


        return {
            "success": True,
            "encrypted": True,
            "login": profile.get(
                "login"
            ),
        }


    def disconnect(self):
        return self.vault.delete()


    def _headers(self):

        token = self.vault.load()

        return {
            "Accept": "application/vnd.github+json",
            "Authorization": (
                "Bearer "
                + token
            ),
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "JARVIS-Connected-Services",
        }


    def _request(
        self,
        method,
        path,
        *,
        params=None,
        body=None,
    ):

        url = (
            API_BASE
            + "/"
            + str(path).lstrip("/")
        )


        response = self.session.request(
            str(method).upper(),
            url,
            headers=self._headers(),
            params=params,
            json=body,
            timeout=20,
        )


        if response.status_code == 204:
            return {}


        try:
            data = response.json()

        except Exception:
            data = {
                "message": (
                    response.text[:1000]
                )
            }


        if not (
            200
            <= response.status_code
            < 300
        ):
            message = (
                data.get(
                    "message"
                )
                if isinstance(
                    data,
                    dict,
                )
                else str(data)
            )

            raise RuntimeError(
                "GitHub API "
                + str(
                    response.status_code
                )
                + ": "
                + str(message)
            )


        return data


    def status(
        self,
        *,
        verify=False,
    ):

        result = {
            "vault_available": (
                self.vault.available()
            ),
            "token_encrypted": (
                self.vault.exists()
            ),
            "connected": False,
            "login": None,
            "api_version": API_VERSION,
            "automatic_write": False,
            "merge_supported": False,
            "force_push_supported": False,
        }


        if (
            verify
            and result[
                "token_encrypted"
            ]
        ):
            try:
                profile = self.profile()

                result["connected"] = True
                result["login"] = profile.get(
                    "login"
                )

            except Exception as exc:
                result["error"] = (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                )

        else:
            result["connected"] = result[
                "token_encrypted"
            ]


        return result


    # --------------------------------------------------------
    # READS
    # --------------------------------------------------------

    def profile(self):

        result = self._request(
            "GET",
            "/user",
        )

        self._audit(
            "github.profile",
            success=True,
            metadata={
                "login": result.get(
                    "login"
                )
            },
        )

        return result


    def repos(
        self,
        *,
        per_page=30,
    ):

        return self._request(
            "GET",
            "/user/repos",
            params={
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
                "sort": "updated",
            },
        )


    def issues(
        self,
        owner,
        repo,
        *,
        state="open",
        per_page=30,
    ):

        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            params={
                "state": str(state),
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
            },
        )


    def pulls(
        self,
        owner,
        repo,
        *,
        state="open",
        per_page=30,
    ):

        return self._request(
            "GET",
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": str(state),
                "per_page": max(
                    1,
                    min(
                        int(per_page),
                        100,
                    ),
                ),
            },
        )


    # --------------------------------------------------------
    # GOVERNED WRITES
    # --------------------------------------------------------

    @staticmethod
    def _hash_text(value):

        text = str(
            value
            or ""
        )

        return {
            "sha256": hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest(),
            "length": len(text),
        }


    def prepare_create_issue(
        self,
        owner,
        repo,
        title,
        body="",
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "title": str(title),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.issue.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "title": str(title),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-write",
        }


    def create_issue(
        self,
        owner,
        repo,
        title,
        body="",
        *,
        approval_id=None,
    ):

        prepared = self.prepare_create_issue(
            owner,
            repo,
            title,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues",
            body={
                "title": str(title),
                "body": str(body),
            },
        )


        self._audit(
            "github.issue.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "number": result.get(
                    "number"
                ),
            },
        )


        return {
            "success": True,
            "issue": result,
        }


    def prepare_comment(
        self,
        owner,
        repo,
        issue_number,
        body,
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "issue_number": int(
                issue_number
            ),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.comment.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "issue_number": int(
                    issue_number
                ),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-write",
        }


    def create_comment(
        self,
        owner,
        repo,
        issue_number,
        body,
        *,
        approval_id=None,
    ):

        prepared = self.prepare_comment(
            owner,
            repo,
            issue_number,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            (
                f"/repos/{owner}/{repo}"
                f"/issues/{int(issue_number)}/comments"
            ),
            body={
                "body": str(body)
            },
        )


        self._audit(
            "github.comment.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "issue_number": int(
                    issue_number
                ),
                "comment_id": result.get(
                    "id"
                ),
            },
        )


        return {
            "success": True,
            "comment": result,
        }


    def prepare_pull(
        self,
        owner,
        repo,
        title,
        head,
        base,
        body="",
    ):

        digest = self._hash_text(
            body
        )


        payload = {
            "owner": str(owner),
            "repo": str(repo),
            "title": str(title),
            "head": str(head),
            "base": str(base),
            "body_sha256": digest["sha256"],
            "body_length": digest["length"],
        }


        return {
            "success": True,
            "action": "github.pull.create",
            "payload": payload,
            "display": {
                "owner": str(owner),
                "repo": str(repo),
                "title": str(title),
                "head": str(head),
                "base": str(base),
                "body_length": digest["length"],
                "body_sha256_prefix": (
                    digest["sha256"][:12]
                ),
            },
            "risk": "github-pull-request-write",
        }


    def create_pull(
        self,
        owner,
        repo,
        title,
        head,
        base,
        body="",
        *,
        approval_id=None,
    ):

        prepared = self.prepare_pull(
            owner,
            repo,
            title,
            head,
            base,
            body,
        )


        if not approval_id:
            return {
                "success": False,
                "requires_approval": True,
                "approval": approval_queue.request(
                    prepared["action"],
                    prepared["payload"],
                    display=prepared["display"],
                    risk=prepared["risk"],
                ),
            }


        approval_queue.consume(
            approval_id,
            prepared["action"],
            prepared["payload"],
        )


        result = self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            body={
                "title": str(title),
                "head": str(head),
                "base": str(base),
                "body": str(body),
            },
        )


        self._audit(
            "github.pull.create",
            success=True,
            metadata={
                "owner": str(owner),
                "repo": str(repo),
                "number": result.get(
                    "number"
                ),
            },
        )


        return {
            "success": True,
            "pull": result,
        }


github_connected = GitHubConnectedService()
