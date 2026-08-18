"""Parse every project-owned Python file without importing or modifying it."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".venv", ".venv-new", "__pycache__"}


def main() -> int:
    files = [
        path
        for path in ROOT.rglob("*.py")
        if not EXCLUDED_PARTS.intersection(path.parts)
    ]
    errors = []

    for path in files:
        try:
            ast.parse(
                path.read_text(encoding="utf-8-sig"),
                filename=str(path),
            )
        except (OSError, SyntaxError, UnicodeError) as error:
            errors.append((path, error))

    print(f"AST files checked: {len(files)}")
    for path, error in errors:
        print(f"ERROR {path.relative_to(ROOT)}: {error}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

