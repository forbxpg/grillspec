"""Fixes from the S8 final review."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.gates import ToolCall, decide, pre_tool, shell_targets
from grillspec.hooks import Harness
from grillspec.state import gates_pause, pause_gates
from support import GATED_ID, REPO, phase_project, write

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

CHANGE = f"openspec/changes/{GATED_ID}"


def _answer(text: str) -> Callable[[str], str]:
    def reply(_prompt: str) -> str:
        return text

    return reply


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return phase_project(tmp_path, "spec")


def _shell(root: Path, command: str) -> str | None:
    return decide(root, ToolCall("shell", command=command))


def _edit(root: Path, relative: str) -> str | None:
    return decide(root, ToolCall("edit", (str(root / relative),)))


def test_antigravity_gate_ships_disabled():  # C1
    hooks = cast(
        "dict[str, dict[str, object]]", json.loads((REPO / "hooks.json").read_text())
    )
    assert hooks["grillspec-gate"]["enabled"] is False


def test_approval_ends_the_pause(spec: Path):  # I1
    pause_gates(spec, GATED_ID, "spec")
    assert main(["approve", "spec"]) == 0
    assert gates_pause(spec) is None
    write(spec / CHANGE / "specs/limits/spec.md", "## ADDED Requirements\n\nchanged\n")
    assert _edit(spec, "src/app.py") is not None  # stale spec: back in spec, gated


@pytest.mark.parametrize(
    "command",
    [
        "git worktree add ../repo-x -b x",
        "git worktree list",
        "git checkout -b feature",
        "git switch -c feature",
        "git stash list",
        "git commit -qm 'spec: draft'",
        "git add -A",
        "git -C sub status",
    ],
)
def test_git_without_file_writes_allowed(spec: Path, command: str):  # I2
    assert _shell(spec, command) is None


@pytest.mark.parametrize(
    "command",
    [
        "git checkout -- src/a.py",
        "git reset --hard",
        "git stash",
        "git stash pop",
        "git restore src/a.py",
        "git apply x.patch",
        "git clean -fd",
        "git -C sub restore a.py",
    ],
)
def test_git_file_writes_refused(spec: Path, command: str):  # I2, M4
    assert _shell(spec, command) is not None


def test_memory_docs_and_council_gitignore_allowed(spec: Path):  # I2
    assert _edit(spec, "docs/grillspec/memory/retry.md") is None
    assert _edit(spec, ".grillspec/council/.gitignore") is None
    council = (REPO / "skills/grillspec-council/SKILL.md").read_text(encoding="utf-8")
    assert "to `.gitignore`" not in council


@pytest.mark.parametrize(
    "command",
    [
        'python -c "\nprint(1 > 0)\n"',
        'gh pr create --body "a\n> quoted\n"',
        "gh pr create --body \"$(cat <<'EOF'\nline > x\nEOF\n)\"",
    ],
)
def test_multiline_quotes_are_one_argument(spec: Path, command: str):  # I3
    assert _shell(spec, command) is None


@pytest.mark.parametrize(
    "relative",
    [
        ".grillspec/state.json",
        ".grillspec/config.toml",
        f".grillspec/changes/{GATED_ID}.toml",
    ],
)
def test_grillspec_state_is_not_hand_editable(spec: Path, relative: str):  # I4
    assert _edit(spec, relative) is not None


@pytest.mark.parametrize(
    "command",
    ['grillspec gate "pause"', 'grillspec gate pau""se', "sh ./grillspec gate pause"],
)
def test_quoted_pause_still_refused(spec: Path, command: str):  # I4
    line = _shell(spec, command)
    assert line is not None
    assert "only the user" in line


def test_searching_for_pause_is_a_read(spec: Path):  # I4
    assert _shell(spec, 'rg "gate pause" src/grillspec') is None


def test_pause_needs_a_terminal(
    spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # I4
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    _ = capsys.readouterr()
    assert main(["gate", "pause"]) == 1
    assert "own terminal" in capsys.readouterr().err
    assert gates_pause(spec) is None


@pytest.mark.parametrize(("answer", "code"), [("y", 0), ("n", 1)])
def test_pause_asks_first(
    spec: Path, monkeypatch: pytest.MonkeyPatch, answer: str, code: int
):  # I4
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", _answer(answer))
    assert main(["gate", "pause"]) == code
    assert (gates_pause(spec) is not None) is (code == 0)


@pytest.mark.parametrize(
    ("command", "paths", "unknown"),
    [
        ('grep ">" README.md', [], False),  # M1
        ("grep '<<' x\nrm src/a.py", ["src/a.py"], False),  # M1
        ("ls > $null", [], False),  # M2
        ("sed -i '' s/a/b/ f.txt", ["f.txt"], False),  # M2
        ("perl -Mstrict -e 'print 1'", [], False),  # M2
        ("mkdir -m 755 d", ["d"], False),  # M2
        ("cmd >& out.log", ["out.log"], False),  # M4
        ('bash -c "rm src/a.py"', ["src/a.py"], False),  # M4
        ('rm src/a.py; echo "*** Begin Patch"', ["src/a.py"], False),  # M4
        ("New-Item -ItemType Directory specs/x", ["specs/x"], False),  # M5
        ("Remove-Item -Path src/a.py -Force", ["src/a.py"], False),  # M5
        ("Set-Content -Path a.txt -Value x", ["a.txt"], False),  # M5
        ("ni foo.txt", ["foo.txt"], False),  # M5
        ("echo x > C:\\proj\\a.txt", ["C:\\proj\\a.txt"], False),  # M6
    ],
)
def test_shell_targets_review(command: str, paths: list[str], unknown: bool):  # ruff: ignore[boolean-type-hint-positional-argument]
    assert shell_targets(command) == (paths, unknown)


def test_home_and_variables_expand(spec: Path, monkeypatch: pytest.MonkeyPatch):  # M2
    monkeypatch.setenv("HOME", str(spec.parent))
    monkeypatch.setenv("PROJ", str(spec))
    assert _shell(spec, "echo x > ~/notes.txt") is None
    assert _shell(spec, "echo x > $HOME/notes.txt") is None
    assert _shell(spec, "echo x > $PROJ/src/app.py") is not None
    assert _shell(spec, "echo x > $UNSET_VAR_XYZ/a.txt") is None


def test_cd_moves_the_base(spec: Path):  # M3
    assert _shell(spec, f"cd {CHANGE} && touch notes.md") is None
    line = _shell(spec, "cd src && touch x.py")
    assert line is not None
    assert "src/x.py is outside them" in line


def test_cursor_shell_cwd(spec: Path):  # M3
    data = {
        "workspace_roots": [str(spec)],
        "tool_name": "Shell",
        "tool_input": {"command": "touch notes.md", "cwd": str(spec / CHANGE)},
    }
    assert pre_tool(Harness.CURSOR, json.dumps(data).encode(), {}) == "{}"
