"""Jobs talk only through data/ and schema/. Watchers only read.

Spec: "the next job reads its work from the notebook rather than from Decide",
and "Watchers are not jobs". If one job could call another's code, it could
recompute what the record already says it saw.
"""

from __future__ import annotations

import ast

from ._source import JOBS, imported_trader_packages, modules

SHARED = {"schema", "store"}


def test_jobs_import_only_themselves_and_shared_packages():
    offences = []
    for package, path, tree in modules():
        if package not in JOBS:
            continue
        for other in imported_trader_packages(tree, package) - SHARED - {package}:
            offences.append(f"{path.name} in {package}/ imports {other}/")
    assert not offences, offences


def test_shared_packages_import_no_job():
    offences = []
    for package, path, tree in modules():
        if package not in SHARED:
            continue
        for other in imported_trader_packages(tree, package) - SHARED:
            offences.append(f"{package}/{path.name} imports {other}/")
    assert not offences, offences


def test_report_never_asks_for_a_writer():
    offences = []
    for package, path, tree in modules():
        if package != "report":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"writer", "publish"}:
                offences.append(f"report/{path.name}:{node.lineno}")
        if {"store"} & imported_trader_packages(tree, package) and "publish" in path.read_text():
            offences.append(f"report/{path.name} references publish")
    assert not offences, offences
