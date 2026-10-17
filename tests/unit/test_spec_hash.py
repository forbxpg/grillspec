"""Tests for approval bound to the spec's content (spec S4-R3, S4-R4)."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.config import Backend
from grillspec.state import artifact_hash, spec_files
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ID = "2026-10-17-limits"
SPEC = """# 2026-10-17-limits

## Intent

Limit bursts.

## Decision log

### Settled
- [x] D1 Limit — **10/s** · user

## Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive within a second
- **THEN** the eleventh is rejected
"""
PLAN = f"""# {ID} — plan

**Spec:** docs/grillspec/specs/{ID}.md

## 1. Limiter

- [ ] 1.1 Burst limit — verify: pytest passes

Covers: RL-1 · Test: scenario-first

Files: create src/limit.py

1. Write the test. Expected: FAIL
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    write(tmp_path / f"docs/grillspec/specs/{ID}.md", SPEC)
    write(
        tmp_path / f".grillspec/changes/{ID}.toml",
        "version = 1\ngrilled = 2026-10-17\n",
    )
    write(tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{ID}"}}\n')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _status(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    _ = capsys.readouterr()
    assert main(["status", "--json"]) == 0
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


def test_hash_ignores_line_endings_and_trailing_space(project: Path):  # S4-R3-S2
    before = artifact_hash(project, Backend.SUPERPOWERS, ID)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", before)
    spec = project / f"docs/grillspec/specs/{ID}.md"
    crlf = "﻿" + SPEC.replace("\n", "  \r\n")
    _ = spec.write_bytes(crlf.encode())
    assert artifact_hash(project, Backend.SUPERPOWERS, ID) == before


def test_hash_changes_with_content_and_path(project: Path):
    before = artifact_hash(project, Backend.SUPERPOWERS, ID)
    spec = project / f"docs/grillspec/specs/{ID}.md"
    _ = spec.write_text(
        SPEC.replace("11 deliveries", "12 deliveries"), encoding="utf-8"
    )
    assert artifact_hash(project, Backend.SUPERPOWERS, ID) != before


def test_openspec_hash_covers_proposal_design_specs(tmp_path: Path):
    change = tmp_path / "openspec/changes/add-x"
    for name in ("proposal.md", "design.md", "specs/b/spec.md", "specs/a/spec.md"):
        write(change / name, name)
    write(change / "tasks.md", "tasks")
    write(change / ".openspec.yaml", "schema: spec-driven\n")
    files = spec_files(tmp_path, Backend.OPENSPEC, "add-x")
    assert [p.relative_to(change).as_posix() for p in files] == [
        "design.md",
        "proposal.md",
        "specs/a/spec.md",
        "specs/b/spec.md",
    ]
    before = artifact_hash(tmp_path, Backend.OPENSPEC, "add-x")
    write(change / "tasks.md", "changed tasks")
    assert artifact_hash(tmp_path, Backend.OPENSPEC, "add-x") == before
    write(change / "specs/a/spec.md", "changed")
    assert artifact_hash(tmp_path, Backend.OPENSPEC, "add-x") != before


def test_approve_refuses_invalid(  # S4-R3-S1
    project: Path, capsys: pytest.CaptureFixture[str]
):
    spec = project / f"docs/grillspec/specs/{ID}.md"
    _ = spec.write_text(SPEC.replace("SHALL reject", "rejects"), encoding="utf-8")
    sidecar = project / f".grillspec/changes/{ID}.toml"
    before = sidecar.read_bytes()
    assert main(["approve", "spec"]) == 1
    err = capsys.readouterr().err
    assert "requirement-shall" in err
    assert err.rstrip().endswith("grillspec: fix these, then approve again")
    assert sidecar.read_bytes() == before


def test_approve_writes_hash(project: Path):
    assert main(["approve", "spec"]) == 0
    text = (project / f".grillspec/changes/{ID}.toml").read_text(encoding="utf-8")
    assert f'spec_hash = "{artifact_hash(project, Backend.SUPERPOWERS, ID)}"' in text
    assert "spec_approved = " in text


def test_edit_before_plan_approval(  # S4-R4-S1
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["approve", "spec"]) == 0
    assert _status(capsys)["phase"] == "plan"
    spec = project / f"docs/grillspec/specs/{ID}.md"
    _ = spec.write_text(
        SPEC.replace("11 deliveries", "12 deliveries"), encoding="utf-8"
    )
    status = _status(capsys)
    assert status["phase"] == "spec"
    assert status["next"] == (
        "spec changed since approval: review it, then grillspec approve spec"
    )


def test_edit_during_execution_warns(  # S4-R4-S2
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["approve", "spec"]) == 0
    write(project / f"docs/grillspec/plans/{ID}.md", PLAN)
    assert main(["approve", "plan"]) == 0
    spec = project / f"docs/grillspec/specs/{ID}.md"
    _ = spec.write_text(
        SPEC.replace("11 deliveries", "12 deliveries"), encoding="utf-8"
    )
    status = _status(capsys)
    assert status["phase"] == "execute"
    assert "spec changed after approval" in cast("list[str]", status["warnings"])


def test_pre_s4_sidecar(project: Path, capsys: pytest.CaptureFixture[str]):  # S4-R4-S3
    write(
        project / f".grillspec/changes/{ID}.toml",
        "version = 1\ngrilled = 2026-10-17\nspec_approved = 2026-10-17\n",
    )
    status = _status(capsys)
    assert status["phase"] == "plan"
    assert status["warnings"] == []


@pytest.mark.usefixtures("project")
def test_spec_phase_next_step(capsys: pytest.CaptureFixture[str]):
    status = _status(capsys)
    assert status["phase"] == "spec"
    assert status["next"] == "write the spec, grillspec validate, then approve"


@pytest.mark.parametrize("value", ['"md5:abc"', '"sha256:abc"', "1"])
def test_bad_spec_hash_one_line(  # Review Focus 4
    project: Path, capsys: pytest.CaptureFixture[str], value: str
):
    write(
        project / f".grillspec/changes/{ID}.toml",
        f"version = 1\nspec_approved = 2026-10-17\nspec_hash = {value}\n",
    )
    assert main(["status"]) == 1
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "spec_hash must be sha256:<64 hex digits>" in err
    assert f"{ID}.toml" in err
