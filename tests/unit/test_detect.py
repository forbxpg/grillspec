"""Tests for brownfield detection and the backend recommendation."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from grillspec.config import Backend
from grillspec.detect import (
    Signals,
    available_clis,
    brownfield_signals,
    recommend_backend,
)
from support import write

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        (
            Signals(has_source=False, has_openspec=False, commit_count=0),
            Backend.SUPERPOWERS,
        ),
        (
            Signals(has_source=True, has_openspec=False, commit_count=0),
            Backend.OPENSPEC,
        ),
        (
            Signals(has_source=False, has_openspec=True, commit_count=0),
            Backend.OPENSPEC,
        ),
        (
            Signals(has_source=False, has_openspec=False, commit_count=100),
            Backend.OPENSPEC,
        ),
        (
            Signals(has_source=False, has_openspec=False, commit_count=99),
            Backend.SUPERPOWERS,
        ),
    ],
)
def test_recommend_backend_table(signals: Signals, expected: Backend):
    assert recommend_backend(signals) is expected


def test_signals_on_plain_dir(tmp_path: Path):
    write(tmp_path / "docs/readme.md", "x\n")
    assert brownfield_signals(tmp_path) == Signals(
        has_source=False, has_openspec=False, commit_count=0
    )
    write(tmp_path / "src/app.py", "x\n")
    write(tmp_path / "openspec/specs/a/spec.md", "x\n")
    assert brownfield_signals(tmp_path) == Signals(
        has_source=True, has_openspec=True, commit_count=0
    )


def test_docs_code_is_not_source(tmp_path: Path):
    write(tmp_path / "docs/example.py", "x\n")
    assert not brownfield_signals(tmp_path).has_source


def test_available_clis_reports_known_names():
    assert set(available_clis()) == {
        "claude",
        "cursor-agent",
        "codex",
        "gemini",
        "agy",
        "gigacode",
    }


def test_commit_count_ignores_parent_repository(tmp_path: Path):
    parent = tmp_path / "outer"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", str(parent)], check=True)
    subprocess.run(
        [*git, "-C", str(parent), "commit", "-q", "--allow-empty", "-m", "x"],
        check=True,
    )
    inner = parent / "plain"
    inner.mkdir()
    assert brownfield_signals(inner).commit_count == 0
