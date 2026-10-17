"""Tests for the fallback installer (spec S1-R6)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from grillspec.cli import main
from grillspec.hooks import Harness
from grillspec.install import Scope, install, uninstall
from support import write

if TYPE_CHECKING:
    from pathlib import Path

IMPORT = "@.gigacode/skills/using-grillspec/SKILL.md"


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_gigacode_project_install(tmp_path: Path):  # S1-R6-S1
    result = install(
        Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False
    )
    assert result.native_command is None
    router = tmp_path / ".gigacode/skills/using-grillspec/SKILL.md"
    assert router.is_file()
    assert IMPORT in (tmp_path / "GIGACODE.md").read_text().splitlines()
    receipt = json.loads((tmp_path / ".grillspec/install-receipt.json").read_text())
    entry = receipt["installs"]["gigacode"]
    assert receipt["version"] == 1
    assert entry["scope"] == "project"
    assert ".gigacode/skills/using-grillspec/SKILL.md" in entry["files"]
    assert entry["lines"] == [{"file": "GIGACODE.md", "line": IMPORT}]
    assert set(result.planned) >= {router, tmp_path / "GIGACODE.md"}


def test_uninstall_is_exact(tmp_path: Path):  # S1-R6-S2
    write(tmp_path / "GIGACODE.md", "# Mine\n")
    write(tmp_path / ".gigacode/skills/own-skill/SKILL.md", "mine\n")
    install(Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    giga = tmp_path / "GIGACODE.md"
    giga.write_text(giga.read_text().replace("# Mine", "# Mine, edited"))
    removed = uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert removed
    assert giga.read_text() == "# Mine, edited\n"
    assert not (tmp_path / ".gigacode/skills/using-grillspec").exists()
    assert (tmp_path / ".gigacode/skills/own-skill/SKILL.md").is_file()
    assert not (tmp_path / ".grillspec/install-receipt.json").exists()


def test_uninstall_keeps_other_harness_entries(tmp_path: Path):
    install(Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    install(Harness.CODEX, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    receipt = json.loads((tmp_path / ".grillspec/install-receipt.json").read_text())
    assert set(receipt["installs"]) == {"codex"}
    assert (tmp_path / ".agents/skills/using-grillspec/SKILL.md").is_file()


def test_dry_run_writes_nothing(tmp_path: Path):  # S1-R6-S3
    before = snapshot(tmp_path)
    result = install(
        Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=True
    )
    assert result.planned
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("harness", "needle"),
    [
        (Harness.CLAUDE, "claude plugin install grillspec@grillspec"),
        (Harness.CODEX, "codex plugin marketplace add forbxpg/grillspec"),
        (Harness.CURSOR, "/add-plugin forbxpg/grillspec"),
        (
            Harness.ANTIGRAVITY,
            "agy plugin install https://github.com/forbxpg/grillspec",
        ),
    ],
)
def test_native_harness_prints_command_without_copy(
    tmp_path: Path, harness: Harness, needle: str
):
    result = install(harness, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    assert result.native_command is not None
    assert needle in result.native_command
    assert result.planned == ()
    assert snapshot(tmp_path) == {}


def test_copy_installs_into_harness_dir(tmp_path: Path):
    install(Harness.CODEX, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    assert (tmp_path / ".agents/skills/using-grillspec/SKILL.md").is_file()


def test_user_scope_uses_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    install(
        Harness.GIGACODE, Scope.USER, root=tmp_path / "proj", copy=False, dry_run=False
    )
    assert (home / ".gigacode/skills/using-grillspec/SKILL.md").is_file()
    giga = (home / ".gigacode/GIGACODE.md").read_text()
    assert "@skills/using-grillspec/SKILL.md" in giga
    assert (home / ".config/grillspec/install-receipt.json").is_file()
    assert not (tmp_path / "proj").exists()
    uninstall(Harness.GIGACODE, Scope.USER, root=tmp_path / "proj")
    assert not (home / ".gigacode/skills/using-grillspec").exists()


def test_cli_install_and_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    assert main(["install", "--harness", "claude"]) == 0
    assert "claude plugin marketplace add" in capsys.readouterr().out
    assert main(["install", "--harness", "gigacode", "--dry-run"]) == 0
    assert "would write" in capsys.readouterr().out
    assert main(["install", "--harness", "gigacode"]) == 0
    capsys.readouterr()
    assert main(["uninstall", "--harness", "gigacode"]) == 0
    assert "removed" in capsys.readouterr().out
