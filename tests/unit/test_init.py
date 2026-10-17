"""Tests for ``init`` (spec S1-R7)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from grillspec.blocks import BEGIN, END
from grillspec.cli import main
from grillspec.config import Backend, load_config
from grillspec.init import init_project
from support import write

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_init_writes_everything(tmp_path: Path):
    write(tmp_path / "CLAUDE.md", "# Claude\n")
    changed = init_project(tmp_path, Backend.OPENSPEC)
    names = {path.relative_to(tmp_path).as_posix() for path in changed}
    assert names == {".grillspec/config.toml", ".gitignore", "AGENTS.md", "CLAUDE.md"}
    cfg = load_config(tmp_path, user_path=tmp_path / "none.toml").config
    assert cfg.backend is Backend.OPENSPEC
    assert ".grillspec/state.json" in (tmp_path / ".gitignore").read_text()
    assert BEGIN in (tmp_path / "AGENTS.md").read_text()
    assert (tmp_path / "CLAUDE.md").read_text() == "# Claude\n@AGENTS.md\n"
    assert not (tmp_path / "GIGACODE.md").exists()


def test_init_is_idempotent(tmp_path: Path):  # S1-R7-S1
    init_project(tmp_path, Backend.OPENSPEC)
    before = snapshot(tmp_path)
    assert init_project(tmp_path, Backend.OPENSPEC) == ()
    assert snapshot(tmp_path) == before


def test_init_preserves_user_content(tmp_path: Path):  # S1-R7-S2
    original = "# Agents\n\nUse tabs.\n"
    write(tmp_path / "AGENTS.md", original)
    init_project(tmp_path, Backend.SUPERPOWERS)
    text = (tmp_path / "AGENTS.md").read_text()
    assert text.startswith(original)
    assert text.rstrip().endswith(END)


def test_existing_config_untouched(tmp_path: Path):
    write(tmp_path / ".grillspec/config.toml", 'version = 1\n[grill]\ndepth = "deep"\n')
    init_project(tmp_path, Backend.OPENSPEC)
    assert "deep" in (tmp_path / ".grillspec/config.toml").read_text()


def test_dry_run_writes_nothing(tmp_path: Path):
    write(tmp_path / "GIGACODE.md", "x\n")
    before = snapshot(tmp_path)
    planned = init_project(tmp_path, Backend.OPENSPEC, dry_run=True)
    assert len(planned) == 4
    assert snapshot(tmp_path) == before


def test_cli_init_and_detect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--backend", "superpowers", "--dry-run"]) == 0
    assert "would change: AGENTS.md" in capsys.readouterr().out
    assert main(["init", "--backend", "superpowers"]) == 0
    capsys.readouterr()
    assert main(["init", "--backend", "superpowers"]) == 0
    assert "already set up" in capsys.readouterr().out
    assert main(["detect", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["recommended_backend"] == "superpowers"
