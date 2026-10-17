"""Tests for ``grillspec validate`` and the advisory openspec call (S4-R1, S4-R2)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from fakes import make_fake, records
from grillspec.cli import main
from support import write

if TYPE_CHECKING:
    from pathlib import Path

SP_ID = "2026-10-17-limits"
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
OS_ID = "add-limits"
WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
DELTA = """## Purpose

Keeps webhook receivers safe from bursts of deliveries by one sender.

## ADDED Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive within a second
- **THEN** the eleventh is rejected
"""
ISSUES = {
    "items": [
        {
            "id": OS_ID,
            "issues": [
                {"level": "WARNING", "path": "limits/spec.md", "message": "be brief"}
            ],
        }
    ]
}


@pytest.fixture
def superpowers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> Path:
    assert bin_dir.is_dir()
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    write(tmp_path / f"docs/grillspec/specs/{SP_ID}.md", SPEC)
    write(
        tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{SP_ID}"}}\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def openspec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> Path:
    assert bin_dir.is_dir()
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    change = tmp_path / "openspec/changes" / OS_ID
    write(change / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- Limits.\n")
    write(change / "design.md", "# Design: add-limits\n\n## Decision log\n")
    write(change / "specs/limits/spec.md", DELTA)
    write(change / ".openspec.yaml", "schema: spec-driven\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_validate_text_and_exit(superpowers: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["validate", SP_ID]) == 0
    assert capsys.readouterr().out.strip() == "0 errors, 0 warnings"
    spec = superpowers / f"docs/grillspec/specs/{SP_ID}.md"
    _ = spec.write_text(SPEC.replace("RL-1 burst", "burst"), encoding="utf-8")
    assert main(["validate", SP_ID]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(f"error docs/grillspec/specs/{SP_ID}.md:17 scenario-id:")
    assert out[-1] == "1 errors, 0 warnings"


def test_validate_json_shape(superpowers: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["validate", "--json"]) == 0
    data = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert data == {"version": 1, "change": SP_ID, "errors": [], "warnings": []}
    assert superpowers.is_dir()


def test_validate_active_change_default(
    superpowers: Path, capsys: pytest.CaptureFixture[str]
):
    (superpowers / ".grillspec/state.json").unlink()
    assert main(["validate"]) == 1
    assert "no active change" in capsys.readouterr().err


def test_validate_unknown_change_one_line(  # Review Focus 3
    superpowers: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["validate", "nope"]) == 1
    err = capsys.readouterr().err
    assert err == "grillspec: no change nope\n"
    assert superpowers.is_dir()


def test_openspec_issues_become_warnings(
    openspec: Path, bin_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(
        bin_dir, "openspec", stdout=json.dumps(ISSUES), exit_code=1, record=record
    )
    assert main(["validate", OS_ID]) == 0
    out = capsys.readouterr().out.splitlines()
    where = f"openspec/changes/{OS_ID}/specs/limits/spec.md:0"
    finding = f"warning {where} openspec: WARNING limits/spec.md: be brief"
    assert out == [finding, "0 errors, 1 warnings"]
    (call,) = records(record)
    assert call["argv"] == ["validate", OS_ID, "--strict", "--json", "--no-interactive"]
    assert openspec.is_dir()


def test_openspec_broken_is_one_warning(  # S4-R2-S1
    openspec: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):
    _ = make_fake(bin_dir, "openspec", stdout="dyld: Library not loaded", exit_code=1)
    assert main(["validate", OS_ID, "--json"]) == 0
    data = cast(
        "dict[str, list[dict[str, object]]]", json.loads(capsys.readouterr().out)
    )
    assert data["errors"] == []
    (warning,) = data["warnings"]
    assert warning["rule"] == "openspec"
    assert str(warning["message"]).startswith("unavailable (")
    assert openspec.is_dir()


def test_openspec_absent_adds_nothing(
    openspec: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["validate", OS_ID]) == 0
    assert capsys.readouterr().out.strip() == "0 errors, 0 warnings"
    assert openspec.is_dir()


def test_superpowers_never_calls_openspec(
    superpowers: Path, bin_dir: Path, tmp_path: Path
):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "openspec", stdout="{}", record=record)
    assert main(["validate", SP_ID]) == 0
    assert records(record) == []
    assert superpowers.is_dir()
