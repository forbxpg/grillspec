"""The wheel bundles skills, hooks and templates byte-for-byte."""

from __future__ import annotations

import subprocess
import tarfile
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


def test_sdist_carries_plugin_files(tmp_path: Path):
    subprocess.run(
        ["uv", "build", "--sdist", "-q", "-o", str(tmp_path)], cwd=REPO, check=True
    )
    (sdist,) = tmp_path.glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        names = {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}
    expected = {
        "skills/using-grillspec/SKILL.md",
        "hooks/run-hook.cmd",
        "hooks/hooks.json",
        "hooks.json",
        "templates/config.toml",
        "scripts/grillspec",
        "scripts/grillspec.cmd",
        "scripts/grillspec.py",
        ".claude-plugin/plugin.json",
    }
    assert expected <= names, sorted(expected - names)


LOCAL_ONLY = (".superpowers", "private", "tests/evals/results", ".grillspec")


def test_sdist_leaves_local_scratch_out(tmp_path: Path):
    probes = [REPO / folder / "zz-sdist-probe.md" for folder in LOCAL_ONLY]
    made = [probe for probe in probes if not probe.exists()]
    try:
        for probe in made:
            probe.parent.mkdir(parents=True, exist_ok=True)
            _ = probe.write_text("local only\n", encoding="utf-8")
        subprocess.run(
            ["uv", "build", "--sdist", "-q", "-o", str(tmp_path)], cwd=REPO, check=True
        )
    finally:
        for probe in made:
            probe.unlink(missing_ok=True)
    (sdist,) = tmp_path.glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        names = [name.split("/", 1)[1] for name in archive.getnames() if "/" in name]
    leaked = [
        n for n in names if any(n == f or n.startswith(f + "/") for f in LOCAL_ONLY)
    ]
    assert leaked == []
