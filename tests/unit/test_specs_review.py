"""Fixes from the S4 final review."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fakes import make_fake
from grillspec.cli import main
from grillspec.config import Backend
from grillspec.specs import openspec_advice, validate_change
from grillspec.state import artifact_hash
from support import write

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ID = "add-limits"
WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
LIVING = """## Purpose

Lets users sign in with a password and keeps sessions alive across requests.

## Requirements

### Requirement: Session expiry
The system SHALL expire sessions after 30 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 31 minutes
- **THEN** the next request is rejected
"""
MODIFIED_TIMEOUT = """## RENAMED Requirements

- FROM: `### Requirement: Session expiry`
- TO: `### Requirement: Session timeout`

## MODIFIED Requirements

### Requirement: Session timeout
The system SHALL expire sessions after 15 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 16 minutes
- **THEN** the next request is rejected
"""
MODIFIED_EXPIRY = MODIFIED_TIMEOUT.split("## MODIFIED", 1)[1].replace(
    "Session timeout", "Session expiry"
)


def _change(root: Path, change_id: str, delta: str) -> None:
    folder = root / "openspec/changes" / change_id
    write(folder / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- x\n")
    write(folder / "specs/auth/spec.md", delta)


def test_renamed_then_modified_under_new_name(tmp_path: Path):  # I1
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    _change(tmp_path, ID, MODIFIED_TIMEOUT)
    report = validate_change(tmp_path, Backend.OPENSPEC, ID)
    assert report.errors == ()


def test_two_changes_modify_the_same_requirement(tmp_path: Path):  # I3
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    _change(tmp_path, ID, f"## MODIFIED{MODIFIED_EXPIRY}")
    _change(tmp_path, "other", f"## MODIFIED{MODIFIED_EXPIRY}")
    assert validate_change(tmp_path, Backend.OPENSPEC, ID).errors == ()


SP = "2026-10-17-limits"
SPEC = """# x

## Intent

Limit bursts.

## Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

##### Example
Some notes.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected

##### Example
Notes inside the scenario.

#### Scenario: burst allowed
"""


def test_subheadings_do_not_end_a_requirement(tmp_path: Path):  # I4
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", SPEC)
    report = validate_change(tmp_path, Backend.SUPERPOWERS, SP)
    assert sorted(f.rule for f in report.errors) == [
        "scenario-id",
        "scenario-when-then",
    ]


def test_non_scenario_level4_heading_is_an_error(tmp_path: Path):  # I4
    text = SPEC.replace("#### Scenario: burst allowed\n", "#### Edge case\n")
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", text)
    report = validate_change(tmp_path, Backend.SUPERPOWERS, SP)
    assert [f.rule for f in report.errors] == ["scenario-format"]


def test_approve_plan_refuses_stale_or_unapproved_spec(  # I5
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    valid = SPEC.split("##### Example\nSome", 1)[0] + (
        "#### Scenario: RL-1 burst\n- **WHEN** a\n- **THEN** b\n"
    )
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", valid)
    write(tmp_path / f"docs/grillspec/plans/{SP}.md", "- [ ] step\n")
    write(
        tmp_path / f".grillspec/changes/{SP}.toml",
        "version = 1\ngrilled = 2026-10-17\n",
    )
    write(tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{SP}"}}\n')
    monkeypatch.chdir(tmp_path)
    assert main(["approve", "plan"]) == 1
    assert "approve the spec first" in capsys.readouterr().err
    assert main(["approve", "spec"]) == 0
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", valid + "\nmore\n")
    assert main(["approve", "plan"]) == 1
    assert "spec changed since approval" in capsys.readouterr().err


def test_final_newline_does_not_change_the_hash(tmp_path: Path):
    spec = tmp_path / f"docs/grillspec/specs/{SP}.md"
    write(spec, SPEC)
    before = artifact_hash(tmp_path, Backend.SUPERPOWERS, SP)
    write(spec, SPEC + "\n\n")
    assert artifact_hash(tmp_path, Backend.SUPERPOWERS, SP) == before
    write(spec, SPEC.rstrip("\n"))
    assert artifact_hash(tmp_path, Backend.SUPERPOWERS, SP) == before


def test_advice_paths_point_into_specs(tmp_path: Path, bin_dir: Path):
    issues = {
        "items": [
            {"issues": [{"level": "ERROR", "path": "auth/spec.md", "message": "m"}]}
        ]
    }
    _ = make_fake(bin_dir, "openspec", stdout=json.dumps(issues), exit_code=1)
    (finding,) = openspec_advice(tmp_path, ID)
    assert finding.path.as_posix() == f"openspec/changes/{ID}/specs/auth/spec.md"


LEGACY = LIVING.replace(
    "#### Scenario: AU-1 idle session", "#### Scenario: Idle session"
)


def test_modified_legacy_scenario_without_id_warns(tmp_path: Path):  # I2
    write(tmp_path / "openspec/specs/auth/spec.md", LEGACY)
    block = LEGACY.split("## Requirements\n", 1)[1].replace("30 minutes", "15 minutes")
    _change(tmp_path, ID, f"## MODIFIED Requirements\n{block}")
    report = validate_change(tmp_path, Backend.OPENSPEC, ID)
    assert report.errors == ()
    assert [w.rule for w in report.warnings] == ["scenario-id-legacy"]


def test_new_scenario_without_id_in_modified_is_still_an_error(tmp_path: Path):
    write(tmp_path / "openspec/specs/auth/spec.md", LEGACY)
    block = LEGACY.split("## Requirements\n", 1)[1] + (
        "\n#### Scenario: Remember me\n- **WHEN** a\n- **THEN** b\n"
    )
    _change(tmp_path, ID, f"## MODIFIED Requirements\n{block}")
    report = validate_change(tmp_path, Backend.OPENSPEC, ID)
    assert [f.rule for f in report.errors] == ["scenario-id"]
    assert [w.rule for w in report.warnings] == ["scenario-id-legacy"]
