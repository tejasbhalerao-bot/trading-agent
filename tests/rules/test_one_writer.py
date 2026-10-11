"""Only store/ writes files. Every other package must go through it.

Spec: "One writer per fact" and "Your safety limits are yours". store/ can
only write inside data/, so config/ (the limits) is unwritable by code.
"""

from __future__ import annotations

import ast

from ._source import modules

WRITE_METHODS = {
    "write_text", "write_bytes", "unlink", "rmdir", "touch",
    "mkdir", "to_csv", "to_parquet", "to_json", "to_pickle", "to_excel",
}
# Path.rename/replace take one argument; str.replace takes two.
ONE_ARG_WRITE_METHODS = {"rename", "replace"}
WRITE_FUNCTIONS = {
    ("os", "remove"), ("os", "unlink"), ("os", "rename"), ("os", "replace"),
    ("os", "makedirs"), ("os", "mkdir"), ("os", "rmdir"),
}


def _offences(tree: ast.AST) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in WRITE_METHODS:
            lines.append(node.lineno)
        elif isinstance(f, ast.Attribute) and f.attr in ONE_ARG_WRITE_METHODS and len(node.args) == 1:
            lines.append(node.lineno)
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (
            (f.value.id, f.attr) in WRITE_FUNCTIONS or f.value.id == "shutil"
        ):
            lines.append(node.lineno)
        elif isinstance(f, (ast.Name, ast.Attribute)) and getattr(f, "id", getattr(f, "attr", "")) == "open":
            if _opens_for_writing(node):
                lines.append(node.lineno)
    return lines


def _opens_for_writing(call: ast.Call) -> bool:
    mode = call.args[1] if len(call.args) > 1 else None
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    if mode is None:
        return False
    if not isinstance(mode, ast.Constant) or not isinstance(mode.value, str):
        return True  # a mode we cannot read is treated as a write
    return any(c in mode.value for c in "wax+")


def test_no_package_but_store_writes_files():
    offences = [
        f"{path.relative_to(path.parents[2])}:{line}"
        for package, path, tree in modules()
        if package != "store"
        for line in _offences(tree)
    ]
    assert not offences, offences


def test_the_check_itself_catches_writes():
    sample = ast.parse(
        "open(p, 'w')\nopen(p, mode='ab')\np.write_text('x')\nos.remove(p)\nshutil.rmtree(p)\nopen(p, m)\np.replace(q)"
    )
    assert len(_offences(sample)) == 7
    assert _offences(ast.parse("open(p)\nopen(p, 'rb')\np.read_text()\ns.replace(':', '')")) == []



def test_no_package_but_store_starts_processes():
    """A shell command could write anywhere, so only store/ may run one."""
    offences = []
    for package, path, tree in modules():
        if package == "store":
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                names = [f"{node.value.id}.{node.attr}"]
            offences += [f"{path.name}:{node.lineno}" for n in names if n.split(".")[0] in {"subprocess", "pty", "multiprocessing"} or n in {"os.system", "os.popen", "os.exec", "os.spawn"}]
    assert not offences, offences
