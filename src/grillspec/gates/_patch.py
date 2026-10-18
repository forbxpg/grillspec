"""Read the files a Codex ``apply_patch`` patch touches."""

from __future__ import annotations

import re

_FILE = re.compile(
    r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$", re.MULTILINE
)


def patch_paths(patch: str) -> list[str]:
    """Return every path a patch adds, updates, deletes or moves to.

    Args:
        patch: str - The patch text (``*** Begin Patch`` … ``*** End Patch``).

    Returns:
        list[str] - Paths in patch order, as written in the patch.

    """
    return [match.group(1) for match in _FILE.finditer(patch)]
