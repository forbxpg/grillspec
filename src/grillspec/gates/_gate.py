"""Decide whether a tool call may run in the active change's phase."""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from grillspec.config import Backend, load_config
from grillspec.state import Phase, compute_status, gates_pause
from grillspec.state._layout import OPENSPEC_CHANGES, PLANS, SPECS

from ._shell import shell_targets

if TYPE_CHECKING:
    from grillspec.config import Config
    from grillspec.state import Status

GATED = frozenset({Phase.GRILL, Phase.SPEC, Phase.PLAN})
_SHORT = 80
_PAUSE = re.compile(r"\bgrillspec\b.*\bgate\s+pause\b|\bgate\s+pause\b.*grillspec")
_BYPASS = "To bypass, the user runs grillspec gate pause in their own terminal."
PAUSE_REFUSAL = (
    "grillspec gate: only the user may pause gates; ask them to run "
    "grillspec gate pause in their own terminal."
)


@dataclass(frozen=True)
class ToolCall:
    """A tool call reduced to what the gate needs.

    Attributes:
        kind: Literal["edit", "shell"] - A file edit or a shell command.
        paths: tuple[str, ...] - Files an edit touches, absolute or relative to
            the project root.
        command: str - The shell command line.
        cwd: str - Directory relative paths start from; the root when empty.

    """

    kind: Literal["edit", "shell"]
    paths: tuple[str, ...] = ()
    command: str = ""
    cwd: str = ""


def _norm(path: str) -> str:
    """Normalise a path for comparison.

    Args:
        path: str - Absolute path.

    Returns:
        str - Real, absolute, and case-folded on Windows.

    """
    return os.path.normcase(os.path.realpath(path))


def _relative(root: Path, path: str) -> str | None:
    """Return a path relative to the root, POSIX style, or None outside it.

    Args:
        root: Path - Project root.
        path: str - Absolute, or relative to the root.

    Returns:
        str | None - The relative path.

    """
    full = path if Path(path).is_absolute() else str(root / path)
    base = _norm(str(root))
    try:
        rel = os.path.relpath(_norm(full), base)
    except ValueError:  # another drive on Windows
        return None
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel.replace(os.sep, "/")


def _artifacts(config: Config, change_id: str) -> tuple[list[str], list[str]]:
    """Return the folders and files a gated change may edit, relative to the root.

    Args:
        config: Config - Effective configuration.
        change_id: str - The active change.

    Returns:
        tuple[list[str], list[str]] - Folder prefixes and exact files.

    """
    folders = [".grillspec"]
    if config.backend is Backend.OPENSPEC:
        return [*folders, (OPENSPEC_CHANGES / change_id).as_posix()], []
    files = [
        (SPECS / f"{change_id}.md").as_posix(),
        (PLANS / f"{change_id}.md").as_posix(),
    ]
    return folders, files


def _allowed(rel: str, config: Config, change_id: str) -> bool:
    """Tell whether a gated change may edit a path inside the project.

    Args:
        rel: str - Path relative to the root, POSIX style.
        config: Config - Effective configuration.
        change_id: str - The active change.

    Returns:
        bool - True for the change's artifacts and ``[gates] allow`` globs.

    """
    fold = os.path.normcase
    folders, files = _artifacts(config, change_id)
    if any(fold(rel) == fold(name) for name in files):
        return True
    if any(
        fold(rel) == fold(d) or fold(rel).startswith(fold(d + "/")) for d in folders
    ):
        return True
    return any(fnmatch.fnmatch(rel, pattern) for pattern in config.gates_allow)


def _refusal(status: Status, subject: str) -> str:
    step = status.next_step.rstrip(".")
    return (
        f"grillspec gate: {status.change_id} is in the {status.phase} phase, so only "
        f"its spec artifacts may change; {subject} is outside them. Next: {step}. "
        f"{_BYPASS}"
    )


def _subjects(root: Path, call: ToolCall) -> list[str] | None:
    """Return the paths a call writes, or None when a writer's target is unknown.

    Args:
        root: Path - Project root.
        call: ToolCall - The tool call.

    Returns:
        list[str] | None - Paths relative to the root (outside paths dropped).

    """
    if call.kind == "edit":
        paths = list(call.paths)
    else:
        paths, unknown = shell_targets(call.command)
        if unknown:
            return None
    base = Path(call.cwd) if call.cwd else root
    absolute = (
        path if Path(path).is_absolute() else str(base / path) for path in paths
    )
    relative = (_relative(root, path) for path in absolute)
    return [rel for rel in relative if rel is not None]


def _gated(root: Path) -> tuple[Config, Status] | None:
    """Return the configuration and status when the gate is in force.

    Args:
        root: Path - Project root.

    Returns:
        tuple[Config, Status] | None - None when gates are off, nothing is
            active, or the active change is past its plan.

    """
    config = load_config(root).config
    if not config.gates_enabled or config.backend is None:
        return None
    status = compute_status(root, config)
    if status.change_id is None or status.phase not in GATED:
        return None
    return config, status


def _decide(root: Path, call: ToolCall) -> str | None:
    gated = _gated(root)
    if gated is None:
        return None
    config, status = gated
    if call.kind == "shell" and _PAUSE.search(call.command):
        return PAUSE_REFUSAL
    if gates_pause(root) == (status.change_id, str(status.phase)):
        return None
    subjects = _subjects(root, call)
    if subjects is None:
        command = " ".join(call.command.split())
        short = command if len(command) <= _SHORT else command[: _SHORT - 3] + "..."
        return _refusal(status, f"`{short}`")
    outside = (
        rel for rel in subjects if not _allowed(rel, config, status.change_id or "")
    )
    rel = next(outside, None)
    return None if rel is None else _refusal(status, rel)


def decide(root: Path, call: ToolCall) -> str | None:
    """Decide a tool call; never raises.

    Args:
        root: Path - Project root.
        call: ToolCall - The tool call.

    Returns:
        str | None - The one-line refusal, or None when the gate has no opinion
            (including on any error: gates fail open).

    """
    try:
        return _decide(root, call)
    except Exception:  # ruff: ignore[blind-except] - a gate must never block on its own failure
        return None
