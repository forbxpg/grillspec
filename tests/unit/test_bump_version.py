"""Tests for version sync across pyproject and manifests (spec S1-R9-S1)."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "bump_version", REPO / "scripts" / "bump_version.py"
)
assert _spec is not None
assert _spec.loader is not None
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


def repo_copy(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in bump_version.VERSION_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / relative, target)
    return root


def test_repo_is_in_sync():
    assert bump_version.drift(REPO) == []


def test_check_reports_drift(tmp_path: Path):
    root = repo_copy(tmp_path)
    manifest = root / ".cursor-plugin/plugin.json"
    text = manifest.read_text()
    manifest.write_text(text.replace('"version": "0.0.1"', '"version": "0.0.2"'))
    assert bump_version.drift(root) == [".cursor-plugin/plugin.json: 0.0.2"]


def test_bump_aligns_all(tmp_path: Path):
    root = repo_copy(tmp_path)
    bump_version.bump(root, "1.2.3")
    versions = bump_version.versions(root)
    assert set(versions.values()) == {"1.2.3"}
    assert set(versions) == set(bump_version.VERSION_FILES)
