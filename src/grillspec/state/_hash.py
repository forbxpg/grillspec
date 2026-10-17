"""Fingerprint a change's spec, so an approval means "this text"."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from grillspec.config import Backend

from ._layout import OPENSPEC_CHANGES, log_path

if TYPE_CHECKING:
    from pathlib import Path


def spec_files(root: Path, backend: Backend, change_id: str) -> tuple[Path, ...]:
    """List the files that make up a change's spec.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        tuple[Path, ...] - Superpowers: the spec file. OpenSpec: ``proposal.md``,
            ``design.md`` and ``specs/**/*.md``. Existing files only, sorted by
            their project-relative POSIX path.

    """
    if backend is Backend.SUPERPOWERS:
        candidates = [log_path(root, backend, change_id)]
    else:
        folder = root / OPENSPEC_CHANGES / change_id
        candidates = [
            folder / "proposal.md",
            folder / "design.md",
            *(folder / "specs").glob("**/*.md"),
        ]
    existing = [path for path in candidates if path.is_file()]
    return tuple(sorted(existing, key=lambda path: path.relative_to(root).as_posix()))


def _normalised(text: str) -> str:
    """Normalise text so editors and platforms do not change the fingerprint.

    Args:
        text: str - File text.

    Returns:
        str - Without a BOM, with LF line endings, no trailing whitespace and
            no trailing blank lines (editors add or drop a final newline).

    """
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).rstrip("\n")


def artifact_hash(root: Path, backend: Backend, change_id: str) -> str:
    """Fingerprint a change's spec files.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        str - ``sha256:<hex>`` over each file's relative path and normalised text.

    """
    digest = hashlib.sha256()
    for path in spec_files(root, backend, change_id):
        text = path.read_bytes().decode("utf-8", "replace")
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(_normalised(text).encode() + b"\0")
    return f"sha256:{digest.hexdigest()}"
