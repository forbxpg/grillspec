"""Tests for ``grillspec memory`` (spec S5-R2)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from grillspec.cli import main
from grillspec.memory import MEMORY_BEGIN, MEMORY_END
from support import write

if TYPE_CHECKING:
    from pathlib import Path

CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'
TESTS = "Run tests with uv run pytest"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _add(text: str, category: str = "command", change: str = "add-x") -> int:
    return main(["memory", "add", "--category", category, "--change", change, text])


def test_add_creates_block_and_list_counts(  # S5-R2-S1
    project: Path, capsys: pytest.CaptureFixture[str]
):
    write(
        project / "AGENTS.md",
        "# Agents\n\n<!-- grillspec:begin -->\nr\n<!-- grillspec:end -->\n",
    )
    assert _add(TESTS) == 0
    assert capsys.readouterr().out == "added 1/40\n"
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert text.index("<!-- grillspec:end -->") < text.index(MEMORY_BEGIN)
    assert main(["memory", "list"]) == 0
    assert capsys.readouterr().out == (f"1. [command] {TESTS} (add-x)\n1/40 entries\n")


def test_cli_refusals_leave_file_unchanged(  # S5-R2-S2
    project: Path, capsys: pytest.CaptureFixture[str]
):
    assert _add(TESTS) == 0
    before = (project / "AGENTS.md").read_bytes()
    _ = capsys.readouterr()
    assert _add("x" * 161) == 1
    assert _add("  run TESTS with uv run pytest ") == 1
    assert _add("x", change="bad id") == 1
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 3
    assert all(line.startswith("grillspec: ") for line in err)
    assert _add("x", category="misc") == 1
    assert (project / "AGENTS.md").read_bytes() == before


def test_retire(project: Path, capsys: pytest.CaptureFixture[str]):  # S5-R2-S3
    for n in range(3):
        assert _add(f"fact {n}") == 0
    assert main(["memory", "retire", "2"]) == 0
    assert capsys.readouterr().out.endswith("retired 2\n")
    assert main(["memory", "list", "--json"]) == 0
    data = cast(
        "dict[str, list[dict[str, object]]]", json.loads(capsys.readouterr().out)
    )
    assert [e["text"] for e in data["entries"]] == ["fact 0", "fact 2"]
    assert project.is_dir()


def test_list_json_shape(project: Path, capsys: pytest.CaptureFixture[str]):
    assert main(["memory", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "version": 1,
        "cap": 40,
        "entries": [],
    }
    assert _add(TESTS) == 0
    _ = capsys.readouterr()
    assert main(["memory", "list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["entries"] == [
        {"n": 1, "category": "command", "text": TESTS, "change": "add-x"}
    ]
    assert project.is_dir()


def test_not_set_up(  # Review Focus 4
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert _add(TESTS) == 1
    assert "grillspec is not set up here; run grillspec init" in capsys.readouterr().err
    assert not (tmp_path / "AGENTS.md").exists()


@pytest.mark.parametrize("number", ["0", "-1", "41"])
def test_retire_bad_numbers(  # Review Focus 5
    project: Path, capsys: pytest.CaptureFixture[str], number: str
):
    assert _add(TESTS) == 0
    _ = capsys.readouterr()
    assert main(["memory", "retire", number]) == 1
    assert capsys.readouterr().err.count("\n") == 1
    assert project.is_dir()


def test_retire_not_a_number(project: Path):
    with pytest.raises(SystemExit) as raised:
        _ = main(["memory", "retire", "abc"])
    assert raised.value.code == 2
    assert project.is_dir()


def test_broken_markers_one_line(project: Path, capsys: pytest.CaptureFixture[str]):
    write(project / "AGENTS.md", f"{MEMORY_BEGIN}\n- [command] x (a)\n")
    before = (project / "AGENTS.md").read_bytes()
    assert main(["memory", "list"]) == 1
    assert _add(TESTS) == 1
    err = capsys.readouterr().err.splitlines()
    assert (
        err
        == [
            "grillspec: unbalanced grillspec memory markers in AGENTS.md; fix them by hand"
        ]
        * 2
    )
    assert (project / "AGENTS.md").read_bytes() == before


def test_crlf_file_stays_crlf(project: Path):
    write(project / "AGENTS.md", "")
    (project / "AGENTS.md").write_bytes(b"# Agents\r\n")
    assert _add(TESTS) == 0
    data = (project / "AGENTS.md").read_bytes()
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert MEMORY_END.encode() in data


def test_uninstall_leaves_agents_md(project: Path):  # S5-R1-S2 end to end
    assert _add(TESTS) == 0
    before = (project / "AGENTS.md").read_bytes()
    assert main(["install", "--harness", "codex", "--copy"]) == 0
    assert main(["uninstall", "--harness", "codex"]) == 0
    assert (project / "AGENTS.md").read_bytes() == before
