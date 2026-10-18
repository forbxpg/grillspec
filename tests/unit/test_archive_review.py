"""Fixes from the S7b final review."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from fakes import make_fake
from grillspec.cli import main
from grillspec.paths import write_atomic
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
"""
MODIFIED = """## MODIFIED Requirements

### Requirement: Session expiry
The system SHALL expire sessions after 15 minutes.

#### Scenario: AU-1 idle session
- **WHEN** a session is idle for 16 minutes
- **THEN** the next request is rejected
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
PLAN = f"""# plan

**Spec:** openspec/changes/{ID}/proposal.md

## 1. Work

- [ ] 1.1 Work — verify: pytest passes

Covers: RL-1, AU-1 · Test: scenario-first

Files: x
"""


def _setup(root: Path, living: str = LIVING, modified: str = MODIFIED) -> Path:
    write(
        root / ".grillspec/config.toml", 'version = 1\n[spec]\nbackend = "openspec"\n'
    )
    write(root / "openspec/specs/auth/spec.md", living)
    folder = root / "openspec/changes" / ID
    write(folder / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- x\n")
    write(folder / "specs/auth/spec.md", modified)
    write(folder / "specs/limits/spec.md", NEW_CAP)
    write(folder / ".openspec.yaml", "schema: spec-driven\n")
    write(root / f".grillspec/changes/{ID}.toml", "version = 1\ngrilled = 2026-10-17\n")
    write(root / ".grillspec/state.json", f'{{"version": 1, "active": "{ID}"}}\n')
    assert main(["approve", "spec"]) == 0
    write(folder / "tasks.md", PLAN)
    assert main(["approve", "plan"]) == 0
    write(folder / "tasks.md", PLAN.replace("- [ ]", "- [x]"))
    return folder


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> Path:
    assert bin_dir.is_dir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _snapshot(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in (root / "openspec").rglob("*") if p.is_file()}


def test_stale_spec_refused(root: Path, capsys: pytest.CaptureFixture[str]):  # I1
    folder = _setup(root)
    write(folder / "specs/auth/spec.md", MODIFIED.replace("15 minutes", "10 minutes"))
    before = _snapshot(root)
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "changed since approval" in capsys.readouterr().err
    assert _snapshot(root) == before


def test_level4_heading_loss_refused(
    root: Path, capsys: pytest.CaptureFixture[str]
):  # I2
    living = LIVING + "\n#### Edge case\nNotes that must not vanish.\n"
    _setup(root, living=living)
    before = _snapshot(root)
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "Edge case" in capsys.readouterr().err
    assert _snapshot(root) == before


def test_fenced_scenario_is_not_counted(root: Path):  # I2
    living = LIVING.replace(
        "- **THEN** the next request is rejected\n",
        "- **THEN** the next request is rejected\n\n```markdown\n#### Scenario: example\n```\n",
    )
    modified = MODIFIED + "\n```markdown\n#### Scenario: example\n```\n"
    _setup(root, living=living, modified=modified)
    assert main(["archive"]) == 0


def test_duplicate_living_names_refused(root: Path):  # I2
    living = LIVING + "\n" + LIVING.split("## Requirements\n\n", 1)[1]
    _setup(root, living=living)
    before = _snapshot(root)
    assert main(["archive"]) == 1
    assert _snapshot(root) == before


def test_write_failure_restores_everything(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # I3
    _setup(root)
    before = _snapshot(root)
    calls: list[Path] = []

    def flaky(path: Path, text: str) -> None:
        calls.append(path)
        if len(calls) == 2:
            raise PermissionError(13, "Permission denied", str(path))
        write_atomic(path, text)

    monkeypatch.setattr("grillspec.archive._archive.write_atomic", flaky)
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: ")
    assert err.count("\n") == 1
    assert _snapshot(root) == before


def test_move_failure_restores_everything(
    root: Path, monkeypatch: pytest.MonkeyPatch
):  # I3
    _setup(root)
    before = _snapshot(root)

    def boom(src: str, _dst: str) -> str:
        raise OSError(16, "Resource busy", src)

    monkeypatch.setattr("grillspec.archive._archive.shutil.move", boom)
    assert main(["archive"]) == 1
    assert _snapshot(root) == before


def _openspec(bin_dir: Path, *body: str) -> None:
    """Fake an OpenSpec CLI whose ``--version`` works and whose archive runs ``body``."""
    _ = make_fake(bin_dir, "openspec")
    lines = [
        "import shutil, sys",
        "if sys.argv[1:] == ['--version']:",
        "    print('1.12.0'); sys.exit(0)",
        *body,
    ]
    _ = (bin_dir / "_openspec_fake.py").write_text("\n".join(lines), encoding="utf-8")


def _moves(root: Path) -> str:
    folder = (root / "openspec/changes" / ID).as_posix()
    target = (root / "openspec/changes/archive" / f"{TODAY}-{ID}").as_posix()
    return f"shutil.move({folder!r}, {target!r})"


def test_openspec_failure_shows_its_stdout(
    root: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):  # I4
    _setup(root)
    _openspec(bin_dir, "print('Validation failed: auth spec'); sys.exit(1)")
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "Validation failed: auth spec" in capsys.readouterr().err


def test_openspec_success_relays_its_output(
    root: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):  # I5
    _setup(root)
    _openspec(bin_dir, _moves(root), "print('Applying changes: auth ~1')")
    _ = capsys.readouterr()
    assert main(["archive"]) == 0
    assert "Applying changes: auth ~1" in capsys.readouterr().out


def test_openspec_success_without_the_move_refused(
    root: Path, bin_dir: Path, capsys: pytest.CaptureFixture[str]
):  # I5
    _setup(root)
    _openspec(bin_dir, "print('ok')")
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert "still there" in capsys.readouterr().err


def test_cli_path_is_not_blocked_by_bundled_check(root: Path, bin_dir: Path):  # I6
    living = LIVING + "\n#### Edge case\nNotes.\n"  # the bundled merge would refuse
    _setup(root, living=living)
    _openspec(bin_dir, _moves(root))
    assert main(["archive"]) == 0
    assert (root / "openspec/changes/archive" / f"{TODAY}-{ID}").is_dir()
    assert main(["archive", "--dry-run"]) == 1  # nothing active any more


def test_rename_header_is_rewritten_exactly(root: Path):  # minor
    living = LIVING.replace("Session expiry", "Re")
    rename = (
        "## RENAMED Requirements\n\n- FROM: `### Requirement: Re`\n"
        "- TO: `### Requirement: Retry`\n\n"
    )
    _setup(
        root,
        living=living,
        modified=rename + MODIFIED.replace("Session expiry", "Retry"),
    )
    assert main(["archive"]) == 0
    text = (root / "openspec/specs/auth/spec.md").read_text(encoding="utf-8")
    assert "### Requirement: Retry\n" in text
    assert "quirement: Re\n" not in text


def test_no_active_change_message(root: Path, capsys: pytest.CaptureFixture[str]):
    _ = _setup(root)
    write(root / ".grillspec/state.json", '{"version": 1, "active": null}\n')
    _ = capsys.readouterr()
    assert main(["archive"]) == 1
    assert capsys.readouterr().err.startswith("grillspec: no active change: ")


def test_nested_title_uses_full_path(root: Path):  # minor
    folder = _setup(root)
    (folder / "specs/limits/spec.md").unlink()
    write(folder / "specs/net/limits/spec.md", NEW_CAP)
    assert main(["approve", "spec"]) == 0
    assert main(["archive"]) == 0
    text = (root / "openspec/specs/net/limits/spec.md").read_text(encoding="utf-8")
    assert text.startswith("# net/limits Specification\n")


def test_removed_requirement(root: Path, capsys: pytest.CaptureFixture[str]):
    living = LIVING + "\n### Requirement: Legacy\nThe system SHALL keep cookies.\n"
    removed = MODIFIED + (
        "\n## REMOVED Requirements\n\n### Requirement: Legacy\n"
        "**Reason**: cookies are gone.\n**Migration**: none.\n"
    )
    _setup(root, living=living, modified=removed)
    _ = capsys.readouterr()
    assert main(["archive"]) == 0
    out = capsys.readouterr().out
    assert "auth: remove 'Legacy'" in out
    text = (root / "openspec/specs/auth/spec.md").read_text(encoding="utf-8")
    assert "Legacy" not in text


def test_crlf_bytes_exact(root: Path):
    _setup(root, living=LIVING.replace("\n", "\r\n"))
    assert main(["archive"]) == 0
    expected = LIVING.replace("30 minutes", "15 minutes").replace(
        "31 minutes", "16 minutes"
    )
    data = (root / "openspec/specs/auth/spec.md").read_bytes()
    assert data == expected.replace("\n", "\r\n").encode()
