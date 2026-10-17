"""Brownfield signals for the backend recommendation, and CLI presence."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from grillspec.config import Backend

CODE_SUFFIXES = frozenset({
    ".c",
    ".cc",
    ".clj",
    ".cpp",
    ".cs",
    ".css",
    ".dart",
    ".erl",
    ".ex",
    ".exs",
    ".go",
    ".groovy",
    ".h",
    ".hs",
    ".htm",
    ".html",
    ".java",
    ".jl",
    ".js",
    ".jsx",
    ".kt",
    ".less",
    ".lua",
    ".m",
    ".ml",
    ".mm",
    ".php",
    ".ps1",
    ".py",
    ".r",
    ".rb",
    ".rs",
    ".sass",
    ".scala",
    ".scss",
    ".sh",
    ".sql",
    ".svelte",
    ".swift",
    ".tf",
    ".ts",
    ".tsx",
    ".vue",
    ".zig",
})
SKIPPED_DIRS = frozenset({".git", ".venv", "node_modules", "docs", "dist", "build"})
LONG_HISTORY = 100
AGENT_CLIS = ("claude", "cursor-agent", "codex", "agy", "gigacode")


@dataclass(frozen=True)
class Signals:
    """Evidence that a project is long-lived.

    Attributes:
        has_source: bool - Source code exists outside ``docs/``.
        has_openspec: bool - An ``openspec/`` directory exists.
        commit_count: int - Commits reachable from HEAD; 0 outside git.

    """

    has_source: bool
    has_openspec: bool
    commit_count: int


def _has_source(root: Path) -> bool:
    """Tell whether the project holds source code outside skipped directories.

    Args:
        root: Path - Project root.

    Returns:
        bool - True when any code file exists.

    """
    for _, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
        if any(Path(name).suffix in CODE_SUFFIXES for name in files):
            return True
    return False


def _commit_count(root: Path) -> int:
    """Count commits reachable from HEAD.

    Args:
        root: Path - Project root.

    Returns:
        int - The count; 0 when the root is not itself a repository (a parent
            repository's history does not count) or git is missing.

    """
    git = shutil.which("git")
    # `git -C` walks up to a parent repository; only this project's history counts.
    if git is None or not (root / ".git").exists():
        return 0
    # A fixed argv without a shell; the only variable is the -C directory value.
    # nosemgrep
    done = subprocess.run(
        [git, "-C", str(root), "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(done.stdout.strip()) if done.returncode == 0 else 0


def brownfield_signals(root: Path) -> Signals:
    """Collect brownfield signals for a project.

    Args:
        root: Path - Project root.

    Returns:
        Signals - What was found.

    """
    return Signals(
        has_source=_has_source(root),
        has_openspec=(root / "openspec").is_dir(),
        commit_count=_commit_count(root),
    )


def recommend_backend(signals: Signals) -> Backend:
    """Recommend a spec backend from brownfield signals.

    Args:
        signals: Signals - Collected signals.

    Returns:
        Backend - OpenSpec for long-lived projects, Superpowers otherwise.

    """
    long_lived = (
        signals.has_openspec
        or signals.has_source
        or signals.commit_count >= LONG_HISTORY
    )
    return Backend.OPENSPEC if long_lived else Backend.SUPERPOWERS


def available_clis() -> dict[str, bool]:
    """Report which agent CLIs are on PATH (presence only, not authentication).

    Returns:
        dict[str, bool] - CLI name to presence.

    """
    return {name: shutil.which(name) is not None for name in AGENT_CLIS}
