"""Tests for the OpenSpec rules and scenario-ID uniqueness (spec S4-R1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.config import Backend
from grillspec.specs import Report, validate_change
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ID = "add-limits"
WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
PROPOSAL = f"## Why\n\n{WHY}\n\n## What Changes\n\n- Add burst limits.\n"
DESIGN = """# Design: add-limits

## Decision log

### Settled
- [x] D1 Limit — **10 per second** · user

## Goals / Non-Goals

Goal: protect receivers.
"""
PURPOSE = "Keeps webhook receivers safe from bursts of deliveries by one sender."
DELTA = f"""## Purpose

{PURPOSE}

## ADDED Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive within a second
- **THEN** the eleventh is rejected
"""
LIVING = """# auth Specification

## Purpose

Lets users sign in with a password and keeps sessions alive across requests.

## Requirements

### Requirement: Session expiry
The system SHALL expire sessions after 30 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 31 minutes
- **THEN** the next request is rejected
"""


def _change(root: Path, files: dict[str, str]) -> Report:
    base = {
        "proposal.md": PROPOSAL,
        "design.md": DESIGN,
        "specs/limits/spec.md": DELTA,
        ".openspec.yaml": "schema: spec-driven\ncreated: 2026-10-17\n",
    }
    for name, text in {**base, **files}.items():
        if text:
            write(root / "openspec/changes" / ID / name, text)
    return validate_change(root, Backend.OPENSPEC, ID)


def _errors(report: Report) -> list[str]:
    return [finding.rule for finding in report.errors]


def _warnings(report: Report) -> list[str]:
    return [finding.rule for finding in report.warnings]


def test_valid_openspec_change(tmp_path: Path):
    report = _change(tmp_path, {})
    assert report.errors == ()
    assert report.warnings == ()


def test_id_clash_with_living_spec_and_modified_exception(tmp_path: Path):  # S4-R1-S3
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    clash = _change(tmp_path, {"specs/limits/spec.md": DELTA.replace("RL-1", "AU-1")})
    assert _errors(clash) == ["scenario-id-clash"]
    modified = LIVING.split("## Requirements\n", 1)[1].replace(
        "30 minutes", "15 minutes"
    )
    keep = _change(
        tmp_path,
        {"specs/auth/spec.md": f"## MODIFIED Requirements\n{modified}"},
    )
    assert keep.errors == ()


def test_id_clash_with_other_change(tmp_path: Path):
    write(tmp_path / "openspec/changes/other/specs/x/spec.md", DELTA)
    write(tmp_path / "openspec/changes/archive/2026-01-01-old/specs/y/spec.md", DELTA)
    report = _change(tmp_path, {})
    assert _errors(report) == ["scenario-id-clash"]
    assert "openspec/changes/other/specs/x/spec.md" in report.errors[0].message


def test_why_and_skip_specs(tmp_path: Path):  # S4-R1-S4
    report = _change(
        tmp_path,
        {
            "proposal.md": PROPOSAL.replace(WHY, "Too short, thirty characters."),
            ".openspec.yaml": "schema: spec-driven\nskip_specs: true\n",
        },
    )
    assert sorted(_errors(report)) == ["deltas", "why-length"]


def test_what_changes_empty(tmp_path: Path):
    report = _change(tmp_path, {"proposal.md": f"## Why\n\n{WHY}\n\n## What Changes\n"})
    assert _errors(report) == ["what-changes-empty"]


def test_no_delta_without_skip_specs(tmp_path: Path):
    report = _change(tmp_path, {"specs/limits/spec.md": ""})
    assert _errors(report) == ["deltas"]


def test_skip_specs_without_delta_is_fine(tmp_path: Path):
    report = _change(
        tmp_path,
        {
            "specs/limits/spec.md": "",
            ".openspec.yaml": "schema: spec-driven\nskip_specs: true\n",
        },
    )
    assert report.errors == ()


def test_modified_target_missing(tmp_path: Path):
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    delta = (
        "## MODIFIED Requirements\n\n### Requirement: Session lifetime\n"
        "The system SHALL expire sessions.\n\n#### Scenario: AU-9 x\n"
        "- **WHEN** a\n- **THEN** b\n"
    )
    report = _change(tmp_path, {"specs/auth/spec.md": delta})
    assert _errors(report) == ["delta-target"]


def test_removed_needs_reason_and_migration(tmp_path: Path):
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    removed = (
        "## REMOVED Requirements\n\n### Requirement: Session expiry\n**Reason**: gone\n"
    )
    assert _errors(_change(tmp_path, {"specs/auth/spec.md": removed})) == [
        "removed-reason"
    ]
    ok = removed + "**Migration**: use tokens\n"
    assert _change(tmp_path, {"specs/auth/spec.md": ok}).errors == ()


def test_renamed_from_to(tmp_path: Path):
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    renamed = "## RENAMED Requirements\n\n- FROM: `### Requirement: Session expiry`\n"
    assert _errors(_change(tmp_path, {"specs/auth/spec.md": renamed})) == [
        "renamed-from-to"
    ]
    ok = renamed + "- TO: `### Requirement: Session timeout`\n"
    assert _change(tmp_path, {"specs/auth/spec.md": ok}).errors == ()


def test_purpose_warning(tmp_path: Path):
    report = _change(
        tmp_path, {"specs/limits/spec.md": DELTA.replace(PURPOSE, "Short purpose.")}
    )
    assert report.errors == ()
    assert _warnings(report) == ["purpose"]


def test_delta_count_warning(tmp_path: Path):
    steps = "- **WHEN** a\n- **THEN** b\n\n"
    blocks = "".join(
        f"### Requirement: R{n}\nThe sender SHALL do {n}.\n\n#### Scenario: RL-{n} s\n{steps}"
        for n in range(1, 12)
    )
    delta = f"## Purpose\n\n{PURPOSE}\n\n## ADDED Requirements\n\n{blocks}"
    report = _change(tmp_path, {"specs/limits/spec.md": delta})
    assert report.errors == ()
    assert _warnings(report) == ["delta-count"]


def test_nested_capability(tmp_path: Path):  # Review Focus 5
    write(tmp_path / "openspec/specs/identity/user-auth/spec.md", LIVING)
    modified = LIVING.split("## Requirements\n", 1)[1]
    report = _change(
        tmp_path,
        {
            "specs/limits/spec.md": "",
            "specs/identity/user-auth/spec.md": f"## MODIFIED Requirements\n{modified}",
        },
    )
    assert report.errors == ()


def test_log_rules_use_design_md(tmp_path: Path):
    design = DESIGN.replace(
        "### Settled", "### Open\n- [ ] Q2 Window · deferred\n\n### Settled"
    )
    report = _change(tmp_path, {"design.md": design})
    assert _errors(report) == ["deferred-not-listed"]
    listed = design + "\n## Open questions\n\n- Q2 Window: decide later.\n"
    assert _change(tmp_path, {"design.md": listed}).errors == ()


def test_requirement_rules_apply_to_deltas(tmp_path: Path):
    report = _change(
        tmp_path, {"specs/limits/spec.md": DELTA.replace("RL-1 burst", "burst")}
    )
    assert _errors(report) == ["scenario-id"]
