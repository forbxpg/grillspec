"""Approval sidecars: write them atomically and record approvals."""

from __future__ import annotations

import datetime as dt
import json
import re
import tomllib
from enum import StrEnum
from typing import TYPE_CHECKING

from grillspec.config import ConfigError
from grillspec.paths import write_atomic

from ._changes import SIDECARS, read_sidecar
from ._hash import artifact_hash, plan_hash
from ._store import active_change_id

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from grillspec.config import Backend


class ChangeError(Exception):
    """A change cannot be created, switched to or approved as asked."""


class Stage(StrEnum):
    """What the user approves."""

    GRILL = "grill"
    SPEC = "spec"
    PLAN = "plan"


_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_KEYS = {
    Stage.GRILL: "grilled",
    Stage.SPEC: "spec_approved",
    Stage.PLAN: "plan_approved",
}


def _toml_key(key: str) -> str:
    """Render a key bare when TOML allows it, quoted otherwise.

    Args:
        key: str - Sidecar key.

    Returns:
        str - The TOML key.

    """
    return key if _BARE_KEY.fullmatch(key) else json.dumps(key, ensure_ascii=False)


def _toml_value(key: str, value: object) -> str:
    """Render one sidecar value as TOML.

    Args:
        key: str - Key, for the error message.
        value: object - Value to render.

    Returns:
        str - The TOML literal.

    Raises:
        ConfigError: For a type sidecars do not hold.

    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # JSON escapes are TOML escapes, except that TOML also forbids a raw DEL.
        return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
    if isinstance(value, dt.date):  # dt.datetime included
        return value.isoformat()
    msg = f"sidecar key {key!r} has unsupported type {type(value).__name__}"
    raise ConfigError(msg)


def write_sidecar(path: Path, data: Mapping[str, object]) -> None:
    """Write an approval sidecar atomically, ``version = 1`` first.

    Args:
        path: Path - Sidecar file.
        data: Mapping[str, object] - Keys and values; ``version`` is forced to 1.

    Raises:
        ConfigError: If the rendered text would not parse back as TOML.

    """
    lines = ["version = 1"]
    lines += [
        f"{_toml_key(key)} = {_toml_value(key, value)}"
        for key, value in sorted(data.items())
        if key != "version"
    ]
    text = "\n".join(lines) + "\n"
    try:
        _ = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:  # a bug here must never corrupt a file
        msg = f"{path}: refusing to write an unreadable sidecar: {error}"
        raise ConfigError(msg) from error
    write_atomic(path, text)


def approve(
    root: Path,
    backend: Backend,
    stage: Stage,
    *,
    today: dt.date,
    executor: str | None = None,
) -> Path:
    """Record that the user approved a stage of the active change.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend (decides which files the spec hash covers).
        stage: Stage - What was approved.
        today: dt.date - Approval date.
        executor: str | None - For the plan: ``subagent`` or ``inline``.

    Returns:
        Path - The sidecar written.

    Raises:
        ChangeError: If no change is active.

    """
    change_id, _ = active_change_id(root)
    if change_id is None:
        msg = "no active change; run grillspec new or grillspec use"
        raise ChangeError(msg)
    sidecar = root / SIDECARS / f"{change_id}.toml"
    data = dict(read_sidecar(sidecar))
    data[_KEYS[stage]] = today
    if stage is Stage.SPEC:
        data["spec_hash"] = artifact_hash(root, backend, change_id)
    if stage is Stage.PLAN:
        data["plan_hash"] = plan_hash(root, backend, change_id)
        if executor is not None:
            data["executor"] = executor
    write_sidecar(sidecar, data)
    return sidecar
