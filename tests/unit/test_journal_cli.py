"""Tests for notes, events, recall and the resume brief (spec JR-R2, JR-R4)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.config import load_config
from grillspec.journal import Journal
from grillspec.journal._brief import brief
from grillspec.state import compute_status
from grillspec.tokens import estimate
from support import GATED_ID, phase_project, write

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return phase_project(tmp_path, "spec")


def _texts(root: Path) -> list[str]:
    return [entry.text for entry in Journal(root).recent(100)]


def test_approval_is_recorded(spec: Path):  # JR-4
    assert main(["approve", "spec"]) == 0
    assert f"{GATED_ID}: spec approved" in _texts(spec)
    (event,) = [e for e in Journal(spec).recent(10) if e.text.endswith("spec approved")]
    assert event.kind == "event"
    assert event.change == GATED_ID


def test_new_change_is_recorded(spec: Path):
    assert main(["new", "add-other", "--switch"]) == 0
    assert any(t.startswith("add-other") and "started" in t for t in _texts(spec))


def test_broken_store_never_breaks_a_command(
    spec: Path, capsys: pytest.CaptureFixture[str]
):  # JR-5
    folder = spec / ".grillspec" / "journal"
    folder.mkdir(parents=True)
    _ = (folder / "memory.db").write_bytes(b"this is not a database" * 100)
    _ = capsys.readouterr()
    assert main(["approve", "spec"]) == 0
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert err.startswith("grillspec: journal: ")


def test_note_command(spec: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["note", "handoff", "--", "next: wire the retry queue"]) == 0
    assert "next: wire the retry queue" in capsys.readouterr().out
    (entry,) = Journal(spec).recent(1)
    assert entry.kind == "handoff"
    assert entry.change == GATED_ID


@pytest.mark.parametrize("text", ["two\nlines", "x" * 501, "   "])
def test_note_refuses_bad_text(
    spec: Path, capsys: pytest.CaptureFixture[str], text: str
):
    assert main(["note", "todo", "--", text]) == 1
    assert capsys.readouterr().err.startswith("grillspec: ")
    assert _texts(spec) == []


def test_note_outside_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["note", "todo", "--", "x"]) == 1
    assert "not set up" in capsys.readouterr().err


def test_recall_search_pin_forget(spec: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["note", "discovery", "--", "the CI runner caches uv"]) == 0
    assert main(["note", "todo", "--", "document the cache expiry"]) == 0
    _ = capsys.readouterr()
    assert main(["recall", "cache", "expiry"]) == 0
    out = capsys.readouterr().out
    assert "document the cache expiry" in out
    assert "CI runner" not in out
    entry_id = Journal(spec).search("runner", 1)[0].id
    assert main(["recall", "--pin", str(entry_id)]) == 0
    assert [e.id for e in Journal(spec).pinned()] == [entry_id]
    assert main(["recall", "--unpin", str(entry_id)]) == 0
    assert Journal(spec).pinned() == []
    assert main(["recall", "--forget", str(entry_id)]) == 0
    assert Journal(spec).get(entry_id) is None
    _ = capsys.readouterr()
    assert main(["recall", "--json", "cache"]) == 0
    data = cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))
    assert [d["text"] for d in data] == ["document the cache expiry"]


@pytest.mark.usefixtures("spec")
def test_recall_unknown_id(capsys: pytest.CaptureFixture[str]):
    assert main(["recall", "--pin", "999"]) == 1
    assert "no entry 999" in capsys.readouterr().err


def _brief(root: Path) -> str:
    return brief(root, compute_status(root, load_config(root).config))


def test_brief_under_its_cap(spec: Path):  # JR-7
    journal = Journal(spec)
    for n in range(500):
        kind = ("event", "discovery", "todo", "blocker", "handoff")[n % 5]
        _ = journal.add(kind, f"entry {n} " + "word " * (n % 40), change=GATED_ID)
    text = _brief(spec)
    assert estimate(text) <= 1500
    stored = {e.text for e in journal.recent(1000)}
    for line in text.splitlines():
        if line.startswith("- "):
            body = line.split("] ", 1)[1]
            assert body in stored  # whole entries only


def test_pinned_come_first(spec: Path):  # JR-8
    journal = Journal(spec)
    old = journal.add(
        "discovery", "the old pinned fact", change=None, ts="2026-01-01T00:00:00Z"
    )
    for n in range(30):
        _ = journal.add("event", f"newer event {n}", change=GATED_ID)
    journal.set_pinned(old.id, flag=True)
    text = _brief(spec)
    assert text.index("the old pinned fact") < text.index("newer event 29")


def test_brief_names_change_phase_and_latest_handoff(spec: Path):
    journal = Journal(spec)
    _ = journal.add("handoff", "first handoff", change=GATED_ID)
    _ = journal.add("handoff", "latest handoff: next is the plan", change=GATED_ID)
    text = _brief(spec)
    assert text.splitlines()[0] == f"grillspec memory: {GATED_ID} in the spec phase"
    assert "latest handoff: next is the plan" in text
    assert "first handoff" not in text


def test_brief_cli_and_empty_journal(spec: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["recall", "--brief"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"grillspec memory: {GATED_ID} in the spec phase")
    assert "nothing recorded yet" in out.lower()
    assert not (spec / ".grillspec" / "journal").exists()


def test_exec_done_records_the_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    root = phase_project(tmp_path, "execute")
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@t"],
        ["config", "user.name", "t"],
    ):
        _ = subprocess.run(["git", "-C", str(root), *args], check=True)
    write(root / ".gitignore", ".grillspec/\n")
    _ = subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    _ = subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert main(["exec", "done", "1.1", base, "--", sys.executable, "-c", "pass"]) == 0
    assert f"{GATED_ID}: task 1.1 done" in _texts(root)
