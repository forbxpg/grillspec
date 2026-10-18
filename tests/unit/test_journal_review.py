"""Fixes from the session-memory final review."""

from __future__ import annotations

import base64
import sqlite3
import subprocess
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.config import load_config
from grillspec.journal import Journal, brief, redact
from grillspec.state import compute_status
from support import GATED_ID, REPO, phase_project

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return phase_project(tmp_path, "spec")


def test_index_rebuilt_after_fts_arrives(tmp_path: Path):  # I1
    old = Journal(tmp_path, fts=False)
    _ = old.add("discovery", "the needle was written without an index", change=None)
    new = Journal(tmp_path)
    _ = new.add("todo", "a later write builds the index", change=None)
    found = new.search("needle", 10)
    if not new.fts:
        pytest.skip("this Python's SQLite has no FTS5")
    assert [e.text for e in found] == ["the needle was written without an index"]
    entry = found[0]
    new.forget(entry.id)
    with closing(sqlite3.connect(new.path)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        con.execute("INSERT INTO entries_fts(entries_fts) VALUES ('integrity-check')")


def test_note_takes_unquoted_words(spec: Path):  # I2
    assert main(["note", "discovery", "--", "retries", "use", "backoff"]) == 0
    assert Journal(spec).recent(1)[0].text == "retries use backoff"


def test_router_and_hint_quote_the_note():  # I2
    router = (REPO / "skills/using-grillspec/SKILL.md").read_text(encoding="utf-8")
    assert 'grillspec note handoff -- "' in router


def test_worktree_writes_to_the_main_journal(
    spec: Path, monkeypatch: pytest.MonkeyPatch
):  # I3
    def git(*args: str, cwd: Path) -> None:
        _ = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    git("init", "-q", cwd=spec)
    git(
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "i",
        cwd=spec,
    )
    tree = spec / ".worktrees" / "task"
    git("worktree", "add", "-q", str(tree), cwd=spec)
    (tree / ".grillspec").mkdir()
    (tree / ".grillspec" / "config.toml").write_text(
        (spec / ".grillspec" / "config.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tree)
    assert main(["note", "handoff", "--", "written in the worktree"]) == 0
    assert [e.text for e in Journal(spec).recent(5)] == ["written in the worktree"]
    assert not (tree / ".grillspec" / "journal").exists()


@pytest.mark.parametrize(
    "prose",
    [
        "task-dependencies are tracked",
        "risk-assessment first",
        "flask-sqlalchemy pinned",
        "token: the cap is per session",
        "BRIEF_TOKENS = 1500",
        "max_tokens=4096 for the judge",
        "see https://example.com/docs/token-auth",
    ],
)
def test_ordinary_prose_is_kept(prose: str):  # I4
    assert redact(prose) == prose


def test_grillspec_events_are_not_redacted(spec: Path):  # I4
    assert main(["new", "rotate-api-token", "--switch"]) == 0
    assert "rotate-api-token: change started" in [
        e.text for e in Journal(spec).recent(5)
    ]


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ('password="correct horse battery"', "horse"),
        ('{"password": "hunter2", "api_key": "abc123xyz"}', "hunter2"),
        ('{"password": "hunter2", "api_key": "abc123xyz"}', "abc123xyz"),
        ("postgres://admin:hunter2@db.internal/app", "hunter2"),
        (
            "Authorization: Basic " + base64.b64encode(b"admin:hunter2").decode(),
            "YWRtaW46",
        ),
        ("пароль: hunter2", "hunter2"),
        ("токен = abc123def456", "abc123def456"),
    ],
)
def test_more_secrets_are_caught(text: str, secret: str):  # I5
    assert secret not in redact(text)


def test_forget_leaves_no_trace(tmp_path: Path):  # I5
    journal = Journal(tmp_path)
    entry = journal.add("discovery", "codename bluefalcon rollout", change=None)
    for n in range(20):
        _ = journal.add("event", f"padding {n}", change=None)
    journal.forget(entry.id)
    for name in ("memory.db", "memory.db-wal"):
        path = journal.folder / name
        if path.exists():
            assert b"bluefalcon" not in path.read_bytes()


def test_resolved_notes_leave_the_brief(spec: Path):  # I6
    journal = Journal(spec)
    blocker = journal.add("blocker", "staging token expired", change=GATED_ID)
    _ = journal.add("todo", "document the backoff", change=GATED_ID)
    assert main(["recall", "--resolve", str(blocker.id)]) == 0
    text = brief(spec, compute_status(spec, load_config(spec).config))
    assert "staging token expired" not in text.split("Recent:")[0]
    assert "document the backoff" in text
    router = (REPO / "skills/using-grillspec/SKILL.md").read_text(encoding="utf-8")
    assert "--resolve" in router


def test_reads_do_not_take_the_write_lock(spec: Path):  # M1
    journal = Journal(spec)
    _ = journal.add("todo", "x", change=None)
    with closing(sqlite3.connect(journal.path, isolation_level=None)) as holder:
        _ = holder.execute("BEGIN IMMEDIATE")
        assert [e.text for e in Journal(spec).recent(5)] == ["x"]
        holder.execute("ROLLBACK")


@pytest.mark.parametrize("fts", [True, False], ids=["fts5", "like"])
def test_prefix_and_yo_search(tmp_path: Path, fts: bool):  # ruff: ignore[boolean-type-hint-positional-argument]
    journal = Journal(tmp_path, fts=fts)
    _ = journal.add("discovery", "ретраи с экспоненциальной задержкой", change=None)  # ruff: ignore[ambiguous-unicode-character-string]
    _ = journal.add("todo", "купить ёлку", change=None)
    assert len(journal.search("задерж", 10)) == 1
    assert len(journal.search("елку", 10)) == 1


def test_gigacode_context_asks_for_a_handoff():  # M7
    context = (REPO / "gigacode-context.md").read_text(encoding="utf-8")
    assert "note handoff" in context
