"""Checks a range of commits against the data/ rules.

    python3 src/trader/store/guard.py BASE HEAD [--data-only]

Rules:
- Under data/, a commit may add files or append lines to the end of existing
  files. Nothing is changed, removed or renamed. This applies once the
  permanent record has started (data/RECORD_START exists at BASE). Before
  that, data/ is practice and may be reset.
- With --data-only (used by the daily run before it pushes), nothing outside
  data/ may change at all.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RECORD_START = "data/RECORD_START"


def check(repo: Path | str, base: str, head: str, data_only: bool = False) -> list[str]:
    repo = Path(repo)
    problems = []
    record_started = _exists_at(repo, base, RECORD_START)
    for status, path in _changes(repo, base, head):
        if not path.startswith("data/"):
            if data_only:
                problems.append(f"{path}: changed outside data/")
            continue
        if not record_started or status == "A":
            continue
        if status == "M":
            old, new = _show(repo, base, path), _show(repo, head, path)
            if old and not old.endswith(b"\n"):
                problems.append(f"{path}: old version does not end in a line break")
            elif not new.startswith(old):
                problems.append(f"{path}: existing content was changed")
        else:
            problems.append(f"{path}: {_VERBS.get(status[0], 'changed')}; data files only grow")
    return problems


_VERBS = {"D": "deleted", "R": "renamed", "T": "changed type", "C": "copied"}


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def _changes(repo: Path, base: str, head: str) -> list[tuple[str, str]]:
    out = _git(repo, "diff", "--name-status", "--no-renames", "-z", base, head).split(b"\0")
    fields = [f.decode() for f in out if f]
    return list(zip(fields[0::2], fields[1::2]))


def _show(repo: Path, rev: str, path: str) -> bytes:
    return _git(repo, "show", f"{rev}:{path}")


def _exists_at(repo: Path, rev: str, path: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{rev}:{path}"], capture_output=True
    ).returncode == 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    found = check(Path.cwd(), args[0], args[1], data_only="--data-only" in sys.argv)
    for p in found:
        print(p)
    sys.exit(1 if found else 0)
