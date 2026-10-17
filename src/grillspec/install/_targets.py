"""Where each harness reads skills, and how it installs plugins natively."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from grillspec.config import user_config_path
from grillspec.hooks import Harness

REPO = "forbxpg/grillspec"


class Scope(StrEnum):
    """Install for one project or for the whole user account."""

    PROJECT = "project"
    USER = "user"


SKILL_DIRS: dict[tuple[Harness, Scope], Path] = {
    (Harness.CLAUDE, Scope.PROJECT): Path(".claude/skills"),
    (Harness.CURSOR, Scope.PROJECT): Path(".cursor/skills"),
    (Harness.CODEX, Scope.PROJECT): Path(".agents/skills"),
    (Harness.ANTIGRAVITY, Scope.PROJECT): Path(".agents/skills"),
    (Harness.GIGACODE, Scope.PROJECT): Path(".gigacode/skills"),
    (Harness.CLAUDE, Scope.USER): Path(".claude/skills"),
    (Harness.CURSOR, Scope.USER): Path(".cursor/skills"),
    (Harness.CODEX, Scope.USER): Path(".agents/skills"),
    (Harness.ANTIGRAVITY, Scope.USER): Path(".gemini/config/skills"),
    (Harness.GIGACODE, Scope.USER): Path(".gigacode/skills"),
}

GIGACODE_CONTEXT = {
    Scope.PROJECT: Path("GIGACODE.md"),
    Scope.USER: Path(".gigacode/GIGACODE.md"),
}

NATIVE_COMMANDS = {
    Harness.CLAUDE: (
        f"claude plugin marketplace add {REPO} && "
        "claude plugin install grillspec@grillspec"
    ),
    Harness.CODEX: f"codex plugin marketplace add {REPO}, then /plugins",
    Harness.CURSOR: f"In Cursor: /add-plugin {REPO} (unverified)",
    Harness.ANTIGRAVITY: f"agy plugin install https://github.com/{REPO}",
}


def base_dir(scope: Scope, root: Path) -> Path:
    """Return the directory install paths are relative to.

    Args:
        scope: Scope - Install scope.
        root: Path - Project root.

    Returns:
        Path - The project root, or the user's home directory.

    """
    return root if scope is Scope.PROJECT else Path.home()


def receipt_path(scope: Scope, root: Path) -> Path:
    """Return where the install receipt for a scope lives.

    Args:
        scope: Scope - Install scope.
        root: Path - Project root.

    Returns:
        Path - The receipt file.

    """
    if scope is Scope.PROJECT:
        return root / ".grillspec" / "install-receipt.json"
    return user_config_path().parent / "install-receipt.json"
