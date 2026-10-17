"""Tests for the CLI entry point and the plugin shim."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import grillspec
from grillspec.cli import main

if TYPE_CHECKING:
    import pytest

REPO = Path(__file__).resolve().parents[2]


def test_version_command_prints_package_version(capsys: pytest.CaptureFixture[str]):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == grillspec.__version__


def test_module_entry_runs():
    out = subprocess.run(
        [sys.executable, "-m", "grillspec", "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == grillspec.__version__


def test_shim_runs_without_install(tmp_path: Path):
    shutil.copytree(REPO / "scripts", tmp_path / "scripts")
    shutil.copytree(REPO / "src", tmp_path / "src")
    out = subprocess.run(
        [sys.executable, "-I", str(tmp_path / "scripts" / "grillspec.py"), "version"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert out.stdout.strip() == grillspec.__version__
