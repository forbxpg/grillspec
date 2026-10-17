"""Second-review regressions: sidecar/state/receipt validation and phase edges."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend, ConfigError
from grillspec.hooks import Harness
from grillspec.install import Scope, install, uninstall
from grillspec.state import Change, Phase, active_change_id, derive_phase, list_changes
from support import write

if TYPE_CHECKING:
    from pathlib import Path

SPEC = "docs/grillspec/specs/c1.md"
PLAN = "docs/grillspec/plans/c1.md"
SIDECAR = ".grillspec/changes/c1.toml"


def change_with(tmp_path: Path, plan: str | None, *, spec: bool = True) -> Change:
    if spec:
        write(tmp_path / SPEC, "# spec\n")
    if plan is not None:
        write(tmp_path / PLAN, plan)
    write(
        tmp_path / SIDECAR,
        "version = 1\nspec_approved = 2026-10-17\nplan_approved = 2026-10-17\n",
    )
    (change,) = list_changes(tmp_path, Backend.SUPERPOWERS)
    return change


# 1.1 sidecar version
def test_sidecar_unsupported_version_is_config_error(tmp_path: Path):
    write(tmp_path / SIDECAR, "version = 2\n")
    with pytest.raises(ConfigError, match=r"c1\.toml.*version"):
        list_changes(tmp_path, Backend.SUPERPOWERS)


# 1.2 datetime values
def test_sidecar_datetime_becomes_date(tmp_path: Path):
    write(tmp_path / SPEC, "# spec\n")
    write(tmp_path / SIDECAR, "version = 1\nspec_approved = 2026-10-17T10:00:00Z\n")
    (change,) = list_changes(tmp_path, Backend.SUPERPOWERS)
    assert change.spec_approved == dt.date(2026, 10, 17)
    assert type(change.spec_approved) is dt.date


def test_sidecar_iso_datetime_string_becomes_date(tmp_path: Path):
    write(tmp_path / SIDECAR, 'version = 1\nplan_approved = "2026-10-17T10:00:00"\n')
    (change,) = list_changes(tmp_path, Backend.SUPERPOWERS)
    assert change.plan_approved == dt.date(2026, 10, 17)


# 1.3 phase edges
def test_approved_spec_without_file_is_spec(tmp_path: Path):
    change = change_with(tmp_path, "- [ ] a\n", spec=False)
    assert derive_phase(change) is Phase.SPEC


def test_plan_without_checkboxes_is_plan(tmp_path: Path):
    assert (
        derive_phase(change_with(tmp_path, "# Plan\n\nNo steps yet.\n")) is Phase.PLAN
    )


def test_checkboxes_in_code_fences_are_ignored(tmp_path: Path):
    plan = "- [x] real step\n\n```markdown\n- [ ] example inside a fence\n```\n"
    assert derive_phase(change_with(tmp_path, plan)) is Phase.DONE


def test_tilde_fences_and_longer_fences_are_ignored(tmp_path: Path):
    plan = "- [x] a\n~~~\n- [ ] x\n~~~\n````md\n```\n- [ ] y\n```\n````\n"
    assert derive_phase(change_with(tmp_path, plan)) is Phase.DONE


def test_unchecked_outside_fence_is_execute(tmp_path: Path):
    plan = "```\n- [x] sample\n```\n- [ ] real\n"
    assert derive_phase(change_with(tmp_path, plan)) is Phase.EXECUTE


def test_uppercase_x_and_star_bullets_count(tmp_path: Path):
    assert derive_phase(change_with(tmp_path, "* [X] a\n- [x] b\n")) is Phase.DONE


# 1.4 state.json and receipt
def test_state_null_active_is_quiet(tmp_path: Path):
    write(tmp_path / ".grillspec/state.json", '{"version": 1, "active": null}')
    assert active_change_id(tmp_path) == (None, ())


def test_state_unsupported_version_warns(tmp_path: Path):
    write(tmp_path / ".grillspec/state.json", '{"version": 2, "active": "c1"}')
    change_id, warnings = active_change_id(tmp_path)
    assert change_id is None
    assert any("version" in w for w in warnings)


def test_receipt_unsupported_version_is_config_error(tmp_path: Path):
    write(
        tmp_path / ".grillspec/install-receipt.json",
        json.dumps({"version": 2, "installs": {}}),
    )
    with pytest.raises(ConfigError, match="version"):
        uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)


def test_uninstall_leaves_no_empty_dirs_or_created_files(tmp_path: Path):
    install(Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_uninstall_keeps_preexisting_context_file(tmp_path: Path):
    write(tmp_path / "GIGACODE.md", "# Mine\n")
    install(Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["GIGACODE.md"]
    assert (tmp_path / "GIGACODE.md").read_text() == "# Mine\n"
