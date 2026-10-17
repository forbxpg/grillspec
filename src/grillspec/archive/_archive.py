"""Close a done change: merge OpenSpec deltas, or mark a superpowers change."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from grillspec.config import Backend
from grillspec.council import resolve_cli, run_tree
from grillspec.paths import write_atomic
from grillspec.specs import validate_change
from grillspec.state import (
    Phase,
    clear_active,
    compute_status,
    mark_archived,
)

from ._merge import MergeError, apply_delta, new_spec, parse_delta, parse_living

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path

    from grillspec.config import Config

CHANGES = ("openspec", "changes")
LIVING = ("openspec", "specs")
_TIMEOUT = 120


class ArchiveError(Exception):
    """The change cannot be archived as asked; nothing was written."""


def _openspec_cli() -> str | None:
    """Return the OpenSpec CLI when it runs at all.

    Returns:
        str | None - Its path, or None when it is missing or broken.

    """
    executable = resolve_cli("openspec")
    if executable is None:
        return None
    try:
        done = run_tree([executable, "--version"], stdin=None, timeout=30)
    except OSError:
        return None
    return executable if done.returncode == 0 else None


def _merge_one(
    root: Path, change_id: str, delta_path: Path, specs: Path
) -> tuple[Path, str, list[str]] | None:
    """Compute one capability's new living spec.

    Args:
        root: Path - Project root.
        change_id: str - Change id.
        delta_path: Path - The delta ``spec.md``.
        specs: Path - The change's ``specs`` folder.

    Returns:
        tuple[Path, str, list[str]] | None - Living spec path, its new text and
            the operations; None when the file holds no delta.

    Raises:
        MergeError: If a delta cannot be applied.

    """
    capability = delta_path.parent.relative_to(specs).as_posix()
    delta, renames, purpose = parse_delta(delta_path.read_text(encoding="utf-8"))
    if not delta and not renames:
        return None
    living_path = root.joinpath(*LIVING, *capability.split("/"), "spec.md")
    ops: list[str] = []
    if living_path.is_file():
        with living_path.open(encoding="utf-8", newline="") as handle:
            living = parse_living(handle.read())
    elif renames or delta.get("MODIFIED"):
        msg = f"{capability}: MODIFIED and RENAMED need an existing living spec"
        raise MergeError(msg)
    else:
        living = new_spec(capability, purpose, change_id)
        ops.append(f"{capability}: create spec")
    merged, done = apply_delta(living, delta, renames, capability)
    return living_path, merged.render(), [*ops, *done]


def _plan_merge(root: Path, change_id: str) -> tuple[dict[Path, str], list[str]]:
    """Compute every living spec's new text, refusing on any conflict.

    Args:
        root: Path - Project root.
        change_id: str - Change id.

    Returns:
        tuple[dict[Path, str], list[str]] - New text per living spec file, and
            one line per operation.

    Raises:
        ArchiveError: If a delta cannot be applied.

    """
    specs = root.joinpath(*CHANGES, change_id, "specs")
    writes: dict[Path, str] = {}
    ops: list[str] = []
    for delta_path in sorted(specs.glob("**/spec.md")) if specs.is_dir() else []:
        try:
            result = _merge_one(root, change_id, delta_path, specs)
        except MergeError as error:
            raise ArchiveError(str(error)) from None
        if result is not None:
            writes[result[0]] = result[1]
            ops.extend(result[2])
    return writes, ops


def _archive_openspec(
    root: Path, change_id: str, *, today: dt.date, dry_run: bool
) -> list[str]:
    """Archive an OpenSpec change through its CLI, or the bundled merge.

    Args:
        root: Path - Project root.
        change_id: str - Change id.
        today: dt.date - Archive date.
        dry_run: bool - Report the operations without writing anything.

    Returns:
        list[str] - One line per operation.

    Raises:
        ArchiveError: On validator errors, an existing archive folder, a
            conflicting delta, or a failed OpenSpec CLI run.

    """
    report = validate_change(root, Backend.OPENSPEC, change_id)
    if report.errors:
        msg = f"{len(report.errors)} validator error(s); run grillspec validate"
        raise ArchiveError(msg)
    target = root.joinpath(*CHANGES, "archive", f"{today.isoformat()}-{change_id}")
    if target.exists():
        msg = f"{target.relative_to(root).as_posix()} already exists"
        raise ArchiveError(msg)
    cli = _openspec_cli()
    writes, ops = _plan_merge(root, change_id)
    if cli is not None:
        ops = [f"openspec archive {change_id} --yes", *ops]
    ops.append(f"move to {target.relative_to(root).as_posix()}")
    if dry_run:
        return ops
    if cli is not None:
        argv = [cli, "archive", change_id, "--yes"]
        done = run_tree(argv, stdin=None, timeout=_TIMEOUT, cwd=root)
        if done.returncode != 0:
            tail = done.stderr.decode("utf-8", "replace").strip().splitlines()
            msg = f"openspec archive failed: {tail[-1] if tail else 'no output'}"
            raise ArchiveError(msg)
        clear_active(root)
        return ops[:1]
    for path, text in writes.items():
        write_atomic(path, text)
    target.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.move(str(root.joinpath(*CHANGES, change_id)), str(target))
    clear_active(root)
    return ops


def archive_change(
    root: Path, config: Config, *, today: dt.date, dry_run: bool = False
) -> list[str]:
    """Archive the active change once it is done.

    Args:
        root: Path - Project root.
        config: Config - Effective configuration.
        today: dt.date - Archive date.
        dry_run: bool - Report the operations without writing anything.

    Returns:
        list[str] - One line per operation.

    Raises:
        ArchiveError: If the change is not done, has validator errors, its
            archive folder exists, or a delta conflicts.

    """
    status = compute_status(root, config)
    if status.change_id is None or status.phase is not Phase.DONE:
        msg = f"the change is not done: {status.next_step}"
        raise ArchiveError(msg)
    change_id = status.change_id
    if config.backend is Backend.SUPERPOWERS:
        if not dry_run:
            _ = mark_archived(root, change_id, today=today)
            clear_active(root)
        return [f"mark {change_id} archived ({today.isoformat()})"]
    return _archive_openspec(root, change_id, today=today, dry_run=dry_run)
