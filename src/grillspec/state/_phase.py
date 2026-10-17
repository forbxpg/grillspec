"""Derive the phase of the active change from its artifacts and approvals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from ._changes import list_changes
from ._store import active_change_id

if TYPE_CHECKING:
    from pathlib import Path

    from grillspec.config import Config

    from ._changes import Change

_UNCHECKED = re.compile(r"^\s*- \[ \]", re.MULTILINE)


class Phase(StrEnum):
    """Where the active change stands."""

    IDLE = "idle"
    SPEC = "spec"
    PLAN = "plan"
    EXECUTE = "execute"
    DONE = "done"


_NEXT = {
    Phase.IDLE: "start a change with the grilling skill",
    Phase.SPEC: "write and approve the spec",
    Phase.PLAN: "write and approve the plan",
    Phase.EXECUTE: "execute the plan",
    Phase.DONE: "archive the change",
}


@dataclass(frozen=True)
class Status:
    """The phase of this working tree and what to do next.

    Attributes:
        phase: Phase - Derived phase.
        change_id: str | None - Active change, if any.
        next_step: str - The next thing to do.
        warnings: tuple[str, ...] - Problems found while reading state.

    """

    phase: Phase
    change_id: str | None
    next_step: str
    warnings: tuple[str, ...] = ()

    def line(self) -> str:
        """Render the one-line status shown at session start.

        Returns:
            str - ``grillspec: phase=<phase> change=<id> next=<step>``.

        """
        change = self.change_id or "-"
        return f"grillspec: phase={self.phase} change={change} next={self.next_step}"


def derive_phase(change: Change | None) -> Phase:
    """Derive a change's phase from its approvals and plan checkboxes.

    Args:
        change: Change | None - The active change, or None.

    Returns:
        Phase - The derived phase.

    """
    if change is None:
        return Phase.IDLE
    if change.spec_approved is None:
        return Phase.SPEC
    if change.plan_approved is None or change.plan_path is None:
        return Phase.PLAN
    if _UNCHECKED.search(change.plan_path.read_text(encoding="utf-8")):
        return Phase.EXECUTE
    return Phase.DONE


def compute_status(root: Path, config: Config) -> Status:
    """Compute the status of a project's working tree.

    Args:
        root: Path - Project root.
        config: Config - Effective configuration.

    Returns:
        Status - Phase, active change, next step and warnings.

    """
    if config.backend is None:
        return Status(Phase.IDLE, None, "run grillspec init")
    change_id, warnings = active_change_id(root)
    changes = {change.id: change for change in list_changes(root, config.backend)}
    change = changes.get(change_id) if change_id else None
    if change_id and change is None:
        warnings = (*warnings, f"active change {change_id!r} no longer exists")
    phase = derive_phase(change)
    return Status(phase, change.id if change else None, _NEXT[phase], warnings)
