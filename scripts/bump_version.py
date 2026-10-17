"""Keep the version identical in pyproject.toml, the package and every manifest."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import cast

VERSION_FILES = (
    "pyproject.toml",
    "src/grillspec/__init__.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".antigravity-plugin/plugin.json",
)
_PYPROJECT = re.compile(r'^(version = ")([^"]+)(")', re.MULTILINE)
_PACKAGE = re.compile(r'^(__version__ = ")([^"]+)(")', re.MULTILINE)
_JSON = re.compile(r'("version":\s*")([^"]+)(")')


def _read_version(path: Path, relative: str) -> str:
    """Read the version a file declares.

    Args:
        path: Path - The file.
        relative: str - Its repository-relative path, which decides the format.

    Returns:
        str - The declared version.

    """
    text = path.read_text(encoding="utf-8")
    if relative == "pyproject.toml":
        project = cast("dict[str, object]", tomllib.loads(text)["project"])
        return str(project["version"])
    if relative.endswith(".py"):
        match = _PACKAGE.search(text)
        return match.group(2) if match else ""
    data = cast("dict[str, object]", json.loads(text))
    if "plugins" in data:
        plugins = cast("list[dict[str, object]]", data["plugins"])
        return str(plugins[0]["version"])
    return str(data["version"])


def versions(root: Path) -> dict[str, str]:
    """Read every declared version.

    Args:
        root: Path - Repository root.

    Returns:
        dict[str, str] - Repository-relative path to version.

    """
    return {rel: _read_version(root / rel, rel) for rel in VERSION_FILES}


def drift(root: Path) -> list[str]:
    """List files whose version differs from pyproject.toml.

    Args:
        root: Path - Repository root.

    Returns:
        list[str] - ``<path>: <version>`` per drifting file.

    """
    found = versions(root)
    expected = found["pyproject.toml"]
    return [f"{rel}: {value}" for rel, value in found.items() if value != expected]


def bump(root: Path, version: str) -> None:
    """Set one version everywhere.

    Args:
        root: Path - Repository root.
        version: str - New version, e.g. ``0.1.0``.

    """
    for relative in VERSION_FILES:
        path = root / relative
        pattern = (
            _PYPROJECT
            if relative == "pyproject.toml"
            else _PACKAGE
            if relative.endswith(".py")
            else _JSON
        )
        text = path.read_text(encoding="utf-8")
        _ = path.write_text(
            pattern.sub(rf"\g<1>{version}\g<3>", text, count=1), encoding="utf-8"
        )


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[1]
    match sys.argv[1:]:
        case ["--check"]:
            problems = drift(repo)
            for problem in problems:
                _ = sys.stdout.write(f"version drift: {problem}\n")
            sys.exit(1 if problems else 0)
        case [version]:
            bump(repo, version)
        case _:
            _ = sys.stderr.write("usage: bump_version.py --check | X.Y.Z\n")
            sys.exit(2)
