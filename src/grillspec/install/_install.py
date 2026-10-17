"""Copy skills into a harness and undo exactly that."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from grillspec.blocks import ensure_line, remove_line
from grillspec.config import ConfigError
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


class InstallConflictError(Exception):
    """Install would overwrite files grillspec does not own.

    Attributes:
        paths: tuple[Path, ...] - The conflicting files.

    """

    def __init__(self, paths: tuple[Path, ...]) -> None:
        listed = ", ".join(str(path) for path in paths)
        super().__init__(
            f"refusing to overwrite files grillspec did not write: {listed}"
        )
        self.paths: tuple[Path, ...] = paths


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


def _import_line(harness: Harness, scope: Scope, base: Path) -> str:
    """Return the exact import line grillspec adds to a GigaCode context file.

    Args:
        harness: Harness - Target harness (GigaCode).
        scope: Scope - Install scope.
        base: Path - Directory install paths are relative to.

    Returns:
        str - ``@`` plus the router path relative to the context file.

    """
    context = base / GIGACODE_CONTEXT[scope]
    router = base / SKILL_DIRS[harness, scope] / ROUTER
    return "@" + Path(os.path.relpath(router, context.parent)).as_posix()


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

    Raises:
        InstallConflictError: If a destination exists that this harness's install
            did not write; nothing is written then.

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
        line = _import_line(harness, scope, base)
        # A line the user already has is theirs: never record it, never remove it.
        if line not in _read(context).splitlines():
            lines.append({
                "file": context.relative_to(base).as_posix(),
                "line": line,
                "created": "no" if context.exists() else "yes",
            })
            planned.append(context)
    receipt = receipt_path(scope, root)
    installs = read_receipt(receipt)
    owned = set(cast("list[str]", installs.get(str(harness), {}).get("files", [])))
    conflicts = tuple(
        destination
        for destination in copies
        if destination.exists()
        and destination.relative_to(base).as_posix() not in owned
    )
    if conflicts:
        raise InstallConflictError(conflicts)
    if dry_run:
        return InstallResult(tuple(planned), None)
    for destination, origin in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copyfile(origin, destination)
    for entry in lines:
        path = base / entry["file"]
        _write(path, ensure_line(_read(path), entry["line"]))
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


def _check_recorded(
    receipt: Path,
    base: Path,
    skills: Path,
    entry: dict[str, object],
    *,
    scope: Scope,
) -> None:
    """Refuse a receipt that points outside what an install can write.

    A receipt can arrive through a clone, so it is input, not truth: every file
    must sit inside the harness's skill directory and every edited line must be in
    the GigaCode context file.

    Args:
        receipt: Path - The receipt file, for the error message.
        base: Path - Directory recorded paths are relative to.
        skills: Path - The harness's skill directory.
        entry: dict[str, object] - The harness's receipt entry.
        scope: Scope - Install scope.

    Raises:
        ConfigError: If any recorded path is absolute, climbs with ``..`` or lies
            outside the allowed places.

    """
    allowed = skills.resolve()
    for relative in cast("list[str]", entry.get("files", [])):
        path = Path(relative)
        inside = (base / path).resolve().is_relative_to(allowed)
        if path.is_absolute() or ".." in path.parts or not inside:
            msg = f"{receipt}: refusing to remove {relative!r}, outside {skills}"
            raise ConfigError(msg)
    context = GIGACODE_CONTEXT[scope].as_posix()
    expected = _import_line(Harness.GIGACODE, scope, base)
    for line in cast("list[dict[str, str]]", entry.get("lines", [])):
        if line.get("file") != context or line.get("line") != expected:
            recorded = f"{line.get('file')!r}: {line.get('line')!r}"
            msg = f"{receipt}: refusing to edit {recorded}"
            raise ConfigError(msg)


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
    _check_recorded(receipt, base, stop, entry, scope=scope)
    files = cast("list[str]", entry.get("files", []))
    lines = cast("list[dict[str, str]]", entry.get("lines", []))
    touched: list[Path] = []
    for relative in files:
        path = base / relative
        if path.is_file():
            path.unlink()
            touched.append(path)
            _prune(path.parent, base)
    for line in lines:
        path = base / line["file"]
        if not path.is_file():
            continue
        remaining = remove_line(_read(path), line["line"])
        if line.get("created") == "yes" and not remaining.strip():
            path.unlink()
            _prune(path.parent, base)
        else:
            _write(path, remaining)
        touched.append(path)
    write_receipt(receipt, installs)
    _prune(receipt.parent, base)
    return tuple(touched)
