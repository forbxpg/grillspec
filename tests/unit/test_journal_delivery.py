"""The resume brief reaches new sessions (spec JR-R4, JR-9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grillspec.hooks import session_context
from grillspec.journal import Journal
from support import GATED_ID, REPO, phase_project

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_session_start_carries_the_brief(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):  # JR-9
    monkeypatch.chdir(tmp_path)
    root = phase_project(tmp_path, "spec")
    _ = Journal(root).add("handoff", "next: approve the spec", change=GATED_ID)
    context = session_context(root)
    assert f"grillspec memory: {GATED_ID} in the spec phase" in context
    assert "next: approve the spec" in context


def test_no_brief_outside_a_project(tmp_path: Path):
    lines = session_context(tmp_path).splitlines()
    assert not any(line.startswith("grillspec memory:") for line in lines)


def test_router_tells_the_agent_how_to_remember():
    router = (REPO / "skills/using-grillspec/SKILL.md").read_text(encoding="utf-8")
    assert "recall --brief" in router
    assert "note handoff" in router


def test_gigacode_context_asks_for_the_brief():
    context = (REPO / "gigacode-context.md").read_text(encoding="utf-8")
    assert "recall --brief" in context
