"""The configuration values and their allowed choices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


@dataclass(frozen=True)
class Config:
    """Effective configuration after merging every layer.

    Attributes:
        backend: Backend | None - Spec backend; None until ``init`` ran.
        artifacts_language: str - Language of specs and plans, or ``auto``.
        depth: Depth - Default grilling depth.
        council_enabled: CouncilMode - Whether grilling uses a council.
        council_members: tuple[str, ...] - Default council members.
        gates_enabled: bool - Whether phase gates are active.

    """

    backend: Backend | None = None
    artifacts_language: str = "auto"
    depth: Depth = Depth.STANDARD
    council_enabled: CouncilMode = CouncilMode.ASK
    council_members: tuple[str, ...] = ()
    gates_enabled: bool = True
