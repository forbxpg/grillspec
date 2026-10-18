"""Read each harness's pre-tool payload and answer in its own shape."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec.hooks import Harness
from grillspec.paths import project_root

from ._gate import ToolCall, decide
from ._patch import patch_paths

if TYPE_CHECKING:
    from collections.abc import Mapping

_EDITS = {
    Harness.CLAUDE: frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"}),
    Harness.CURSOR: frozenset({"Write", "Delete"}),
    Harness.CODEX: frozenset({"apply_patch", "Edit", "Write"}),
    Harness.ANTIGRAVITY: frozenset({
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }),
    Harness.GIGACODE: frozenset({"write_file", "edit"}),
}
_SHELLS = {
    Harness.CLAUDE: frozenset({"Bash", "PowerShell"}),
    Harness.CURSOR: frozenset({"Shell"}),
    Harness.CODEX: frozenset({"Bash", "exec_command"}),
    Harness.ANTIGRAVITY: frozenset({"run_command"}),
    Harness.GIGACODE: frozenset({"run_shell_command"}),
}
NO_OPINION = {
    Harness.CLAUDE: "",
    Harness.CODEX: "",
    Harness.CURSOR: "{}",
    # agy 1.4.2: an empty reply is no opinion; IDE docs define "allow" as approval.
    Harness.ANTIGRAVITY: "",
    Harness.GIGACODE: "",
}


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _object(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _first(value: object) -> str:
    items = cast("list[object]", value) if isinstance(value, list) else []
    return _text(items[0]) if items else ""


def _read(
    harness: Harness, data: dict[str, object], env: Mapping[str, str]
) -> tuple[str, str, dict[str, object]]:
    """Pull the tool name, working directory and tool input out of a payload.

    Args:
        harness: Harness - Who sent it.
        data: dict[str, object] - The parsed payload.
        env: Mapping[str, str] - The hook's environment.

    Returns:
        tuple[str, str, dict[str, object]] - Tool name, directory, tool input.

    """
    if harness is Harness.ANTIGRAVITY:
        call = _object(data.get("toolCall"))
        args = _object(call.get("args"))
        cwd = _text(args.get("Cwd")) or _first(data.get("workspacePaths"))
        return _text(call.get("name")), cwd, args
    cwd = _text(data.get("cwd"))
    if harness is Harness.CURSOR and not cwd:
        cwd = _first(data.get("workspace_roots")) or env.get("CURSOR_PROJECT_DIR", "")
    return _text(data.get("tool_name")), cwd, _object(data.get("tool_input"))


def _call(
    harness: Harness, tool: str, cwd: str, args: dict[str, object]
) -> ToolCall | None:
    """Reduce a tool call to what the gate needs.

    Args:
        harness: Harness - Who sent it.
        tool: str - Tool name.
        cwd: str - Directory relative paths start from.
        args: dict[str, object] - Tool input.

    Returns:
        ToolCall | None - None for tools the gate ignores.

    """
    if tool in _SHELLS[harness]:
        keys = ("cwd", "working_directory", "workdir", "directory")
        named = (args.get(key) for key in keys)
        cwd = next((text for value in named if (text := _text(value))), cwd)
        command = _text(
            args.get("CommandLine" if harness is Harness.ANTIGRAVITY else "command")
        )
        return ToolCall("shell", command=command, cwd=cwd)
    if tool not in _EDITS[harness]:
        return None
    if harness is Harness.CODEX:
        paths = tuple(patch_paths(_text(args.get("command"))))
    elif harness is Harness.ANTIGRAVITY:
        paths = (_text(args.get("TargetFile")),)
    else:
        paths = (_text(args.get("file_path")) or _text(args.get("notebook_path")),)
    return ToolCall("edit", tuple(path for path in paths if path), cwd=cwd)


def _deny(harness: Harness, reason: str) -> str:
    if harness is Harness.CURSOR:
        return json.dumps({
            "permission": "deny",
            "user_message": reason,
            "agent_message": reason,
        })
    if harness is Harness.ANTIGRAVITY:
        return json.dumps({"decision": "deny", "reason": reason})
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


def pre_tool(harness: Harness, stdin: bytes, env: Mapping[str, str]) -> str:
    """Answer one pre-tool hook call; never raises.

    Args:
        harness: Harness - Who is asking.
        stdin: bytes - The payload as received (a UTF-8 BOM is fine).
        env: Mapping[str, str] - The hook's environment.

    Returns:
        str - The harness's deny answer, or its no-opinion answer (maybe "").

    """
    try:
        data = _object(cast("object", json.loads(stdin.decode("utf-8-sig"))))
        tool, cwd, args = _read(harness, data, env)
        call = _call(harness, tool, cwd, args)
        if call is None or not cwd:
            return NO_OPINION[harness]
        reason = decide(project_root(Path(cwd)), call)
    except Exception:  # ruff: ignore[blind-except] - a hook must never fail the agent
        return NO_OPINION[harness]
    return NO_OPINION[harness] if reason is None else _deny(harness, reason)
