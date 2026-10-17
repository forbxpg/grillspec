"""The configuration values and their allowed choices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

VENDOR_NAMES = ("claude", "codex", "cursor-agent", "gemini", "agy", "gigacode")
ROLE_NAMES = ("simplicity", "devil", "risk")
# Vendors whose CLI has no option to choose a model.
NO_MODEL_VENDORS = frozenset({"agy"})
MEMBER_FORMS = "role:<simplicity|devil|risk> or cli:<vendor>[@<model>]"
_ROLE = re.compile(r"role:(" + "|".join(ROLE_NAMES) + r")")
_MODEL = r"(?:@([A-Za-z0-9][A-Za-z0-9._:/-]{0,99}))?"
_CLI = re.compile(r"cli:(" + "|".join(map(re.escape, VENDOR_NAMES)) + r")" + _MODEL)


class Backend(StrEnum):
    """Where specs and plans live and in which format."""

    OPENSPEC = "openspec"
    SUPERPOWERS = "superpowers"


class Depth(StrEnum):
    """How deep the grilling phase goes."""

    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class CouncilMode(StrEnum):
    """Whether grilling consults a council."""

    ASK = "ask"
    YES = "yes"
    NO = "no"


class External(StrEnum):
    """Whether external agent CLIs may sit on the council."""

    ALLOW = "allow"
    NEVER = "never"


@dataclass(frozen=True)
class Member:
    """One council member.

    Attributes:
        kind: str - ``role`` (a subagent) or ``cli`` (an external agent CLI).
        name: str - Role or vendor name.
        model: str | None - Model override for a CLI member.

    """

    kind: str
    name: str
    model: str | None = None


def parse_member(text: str) -> Member:
    """Parse a council member entry.

    Args:
        text: str - ``role:<role>`` or ``cli:<vendor>[@<model>]``.

    Returns:
        Member - The parsed member.

    Raises:
        ValueError: If the entry has neither form, or names a model for a CLI
            without a model option; the model may hold only letters, digits
            and ``._:/-`` and must not start with ``-``.

    """
    role = _ROLE.fullmatch(text)
    if role:
        return Member("role", role.group(1))
    cli = _CLI.fullmatch(text)
    if cli and cli.group(2) and cli.group(1) in NO_MODEL_VENDORS:
        msg = f"{text!r}: {cli.group(1)} has no model option"
        raise ValueError(msg)
    if cli:
        return Member("cli", cli.group(1), cli.group(2))
    vendors = "|".join(VENDOR_NAMES)
    msg = f"{text!r} is not a council member; allowed: {MEMBER_FORMS} ({vendors})"
    raise ValueError(msg)


@dataclass(frozen=True)
class Config:
    """Effective configuration after merging every layer.

    Attributes:
        backend: Backend | None - Spec backend; None until ``init`` ran.
        artifacts_language: str - Language of specs and plans, or ``auto``.
        depth: Depth - Default grilling depth.
        council_enabled: CouncilMode - Whether grilling uses a council.
        council_members: tuple[str, ...] - Default council members.
        council_external: External - Whether external CLIs may be asked.
        council_timeout: int - Seconds each external member may take.
        council_share_project: bool - Run external members in the project
            directory instead of an empty temporary one.
        gates_enabled: bool - Whether phase gates are active.

    """

    backend: Backend | None = None
    artifacts_language: str = "auto"
    depth: Depth = Depth.STANDARD
    council_enabled: CouncilMode = CouncilMode.ASK
    council_members: tuple[str, ...] = ()
    council_external: External = External.ALLOW
    council_timeout: int = 120
    council_share_project: bool = False
    gates_enabled: bool = True
