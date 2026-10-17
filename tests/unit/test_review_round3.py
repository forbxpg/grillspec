"""Regressions from the stacked-PR reviews (Sourcery, CodeRabbit)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from grillspec.cli import main
from grillspec.config import Backend, ConfigError, load_config
from grillspec.detect import brownfield_signals
from grillspec.hooks import Harness, session_context
from grillspec.install import Scope, install, uninstall
from grillspec.markdown import lines_outside_fences
from grillspec.paths import template
from grillspec.state import Phase, Status, active_change_id, list_changes, set_active
from support import write

REPO = Path(__file__).resolve().parents[2]
CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'
POSIX = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions/symlinks")


# --- installer -------------------------------------------------------------
def test_uninstall_keeps_an_import_line_the_user_already_had(tmp_path: Path):
    line = "@.gigacode/skills/using-grillspec/SKILL.md"
    write(tmp_path / "GIGACODE.md", f"# Mine\n{line}\n")
    install(Harness.GIGACODE, Scope.PROJECT, root=tmp_path, copy=False, dry_run=False)
    uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert (tmp_path / "GIGACODE.md").read_text() == f"# Mine\n{line}\n"


def test_receipt_with_a_foreign_line_is_refused(tmp_path: Path):
    write(tmp_path / "GIGACODE.md", "Always answer in French.\n")
    receipt = {
        "version": 1,
        "installs": {
            "gigacode": {
                "scope": "project",
                "files": [],
                "lines": [{"file": "GIGACODE.md", "line": "Always answer in French."}],
            }
        },
    }
    write(tmp_path / ".grillspec/install-receipt.json", json.dumps(receipt))
    with pytest.raises(ConfigError):
        uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)
    assert (tmp_path / "GIGACODE.md").read_text() == "Always answer in French.\n"


# --- detection, hooks, markdown ---------------------------------------------
@pytest.mark.parametrize("name", ["index.html", "site.css", "App.vue", "main.dart"])
def test_web_and_other_sources_count(tmp_path: Path, name: str):
    write(tmp_path / name, "x\n")
    assert brownfield_signals(tmp_path).has_source


def test_router_with_invalid_utf8_still_gives_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    data = tmp_path / "data"
    shutil.copytree(REPO / "skills", data / "skills")
    (data / "skills/using-grillspec/SKILL.md").write_bytes(
        b"---\nname: x\n---\n\xff\xfe"
    )
    monkeypatch.setattr("grillspec.hooks._session_start.data_root", lambda: data)
    text = session_context(tmp_path)
    assert "router unreadable" in text
    assert "grillspec: phase=" in text


def test_indented_fence_lines_do_not_close_a_block():
    text = "```\n    ```\n- [ ] inside\n```\n- [x] outside\n"
    assert list(lines_outside_fences(text)) == ["- [x] outside"]


# --- versions must be integers ------------------------------------------------
@pytest.mark.parametrize("value", ["true", "1.0"])
def test_config_version_must_be_integer_one(tmp_path: Path, value: str):
    write(tmp_path / ".grillspec/config.toml", f"version = {value}\n")
    with pytest.raises(ConfigError, match="version"):
        load_config(tmp_path, user_path=tmp_path / "none.toml")


def test_sidecar_version_true_is_rejected(tmp_path: Path):
    write(tmp_path / ".grillspec/changes/c1.toml", "version = true\n")
    with pytest.raises(ConfigError, match="version"):
        list_changes(tmp_path, Backend.SUPERPOWERS)


def test_state_version_true_is_ignored(tmp_path: Path):
    write(tmp_path / ".grillspec/state.json", '{"version": true, "active": "c1"}')
    assert active_change_id(tmp_path)[0] is None


def test_receipt_version_true_is_rejected(tmp_path: Path):
    write(
        tmp_path / ".grillspec/install-receipt.json",
        '{"version": true, "installs": {}}',
    )
    with pytest.raises(ConfigError):
        uninstall(Harness.GIGACODE, Scope.PROJECT, root=tmp_path)


# --- templates, state writes, config reads -----------------------------------
@pytest.mark.parametrize(
    "name", ["../pyproject.toml", "/etc/hosts", "sub/../config.toml"]
)
def test_template_names_cannot_escape(name: str):
    with pytest.raises(ValueError, match="template"):
        template(name)


@POSIX
def test_state_symlink_is_replaced_not_followed(tmp_path: Path):
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    write(tmp_path / "docs/grillspec/specs/c1.md", "# spec\n")
    victim = write(tmp_path / "victim.txt", "keep\n")
    (tmp_path / ".grillspec/state.json").symlink_to(victim)
    set_active(tmp_path, "c1", Backend.SUPERPOWERS)
    assert victim.read_text() == "keep\n"
    assert not (tmp_path / ".grillspec/state.json").is_symlink()
    assert active_change_id(tmp_path) == ("c1", ())


@POSIX
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads anything"
)
def test_unreadable_config_is_config_error(tmp_path: Path):
    config = write(tmp_path / ".grillspec/config.toml", CONFIG)
    config.chmod(0)
    try:
        with pytest.raises(ConfigError, match=r"config\.toml"):
            load_config(tmp_path, user_path=tmp_path / "none.toml")
    finally:
        config.chmod(0o644)


def test_status_line_escapes_control_characters():
    status = Status(
        Phase.SPEC, "evil\x1b[2Jid", "write the spec, grillspec validate, then approve"
    )
    assert "\x1b" not in status.line()
    assert "evil\\x1b[2Jid" in status.line()


def test_status_finds_the_project_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write(tmp_path / ".grillspec/config.toml", CONFIG)
    write(tmp_path / "docs/grillspec/specs/c1.md", "# spec\n")
    sub = tmp_path / "src" / "pkg"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert main(["use", "c1"]) == 0
    assert main(["status", "--json"]) == 0
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)["change"] == "c1"
    assert (tmp_path / ".grillspec/state.json").is_file()


def test_archived_change_with_leftover_sidecar_is_not_listed(tmp_path: Path):
    write(tmp_path / "openspec/changes/archive/2026-10-17-old/proposal.md", "x\n")
    write(
        tmp_path / ".grillspec/changes/old.toml",
        "version = 1\nspec_approved = 2026-10-17\n",
    )
    assert list_changes(tmp_path, Backend.OPENSPEC) == ()


# --- test-quality findings ---------------------------------------------------
def test_shim_runs_from_the_copied_tree_without_site_packages(tmp_path: Path):
    shutil.copytree(REPO / "scripts", tmp_path / "scripts")
    shutil.copytree(REPO / "src", tmp_path / "src")
    probe = (
        "import runpy, sys; sys.argv = ['grillspec', 'version'];"
        f" runpy.run_path({str(tmp_path / 'scripts' / 'grillspec.py')!r})"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert done.returncode == 0, done.stderr


def test_template_returns_the_whole_file():
    expected = (REPO / "templates" / "config.toml").read_text(encoding="utf-8")
    assert template("config.toml") == expected
