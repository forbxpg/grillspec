"""Find bundled data in an installed wheel or in a repository checkout."""

from __future__ import annotations

from pathlib import Path

_PACKAGE = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Return the directory that holds ``skills/``, ``hooks/`` and ``templates/``.

    An installed wheel carries them in ``grillspec/_bundled``; a checkout (plugin
    install or development) has them at the repository root.

    Returns:
        Path - The data directory.

    """
    bundled = _PACKAGE / "_bundled"
    if bundled.is_dir():
        return bundled
    return _PACKAGE.parents[1]


def template(name: str) -> str:
    """Read a template shipped with grillspec.

    Args:
        name: str - File name inside ``templates/``.

    Returns:
        str - The template text.

    Raises:
        ValueError: If the name is not a plain file name inside ``templates/``.

    """
    if not name or name != Path(name).name or name in {".", ".."}:
        msg = f"invalid template name: {name!r}"
        raise ValueError(msg)
    return (data_root() / "templates" / name).read_text(encoding="utf-8")


def project_root(start: Path) -> Path:
    """Find the project a command run from ``start`` belongs to.

    The nearest directory, ``start`` included, that holds a ``.grillspec/``
    directory; ``start`` itself when none does (a project not set up yet).

    Args:
        start: Path - Directory the command runs in.

    Returns:
        Path - The project root.

    """
    for candidate in (start, *start.parents):
        if (candidate / ".grillspec").is_dir():
            return candidate
    return start
