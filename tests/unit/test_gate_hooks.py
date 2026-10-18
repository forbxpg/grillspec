"""Tests for ``grillspec hook pre-tool`` and ``grillspec gate`` (spec S8-R2)."""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.gates import pre_tool
from grillspec.hooks import Harness
from support import GATED_ID, phase_project

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

PREFIX = f"grillspec gate: {GATED_ID} is in the spec phase, "
ARTIFACT = f"openspec/changes/{GATED_ID}/design.md"


def _answer(text: str) -> Callable[[str], str]:
    def reply(_prompt: str) -> str:
        return text

    return reply


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return phase_project(tmp_path, "spec")


def _payload(harness: Harness, root: Path, target: str) -> bytes:
    """Build a write payload for ``target`` (relative to ``root``) per harness.

    Returns:
        bytes - The stdin the harness would send.

    """
    absolute = str(root / target)
    if harness is Harness.CLAUDE:
        data: object = {
            "cwd": str(root),
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": absolute, "content": "x"},
        }
    elif harness is Harness.CODEX:
        patch = f"*** Begin Patch\n*** Add File: {target}\n+x\n*** End Patch\n"
        data = {
            "cwd": str(root),
            "tool_name": "apply_patch",
            "tool_input": {"command": patch},
        }
    elif harness is Harness.CURSOR:
        data = {
            "cwd": "",
            "workspace_roots": [str(root)],
            "tool_name": "Write",
            "tool_input": {"file_path": absolute, "content": "x"},
        }
        return b"\xef\xbb\xbf" + json.dumps(data).encode()
    else:
        data = {
            "workspacePaths": [str(root)],
            "toolCall": {"name": "write_to_file", "args": {"TargetFile": absolute}},
        }
    return json.dumps(data).encode()


def _reason(harness: Harness, output: str) -> str:
    data = cast("dict[str, object]", json.loads(output))
    if harness is Harness.CURSOR:
        assert data["permission"] == "deny"
        assert data["agent_message"] == data["user_message"]
        return cast("str", data["user_message"])
    if harness is Harness.ANTIGRAVITY:
        assert data["decision"] == "deny"
        return cast("str", data["reason"])
    hook = cast("dict[str, object]", data["hookSpecificOutput"])
    assert hook["hookEventName"] == "PreToolUse"
    assert hook["permissionDecision"] == "deny"
    return cast("str", hook["permissionDecisionReason"])


NO_OPINION = {
    Harness.CLAUDE: "",
    Harness.CODEX: "",
    Harness.CURSOR: "{}",
    Harness.ANTIGRAVITY: "",  # agy: an empty reply defers; IDE docs say "allow" approves
}
HARNESSES = list(NO_OPINION)


@pytest.mark.parametrize("harness", HARNESSES)
def test_one_denial_per_harness(spec: Path, harness: Harness):  # GT-7
    output = pre_tool(harness, _payload(harness, spec, "src/app.py"), {})
    reason = _reason(harness, output)
    assert reason.startswith(PREFIX)
    assert "src/app.py is outside them" in reason


@pytest.mark.parametrize("harness", HARNESSES)
def test_no_opinion_per_harness(spec: Path, harness: Harness):
    assert (
        pre_tool(harness, _payload(harness, spec, ARTIFACT), {}) == NO_OPINION[harness]
    )


@pytest.mark.parametrize("harness", HARNESSES)
@pytest.mark.parametrize("stdin", [b"", b"not json", b"[1, 2]", b'{"tool_name": 3}'])
def test_garbage_is_no_opinion(spec: Path, harness: Harness, stdin: bytes):  # GT-6
    assert spec.is_dir()
    assert pre_tool(harness, stdin, {}) == NO_OPINION[harness]


