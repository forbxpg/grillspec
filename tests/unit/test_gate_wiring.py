"""Hook files, the runner, session start and the router carry the gate (S8-R3)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from grillspec.gates._adapters import _EDITS, _SHELLS
from grillspec.hooks import Harness, session_context
from support import GATED_ID, WINDOWS, phase_project, plugin_copy, write

REPO = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, object]:
    return cast(
        "dict[str, object]", json.loads((REPO / relative).read_text(encoding="utf-8"))
    )


def _entries(harness: Harness) -> list[dict[str, object]]:
    """Return the harness's pre-tool hook entries (matcher + command).

    Returns:
        list[dict[str, object]] - One dict with ``matcher`` and ``command`` each.

    """
    if harness is Harness.ANTIGRAVITY:
        group = cast("dict[str, object]", _load("hooks.json")["grillspec-gate"])
        raw = cast("list[dict[str, object]]", group["PreToolUse"])
    elif harness is Harness.CURSOR:
        hooks = cast("dict[str, object]", _load("hooks/hooks-cursor.json")["hooks"])
        flat = cast("list[dict[str, object]]", hooks["preToolUse"])
        return [{"matcher": e["matcher"], "command": e["command"]} for e in flat]
    else:
        name = (
            "hooks/hooks.json"
            if harness is Harness.CLAUDE
            else "hooks/hooks-codex.json"
        )
        hooks = cast("dict[str, object]", _load(name)["hooks"])
        raw = cast("list[dict[str, object]]", hooks["PreToolUse"])
    return [
        {"matcher": item["matcher"], "command": hook["command"]}
        for item in raw
        for hook in cast("list[dict[str, object]]", item["hooks"])
    ]


@pytest.mark.parametrize(
    "harness", [Harness.CLAUDE, Harness.CODEX, Harness.CURSOR, Harness.ANTIGRAVITY]
)
def test_hook_files_route_write_and_shell_tools(harness: Harness):
    entries = _entries(harness)
    assert len(entries) == 1
    entry = entries[0]
    assert f"pre-tool {harness}" in cast("str", entry["command"])
    assert "run-hook.cmd" in cast("str", entry["command"])
    matcher = re.compile(cast("str", entry["matcher"]))
    for tool in _EDITS[harness] | _SHELLS[harness]:
        assert matcher.fullmatch(tool), tool
    assert not matcher.fullmatch("Read")


def test_claude_hook_quotes_the_plugin_root():
    command = cast("str", _entries(Harness.CLAUDE)[0]["command"])
    assert command.startswith('"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd"')


def _run(
    root: Path, harness: str, env: dict[str, str], stdin: bytes
) -> tuple[int, str]:
    runner = root / "hooks" / "run-hook.cmd"
    command = (
        ["cmd.exe", "/c", str(runner), "pre-tool", harness]
        if WINDOWS
        else ["/bin/sh", str(runner), "pre-tool", harness]
    )
    done = subprocess.run(
        command, input=stdin, capture_output=True, env=env, cwd=root, check=False
    )
    return done.returncode, done.stdout.decode().strip()


@pytest.mark.parametrize(
    ("harness", "expected"),
    [
        ("claude", ""),
        ("codex", ""),
        ("cursor", "{}"),
        ("antigravity", '{"decision": "allow"}'),
    ],
)
def test_runner_without_python_has_no_opinion(
    tmp_path: Path, harness: str, expected: str
):
    root = plugin_copy(tmp_path)
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    env = {"PATH": str(empty), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    code, out = _run(root, harness, env, b"{}")
    assert code == 0
    assert out == expected


def test_runner_passes_the_payload_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    _ = phase_project(project, "spec")
    root = plugin_copy(tmp_path)
    python_dir = str(Path(sys.executable).parent)
    env = {**os.environ, "PATH": python_dir + os.pathsep + os.environ.get("PATH", "")}
    payload = {
        "cwd": str(project),
        "tool_name": "Write",
        "tool_input": {"file_path": str(project / "src/app.py")},
    }
    code, out = _run(root, "claude", env, json.dumps(payload).encode())
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"


GATES_LINE = f"gates: on — edits outside {GATED_ID}'s artifacts are blocked"


def test_session_start_announces_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    _ = phase_project(tmp_path, "spec")
    assert GATES_LINE in session_context(tmp_path)


def test_session_start_quiet_when_gates_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    _ = phase_project(tmp_path, "execute")
    assert "gates: on" not in session_context(tmp_path)
    write(
        tmp_path / ".grillspec/state.json",
        f'{{"version": 1, "active": "{GATED_ID}"}}\n',
    )
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n[gates]\nenabled = false\n',
    )
    assert "gates: on" not in session_context(tmp_path)


def test_router_forbids_working_around_gates():
    router = (REPO / "skills/using-grillspec/SKILL.md").read_text(encoding="utf-8")
    assert "never work around a gate" in router.lower()
