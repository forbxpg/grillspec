"""Check that docs/en and docs/ru have the same files and heading structure."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grillspec.markdown import lines_outside_fences

MAX_LEVEL = 6


def _levels(path: Path) -> list[int]:
    """List heading levels of a Markdown file, ignoring fenced code blocks.

    Args:
        path: Path - Markdown file.

    Returns:
        list[int] - Level of each ATX heading, in order.

    """
    levels: list[int] = []
    for line in lines_outside_fences(path.read_text(encoding="utf-8")):
        marks = len(line) - len(line.lstrip("#"))
        if 1 <= marks <= MAX_LEVEL and line[marks : marks + 1] in {" ", ""}:
            levels.append(marks)
    return levels


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
        en_levels, ru_levels = _levels(en / name), _levels(ru / name)
        if en_levels != ru_levels:
            problems.append(
                f"{name}: heading levels differ: en {en_levels}, ru {ru_levels}"
            )
    return problems


if __name__ == "__main__":
    docs = Path(__file__).resolve().parents[1] / "docs"
    found = compare(docs / "en", docs / "ru")
    for problem in found:
        _ = sys.stdout.write(problem + "\n")
    sys.exit(1 if found else 0)
