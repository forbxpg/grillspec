"""Helpers shared by the tests."""

from __future__ import annotations

from pathlib import Path

GATED_ID = "add-limits"
_WHY = "Webhook receivers are overwhelmed by bursts of deliveries from one sender."
_DELTA = """## ADDED Requirements

### Requirement: Burst limit
The sender SHALL reject a burst over the limit.

#### Scenario: RL-1 burst exceeded
- **WHEN** 11 deliveries arrive
- **THEN** the eleventh is rejected
"""
_PLAN = f"""# plan

**Spec:** openspec/changes/{GATED_ID}/proposal.md

## 1. Work

- [ ] 1.1 Limit — verify: pytest passes

Covers: RL-1 · Test: scenario-first

Files: x
"""
PHASES = ("grill", "spec", "plan", "execute")


def write(path: Path, text: str) -> Path:
    """Write UTF-8 text, creating parent directories.

    Returns:
        Path - The written path.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")
    return path


def openspec_change(root: Path, change_id: str, *, grilled: bool) -> None:
    """Write an OpenSpec change with a valid proposal, delta and decision log."""
    folder = root / "openspec/changes" / change_id
    _ = write(folder / "proposal.md", f"## Why\n\n{_WHY}\n\n## What Changes\n\n- x\n")
    _ = write(folder / "design.md", "# Design\n\n## Decision log\n")
    _ = write(folder / "specs/limits/spec.md", _DELTA)
    sidecar = "version = 1\n" + ("grilled = 2026-10-17\n" if grilled else "")
    _ = write(root / f".grillspec/changes/{change_id}.toml", sidecar)


def phase_project(root: Path, phase: str) -> Path:
    """Build an OpenSpec project whose active change is in ``phase``.

    The working directory must already be ``root``.

    Returns:
        Path - The project root.

    """
    from grillspec.cli import main  # ruff: ignore[import-outside-top-level] - keep support importable without it

    assert Path.cwd().resolve() == root.resolve()
    _ = write(
        root / ".grillspec/config.toml", 'version = 1\n[spec]\nbackend = "openspec"\n'
    )
    openspec_change(root, GATED_ID, grilled=phase != "grill")
    _ = write(
        root / ".grillspec/state.json", f'{{"version": 1, "active": "{GATED_ID}"}}\n'
    )
    if PHASES.index(phase) >= PHASES.index("plan"):
        assert main(["approve", "spec"]) == 0
    if phase == "execute":
        _ = write(root / "openspec/changes" / GATED_ID / "tasks.md", _PLAN)
        assert main(["approve", "plan"]) == 0
    return root