@pytest.mark.parametrize(
    ("harness", "data"),
    [
        (
            Harness.CLAUDE,
            {"tool_name": "Bash", "tool_input": {"command": "rm src/a.py"}},
        ),
        (
            Harness.CODEX,
            {"tool_name": "Bash", "tool_input": {"command": "rm src/a.py"}},
        ),
        (
            Harness.CURSOR,
            {"tool_name": "Shell", "tool_input": {"command": "rm src/a.py"}},
        ),
        (
            Harness.ANTIGRAVITY,
            {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "rm src/a.py"},
                }
            },
        ),
    ],
)
def test_shell_denied_per_harness(
    spec: Path, harness: Harness, data: dict[str, object]
):  # GT-4
    root_key = {
        Harness.CURSOR: "workspace_roots",
        Harness.ANTIGRAVITY: "workspacePaths",
    }
    key = root_key.get(harness, "cwd")
    data[key] = [str(spec)] if key != "cwd" else str(spec)
    reason = _reason(harness, pre_tool(harness, json.dumps(data).encode(), {}))
    assert "src/a.py is outside them" in reason


def test_cursor_root_from_environment(spec: Path):
    data = {"tool_name": "Write", "tool_input": {"file_path": str(spec / "src/x.py")}}
    env = {"CURSOR_PROJECT_DIR": str(spec)}
    output = pre_tool(Harness.CURSOR, json.dumps(data).encode(), env)
    assert _reason(Harness.CURSOR, output).startswith(PREFIX)


def test_claude_notebook_and_reads(spec: Path):
    notebook = {
        "cwd": str(spec),
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(spec / "nb.ipynb")},
    }
    assert pre_tool(Harness.CLAUDE, json.dumps(notebook).encode(), {})
    read = {"cwd": str(spec), "tool_name": "Read", "tool_input": {"file_path": "x"}}
    assert not pre_tool(Harness.CLAUDE, json.dumps(read).encode(), {})


def test_codex_patch_with_one_code_file_denied(spec: Path):
    patch = (
        f"*** Begin Patch\n*** Update File: {ARTIFACT}\n@@\n-a\n+b\n"
        "*** Add File: src/z.py\n+x\n*** End Patch\n"
    )
    data = {
        "cwd": str(spec),
        "tool_name": "apply_patch",
        "tool_input": {"command": patch},
    }
    reason = _reason(
        Harness.CODEX, pre_tool(Harness.CODEX, json.dumps(data).encode(), {})
    )
    assert "src/z.py is outside them" in reason


def test_codex_patch_relative_to_subdirectory(spec: Path):
    sub = spec / "openspec"
    patch = f"*** Begin Patch\n*** Add File: changes/{GATED_ID}/notes.md\n+x\n*** End Patch\n"
    data = {
        "cwd": str(sub),
        "tool_name": "apply_patch",
        "tool_input": {"command": patch},
    }
    assert not pre_tool(Harness.CODEX, json.dumps(data).encode(), {})


def _stdin(monkeypatch: pytest.MonkeyPatch, data: bytes) -> None:
    monkeypatch.setattr(
        "sys.stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
    )


def test_cli_hook_pre_tool(
    spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _stdin(monkeypatch, _payload(Harness.CLAUDE, spec, "src/app.py"))
    assert main(["hook", "pre-tool", "--harness", "claude"]) == 0
    assert _reason(Harness.CLAUDE, capsys.readouterr().out).startswith(PREFIX)


def test_cli_hook_pre_tool_silent(
    spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _stdin(monkeypatch, _payload(Harness.CLAUDE, spec, ARTIFACT))
    assert main(["hook", "pre-tool", "--harness", "claude"]) == 0
    assert not capsys.readouterr().out


def test_cli_gate_pause_and_resume(
    spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # GT-5
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", _answer("y"))
    assert main(["gate", "pause"]) == 0
    assert "paused" in capsys.readouterr().out
    assert not pre_tool(Harness.CLAUDE, _payload(Harness.CLAUDE, spec, "src/a.py"), {})
    assert main(["gate", "resume"]) == 0
    assert pre_tool(Harness.CLAUDE, _payload(Harness.CLAUDE, spec, "src/a.py"), {})


def test_cli_gate_pause_outside_gated_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    _ = phase_project(tmp_path, "execute")
    _ = capsys.readouterr()
    assert main(["gate", "pause"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: nothing to pause: ")
    assert err.count("\n") == 1
