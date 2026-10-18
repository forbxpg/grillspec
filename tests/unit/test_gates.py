"""Tests for the phase gate decision (spec S8-R1)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.gates import ToolCall, decide, patch_paths, shell_targets
from grillspec.state import gates_pause, pause_gates, resume_gates
from support import GATED_ID, openspec_change, phase_project, write

if TYPE_CHECKING:
    from pathlib import Path

ID = GATED_ID
OTHER = "add-other"


def _project(root: Path, phase: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(root)
    return phase_project(root, phase)


def _change(root: Path, change_id: str, *, grilled: bool) -> None:
    openspec_change(root, change_id, grilled=grilled)


def _edit(root: Path, relative: str) -> str | None:
    return decide(root, ToolCall("edit", (str(root / relative),)))


def _shell(root: Path, command: str) -> str | None:
    return decide(root, ToolCall("shell", command=command))


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _project(tmp_path, "spec", monkeypatch)


def test_code_edit_refused_while_specifying(spec: Path):  # GT-1
    line = _edit(spec, "src/app.py")
    assert line is not None
    assert line.startswith(f"grillspec gate: {ID} is in the spec phase, ")
    assert "src/app.py is outside them" in line
    assert "Next: " in line
    assert line.endswith("the user runs grillspec gate pause in their own terminal.")
    assert "\n" not in line


@pytest.mark.parametrize(
    "relative",
    [
        f"openspec/changes/{ID}/design.md",
        f"openspec/changes/{ID}/specs/limits/spec.md",
        ".grillspec/council/q1.json",
        f"src/../openspec/changes/{ID}/proposal.md",
    ],
)
def test_artifacts_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
):  # GT-2
    root = _project(tmp_path, "grill", monkeypatch)
    assert _edit(root, relative) is None


def test_other_change_is_not_an_artifact(spec: Path):  # GT-2
    assert _edit(spec, f"openspec/changes/{OTHER}/design.md") is not None


def test_outside_root_allowed(spec: Path):  # GT-2
    assert decide(spec, ToolCall("edit", (str(spec.parent / "elsewhere.txt"),))) is None


def test_relative_path_resolved_against_root(spec: Path):
    assert decide(spec, ToolCall("edit", ("src/app.py",))) is not None
    assert decide(spec, ToolCall("edit", (f"openspec/changes/{ID}/design.md",))) is None


def test_allow_globs_from_config(spec: Path):
    write(
        spec / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n[gates]\nallow = ["notes/*"]\n',
    )
    assert _edit(spec, "notes/research/a.md") is None
    assert _edit(spec, "src/app.py") is not None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows paths ignore case")
def test_windows_case_and_separators(spec: Path):
    path = str(spec / "SRC" / "App.py").upper()
    assert decide(spec, ToolCall("edit", (path,))) is not None
    allowed = str(spec / "openspec" / "changes" / ID / "DESIGN.md").replace("\\", "/")
    assert decide(spec, ToolCall("edit", (allowed,))) is None


def test_silent_in_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # GT-3
    root = _project(tmp_path, "execute", monkeypatch)
    assert _edit(root, "src/app.py") is None
    assert _shell(root, "rm -rf src") is None


def test_silent_without_active_change(spec: Path):  # GT-3
    write(spec / ".grillspec/state.json", '{"version": 1, "active": null}\n')
    assert _edit(spec, "src/app.py") is None


def test_silent_when_disabled(spec: Path):  # GT-3
    write(
        spec / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n[gates]\nenabled = false\n',
    )
    assert _edit(spec, "src/app.py") is None


@pytest.mark.parametrize(
    "command", ["echo x > src/a.py", "sed -i s/a/b/ src/a.py", "rm src/a.py"]
)
def test_shell_writes_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
):  # GT-4
    root = _project(tmp_path, "plan", monkeypatch)
    line = _shell(root, command)
    assert line is not None
    assert line.startswith(f"grillspec gate: {ID} is in the plan phase, ")


@pytest.mark.parametrize(
    "command",
    [
        "ls src",
        "git status",
        "pytest -q",
        "grillspec status",
        f"echo note >> openspec/changes/{ID}/design.md",
    ],
)
def test_shell_reads_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
):  # GT-4
    root = _project(tmp_path, "plan", monkeypatch)
    assert _shell(root, command) is None


def test_unknown_writer_target_refused(spec: Path):  # GT-4
    line = _shell(spec, "git reset --hard")
    assert line is not None
    assert "`git reset --hard` is outside them" in line


def test_pause_until_phase_changes(spec: Path):  # GT-5
    pause_gates(spec, ID, "spec")
    assert gates_pause(spec) == (ID, "spec")
    assert _edit(spec, "src/app.py") is None
    assert main(["approve", "spec"]) == 0  # phase is now plan
    assert _edit(spec, "src/app.py") is not None


def test_resume(spec: Path):  # GT-5
    pause_gates(spec, ID, "spec")
    resume_gates(spec)
    assert gates_pause(spec) is None
    assert _edit(spec, "src/app.py") is not None


def test_switching_change_drops_pause(spec: Path):  # GT-5
    pause_gates(spec, ID, "spec")
    _change(spec, OTHER, grilled=True)
    assert main(["use", OTHER]) == 0
    assert gates_pause(spec) is None
    assert _edit(spec, "src/app.py") is not None


def test_agent_cannot_pause(spec: Path):  # GT-5
    line = _shell(spec, "grillspec gate pause")
    assert line is not None
    assert "only the user" in line
    assert _shell(spec, 'sh "/x/scripts/grillspec" gate pause') is not None


def test_corrupt_config_is_no_opinion(spec: Path):  # GT-6
    write(spec / ".grillspec/config.toml", "version = [\n")
    assert _edit(spec, "src/app.py") is None


def test_corrupt_state_is_no_opinion(spec: Path):  # GT-6
    write(spec / ".grillspec/state.json", "{not json")
    assert _edit(spec, "src/app.py") is None


@pytest.mark.parametrize(
    ("command", "paths", "unknown"),
    [
        ("echo x > src/a.py", ["src/a.py"], False),
        ("echo x >out.txt", ["out.txt"], False),
        ("make 2>>err.log", ["err.log"], False),
        ("cmd &> all.log", ["all.log"], False),
        ("echo 'a > b'", [], False),
        ("pytest -q 2>&1 | tail -5", [], False),
        ("ls > /dev/null", [], False),
        ("sed -i s/a/b/ src/a.py", ["src/a.py"], False),
        ("perl -pi -e s/a/b/ a.txt", ["a.txt"], False),
        ("cp a.txt b.txt", ["b.txt"], False),
        ("mv a.txt b.txt", ["a.txt", "b.txt"], False),
        ("rm -rf build dist", ["build", "dist"], False),
        ("touch a b", ["a", "b"], False),
        ("mkdir -p d/e", ["d/e"], False),
        ("tee -a log.txt", ["log.txt"], False),
        ("X=1 sudo rm a", ["a"], False),
        ("true && echo y >> b.txt", ["b.txt"], False),
        ("cat <<EOF > notes.md\nhello\nEOF", ["notes.md"], False),
        ("git restore a.py", [], True),
        ("git status", [], False),
        ("git diff --stat", [], False),
        ("Set-Content -Path a.txt -Value x", ["a.txt"], False),
        ("grillspec status", [], False),
        ("python -c \"open('a', 'w')\"", [], False),
    ],
)
def test_shell_targets(command: str, paths: list[str], unknown: bool):  # ruff: ignore[boolean-type-hint-positional-argument]
    assert shell_targets(command) == (paths, unknown)


def test_shell_apply_patch_heredoc():
    command = (
        "apply_patch <<'EOF'\n*** Begin Patch\n*** Add File: src/a.py\n+x\n"
        "*** End Patch\nEOF"
    )
    assert shell_targets(command) == (["src/a.py"], False)


def test_patch_paths():
    patch = """*** Begin Patch
*** Add File: docs/a.md
+hello
*** Update File: src/b.py
*** Move to: src/c.py
@@
-x
+y
*** Delete File: old.txt
*** End Patch
"""
    assert patch_paths(patch) == ["docs/a.md", "src/b.py", "src/c.py", "old.txt"]
