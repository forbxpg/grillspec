"""Tests for ``grillspec exec`` (spec S7A-R1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from grillspec.cli import main
from support import write

ID = "add-x"
PLAN = """# add-x — plan

**Spec:** openspec/changes/add-x/proposal.md

## Global Constraints

- stdlib only

## 1. Core

- [ ] 1.1 First — verify: pytest -k first passes

Covers: — · Test: none: glue

Files: create a.py

1. Do the first thing.

- [ ] 1.2 Second — verify: pytest -k second passes

Covers: — · Test: none: glue

Files: create b.py

1. Do the second thing.

## 2. Wiring

- [ ] 2.1 Third — verify: it runs

Covers: — · Test: none: glue

Files: modify c.py

1. Wire it.
"""


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _ = _git(tmp_path, "init", "-q")
    _ = _git(tmp_path, "config", "user.email", "t@t")
    _ = _git(tmp_path, "config", "user.name", "t")
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    write(tmp_path / f"openspec/changes/{ID}/tasks.md", PLAN)
    write(tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{ID}"}}\n')
    write(tmp_path / ".gitignore", ".grillspec/state.json\n")
    _ = _git(tmp_path, "add", "-A")
    _ = _git(tmp_path, "commit", "-qm", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _tasks(root: Path) -> str:
    return (root / f"openspec/changes/{ID}/tasks.md").read_text(encoding="utf-8")


def test_workspace(project: Path, capsys: pytest.CaptureFixture[str]):  # EX-1
    assert main(["exec", "workspace"]) == 0
    path = capsys.readouterr().out.strip()
    folder = project / ".grillspec/exec" / ID
    assert path == folder.resolve().as_posix()
    assert (folder / ".gitignore").read_text(encoding="utf-8") == "*\n"
    ledger = (folder / "progress.md").read_text(encoding="utf-8")
    assert ledger.startswith(f"# grillspec ledger — change: {ID}\n")
    assert not _git(project, "status", "--porcelain")


def test_start_writes_brief(project: Path, capsys: pytest.CaptureFixture[str]):  # EX-2
    assert main(["exec", "start", "1.2"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("brief: ")
    assert lines[1] == f"base: {_git(project, 'rev-parse', 'HEAD')}"
    brief = (project / ".grillspec/exec" / ID / "task-1.2-brief.md").read_text(
        encoding="utf-8"
    )
    assert "## Global Constraints" in brief
    assert "1.2 Second" in brief
    assert "Do the second thing." in brief
    assert "1.1 First" not in brief
    assert "2.1 Third" not in brief


def test_done_ticks_on_success_only(  # EX-3
    project: Path, capsys: pytest.CaptureFixture[str]
):
    base = _git(project, "rev-parse", "HEAD")
    ok = [sys.executable, "-c", "print('fine')"]
    assert main(["exec", "done", "1.2", base, "--", *ok]) == 0
    assert "fine" in capsys.readouterr().out
    assert "- [x] 1.2 Second" in _tasks(project)
    assert "- [ ] 1.1 First" in _tasks(project)
    bad = [sys.executable, "-c", "raise SystemExit(1)"]
    assert main(["exec", "done", "2.1", base, "--", *bad]) == 1
    assert "- [ ] 2.1 Third" in _tasks(project)
    ledger = (project / ".grillspec/exec" / ID / "progress.md").read_text(
        encoding="utf-8"
    )
    assert ledger.count("Task 1.2: complete") == 1
    assert "Task 2.1" not in ledger


def test_review_package_guards(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # EX-4
    base = _git(project, "rev-parse", "HEAD")
    assert main(["exec", "review-package", base]) == 3
    write(project / "a.py", "x = 1\n")
    _ = _git(project, "add", "a.py")
    _ = _git(project, "commit", "-qm", "feat: add a")
    _ = capsys.readouterr()
    assert main(["exec", "review-package", base]) == 0
    path = capsys.readouterr().out.strip()
    text = Path(path).read_text(encoding="utf-8")
    assert "feat: add a" in text
    assert "a.py" in text


def test_unknown_task(project: Path, capsys: pytest.CaptureFixture[str]):  # EX-5
    assert main(["exec", "start", "9.9"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: no task 9.9 in openspec/changes/add-x/tasks.md")
    assert err.count("\n") == 1
    assert project.is_dir()


def test_crlf_plan_ticks_and_stays_crlf(project: Path):  # Review Focus 1
    path = project / f"openspec/changes/{ID}/tasks.md"
    _ = path.write_bytes(PLAN.replace("\n", "\r\n").encode())
    base = _git(project, "rev-parse", "HEAD")
    assert main(["exec", "done", "1.1", base, "--", sys.executable, "-c", "pass"]) == 0
    data = path.read_bytes()
    assert b"- [x] 1.1 First" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_missing_command_one_line(  # Review Focus 2
    project: Path, capsys: pytest.CaptureFixture[str]
):
    base = _git(project, "rev-parse", "HEAD")
    assert main(["exec", "done", "1.1", base, "--", "no-such-command-xyz"]) == 1
    assert capsys.readouterr().err.count("\n") == 1
    assert "- [ ] 1.1 First" in _tasks(project)


def test_done_twice_is_idempotent(project: Path):  # Review Focus 3
    base = _git(project, "rev-parse", "HEAD")
    for _ in range(2):
        assert (
            main(["exec", "done", "1.1", base, "--", sys.executable, "-c", "pass"]) == 0
        )
    assert _tasks(project).count("- [x] 1.1 First") == 1


def test_not_set_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["exec", "workspace"]) == 1
    assert "not set up" in capsys.readouterr().err
