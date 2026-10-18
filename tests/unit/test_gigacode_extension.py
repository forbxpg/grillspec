"""grillspec as a native GigaCode extension (GigaCode 0.13.1, read from its bundle)."""

from __future__ import annotations

import io
import json
import re
from typing import TYPE_CHECKING, cast

import pytest

from grillspec import __version__
from grillspec.cli import main
from grillspec.gates import pre_tool
from grillspec.gates._adapters import _EDITS, _SHELLS
from grillspec.hooks import Harness
from support import GATED_ID, REPO, phase_project

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

MANIFEST = REPO / "gigacode-extension.json"


def _manifest() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(MANIFEST.read_text(encoding="utf-8")))


def test_manifest_names_the_extension():
    data = _manifest()
    assert data["name"] == "grillspec"
    assert data["version"] == __version__


def test_context_files_load_the_router_and_the_cli_line():
    files = cast("list[str]", _manifest()["contextFileName"])
    assert "skills/using-grillspec/SKILL.md" in files
    for name in files:
        assert (REPO / name).is_file(), name
    context = next(REPO / n for n in files if not n.startswith("skills/"))
    text = context.read_text(encoding="utf-8")
    assert re.search(
        r"^grillspec CLI: .*scripts/grillspec.* <command>$", text, re.MULTILINE
    )
    assert "grillspec.cmd" in text  # Windows


def test_pre_tool_hook_matches_gigacode_tools():
    hooks = cast("dict[str, list[dict[str, object]]]", _manifest()["hooks"])
    (entry,) = hooks["PreToolUse"]
    matcher = re.compile(cast("str", entry["matcher"]))
    for tool in _EDITS[Harness.GIGACODE] | _SHELLS[Harness.GIGACODE]:
        assert matcher.search(tool), tool
    assert not matcher.search("read_file")
    (hook,) = cast("list[dict[str, object]]", entry["hooks"])
    command = cast("str", hook["command"])
    assert "${extensionPath}" in command
    assert command.endswith("pre-tool gigacode")
    assert cast("int", hook["timeout"]) >= 10_000  # GigaCode counts milliseconds


def test_no_session_start_hook():  # GigaCode 0.13.1 discards SessionStart output
    assert "SessionStart" not in cast("dict[str, object]", _manifest()["hooks"])


@pytest.fixture
def spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return phase_project(tmp_path, "spec")


def _payload(root: Path, tool: str, tool_input: Mapping[str, object]) -> bytes:
    data = {"cwd": str(root), "tool_name": tool, "tool_input": tool_input}
    return json.dumps(data).encode()


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("write_file", {"file_path": "src/app.py", "content": "x"}),
        ("edit", {"file_path": "src/app.py", "old_string": "a", "new_string": "b"}),
        ("run_shell_command", {"command": "rm src/app.py"}),
    ],
)
def test_gigacode_denies_in_the_claude_shape(
    spec: Path, tool: str, tool_input: dict[str, object]
):
    if "file_path" in tool_input:
        tool_input = {**tool_input, "file_path": str(spec / "src/app.py")}
    out = pre_tool(Harness.GIGACODE, _payload(spec, tool, tool_input), {})
    hook = json.loads(out)["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert hook["permissionDecisionReason"].startswith(f"grillspec gate: {GATED_ID} ")


def test_gigacode_shell_directory_is_the_cwd(spec: Path):
    tool_input = {
        "command": "touch notes.md",
        "directory": f"openspec/changes/{GATED_ID}",
    }
    payload = _payload(spec, "run_shell_command", tool_input)
    assert not pre_tool(Harness.GIGACODE, payload, {})


def test_gigacode_no_opinion_is_empty(spec: Path):
    payload = _payload(spec, "read_file", {"file_path": str(spec / "src/app.py")})
    assert not pre_tool(Harness.GIGACODE, payload, {})


def test_cli_hook_accepts_gigacode(
    spec: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    data = _payload(spec, "write_file", {"file_path": str(spec / "src/app.py")})
    monkeypatch.setattr(
        "sys.stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
    )
    assert main(["hook", "pre-tool", "--harness", "gigacode"]) == 0
    assert "deny" in capsys.readouterr().out


def test_cli_session_start_for_gigacode_is_silent(capsys: pytest.CaptureFixture[str]):
    assert main(["hook", "session-start", "--harness", "gigacode"]) == 0
    assert not capsys.readouterr().out
