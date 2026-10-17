"""Tests for the bundled spec rules, superpowers backend (spec S4-R1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend
from grillspec.specs import Report, validate_change
from grillspec.state import ChangeError
from support import write

if TYPE_CHECKING:
    from pathlib import Path

ID = "2026-10-17-limits"
VALID = """# 2026-10-17-limits

## Intent

Limit bursts of webhook deliveries.

## Decision log

### Open
- [ ] Q4 Window size · deferred

### Settled
- [x] D1 Delivery — **at-least-once** · user

## Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive within a second
- **THEN** the eleventh is rejected

#### Scenario: RL-2 burst allowed
- **WHEN** 10 deliveries arrive within a second
- **THEN** all are accepted

## Open questions

- Q4 Window size: recommend 1 s; decide before the plan.
"""


def _check(tmp_path: Path, text: str) -> Report:
    write(tmp_path / f"docs/grillspec/specs/{ID}.md", text)
    return validate_change(tmp_path, Backend.SUPERPOWERS, ID)


def _rules(report: Report) -> list[str]:
    return [finding.rule for finding in report.errors]


def test_valid_superpowers_spec(tmp_path: Path):  # S4-R1-S1
    report = _check(tmp_path, VALID)
    assert report.errors == ()
    assert report.warnings == ()
    assert report.change == ID


def test_missing_scenario_id(tmp_path: Path):  # S4-R1-S2
    report = _check(tmp_path, VALID.replace("RL-1 burst exceeded", "burst exceeded"))
    (finding,) = report.errors
    assert finding.rule == "scenario-id"
    assert finding.text() == (
        f"error docs/grillspec/specs/{ID}.md:20 scenario-id: "
        "'burst exceeded': start the scenario name with an ID like RL-1"
    )


@pytest.mark.parametrize("bad", ["rl-1", "RL-0", "RL-01", "ABCDE-1", "burst RL-1"])
def test_bad_ids(tmp_path: Path, bad: str):  # Review Focus 2
    report = _check(tmp_path, VALID.replace("RL-1 burst exceeded", bad))
    assert _rules(report) == ["scenario-id"]
    assert "like RL-1" in report.errors[0].message


def test_duplicate_id(tmp_path: Path):
    report = _check(tmp_path, VALID.replace("RL-2 burst allowed", "RL-1 burst allowed"))
    assert _rules(report) == ["scenario-id-duplicate"]


def test_shall_must(tmp_path: Path):
    report = _check(tmp_path, VALID.replace("SHALL reject", "rejects"))
    assert _rules(report) == ["requirement-shall"]


def test_when_then(tmp_path: Path):
    report = _check(
        tmp_path, VALID.replace("- **THEN** the eleventh is rejected\n", "")
    )
    assert _rules(report) == ["scenario-when-then"]


def test_requirement_without_scenario(tmp_path: Path):
    text = VALID.replace(
        "## Open questions",
        "### Requirement: Lonely\nThe sender SHALL log.\n\n## Open questions",
    )
    assert _rules(_check(tmp_path, text)) == ["requirement-scenario"]


def test_open_item_not_deferred(tmp_path: Path):
    text = VALID.replace(
        "- [ ] Q4 Window size · deferred",
        "- [ ] Q4 Window size · deferred\n- [ ] Q5 Tz",
    )
    assert _rules(_check(tmp_path, text)) == ["log-open-item"]


def test_deferred_not_listed(tmp_path: Path):  # S4-R1-S5
    text = VALID.replace(
        "- Q4 Window size: recommend 1 s; decide before the plan.", "-"
    )
    report = _check(tmp_path, text)
    assert _rules(report) == ["deferred-not-listed"]
    assert "Q4" in report.errors[0].message


def test_q40_does_not_list_q4(tmp_path: Path):
    text = VALID.replace("- Q4 Window size:", "- Q40 Window size:")
    assert _rules(_check(tmp_path, text)) == ["deferred-not-listed"]


def test_long_requirement_warns(tmp_path: Path):
    text = VALID.replace(
        "The sender SHALL reject a burst over the limit.",
        "The sender SHALL reject a burst over the limit. " + "x" * 500,
    )
    report = _check(tmp_path, text)
    assert report.errors == ()
    assert [w.rule for w in report.warnings] == ["requirement-length"]


def test_missing_sections(tmp_path: Path):
    text = VALID.replace("## Intent", "## Purpose")
    assert _rules(_check(tmp_path, text)) == ["section-missing"]


def test_missing_spec_file(tmp_path: Path):
    write(tmp_path / f".grillspec/changes/{ID}.toml", "version = 1\n")
    report = validate_change(tmp_path, Backend.SUPERPOWERS, ID)
    assert _rules(report) == ["section-missing"]


def test_unknown_change(tmp_path: Path):
    with pytest.raises(ChangeError, match="no change nope"):
        _ = validate_change(tmp_path, Backend.SUPERPOWERS, "nope")


def test_report_json(tmp_path: Path):
    report = _check(tmp_path, VALID.replace("SHALL reject", "rejects"))
    data = report.to_json()
    assert data["version"] == 1
    assert data["change"] == ID
    assert data["errors"] == [
        {
            "severity": "error",
            "path": f"docs/grillspec/specs/{ID}.md",
            "line": 17,
            "rule": "requirement-shall",
            "message": "'Burst limit' has no SHALL or MUST",
        }
    ]
    assert data["warnings"] == []
