"""Tests for the docs mirror check (spec S1-R10-S1)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from support import write

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_docs_mirror", REPO / "scripts" / "check_docs_mirror.py"
)
assert _spec is not None
assert _spec.loader is not None
check_docs_mirror = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_docs_mirror)
compare = check_docs_mirror.compare


def test_mirror_passes(tmp_path: Path):
    write(tmp_path / "en/a.md", "# A\n## B\n")
    write(tmp_path / "ru/a.md", "# Раздел\n## Подраздел\n")
    assert compare(tmp_path / "en", tmp_path / "ru") == []


def test_mirror_reports_missing_and_heading_mismatch(tmp_path: Path):
    write(tmp_path / "en/a.md", "# A\n## B\n")
    write(tmp_path / "en/only-en.md", "# X\n")
    write(tmp_path / "ru/a.md", "# Раздел\n")
    write(tmp_path / "ru/sub/only-ru.md", "# Y\n")
    problems = compare(tmp_path / "en", tmp_path / "ru")
    assert "missing in ru: only-en.md" in problems
    assert "missing in en: sub/only-ru.md" in problems
    assert "a.md: 2 headings in en, 1 in ru" in problems


def test_code_fences_are_not_headings(tmp_path: Path):
    write(tmp_path / "en/a.md", "# A\n```bash\n# comment\n```\n")
    write(tmp_path / "ru/a.md", "# Раздел\n")
    assert compare(tmp_path / "en", tmp_path / "ru") == []
