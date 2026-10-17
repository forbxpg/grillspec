"""CLI tests for ``status`` and ``use`` (spec S1-R3)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

from grillspec.cli import main
from support import write

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

CID = "2026-10-17-login"
CONFIG = 'version = 1\n[spec]\nbackend = "superpowers"\n'


def project(root: Path, *ids: str) -> None:
    write(root / ".grillspec/config.toml", CONFIG)
    for change_id in ids:
        write(root / f"docs/grillspec/specs/{change_id}.md", "# spec\n")


def test_status_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    project(tmp_path, CID)
    monkeypatch.chdir(tmp_path)
    assert main(["use", CID]) == 0
    capsys.readouterr()
    assert main(["status", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {
        "version": 1,
        "phase": "spec",
        "change": CID,
        "next": "write and approve the spec",
        "warnings": [],
    }


def test_use_unknown_exits_1_listing_known(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    project(tmp_path, CID)
    monkeypatch.chdir(tmp_path)
    assert main(["use", "nope"]) == 1
    assert CID in capsys.readouterr().err


def test_worktrees_have_independent_active(tmp_path: Path):  # S1-R3-S3
    main_tree = tmp_path / "main"
    project(main_tree, "a", "b")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", str(main_tree)], check=True)
    subprocess.run([*git, "-C", str(main_tree), "add", "-A"], check=True)
    subprocess.run([*git, "-C", str(main_tree), "commit", "-qm", "x"], check=True)
    other = tmp_path / "other"
    subprocess.run(
        [*git, "-C", str(main_tree), "worktree", "add", "-q", str(other)], check=True
    )
    cli = [sys.executable, "-m", "grillspec"]
    subprocess.run([*cli, "use", "a"], cwd=main_tree, check=True)
    subprocess.run([*cli, "use", "b"], cwd=other, check=True)

    def active(tree: Path) -> str:
        out = subprocess.run(
            [*cli, "status", "--json"], cwd=tree, check=True, capture_output=True
        ).stdout
        return json.loads(out)["change"]

    try:
        assert active(main_tree) == "a"
        assert active(other) == "b"
    finally:
        # Remove the worktree so pytest's tmp cleanup never trips over its .git
        # file (a leaked scandir iterator becomes an error under -W error).
        subprocess.run(
            [*git, "-C", str(main_tree), "worktree", "remove", "--force", str(other)],
            check=False,
        )
