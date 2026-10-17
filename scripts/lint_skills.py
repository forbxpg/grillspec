"""Lint every SKILL.md: portable frontmatter and the router's size budget."""

from __future__ import annotations

import sys
from pathlib import Path

ALLOWED_KEYS = ("description", "name")
MAX_DESCRIPTION = 1024
ROUTER = "using-grillspec"
MAX_ROUTER_LINES = 150


def _unquote(value: str) -> str:
    """Strip one pair of matching quotes around a scalar.

    Args:
        value: str - Raw scalar.

    Returns:
        str - The value without surrounding quotes.

    """
    if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _split(text: str) -> tuple[dict[str, str], list[str], list[str]] | None:
    """Split a SKILL.md into frontmatter keys, body lines and frontmatter problems.

    Frontmatter must be flat ``key: value`` lines: block scalars (``>``, ``|``) and
    continuation lines are reported, because the portable Agent Skills tools read
    descriptions as single lines.

    Args:
        text: str - File content.

    Returns:
        tuple[dict[str, str], list[str], list[str]] | None - Frontmatter, body lines
            and problems, or None when the file has no frontmatter block.

    """
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    end = lines.index("---", 1)
    front: dict[str, str] = {}
    problems: list[str] = []
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if line[0].isspace() or not separator:
            problems.append(f"frontmatter line {line.strip()!r} is not `key: value`")
            continue
        value = value.strip()
        if value[:1] in {">", "|"}:
            problems.append(f"{key.strip()} must be a single line, not a block scalar")
            value = ""
        front[key.strip()] = _unquote(value).strip()
    return front, lines[end + 1 :], problems


def lint(skills_dir: Path) -> list[str]:
    """Check every skill under a directory.

    Args:
        skills_dir: Path - Directory holding one folder per skill.

    Returns:
        list[str] - One message per violation; empty when all skills pass.

    """
    errors = [
        f"{folder}: directory without SKILL.md"
        for folder in sorted(skills_dir.iterdir())
        if folder.is_dir() and not (folder / "SKILL.md").is_file()
    ]
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        folder = path.parent.name
        parts = _split(path.read_text(encoding="utf-8"))
        if parts is None:
            errors.append(f"{path}: no frontmatter block")
            continue
        front, body, problems = parts
        errors.extend(f"{path}: {problem}" for problem in problems)
        extra = sorted(set(front) - set(ALLOWED_KEYS))
        if extra:
            errors.append(f"{path}: keys beyond name/description: {', '.join(extra)}")
        errors.extend(
            f"{path}: missing {key}" for key in ALLOWED_KEYS if not front.get(key)
        )
        if front.get("name") and front["name"] != folder:
            errors.append(f"{path}: name {front['name']!r} != directory {folder!r}")
        if len(front.get("description", "")) > MAX_DESCRIPTION:
            errors.append(f"{path}: description over {MAX_DESCRIPTION} characters")
        if folder == ROUTER and len(body) > MAX_ROUTER_LINES:
            errors.append(f"{path}: router body over {MAX_ROUTER_LINES} lines")
    return errors


if __name__ == "__main__":
    root = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / "skills"
    )
    problems = lint(root)
    for problem in problems:
        _ = sys.stdout.write(problem + "\n")
    sys.exit(1 if problems else 0)
