"""The wheel bundles skills, hooks and templates byte-for-byte."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUNDLED = ("skills", "hooks", "templates")


def test_wheel_bundles_identical_data(tmp_path: Path):
    subprocess.run(
        ["uv", "build", "--wheel", "-q", "-o", str(tmp_path)], cwd=REPO, check=True
    )
    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        for name in BUNDLED:
            for source in (REPO / name).rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(REPO).as_posix()
                member = f"grillspec/_bundled/{relative}"
                assert member in names, member
                assert archive.read(member) == source.read_bytes(), member
