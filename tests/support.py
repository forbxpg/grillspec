"""Helpers shared by the tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write(path: Path, text: str) -> Path:
    """Write UTF-8 text, creating parent directories.

    Returns:
        Path - The written path.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")
    return path
