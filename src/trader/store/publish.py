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
    errors = []
    for _ in range(attempts):
        _git(repo, "fetch", "--quiet", "origin", branch)
        _git(repo, *AUTHOR, "rebase", "--quiet", f"origin/{branch}")
        problems = check(repo, f"origin/{branch}", "HEAD", data_only=True)
        if problems:
            raise StoreError("refusing to push: " + "; ".join(problems))
        pushed = _run(repo, "push", "--quiet", "origin", f"HEAD:{branch}")
        if pushed.returncode == 0:
            return _git(repo, "rev-parse", "HEAD").strip()
        errors.append(pushed.stderr.strip())
    raise StoreError(f"push to {branch} rejected {attempts} times: {errors[-1]}")


def read_from_branch(repo: Path | str, branch: str, path: str) -> bytes | None:
    """One file from a branch on GitHub (e.g. Claude's review), or None if it is not there."""
    repo = Path(repo)
    if _run(repo, "fetch", "--quiet", "origin", branch).returncode != 0:
        return None
    r = subprocess.run(["git", "-C", str(repo), "show", f"FETCH_HEAD:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _git(repo: Path, *args: str) -> str:
    r = _run(repo, *args)
    if r.returncode != 0:
        raise StoreError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout
