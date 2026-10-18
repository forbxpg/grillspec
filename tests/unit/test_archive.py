"""Tests for ``grillspec archive`` (spec S7B-R1)."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, cast

import pytest

from fakes import make_fake, records
from grillspec.cli import main
from support import write

if TYPE_CHECKING:
    from pathlib import Path

TODAY = dt.datetime.now().astimezone().date().isoformat()
ID = "add-limits"
WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
LIVING = """# auth Specification

## Purpose

Lets users sign in with a password and keeps sessions alive across requests.

## Requirements

### Requirement: Session expiry
The system SHALL expire sessions after 30 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 31 minutes
- **THEN** the next request is rejected

### Requirement: Login
The system SHALL let users log in.

#### Scenario: AU-2 login
- **WHEN** the password is right
- **THEN** a session starts
"""
NEW_CAP = """## Purpose

Keeps webhook receivers safe from bursts of deliveries by one sender.

## ADDED Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected
"""
AUTH_DELTA = """## RENAMED Requirements

- FROM: `### Requirement: Login`
- TO: `### Requirement: Sign in`

## MODIFIED Requirements

### Requirement: Session expiry
The system SHALL expire sessions after 15 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 16 minutes
- **THEN** the next request is rejected
"""
PLAN = f"""# plan

**Spec:** openspec/changes/{ID}/proposal.md

## 1. Work

- [x] 1.1 Limit — verify: pytest passes

Covers: RL-1, AU-1 · Test: scenario-first

