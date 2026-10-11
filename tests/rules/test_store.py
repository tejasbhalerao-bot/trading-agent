"""Each job writes only its own folder, and can only add files or append lines."""

from __future__ import annotations

import pytest

from trader.store import FOLDER_OF, OWNERS, Store, StoreError


def test_every_folder_has_exactly_one_owner():
    assert len(set(OWNERS.values())) == len(OWNERS)
    assert set(OWNERS) == {"raw", "history", "analysis", "notebook", "books", "trust", "backtest", "reports"}


def test_a_job_writes_only_its_own_folder(tmp_path):
    store = Store(tmp_path)
    store.writer("clean").append_lines("prices/2026.csv", ["a,b"])
    assert (tmp_path / "data/history/prices/2026.csv").read_text() == "a,b\n"
    for escape in ["../notebook/x", "../../config/limits.yaml", "/etc/passwd", ".", "a/../../x"]:
        with pytest.raises(StoreError):
            store.writer("clean").append_lines(escape, ["x"])


@pytest.mark.parametrize("job", ["decide", "run", "probe", ""])
def test_non_owners_get_no_writer(tmp_path, job):
    assert job not in FOLDER_OF
    with pytest.raises(StoreError):
        Store(tmp_path).writer(job)


def test_files_are_never_replaced(tmp_path):
    w = Store(tmp_path).writer("fetch")
    w.add_file("2026/receipt.json", b"{}")
    with pytest.raises(StoreError):
        w.add_file("2026/receipt.json", b"{}")


def test_append_only_adds_lines_at_the_end(tmp_path):
    store = Store(tmp_path)
    w = store.writer("record")
    w.append_lines("2026.jsonl", ["one"])
    w.append_lines("2026.jsonl", ["two", "three"])
    assert store.read_lines("notebook/2026.jsonl") == ["one", "two", "three"]
    with pytest.raises(StoreError):
        w.append_lines("2026.jsonl", ["sneaky\nextra"])


def test_refuses_to_append_to_a_file_without_a_final_line_break(tmp_path):
    path = tmp_path / "data/trust/v.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"partial")
    with pytest.raises(StoreError):
        Store(tmp_path).writer("learn").append_lines("v.jsonl", ["x"])
