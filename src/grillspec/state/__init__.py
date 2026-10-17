"""Changes, their approvals, the active change and the derived phase."""

from __future__ import annotations

from ._changes import Change, list_changes, open_questions
from ._create import create_change
from ._hash import artifact_hash, plan_hash, spec_files
from ._layout import log_path, plan_path
from ._phase import Phase, Status, compute_status, derive_phase
from ._sidecar import ChangeError, Stage, approve, write_sidecar
from ._store import UnknownChangeError, active_change_id, set_active

__all__ = (
    "Change",
    "ChangeError",
    "Phase",
    "Stage",
    "Status",
    "UnknownChangeError",
    "active_change_id",
    "approve",
    "artifact_hash",
    "compute_status",
    "create_change",
    "derive_phase",
    "list_changes",
    "log_path",
    "open_questions",
    "plan_hash",
    "plan_path",
    "set_active",
    "spec_files",
    "write_sidecar",
)
