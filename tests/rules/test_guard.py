"""The commit check: data files only grow, and the daily run touches only data/."""

from __future__ import annotations

import subprocess

import pytest

from trader.store.guard import check


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def commit(repo, files: dict, delete=()):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for name in delete:
        (repo / name).unlink()
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    commit(tmp_path, {"data/RECORD_START": "", "data/notebook/2026.jsonl": "one\n", "src/a.py": "x=1\n"})
    return tmp_path


def test_adding_and_appending_pass(repo):
    base = commit(repo, {})
    head = commit(repo, {"data/notebook/2026.jsonl": "one\ntwo\n", "data/books/2026.jsonl": "b\n"})
    assert check(repo, base, head) == []
    assert check(repo, base, head, data_only=True) == []


@pytest.mark.parametrize(
    "files,delete,expected",
    [
        ({"data/notebook/2026.jsonl": "ONE\n"}, (), "existing content was changed"),
        ({"data/notebook/2026.jsonl": "zero\none\n"}, (), "existing content was changed"),
        ({}, ("data/notebook/2026.jsonl",), "deleted"),
    ],
)
def test_changing_or_removing_data_fails(repo, files, delete, expected):
    base = commit(repo, {})
    head = commit(repo, files, delete)
    problems = check(repo, base, head)
    assert len(problems) == 1 and expected in problems[0]


def test_code_may_change_but_not_in_a_daily_run(repo):
    base = commit(repo, {})
    head = commit(repo, {"src/a.py": "x=2\n", "data/notebook/2026.jsonl": "one\ntwo\n"})
    assert check(repo, base, head) == []
    assert check(repo, base, head, data_only=True) == ["src/a.py: changed outside data/"]


def test_before_the_record_starts_data_is_practice(tmp_path):
    git(tmp_path, "init", "-q")
    base = commit(tmp_path, {"data/notebook/2026.jsonl": "practice\n"})
    head = commit(tmp_path, {}, delete=("data/notebook/2026.jsonl",))
    assert check(tmp_path, base, head) == []
