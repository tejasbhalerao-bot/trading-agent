"""Who may write where under data/, and the rule that files only grow."""

from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path
from typing import Iterable

import yaml

from .history import History

REPO = Path(__file__).resolve().parents[3]

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
    "reports": "report",  # the daily report: written for you, read by nothing in the system
}

FOLDER_OF = {job: folder for folder, job in OWNERS.items()}


def month_file(d, ext: str) -> str:
    """Every growing data file holds one month (constraints.md: GitHub blocks files over 100 MB)."""
    return f"{d.year:04d}-{d.month:02d}.{ext}"


class StoreError(Exception):
    """A write that breaks a store rule. Never caught and ignored."""


class Store:
    """data/ under `root`. `history_from` reads market history from another root's data/
    instead (a practice replay reads the repo's real history but writes elsewhere)."""

    def __init__(self, root: Path | str, history_from: Path | str | None = None, config_dir: Path | str | None = None):
        self.repo_root = Path(root).resolve()
        self.data = self.repo_root / "data"
        self.history_dir = (Path(history_from).resolve() / "data" if history_from else self.data) / "history"
        self.config_dir = Path(config_dir) if config_dir else REPO / "config"
        self._seen: dict[Path, tuple[int, list[dict]]] = {}
        self._all: dict[str, tuple[list[dict], dict[str, int]]] = {}

    def history(self) -> History:
        return History.load(self.history_dir)

    def config(self, name: str) -> dict:
        with open(self.config_dir / f"{name}.yaml") as f:
            return yaml.safe_load(f)

    def checklists(self) -> dict[str, dict]:
        out = {}
        for path in sorted((self.config_dir / "checklists").glob("*.yaml")):
            with open(path) as f:
                c = yaml.safe_load(f)
            out[c["id"]] = c
        return out

    def records(self, relpath: str) -> list[dict]:
        """All records in a .jsonl file. Files only grow, so each call reads only the new bytes."""
        path = _inside(self.data, relpath)
        if not path.exists():
            return []
        offset, records = self._seen.get(path, (0, []))
        with open(path, "rb") as f:
            f.seek(offset)
            new = f.read()
        records = records + [json.loads(line) for line in new.decode("utf-8").splitlines() if line]
        self._seen[path] = (offset + len(new), records)
        return records

    def records_all(self, folder: str) -> list[dict]:
        """Every record in every monthly .jsonl file of a folder, oldest month first.

        Files only grow, so the combined list is kept and extended with new lines only.
        Callers must treat the returned list and its records as read-only.
        """
        base = self.data / folder
        if not base.exists():
            return []
        combined, counts = self._all.get(folder, ([], {}))
        paths = sorted(str(p.relative_to(self.data)) for p in base.glob("*.jsonl"))
        for i, rel in enumerate(paths):
            recs = self.records(rel)
            seen = counts.get(rel, 0)
            if len(recs) > seen:
                if i < len(paths) - 1 and any(counts.get(p, 0) for p in paths[i + 1:]):
                    combined, counts = [], {}      # an older month grew after newer ones: rebuild in order
                    return self._rebuild(folder, paths)
                combined.extend(recs[seen:])
                counts[rel] = len(recs)
        self._all[folder] = (combined, counts)
        return combined

    def _rebuild(self, folder: str, paths: list[str]) -> list[dict]:
        combined, counts = [], {}
        for rel in paths:
            recs = self.records(rel)
            combined.extend(recs)
            counts[rel] = len(recs)
        self._all[folder] = (combined, counts)
        return combined

    def code_version(self) -> str:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else "unknown"

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

    def append_records(self, relpath: str, records: Iterable[dict]) -> Path:
        return self.append_lines(relpath, [json.dumps(r, sort_keys=True, separators=(",", ":"), default=str) for r in records])

    def append_csv(self, relpath: str, fields: list[str], rows: Iterable[dict]) -> Path:
        path = _inside(self.base, relpath)
        new = not path.exists() or path.stat().st_size == 0
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
        if new:
            w.writeheader()
        for row in rows:
            w.writerow(row)
        return self.append_lines(relpath, buf.getvalue().splitlines())

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
