"""The grill phase and the open-question count (spec S2-R1, S2-R4)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from grillspec.cli import main
from grillspec.config import Backend, Config
from grillspec.state import (
    Phase,
    compute_status,
    derive_phase,
    list_changes,
    open_questions,
)
from support import write

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

LOG = """# c1

## Decision log

<!-- grillspec: depth=standard council=no budget=15 asked=1 -->

### Open
- [ ] Q2 Retry policy
- [ ] Q3 Log format

### Settled
- [x] D1 Auth — **JWT** · user

## Requirements
- [ ] not a question: outside the log section
"""
SPEC = "docs/grillspec/specs/c1.md"
SIDECAR = ".grillspec/changes/c1.toml"
CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'


def superpowers_change(root: Path, log: str = LOG, sidecar: str = "version = 1\n"):
    write(root / SPEC, log)
    write(root / SIDECAR, sidecar)
    (change,) = list_changes(root, Backend.SUPERPOWERS)
    return change


def test_grill_before_spec(tmp_path: Path):  # S2-R1-S1
    change = superpowers_change(tmp_path)
    assert derive_phase(change) is Phase.GRILL
    assert open_questions(change.log_path) == 2
    write(tmp_path / ".grillspec/state.json", '{"version": 1, "active": "c1"}')
    status = compute_status(tmp_path, Config(backend=Backend.SUPERPOWERS))
    assert status.phase is Phase.GRILL
    assert status.open_questions == 2
    assert status.next_step == "continue grilling: 2 open questions"


def test_grilled_moves_to_spec(tmp_path: Path):
    change = superpowers_change(tmp_path, sidecar="version = 1\ngrilled = 2026-10-17\n")
    assert change.grilled is not None
    assert derive_phase(change) is Phase.SPEC


def test_spec_approved_implies_grilled(tmp_path: Path):  # S2-R1-S2
    change = superpowers_change(
        tmp_path, sidecar="version = 1\nspec_approved = 2026-10-17\n"
    )
    assert derive_phase(change) is Phase.PLAN


def test_fenced_checkboxes_not_counted(tmp_path: Path):  # S2-R1-S3
    log = "## Decision log\n### Open\n- [ ] Q1 real\n```\n- [ ] example\n```\n"
    assert open_questions(write(tmp_path / "log.md", log)) == 1


def test_missing_log_section_counts_zero(tmp_path: Path):  # Review Focus 1
    change = superpowers_change(tmp_path, log="# c1\n\n## Notes\n- [ ] x\n")
    assert open_questions(change.log_path) == 0
    assert derive_phase(change) is Phase.GRILL
    assert open_questions(None) == 0


def test_crlf_log_counts(tmp_path: Path):  # Review Focus 2
    path = tmp_path / "log.md"
    path.write_bytes(LOG.replace("\n", "\r\n").encode())
    assert open_questions(path) == 2


def test_openspec_log_is_design_md(tmp_path: Path):
    write(tmp_path / "openspec/changes/add-x/design.md", LOG)
    write(tmp_path / ".grillspec/changes/add-x.toml", "version = 1\n")
    (change,) = list_changes(tmp_path, Backend.OPENSPEC)
    assert change.log_path == tmp_path / "openspec/changes/add-x/design.md"
    assert derive_phase(change) is Phase.GRILL


def test_status_json_has_open_questions_and_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # S2-R4
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    superpowers_change(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["use", "c1"]) == 0
    capsys.readouterr()
    assert main(["status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["phase"] == "grill"
    assert data["open_questions"] == 2
    assert data["log"] == SPEC