Files: x
"""


def _status(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    _ = capsys.readouterr()
    assert main(["status", "--json"]) == 0
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


@pytest.fixture
def openspec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> Path:
    assert bin_dir.is_dir()
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    write(tmp_path / "openspec/specs/auth/spec.md", LIVING)
    folder = tmp_path / "openspec/changes" / ID
    write(folder / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- x\n")
    write(folder / "design.md", "# Design\n\n## Decision log\n")
    write(folder / "specs/limits/spec.md", NEW_CAP)
    write(folder / "specs/auth/spec.md", AUTH_DELTA)
    write(folder / ".openspec.yaml", "schema: spec-driven\n")
    write(
        tmp_path / f".grillspec/changes/{ID}.toml",
        "version = 1\ngrilled = 2026-10-17\n",
    )
    write(tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{ID}"}}\n')
    monkeypatch.chdir(tmp_path)
    assert main(["approve", "spec"]) == 0
    write(folder / "tasks.md", PLAN.replace("- [x]", "- [ ]"))
    assert main(["approve", "plan"]) == 0
    write(folder / "tasks.md", PLAN)
    return tmp_path


def test_refuses_when_not_done(
    openspec: Path, capsys: pytest.CaptureFixture[str]
):  # AR-1
    tasks = openspec / "openspec/changes" / ID / "tasks.md"
    write(tasks, PLAN.replace("- [x]", "- [ ]"))
    before = (openspec / "openspec/specs/auth/spec.md").read_bytes()
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: the change is not done: ")
    assert (openspec / "openspec/specs/auth/spec.md").read_bytes() == before


def test_bundled_archive_merges_deltas(  # AR-2
    openspec: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["archive"]) == 0
    auth = (openspec / "openspec/specs/auth/spec.md").read_text(encoding="utf-8")
    assert "15 minutes" in auth
    assert "30 minutes" not in auth
    assert "### Requirement: Sign in" in auth
    assert "### Requirement: Login" not in auth
    assert "AU-2 login" in auth
    limits = (openspec / "openspec/specs/limits/spec.md").read_text(encoding="utf-8")
    assert limits.startswith("# limits Specification\n\n## Purpose\n\nKeeps webhook")
    assert "### Requirement: Burst limit" in limits
    assert not (openspec / "openspec/changes" / ID).exists()
    assert (openspec / "openspec/changes/archive" / f"{TODAY}-{ID}/tasks.md").is_file()
    assert _status(capsys)["phase"] == "idle"


def test_nothing_written_on_conflict(  # AR-3
    openspec: Path, capsys: pytest.CaptureFixture[str]
):
    delta = openspec / "openspec/changes" / ID / "specs/auth/spec.md"
    write(
        delta,
        AUTH_DELTA.replace(
            "#### Scenario: AU-1 idle session", "#### Scenario: AU-1 idle"
        ),
    )
    assert main(["approve", "spec"]) == 0
    before = {p: p.read_bytes() for p in (openspec / "openspec").rglob("*.md")}
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "AU-1 idle session" in capsys.readouterr().err
    assert {p: p.read_bytes() for p in (openspec / "openspec").rglob("*.md")} == before


def test_dry_run_changes_nothing(  # AR-5
    openspec: Path, capsys: pytest.CaptureFixture[str]
):
    before = {p: p.read_bytes() for p in (openspec / "openspec").rglob("*.md")}
    _ = capsys.readouterr()
    assert main(["archive", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "auth: rename 'Login' → 'Sign in'" in out
    assert "auth: modify 'Session expiry'" in out
    assert "limits: create spec" in out
    assert "limits: add 'Burst limit'" in out
    assert {p: p.read_bytes() for p in (openspec / "openspec").rglob("*.md")} == before


def test_openspec_cli_used_when_it_runs(openspec: Path, bin_dir: Path, tmp_path: Path):
    record = tmp_path / "rec.jsonl"
    _ = make_fake(bin_dir, "openspec", stdout="1.12.0\n", record=record)
    assert main(["archive"]) == 1  # the fake leaves the change folder in place
    argvs = [call["argv"] for call in records(record)]
    assert ["archive", ID, "--yes"] in argvs
    living = (openspec / "openspec/specs/auth/spec.md").read_text(encoding="utf-8")
    assert "30 minutes" in living  # the fake changed nothing; grillspec did not merge


def test_broken_openspec_cli_falls_back_to_bundled(openspec: Path, bin_dir: Path):
    _ = make_fake(bin_dir, "openspec", stdout="dyld: Library not loaded", exit_code=1)
    assert main(["archive"]) == 0
    assert "15 minutes" in (openspec / "openspec/specs/auth/spec.md").read_text(
        encoding="utf-8"
    )


def test_crlf_living_spec_kept_outside_blocks(openspec: Path):  # Review Focus 1
    path = openspec / "openspec/specs/auth/spec.md"
    _ = path.write_bytes(LIVING.replace("\n", "\r\n").encode())
    assert main(["archive"]) == 0
    data = path.read_bytes()
    assert data.startswith(b"# auth Specification\r\n\r\n## Purpose\r\n")
    assert b"\n" not in data.replace(b"\r\n", b"")


@pytest.mark.parametrize(
    "delta",
    [
        AUTH_DELTA.replace(
            "FROM: `### Requirement: Login`", "FROM: `### Requirement: Logon`"
        ),
        AUTH_DELTA.replace(
            "TO: `### Requirement: Sign in`", "TO: `### Requirement: Session expiry`"
        ),
    ],
)
def test_bad_rename_refused(  # Review Focus 2
    openspec: Path, delta: str, capsys: pytest.CaptureFixture[str]
):
    write(openspec / "openspec/changes" / ID / "specs/auth/spec.md", delta)
    assert main(["approve", "spec"]) == 0
    before = (openspec / "openspec/specs/auth/spec.md").read_bytes()
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "RENAMED" in capsys.readouterr().err
    assert (openspec / "openspec/specs/auth/spec.md").read_bytes() == before


def test_archive_folder_exists(
    openspec: Path, capsys: pytest.CaptureFixture[str]
):  # RF 3
    (openspec / "openspec/changes/archive" / f"{TODAY}-{ID}").mkdir(parents=True)
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert capsys.readouterr().err.count("\n") == 1


def test_nested_capability_created(openspec: Path):  # Review Focus 5
    folder = openspec / "openspec/changes" / ID / "specs"
    (folder / "limits/spec.md").rename(folder / "limits.md")
    write(folder / "net/limits/spec.md", NEW_CAP)
    (folder / "limits.md").unlink()
    assert main(["approve", "spec"]) == 0
    assert main(["archive"]) == 0
    assert (openspec / "openspec/specs/net/limits/spec.md").is_file()


@pytest.fixture
def superpowers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    change = "2026-10-17-limits"
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "superpowers"\n',
    )
    spec = (
        "# x\n\n## Intent\n\nLimit.\n\n## Requirements\n\n"
        + NEW_CAP.split("## ADDED Requirements\n\n", 1)[1]
    )
    write(tmp_path / f"docs/grillspec/specs/{change}.md", spec)
    write(
        tmp_path / f".grillspec/changes/{change}.toml",
        "version = 1\ngrilled = 2026-10-17\n",
    )
    write(
        tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{change}"}}\n'
    )
    monkeypatch.chdir(tmp_path)
    assert main(["approve", "spec"]) == 0
    plan = PLAN.replace(
        f"openspec/changes/{ID}/proposal.md", f"docs/grillspec/specs/{change}.md"
    ).replace("RL-1, AU-1", "RL-1")
    write(
        tmp_path / f"docs/grillspec/plans/{change}.md", plan.replace("- [x]", "- [ ]")
    )
    assert main(["approve", "plan"]) == 0
    write(tmp_path / f"docs/grillspec/plans/{change}.md", plan)
    return tmp_path


def test_superpowers_archive(  # AR-4, Review Focus 4
    superpowers: Path, capsys: pytest.CaptureFixture[str]
):
    change = "2026-10-17-limits"
    assert main(["archive"]) == 0
    sidecar = (superpowers / f".grillspec/changes/{change}.toml").read_text(
        encoding="utf-8"
    )
    assert f"archived = {TODAY}" in sidecar
    assert _status(capsys)["phase"] == "idle"
    assert main(["use", change]) == 1
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert capsys.readouterr().err.count("\n") == 1
