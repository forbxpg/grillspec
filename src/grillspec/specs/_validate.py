"""Run every rule that applies to one change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.config import Backend
from grillspec.state import ChangeError, list_changes, log_path

from ._openspec import CHANGES, MODIFIED, validate_openspec
from ._parse import parse_markdown
from ._plan import parse_plan, plan_findings
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


def _spec_scenarios(
    root: Path, backend: Backend, change_id: str
) -> tuple[set[str], int]:
    """Collect the spec's scenario IDs and its size, for the plan checks.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        tuple[set[str], int] - Scenario IDs of behaviour the change adds or
            modifies, and the spec files' total line count.

    """
    if backend is Backend.SUPERPOWERS:
        files = [log_path(root, backend, change_id)]
    else:
        folder = root / CHANGES / change_id
        files = [folder / "proposal.md", *sorted((folder / "specs").glob("**/*.md"))]
    ids: set[str] = set()
    lines = 0
    for path in files:
        if not path.is_file():
            continue
        doc = parse_markdown(path)
        lines += len(path.read_text(encoding="utf-8-sig").splitlines())
        for req in doc.requirements:
            if req.section in {"Requirements", "ADDED Requirements", MODIFIED}:
                ids.update(s.scenario_id for s in req.scenarios if s.scenario_id)
    return ids, lines


def _plan_path(root: Path, backend: Backend, change_id: str) -> Path:
    """Return where a change's plan lives.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        Path - Superpowers plan or OpenSpec ``tasks.md``.

    """
    if backend is Backend.SUPERPOWERS:
        return root / "docs" / "grillspec" / "plans" / f"{change_id}.md"
    return root / CHANGES / change_id / "tasks.md"


def plan_report(root: Path, backend: Backend, change_id: str) -> list[Finding]:
    """Check a change's plan, when it has one.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        list[Finding] - Plan findings; empty without a plan.

    """
    path = _plan_path(root, backend, change_id)
    if not path.is_file():
        return []
    ids, lines = _spec_scenarios(root, backend, change_id)
    return plan_findings(parse_plan(path), ids, lines, root)


def validate_change(
    root: Path, backend: Backend, change_id: str, *, include_plan: bool = True
) -> Report:
    """Check one change's spec against the bundled rules.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.
        include_plan: bool - Also check the plan when it exists.

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
    if include_plan:
        findings = [*findings, *plan_report(root, backend, change_id)]
    errors = tuple(f for f in findings if f.severity == ERROR)
    warnings = tuple(f for f in findings if f.severity != ERROR)
    return Report(change_id, errors, warnings)
