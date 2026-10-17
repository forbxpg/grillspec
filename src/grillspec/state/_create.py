"""Create a change: its id, approval sidecar and decision-log skeleton."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from grillspec.config import Backend, CouncilMode, Depth
from grillspec.paths import write_atomic

from ._changes import SIDECARS, archived_ids, list_changes, log_path
from ._phase import Phase, compute_status
from ._sidecar import ChangeError, write_sidecar
from ._store import set_active

if TYPE_CHECKING:
    import datetime as dt
    from pathlib import Path

    from grillspec.config import Config

    from ._changes import Change

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BUDGET = {Depth.QUICK: "5", Depth.STANDARD: "15", Depth.DEEP: "none"}
_BUSY = frozenset({Phase.GRILL, Phase.SPEC, Phase.PLAN, Phase.EXECUTE})


def _skeleton(change_id: str, backend: Backend, depth: Depth, *, council: bool) -> str:
    """Render the empty decision log a new change starts with.

    Args:
        change_id: str - Change id.
        backend: Backend - Spec backend (decides the title).
        depth: Depth - Grilling depth, which sets the question budget.
        council: bool - Whether the grill consults a council.

    Returns:
        str - Markdown text.

    """
    title = (
        f"# {change_id}" if backend is Backend.SUPERPOWERS else f"# Design: {change_id}"
    )
    calls = " council_calls=0" if council else ""
    meta = (
        f"<!-- grillspec: depth={depth} council={'yes' if council else 'no'}"
        f" budget={_BUDGET[depth]} asked=0{calls} -->"
    )
    return f"{title}\n\n## Decision log\n\n{meta}\n\n### Open\n\n### Settled\n"


def create_change(  # ruff: ignore[too-many-arguments] - every argument is a user-facing CLI option
    root: Path,
    config: Config,
    slug: str,
    *,
    today: dt.date,
    switch: bool = False,
    depth: Depth | None = None,
    council: bool = False,
) -> Change:
    """Create a change with its sidecar and decision log, and make it active.

    Args:
        root: Path - Project root.
        config: Config - Effective configuration (backend, default depth).
        slug: str - Lowercase kebab-case name.
        today: dt.date - Creation date (superpowers ids start with it).
        switch: bool - Allow leaving an unfinished active change.
        depth: Depth | None - Grilling depth; the configured default when None.
        council: bool - Whether the grill consults a council; also on when the
            config says ``council.enabled = "yes"``.

    Returns:
        Change - The new, active change.

    Raises:
        ChangeError: If grillspec is not set up, the slug is invalid, the id exists
            or was archived, or an unfinished change is active without ``switch``.

    """
    backend = config.backend
    if backend is None:
        msg = "grillspec is not set up here; run grillspec init first"
        raise ChangeError(msg)
    if not _SLUG.fullmatch(slug):
        msg = f"slug {slug!r} must be lowercase kebab-case: a-z, 0-9 and single hyphens"
        raise ChangeError(msg)
    change_id = f"{today:%Y-%m-%d}-{slug}" if backend is Backend.SUPERPOWERS else slug
    if change_id in {change.id for change in list_changes(root, backend)}:
        msg = f"change {change_id!r} already exists; run grillspec use {change_id}"
        raise ChangeError(msg)
    if change_id in archived_ids(root, backend):
        msg = f"change {change_id!r} was archived; pick another slug"
        raise ChangeError(msg)
    status = compute_status(root, config)
    if status.change_id and status.phase in _BUSY and not switch:
        msg = (
            f"active change {status.change_id!r} is in phase {status.phase}; finish it,"
            " or pass --switch to start another"
        )
        raise ChangeError(msg)
    depth = depth or config.depth
    council = council or config.council_enabled is CouncilMode.YES
    log = log_path(root, backend, change_id)
    write_sidecar(root / SIDECARS / f"{change_id}.toml", {"version": 1})
    write_atomic(log, _skeleton(change_id, backend, depth, council=council))
    if backend is Backend.OPENSPEC:
        write_atomic(
            log.parent / ".openspec.yaml",
            f"schema: spec-driven\ncreated: {today:%Y-%m-%d}\n",
        )
    set_active(root, change_id, backend)
    return next(c for c in list_changes(root, backend) if c.id == change_id)
