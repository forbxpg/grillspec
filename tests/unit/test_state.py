"""Tests for changes, approvals and the derived phase (spec S1-R3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend, Config
from grillspec.state import (
    Phase,
    UnknownChangeError,
    active_change_id,
    compute_status,
    derive_phase,
    list_changes,
    set_active,
)
from support import write

if TYPE_CHECKING:
    from pathlib import Path

CID = "2026-10-17-login"


def make_change(
    root: Path,
    backend: Backend,
    *,
    spec_ok: bool = False,
    plan: str | None = None,
    plan_ok: bool = False,
) -> None:
    if backend is Backend.SUPERPOWERS:
        write(root / f"docs/grillspec/specs/{CID}.md", "# spec\n")
        if plan is not None:
            write(root / f"docs/grillspec/plans/{CID}.md", plan)
    else:
        write(root / f"openspec/changes/{CID}/proposal.md", "## Why\n")
        if plan is not None:
            write(root / f"openspec/changes/{CID}/tasks.md", plan)
    lines = ["version = 1"]
    if spec_ok:
        lines.append("spec_approved = 2026-10-17")
    if plan_ok:
        lines.append("plan_approved = 2026-10-17")
    write(root / f".grillspec/changes/{CID}.toml", "\n".join(lines) + "\n")


ROWS: list[tuple[str, dict[str, object], Phase]] = [
    ("grill", {}, Phase.GRILL),
    ("plan", {"spec_ok": True}, Phase.PLAN),
    ("plan-written", {"spec_ok": True, "plan": "- [ ] a\n"}, Phase.PLAN),
    (
        "execute",
        {"spec_ok": True, "plan": "- [x] a\n  - [ ] b\n", "plan_ok": True},
        Phase.EXECUTE,
    ),
    ("done", {"spec_ok": True, "plan": "- [x] a\n", "plan_ok": True}, Phase.DONE),
]


@pytest.mark.parametrize("backend", list(Backend))
@pytest.mark.parametrize(("label", "kwargs", "phase"), ROWS)
def test_phase_table(  # S1-R3-S1
    tmp_path: Path,
    backend: Backend,
    label: str,
    kwargs: dict[str, object],
    phase: Phase,
):
    make_change(tmp_path, backend, **kwargs)  # pyright: ignore[reportArgumentType]
    (change,) = list_changes(tmp_path, backend)
    assert change.id == CID, label
    assert derive_phase(change) is phase, label


def test_no_change_is_idle():
    assert derive_phase(None) is Phase.IDLE


def test_openspec_archive_is_skipped(tmp_path: Path):
    write(tmp_path / "openspec/changes/archive/2026-01-01-old/proposal.md", "x\n")
    assert list_changes(tmp_path, Backend.OPENSPEC) == ()


def test_use_switches_active(tmp_path: Path):  # S1-R3-S2
    make_change(tmp_path, Backend.SUPERPOWERS)
    set_active(tmp_path, CID, Backend.SUPERPOWERS)
    assert active_change_id(tmp_path) == (CID, ())
    status = compute_status(tmp_path, Config(backend=Backend.SUPERPOWERS))
    assert status.phase is Phase.GRILL
    log = f"docs/grillspec/specs/{CID}.md"
    assert status.line() == (
        f"grillspec: phase=grill change={CID}"
        f" next=confirm the grill, then run grillspec approve grill log={log}"
    )


def test_use_unknown_lists_known(tmp_path: Path):  # S1-R3-S2
    make_change(tmp_path, Backend.SUPERPOWERS)
    with pytest.raises(UnknownChangeError) as info:
        set_active(tmp_path, "nope", Backend.SUPERPOWERS)
    assert info.value.known == (CID,)


@pytest.mark.parametrize("content", ["", "{", '{"version": 1}', "[1]"])
def test_corrupt_state_is_idle_with_warning(tmp_path: Path, content: str):  # RF2
    write(tmp_path / ".grillspec/state.json", content)
    change_id, warnings = active_change_id(tmp_path)
    assert change_id is None
    assert warnings
    status = compute_status(tmp_path, Config(backend=Backend.SUPERPOWERS))
    assert status.phase is Phase.IDLE
    assert status.warnings


def test_no_backend_says_run_init(tmp_path: Path):
    status = compute_status(tmp_path, Config())
    assert status.phase is Phase.IDLE
    assert status.next_step == "run grillspec init"
