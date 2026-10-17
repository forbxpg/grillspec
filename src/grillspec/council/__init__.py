"""The council: ask external agent CLIs about one decision, headless and read-only."""

from __future__ import annotations

from ._contract import extract_contract
from ._proc import killing_on_exit, run_tree
from ._prompt import CouncilError, Payload, parse_payload, render_prompt
from ._run import MemberResult, member_spec, resolve_members, run_members
from ._vendors import (
    INSTRUCTION,
    VENDORS,
    Vendor,
    auth_state,
    build_argv,
    parse_answer,
    resolve_cli,
)

__all__ = (
    "INSTRUCTION",
    "VENDORS",
    "CouncilError",
    "MemberResult",
    "Payload",
    "Vendor",
    "auth_state",
    "build_argv",
    "extract_contract",
    "killing_on_exit",
    "member_spec",
    "parse_answer",
    "parse_payload",
    "render_prompt",
    "resolve_cli",
    "resolve_members",
    "run_members",
    "run_tree",
)
