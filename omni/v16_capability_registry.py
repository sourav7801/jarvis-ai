"""Install JARVIS V16 workstation capabilities into one canonical registry.

The first V16 bundle wires managed files, verified artifacts, workspaces and the
existing governed public-URL retriever.  Legacy V15 tools remain discoverable as
metadata adapters while their proven execution paths remain untouched.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from omni.v16_artifact_service import ARTIFACT_SERVICE_V16
from omni.v16_file_service import MANAGED_FILE_SERVICE_V16
from omni.v16_tool_contract import (
    CANONICAL_TOOL_REGISTRY_V16,
    ToolRegistryV16,
    ToolRisk,
    ToolSpec,
    install_legacy_tool_metadata,
)
from omni.v16_workspace_service import WORKSPACE_SERVICE_V16


_INSTALLED = False


def _web_fetch(url: str, max_chars: int = 200_000) -> dict[str, Any]:
    from omni.web_research import GovernedWebRetriever

    document = GovernedWebRetriever().fetch(url)
    text = document.text[: max(1, min(int(max_chars), 500_000))]
    return {
        "success": True,
        "url": document.url,
        "title": document.title,
        "retrieved_at": document.retrieved_at,
        "status": document.status,
        "content_type": document.content_type,
        "checksum": document.checksum,
        "byte_count": document.byte_count,
        "text": text,
        "truncated": len(document.text) > len(text),
    }


def _register(registry: ToolRegistryV16, spec: ToolSpec, executor) -> None:
    try:
        registry.register(spec, executor)
    except ValueError:
        # Installation is idempotent for long-lived runtimes.
        pass


def install_v16_capabilities(registry: ToolRegistryV16 | None = None) -> dict[str, Any]:
    global _INSTALLED
    target = registry or CANONICAL_TOOL_REGISTRY_V16

    _register(
        target,
        ToolSpec(
            name="file.upload",
            capability="filesystem.managed_upload",
            description="Store a user-selected file in the managed JARVIS file service.",
            risk=ToolRisk.LOCAL_WRITE,
            input_schema={"filename": "string", "content": "bytes", "workspace": "string"},
            output_schema={"file_id": "string", "sha256": "string"},
            timeout_seconds=60,
            idempotent=False,
        ),
        MANAGED_FILE_SERVICE_V16.ingest_bytes,
    )
    _register(
        target,
        ToolSpec(
            name="file.list",
            capability="filesystem.managed_read",
            description="List managed files without granting arbitrary filesystem access.",
            risk=ToolRisk.READ,
            input_schema={"workspace": "string|null", "limit": "integer"},
        ),
        MANAGED_FILE_SERVICE_V16.list_files,
    )
    _register(
        target,
        ToolSpec(
            name="file.search",
            capability="filesystem.managed_search",
            description="Search filenames and safely extracted document text.",
            risk=ToolRisk.READ,
            input_schema={"query": "string", "workspace": "string|null", "limit": "integer"},
        ),
        MANAGED_FILE_SERVICE_V16.search,
    )
    _register(
        target,
        ToolSpec(
            name="file.read_text",
            capability="filesystem.managed_read",
            description="Read bounded extracted text for a managed file_id.",
            risk=ToolRisk.READ,
            input_schema={"file_id": "string", "max_chars": "integer"},
        ),
        MANAGED_FILE_SERVICE_V16.extracted_text,
    )
    _register(
        target,
        ToolSpec(
            name="artifact.create",
            capability="artifact.local_create",
            description="Create and reopen-verify XLSX, CSV, DOCX, PPTX, PDF, Markdown, JSON or text artifacts.",
            risk=ToolRisk.LOCAL_WRITE,
            input_schema={"kind": "string", "filename": "string", "specification": "object", "workspace": "string"},
            output_schema={"verification": "object", "file_registration": "object"},
            timeout_seconds=120,
            idempotent=False,
        ),
        ARTIFACT_SERVICE_V16.create,
    )
    _register(
        target,
        ToolSpec(
            name="workspace.create_project",
            capability="workspace.local_write",
            description="Create a persistent JARVIS project workspace.",
            risk=ToolRisk.LOCAL_WRITE,
            input_schema={"name": "string", "parent_kind": "string", "metadata": "object"},
            idempotent=False,
        ),
        WORKSPACE_SERVICE_V16.create_project,
    )
    _register(
        target,
        ToolSpec(
            name="workspace.list",
            capability="workspace.read",
            description="List canonical workspaces and projects.",
            risk=ToolRisk.READ,
            input_schema={"kind": "string|null"},
        ),
        WORKSPACE_SERVICE_V16.list,
    )
    _register(
        target,
        ToolSpec(
            name="workspace.attach_file",
            capability="workspace.local_write",
            description="Attach a managed file_id to a workspace or project.",
            risk=ToolRisk.LOCAL_WRITE,
            input_schema={"workspace_id": "string", "file_id": "string"},
            idempotent=True,
        ),
        WORKSPACE_SERVICE_V16.attach_file,
    )
    _register(
        target,
        ToolSpec(
            name="web.fetch_public",
            capability="network.public_read",
            description="Read a public HTTP/HTTPS page through the existing SSRF-governed research retriever.",
            risk=ToolRisk.READ,
            input_schema={"url": "string", "max_chars": "integer"},
            output_schema={"url": "string", "title": "string", "text": "string", "checksum": "string"},
            timeout_seconds=30,
        ),
        _web_fetch,
    )

    legacy = install_legacy_tool_metadata(target)
    _INSTALLED = True
    return {
        "success": True,
        "version": "16.0",
        "service": "JARVIS_V16_CAPABILITY_REGISTRY",
        "installed": True,
        "legacy_metadata_installed": legacy.get("installed", 0),
        "registry": target.inventory(),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def status() -> dict[str, Any]:
    return {
        "success": True,
        "version": "16.0",
        "service": "JARVIS_V16_CAPABILITY_REGISTRY",
        "installed": _INSTALLED,
        "file_service": MANAGED_FILE_SERVICE_V16.status(),
        "artifact_service": ARTIFACT_SERVICE_V16.status(),
        "workspace_service": WORKSPACE_SERVICE_V16.status(),
        "registry": CANONICAL_TOOL_REGISTRY_V16.inventory(),
        "consequential_actions_approval_gated": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["install_v16_capabilities", "status"]
