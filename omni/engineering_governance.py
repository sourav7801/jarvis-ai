"""Governed local engineering workflow for JARVIS V10.

The workflow can inspect repository state, create a child branch when explicitly
requested, run bounded compile/test commands, and materialize a review packet.
It deliberately cannot edit production source automatically, merge, push,
deploy, or change broker/live-execution policy.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "state" / "engineering_governance.json"
REVIEW_ROOT = ROOT / "data" / "engineering_reviews"
MAX_RUNS = 100
_PROTECTED_BRANCH_FRAGMENTS = (
    "JARVIS-V8-unified-intelligence-os",
    "JARVIS-V7-project-completion-core",
    "JARVIS-V6-3-full-advanced-single-patch",
    "JARVIS-V6-2-runtime-hardening",
)
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{3,180}$")
_TEST_RE = re.compile(r"^[A-Za-z0-9_.-]{3,240}$")
_REL_PY_RE = re.compile(r"^[A-Za-z0-9_./\\-]+\.py$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(args: list[str], *, timeout: float = 30.0) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=max(1.0, min(float(timeout), 900.0)),
            check=False,
        )
        return {
            "success": completed.returncode == 0,
            "returncode": int(completed.returncode),
            "stdout": (completed.stdout or "")[-12000:],
            "stderr": (completed.stderr or "")[-12000:],
            "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000.0, 2),
            "argv": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "returncode": None,
            "stdout": str(exc.stdout or "")[-4000:],
            "stderr": str(exc.stderr or "")[-4000:],
            "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000.0, 2),
            "argv": args,
            "error": "TIMEOUT",
        }
    except OSError as exc:
        return {
            "success": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}"[:1000],
            "duration_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000.0, 2),
            "argv": args,
            "error": type(exc).__name__,
        }


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


class GovernedEngineeringWorkflow:
    def __init__(self, state_path: Path | str = STATE_PATH) -> None:
        self.state_path = Path(state_path)
        self._lock = RLock()
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value.setdefault("runs", [])
                return value
        except (FileNotFoundError, OSError, ValueError, TypeError):
            pass
        return {"version": 1, "runs": [], "updated_at": None}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        temporary.replace(self.state_path)

    def inspect(self) -> dict[str, Any]:
        branch = _run(["git", "branch", "--show-current"])
        head = _run(["git", "rev-parse", "HEAD"])
        status = _run(["git", "status", "--porcelain"])
        diff_check = _run(["git", "diff", "--check"])
        diff_stat = _run(["git", "diff", "--stat", "HEAD"])
        return {
            "success": branch["success"] and head["success"] and status["success"],
            "branch": branch["stdout"].strip(),
            "head": head["stdout"].strip(),
            "clean": not bool(status["stdout"].strip()),
            "status_porcelain": status["stdout"].splitlines()[-200:],
            "diff_check": diff_check,
            "diff_stat": diff_stat["stdout"].splitlines()[-200:],
            "root": str(ROOT),
            "automatic_editing": False,
            "automatic_merge": False,
            "automatic_push": False,
            "automatic_deploy": False,
            "paper_only": True,
            "live_execution": False,
        }

    def plan(self, request: str) -> dict[str, Any]:
        clean = " ".join(str(request or "").split())[:6000]
        if len(clean) < 8:
            raise ValueError("Engineering request is too short.")
        try:
            from omni.code_intelligence import CODE_INTELLIGENCE
            matches = CODE_INTELLIGENCE.search(clean, limit=12)
        except Exception:
            matches = []
        inspection = self.inspect()
        plan = {
            "success": True,
            "workflow_id": "eng-" + uuid4().hex[:20],
            "version": "10.0",
            "created_at": _now(),
            "request": clean,
            "repository": inspection,
            "code_matches": matches,
            "stages": [
                "INSPECT", "PLAN", "CREATE_CHILD_BRANCH", "EDIT_GOVERNED",
                "COMPILE", "TARGETED_TESTS", "FULL_REGRESSION_IF_RELEASE",
                "DIFF_CHECK", "CRITIC_VERIFY", "REVIEW_PACKET", "WAIT_APPROVAL",
            ],
            "current_stage": "PLAN",
            "next_action": "Apply bounded edits through an explicitly governed editing surface; automatic production rewrite is disabled.",
            "safety": {
                "automatic_editing": False,
                "automatic_production_rewrite": False,
                "automatic_merge": False,
                "automatic_push": False,
                "external_actions": "APPROVAL_GATED",
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            },
        }
        self._record(plan)
        self._emit("FILE_CHANGED", plan["workflow_id"], {"stage": "PLAN_CREATED", "request": clean[:500]})
        return plan

    def create_child_branch(self, branch_name: str, *, operator_confirmed: bool = False) -> dict[str, Any]:
        if not operator_confirmed:
            raise PermissionError("Local branch creation requires explicit operator confirmation.")
        name = str(branch_name or "").strip()
        if not _BRANCH_RE.fullmatch(name) or ".." in name or name.startswith("-"):
            raise ValueError("Unsafe branch name.")
        if any(fragment.lower() in name.lower() for fragment in _PROTECTED_BRANCH_FRAGMENTS):
            raise PermissionError("Verified/protected recovery branches cannot be reused for development.")
        inspection = self.inspect()
        if not inspection["clean"]:
            raise RuntimeError("Working tree must be clean before creating a governed child branch.")
        result = _run(["git", "switch", "-c", name], timeout=20)
        if not result["success"]:
            raise RuntimeError(result["stderr"] or "git branch creation failed")
        return {"success": True, "branch": name, "base_head": inspection["head"], "external_actions": "LOCAL_REVERSIBLE_ONLY"}

    def run_checks(
        self,
        *,
        python_files: Iterable[str] = (),
        test_modules: Iterable[str] = (),
        full_regression: bool = False,
    ) -> dict[str, Any]:
        compile_results: list[dict[str, Any]] = []
        for raw in list(python_files)[:80]:
            rel = str(raw).replace("\\", "/").strip()
            if not _REL_PY_RE.fullmatch(rel):
                raise ValueError(f"Unsafe Python path: {raw}")
            path = (ROOT / rel).resolve()
            if not _inside_root(path) or not path.exists():
                raise ValueError(f"Python file is outside repository or missing: {rel}")
            compile_results.append(_run([sys.executable, "-m", "py_compile", str(path)], timeout=30))

        test_results: list[dict[str, Any]] = []
        modules = list(test_modules)[:50]
        for module in modules:
            value = str(module).strip()
            if not _TEST_RE.fullmatch(value) or not value.startswith("tests."):
                raise ValueError(f"Unsafe unittest module: {module}")
            test_results.append(_run([sys.executable, "-m", "unittest", value, "-q"], timeout=180))
        full_result = None
        if full_regression:
            full_result = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], timeout=900)
        diff_check = _run(["git", "diff", "--check"], timeout=30)
        success = (
            all(item["success"] for item in compile_results)
            and all(item["success"] for item in test_results)
            and (full_result is None or full_result["success"])
            and diff_check["success"]
        )
        payload = {
            "success": success,
            "compile": compile_results,
            "targeted_tests": test_results,
            "full_regression": full_result,
            "diff_check": diff_check,
            "paper_only": True,
            "live_execution": False,
        }
        self._emit("TEST_PASSED" if success else "TEST_FAILED", "engineering-checks", {"success": success})
        return payload

    def review_packet(
        self,
        *,
        request: str = "",
        test_results: dict[str, Any] | None = None,
        known_risks: Iterable[str] = (),
    ) -> dict[str, Any]:
        inspection = self.inspect()
        changed = _run(["git", "diff", "--name-only", "HEAD"])
        changed_files = [row.strip() for row in changed["stdout"].splitlines() if row.strip()][:300]
        evidence = [
            {
                "source": "git",
                "freshness": "FRESH",
                "provenance": {"head": inspection["head"], "branch": inspection["branch"]},
                "claim": "Repository state inspected",
            }
        ]
        if test_results:
            evidence.append({
                "source": "engineering_governance",
                "freshness": "FRESH",
                "provenance": {"kind": "test_results"},
                "claim": "Bounded validation results supplied",
                "success": bool(test_results.get("success")),
            })
        from omni.critic_verifier import CRITIC_VERIFIER
        critic = CRITIC_VERIFIER.verify(
            subject=f"engineering:{inspection['branch']}:{inspection['head'][:12]}",
            domain="ENGINEERING",
            evidence=evidence,
            tool_results=[test_results] if test_results else [],
            required_evidence=1,
            require_fresh=True,
            require_provenance=True,
            policy={
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            },
        )
        packet_id = "review-" + uuid4().hex[:20]
        packet = {
            "success": True,
            "review_id": packet_id,
            "created_at": _now(),
            "request": str(request or "")[:6000],
            "branch": inspection["branch"],
            "head": inspection["head"],
            "clean": inspection["clean"],
            "changed_files": changed_files,
            "diff_stat": inspection["diff_stat"],
            "diff_check_pass": bool(inspection["diff_check"].get("success")),
            "tests": test_results or {"run": False},
            "critic": critic,
            "known_risks": [str(item)[:500] for item in list(known_risks)[:30]],
            "recommended_next_action": "WAIT_FOR_OPERATOR_REVIEW",
            "merge_performed": False,
            "push_performed": False,
            "deploy_performed": False,
            "automatic_production_rewrite": False,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
        REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
        path = REVIEW_ROOT / f"{packet_id}.json"
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        packet["artifact"] = str(path)
        self._record(packet)
        return packet

    def _record(self, payload: dict[str, Any]) -> None:
        with self._lock:
            rows = list(self._state.get("runs") or [])
            rows.append({
                "recorded_at": _now(),
                "workflow_id": payload.get("workflow_id") or payload.get("review_id"),
                "request": str(payload.get("request") or "")[:1000],
                "branch": payload.get("branch") or (payload.get("repository") or {}).get("branch"),
                "head": payload.get("head") or (payload.get("repository") or {}).get("head"),
                "stage": payload.get("current_stage") or ("REVIEW_PACKET" if payload.get("review_id") else "UNKNOWN"),
            })
            self._state["runs"] = rows[-MAX_RUNS:]
            self._state["updated_at"] = _now()
            self._save()

    @staticmethod
    def _emit(event_type: str, subject: str, payload: dict[str, Any]) -> None:
        try:
            from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS, CognitiveEventType
            COGNITIVE_EVENT_BUS.publish(
                CognitiveEventType(event_type),
                source="engineering_governance",
                subject=subject,
                payload=payload,
                provenance={"scope": "LOCAL_REPOSITORY", "automatic_editing": False},
            )
        except Exception:
            pass

    def status(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._state.get("runs") or [])[-20:]
            updated = self._state.get("updated_at")
        return {
            "success": True,
            "version": "10.0",
            "service": "JARVIS_ENGINEERING_GOVERNANCE",
            "updated_at": updated,
            "recent_runs": rows,
            "capabilities": {
                "inspect_repository": True,
                "create_child_branch_explicit": True,
                "run_bounded_compile": True,
                "run_bounded_unittest": True,
                "run_full_regression_explicit": True,
                "materialize_review_packet": True,
                "automatic_editing": False,
                "automatic_merge": False,
                "automatic_push": False,
                "automatic_deploy": False,
            },
            "external_actions": "APPROVAL_GATED",
            "automatic_production_strategy_rewrite": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


ENGINEERING_GOVERNANCE = GovernedEngineeringWorkflow()

__all__ = ["ENGINEERING_GOVERNANCE", "GovernedEngineeringWorkflow"]
