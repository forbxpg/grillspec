"""The skills adapted from Superpowers reference nothing grillspec does not ship (EX-6)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2] / "skills"
VENDORED = {
    "grillspec-subagent-execution": (
        "implementer-prompt.md",
        "task-reviewer-prompt.md",
        "re-review-prompt.md",
    ),
    "grillspec-inline-execution": (),
    "grillspec-tdd": ("writing-good-tests.md",),
    "grillspec-debugging": (
        "root-cause-tracing.md",
        "defense-in-depth.md",
        "condition-based-waiting.md",
    ),
    "grillspec-verification": (),
    "grillspec-requesting-review": ("code-reviewer.md",),
    "grillspec-receiving-review": (),
    "grillspec-worktrees": (),
    "grillspec-finishing": (),
    "grillspec-parallel-agents": (),
}
_SKIPPED = "brainstorming|writing-plans|using-superpowers|writing-skills|diagnosing-superpowers"
FORBIDDEN = re.compile(
    rf"superpowers:|scripts/|\.superpowers/|docs/superpowers/|### Task \d|\b({_SKIPPED})\b"
)


@pytest.mark.parametrize(("skill", "extra"), sorted(VENDORED.items()))
def test_vendored_files_exist(skill: str, extra: tuple[str, ...]):
    for name in ("SKILL.md", *extra):
        assert (SKILLS / skill / name).is_file(), f"{skill}/{name}"


@pytest.mark.parametrize("skill", sorted(VENDORED))
def test_no_foreign_references(skill: str):  # EX-6
    hits = [
        f"{path.name}:{n}: {line.strip()}"
        for path in sorted((SKILLS / skill).glob("*.md"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert hits == []


def test_executors_use_grillspec_exec():
    for skill in ("grillspec-subagent-execution", "grillspec-inline-execution"):
        text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "grillspec exec start" in text
        assert "grillspec exec done" in text
        assert "grillspec exec review-package" in text


def test_tdd_states_the_d5_model():
    text = (SKILLS / "grillspec-tdd" / "SKILL.md").read_text(encoding="utf-8")
    assert "batch-red" in text
    for strategy in ("scenario-first", "reproduce-first", "characterization", "none:"):
        assert strategy in text
