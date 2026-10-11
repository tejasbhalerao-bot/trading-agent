"""Commits what the run added under data/ and pushes it. Refuses anything else."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .core import StoreError
from .guard import check

AUTHOR = ["-c", "user.name=trader-run", "-c", "user.email=trader-run@users.noreply.github.com"]


def publish(repo: Path | str, message: str, branch: str = "main", attempts: int = 3) -> str:
    """Returns the pushed commit, or "" if the run added nothing."""
    repo = Path(repo)
    _git(repo, "add", "--all", "data/")
    if _run(repo, "diff", "--cached", "--quiet").returncode == 0:
        return ""
    if _run(repo, "diff", "--quiet").returncode != 0:
        raise StoreError("files outside data/ were modified during the run; refusing to publish")
    _git(repo, *AUTHOR, "commit", "--quiet", "-m", message)
    for _ in range(attempts):
        _git(repo, "fetch", "--quiet", "origin", branch)
        _git(repo, *AUTHOR, "rebase", "--quiet", f"origin/{branch}")
        problems = check(repo, f"origin/{branch}", "HEAD", data_only=True)
        if problems:
            raise StoreError("refusing to push: " + "; ".join(problems))
        if _run(repo, "push", "--quiet", "origin", f"HEAD:{branch}").returncode == 0:
            return _git(repo, "rev-parse", "HEAD").strip()
    raise StoreError(f"push to {branch} rejected {attempts} times")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _git(repo: Path, *args: str) -> str:
    r = _run(repo, *args)
    if r.returncode != 0:
        raise StoreError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout
