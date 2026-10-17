"""The per-working-tree pointer to the active change."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ._changes import list_changes

if TYPE_CHECKING:
    from grillspec.config import Backend

STATE = Path(".grillspec") / "state.json"


class UnknownChangeError(Exception):
    """The requested change does not exist.

    Attributes:
        change_id: str - The requested id.
        known: tuple[str, ...] - Ids that do exist.

    """

    def __init__(self, change_id: str, known: tuple[str, ...]) -> None:
        super().__init__(f"unknown change {change_id!r}; known: {', '.join(known)}")
        self.change_id: str = change_id
        self.known: tuple[str, ...] = known


def active_change_id(root: Path) -> tuple[str | None, tuple[str, ...]]:
    """Read the active change id of this working tree.

    Args:
        root: Path - Project root.

    Returns:
        tuple[str | None, tuple[str, ...]] - The id (None when none is active)
            and warnings about an unreadable state file.

    """
    path = root / STATE
    if not path.is_file():
        return None, ()
    try:
        data = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        return None, (f"{path}: unreadable ({error}); treating as no active change",)
    active = (
        cast("dict[str, object]", data).get("active")
        if isinstance(data, dict)
        else None
    )
    if not isinstance(active, str):
        return None, (f"{path}: no active change recorded; treating as none",)
    return active, ()


def set_active(root: Path, change_id: str, backend: Backend) -> None:
    """Make a change the active one in this working tree.

    Args:
        root: Path - Project root.
        change_id: str - Id of an existing change.
        backend: Backend - Spec backend, used to find known changes.

    Raises:
        UnknownChangeError: If no change has this id.

    """
    known = tuple(change.id for change in list_changes(root, backend))
    if change_id not in known:
        raise UnknownChangeError(change_id, known)
    path = root / STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(
        json.dumps({"version": 1, "active": change_id}) + "\n", encoding="utf-8"
    )
