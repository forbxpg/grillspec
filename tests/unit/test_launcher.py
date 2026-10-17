"""Tests for the Python-discovering launchers (scripts/grillspec, scripts/grillspec.cmd)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import grillspec

REPO = Path(__file__).resolve().parents[2]
POSIX = pytest.mark.skipif(sys.platform == "win32", reason="POSIX launcher")
WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe launcher")
TOO_OLD = "#!/bin/sh\n# pretends to be Python 3.10: fails the version probe\nexit 1\n"


def fake_bin(tmp_path: Path, **programs: str) -> Path:
    # A PATH directory holding the given programs (name -> script body, or "real").
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    for name, body in programs.items():
        target = directory / name
        if body == "real":
            target.symlink_to(sys.executable)
            continue
        target.write_text(body, encoding="utf-8")
        target.chmod(0o755)
    return directory


def run_posix(path: Path, *args: str, extra: dict[str, str] | None = None):
    env = {"PATH": str(path), **(extra or {})}
    return subprocess.run(
        ["/bin/sh", str(REPO / "scripts" / "grillspec"), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@POSIX
def test_skips_too_old_python3_and_uses_versioned_name(tmp_path: Path):
    path = fake_bin(tmp_path, python3=TOO_OLD, **{"python3.14": "real"})
    done = run_posix(path, "version")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == grillspec.__version__


@POSIX
def test_plain_python_is_a_candidate(tmp_path: Path):
    path = fake_bin(tmp_path, python3=TOO_OLD, python="real")
    assert run_posix(path, "version").stdout.strip() == grillspec.__version__


@POSIX
def test_env_override_wins(tmp_path: Path):
    path = fake_bin(tmp_path, python3="real")
    marker = tmp_path / "used"
    wrapper = f'#!/bin/sh\n: > "{marker}"\nexec "{sys.executable}" "$@"\n'
    custom = tmp_path / "custom-python"
    custom.write_text(wrapper, encoding="utf-8")
    custom.chmod(0o755)
    done = run_posix(path, "version", extra={"GRILLSPEC_PYTHON": str(custom)})
    assert done.returncode == 0
    assert marker.exists()


@POSIX
def test_py_launcher_under_git_bash(tmp_path: Path):
    # Git Bash on Windows has `py` but often no python3: py -3.X must be tried.
    py = f'#!/bin/sh\ncase "$1" in -3.1[1-5]) shift; exec "{sys.executable}" "$@";; esac\nexit 1\n'
    path = fake_bin(tmp_path, py=py)
    assert run_posix(path, "version").stdout.strip() == grillspec.__version__


@POSIX
def test_uv_fallback_when_no_python(tmp_path: Path):
    log = tmp_path / "uv-args"
    uv = (
        f'#!/bin/sh\necho "$@" > "{log}"\n'
        'while [ "$1" != python ]; do shift; done\nshift\n'
        f'exec "{sys.executable}" "$@"\n'
    )
    path = fake_bin(tmp_path, uv=uv)
    done = run_posix(path, "version")
    assert done.stdout.strip() == grillspec.__version__
    assert "--python >=3.11" in log.read_text()


@POSIX
def test_no_python_no_uv_exits_127(tmp_path: Path):
    done = run_posix(fake_bin(tmp_path, python3=TOO_OLD), "version")
    assert done.returncode == 127
    assert "Python 3.11" in done.stderr


@WINDOWS
def test_cmd_launcher_runs_cli():
    done = subprocess.run(
        ["cmd.exe", "/c", str(REPO / "scripts" / "grillspec.cmd"), "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.stdout.strip() == grillspec.__version__, done.stderr


@WINDOWS
def test_cmd_launcher_without_python_exits_127(tmp_path: Path):
    env = {"PATH": str(tmp_path), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    done = subprocess.run(
        ["cmd.exe", "/c", str(REPO / "scripts" / "grillspec.cmd"), "version"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.returncode == 127


def test_both_launchers_exist_and_are_lf():
    for name in ("grillspec", "grillspec.cmd"):
        data = (REPO / "scripts" / name).read_bytes()
        assert b"\r" not in data, name
