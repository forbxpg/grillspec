"""Where each backend keeps a change's artifacts."""

from __future__ import annotations

from pathlib import Path

from grillspec.config import Backend

SPECS = Path("docs") / "grillspec" / "specs"
PLANS = Path("docs") / "grillspec" / "plans"
OPENSPEC_CHANGES = Path("openspec") / "changes"


def log_path(root: Path, backend: Backend, change_id: str) -> Path:
    """Return where a change's decision log lives in a backend.

    Args:
        root: Path - Project root.
        backend: Backend - Spec backend.
        change_id: str - Change id.

    Returns:
        Path - The spec file (superpowers) or ``design.md`` (OpenSpec); it may not
            exist yet.

    """
    if backend is Backend.SUPERPOWERS:
        return root / SPECS / f"{change_id}.md"
    return root / OPENSPEC_CHANGES / change_id / "design.md"
