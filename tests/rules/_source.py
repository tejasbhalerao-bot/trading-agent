"""Reads the source tree for the rules tests."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "trader"
JOBS = ["fetch", "clean", "analyze", "decide", "record", "settle", "learn"]


def modules():
    """Yields (package, path, tree) for every module; package is the folder under trader/."""
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC)
        package = rel.parts[0] if len(rel.parts) > 1 else rel.stem
        yield package, path, ast.parse(path.read_text(), filename=str(path))


def imported_trader_packages(tree: ast.AST, package: str) -> set[str]:
    """Top-level trader packages a module imports, resolving relative imports."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1:
                found.add(package)
                continue
            if node.level >= 2:
                names = [f"trader.{node.module}" if node.module else "trader"]
                if not node.module:
                    found.update(a.name for a in node.names)
                    continue
            else:
                names = [node.module or ""]
                if node.module == "trader":
                    found.update(a.name for a in node.names)
                    continue
        else:
            continue
        for name in names:
            parts = name.split(".")
            if parts[0] == "trader" and len(parts) > 1:
                found.add(parts[1])
    return found
