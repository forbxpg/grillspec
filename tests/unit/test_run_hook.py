"""Tests for the polyglot hook runner (spec S1-R4-S2, Review Focus 5)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WINDOWS = sys.platform == "win32"


def plugin_copy(tmp_path: Path) -> Path:
    root = tmp_path / "plugin root"  # a space, like "Program Files"
    for name in ("hooks", "scripts", "skills", "src", "templates"):
        shutil.copytree(REPO / name, root / name)
    return root


def run_runner(root: Path, harness: str, env: dict[str, str]) -> tuple[int, str]:
    runner = root / "hooks" / "run-hook.cmd"
    command = (
        ["cmd.exe", "/c", str(runner), "session-start", harness]
        if WINDOWS
        else ["/bin/sh", str(runner), "session-start", harness]
    )
    done = subprocess.run(
        command, capture_output=True, text=True, env=env, cwd=root, check=False
    )
    return done.returncode, done.stdout


def test_runner_executes_cli(tmp_path: Path):
    root = plugin_copy(tmp_path)
    python_dir = str(Path(sys.executable).parent)
    env = {**os.environ, "PATH": python_dir + os.pathsep + os.environ.get("PATH", "")}
    code, out = run_runner(root, "claude", env)
    assert code == 0
    payload = json.loads(out)
    assert "grillspec: phase=" in payload["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    ("harness", "key"),
    [
        ("claude", "hookSpecificOutput"),
        ("cursor", "additional_context"),
        ("antigravity", "injectSteps"),
    ],
)
def test_runner_without_python_fails_open(tmp_path: Path, harness: str, key: str):
    root = plugin_copy(tmp_path)
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    env = {"PATH": str(empty), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    code, out = run_runner(root, harness, env)
    assert code == 0
    payload = json.loads(out)
    assert key in payload
    assert "gates are OFF" in out
