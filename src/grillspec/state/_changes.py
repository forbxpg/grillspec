"""Discover changes from backend artifacts and approval sidecars."""

from __future__ import annotations

import datetime as dt
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec.config import Backend, ConfigError
from grillspec.markdown import lines_outside_fences

from ._hash import artifact_hash
from ._layout import OPENSPEC_CHANGES as _OPENSPEC_CHANGES
from ._layout import PLANS as _PLANS
from ._layout import SPECS as _SPECS
from ._layout import log_path

if TYPE_CHECKING:
    from collections.abc import Iterable

SIDECARS = Path(".grillspec") / "changes"
_ARCHIVE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_OPEN_ITEM = re.compile(r"^\s*[-*+] \[ \]")
LOG_HEADING = "## Decision log"


@dataclass(frozen=True)
class Change:
    """One change and how far it got.

    Attributes:
        id: str - Change id (file stem or OpenSpec change directory name).
        spec_path: Path | None - The spec artifact, when written.
        plan_path: Path | None - The plan artifact, when written.
        spec_approved: dt.date | None - When the user approved the spec.
        plan_approved: dt.date | None - When the user approved the plan.
        grilled: dt.date | None - When the user confirmed the grill's shared
            understanding.
        log_path: Path | None - The decision log, when written: the spec file
            (superpowers) or ``design.md`` (OpenSpec).
        spec_stale: bool - The spec changed since it was approved (its
            ``spec_hash`` no longer matches).

    """

    id: str
    spec_path: Path | None
    plan_path: Path | None
    spec_approved: dt.date | None
    plan_approved: dt.date | None
    grilled: dt.date | None = None
    log_path: Path | None = None
    spec_stale: bool = False


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


def open_questions(log: Path | None) -> int:
    """Count the open questions in a decision log.

    Open questions are unchecked list items inside the ``## Decision log``
    section, outside fenced code blocks.

    Args:
        log: Path | None - The decision log, or None.

    Returns:
        int - The count; 0 without a log or without the section.

    Raises:
        ConfigError: If the log is not valid UTF-8.

    """
    if log is None or not log.is_file():
        return 0
    try:
        text = log.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        msg = f"{log}: decision log is not UTF-8 ({error}); re-save it as UTF-8"
        raise ConfigError(msg) from error
    count = 0
    inside = False
    for line in lines_outside_fences(text):
        if line.startswith("## "):
            inside = line.strip() == LOG_HEADING
        elif inside and _OPEN_ITEM.match(line):
            count += 1
    return count


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


def _date(data: dict[str, object], key: str, sidecar: Path) -> dt.date | None:
    """Read an approval date from a sidecar.

    Accepts a TOML date or date-time, or an ISO date or date-time string; a
    date-time counts as its date.

    Args:
        data: dict[str, object] - Parsed sidecar.
        key: str - ``spec_approved`` or ``plan_approved``.
        sidecar: Path - The sidecar file, for the error message.

    Returns:
        dt.date | None - The date, or None when the key is absent.

    Raises:
        ConfigError: If the value is neither a date nor an ISO date string.

    """
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value).date()
        except ValueError:
            pass
    msg = f"{sidecar}: {key} must be a date like 2026-10-17, got {value!r}"
    raise ConfigError(msg)


_HASH = re.compile(r"sha256:[0-9a-f]{64}")


def spec_hash(data: dict[str, object], sidecar: Path) -> str | None:
    """Read the approved spec's fingerprint from a sidecar.

    Args:
        data: dict[str, object] - Parsed sidecar.
        sidecar: Path - The sidecar file, for the error message.

    Returns:
        str | None - ``sha256:<hex>``, or None when the key is absent.

    Raises:
        ConfigError: If the value is not ``sha256:`` and 64 hex digits.

    """
    value = data.get("spec_hash")
    if value is None:
        return None
    if isinstance(value, str) and _HASH.fullmatch(value):
        return value
    msg = f"{sidecar}: spec_hash must be sha256:<64 hex digits>, got {value!r}"
    raise ConfigError(msg)


def read_sidecar(sidecar: Path) -> dict[str, object]:
    """Parse a sidecar, or return nothing when it does not exist.

    Args:
        sidecar: Path - The sidecar file.

    Returns:
        dict[str, object] - Parsed content.

    Raises:
        ConfigError: If the file is not valid UTF-8 TOML or has another version.

    """
    if not sidecar.is_file():
        return {}
    try:
        data = tomllib.loads(sidecar.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        msg = f"{sidecar}: invalid TOML: {error}"
        raise ConfigError(msg) from error
    version = cast("object", data.get("version", 1))
    if type(version) is not int or version != 1:
        msg = f"{sidecar}: unsupported version {version!r}; this grillspec reads 1"
        raise ConfigError(msg)
    return data


def archived_ids(root: Path, backend: Backend) -> set[str]:
    """List change ids OpenSpec has archived (``archive/YYYY-MM-DD-<id>``).

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.

    Returns:
        set[str] - Archived change ids; empty for the Superpowers backend.

    """
    archive = root / _OPENSPEC_CHANGES / "archive"
    if backend is not Backend.OPENSPEC or not archive.is_dir():
        return set()
    return {
        _ARCHIVE_DATE.sub("", path.name) for path in archive.iterdir() if path.is_dir()
    }


def _stale(root: Path, backend: Backend, change_id: str, approved: str | None) -> bool:
    """Tell whether an approved spec changed since its approval.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.
        approved: str | None - The fingerprint recorded at approval.

    Returns:
        bool - True when a fingerprint was recorded and no longer matches; a
            sidecar approved before fingerprints existed never counts as stale.

    """
    if approved is None:
        return False
    return artifact_hash(root, backend, change_id) != approved


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
    ids -= archived_ids(root, backend) - set(_artifact_ids(root, backend))
    changes: list[Change] = []
    for change_id in sorted(ids):
        sidecar = root / SIDECARS / f"{change_id}.toml"
        data = read_sidecar(sidecar)
        spec, plan = _artifacts(root, backend, change_id)
        changes.append(
            Change(
                id=change_id,
                spec_path=_existing(spec),
                plan_path=_existing(plan),
                spec_approved=_date(data, "spec_approved", sidecar),
                plan_approved=_date(data, "plan_approved", sidecar),
                grilled=_date(data, "grilled", sidecar),
                log_path=_existing(log_path(root, backend, change_id)),
                spec_stale=_stale(root, backend, change_id, spec_hash(data, sidecar)),
            )
        )
    return tuple(changes)
