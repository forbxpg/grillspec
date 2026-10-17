"""Regression tests for the final-review findings of S1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grillspec.cli import main
from grillspec.config import Backend, ConfigError, load_config
from grillspec.hooks import Harness
from grillspec.install import InstallConflictError, Scope, install, uninstall
from grillspec.state import Phase, derive_phase, list_changes
from support import write

REPO = Path(__file__).resolve().parents[2]
CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'


def test_malformed_sidecar_is_one_line_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    write(tmp_path / ".grillspec/changes/c1.toml", "spec_approved = \n")
    monkeypatch.chdir(tmp_path)
    assert main(["status"]) == 1
    assert main(["use", "c1"]) == 1
    err = capsys.readouterr().err
    assert "c1.toml" in err
    assert "Traceback" not in err


def test_non_utf8_config_is_config_error(tmp_path: Path):
    (tmp_path / ".grillspec").mkdir()
    (tmp_path / ".grillspec/config.toml").write_bytes(b"version = 1\n# \xff\xfe\n")
    with pytest.raises(ConfigError, match=r"config\.toml"):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_corrupt_receipt_is_one_line_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(tmp_path / ".grillspec/install-receipt.json", "{")
    monkeypatch.chdir(tmp_path)
    assert main(["uninstall", "--harness", "gigacode"]) == 1
    err = capsys.readouterr().err
    assert "install-receipt.json" in err
    assert "Traceback" not in err


def test_install_refuses_to_overwrite_user_skill(tmp_path: Path):
    mine = write(tmp_path / ".claude/skills/init/SKILL.md", "my own init skill\n")
    with pytest.raises(InstallConflictError) as info:
        install(Harness.CLAUDE, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    assert mine in info.value.paths
    assert mine.read_text() == "my own init skill\n"
    assert not (tmp_path / ".grillspec/install-receipt.json").exists()


def test_reinstall_same_harness_is_fine(tmp_path: Path):
    install(Harness.CLAUDE, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    install(Harness.CLAUDE, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    assert (tmp_path / ".claude/skills/using-grillspec/SKILL.md").is_file()


def test_shared_skill_dir_conflicts_instead_of_double_owning(tmp_path: Path):
    install(Harness.CODEX, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False)
    with pytest.raises(InstallConflictError):
        install(
            Harness.ANTIGRAVITY, Scope.PROJECT, root=tmp_path, copy=True, dry_run=False
        )


@pytest.mark.parametrize("kind", ["parent", "absolute", "outside-skill-dir"])
def test_uninstall_rejects_paths_outside_the_install(tmp_path: Path, kind: str):
    project = tmp_path / "project"
    outside = write(tmp_path / "victim/keep.txt", "keep\n")
    inside = write(project / "victim/keep.txt", "keep\n")
    bad = {
        "parent": "../victim/keep.txt",
        "absolute": str(outside),
        "outside-skill-dir": "victim/keep.txt",
    }[kind]
    receipt = {
        "version": 1,
        "installs": {"gigacode": {"scope": "project", "files": [bad], "lines": []}},
    }
    write(project / ".grillspec/install-receipt.json", json.dumps(receipt))
    with pytest.raises(ConfigError, match=r"install-receipt\.json"):
        uninstall(Harness.GIGACODE, Scope.PROJECT, root=project)
    assert outside.read_text() == "keep\n"
    assert inside.read_text() == "keep\n"


def test_uninstall_rejects_foreign_context_line(tmp_path: Path):
    other = write(tmp_path / "README.md", "keep\n@x\n")
    receipt = {
        "version": 1,
        "installs": {
            "gigacode": {
                "scope": "project",
                "files": [],
                "lines": [{"file": "README.md", "line": "@x"}],
            }
        },
    }
    write(tmp_path / ".grillspec/install-receipt.json", json.dumps(receipt))
    with pytest.raises(ConfigError):
        uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert other.read_text() == "keep\n@x\n"


def test_router_offers_init_only_for_real_work():
    router = (REPO / "skills/using-grillspec/SKILL.md").read_text()
    assert (
        "No `.grillspec/config.toml` in the project? Use the `init` skill first."
        not in router
    )
    assert "offer the `init` skill once" in router


def test_string_sidecar_dates_are_read(tmp_path: Path):
    write(tmp_path / "docs/grillspec/specs/c1.md", "# spec\n")
    write(
        tmp_path / ".grillspec/changes/c1.toml",
        'version = 1\nspec_approved = "2026-10-17"\n',
    )
    (change,) = list_changes(tmp_path, Backend.SUPERPOWERS)
    assert derive_phase(change) is Phase.PLAN


def test_invalid_string_date_is_config_error(tmp_path: Path):
    write(
        tmp_path / ".grillspec/changes/c1.toml", 'version = 1\nspec_approved = "soon"\n'
    )
    with pytest.raises(ConfigError, match=r"c1\.toml.*spec_approved"):
        list_changes(tmp_path, Backend.SUPERPOWERS)


def test_runner_is_lf_pinned_and_has_no_goto():
    attributes = (REPO / ".gitattributes").read_text()
    assert "hooks/run-hook.cmd text eol=lf" in attributes
    runner = (REPO / "hooks/run-hook.cmd").read_text().lower()
    assert "goto" not in runner
    assert "\r" not in (REPO / "hooks/run-hook.cmd").read_bytes().decode()
