"""Tests for plan approval, its hash and the phase after edits (spec S6-R2, S6-R3)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.config import Backend
from grillspec.state import plan_hash
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
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected
"""
PLAN = f"""# {ID} — plan

**Spec:** docs/grillspec/specs/{ID}.md

## 1. Limiter

- [ ] 1.1 Burst limit — verify: pytest -k burst passes

Covers: RL-1 · Test: scenario-first

Files: create src/limit.py

1. Write test_burst. Expected: FAIL

- [ ] 1.2 Wire the CLI — verify: grillspec --help lists limit

Covers: — · Test: none: glue

Files: modify src/cli.py

1. Add the command.
"""
NEXT_STALE = "plan changed since approval: review it, then grillspec approve plan"


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
    assert main(["approve", "spec"]) == 0
    write(tmp_path / f"docs/grillspec/plans/{ID}.md", PLAN)
    return tmp_path


def _plan(project: Path) -> Path:
    return project / f"docs/grillspec/plans/{ID}.md"


def _sidecar(project: Path) -> str:
    return (project / f".grillspec/changes/{ID}.toml").read_text(encoding="utf-8")


def _status(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    _ = capsys.readouterr()
    assert main(["status", "--json"]) == 0
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


@pytest.mark.parametrize(
    "change",
    [("Test: none: glue", "Test: maybe"), ("- [ ] 1.2 Wire", "- [x] 1.2 Wire")],
)
def test_approval_refuses(  # PL-7
    project: Path, capsys: pytest.CaptureFixture[str], change: tuple[str, str]
):
    _ = _plan(project).write_text(PLAN.replace(*change), encoding="utf-8")
    before = _sidecar(project)
    _ = capsys.readouterr()
    assert main(["approve", "plan"]) == 1
    assert capsys.readouterr().err.rstrip().splitlines()[-1].startswith("grillspec: ")
    assert _sidecar(project) == before


def test_approval_writes_hash_and_executor(project: Path):  # PL-8
    assert main(["approve", "plan", "--executor", "inline"]) == 0
    text = _sidecar(project)
    assert "plan_approved = " in text
    assert f'plan_hash = "{plan_hash(project, Backend.SUPERPOWERS, ID)}"' in text
    assert 'executor = "inline"' in text


def test_ticking_boxes_keeps_the_hash(  # PL-9
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["approve", "plan"]) == 0
    before = plan_hash(project, Backend.SUPERPOWERS, ID)
    _ = _plan(project).write_text(
        PLAN.replace("- [ ] 1.1", "- [x] 1.1"), encoding="utf-8"
    )
    assert plan_hash(project, Backend.SUPERPOWERS, ID) == before
    assert _status(capsys)["phase"] == "execute"
    _ = _plan(project).write_text(PLAN.replace("- [ ]", "- [X]"), encoding="utf-8")
    status = _status(capsys)
    assert status["phase"] == "done"
    assert status["warnings"] == []


def test_edit_before_execution(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # PL-10
    assert main(["approve", "plan"]) == 0
    _ = _plan(project).write_text(
        PLAN.replace("Add the command.", "Add it."), encoding="utf-8"
    )
    status = _status(capsys)
    assert status["phase"] == "plan"
    assert status["next"] == NEXT_STALE


def test_deleting_open_tasks_is_not_done(  # PL-11
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert main(["approve", "plan"]) == 0
    ticked = PLAN.replace("- [ ] 1.1", "- [x] 1.1").split("- [ ] 1.2", 1)[0]
    _ = _plan(project).write_text(ticked, encoding="utf-8")
    status = _status(capsys)
    assert status["phase"] == "execute"
    assert "plan changed after approval" in cast("list[str]", status["warnings"])


def test_pre_s6_sidecar(project: Path, capsys: pytest.CaptureFixture[str]):  # PL-12
    text = _sidecar(project) + "plan_approved = 2026-10-17\n"
    write(project / f".grillspec/changes/{ID}.toml", text)
    _ = _plan(project).write_text(PLAN + "\nmore\n", encoding="utf-8")
    assert _status(capsys)["phase"] == "execute"


def test_hash_resets_every_box_style(project: Path):  # Review Focus 2
    before = plan_hash(project, Backend.SUPERPOWERS, ID)
    for mark in ("- [x] 1.1", "- [X] 1.1"):
        _ = _plan(project).write_text(PLAN.replace("- [ ] 1.1", mark), encoding="utf-8")
        assert plan_hash(project, Backend.SUPERPOWERS, ID) == before


def test_bogus_executor(project: Path):  # Review Focus 4
    before = _sidecar(project)
    with pytest.raises(SystemExit) as raised:
        _ = main(["approve", "plan", "--executor", "bogus"])
    assert raised.value.code == 2
    assert _sidecar(project) == before


def test_missing_plan(
    project: Path, capsys: pytest.CaptureFixture[str]
):  # Review Focus 5
    _plan(project).unlink()
    _ = capsys.readouterr()
    assert main(["approve", "plan"]) == 1
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "no plan" in err


def test_bad_sidecar_values(project: Path, capsys: pytest.CaptureFixture[str]):
    for line in ('plan_hash = "md5:x"', 'executor = "robot"'):
        write(
            project / f".grillspec/changes/{ID}.toml",
            _sidecar(project).split("plan_hash")[0] + line + "\n",
        )
        _ = capsys.readouterr()
        assert main(["status"]) == 1
        assert capsys.readouterr().err.count("\n") == 1


def test_executor_skill_named_when_installed(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    assert main(["approve", "plan", "--executor", "inline"]) == 0
    empty = project / "empty-data"
    empty.mkdir()
    monkeypatch.setattr("grillspec.state._phase.data_root", lambda: empty)
    status = _status(capsys)
    assert status["phase"] == "execute"
    assert status["next"] == "execute the plan"
    data = project / "data"
    write(data / "skills/grillspec-inline-execution/SKILL.md", "x")
    monkeypatch.setattr("grillspec.state._phase.data_root", lambda: data)
    assert _status(capsys)["next"] == "execute the plan with grillspec-inline-execution"
