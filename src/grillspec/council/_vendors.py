"""What grillspec knows about each external agent CLI."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ._proc import run_tree
from ._prompt import CouncilError

if TYPE_CHECKING:
    from collections.abc import Callable

    from grillspec.config import Member

PROBE_TIMEOUT = 10
INSTRUCTION = "Answer the request given on standard input."


@dataclass(frozen=True)
class Vendor:
    """One external agent CLI.

    Attributes:
        name: str - Executable name.
        experimental: bool - Not offered unless configured explicitly.
        probe: tuple[str, ...] | None - Arguments of a call that reports the
            login state without spending tokens; None when there is none.
        model_flag: str | None - Option that selects a model; None when the CLI
            has none.
        positional: bool - The CLI needs a short instruction argument while the
            prompt itself arrives on stdin.

    """

    name: str
    experimental: bool
    probe: tuple[str, ...] | None
    model_flag: str | None
    positional: bool


def _vendor(
    name: str,
    probe: tuple[str, ...] | None,
    model_flag: str | None,
    *,
    experimental: bool = False,
    positional: bool = False,
) -> Vendor:
    """Build a vendor entry with keyword flags.

    Returns:
        Vendor - The entry.

    """
    return Vendor(name, experimental, probe, model_flag, positional)


VENDORS: dict[str, Vendor] = {
    "claude": _vendor("claude", ("auth", "status"), "--model"),
    "codex": _vendor("codex", ("login", "status"), "-m"),
    "cursor-agent": _vendor("cursor-agent", ("status", "--format", "json"), "--model"),
    "gemini": _vendor("gemini", None, "-m", positional=True),
    "agy": _vendor("agy", None, None, positional=True),
    "gigacode": _vendor(
        "gigacode", ("auth", "status"), "-m", experimental=True, positional=True
    ),
}


def resolve_cli(name: str) -> str | None:
    """Find an agent CLI on PATH, never in the current directory.

    ``shutil.which`` on Windows looks in the current directory first, so a
    ``codex.cmd`` shipped inside a cloned repository would run instead of the
    real CLI. Only absolute PATH entries are searched here.

    Args:
        name: str - Executable name.

    Returns:
        str | None - Full path of the first match, or None.

    """
    windows = sys.platform == "win32"
    pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    suffixes = [ext for ext in pathext.split(";") if ext] if windows else [""]
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        folder = Path(entry.strip('"'))
        if not entry or not folder.is_absolute():
            continue
        for suffix in suffixes:
            candidate = folder / f"{name}{suffix}"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


_GIGACODE_LOGGED_OUT = "No authentication method configured"


def _json_flag(text: str, key: str) -> bool | None:
    """Read a boolean field from a JSON object.

    Args:
        text: str - Probe output.
        key: str - Field name.

    Returns:
        bool | None - The field, or None when the output is not such an object.

    """
    try:
        data = cast("object", json.loads(text))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    value = cast("dict[str, object]", data).get(key)
    return value if isinstance(value, bool) else None


def _gemini_logged_in() -> bool | None:
    """Tell from the environment and home directory whether gemini can log in.

    Returns:
        bool | None - True with an API key or saved login; None otherwise,
            since gemini has no probe that spends no tokens.

    """
    if os.environ.get("GEMINI_API_KEY"):
        return True
    if (Path.home() / ".gemini" / "oauth_creds.json").is_file():
        return True
    return None


def _gigacode_state(text: str) -> bool | None:
    """Read gigacode's probe, which exits 0 whether or not it is logged in.

    Args:
        text: str - Probe stdout and stderr.

    Returns:
        bool | None - False when it says no login is configured; None otherwise,
            since the logged-in wording has not been verified.

    """
    return False if _GIGACODE_LOGGED_OUT in text else None


# Vendor name -> reader of (exit code, stdout, stdout + stderr).
_READERS: dict[str, Callable[[int, str, str], bool | None]] = {
    "claude": lambda _code, out, _text: _json_flag(out, "loggedIn"),
    "cursor-agent": lambda _code, out, _text: _json_flag(out, "isAuthenticated"),
    "codex": lambda code, _out, _text: code == 0,
    "gigacode": lambda _code, _out, text: _gigacode_state(text),
}


def auth_state(name: str, executable: str) -> bool | None:
    """Tell whether an agent CLI is logged in, without sending a prompt.

    Args:
        name: str - Vendor name from ``VENDORS``.
        executable: str - Resolved path of the CLI.

    Returns:
        bool | None - True or False when the CLI says so; None when it cannot
            tell cheaply, does not answer in time, or answers unexpectedly.

    """
    if name == "gemini":
        return _gemini_logged_in()
    probe = VENDORS[name].probe
    reader = _READERS.get(name)
    if probe is None or reader is None:
        return None
    try:
        done = run_tree([executable, *probe], stdin=None, timeout=PROBE_TIMEOUT)
    except OSError:
        return None
    if done.returncode is None:
        return None
    out = done.stdout.decode("utf-8", "replace")
    return reader(done.returncode, out, out + done.stderr.decode("utf-8", "replace"))


# Fixed flags before the model option, and arguments after it; the prompt itself
# always goes to stdin.
_HEAD: dict[str, tuple[str, ...]] = {
    "claude": (
        "-p",
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--setting-sources",
        "user",
        "--output-format",
        "json",
    ),
    "codex": ("exec", "--skip-git-repo-check", "-s", "read-only", "--ephemeral"),
    "cursor-agent": ("-p", "--trust", "--mode", "ask", "--output-format", "json"),
    "gemini": ("--approval-mode", "plan", "-o", "json"),
    "agy": ("--sandbox",),
    "gigacode": ("--approval-mode", "plan", "-o", "json"),
}
_TAIL: dict[str, tuple[str, ...]] = {
    "codex": ("-",),
    "gemini": ("-p", INSTRUCTION),
    "agy": ("-p", INSTRUCTION),
    "gigacode": (INSTRUCTION,),
}


def build_argv(member: Member, executable: str) -> list[str]:
    """Build the headless, read-only call for an external member.

    Args:
        member: Member - A ``cli:`` member.
        executable: str - Resolved path of the CLI.

    Returns:
        list[str] - The executable and its arguments.

    Raises:
        CouncilError: If a model is given for a CLI without a model option.

    """
    vendor = VENDORS[member.name]
    model: tuple[str, ...] = ()
    if member.model is not None:
        if vendor.model_flag is None:
            msg = f"{member.name} has no model option"
            raise CouncilError(msg)
        model = (vendor.model_flag, member.model)
    return [executable, *_HEAD[member.name], *model, *_TAIL.get(member.name, ())]


def _field(node: object, key: str) -> object:
    """Read a field of a decoded JSON object.

    Args:
        node: object - Decoded value.
        key: str - Field name.

    Returns:
        object - The field, or None when the value is not an object.

    """
    return cast("dict[str, object]", node).get(key) if isinstance(node, dict) else None


def _first_key(data: dict[str, object], *path: str) -> str | None:
    """Return the first key of a nested object, such as the model that answered.

    Args:
        data: dict[str, object] - Decoded output.
        *path: str - Keys leading to the object.

    Returns:
        str | None - Its first key, or None when the path does not lead to one.

    """
    node: object = data
    for key in path:
        node = _field(node, key)
    if not isinstance(node, dict):
        return None
    return next(iter(cast("dict[str, object]", node)), None)


def _text(value: object) -> str | None:
    """Accept a string field.

    Args:
        value: object - Raw field.

    Returns:
        str | None - The string, or None.

    """
    return value if isinstance(value, str) else None


def parse_answer(name: str, stdout: str) -> tuple[str, str | None, str | None]:
    """Unwrap a CLI's output envelope.

    Args:
        name: str - Vendor name.
        stdout: str - What the CLI printed.

    Returns:
        tuple[str, str | None, str | None] - The answer text, the model the CLI
            reports, and an error the CLI reports; output that is not the
            expected envelope comes back whole as the text.

    """
    if name in {"codex", "agy"}:
        return stdout, None, None
    try:
        decoded = cast("object", json.loads(stdout))
    except ValueError:
        return stdout, None, None
    if isinstance(decoded, list):
        # Event-stream output: the last object carrying a result string.
        items = cast("list[object]", decoded)
        events = [cast("dict[str, object]", e) for e in items if isinstance(e, dict)]
        decoded = next((e for e in reversed(events) if _text(e.get("result"))), None)
    if not isinstance(decoded, dict):
        return stdout, None, None
    data = cast("dict[str, object]", decoded)
    if name in {"claude", "cursor-agent"}:
        text = _text(data.get("result")) or stdout
        error = f"{name} reported an error: {text}" if data.get("is_error") else None
        model = _first_key(data, "modelUsage") if name == "claude" else None
        return text, model, error
    text = _text(data.get("response")) or _text(data.get("result")) or stdout
    failure = data.get("error")
    message = (
        _text(cast("dict[str, object]", failure).get("message"))
        if isinstance(failure, dict)
        else _text(failure)
    )
    error = f"{name} reported an error: {message}" if message else None
    return text, _first_key(data, "stats", "models"), error
