"""Run every rule that applies to one change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.config import Backend
from grillspec.state import ChangeError, list_changes, log_path

from ._openspec import validate_openspec
from ._parse import parse_markdown
from ._report import ERROR, Finding, Report
from ._rules import (
    duplicate_ids,
    log_findings,
    missing_sections,
    relative,
    requirement_findings,
)

if TYPE_CHECKING:
    from pathlib import Path

_SUPERPOWERS_SECTIONS = ("Intent", "Requirements")


def _superpowers(root: Path, change_id: str) -> list[Finding]:
    """Check a superpowers spec: one file holding the log and the requirements.

    Args:
        root: Path - Project root.
        change_id: str - Change id.

    Returns:
        list[Finding] - Every problem.

    """
    path = log_path(root, Backend.SUPERPOWERS, change_id)
    if not path.is_file():
        return missing_sections(None, relative(path, root), _SUPERPOWERS_SECTIONS)
    doc = parse_markdown(path)
    return [
        *missing_sections(doc, relative(path, root), _SUPERPOWERS_SECTIONS),
        *log_findings(doc, doc, root),
        *requirement_findings(doc, root),
        *duplicate_ids([doc], root),
    ]


def validate_change(root: Path, backend: Backend, change_id: str) -> Report:
    """Check one change's spec against the bundled rules.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        Report - Errors and warnings, in file order.

    Raises:
        ChangeError: If the project has no such change.

    """
    if change_id not in {change.id for change in list_changes(root, backend)}:
        msg = f"no change {change_id}"
        raise ChangeError(msg)
    if backend is Backend.SUPERPOWERS:
        findings = _superpowers(root, change_id)
    else:
        findings = validate_openspec(root, change_id)
    errors = tuple(f for f in findings if f.severity == ERROR)
    warnings = tuple(f for f in findings if f.severity != ERROR)
    return Report(change_id, errors, warnings)
