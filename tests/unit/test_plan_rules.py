"""Tests for the plan format checks (spec S6-R1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend
from grillspec.specs import Report, parse_plan, validate_change
from support import write

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SP = "2026-10-17-limits"
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
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected

#### Scenario: RL-2 burst allowed
- **WHEN** 10 deliveries arrive
- **THEN** all are accepted
"""
PLAN = """# 2026-10-17-limits — plan

## Goal

Limit bursts.

**Spec:** docs/grillspec/specs/2026-10-17-limits.md

## Global Constraints

- stdlib only

## Review Focus

none found

## 1. Limiter

- [ ] 1.1 Burst limit — verify: pytest -k burst passes

Covers: RL-1 · Test: scenario-first

Files: create src/limit.py

1. Write test_burst. Expected: FAIL
2. Implement the limiter.

- [ ] 1.2 Allowed bursts — verify: pytest -k allowed passes

Covers: RL-2 · Test: scenario-first

Files: modify src/limit.py

1. Write test_allowed. Expected: FAIL

## 2. Glue

- [ ] 2.1 Wire the CLI — verify: grillspec --help lists limit

Covers: — · Test: none: glue

Files: modify src/cli.py

1. Add the command.
"""


def _sp(root: Path, plan: str) -> Report:
    write(root / f"docs/grillspec/specs/{SP}.md", SPEC)
    write(root / f"docs/grillspec/plans/{SP}.md", plan)
    return validate_change(root, Backend.SUPERPOWERS, SP)


OS = "add-limits"
WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
DELTA = """## Purpose

Keeps webhook receivers safe from bursts of deliveries by one sender.

## ADDED Requirements

""" + SPEC.split("## Requirements\n\n", 1)[1]


def _os(root: Path, tasks: str, *, skip: bool = False) -> Report:
    folder = root / "openspec/changes" / OS
    write(folder / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- x\n")
    meta = "schema: spec-driven\n" + ("skip_specs: true\n" if skip else "")
    write(folder / ".openspec.yaml", meta)
    if not skip:
        write(folder / "specs/limits/spec.md", DELTA)
    link = f"openspec/changes/{OS}/proposal.md"
    write(folder / "tasks.md", tasks.replace(f"docs/grillspec/specs/{SP}.md", link))
    return validate_change(root, Backend.OPENSPEC, OS)


def _plan_rules(report: Report) -> list[str]:
    return sorted(f.rule for f in report.errors if f.rule.startswith("plan-"))


def _plan_warnings(report: Report) -> list[str]:
    return sorted(f.rule for f in report.warnings if f.rule.startswith("plan-"))


@pytest.mark.parametrize("check", [_sp, _os])
def test_valid_plan(tmp_path: Path, check: Callable[[Path, str], Report]):  # PL-1
    report = check(tmp_path, PLAN)
    assert _plan_rules(report) == []
    assert _plan_warnings(report) == []


def test_parse_plan(tmp_path: Path):
    plan = parse_plan(write(tmp_path / "plan.md", PLAN))
    assert [t.number for t in plan.tasks] == [(1, 1), (1, 2), (2, 1)]
    first = plan.tasks[0]
    assert first.title == "Burst limit"
    assert first.verify == "pytest -k burst passes"
    assert first.covers == ("RL-1",)
    assert first.test == "scenario-first"
    assert first.files
    assert first.steps == 2
    assert plan.tasks[2].covers == ()
    assert plan.spec_link


def test_fenced_checkbox(tmp_path: Path):  # PL-2
    plan = PLAN.replace(
        "2. Implement the limiter.\n", "2. Implement.\n\n```\n- [ ] step\n```\n"
    )
    report = _sp(tmp_path, plan)
    assert _plan_rules(report) == ["plan-checkbox"]


def test_indented_and_star_boxes_are_checked_too(tmp_path: Path):
    plan = PLAN.replace(
        "2. Implement the limiter.\n", "2. Implement.\n   * [ ] nested\n"
    )
    assert _plan_rules(_sp(tmp_path, plan)) == ["plan-checkbox"]


def test_uncovered_scenario(tmp_path: Path):  # PL-3
    plan = PLAN.replace(
        "Covers: RL-2 · Test: scenario-first", "Covers: RL-2 · Test: none: glue"
    )
    report = _sp(tmp_path, plan)
    assert _plan_rules(report) == ["plan-coverage"]
    assert "RL-2" in report.errors[0].message


def test_unknown_id_and_bad_test(tmp_path: Path):  # PL-4
    plan = PLAN.replace("Covers: — · Test: none: glue", "Covers: RL-9 · Test: maybe")
    assert _plan_rules(_sp(tmp_path, plan)) == ["plan-covers-unknown", "plan-test"]


@pytest.mark.parametrize(
    "change",
    [("- [ ] 1.2 Allowed", "- [ ] 1.3 Allowed"), ("- [ ] 2.1 Wire", "- [ ] 3.1 Wire")],
)
def test_numbering(tmp_path: Path, change: tuple[str, str]):  # PL-5
    assert _plan_rules(_sp(tmp_path, PLAN.replace(*change))) == ["plan-numbering"]


def test_proportion_warnings(tmp_path: Path):  # PL-6
    many = "".join(
        f"- [ ] 2.{n} Glue {n} — verify: ok\n\nCovers: — · Test: none: glue\n\nFiles: x\n\n"
        for n in range(2, 13)
    )
    report = _sp(tmp_path, PLAN + many)
    assert _plan_rules(report) == []
    assert "plan-size" in _plan_warnings(report)
    steps = "".join(f"{n}. step {n}\n" for n in range(2, 10))
    report = _sp(
        tmp_path, PLAN.replace("1. Add the command.\n", "1. Add the command.\n" + steps)
    )
    assert _plan_warnings(report) == ["plan-steps"]


def test_missing_fields(tmp_path: Path):
    plan = PLAN.replace("Files: modify src/cli.py\n", "").replace(
        " — verify: pytest -k burst passes", ""
    )
    plan = plan.replace("**Spec:** docs/grillspec/specs/2026-10-17-limits.md\n", "")
    assert _plan_rules(_sp(tmp_path, plan)) == [
        "plan-checkbox",
        "plan-files",
        "plan-spec-link",
    ]


def test_tbd(tmp_path: Path):
    plan = PLAN.replace("2. Implement the limiter.", "2. TBD")
    assert _plan_rules(_sp(tmp_path, plan)) == ["plan-tbd"]


def test_crlf_and_bom_plan(tmp_path: Path):  # Review Focus 1
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", SPEC)
    path = tmp_path / f"docs/grillspec/plans/{SP}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(b"\xef\xbb\xbf" + PLAN.replace("\n", "\r\n").encode())
    plan = parse_plan(path)
    assert [t.number for t in plan.tasks] == [(1, 1), (1, 2), (2, 1)]
    assert _plan_rules(validate_change(tmp_path, Backend.SUPERPOWERS, SP)) == []


def test_skip_specs_change_with_glue_tasks(tmp_path: Path):  # Review Focus 3
    glue = PLAN.split("## 1. Limiter", 1)[0] + PLAN.split("## 2. Glue", 1)[1].join([
        "## 1. Glue",
        "",
    ]).replace("2.1 Wire", "1.1 Wire")
    report = _os(tmp_path, glue, skip=True)
    assert _plan_rules(report) == []


def test_no_plan_no_plan_rules(tmp_path: Path):
    write(tmp_path / f"docs/grillspec/specs/{SP}.md", SPEC)
    report = validate_change(tmp_path, Backend.SUPERPOWERS, SP)
    assert _plan_rules(report) == []
