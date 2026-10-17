"""Check that docs/en and docs/ru have the same files and heading counts."""

from __future__ import annotations

import sys
from pathlib import Path


def _headings(path: Path) -> int:
    """Count Markdown headings outside fenced code blocks.

    Args:
        path: Path - Markdown file.

    Returns:
        int - Number of ``#`` heading lines.

    """
    count = 0
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            count += 1
    return count


def _files(root: Path) -> set[str]:
    """List Markdown files under a directory.

    Args:
        root: Path - Docs language root.

    Returns:
        set[str] - POSIX paths relative to the root.

    """
    return {path.relative_to(root).as_posix() for path in root.rglob("*.md")}


def compare(en: Path, ru: Path) -> list[str]:
    """Compare the English and Russian docs trees.

    Args:
        en: Path - English docs root.
        ru: Path - Russian docs root.

    Returns:
        list[str] - One message per mismatch; empty when they mirror.

    """
    en_files, ru_files = _files(en), _files(ru)
    problems = [f"missing in ru: {name}" for name in sorted(en_files - ru_files)]
    problems += [f"missing in en: {name}" for name in sorted(ru_files - en_files)]
    for name in sorted(en_files & ru_files):
        en_count, ru_count = _headings(en / name), _headings(ru / name)
        if en_count != ru_count:
            problems.append(f"{name}: {en_count} headings in en, {ru_count} in ru")
    return problems


if __name__ == "__main__":
    docs = Path(__file__).resolve().parents[1] / "docs"
    found = compare(docs / "en", docs / "ru")
    for problem in found:
        _ = sys.stdout.write(problem + "\n")
    sys.exit(1 if found else 0)
