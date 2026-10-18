"""Tests for ``grillspec tokens`` (spec S9-R1)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.paths import data_root
from grillspec.tokens import BYTES_PER_TOKEN, estimate, measure, render_markdown
from support import write

if TYPE_CHECKING:
    from pathlib import Path

BLOCK = (
    "<!-- grillspec:memory:begin -->\n"
    "- [command] Run tests with uv run pytest (change: add-x)\n"
    "<!-- grillspec:memory:end -->\n"
)


@pytest.mark.parametrize(
    ("text", "tokens"), [("", 0), ("123456789", 2), ("1234", 1), ("привет", 3)]
)
def test_estimate_counts_bytes(text: str, tokens: int):  # TK-2
    assert estimate(text) == tokens


def test_measure_installed_skills():  # TK-1
    costs = measure(data_root(), None)
    assert costs.router > 0
    assert costs.catalogue > 0
    assert costs.memory is None
    names = [skill.name for skill in costs.skills]
    assert names == sorted(names)
    assert "using-grillspec" in names
    tdd = next(skill for skill in costs.skills if skill.name == "grillspec-tdd")
    assert tdd.body > 0
    assert tdd.references > 0  # writing-good-tests.md


def test_cli_table(capsys: pytest.CaptureFixture[str]):  # TK-1
    assert main(["tokens"]) == 0
    out = capsys.readouterr().out
    assert "always-on" in out
    assert "≈" in out
    assert "grillspec-grill" in out


def test_cli_json(capsys: pytest.CaptureFixture[str]):
    assert main(["tokens", "--json"]) == 0
    data = cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert data["bytes_per_token"] == BYTES_PER_TOKEN
    assert isinstance(data["skills"], list)


def test_project_memory_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # TK-3
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    write(tmp_path / "AGENTS.md", "# Project\n\n" + BLOCK)
    monkeypatch.chdir(tmp_path)
    costs = measure(data_root(), tmp_path)
    assert costs.memory == estimate(BLOCK.rstrip("\n"))
    assert main(["tokens", "--project"]) == 0
    assert "memory block" in capsys.readouterr().out


def test_markdown_is_deterministic():
    first = render_markdown(measure(data_root(), None))
    assert first == render_markdown(measure(data_root(), None))
    assert first.startswith("| ")
    assert "\r" not in first
