"""Fixes from the S6 final review."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.config import Backend
from grillspec.specs import parse_plan
from grillspec.state import plan_hash
from support import write

if TYPE_CHECKING:
    from pathlib import Path

WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
SCENARIOS = """### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected
"""


def _plan(link: str) -> str:
    return f"""# plan

**Spec:** {link}

## 1. Limiter

- [ ] 1.1 Burst limit — verify: pytest passes

Covers: RL-1 · Test: scenario-first

Files: create src/limit.py

1. Write the test. Expected: FAIL

- [ ] 1.2 Wire it — verify: help lists it

Covers: — · Test: none: glue

Files: modify src/cli.py

1. Add the command.
"""


@pytest.fixture(params=[Backend.SUPERPOWERS, Backend.OPENSPEC])
def project(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Backend, Path]:
    backend = cast("Backend", request.param)
    write(
        tmp_path / ".grillspec/config.toml",
        f'version = 1\n[spec]\nbackend = "{backend}"\n',
    )
    if backend is Backend.SUPERPOWERS:
        change = "2026-10-17-limits"
        spec = f"# x\n\n## Intent\n\nLimit.\n\n## Requirements\n\n{SCENARIOS}"
        write(tmp_path / f"docs/grillspec/specs/{change}.md", spec)
        plan = tmp_path / f"docs/grillspec/plans/{change}.md"
        link = f"docs/grillspec/specs/{change}.md"
    else:
        change = "add-limits"
        folder = tmp_path / "openspec/changes" / change
        write(folder / "proposal.md", f"## Why\n\n{WHY}\n\n## What Changes\n\n- x\n")
        purpose = (
            "Keeps webhook receivers safe from bursts of deliveries by one sender."
        )
        write(
            folder / "specs/limits/spec.md",
            f"## Purpose\n\n{purpose}\n\n## ADDED Requirements\n\n{SCENARIOS}",
        )
        write(folder / ".openspec.yaml", "schema: spec-driven\n")
        plan = folder / "tasks.md"
        link = f"openspec/changes/{change}/proposal.md"
    write(
        tmp_path / f".grillspec/changes/{change}.toml",
        "version = 1\ngrilled = 2026-10-17\n",
    )
    write(
        tmp_path / ".grillspec/state.json", f'{{"version": 1, "active": "{change}"}}\n'
    )
    monkeypatch.chdir(tmp_path)
    assert main(["approve", "spec"]) == 0
    write(plan, _plan(link))
    return tmp_path, backend, plan


def _phase(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    _ = capsys.readouterr()
    assert main(["status", "--json"]) == 0
    return cast("dict[str, object]", json.loads(capsys.readouterr().out))


def test_both_backends_approve_execute_done(
    project: tuple[Path, Backend, Path], capsys: pytest.CaptureFixture[str]
):  # I2: PL-8, PL-9 on both backends
    root, backend, plan = project
    assert main(["approve", "plan", "--executor", "subagent"]) == 0
    stored = plan_hash(
        root, backend, plan.parent.name if backend is Backend.OPENSPEC else plan.stem
    )
    text = plan.read_text(encoding="utf-8")
    _ = plan.write_text(text.replace("- [ ] 1.1", "- [x] 1.1"), encoding="utf-8")
    assert (
        plan_hash(
            root,
            backend,
            plan.parent.name if backend is Backend.OPENSPEC else plan.stem,
        )
        == stored
    )
    assert _phase(capsys)["phase"] == "execute"
    _ = plan.write_text(text.replace("- [ ]", "- [x]"), encoding="utf-8")
    assert _phase(capsys)["phase"] == "done"


def test_edit_mid_execution_can_be_reapproved(  # I1
    project: tuple[Path, Backend, Path], capsys: pytest.CaptureFixture[str]
):
    _, _, plan = project
    assert main(["approve", "plan"]) == 0
    done = plan.read_text(encoding="utf-8").replace("- [ ]", "- [x]")
    _ = plan.write_text(done.replace("src/cli.py", "src/main.py"), encoding="utf-8")
    status = _phase(capsys)
    assert status["phase"] == "execute"
    assert "plan changed after approval" in cast("list[str]", status["warnings"])
    assert main(["approve", "plan"]) == 0
    status = _phase(capsys)
    assert status["phase"] == "done"
    assert status["warnings"] == []


def test_first_approval_still_refuses_ticked_boxes(
    project: tuple[Path, Backend, Path], capsys: pytest.CaptureFixture[str]
):
    _, _, plan = project
    _ = plan.write_text(
        plan.read_text(encoding="utf-8").replace("- [ ] 1.1", "- [X] 1.1"),
        encoding="utf-8",
    )
    _ = capsys.readouterr()
    assert main(["approve", "plan"]) == 1
    assert "uncheck" in capsys.readouterr().err


def test_line_separators_do_not_shift_fences(tmp_path: Path):  # Minor 1
    text = (
        _plan("x")
        .replace("# plan", "# plan\u2028note")
        .replace(
            "1. Write the test. Expected: FAIL\n\n- [ ] 1.2",
            "1. Write the test. Expected: FAIL\n\n```\n- [ ] 1.9 fake — verify: x\n```\n- [ ] 1.2",
        )
    )
    plan = parse_plan(write(tmp_path / "p.md", text))
    assert [t.number for t in plan.tasks] == [(1, 1), (1, 2)]
    assert len(plan.bad_boxes) == 1


def test_plus_bullet_box_is_a_plan_error(
    project: tuple[Path, Backend, Path], capsys: pytest.CaptureFixture[str]
):  # Minor 2
    _, _, plan = project
    _ = plan.write_text(
        plan.read_text(encoding="utf-8") + "\n+ [ ] remember the changelog\n",
        encoding="utf-8",
    )
    _ = capsys.readouterr()
    assert main(["validate"]) == 1
    assert "plan-checkbox" in capsys.readouterr().out
