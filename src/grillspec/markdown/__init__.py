"""Small Markdown helpers shared by the CLI and the repository scripts."""

from __future__ import annotations

from ._fences import (
    lines_outside_fences,
    numbered_lines_outside_fences,
    numbered_outside,
)

__all__ = (
    "lines_outside_fences",
    "numbered_lines_outside_fences",
    "numbered_outside",
)
