"""Write the project's config, ignore rule, AGENTS.md block and imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.blocks import ensure_line, upsert_block
from grillspec.paths import template

if TYPE_CHECKING:
    from pathlib import Path

    from grillspec.config import Backend

STATE_IGNORE = ".grillspec/state.json"
AGENTS_IMPORT = "@AGENTS.md"
IMPORTERS = ("CLAUDE.md", "GIGACODE.md")


def _read(path: Path) -> str:
    """Read a text file, or return empty text when it does not exist.

    Args:
        path: Path - File to read.

    Returns:
        str - Content.

    """
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def init_project(
    root: Path, backend: Backend, *, dry_run: bool = False
) -> tuple[Path, ...]:
    """Set grillspec up in a project, idempotently.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend for a new config file.
        dry_run: bool - Report planned changes without writing.

    Returns:
        tuple[Path, ...] - Files changed (or that would change).

    """
    config = root / ".grillspec" / "config.toml"
    targets: dict[Path, str] = {}
    if not config.is_file():
        targets[config] = template("config.toml").replace("__BACKEND__", str(backend))
    gitignore = root / ".gitignore"
    targets[gitignore] = ensure_line(_read(gitignore), STATE_IGNORE)
    agents = root / "AGENTS.md"
    targets[agents] = upsert_block(_read(agents), template("agents-block.md"))
    for name in IMPORTERS:
        path = root / name
        if path.is_file():
            targets[path] = ensure_line(_read(path), AGENTS_IMPORT)
    changed = tuple(
        path
        for path, text in targets.items()
        if not path.is_file() or _read(path) != text
    )
    if not dry_run:
        for path in changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as handle:
                _ = handle.write(targets[path])
    return changed
