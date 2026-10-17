"""Copy skills into a harness and undo exactly that."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from grillspec.blocks import ensure_line, remove_line
from grillspec.hooks import Harness
from grillspec.paths import data_root

from ._receipt import read_receipt, write_receipt
from ._targets import (
    GIGACODE_CONTEXT,
    NATIVE_COMMANDS,
    SKILL_DIRS,
    Scope,
    base_dir,
    receipt_path,
)

ROUTER = Path("using-grillspec") / "SKILL.md"


@dataclass(frozen=True)
class InstallResult:
    """What an install did or would do.

    Attributes:
        planned: tuple[Path, ...] - Files written (or to be written on a dry run).
        native_command: str | None - The harness's own install command, printed
            instead of copying when the harness has a plugin system.

    """

    planned: tuple[Path, ...]
    native_command: str | None


def _read(path: Path) -> str:
    """Read a text file keeping its newlines, or empty text when missing.

    Args:
        path: Path - File to read.

    Returns:
        str - Content.

    """
    if not path.is_file():
        return ""
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path: Path, text: str) -> None:
    """Write a text file exactly as given.

    Args:
        path: Path - File to write.
        text: str - Content.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        _ = handle.write(text)


def install(
    harness: Harness, scope: Scope, *, root: Path, copy: bool, dry_run: bool
) -> InstallResult:
    """Install grillspec's skills for a harness.

    Args:
        harness: Harness - Target harness.
        scope: Scope - Project or user install.
        root: Path - Project root.
        copy: bool - Copy files even when the harness has native plugins.
        dry_run: bool - Report planned writes without writing.

    Returns:
        InstallResult - Planned or written files, or the native command.

    """
    native = NATIVE_COMMANDS.get(harness)
    if native is not None and not copy:
        return InstallResult((), native)
    base = base_dir(scope, root)
    target = base / SKILL_DIRS[harness, scope]
    source = data_root() / "skills"
    copies = {
        target / path.relative_to(source): path
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }
    lines: list[dict[str, str]] = []
    planned = list(copies)
    if harness is Harness.GIGACODE:
        context = base / GIGACODE_CONTEXT[scope]
        relative = Path(os.path.relpath(target / ROUTER, context.parent)).as_posix()
        lines.append({
            "file": context.relative_to(base).as_posix(),
            "line": f"@{relative}",
        })
        planned.append(context)
    if dry_run:
        return InstallResult(tuple(planned), None)
    for destination, origin in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copyfile(origin, destination)
    for entry in lines:
        path = base / entry["file"]
        _write(path, ensure_line(_read(path), entry["line"]))
    receipt = receipt_path(scope, root)
    installs = read_receipt(receipt)
    installs[str(harness)] = {
        "scope": str(scope),
        "files": [path.relative_to(base).as_posix() for path in copies],
        "lines": lines,
    }
    write_receipt(receipt, installs)
    return InstallResult(tuple(planned), None)


def _prune(directory: Path, stop: Path) -> None:
    """Remove empty directories upward from ``directory`` until ``stop``.

    Args:
        directory: Path - Deepest directory to try.
        stop: Path - Directory never removed.

    """
    while directory != stop and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def uninstall(harness: Harness, scope: Scope, *, root: Path) -> tuple[Path, ...]:
    """Remove exactly what an install of a harness recorded.

    Args:
        harness: Harness - Target harness.
        scope: Scope - Project or user install.
        root: Path - Project root.

    Returns:
        tuple[Path, ...] - Files removed or edited.

    """
    receipt = receipt_path(scope, root)
    installs = read_receipt(receipt)
    entry = installs.pop(str(harness), None)
    if entry is None:
        return ()
    base = base_dir(scope, root)
    stop = base / SKILL_DIRS[harness, scope]
    touched: list[Path] = []
    for relative in cast("list[str]", entry.get("files", [])):
        path = base / relative
        if path.is_file():
            path.unlink()
            touched.append(path)
            _prune(path.parent, stop.parent)
    for line in cast("list[dict[str, str]]", entry.get("lines", [])):
        path = base / line["file"]
        if path.is_file():
            _write(path, remove_line(_read(path), line["line"]))
            touched.append(path)
    write_receipt(receipt, installs)
    return tuple(touched)
