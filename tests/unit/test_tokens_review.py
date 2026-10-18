"""Fixes from the S9 final review."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.paths import data_root
from grillspec.tokens import measure, render_markdown
from support import REPO, write

if TYPE_CHECKING:
    from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_tokens", REPO / "scripts" / "check_tokens.py"
)
assert _spec is not None
assert _spec.loader is not None
check_tokens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_tokens)


def test_cli_survives_a_legacy_console_encoding():  # I1
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    for args in (["tokens"], ["tokens", "--markdown"]):
        done = subprocess.run(
            [sys.executable, "-m", "grillspec", *args],
            capture_output=True,
            env=env,
            check=False,
            cwd=REPO,
        )
        assert done.returncode == 0, done.stderr.decode(errors="replace")


def _copy_skills(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    _ = shutil.copytree(data_root() / "skills", root / "skills")
    return root


def test_stray_and_binary_files_are_not_references(tmp_path: Path):  # M3
    root = _copy_skills(tmp_path)
    before = measure(root, None)
    folder = root / "skills" / "grillspec-archive"
    _ = (folder / ".DS_Store").write_bytes(b"\x00\x01\xff" * 2000)
    _ = (folder / "image.bin").write_bytes(b"\xff\xfe\x00" * 500)
    assert measure(root, None) == before


def test_description_change_makes_docs_stale(tmp_path: Path):  # M12 (TK-4)
    root = _copy_skills(tmp_path)
    skill = root / "skills" / "grillspec-archive" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    _ = skill.write_text(
        text.replace("description: ", "description: Much longer now. ", 1),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    for language in ("en", "ru"):
        (docs / language).mkdir(parents=True)
        _ = shutil.copy2(REPO / "docs" / language / "tokens.md", docs / language)
    assert check_tokens.stale(docs, measure(root, None)) == [
        docs / "en/tokens.md",
        docs / "ru/tokens.md",
    ]


@pytest.mark.parametrize(
    "content",
    [
        b"<!-- grillspec:memory:begin -->\n- x\n",  # unbalanced markers
        b"\xff\xfe broken \x80",  # not UTF-8
    ],
)
def test_broken_agents_file_is_one_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: bytes,
):  # M4
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    _ = (tmp_path / "AGENTS.md").write_bytes(content)
    monkeypatch.chdir(tmp_path)
    _ = capsys.readouterr()
    assert main(["tokens", "--project"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("grillspec: ")
    assert err.count("\n") == 1


def test_project_without_block_says_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # M5
    monkeypatch.chdir(tmp_path)
    assert main(["tokens", "--project"]) == 0
    assert "memory block            none" in capsys.readouterr().out


def test_router_row_and_references_wording():  # M6, M7
    table = render_markdown(measure(data_root(), None))
    assert "every session (hooks or `GIGACODE.md`)" in table
    assert "| `using-grillspec` | every session (the router above) |" in table
    assert "up to" in table


def test_russian_numbers_and_wording():  # M11
    table = render_markdown(measure(data_root(), None), "ru")
    assert "каталог скиллов:" in table
    assert "1,2" not in table
    assert "1 2" in table


def test_nul_filled_file_is_binary(tmp_path: Path):  # PR #4 review
    root = _copy_skills(tmp_path)
    before = measure(root, None)
    _ = (root / "skills" / "grillspec-archive" / "zeros.bin").write_bytes(
        b"\x00" * 9000
    )
    assert measure(root, None) == before


def test_markdown_with_project_lists_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):  # PR #4 review
    write(
        tmp_path / ".grillspec/config.toml",
        'version = 1\n[spec]\nbackend = "openspec"\n',
    )
    write(
        tmp_path / "AGENTS.md",
        "<!-- grillspec:memory:begin -->\n- [docs] x (change: a)\n<!-- grillspec:memory:end -->\n",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["tokens", "--markdown", "--project"]) == 0
    assert "| project memory block | every session |" in capsys.readouterr().out
    assert "memory block" not in render_markdown(measure(data_root(), None))


def test_cli_marks_router_as_counted(
    capsys: pytest.CaptureFixture[str],
):  # PR #4 review
    assert main(["tokens"]) == 0
    line = next(
        x for x in capsys.readouterr().out.splitlines() if "using-grillspec" in x
    )
    assert "counted in the router" in line
