"""Who may write where under data/, and the rule that files only grow."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Each folder under data/ has exactly one writer. This table is the single
# source of truth for "one writer per fact" (spec, Rules that bind everything).
OWNERS = {
    "raw": "fetch",  # receipts only; downloads are not kept
    "history": "clean",
    "analysis": "analyze",
    "notebook": "record",
    "books": "settle",
    "trust": "learn",
    "backtest": "backtest",
}

FOLDER_OF = {job: folder for folder, job in OWNERS.items()}


class StoreError(Exception):
    """A write that breaks a store rule. Never caught and ignored."""


class Store:
    def __init__(self, repo_root: Path | str):
        self.repo_root = Path(repo_root).resolve()
        self.data = self.repo_root / "data"

    def writer(self, job: str) -> Writer:
        if job not in FOLDER_OF:
            raise StoreError(f"{job!r} owns no folder under data/ and may not write")
        return Writer(self.data / FOLDER_OF[job])

    def read_bytes(self, relpath: str) -> bytes:
        return _inside(self.data, relpath).read_bytes()

    def read_lines(self, relpath: str) -> list[str]:
        return _inside(self.data, relpath).read_text(encoding="utf-8").splitlines()

    def exists(self, relpath: str) -> bool:
        return _inside(self.data, relpath).exists()


class Writer:
    """Write access to one folder. Can add files and append lines; nothing else."""

    def __init__(self, base: Path):
        self.base = base

    def add_file(self, relpath: str, content: bytes) -> Path:
        path = _inside(self.base, relpath)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "xb") as f:
                f.write(content)
        except FileExistsError:
            raise StoreError(f"{path} already exists; files are never replaced") from None
        return path

    def append_lines(self, relpath: str, lines: Iterable[str]) -> Path:
        lines = list(lines)
        for line in lines:
            if "\n" in line or "\r" in line:
                raise StoreError("a line may not contain a line break")
        path = _inside(self.base, relpath)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size:
            with open(path, "rb") as f:
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    raise StoreError(f"{path} does not end in a line break; refusing to append")
        with open(path, "a", encoding="utf-8") as f:
            f.writelines(line + "\n" for line in lines)
        return path


def _inside(base: Path, relpath: str) -> Path:
    path = (base / relpath).resolve()
    if path == base.resolve() or base.resolve() not in path.parents:
        raise StoreError(f"{relpath!r} is outside {base}")
    return path
