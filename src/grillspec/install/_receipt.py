"""The record of what an install wrote, so uninstall removes exactly that."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

Entry = dict[str, object]


def read_receipt(path: Path) -> dict[str, Entry]:
    """Read the installs recorded in a receipt.

    Args:
        path: Path - Receipt file; missing means nothing installed.

    Returns:
        dict[str, Entry] - Harness name to its install entry.

    """
    if not path.is_file():
        return {}
    data = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    return cast("dict[str, Entry]", data.get("installs", {}))


def write_receipt(path: Path, installs: dict[str, Entry]) -> None:
    """Write a receipt, removing the file when nothing is installed.

    Args:
        path: Path - Receipt file.
        installs: dict[str, Entry] - Harness name to its install entry.

    """
    if not installs:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "installs": installs}
    _ = path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
