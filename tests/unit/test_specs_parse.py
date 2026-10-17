"""Tests for the spec Markdown parser (spec S4-R1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from grillspec.config import ConfigError
from grillspec.markdown import numbered_lines_outside_fences
from grillspec.specs import LogItem, parse_markdown
from support import write

if TYPE_CHECKING:
    from pathlib import Path

SPEC = """# 2026-10-17-limits

## Intent

Limit bursts of webhook deliveries.

## Decision log

<!-- grillspec: depth=standard council=no budget=15 asked=2 -->

### Open
- [ ] Q4 Window size · deferred

### Settled
- [x] D1 Delivery — **at-least-once** · user
- [~] D0 Old choice superseded by D1

## Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive within a second
- **THEN** the eleventh is rejected

#### Scenario: RL-2 burst allowed
- **WHEN** 10 deliveries arrive within a second
- **THEN** all are accepted

### Requirement: Retry
The sender MUST retry failed deliveries.

#### Scenario: RL-3 retry once
- **WHEN** a delivery fails
- **THEN** it is retried

## Open questions

- Q4 Window size: recommend 1 s; decide before the plan.
"""


def test_superpowers_doc(tmp_path: Path):
    doc = parse_markdown(write(tmp_path / "spec.md", SPEC))
    assert [r.name for r in doc.requirements] == ["Burst limit", "Retry"]
    burst, retry = doc.requirements
    assert burst.line == 20
    assert burst.text == "The sender SHALL reject a burst over the limit."
    assert burst.section == "Requirements"
    assert [s.scenario_id for s in burst.scenarios] == ["RL-1", "RL-2"]
    assert burst.scenarios[0].name == "RL-1 burst exceeded"
    assert burst.scenarios[0].line == 23
    assert burst.scenarios[0].has_when
    assert burst.scenarios[0].has_then
    assert [s.scenario_id for s in retry.scenarios] == ["RL-3"]
    assert set(doc.sections) == {
        "Intent",
        "Decision log",
        "Requirements",
        "Open questions",
    }
    assert doc.sections["Intent"][0] == 3
    assert "Q4 Window size" in doc.sections["Open questions"][1]


def test_log_items(tmp_path: Path):
    doc = parse_markdown(write(tmp_path / "spec.md", SPEC))
    assert doc.log == (
        LogItem("Q4", 12, is_open=True, deferred=True),
        LogItem("D1", 15, is_open=False, deferred=False),
        LogItem("D0", 16, is_open=False, deferred=False),
    )


def test_delta_sections(tmp_path: Path):
    text = """## ADDED Requirements

### Requirement: New thing
The system SHALL do it.

#### Scenario: NT-1 it works
- **WHEN** x
- **THEN** y

## MODIFIED Requirements

### Requirement: Old thing
The system SHALL do it better.

#### Scenario: OT-1 it still works
- **WHEN** x
"""
    doc = parse_markdown(write(tmp_path / "spec.md", text))
    assert [(r.name, r.section) for r in doc.requirements] == [
        ("New thing", "ADDED Requirements"),
        ("Old thing", "MODIFIED Requirements"),
    ]
    assert doc.requirements[1].scenarios[0].has_then is False


def test_fenced_requirement_ignored(tmp_path: Path):  # S4-R1-S6
    text = (
        "## Requirements\n\n```markdown\n### Requirement: Example\n"
        "#### Scenario: burst\n```\n"
    )
    assert parse_markdown(write(tmp_path / "spec.md", text)).requirements == ()


def test_crlf_and_bom(tmp_path: Path):  # Review Focus 1
    plain = parse_markdown(write(tmp_path / "a.md", SPEC))
    crlf = tmp_path / "b.md"
    _ = crlf.write_bytes(b"\xef\xbb\xbf" + SPEC.replace("\n", "\r\n").encode())
    other = parse_markdown(crlf)
    assert other.requirements == plain.requirements
    assert other.log == plain.log


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("RL-1 burst", "RL-1"),
        ("ABCD-12 x", "ABCD-12"),
        ("rl-1 burst", None),
        ("RL-0 burst", None),
        ("RL-01 burst", None),
        ("ABCDE-1 burst", None),
        ("burst RL-1", None),
        ("RL-1", "RL-1"),
    ],
)
def test_scenario_id_token(tmp_path: Path, name: str, expected: str | None):
    text = f"## Requirements\n\n### Requirement: R\nSHALL.\n\n#### Scenario: {name}\n"
    (req,) = parse_markdown(write(tmp_path / "s.md", text)).requirements
    assert req.scenarios[0].scenario_id == expected


def test_numbered_lines():
    text = "a\n```\nb\n```\nc\n"
    assert list(numbered_lines_outside_fences(text)) == [(1, "a"), (5, "c")]


def test_non_utf8_is_config_error(tmp_path: Path):
    path = tmp_path / "bad.md"
    _ = path.write_bytes(b"## Intent\n\xff\xfe\n")
    with pytest.raises(ConfigError, match=r"bad\.md"):
        _ = parse_markdown(path)
