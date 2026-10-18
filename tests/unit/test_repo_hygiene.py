"""The repository never tracks private working material."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs the git checkout",
)
def test_private_is_never_tracked():
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "private"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked == [], f"private/ must stay out of git: {tracked}"
