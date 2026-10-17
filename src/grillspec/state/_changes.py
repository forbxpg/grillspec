"""Discover changes from backend artifacts and approval sidecars."""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from grillspec.config import Backend

if TYPE_CHECKING:
    from collections.abc import Iterable

SIDECARS = Path(".grillspec") / "changes"
_SPECS = Path("docs") / "grillspec" / "specs"
_PLANS = Path("docs") / "grillspec" / "plans"
_OPENSPEC_CHANGES = Path("openspec") / "changes"


@dataclass(frozen=True)
class Change:
    """One change and how far it got.

    Attributes:
        id: str - Change id (file stem or OpenSpec change directory name).
        spec_path: Path | None - The spec artifact, when written.
        plan_path: Path | None - The plan artifact, when written.
        spec_approved: dt.date | None - When the user approved the spec.
        plan_approved: dt.date | None - When the user approved the plan.

    """

    id: str
    spec_path: Path | None
    plan_path: Path | None
    spec_approved: dt.date | None
    plan_approved: dt.date | None


def _existing(path: Path) -> Path | None:
    """Return the path when it is a file.

    Args:
        path: Path - Candidate file.

    Returns:
        Path | None - The path, or None when there is no such file.

    """
    return path if path.is_file() else None


def _artifacts(root: Path, backend: Backend, change_id: str) -> tuple[Path, Path]:
    """Return where a change's spec and plan live in a backend.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        tuple[Path, Path] - Spec path and plan path (they may not exist).

    """
    if backend is Backend.SUPERPOWERS:
        return root / _SPECS / f"{change_id}.md", root / _PLANS / f"{change_id}.md"
    folder = root / _OPENSPEC_CHANGES / change_id
    return folder / "proposal.md", folder / "tasks.md"


def _artifact_ids(root: Path, backend: Backend) -> Iterable[str]:
    """List change ids that have backend artifacts.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.

    Yields:
        str - Change ids.

    """
    if backend is Backend.SUPERPOWERS:
        for folder in (_SPECS, _PLANS):
            yield from (path.stem for path in (root / folder).glob("*.md"))
        return
    changes = root / _OPENSPEC_CHANGES
    if changes.is_dir():
        yield from (
            path.name
            for path in changes.iterdir()
            if path.is_dir() and path.name != "archive"
        )


def _date(data: dict[str, object], key: str) -> dt.date | None:
    """Read an approval date from a sidecar.

    Args:
        data: dict[str, object] - Parsed sidecar.
        key: str - ``spec_approved`` or ``plan_approved``.

    Returns:
        dt.date | None - The date when present and a TOML date.

    """
    value = data.get(key)
    return value if isinstance(value, dt.date) else None


def list_changes(root: Path, backend: Backend) -> tuple[Change, ...]:
    """List every change in the project, sorted by id.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.

    Returns:
        tuple[Change, ...] - Changes known from sidecars or backend artifacts.

    """
    ids = set(_artifact_ids(root, backend))
    ids.update(path.stem for path in (root / SIDECARS).glob("*.toml"))
    changes: list[Change] = []
    for change_id in sorted(ids):
        sidecar = root / SIDECARS / f"{change_id}.toml"
        data: dict[str, object] = (
            tomllib.loads(sidecar.read_text(encoding="utf-8"))
            if sidecar.is_file()
            else {}
        )
        spec, plan = _artifacts(root, backend, change_id)
        changes.append(
            Change(
                id=change_id,
                spec_path=_existing(spec),
                plan_path=_existing(plan),
                spec_approved=_date(data, "spec_approved"),
                plan_approved=_date(data, "plan_approved"),
            )
        )
    return tuple(changes)
