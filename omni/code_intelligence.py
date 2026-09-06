"""Bounded, read-only repository code intelligence for JARVIS V7.

The index parses Python source only. It never imports target modules, executes
repository code, edits files, or follows paths outside the repository root.
"""

from __future__ import annotations

import ast
import hashlib
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = ("agents", "omni", "tools", "workstation", "scripts")
EXCLUDED_NAMES = {
    ".git", ".venv", ".venv-new", ".venv-fyers", ".venv-nautilus",
    "__pycache__", "node_modules", "data", ".jarvis-dev",
}


@dataclass(frozen=True)
class SourceRecord:
    path: str
    sha256: str
    lines: int
    functions: tuple[str, ...]
    async_functions: tuple[str, ...]
    classes: tuple[str, ...]
    imports: tuple[str, ...]
    calls: tuple[str, ...]
    parse_status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def _source_files(roots: Iterable[str] = DEFAULT_ROOTS, max_files: int = 2_500) -> list[Path]:
    found: list[Path] = []
    for name in roots:
        base = (ROOT / str(name)).resolve()
        if not _inside_root(base) or not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in EXCLUDED_NAMES for part in path.parts) or not _inside_root(path):
                continue
            found.append(path)
            if len(found) >= max_files:
                return sorted(found)
    return sorted(found)


def _call_name(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if not isinstance(target, ast.Attribute):
        return None
    pieces: list[str] = [target.attr]
    value = target.value
    while isinstance(value, ast.Attribute):
        pieces.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        pieces.append(value.id)
    return ".".join(reversed(pieces))


def analyze_file(path: Path) -> SourceRecord:
    path = path.resolve()
    if not _inside_root(path) or path.suffix.lower() != ".py":
        raise ValueError("Code intelligence accepts Python files inside the JARVIS repository only.")
    relative = path.relative_to(ROOT).as_posix()
    try:
        raw = path.read_bytes()
        source = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return SourceRecord(relative, "", 0, (), (), (), (), (), "READ_ERROR", type(exc).__name__)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return SourceRecord(
            relative, digest, source.count("\n") + 1, (), (), (), (), (),
            "SYNTAX_ERROR", f"line {exc.lineno}: {exc.msg}"[:240],
        )
    functions = sorted({node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)})
    async_functions = sorted({node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)})
    classes = sorted({node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)})
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(str(node.module))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name:
                calls.add(name)
    return SourceRecord(
        relative, digest, source.count("\n") + 1,
        tuple(functions), tuple(async_functions), tuple(classes),
        tuple(sorted(imports)), tuple(sorted(calls))[:500], "OK", None,
    )


class CodeIntelligenceIndex:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[SourceRecord] = []
        self._built = False

    def build(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._built and not force:
                return {"success": True, "files": len(self._records), "cached": True}
        records = [analyze_file(path) for path in _source_files()]
        with self._lock:
            self._records = records
            self._built = True
        return {"success": True, "files": len(records), "cached": False}

    def _records_copy(self) -> list[SourceRecord]:
        if not self._built:
            self.build()
        with self._lock:
            return list(self._records)

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        value = " ".join(str(query or "").lower().split())
        if not value:
            return []
        terms = [term for term in value.replace(".", " ").replace("_", " ").split() if term]
        scored: list[tuple[int, SourceRecord]] = []
        for record in self._records_copy():
            haystack = " ".join(
                [record.path, *record.functions, *record.async_functions, *record.classes, *record.imports]
            ).lower().replace("_", " ").replace(".", " ")
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].path))
        return [
            {"score": score, **record.to_dict()}
            for score, record in scored[: max(1, min(int(limit), 100))]
        ]

    def dependency_edges(self, limit: int = 500) -> list[dict[str, str]]:
        records = self._records_copy()
        local_modules = {
            record.path[:-3].replace("/", "."): record.path
            for record in records if record.path.endswith(".py")
        }
        edges: list[dict[str, str]] = []
        for record in records:
            for imported in record.imports:
                target = local_modules.get(imported)
                if target is None:
                    target = next(
                        (path for module, path in local_modules.items() if module.startswith(imported + ".")),
                        None,
                    )
                if target:
                    edges.append({"source": record.path, "target": target, "import": imported})
                if len(edges) >= max(1, min(int(limit), 5000)):
                    return edges
        return edges

    def snapshot(self, *, include_records: bool = False) -> dict[str, Any]:
        records = self._records_copy()
        errors = [row for row in records if row.parse_status != "OK"]
        result: dict[str, Any] = {
            "success": True,
            "version": "7.0",
            "files": len(records),
            "lines": sum(row.lines for row in records),
            "functions": sum(len(row.functions) + len(row.async_functions) for row in records),
            "classes": sum(len(row.classes) for row in records),
            "parse_errors": len(errors),
            "error_files": [row.to_dict() for row in errors[:50]],
            "dependency_edges": len(self.dependency_edges()),
            "read_only": True,
            "code_execution": False,
            "automatic_editing": False,
        }
        if include_records:
            result["records"] = [row.to_dict() for row in records]
        return result


CODE_INTELLIGENCE = CodeIntelligenceIndex()


__all__ = ["CODE_INTELLIGENCE", "CodeIntelligenceIndex", "SourceRecord", "analyze_file"]
