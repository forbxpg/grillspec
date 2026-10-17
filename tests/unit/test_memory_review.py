"""Fixes from the S5 final review."""

from __future__ import annotations

import stat
import sys
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.memory import Entry, MemoryBlockError, add_entry, read_entries
from support import write

if TYPE_CHECKING:
    from pathlib import Path

CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _add(*args: str) -> int:
    return main(["memory", "add", "--category", "gotcha", "--change", "c1", *args])


@pytest.mark.parametrize("sep", [chr(0x2028), "\x85", "\x0b", "\x0c", "\x1c"])
def test_unicode_line_breaks_refused(project: Path, sep: str):  # I1
    write(project / "AGENTS.md", "# A\n")
    before = (project / "AGENTS.md").read_bytes()
    with pytest.raises(MemoryBlockError):
        _ = add_entry("", Entry("gotcha", f"a{sep}b", "c1"))
    assert _add(f"a{sep}b") == 1
    assert (project / "AGENTS.md").read_bytes() == before


def test_unbalanced_router_markers_one_line(  # I2
    project: Path, capsys: pytest.CaptureFixture[str]
):
    write(project / "AGENTS.md", "<!-- grillspec:begin -->\nrouter\n")
    assert _add("x") == 1
    assert capsys.readouterr().err.count("\n") == 1


def test_bom_before_router_block(project: Path):  # I2
    agents = project / "AGENTS.md"
    _ = agents.write_bytes(
        "﻿<!-- grillspec:begin -->\nr\n<!-- grillspec:end -->\n".encode()
    )
    assert _add("x") == 0
    text = agents.read_text(encoding="utf-8")
    assert text.index("<!-- grillspec:end -->") < text.index("grillspec:memory:begin")
    assert len(read_entries(text)) == 1


def test_user_config_backend_does_not_count(  # I3
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    home = tmp_path / "xdg"
    write(home / "grillspec/config.toml", CONFIG)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    assert _add("x") == 1
    assert "not set up here" in capsys.readouterr().err
    assert not (work / "AGENTS.md").exists()


def test_unknown_category_exit_1_one_line(  # I4
    project: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["memory", "add", "--category", "misc", "--change", "c1", "x"])
    assert code == 1
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "unknown category 'misc'" in err
    assert project.is_dir()


def test_text_starting_with_dash(project: Path):  # I6
    assert _add("--", "-x flag breaks parsing") == 0
    (entry,) = read_entries((project / "AGENTS.md").read_text(encoding="utf-8"))
    assert entry.text == "-x flag breaks parsing"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlinks and modes")
def test_symlinked_agents_md_is_written_through(project: Path):  # I7
    target = write(project / "CLAUDE.md", "# Claude\n")
    (project / "AGENTS.md").symlink_to(target.name)
    assert _add("x") == 0
    assert (project / "AGENTS.md").is_symlink()
    assert "grillspec:memory:begin" in target.read_text(encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_mode_preserved(project: Path):  # I7
    agents = write(project / "AGENTS.md", "# A\n")
    agents.chmod(0o644)
    assert _add("x") == 0
    assert stat.S_IMODE(agents.stat().st_mode) == 0o644
