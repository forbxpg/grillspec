"""The per-working-tree pointer to the active change."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, cast

from grillspec.config import ConfigError

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


def _active_from(data: object, path: Path) -> tuple[str | None, tuple[str, ...]]:
    """Validate parsed ``state.json`` content and pick the active change.

    Args:
        data: object - Parsed JSON.
        path: Path - The state file, for warnings.

    Returns:
        tuple[str | None, tuple[str, ...]] - The id (None when none is active)
            and warnings; ``"active": null`` is a normal, quiet "none".

    """
    state = cast("dict[str, object]", data) if isinstance(data, dict) else None
    if state is None:
        problem = "not a JSON object"
    elif type(state.get("version")) is not int or state.get("version") != 1:
        problem = f"unsupported version {state.get('version')!r}"
    elif "active" in state and state["active"] is None:
        return None, ()
    elif isinstance(state.get("active"), str):
        return cast("str", state["active"]), ()
    else:
        problem = "no active change recorded"
    return None, (f"{path}: {problem}; treating as no active change",)


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
    return _active_from(data, path)


def set_active(root: Path, change_id: str, backend: Backend) -> None:
    """Make a change the active one in this working tree.

    Args:
        root: Path - Project root.
        change_id: str - Id of an existing change.
        backend: Backend - Spec backend, used to find known changes.

    Raises:
        UnknownChangeError: If no change has this id.
        ConfigError: If ``.grillspec`` is a symlink.

    """
    known = tuple(change.id for change in list_changes(root, backend))
    if change_id not in known:
        raise UnknownChangeError(change_id, known)
    path = root / STATE
    if path.parent.is_symlink():
        msg = (
            f"{path.parent} is a symlink; refusing to write grillspec state through it"
        )
        raise ConfigError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a sibling file and swap it in: an interrupted write never leaves a
    # truncated state.json, and a symlink at state.json is replaced, not followed.
    payload = json.dumps({"version": 1, "active": change_id}) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=".state-", delete=False
    ) as handle:
        _ = handle.write(payload)
    _ = Path(handle.name).replace(path)
