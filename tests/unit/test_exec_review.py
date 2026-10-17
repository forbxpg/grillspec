"""Fixes from the S7a final review."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from grillspec.cli import main
from support import write

ID = "add-x"
SKILLS = Path(__file__).resolve().parents[2] / "skills"
PLAN = """# add-x — plan

**Spec:** openspec/changes/add-x/proposal.md

## 1. Docs

- [ ] 1.1 Template — verify: it renders

Covers: — · Test: none: docs

Files: create docs/t.md

1. Write this template:

```markdown
## Not a heading
- not a task
```

2. Check the rendering. Expected: the heading shows.

- [ ] 1.2 Next — verify: ok

Covers: — · Test: none: glue

Files: x
"""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


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
    _ = _git(tmp_path, "add", "-A")
    _ = _git(tmp_path, "commit", "-qm", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _plan(root: Path) -> Path:
    return root / f"openspec/changes/{ID}/tasks.md"


def test_fenced_heading_does_not_cut_the_brief(project: Path):  # I1
    assert main(["exec", "start", "1.1"]) == 0
    brief = (project / ".grillspec/exec" / ID / "task-1.1-brief.md").read_text(
        encoding="utf-8"
    )
    assert "2. Check the rendering." in brief
    assert "1.2 Next" not in brief


def test_relative_command_runs_from_root(
    project: Path, monkeypatch: pytest.MonkeyPatch
):  # I2
    write(project / "tools/check.py", "raise SystemExit(0)\n")
    base = _git(project, "rev-parse", "HEAD")
    sub = project / "openspec"
    monkeypatch.chdir(sub)  # tools/check.py resolves only from the project root
    assert (
        main(["exec", "done", "1.2", base, "--", sys.executable, "tools/check.py"]) == 0
    )
    assert main(["exec", "done", "1.2", base, "--", "./missing.sh"]) == 1


def test_unstartable_command_is_one_line(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # I2
    base = _git(project, "rev-parse", "HEAD")
    bogus = project / "not-executable.txt"
    write(bogus, "hello\n")
    assert main(["exec", "done", "1.2", base, "--", str(bogus)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: ")
    assert err.count("\n") == 1
    assert "- [ ] 1.2 Next" in _plan(project).read_text(encoding="utf-8")


def test_bom_kept_and_only_the_box_changes(project: Path):  # Minor: BOM, byte-exact
    original = ("﻿" + PLAN.replace("\n", "\r\n")).encode()
    _ = _plan(project).write_bytes(original)
    base = _git(project, "rev-parse", "HEAD")
    assert main(["exec", "done", "1.2", base, "--", sys.executable, "-c", "pass"]) == 0
    assert _plan(project).read_bytes() == original.replace(b"- [ ] 1.2", b"- [x] 1.2")


def test_line_separator_does_not_misplace_the_tick(
    project: Path,
):  # Minor: splitlines drift
    _ = _plan(project).write_text(
        PLAN.replace("# add-x — plan", "# add-x" + chr(0x2028) + "plan"),
        encoding="utf-8",
    )
    base = _git(project, "rev-parse", "HEAD")
    assert main(["exec", "done", "1.2", base, "--", sys.executable, "-c", "pass"]) == 0
    assert "- [x] 1.2 Next" in _plan(project).read_text(encoding="utf-8")


def test_bad_base_is_one_line(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # Minor: BASE
    assert (
        main(["exec", "done", "1.2", "not-a-sha", "--", sys.executable, "-c", "pass"])
        == 1
    )
    assert "not-a-sha" in capsys.readouterr().err
    assert "- [ ] 1.2" in _plan(project).read_text(encoding="utf-8")


def test_review_package_without_color(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # Minor
    _ = _git(project, "config", "color.ui", "always")
    base = _git(project, "rev-parse", "HEAD")
    write(project / "a.py", "x = 1\n")
    _ = _git(project, "add", "a.py")
    _ = _git(project, "commit", "-qm", "feat: a")
    assert main(["exec", "review-package", base]) == 0
    text = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert "\x1b[" not in text
    assert "+x = 1" in text


def test_done_twice_writes_two_ledger_lines(project: Path):  # I10
    base = _git(project, "rev-parse", "HEAD")
    for _ in range(2):
        assert (
            main(["exec", "done", "1.2", base, "--", sys.executable, "-c", "pass"]) == 0
        )
    ledger = (project / ".grillspec/exec" / ID / "progress.md").read_text(
        encoding="utf-8"
    )
    assert ledger.count("Task 1.2: complete") == 2


def test_missing_plan(project: Path, capsys: pytest.CaptureFixture[str]):  # I10
    _plan(project).unlink()
    assert main(["exec", "start", "1.1"]) == 1
    assert "no plan at openspec/changes/add-x/tasks.md" in capsys.readouterr().err


@pytest.mark.usefixtures("project")
def test_printed_paths_use_forward_slashes(capsys: pytest.CaptureFixture[str]):  # I10
    assert main(["exec", "start", "1.1"]) == 0
    assert "\\" not in capsys.readouterr().out


def test_vendored_relative_links_resolve():  # I6
    pattern = re.compile(r"\]\((\.\./[^)#]+|[\w-]+\.md)\)")
    broken = [
        f"{path.relative_to(SKILLS)} → {target}"
        for path in sorted(SKILLS.glob("grillspec-*/*.md"))
        for target in pattern.findall(path.read_text(encoding="utf-8"))
        if not (path.parent / target).resolve().exists()
    ]
    assert broken == []
